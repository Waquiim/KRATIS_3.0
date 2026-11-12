"""Regras de inconsistência: pontos que tendem a ser apontados pelo controle externo.

Cada regra devolve um achado com situação:
  apontamento    indício objetivo de descumprimento ou de dado incoerente
  atencao        risco que pede acompanhamento ou justificativa
  regular        verificado e dentro do parâmetro
  nao_avaliado   depende de dado ainda não disponível no painel

As regras trabalham sobre os dados que o próprio município declarou. Um achado é
um indício para o controle interno conferir na origem, não um juízo de mérito.
"""
from __future__ import annotations

import datetime as dt

from . import dados as d

TOL = 1.00  # tolerância, em reais, para diferenças de arredondamento


def brl(v: float | None) -> str:
    if v is None:
        return "não informado"
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {s}" if v < 0 else f"R$ {s}"


def pct(v: float | None, casas: int = 2) -> str:
    if v is None:
        return "não informado"
    return f"{v:.{casas}f}".replace(".", ",") + "%"


def achado(id_, grupo, titulo, ano, periodo, situacao, fundamento, descricao,
           evidencias=None, providencia=""):
    return {"id": id_, "grupo": grupo, "titulo": titulo, "exercicio": ano,
            "periodo": periodo, "situacao": situacao, "fundamento": fundamento,
            "descricao": descricao, "evidencias": evidencias or [],
            "providencia": providencia}


G_LIM = "Limites constitucionais e da LRF"
G_EXE = "Execução orçamentária e financeira"
G_CON = "Consistência dos dados declarados"
G_PRA = "Prazos e transparência"
G_TCE = "Escopo do TCE-MG que depende dos dados do SICOM"


def _ultimo(base, chave, ano, poder=None):
    if chave == "rreo":
        bims = [b for (a, b) in base["rreo"] if a == ano]
        return max(bims) if bims else None
    quads = [q for (a, q, p) in base["rgf"] if a == ano and p == poder]
    return max(quads) if quads else None


def _per_b(ano, bim):
    return f"{bim}º bimestre de {ano}"


def _per_q(ano, quad):
    return f"{quad}º quadrimestre de {ano}"


# ------------------------------------------------------------ limites

def regra_pessoal(base, ano, poder, serie=None):
    nome = "Executivo" if poder == "E" else "Legislativo"
    quad = _ultimo(base, "rgf", ano, poder)
    idr = f"pessoal-{poder.lower()}"
    fund = ("LRF, arts. 19, III, e 20, III; alerta no art. 59, § 1º, II; "
            "limite prudencial no art. 22, parágrafo único; recondução no art. 23")
    if quad is None:
        return achado(idr, G_LIM, f"Despesa com pessoal do {nome}", ano, str(ano),
                      "nao_avaliado", fund, "Não há RGF deste Poder no exercício.")
    p = d.pessoal(base["rgf"][(ano, quad, poder)])
    v, mx, pr, al = (p["percentual"], p["limite_maximo_pct"],
                     p["limite_prudencial_pct"], p["limite_alerta_pct"])
    ev = [["Despesa total com pessoal", brl(p["despesa_total"])],
          ["RCL ajustada informada", brl(p["rcl_ajustada"])],
          ["Percentual apurado", pct(v)],
          ["Alerta / prudencial / máximo", f"{pct(al, 1)} / {pct(pr, 1)} / {pct(mx, 1)}"]]
    if None in (v, mx, pr, al):
        sit, txt = "nao_avaliado", "O RGF não traz o percentual ou os limites."
    elif v > mx:
        sit, txt = "apontamento", (
            f"A despesa com pessoal declarada ({pct(v)}) supera o limite máximo de {pct(mx, 1)} "
            "da RCL ajustada. O excedente deve ser eliminado nos dois quadrimestres seguintes, "
            "com ao menos um terço no primeiro, e incidem de imediato as vedações do art. 22.")
    elif v > pr:
        sit, txt = "apontamento", (
            f"A despesa com pessoal ({pct(v)}) supera o limite prudencial de {pct(pr, 1)}. "
            "Ficam vedados aumento de remuneração, criação de cargo, alteração de carreira com "
            "aumento de despesa, provimento (salvo reposição em educação, saúde e segurança) e "
            "hora extra.")
    elif v > al:
        sit, txt = "atencao", (
            f"A despesa com pessoal ({pct(v)}) ultrapassou o limite de alerta de {pct(al, 1)}, "
            "situação em que o Tribunal de Contas emite alerta ao Poder.")
    else:
        sit, txt = "regular", f"Despesa com pessoal em {pct(v)}, abaixo do limite de alerta."
    # a RCL declarada pode estar errada; nesse caso o percentual publicado não é confiável
    ponto = next((s for s in serie or [] if s["ano"] == ano and s["bimestre"] == quad * 2), None)
    if ponto and p["rcl"] and not 0.75 <= p["rcl"] / ponto["receita_corrente"] <= 1.05:
        outro = base["rgf"].get((ano, quad, "L" if poder == "E" else "E"))
        alt = d.pessoal(outro)["rcl_ajustada"] if outro else None
        txt += (" Ressalva: a RCL usada neste cálculo é incoerente com a receita corrente do "
                "mesmo período (ver o achado sobre a coerência da RCL), de modo que o "
                "percentual publicado não é confiável.")
        if alt and p["despesa_total"]:
            txt += (f" Com a RCL ajustada informada pelo outro Poder ({brl(alt)}), o "
                    f"percentual seria de {pct(p['despesa_total'] / alt * 100)}.")
    return achado(idr, G_LIM, f"Despesa com pessoal do {nome}", ano, _per_q(ano, quad), sit,
                  fund, txt, ev,
                  "Conferir a RCL usada no cálculo e a composição da despesa com pessoal "
                  "(terceirização de mão de obra, inativos custeados com recursos vinculados "
                  "e decisões judiciais)." if sit != "regular" else "")


