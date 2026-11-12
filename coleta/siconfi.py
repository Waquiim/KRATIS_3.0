#!/usr/bin/env python3
"""Coleta os relatórios fiscais do município na API de dados abertos do Siconfi
(Tesouro Nacional) e grava em dados/siconfi/.

São baixados o RREO (bimestral), o RGF (quadrimestral, Executivo e Legislativo)
e o extrato de entregas. O exercício corrente é o ano civil em curso, salvo se
informado com --exercicio. Além dos exercícios comparados, é baixado um ano a
mais para trás, necessário à janela móvel de 12 meses do art. 167-A da CF/88.

Usa somente a biblioteca padrão do Python.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMPOS = ("anexo", "rotulo", "coluna", "cod_conta", "conta", "valor")


def baixar(base: str, recurso: str, params: dict) -> list[dict]:
    """Lê todas as páginas de um recurso da API."""
    itens: list[dict] = []
    offset = 0
    while True:
        q = dict(params)
        if offset:
            q["offset"] = offset
        url = f"{base}/{recurso}?{urllib.parse.urlencode(q)}"
        for tentativa in range(5):
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    pagina = json.load(resp)
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erro:
                if tentativa == 4:
                    raise RuntimeError(f"Falha ao consultar {url}: {erro}") from erro
                time.sleep(2 ** (tentativa + 1))
        itens.extend(pagina.get("items", []))
        if not pagina.get("hasMore"):
            return itens
        offset += pagina.get("limit", len(pagina.get("items", [])) or 5000)
        time.sleep(1)  # a API limita a uma requisição por segundo


def gravar(caminho: Path, meta: dict, itens: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linhas = [[i.get(c) for c in CAMPOS] for i in itens]
    conteudo = {"meta": meta, "campos": list(CAMPOS), "linhas": linhas}
    caminho.write_text(
        json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exercicio", type=int, default=dt.date.today().year,
                    help="exercício corrente (padrão: ano civil em curso)")
    args = ap.parse_args()

    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    base = cfg["siconfi"]["base_url"]
    ente = cfg["cod_ibge"]
    n = cfg["exercicios_comparados"]
    anos = list(range(args.exercicio - n, args.exercicio + 1))  # inclui um ano de base
    destino = RAIZ / "dados" / "siconfi"
    resumo = {"coletado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "exercicio_corrente": args.exercicio, "exercicios": anos, "arquivos": []}

    for ano in anos:
        extrato = baixar(base, "extrato_entregas", {"id_ente": ente, "an_referencia": ano})
        (destino / "extrato").mkdir(parents=True, exist_ok=True)
        (destino / "extrato" / f"{ano}.json").write_text(
            json.dumps(extrato, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        time.sleep(1)

        for bim in range(1, 7):
            itens = baixar(base, "rreo", {
                "an_exercicio": ano, "nr_periodo": bim, "co_tipo_demonstrativo": "RREO",
                "co_esfera": "M", "id_ente": ente})
            time.sleep(1)
            arq = destino / "rreo" / f"{ano}-B{bim}.json"
            if not itens:
                arq.unlink(missing_ok=True)
                continue
            gravar(arq, {"exercicio": ano, "periodo": bim, "demonstrativo": "RREO",
                         "instituicao": itens[0].get("instituicao"),
                         "populacao": itens[0].get("populacao")}, itens)
            resumo["arquivos"].append({"arquivo": str(arq.relative_to(RAIZ)), "linhas": len(itens)})
            print(f"RREO {ano} {bim}º bimestre: {len(itens)} linhas")

        for poder in cfg["siconfi"]["poderes_rgf"]:
            for quad in range(1, 4):
                itens = baixar(base, "rgf", {
                    "an_exercicio": ano, "in_periodicidade": "Q", "nr_periodo": quad,
                    "co_tipo_demonstrativo": "RGF", "co_esfera": "M", "co_poder": poder,
                    "id_ente": ente})
                time.sleep(1)
                arq = destino / "rgf" / f"{ano}-Q{quad}-{poder}.json"
                if not itens:
                    arq.unlink(missing_ok=True)
                    continue
                gravar(arq, {"exercicio": ano, "periodo": quad, "demonstrativo": "RGF",
                             "poder": poder, "instituicao": itens[0].get("instituicao")}, itens)
                resumo["arquivos"].append({"arquivo": str(arq.relative_to(RAIZ)), "linhas": len(itens)})
                print(f"RGF {ano} {quad}º quadrimestre ({poder}): {len(itens)} linhas")

    (destino / "coleta.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Coleta concluída: {len(resumo['arquivos'])} arquivos em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
