"""Inventário dos arquivos baixados do portal de dados abertos do TCE-MG.

O portal (https://dadosabertos.tce.mg.gov.br/) não responde a conexões vindas dos
servidores em nuvem onde este painel foi construído, de modo que a estrutura dos
arquivos não pôde ser examinada de antemão. Por isso esta etapa não presume nomes
de colunas: ela lê qualquer CSV, TXT ou JSON colocado em dados/tce-mg (inclusive
dentro de ZIP), identifica separador, codificação e tipo de cada coluna, soma as
colunas numéricas e guarda uma amostra. Com os arquivos reais no repositório, o
passo seguinte é mapear as colunas para os indicadores e para as regras que hoje
aparecem como "não avaliadas".
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "dados" / "tce-mg"
TABULARES = {".csv", ".txt", ".tsv"}
AMOSTRA = 15
MAX_LINHAS = 2_000_000


def _texto(bruto: bytes) -> tuple[str, str]:
    for cod in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return bruto.decode(cod), cod
        except UnicodeDecodeError:
            continue
    return bruto.decode("latin-1", "replace"), "latin-1"


def _numero(s: str) -> float | None:
    s = s.strip().replace("R$", "").strip()
    if not s or not re.fullmatch(r"-?[\d.,]+", s):
        return None
    if "," in s:  # formato brasileiro: 1.234,56
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _tabela(nome: str, bruto: bytes) -> dict:
    texto, cod = _texto(bruto)
    inicio = texto[:20000]
    try:
        sep = csv.Sniffer().sniff(inicio, delimiters=";,|\t").delimiter
    except csv.Error:
        sep = max(";,|\t", key=inicio.count)
    leitor = csv.reader(io.StringIO(texto), delimiter=sep)
    cab = next(leitor, [])
    cab = [c.strip() or f"coluna_{i + 1}" for i, c in enumerate(cab)]
    n = len(cab)
    numeros = [0] * n
    preenchidos = [0] * n
    somas = [0.0] * n
    valores = [Counter() for _ in range(n)]
    amostra, linhas = [], 0
    for linha in leitor:
        if not any(c.strip() for c in linha):
            continue
        linhas += 1
        if linhas > MAX_LINHAS:
            break
        if len(amostra) < AMOSTRA:
            amostra.append([c.strip()[:80] for c in linha[:n]])
        for i, c in enumerate(linha[:n]):
            c = c.strip()
            if not c:
                continue
            preenchidos[i] += 1
            v = _numero(c)
            if v is not None:
                numeros[i] += 1
                somas[i] += v
            if len(valores[i]) < 2000:
                valores[i][c[:60]] += 1
    colunas = []
    for i, c in enumerate(cab):
        numerica = preenchidos[i] > 0 and numeros[i] / preenchidos[i] > 0.98
        # códigos e identificadores também são numéricos; soma só faz sentido com decimais
        col = {"nome": c, "preenchidos": preenchidos[i],
               "tipo": "número" if numerica else "texto", "distintos": len(valores[i])}
        if numerica:
            col["soma"] = round(somas[i], 2)
        elif 0 < len(valores[i]) <= 40:
            col["valores"] = [[k, q] for k, q in valores[i].most_common(8)]
        colunas.append(col)
    return {"arquivo": nome, "codificacao": cod, "separador": {"\t": "tab"}.get(sep, sep),
            "linhas": linhas, "colunas": colunas, "amostra": amostra}


def _json(nome: str, bruto: bytes) -> dict:
    texto, cod = _texto(bruto)
    try:
        obj = json.loads(texto)
    except json.JSONDecodeError as erro:
        return {"arquivo": nome, "erro": f"JSON inválido: {erro}"}
    lista = obj
    if isinstance(obj, dict):  # procura a primeira lista de registros
        lista = next((v for v in obj.values() if isinstance(v, list)), [obj])
    registros = [r for r in lista if isinstance(r, dict)]
    if not registros:
        return {"arquivo": nome, "codificacao": cod, "linhas": 0, "colunas": [], "amostra": []}
    cab = list(dict.fromkeys(k for r in registros[:500] for k in r))
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";")
    w.writerow(cab)
    for r in registros:
        w.writerow(["" if r.get(k) is None else str(r.get(k)) for k in cab])
    t = _tabela(nome, saida.getvalue().encode("utf-8"))
    t["codificacao"], t["separador"] = cod, "json"
    return t


def _ler(nome: str, bruto: bytes) -> dict | None:
    ext = Path(nome).suffix.lower()
    if ext in TABULARES:
        return _tabela(nome, bruto)
    if ext == ".json":
        return _json(nome, bruto)
    return None


def inventario() -> dict:
    arquivos, ignorados = [], []
    if PASTA.exists():
        for arq in sorted(p for p in PASTA.rglob("*") if p.is_file()):
            rel = str(arq.relative_to(PASTA))
            if arq.name.startswith(".") or arq.name.upper().startswith("LEIAME"):
                continue
            ano = next((int(a) for a in re.findall(r"(?<!\d)(20\d\d)(?!\d)", rel)), None)
            itens = []
            if arq.suffix.lower() == ".zip":
                try:
                    with zipfile.ZipFile(arq) as z:
                        for m in z.infolist():
                            if m.is_dir():
                                continue
                            t = _ler(f"{rel}/{m.filename}", z.read(m))
                            (itens if t else ignorados).append(t or f"{rel}/{m.filename}")
                except zipfile.BadZipFile:
                    ignorados.append(rel)
            else:
                t = _ler(rel, arq.read_bytes())
                (itens if t else ignorados).append(t or rel)
            for t in itens:
                t["exercicio"] = ano
                t["bytes"] = arq.stat().st_size
                arquivos.append(t)
    return {"pasta": "dados/tce-mg", "arquivos": arquivos, "ignorados": ignorados,
            "total_linhas": sum(a.get("linhas", 0) for a in arquivos)}