def regra_divida(base, ano):
    quad = _ultimo(base, "rgf", ano, "E")
    fund = "Resolução do Senado Federal nº 40/2001, art. 3º, II; LRF, arts. 31 e 59, § 1º, III"
    if quad is None:
        return achado("divida", G_LIM, "Dívida consolidada líquida", ano, str(ano),
                      "nao_avaliado", fund, "Não há RGF do Executivo no exercício.")
    x = d.divida(base["rgf"][(ano, quad, "E")], quad)
    v = x["dcl_pct_rcl"]
    ev = [["Dívida consolidada", brl(x["divida_consolidada"])],
          ["Dívida consolidada líquida", brl(x["divida_consolidada_liquida"])],
          ["DCL sobre a RCL ajustada", pct(v)], ["Limite", "120,00%"]]
    if v is None:
        sit, txt = "nao_avaliado", "O RGF não informa o percentual da DCL sobre a RCL."
    elif v > 120:
        sit, txt = "apontamento", f"A DCL ({pct(v)} da RCL) supera o limite de 120%."
    elif v > 108:
        sit, txt = "atencao", f"A DCL ({pct(v)} da RCL) supera 90% do limite (alerta)."
    else:
        sit, txt = "regular", (
            f"DCL em {pct(v)} da RCL. Valor negativo indica disponibilidade de caixa superior "
            "à dívida consolidada." if v < 0 else f"DCL em {pct(v)} da RCL, dentro do limite.")
    return achado("divida", G_LIM, "Dívida consolidada líquida", ano, _per_q(ano, quad),
                  sit, fund, txt, ev)


def regra_167a(serie, ano):
    pontos = [s for s in serie if s["ano"] == ano]
    fund = "CF/88, art. 167-A, caput e §§ 1º, 4º e 6º (EC nº 109/2021)"
    if not pontos:
        return achado("art167a", G_LIM, "Despesa corrente sobre receita corrente", ano,
                      str(ano), "nao_avaliado", fund,
                      "Faltam relatórios para compor a janela de 12 meses.")
    s = pontos[-1]
    i = s["indice"] * 100
    ev = [["Receita corrente em 12 meses", brl(s["receita_corrente"])],
          ["Despesa corrente liquidada em 12 meses", brl(s["despesa_corrente_liquidada"])],
          ["Relação apurada", pct(i)],
          ["Relação sem as operações intraorçamentárias", pct(s["indice_exceto_intra"] * 100)],
          ["Relação com a despesa empenhada", pct(s["indice_empenhada"] * 100)]]
    if i > 95:
        sit, txt = "apontamento", (
            f"A relação entre despesa corrente e receita corrente chegou a {pct(i)} em 12 meses, "
            "acima de 95%. Nessa faixa é facultada a adoção dos mecanismos de ajuste fiscal do "
            "caput (vedações a aumento de remuneração, criação de cargo, admissão, criação de "
            "despesa obrigatória, benefício tributário, entre outras). Enquanto as medidas não "
            "forem adotadas por todos os Poderes, conforme declaração do Tribunal de Contas, o "
            "ente fica impedido de receber garantia de outro ente e de contratar operação de "
            "crédito com outro ente (§ 6º).")
        prov = ("Avaliar a edição do ato de adoção das medidas do art. 167-A e documentar a "
                "apuração bimestral. Conferir a metodologia adotada pelo TCE-MG para o índice.")
    elif i > 85:
        sit, txt = "atencao", (
            f"A relação está em {pct(i)}, entre 85% e 95%. Nessa faixa as medidas de ajuste "
            "podem ser adotadas, no todo ou em parte, por ato do Chefe do Executivo com "
            "vigência imediata, submetido ao Legislativo em regime de urgência (§§ 1º e 2º).")
        prov = "Acompanhar a apuração a cada bimestre e a trajetória do índice."
    else:
        sit, txt, prov = "regular", f"Relação em {pct(i)}, abaixo de 85%.", ""
    return achado("art167a", G_LIM, "Despesa corrente sobre receita corrente", ano,
                  f"12 meses até o {_per_b(ano, s['bimestre'])}", sit, fund, txt, ev, prov)


