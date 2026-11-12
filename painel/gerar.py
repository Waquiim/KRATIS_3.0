#!/usr/bin/env python3
"""Gera site/dados/painel.json a partir dos dados coletados.

Uso: python3 -m painel.gerar
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from . import dados as d
from . import regras, tce_mg

SAIDA = d.RAIZ / "site" / "dados"


def _ultimo_quad(base, ano, poder, ate_bim=None):
    quads = [q for (a, q, p) in base["rgf"] if a == ano and p == poder
             and (ate_bim is None or q * 2 <= ate_bim)]
    return max(quads) if quads else None


def _exercicio(base, ano):
    bims = sorted(b for (a, b) in base["rreo"] if a == ano)
    if not bims:
        return None
    bim = bims[-1]
    r = base["rreo"][(ano, bim)]
    qe, ql = _ultimo_quad(base, ano, "E"), _ultimo_quad(base, ano, "L")
    ex = {
        "bimestre": bim, "quadrimestre": qe,
        "execucao": d.execucao(r), "funcoes": d.funcoes(r), "fiscais": d.fiscais_rreo(r),
        "pessoal_executivo": d.pessoal(base["rgf"][(ano, qe, "E")]) if qe else None,
        "pessoal_legislativo": d.pessoal(base["rgf"][(ano, ql, "L")]) if ql else None,
        "divida": d.divida(base["rgf"][(ano, qe, "E")], qe) if qe else None,
        "caixa_por_fonte": d.caixa_por_fonte(base["rgf"][(ano, 3, "E")])
        if (ano, 3, "E") in base["rgf"] else [],
        "bimestres": [],
    }
    for b in bims:
        e = d.execucao(base["rreo"][(ano, b)])
        ex["bimestres"].append({
            "bimestre": b,
            "receita_realizada": e["receita_total"]["realizada"],
            "despesa_empenhada": e["despesa_total"]["empenhada"],
            "despesa_liquidada": e["despesa_total"]["liquidada"],
            "despesa_paga": e["despesa_total"]["paga"],
        })
    return ex


def _comparativo(base, anos, serie):
    """Mesmo bimestre nos três exercícios, mais o fechamento dos exercícios encerrados."""
    atual = anos[-1]
    bim = max(b for (a, b) in base["rreo"] if a == atual)

    def ponto(ano, b):
        r = base["rreo"].get((ano, b))
        if r is None:
            return None
        e, x = d.execucao(r), d.fiscais_rreo(r)
        q = _ultimo_quad(base, ano, "E", b)
        p = d.pessoal(base["rgf"][(ano, q, "E")]) if q else {}
        s = next((s for s in serie if s["ano"] == ano and s["bimestre"] == b), None)
        v = {
            "Receita total realizada": e["receita_total"]["realizada"],
            "Receita corrente": d.soma(e["receita_corrente"]["realizada"],
                                       e["receita_corrente_intra"]["realizada"]),
            "Receita de capital": e["receita_capital"]["realizada"],
            "Despesa empenhada": e["despesa_total"]["empenhada"],
            "Despesa liquidada": e["despesa_total"]["liquidada"],
            "Despesa paga": e["despesa_total"]["paga"],
            "Despesa corrente liquidada": d.soma(e["despesa_corrente"]["liquidada"],
                                                 e["despesa_corrente_intra"]["liquidada"]),
            "Despesa de capital liquidada": e["despesa_capital"]["liquidada"],
            "Resultado da execução (receita menos empenho)": e["resultado_orcamentario"],
            "Receita corrente líquida em 12 meses": x["rcl_12m"],
            "Despesa corrente sobre receita corrente (art. 167-A)":
                s["indice"] * 100 if s else None,
            "Despesa com pessoal do Executivo sobre a RCL": p.get("percentual"),
            "Dívida consolidada": x["divida_consolidada"],
            "Resultado primário": x["resultado_primario"],
            "Restos a pagar a pagar": x["rp_total"]["a_pagar"],
        }
        for o in e["origens"]:
            v["rec:" + o["nome"]] = o["realizada"]
        for g in e["grupos"]:
            v["grp:" + g["nome"]] = g["liquidada"]
        for f in d.funcoes(r):
            v["fun:" + f["nome"]] = f.get("liquidada")
        return v

    no_bim = {ano: ponto(ano, bim) for ano in anos}
    fecho = {ano: ponto(ano, 6) for ano in anos if (ano, 6) in base["rreo"]}
    chaves = list(dict.fromkeys(k for p in list(no_bim.values()) + list(fecho.values())
                                if p for k in p))
    secoes = {"rec:": "Receita por origem", "grp:": "Despesa liquidada por grupo",
              "fun:": "Despesa liquidada por função"}
    pcts = {"Despesa corrente sobre receita corrente (art. 167-A)",
            "Despesa com pessoal do Executivo sobre a RCL"}
    ordem = [None] + list(secoes)
    chaves.sort(key=lambda k: ordem.index(k[:4] if k[:4] in secoes else None))  # estável
    linhas = []
    for k in chaves:
        prefixo = k[:4] if k[:4] in secoes else None
        linhas.append({
            "secao": secoes[prefixo] if prefixo else "Indicadores gerais",
            "nome": k[4:] if prefixo else k,
            "tipo": "pct" if k in pcts else "brl",
            "no_bimestre": {str(a): (no_bim[a] or {}).get(k) for a in anos},
            "fechamento": {str(a): fecho[a].get(k) for a in fecho},
        })
    return {"bimestre": bim, "exercicios": anos, "linhas": linhas}


def main() -> int:
    cfg = json.loads((d.RAIZ / "config.json").read_text(encoding="utf-8"))
    base = d.carregar()
    if not base["rreo"]:
        print("Nenhum relatório em dados/siconfi. Rode antes: python3 coleta/siconfi.py")
        return 1
    atual = base["coleta"].get("exercicio_corrente") or max(a for a, _ in base["rreo"])
    if not any(a == atual for a, _ in base["rreo"]):
        atual = max(a for a, _ in base["rreo"])  # início de ano, sem relatório ainda
    anos = [atual - i for i in range(cfg["exercicios_comparados"] - 1, -1, -1)]
    coletado = base["coleta"].get("coletado_em")
    hoje = dt.date.fromisoformat(coletado[:10]) if coletado else dt.date.today()

    serie = d.art167a(base, anos)
    inv = tce_mg.inventario()
    achados = regras.apurar(base, anos, serie, hoje, bool(inv["arquivos"]))
    r_atual = base["rreo"][(atual, max(b for (a, b) in base["rreo"] if a == atual))]

    painel = {
        "meta": {
            "municipio": cfg["municipio"], "uf": cfg["uf"], "cod_ibge": cfg["cod_ibge"],
            "populacao": r_atual.meta.get("populacao"),
            "exercicio_corrente": atual, "exercicios": anos,
            "coletado_em": coletado,
            "gerado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "portal_tce_mg": cfg["tce_mg"]["portal"],
        },
        "exercicios": {str(a): _exercicio(base, a) for a in anos},
        "comparativo": _comparativo(base, anos, serie),
        "art167a": {"serie": serie, "limite_ajuste": 95, "limite_facultativo": 85},
        "inconsistencias": achados,
        "tce_mg": {"arquivos": len(inv["arquivos"]), "linhas": inv["total_linhas"],
                   "sonda": _sonda()},
    }
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "painel.json").write_text(
        json.dumps(painel, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (SAIDA / "tce-mg.json").write_text(
        json.dumps(inv, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    cont = {}
    for a in achados:
        if a["exercicio"] == atual:
            cont[a["situacao"]] = cont.get(a["situacao"], 0) + 1
    print(f"Painel de {cfg['municipio']}/{cfg['uf']} gerado para {anos}.")
    print(f"Achados de {atual}: {cont}")
    print(f"Arquivos do TCE-MG inventariados: {len(inv['arquivos'])}")
    return 0


def _sonda():
    """Resultado do teste de acesso ao portal do TCE-MG, quando o fluxo o registra."""
    arq = d.RAIZ / "dados" / "tce-mg" / ".sonda.json"
    if arq.exists():
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


if __name__ == "__main__":
    sys.exit(main())
