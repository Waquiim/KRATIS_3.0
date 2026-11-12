"""Leitura dos relatórios coletados do Siconfi e apuração dos indicadores.

Os valores vêm do RREO (bimestral) e do RGF (quadrimestral) tal como o
município os declarou ao Tesouro Nacional. Nenhum número é estimado aqui: quando
uma linha não existe no relatório, o indicador fica vazio (None).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SICONFI = RAIZ / "dados" / "siconfi"

FUNCOES = [
    "Legislativa", "Judiciária", "Essencial à Justiça", "Administração", "Defesa Nacional",
    "Segurança Pública", "Relações Exteriores", "Assistência Social", "Previdência Social",
    "Saúde", "Trabalho", "Educação", "Cultura", "Direitos da Cidadania", "Urbanismo",
    "Habitação", "Saneamento", "Gestão Ambiental", "Ciência e Tecnologia", "Agricultura",
    "Organização Agrária", "Indústria", "Comércio e Serviços", "Comunicações", "Energia",
    "Transporte", "Desporto e Lazer", "Encargos Especiais",
]

ORIGENS_RECEITA = [
    ("ReceitaTributaria", "Impostos, taxas e contribuições de melhoria", "corrente"),
    ("ReceitaDeContribuicoes", "Contribuições", "corrente"),
    ("ReceitaPatrimonial", "Receita patrimonial", "corrente"),
    ("ReceitaAgropecuaria", "Receita agropecuária", "corrente"),
    ("ReceitaIndustrial", "Receita industrial", "corrente"),
    ("ReceitaDeServicos", "Receita de serviços", "corrente"),
    ("TransferenciasCorrentes", "Transferências correntes", "corrente"),
    ("OutrasReceitasCorrentes", "Outras receitas correntes", "corrente"),
    ("ReceitasDeOperacoesDeCredito", "Operações de crédito", "capital"),
    ("AlienacaoDeBens", "Alienação de bens", "capital"),
    ("AmortizacoesDeEmprestimos", "Amortização de empréstimos", "capital"),
    ("TransferenciasDeCapital", "Transferências de capital", "capital"),
    ("OutrasReceitasDeCapital", "Outras receitas de capital", "capital"),
]

GRUPOS_DESPESA = [
    ("PessoalEEncargosSociais", "Pessoal e encargos sociais", "corrente"),
    ("JurosEEncargosDaDivida", "Juros e encargos da dívida", "corrente"),
    ("OutrasDespesasCorrentes", "Outras despesas correntes", "corrente"),
    ("Investimentos", "Investimentos", "capital"),
    ("InversoesFinanceiras", "Inversões financeiras", "capital"),
    ("AmortizacaoDaDivida", "Amortização da dívida", "capital"),
]


def norm(texto: str) -> str:
    """Maiúsculas, sem acentos e com espaços simples, para comparar rótulos."""
    sem = unicodedata.normalize("NFKD", texto or "")
    sem = "".join(c for c in sem if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem).strip().upper()


class Relatorio:
    """Um arquivo de RREO ou RGF, com busca por anexo, conta e coluna."""

    def __init__(self, caminho: Path):
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        self.meta = bruto["meta"]
        self.linhas = [dict(zip(bruto["campos"], l)) for l in bruto["linhas"]]
        self._idx: dict[tuple[str, str], list[dict]] = {}
        for l in self.linhas:
            l["_col"] = norm(l["coluna"])
            l["_conta"] = norm(l["conta"])
            self._idx.setdefault((l["anexo"][-2:], l["cod_conta"]), []).append(l)

    def tem_anexo(self, anexo: str) -> bool:
        return any(a == anexo for a, _ in self._idx)

    def linhas_de(self, anexo: str, cod: str | None = None) -> list[dict]:
        if cod is not None:
            return self._idx.get((anexo, cod), [])
        return [l for (a, _), ls in self._idx.items() if a == anexo for l in ls]

    def v(self, anexo: str, cod: str, coluna: str, conta: str | None = None,
          rotulo: str | None = None) -> float | None:
        """Valor da primeira linha cuja coluna começa por `coluna` (normalizada)."""
        col = norm(coluna)
        alvo = norm(conta) if conta else None
        for l in self._idx.get((anexo, cod), []):
            if not l["_col"].startswith(col):
                continue
            if alvo and not l["_conta"].startswith(alvo):
                continue
            if rotulo and norm(l["rotulo"]) != norm(rotulo):
                continue
            return l["valor"]
        return None


def carregar() -> dict:
    """Carrega tudo o que foi coletado: {'rreo': {(ano,bim): Relatorio}, 'rgf': {...}}."""
    base = {"rreo": {}, "rgf": {}, "extrato": {}, "coleta": {}}
    for arq in sorted((SICONFI / "rreo").glob("*.json")):
        ano, bim = arq.stem.split("-B")
        base["rreo"][(int(ano), int(bim))] = Relatorio(arq)
    for arq in sorted((SICONFI / "rgf").glob("*.json")):
        ano, quad, poder = re.match(r"(\d+)-Q(\d)-(\w)", arq.stem).groups()
        base["rgf"][(int(ano), int(quad), poder)] = Relatorio(arq)
    for arq in sorted((SICONFI / "extrato").glob("*.json")):
        base["extrato"][int(arq.stem)] = json.loads(arq.read_text(encoding="utf-8"))
    coleta = SICONFI / "coleta.json"
    if coleta.exists():
        base["coleta"] = json.loads(coleta.read_text(encoding="utf-8"))
    return base


def soma(*valores: float | None) -> float | None:
    """Soma que trata None como zero, mas devolve None se tudo for None."""
    presentes = [v for v in valores if v is not None]
    return round(sum(presentes), 2) if presentes else None


def razao(num: float | None, den: float | None) -> float | None:
    if num is None or not den:
        return None
    return num / den


# ---------------------------------------------------------------- RREO

REC_REAL = "ATE O BIMESTRE"
EMP = "DESPESAS EMPENHADAS ATE O BIMESTRE"
LIQ = "DESPESAS LIQUIDADAS ATE O BIMESTRE"
PAGO = "DESPESAS PAGAS ATE O BIMESTRE"


def execucao(r: Relatorio) -> dict:
    """Balanço orçamentário (Anexo 1 do RREO), valores acumulados até o bimestre."""
    a = "01"

    def rec(cod):
        return {"previsao_inicial": r.v(a, cod, "PREVISAO INICIAL"),
                "previsao_atualizada": r.v(a, cod, "PREVISAO ATUALIZADA"),
                "realizada": r.v(a, cod, REC_REAL)}

    def desp(cod):
        return {"dotacao_inicial": r.v(a, cod, "DOTACAO INICIAL"),
                "dotacao_atualizada": r.v(a, cod, "DOTACAO ATUALIZADA"),
                "empenhada": r.v(a, cod, EMP), "liquidada": r.v(a, cod, LIQ),
                "paga": r.v(a, cod, PAGO)}

    e = {
        "receita_total": rec("TotalReceitas"),
        "receita_exceto_intra": rec("ReceitasExcetoIntraOrcamentarias"),
        "receita_intra": rec("ReceitasIntraOrcamentariasTotal"),
        "receita_corrente": rec("ReceitasCorrentes"),
        "receita_corrente_intra": rec("ReceitasCorrentesIntra"),
        "receita_capital": rec("ReceitasDeCapital"),
        "despesa_total": desp("TotalDespesas"),
        "despesa_exceto_intra": desp("DespesasExcetoIntraOrcamentarias"),
        "despesa_intra": desp("DespesasIntraOrcamentariasTotal"),
        "despesa_corrente": desp("DespesasCorrentes"),
        "despesa_corrente_intra": desp("DespesasCorrentesIntra"),
        "despesa_capital": desp("DespesasDeCapital"),
        "reserva_contingencia": desp("ReservaDeContingencia"),
        "superavit_financeiro_utilizado": (
            r.v(a, "SuperavitFinanceiro", REC_REAL)
            or r.v(a, "SaldoDeExerciciosAnterioresUtilizadosParaCreditosAdicionais", REC_REAL)
            or r.v(a, "SuperavitFinanceiro", "PREVISAO ATUALIZADA")
            or r.v(a, "SaldoDeExerciciosAnterioresUtilizadosParaCreditosAdicionais",
                   "PREVISAO ATUALIZADA")),
        "origens": [dict(nome=nome, categoria=cat, **rec(cod))
                    for cod, nome, cat in ORIGENS_RECEITA
                    if any(v is not None for v in rec(cod).values())],
        "grupos": [dict(nome=nome, categoria=cat, **desp(cod))
                   for cod, nome, cat in GRUPOS_DESPESA
                   if any(v is not None for v in desp(cod).values())],
    }
    rt, dt = e["receita_total"]["realizada"], e["despesa_total"]
    e["resultado_orcamentario"] = None if rt is None or dt["empenhada"] is None \
        else round(rt - dt["empenhada"], 2)
    return e


def funcoes(r: Relatorio) -> list[dict]:
    """Despesa por função (Anexo 2 do RREO), exceto intraorçamentária."""
    alvo = {norm(f): f for f in FUNCOES}
    saida: dict[str, dict] = {}
    for l in r.linhas_de("02"):
        if "EXCETO" not in norm(l["rotulo"]) or l["_conta"] not in alvo:
            continue
        f = saida.setdefault(alvo[l["_conta"]], {"nome": alvo[l["_conta"]]})
        if l["_col"].startswith("DOTACAO ATUALIZADA"):
            f.setdefault("dotacao_atualizada", l["valor"])
        elif l["_col"].startswith(EMP):
            f.setdefault("empenhada", l["valor"])
        elif l["_col"].startswith(LIQ):
            f.setdefault("liquidada", l["valor"])
    return sorted(saida.values(), key=lambda f: -(f.get("empenhada") or 0))


def fiscais_rreo(r: Relatorio) -> dict:
    """RCL, resultado primário, dívida, restos a pagar e previdência (Anexos 3, 6, 14)."""
    meses = [r.v("03", "RREO3ReceitaCorrenteLiquida", f"<MR-{i}>") for i in range(11, 0, -1)]
    meses.append(r.v("03", "RREO3ReceitaCorrenteLiquida", "<MR>"))

    def rp(cod):
        return {"inscritos": r.v("14", cod, "INSCRICAO"),
                "cancelados": r.v("14", cod, "CANCELAMENTO"),
                "pagos": r.v("14", cod, "PAGAMENTO"),
                "a_pagar": r.v("14", cod, "SALDO A PAGAR")}

    return {
        "rcl_12m": r.v("03", "RREO3ReceitaCorrenteLiquida", "TOTAL (ULTIMOS 12 MESES)"),
        "rcl_mensal": meses,
        "receita_corrente_bruta_12m": r.v(
            "03", "ReceitasCorrentesLiquidasExcetoTransferenciasEFUNDEB",
            "TOTAL (ULTIMOS 12 MESES)"),
        "resultado_primario": r.v("06", "ResultadoPrimarioSemRPPSAcimaDaLinha", "VALOR"),
        "resultado_nominal": r.v("06", "ResultadoNominalAbaixoDaLinhaSemRPPS", "VALOR"),
        "divida_consolidada": r.v("06", "DividaConsolidada", "ATE O BIMESTRE"),
        "divida_consolidada_liquida": r.v("06", "DividaConsolidadaLiquida", "ATE O BIMESTRE"),
        "rp_processados": rp("RestosAPagarProcessadosDemonstrativoSimplificado"),
        "rp_nao_processados": rp("RestosAPagarNaoProcessadosDemonstrativoSimplificado"),
        "rp_total": rp("TotalRestosAPagarDemonstrativoSimplificado"),
        "previdencia": {
            "capitalizacao": r.v(
                "14", "ResultadoPrevidenciarioRPPSPrevidenciarioDemonstrativoSimplificado",
                "ATE O BIMESTRE"),
            "reparticao": r.v(
                "14", "ResultadoPrevidenciarioRPPSFinanceiroDemonstrativoSimplificado",
                "ATE O BIMESTRE"),
        },
        "a14_receita_realizada": r.v(
            "14", "ReceitasRealizadasDemonstrativoSimplificadoBalancoOrcamentario",
            "ATE O BIMESTRE"),
        "a14_despesa_empenhada": r.v(
            "14", "DespesasEmpenhadasDemonstrativoSimplificadoBalancoOrcamentario",
            "ATE O BIMESTRE"),
    }


# ---------------------------------------------------------------- RGF

def pessoal(r: Relatorio) -> dict:
    """Despesa com pessoal (Anexo 1 do RGF) do Poder a que o relatório se refere."""
    a = "01"
    return {
        "despesa_total": r.v(a, "DespesaComPessoalTotal", "VALOR"),
        "percentual": r.v(a, "DespesaComPessoalTotal", "% SOBRE A RCL"),
        "limite_maximo_pct": r.v(a, "LimiteMaximoDespesaComPessoalTotal", "% SOBRE A RCL"),
        "limite_prudencial_pct": r.v(a, "LimitePrudencialDespesaComPessoalTotal", "% SOBRE A RCL"),
        "limite_alerta_pct": r.v(a, "LimiteDeAlertaDespesaComPessoalTotal", "% SOBRE A RCL"),
        "rcl": r.v(a, "ReceitaCorrenteLiquidaLimiteLegal", "VALOR"),
        "rcl_ajustada": r.v(a, "ReceitaCorrenteLiquidaAjustada", "VALOR"),
    }


def divida(r: Relatorio, quad: int) -> dict:
    """Dívida consolidada (Anexo 2 do RGF do Executivo)."""
    col = f"ATE O {quad}"
    return {
        "divida_consolidada": r.v("02", "DividaConsolidada", col),
        "divida_consolidada_liquida": r.v("02", "DividaConsolidadaLiquida", col),
        "dcl_pct_rcl": r.v("02", "PercentualDaDCLSobreARCL", col),
        "limite": r.v("02", "LimiteDefinidoPorResolucaoDoSenadoFederal", col),
        "rcl": r.v("02", "RGF2ReceitaCorrenteLiquida", col),
    }


def caixa_por_fonte(r: Relatorio) -> list[dict]:
    """Disponibilidade de caixa líquida por fonte (Anexo 5 do RGF, último quadrimestre)."""
    saida = []
    for l in r.linhas_de("05", "DisponibilidadeDeCaixaLiquidaAposRP"):
        if l["_conta"].startswith("TOTAL"):
            continue
        saida.append({"fonte": l["conta"], "valor": l["valor"]})
    return saida


# ---------------------------------------------------------------- art. 167-A

def art167a(base: dict, anos: list[int]) -> list[dict]:
    """Relação despesa corrente / receita corrente em 12 meses, a cada bimestre.

    A janela móvel é montada com os acumulados do Anexo 1 do RREO:
    12 meses até o bimestre b do ano A = acumulado(A, b) + acumulado(A-1, 6) - acumulado(A-1, b).
    """
    def acum(ano, bim):
        r = base["rreo"].get((ano, bim))
        if r is None:
            return None
        rc = r.v("01", "ReceitasCorrentes", REC_REAL)
        rci = r.v("01", "ReceitasCorrentesIntra", REC_REAL) or 0.0
        dl = r.v("01", "DespesasCorrentes", LIQ)
        dli = r.v("01", "DespesasCorrentesIntra", LIQ) or 0.0
        de = r.v("01", "DespesasCorrentes", EMP)
        dei = r.v("01", "DespesasCorrentesIntra", EMP) or 0.0
        if None in (rc, dl, de):
            return None
        return {"rc": rc, "rc_t": rc + rci, "dl": dl, "dl_t": dl + dli,
                "de": de, "de_t": de + dei}

    serie = []
    for ano in anos:
        for bim in range(1, 7):
            atual = acum(ano, bim)
            if atual is None:
                continue
            if bim == 6:
                j = atual
            else:
                fim, igual = acum(ano - 1, 6), acum(ano - 1, bim)
                if fim is None or igual is None:
                    continue
                j = {k: atual[k] + fim[k] - igual[k] for k in atual}
            serie.append({
                "ano": ano, "bimestre": bim,
                "receita_corrente": round(j["rc_t"], 2),
                "despesa_corrente_liquidada": round(j["dl_t"], 2),
                "despesa_corrente_empenhada": round(j["de_t"], 2),
                "indice": j["dl_t"] / j["rc_t"],
                "indice_empenhada": j["de_t"] / j["rc_t"],
                "indice_exceto_intra": j["dl"] / j["rc"],
                "indice_empenhada_exceto_intra": j["de"] / j["rc"],
            })
    return serie