def regra_ouro(base, ano):
    bim = _ultimo(base, "rreo", ano)
    fund = "CF/88, art. 167, III; LRF, arts. 12, § 2º, e 53, § 1º, I"
    if bim is None:
        return None
    e = d.execucao(base["rreo"][(ano, bim)])
    oc = next((o["realizada"] for o in e["origens"] if o["nome"] == "Operações de crédito"), 0) or 0
    dc = e["despesa_capital"]["empenhada"] or 0
    ev = [["Operações de crédito realizadas", brl(oc)],
          ["Despesa de capital empenhada", brl(dc)]]
    if oc > dc + TOL:
        return achado("regra-ouro", G_LIM, "Regra de ouro", ano, _per_b(ano, bim), "apontamento",
                      fund, "As operações de crédito realizadas superam a despesa de capital "
                      "empenhada.", ev)
    return achado("regra-ouro", G_LIM, "Regra de ouro", ano, _per_b(ano, bim), "regular", fund,
                  "As operações de crédito não superam a despesa de capital.", ev)


def regra_caixa(base, ano):
    fund = ("LRF, arts. 8º, parágrafo único, 50, I, e 55, III; no último ano de mandato, "
            "também o art. 42")
    r = base["rgf"].get((ano, 3, "E"))
    if r is None or not r.tem_anexo("05"):
        return achado("caixa-fonte", G_EXE, "Disponibilidade de caixa por fonte de recurso", ano,
                      str(ano), "nao_avaliado", fund,
                      "O demonstrativo da disponibilidade de caixa e dos restos a pagar só é "
                      "publicado no RGF do último quadrimestre.")
    fontes = d.caixa_por_fonte(r)
    neg = [f for f in fontes if (f["valor"] or 0) < -TOL]
    ultimo = ano % 4 == 0
    if not neg:
        return achado("caixa-fonte", G_EXE, "Disponibilidade de caixa por fonte de recurso", ano,
                      _per_q(ano, 3), "regular", fund,
                      "Nenhuma fonte fechou o exercício com disponibilidade líquida negativa "
                      "após a inscrição em restos a pagar não processados.")
    ev = [[f["fonte"], brl(f["valor"])] for f in sorted(neg, key=lambda f: f["valor"])]
    txt = (f"{len(neg)} fonte(s) de recurso fecharam o exercício com disponibilidade de caixa "
           "líquida negativa após a inscrição em restos a pagar, ou seja, com obrigações sem "
           "lastro financeiro na própria fonte.")
    if ultimo:
        txt += (" Por se tratar do último ano do mandato 2021-2024, o ponto se relaciona com a "
                "vedação do art. 42 da LRF.")
    return achado("caixa-fonte", G_EXE, "Disponibilidade de caixa por fonte de recurso", ano,
                  _per_q(ano, 3), "apontamento", fund, txt, ev,
                  "Verificar a classificação por fonte dos saldos bancários e das obrigações e, "
                  "confirmada a insuficiência, a origem das despesas assumidas sem cobertura.")


# ------------------------------------------------------------ execução

def regra_dotacao(base, ano):
    bim = _ultimo(base, "rreo", ano)
    if bim is None:
        return None
    r = base["rreo"][(ano, bim)]
    e = d.execucao(r)
    fund = "CF/88, art. 167, II; Lei nº 4.320/1964, art. 59"
    estouros = []
    for g in e["grupos"] + d.funcoes(r):
        dot, emp = g.get("dotacao_atualizada"), g.get("empenhada")
        if dot is not None and emp is not None and emp > dot + TOL:
            estouros.append([g["nome"], f"empenhado {brl(emp)} para dotação de {brl(dot)}"])
    if estouros:
        return achado("dotacao", G_EXE, "Despesa empenhada acima da dotação", ano,
                      _per_b(ano, bim), "apontamento", fund,
                      "Há grupo de despesa ou função com empenho superior ao crédito "
                      "orçamentário atualizado.", estouros,
                      "Conferir se houve crédito adicional não refletido no demonstrativo.")
    return achado("dotacao", G_EXE, "Despesa empenhada acima da dotação", ano, _per_b(ano, bim),
                  "regular", fund, "Nenhum grupo de despesa ou função com empenho acima da "
                  "dotação atualizada, no nível de detalhe do RREO.")


def regra_resultado(base, ano):
    bim = _ultimo(base, "rreo", ano)
    if bim is None:
        return None
    e = d.execucao(base["rreo"][(ano, bim)])
    rec, emp = e["receita_total"]["realizada"], e["despesa_total"]["empenhada"]
    sup = e["superavit_financeiro_utilizado"] or 0
    fund = "Lei nº 4.320/1964, art. 48, b; LRF, arts. 1º, § 1º, e 9º"
    if rec is None or emp is None:
        return None
    res = rec - emp
    ev = [["Receita realizada", brl(rec)], ["Despesa empenhada", brl(emp)],
          ["Resultado da execução", brl(res)],
          ["Superávit financeiro de exercícios anteriores utilizado", brl(sup)]]
    tit = "Resultado da execução orçamentária"
    if res >= 0:
        return achado("resultado", G_EXE, tit, ano, _per_b(ano, bim), "regular", fund,
                      "A receita realizada cobre a despesa empenhada.", ev)
    if bim < 6:
        return achado("resultado", G_EXE, tit, ano, _per_b(ano, bim), "atencao", fund,
                      "A despesa empenhada supera a receita realizada até o bimestre. Parte da "
                      "diferença decorre de empenhos globais e por estimativa que cobrem o ano "
                      "todo, mas a trajetória deve ser acompanhada para que o exercício não "
                      "feche com déficit sem cobertura.", ev,
                      "Projetar o fechamento e avaliar a necessidade de limitação de empenho.")
    if -res > sup + TOL:
        return achado("resultado", G_EXE, tit, ano, _per_b(ano, bim), "apontamento", fund,
                      "O exercício fechou com déficit de execução orçamentária superior ao "
                      "superávit financeiro de exercícios anteriores utilizado para abertura de "
                      "créditos.", ev,
                      "Demonstrar a cobertura do déficit com superávit financeiro do exercício "
                      "anterior, por fonte de recurso.")
    return achado("resultado", G_EXE, tit, ano, _per_b(ano, bim), "atencao", fund,
                  "O exercício fechou com déficit de execução, coberto pelo superávit financeiro "
                  "de exercícios anteriores utilizado para créditos adicionais.", ev)


def _padrao_arrecadacao(base, ano, bim):
    """Fração da receita anual normalmente realizada até o bimestre (exercícios fechados)."""
    fracoes = []
    for a in sorted({k[0] for k in base["rreo"]}):
        if a >= ano or (a, 6) not in base["rreo"] or (a, bim) not in base["rreo"]:
            continue
        fim = d.execucao(base["rreo"][(a, 6)])["receita_total"]["realizada"]
        par = d.execucao(base["rreo"][(a, bim)])["receita_total"]["realizada"]
        if fim and par:
            fracoes.append(par / fim)
    return sum(fracoes) / len(fracoes) if fracoes else None


def regra_arrecadacao(base, ano):
    bim = _ultimo(base, "rreo", ano)
    if bim is None:
        return None
    e = d.execucao(base["rreo"][(ano, bim)])
    rt = e["receita_total"]
    real, prev, ini = rt["realizada"], rt["previsao_atualizada"], rt["previsao_inicial"]
    fund = "LRF, arts. 9º, 12 e 13; Lei nº 4.320/1964, arts. 30 e 43, § 3º"
    if not real or not prev:
        return None
    if bim == 6:
        proj, rotulo = real, "Receita realizada no exercício"
    else:
        frac = _padrao_arrecadacao(base, ano, bim)
        if frac is None:
            return None
        proj, rotulo = real / frac, "Projeção de fechamento pelo padrão dos anos anteriores"
    ev = [["Previsão inicial", brl(ini)], ["Previsão atualizada", brl(prev)],
          ["Realizada até o período", brl(real)], [rotulo, brl(proj)],
          ["Projeção sobre a previsão atualizada", pct(proj / prev * 100, 1)]]
    piores = sorted(
        (o for o in e["origens"] if o.get("previsao_atualizada")),
        key=lambda o: (o["realizada"] or 0) - o["previsao_atualizada"] * (bim / 6))[:2]
    for o in piores:
        ev.append([f"{o['nome']}: realizado sobre o previsto no ano",
                   pct((o["realizada"] or 0) / o["previsao_atualizada"] * 100, 1)])
    tit = "Arrecadação frente à previsão orçamentária"
    reest = (prev - ini) if ini is not None else 0
    if proj / prev >= 0.9:
        return achado("arrecadacao", G_EXE, tit, ano, _per_b(ano, bim), "regular", fund,
                      "A arrecadação está compatível com a previsão atualizada.", ev)
    txt = ("A arrecadação aponta para fechamento abaixo de 90% da previsão atualizada, o que "
           "caracteriza superestimativa de receita. " if bim < 6 else
           "A receita realizada ficou abaixo de 90% da previsão atualizada, o que caracteriza "
           "superestimativa de receita. ")
    txt += ("Frustrada a receita, a LRF exige limitação de empenho e movimentação financeira "
            "nos trinta dias seguintes ao bimestre.")
    if reest > TOL:
        txt += (f" A previsão foi elevada em {brl(reest)} ao longo do exercício: créditos "
                "adicionais abertos por excesso de arrecadação que não se confirma ficam sem "
                "fonte de recurso.")
    return achado("arrecadacao", G_EXE, tit, ano, _per_b(ano, bim), "atencao", fund, txt, ev,
                  "Reavaliar as receitas previstas e não realizadas (em especial operações de "
                  "crédito e transferências de capital) e conter os empenhos nelas lastreados.")


def regra_creditos(base, ano):
    bim = _ultimo(base, "rreo", ano)
    if bim is None:
        return None
    e = d.execucao(base["rreo"][(ano, bim)])
    dot = e["despesa_total"]["dotacao_atualizada"]
    prev = e["receita_total"]["previsao_atualizada"]
    sup = e["superavit_financeiro_utilizado"] or 0
    ini = e["despesa_total"]["dotacao_inicial"]
    fund = "CF/88, art. 167, V; Lei nº 4.320/1964, arts. 42 e 43"
    if dot is None or prev is None:
        return None
    ev = [["Dotação inicial", brl(ini)], ["Dotação atualizada", brl(dot)],
          ["Previsão atualizada da receita", brl(prev)],
          ["Superávit financeiro utilizado", brl(sup)]]
    if ini:
        ev.append(["Acréscimo líquido da dotação", pct((dot - ini) / ini * 100, 1)])
    tit = "Lastro dos créditos adicionais"
    real = e["receita_total"]["realizada"] or 0
    ev.append(["Receita realizada até o período", brl(real)])
    # o excesso de arrecadação efetivo também é fonte de crédito (art. 43, § 1º, II)
    lastro = max(prev, real) + sup
    if dot > lastro + TOL:
        return achado("creditos", G_EXE, tit, ano, _per_b(ano, bim), "atencao", fund,
                      f"A dotação atualizada supera em {brl(dot - lastro)} a soma da receita "
                      "(a maior entre a prevista e a realizada) com o superávit financeiro "
                      "utilizado, o que sugere crédito adicional aberto sem a indicação de "
                      "recurso correspondente.", ev,
                      "Conciliar os decretos de abertura de crédito com as fontes indicadas.")
    return achado("creditos", G_EXE, tit, ano, _per_b(ano, bim), "regular", fund,
                  "A dotação atualizada está coberta pela receita prevista somada ao superávit "
                  "financeiro utilizado. A verificação por decreto e por fonte, e do limite de "
                  "suplementação da LOA, depende dos dados do SICOM.", ev)


def regra_rp(base, ano):
    bim = _ultimo(base, "rreo", ano)
    if bim is None:
        return None
    x = d.fiscais_rreo(base["rreo"][(ano, bim)])
    canc = x["rp_processados"]["cancelados"] or 0
    fund = "Lei nº 4.320/1964, arts. 36, 62 e 63; LRF, art. 50, II"
    ev = [["Restos a pagar processados inscritos", brl(x["rp_processados"]["inscritos"])],
          ["Restos a pagar processados cancelados", brl(canc)],
          ["Restos a pagar não processados cancelados",
           brl(x["rp_nao_processados"]["cancelados"])],
          ["Saldo total de restos a pagar", brl(x["rp_total"]["a_pagar"])]]
    tit = "Cancelamento de restos a pagar processados"
    if canc > TOL:
        return achado("rp-cancelados", G_EXE, tit, ano, _per_b(ano, bim), "atencao", fund,
                      f"Foram cancelados {brl(canc)} em restos a pagar processados. Como se "
                      "trata de despesa já liquidada, com direito adquirido do credor, o "
                      "cancelamento exige justificativa formal em cada caso.", ev,
                      "Reunir os atos e as justificativas de cada cancelamento.")
    return achado("rp-cancelados", G_EXE, tit, ano, _per_b(ano, bim), "regular", fund,
                  "Não houve cancelamento de restos a pagar processados.", ev)


def regra_previdencia(base, ano):
    bim = _ultimo(base, "rreo", ano)
    if bim is None:
        return None
    p = d.fiscais_rreo(base["rreo"][(ano, bim)])["previdencia"]
    fund = "CF/88, art. 40, caput; LRF, art. 69; Lei nº 9.717/1998, art. 1º"
    ev = [["Resultado do fundo em capitalização", brl(p["capitalizacao"])],
          ["Resultado do fundo em repartição", brl(p["reparticao"])]]
    tit = "Resultado previdenciário do RPPS"
    if p["capitalizacao"] is None and p["reparticao"] is None:
        return None
    if min(v for v in p.values() if v is not None) < -TOL:
        return achado("previdencia", G_EXE, tit, ano, _per_b(ano, bim), "atencao", fund,
                      "Há plano do regime próprio com despesa previdenciária superior à receita "
                      "no período. A insuficiência é coberta por aportes do Tesouro municipal, "
                      "que pressionam a despesa corrente.", ev,
                      "Acompanhar os aportes para cobertura de insuficiência financeira e a "
                      "avaliação atuarial.")
    return achado("previdencia", G_EXE, tit, ano, _per_b(ano, bim), "regular", fund,
                  "Resultado previdenciário positivo no período.", ev)


# ------------------------------------------------------------ consistência

def regras_consistencia(base, ano, serie):
    saida = []
    bim = _ultimo(base, "rreo", ano)
    if bim is None:
        return saida
    r = base["rreo"][(ano, bim)]
    e, x = d.execucao(r), d.fiscais_rreo(r)

    # RCL de 12 meses frente à receita corrente de 12 meses
    ponto = next((s for s in serie if s["ano"] == ano and s["bimestre"] == bim), None)
    if ponto and x["rcl_12m"]:
        rel = x["rcl_12m"] / ponto["receita_corrente"]
        ev = [["RCL de 12 meses (Anexo 3 do RREO)", brl(x["rcl_12m"])],
              ["Receita corrente de 12 meses (Anexo 1 do RREO)", brl(ponto["receita_corrente"])],
              ["RCL sobre a receita corrente", pct(rel * 100, 1)]]
        ok = 0.75 <= rel <= 1.05
        saida.append(achado(
            "rcl-coerencia", G_CON, "Coerência da receita corrente líquida", ano,
            _per_b(ano, bim), "regular" if ok else "apontamento",
            "LRF, art. 2º, IV e § 3º; art. 53, I",
            "A RCL informada é compatível com a receita corrente do balanço orçamentário."
            if ok else
            "A RCL informada é incompatível com a receita corrente do balanço orçamentário do "
            "mesmo período. Como a RCL é a base de todos os limites da LRF, o erro contamina "
            "os percentuais de pessoal e de dívida publicados.", ev,
            "" if ok else "Retificar o Anexo 3 do RREO e os anexos do RGF que usam a RCL."))

    # RCL: RREO x RGF do Executivo x RGF do Legislativo
    quad = _ultimo(base, "rgf", ano, "E")
    if quad:
        pe = d.pessoal(base["rgf"][(ano, quad, "E")])
        rl = base["rgf"].get((ano, quad, "L"))
        pl = d.pessoal(rl) if rl else {}
        rr = base["rreo"].get((ano, quad * 2))
        rcl_rreo = d.fiscais_rreo(rr)["rcl_12m"] if rr else None
        vals = [v for v in (pe.get("rcl"), pl.get("rcl"), rcl_rreo) if v]
        if len(vals) >= 2:
            dif = max(vals) - min(vals)
            rel = dif / max(vals)
            sit = "regular" if dif <= TOL else ("atencao" if rel < 0.005 else "apontamento")
            saida.append(achado(
                "rcl-divergencia", G_CON, "RCL divergente entre os demonstrativos", ano,
                _per_q(ano, quad), sit, "LRF, arts. 2º, IV, 53, I, e 55, I",
                "A RCL é a mesma nos três demonstrativos." if sit == "regular" else
                f"Os demonstrativos do mesmo período trazem valores diferentes de RCL, com "
                f"diferença de {brl(dif)}. A RCL do ente é única e deve ser a mesma para o "
                "Executivo e o Legislativo.",
                [["RREO, Anexo 3", brl(rcl_rreo)], ["RGF do Executivo", brl(pe.get("rcl"))],
                 ["RGF do Legislativo", brl(pl.get("rcl"))]],
                "" if sit == "regular" else
                "Alinhar a RCL entre Prefeitura e Câmara e retificar o relatório divergente."))

        # Dívida consolidada: RREO x RGF
        if rr:
            dc_rreo = d.fiscais_rreo(rr)["divida_consolidada"]
            dc_rgf = d.divida(base["rgf"][(ano, quad, "E")], quad)["divida_consolidada"]
            if dc_rgf is not None:
                igual = dc_rreo is not None and abs(dc_rreo - dc_rgf) <= TOL
                saida.append(achado(
                    "divida-divergencia", G_CON, "Dívida consolidada: RREO e RGF", ano,
                    _per_q(ano, quad), "regular" if igual else "atencao",
                    "LRF, arts. 53, III, e 55, I, b",
                    "A dívida consolidada coincide nos dois relatórios." if igual else
                    "A dívida consolidada do Anexo 6 do RREO não coincide com a do Anexo 2 do "
                    "RGF na mesma data, ou não foi informada no RREO.",
                    [["RREO, Anexo 6", brl(dc_rreo)], ["RGF, Anexo 2", brl(dc_rgf)]]))

    # Balanço orçamentário x demonstrativo simplificado x despesa por função
    difs = []
    pares = [("Receita realizada: Anexo 1 e Anexo 14",
              e["receita_total"]["realizada"], x["a14_receita_realizada"]),
             ("Despesa empenhada: Anexo 1 e Anexo 14",
              e["despesa_total"]["empenhada"], x["a14_despesa_empenhada"]),
             ("Despesa empenhada, exceto intra: Anexo 1 e Anexo 2",
              e["despesa_exceto_intra"]["empenhada"],
              r.v("02", "RREO2TotalDespesas", d.EMP, conta="DESPESAS (EXCETO INTRA"))]
    for nome, a, b in pares:
        if a is not None and b is not None and abs(a - b) > TOL:
            difs.append([nome, f"{brl(a)} e {brl(b)}"])
    rc, rk, rx = (e["receita_corrente"]["realizada"], e["receita_capital"]["realizada"],
                  e["receita_exceto_intra"]["realizada"])
    if None not in (rc, rx) and abs(rc + (rk or 0) - rx) > TOL:
        difs.append(["Receitas correntes mais de capital frente ao total exceto intra",
                     f"{brl(rc + (rk or 0))} e {brl(rx)}"])
    for g in e["grupos"] + [dict(nome="Total da despesa", **e["despesa_total"])]:
        em, li, pg = g.get("empenhada"), g.get("liquidada"), g.get("paga")
        if em is not None and li is not None and li > em + TOL:
            difs.append([f"{g['nome']}: liquidado maior que empenhado", f"{brl(li)} e {brl(em)}"])
        if li is not None and pg is not None and pg > li + TOL:
            difs.append([f"{g['nome']}: pago maior que liquidado", f"{brl(pg)} e {brl(li)}"])
    for b in range(2, bim + 1):
        ant, atu = base["rreo"].get((ano, b - 1)), base["rreo"].get((ano, b))
        if not ant or not atu:
            continue
        ea, eb = d.execucao(ant), d.execucao(atu)
        for nome, ka, kb in (("Receita realizada", "receita_total", "realizada"),
                             ("Despesa liquidada", "despesa_total", "liquidada"),
                             ("Despesa paga", "despesa_total", "paga")):
            va, vb = ea[ka][kb], eb[ka][kb]
            if va is not None and vb is not None and vb < va - TOL:
                difs.append([f"{nome} acumulada caiu do {b - 1}º para o {b}º bimestre",
                             f"{brl(va)} para {brl(vb)}"])
    saida.append(achado(
        "cruzamentos", G_CON, "Cruzamento entre os anexos do RREO", ano, _per_b(ano, bim),
        "apontamento" if difs else "regular", "LRF, arts. 48, 52 e 53; Lei nº 4.320/1964, art. 85",
        "Os anexos do RREO apresentam divergências internas." if difs else
        "Totais coerentes entre o balanço orçamentário, a despesa por função e o demonstrativo "
        "simplificado, e acumulados sem regressão entre os bimestres.", difs,
        "Retificar os anexos divergentes." if difs else ""))
    return saida


# ------------------------------------------------------------ prazos

def _prazo(ano, n, por_ano):
    """Trinta dias após o fim do período (por_ano = 6 bimestres ou 3 quadrimestres)."""
    mes_fim = n * (12 // por_ano)
    if mes_fim == 12:
        return dt.date(ano + 1, 1, 30)
    return dt.date(ano, mes_fim + 1, 30)


def regra_prazos(base, ano, hoje):
    saida = []
    extrato = base["extrato"].get(ano, [])
    for sigla, nome, por_ano, fund, filtro in (
        ("rreo", "Relatório Resumido de Execução Orçamentária", 6,
         "CF/88, art. 165, § 3º; LRF, arts. 52, caput e § 2º, e 51, § 2º", "Resumido"),
        ("rgf", "Relatório de Gestão Fiscal", 3, "LRF, arts. 54, 55, §§ 2º e 3º, e 63",
         "Gestão Fiscal"),
    ):
        ev, pior = [], "regular"
        for n in range(1, por_ano + 1):
            prazo = _prazo(ano, n, por_ano)
            if prazo >= hoje:
                continue
            itens = [i for i in extrato if filtro in i["entregavel"] and int(i["periodo"]) == n]
            if sigla == "rgf":
                grupos = {"Prefeitura": [i for i in itens if "Prefeitura" in i["instituicao"]],
                          "Câmara": [i for i in itens if "Câmara" in i["instituicao"]]}
            else:
                grupos = {"": itens}
            for quem, lista in grupos.items():
                rot = f"{n}º {'bimestre' if por_ano == 6 else 'quadrimestre'}" + \
                      (f" ({quem})" if quem else "")
                if not lista:
                    ev.append([rot, f"não consta entrega; prazo em {prazo:%d/%m/%Y}"])
                    pior = "apontamento"
                    continue
                i = lista[0]
                data = dt.date.fromisoformat(i["data_status"][:10])
                atraso = (data - prazo).days
                if i["status_relatorio"] == "RE":
                    ev.append([rot, f"retificado em {data:%d/%m/%Y}; prazo original em "
                                    f"{prazo:%d/%m/%Y}"])
                    pior = "atencao" if pior == "regular" else pior
                elif atraso > 0:
                    ev.append([rot, f"homologado em {data:%d/%m/%Y}, {atraso} dia(s) após o "
                                    f"prazo de {prazo:%d/%m/%Y}"])
                    pior = "atencao" if pior == "regular" else pior
                else:
                    ev.append([rot, f"homologado em {data:%d/%m/%Y}, no prazo"])
        if not ev:
            continue
        txt = {"regular": "Relatórios homologados no Siconfi dentro do prazo.",
               "atencao": "Há relatório homologado no Siconfi após o prazo legal ou retificado "
                          "depois da entrega. O Siconfi registra a data do último envio, de modo "
                          "que a retificação não permite saber se a primeira entrega foi "
                          "tempestiva. A publicação fora do prazo impede o recebimento de "
                          "transferências voluntárias e a contratação de operações de crédito "
                          "até a regularização.",
               "apontamento": "Há relatório com prazo vencido sem entrega no Siconfi."}[pior]
        saida.append(achado(f"prazo-{sigla}", G_PRA, f"Prazo do {nome}", ano, str(ano), pior,
                            fund, txt, ev,
                            "" if pior == "regular" else
                            "Guardar o comprovante da publicação tempestiva no órgão oficial e "
                            "registrar o motivo de cada retificação."))
    return saida


# ------------------------------------------------------------ escopo SICOM

ESCOPO_SICOM = [
    ("mde", "Aplicação mínima na manutenção e desenvolvimento do ensino",
     "CF/88, art. 212; LDB, arts. 70 e 71",
     "Mínimo de 25% da receita de impostos e transferências."),
    ("fundeb", "Aplicação dos recursos do FUNDEB",
     "CF/88, art. 212-A; Lei nº 14.113/2020, arts. 25 e 26",
     "Mínimo de 70% na remuneração dos profissionais da educação básica e limite de 10% de "
     "saldo para o primeiro quadrimestre do exercício seguinte."),
    ("asps", "Aplicação mínima em ações e serviços públicos de saúde",
     "CF/88, art. 198, § 2º, III; LC nº 141/2012, art. 7º",
     "Mínimo de 15% da receita de impostos e transferências."),
    ("camara", "Repasse ao Poder Legislativo",
     "CF/88, art. 29-A",
     "Limite percentual sobre a receita tributária e de transferências do exercício anterior, "
     "conforme a faixa de população."),
    ("creditos-sicom", "Abertura de créditos adicionais",
     "CF/88, art. 167, V e VII; Lei nº 4.320/1964, arts. 42, 43 e 59",
     "Créditos sem autorização legal, sem recursos disponíveis ou acima do limite de "
     "suplementação da LOA, conferidos decreto a decreto e por fonte."),
    ("licitacoes", "Empenhos, contratos e licitações",
     "Lei nº 14.133/2021; Lei nº 4.320/1964, arts. 60 a 64",
     "Empenho posterior à despesa, fracionamento, contratação direta acima dos limites e "
     "pagamentos sem liquidação, apurados no detalhe dos dados do SICOM."),
    ("controle-interno", "Relatório do controle interno e metas do PNE",
     "CF/88, arts. 31 e 74; Lei nº 13.005/2014",
     "Itens da prestação de contas anual avaliados com documentos e dados próprios do TCE-MG."),
]


def regras_escopo(ano, tem_tce):
    txt = ("Aguardando o mapeamento dos arquivos do portal de dados abertos do TCE-MG."
           if tem_tce else
           "Depende dos arquivos do portal de dados abertos do TCE-MG, ainda não carregados em "
           "dados/tce-mg.")
    return [achado(f"sicom-{i}", G_TCE, tit, ano, str(ano), "nao_avaliado", fund,
                   f"{desc} {txt}") for i, tit, fund, desc in ESCOPO_SICOM]


# ------------------------------------------------------------ orquestração

def apurar(base, anos, serie, hoje, tem_tce):
    achados = []
    for ano in anos:
        lote = [regra_167a(serie, ano), regra_pessoal(base, ano, "E", serie),
                regra_pessoal(base, ano, "L", serie), regra_divida(base, ano), regra_ouro(base, ano),
                regra_resultado(base, ano), regra_arrecadacao(base, ano),
                regra_creditos(base, ano), regra_dotacao(base, ano), regra_caixa(base, ano),
                regra_rp(base, ano), regra_previdencia(base, ano)]
        lote += regras_consistencia(base, ano, serie)
        lote += regra_prazos(base, ano, hoje)
        lote += regras_escopo(ano, tem_tce)
        achados += [a for a in lote if a]
    return achados
