/* Painel fiscal municipal: aplicação estática, sem dependências.
   Lê dados/painel.json (gerado por painel/gerar.py) e desenha as abas. */
(() => {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  const $ = (s, r = document) => r.querySelector(s);
  const h = (tag, attrs = {}, ...filhos) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "html") e.innerHTML = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const f of filhos.flat()) if (f != null && f !== false) e.append(f);
    return e;
  };
  const s = (tag, attrs = {}, texto) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v);
    if (texto != null) e.textContent = texto;
    return e;
  };

  const nf = (o) => new Intl.NumberFormat("pt-BR", o);
  const F = {
    brl: (v) => v == null ? "s/d" : nf({ style: "currency", currency: "BRL" }).format(v),
    mi: (v) => {
      if (v == null) return "s/d";
      const a = Math.abs(v), p = v < 0 ? "-R$ " : "R$ ";
      if (a >= 1e9) return p + nf({ maximumFractionDigits: 2 }).format(a / 1e9) + " bi";
      if (a >= 1e6) return p + nf({ minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(a / 1e6) + " mi";
      if (a >= 1e3) return p + nf({ maximumFractionDigits: 0 }).format(a / 1e3) + " mil";
      return p + nf({ maximumFractionDigits: 0 }).format(a);
    },
    pct: (v, c = 1) => v == null ? "s/d" : nf({ minimumFractionDigits: c, maximumFractionDigits: c }).format(v) + "%",
    data: (iso) => iso ? new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" }) : "s/d",
  };
  const ORD = (n) => `${n}º`;
  const SIT = {
    apontamento: "Apontamento provável", atencao: "Ponto de atenção",
    regular: "Regular", nao_avaliado: "Não avaliado",
  };
  const CORES = ["var(--serie-1)", "var(--serie-2)", "var(--serie-3)"];

  let P = null, TCE = null;
  const E = { aba: "visao", ano: null, comp: "no_bimestre", sit: "todas" };

  /* ---------------------------------------------------------- dica flutuante */
  const dica = $("#dica");
  const mostrarDica = (html, x, y) => {
    dica.innerHTML = html; dica.hidden = false;
    const r = dica.getBoundingClientRect();
    dica.style.left = Math.max(8, Math.min(x + 14, innerWidth - r.width - 8)) + "px";
    dica.style.top = Math.max(8, y - r.height - 12 < 8 ? y + 18 : y - r.height - 12) + "px";
  };
  const ocultarDica = () => { dica.hidden = true; };

  /* ---------------------------------------------------------- componentes */
  const selo = (sit) => h("span", { class: "selo " + sit }, SIT[sit]);

  const botoes = (opcoes, atual, aoEscolher, rotulo) => h("div", { class: "grupo-botoes", role: "group", "aria-label": rotulo },
    opcoes.map(([valor, texto]) => h("button", {
      type: "button", "aria-pressed": String(valor === atual),
      onclick: () => aoEscolher(valor),
    }, texto)));

  const kpi = (nome, valor, apoio, extra) => h("div", { class: "cartao kpi" },
    h("div", { class: "nome" }, nome), h("div", { class: "valor" }, valor),
    extra, apoio && h("div", { class: "apoio" }, apoio));

  const medidor = (v, max, marcas = []) => h("div", { class: "medidor", "aria-hidden": "true" },
    h("i", { style: `width:${Math.max(0, Math.min(100, v / max * 100))}%` }),
    marcas.map((m) => h("b", { style: `left:${Math.min(100, m / max * 100)}%` })));

  /* Barras horizontais: valor preenchido sobre um trilho que representa a referência. */
  const barrasH = (linhas, { rotuloValor, rotuloRef, rotuloMarca }) => {
    const max = Math.max(...linhas.flatMap((l) => [l.valor || 0, l.ref || 0, l.marca || 0]), 1);
    return h("div", { class: "barras" }, linhas.map((l) => {
      const html = `<b>${l.nome}</b>${rotuloValor}: ${F.brl(l.valor)}` +
        (l.marca != null ? `<br>${rotuloMarca}: ${F.brl(l.marca)}` : "") +
        (l.ref ? `<br>${rotuloRef}: ${F.brl(l.ref)}<br>${rotuloValor} sobre ${rotuloRef.toLowerCase()}: ${F.pct((l.valor || 0) / l.ref * 100)}` : "");
      const linha = h("div", { class: "barra-h", tabindex: "0" },
        h("span", { class: "n", title: l.nome }, l.nome),
        h("span", { class: "t", style: `width:${Math.max(2, (l.ref || l.valor || 0) / max * 100)}%` },
          h("i", { style: `width:${l.ref ? Math.min(100, (l.valor || 0) / l.ref * 100) : (l.valor ? 100 : 0)}%` }),
          l.marca != null && l.ref ? h("b", { style: `left:${Math.min(100, l.marca / l.ref * 100)}%` }) : null),
        h("span", { class: "v" }, F.mi(l.valor)));
      linha.addEventListener("mousemove", (ev) => mostrarDica(html, ev.clientX, ev.clientY));
      linha.addEventListener("mouseleave", ocultarDica);
      linha.addEventListener("focus", () => { const r = linha.getBoundingClientRect(); mostrarDica(html, r.left + 40, r.top); });
      linha.addEventListener("blur", ocultarDica);
      return linha;
    }));
  };

  /* Gráfico de linhas com eixo único, rótulo direto no fim de cada série e mira no hover. */
  const linhas = (alvo, { series, categorias, fmt, fmtEixo, limites = [], minY, maxY, altura = 260 }) => {
    const desenhar = () => {
      alvo.textContent = "";
      const L = Math.max(300, alvo.clientWidth || 600), A = altura;
      const m = { e: 52, d: 78, t: 14, b: 28 };
      const todos = series.flatMap((x) => x.pontos.filter((p) => p != null)).concat(limites.map((l) => l.valor));
      let lo = minY != null ? minY : Math.min(0, ...todos), hi = Math.max(...todos);
      if (maxY != null) hi = maxY;
      else if (minY == null && lo === 0) hi *= 1.06; else { const f = (hi - lo) * 0.1 || 1; hi += f; if (minY == null) lo -= f; }
      const X = (i) => m.e + (categorias.length === 1 ? 0 : i * (L - m.e - m.d) / (categorias.length - 1));
      const Y = (v) => m.t + (hi - v) * (A - m.t - m.b) / (hi - lo);
      const svg = s("svg", { viewBox: `0 0 ${L} ${A}`, role: "img", "aria-label": series.map((x) => x.nome).join(", ") });
      for (let i = 0; i <= 4; i++) {
        const v = lo + (hi - lo) * i / 4, y = Y(v);
        svg.append(s("line", { x1: m.e, x2: L - m.d, y1: y, y2: y, stroke: "var(--linha)", "stroke-width": 1 }));
        svg.append(s("text", { x: m.e - 8, y: y + 4, "text-anchor": "end" }, fmtEixo(v)));
      }
      const passo = Math.ceil(categorias.length / Math.max(2, Math.floor((L - m.e - m.d) / 62)));
      categorias.forEach((c, i) => {
        if (i % passo === 0 || i === categorias.length - 1 && (categorias.length - 1) % passo > passo / 2)
          svg.append(s("text", { x: X(i), y: A - 8, "text-anchor": "middle" }, c));
      });
      limites.forEach((l) => {
        svg.append(s("line", { x1: m.e, x2: L - m.d, y1: Y(l.valor), y2: Y(l.valor), stroke: "var(--texto-3)", "stroke-width": 1.5, "stroke-dasharray": "5 4" }));
        svg.append(s("text", { x: L - m.d + 6, y: Y(l.valor) + 4, class: "rot" }, l.nome));
      });
      const fins = [];
      series.forEach((sr, k) => {
        const pts = sr.pontos.map((v, i) => v == null ? null : [X(i), Y(v)]).filter(Boolean);
        if (!pts.length) return;
        svg.append(s("path", { d: "M" + pts.map((p) => p.join(",")).join("L"), fill: "none", stroke: sr.cor, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
        pts.forEach((p) => svg.append(s("circle", { cx: p[0], cy: p[1], r: 3.5, fill: sr.cor, stroke: "var(--superficie)", "stroke-width": 2 })));
        const ult = sr.pontos.reduce((a, v, i) => v == null ? a : i, 0);
        fins.push({ x: pts[pts.length - 1][0], y: pts[pts.length - 1][1], nome: sr.rotulo || sr.nome, valor: fmt(sr.pontos[ult]), interno: ult < categorias.length - 1 });
      });
      // rótulos diretos, afastados entre si quando colidem
      if (!limites.length) fins.filter((f) => f.interno).forEach((f) => {
        svg.append(s("text", { x: f.x - 8, y: f.y - 12, class: "val", "text-anchor": "end" }, `${f.nome}: ${f.valor}`));
      });
      const noFim = fins.filter((f) => !f.interno).sort((a, b) => a.y - b.y);
      for (let i = 1; i < noFim.length; i++) if (noFim[i].y - noFim[i - 1].y < 26) noFim[i].y = noFim[i - 1].y + 26;
      if (!limites.length) noFim.forEach((f) => {
        svg.append(s("text", { x: f.x + 9, y: f.y - 1, class: "val" }, f.valor));
        svg.append(s("text", { x: f.x + 9, y: f.y + 12, class: "rot" }, f.nome));
      });
      const mira = s("line", { y1: m.t, y2: A - m.b, stroke: "var(--texto-3)", "stroke-width": 1, visibility: "hidden" });
      svg.append(mira);
      const area = s("rect", { x: m.e - 10, y: 0, width: L - m.e - m.d + 20, height: A, fill: "transparent" });
      const mover = (ev) => {
        const r = svg.getBoundingClientRect();
        const px = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * L / r.width;
        const i = Math.max(0, Math.min(categorias.length - 1, Math.round((px - m.e) / ((L - m.e - m.d) / Math.max(1, categorias.length - 1)))));
        mira.setAttribute("x1", X(i)); mira.setAttribute("x2", X(i)); mira.setAttribute("visibility", "visible");
        const corpo = series.filter((x) => x.pontos[i] != null).map((x) => `<i style="background:${x.cor}"></i>${x.nome}: <strong>${fmt(x.pontos[i])}</strong>`).join("<br>");
        mostrarDica(`<b>${categorias[i]}</b>${corpo}`, r.left + X(i) * r.width / L, (ev.touches ? ev.touches[0].clientY : ev.clientY));
      };
      area.addEventListener("mousemove", mover); area.addEventListener("touchstart", mover, { passive: true });
      area.addEventListener("mouseleave", () => { mira.setAttribute("visibility", "hidden"); ocultarDica(); });
      svg.append(area);
      alvo.append(svg);
    };
    desenhar();
    alvo._redesenhar = desenhar;
  };

  const legenda = (itens) => h("div", { class: "legenda" }, itens.map(([cor, nome, tipo]) =>
    h("span", {}, h("i", { class: tipo || "", style: tipo === "tracejado" ? "" : `background:${cor}` }), nome)));

  const tabela = (cab, corpo) => h("div", { class: "rolagem" }, h("table", {},
    h("thead", {}, h("tr", {}, cab.map((c) => h("th", { scope: "col" }, c)))),
    h("tbody", {}, corpo)));

  /* ---------------------------------------------------------- aba: visão geral */
  const visao = () => {
    const ano = E.ano, x = P.exercicios[ano], e = x.execucao, f = x.fiscais;
    const rt = e.receita_total, dt = e.despesa_total;
    const ponto = P.art167a.serie.filter((p) => p.ano === +ano).pop();
    const achados = P.inconsistencias.filter((a) => a.exercicio === +ano);
    const conta = (sit) => achados.filter((a) => a.situacao === sit).length;
    const pe = x.pessoal_executivo;
    const raiz = h("div", {});
    raiz.append(
      h("div", { class: "barra" }, h("span", { class: "rotulo" }, "Exercício"),
        botoes(P.meta.exercicios.map((a) => [String(a), String(a)]), ano, (a) => { E.ano = a; render(); }, "Exercício")),
      h("p", { class: "intro" }, `Posição acumulada até o ${ORD(x.bimestre)} bimestre de ${ano}, segundo o Relatório Resumido de Execução Orçamentária` +
        (x.quadrimestre ? `, e até o ${ORD(x.quadrimestre)} quadrimestre no Relatório de Gestão Fiscal.` : ".")),
      h("div", { class: "grade kpis" },
        kpi("Receita realizada", F.mi(rt.realizada), `${F.pct(rt.realizada / rt.previsao_atualizada * 100)} da previsão atualizada de ${F.mi(rt.previsao_atualizada)}`,
          medidor(rt.realizada, rt.previsao_atualizada)),
        kpi("Despesa empenhada", F.mi(dt.empenhada), `${F.pct(dt.empenhada / dt.dotacao_atualizada * 100)} da dotação atualizada de ${F.mi(dt.dotacao_atualizada)}`,
          medidor(dt.empenhada, dt.dotacao_atualizada)),
        kpi("Despesa liquidada", F.mi(dt.liquidada), `Paga: ${F.mi(dt.paga)}`),
        kpi("Resultado da execução", F.mi(e.resultado_orcamentario), "Receita realizada menos despesa empenhada"),
        kpi("Despesa corrente sobre receita corrente", ponto ? F.pct(ponto.indice * 100, 2) : "s/d",
          "Art. 167-A da CF/88, 12 meses. Marcas em 85% e 95%.", ponto && medidor(ponto.indice * 100, 110, [85, 95])),
        kpi("Pessoal do Executivo sobre a RCL", pe ? F.pct(pe.percentual, 2) : "s/d",
          pe ? `Limite máximo de ${F.pct(pe.limite_maximo_pct, 0)}; alerta em ${F.pct(pe.limite_alerta_pct)}` : "",
          pe && medidor(pe.percentual, 60, [pe.limite_alerta_pct, pe.limite_prudencial_pct, pe.limite_maximo_pct])),
        kpi("Receita corrente líquida", F.mi(f.rcl_12m), "Últimos 12 meses"),
        kpi("Restos a pagar em aberto", F.mi(f.rp_total.a_pagar), `Inscritos: ${F.mi(f.rp_total.inscritos)}`)));

    const cartaoAchados = h("div", { class: "cartao" }, h("h2", {}, `Inconsistências apuradas em ${ano}`),
      h("p", { class: "sub" }, "Resumo das verificações. O detalhe está na aba Inconsistências."),
      h("div", { class: "legenda" }, ["apontamento", "atencao", "regular", "nao_avaliado"].map((k) =>
        h("span", {}, selo(k), h("strong", {}, String(conta(k)))))),
      achados.filter((a) => a.situacao === "apontamento").map((a) =>
        h("p", { style: "margin-top:8px;font-size:.92rem" }, h("strong", {}, a.titulo + ". "), a.descricao.split(". ")[0] + ".")),
      h("p", { style: "margin-top:10px" }, h("button", { class: "botao", type: "button", onclick: () => { E.aba = "inconsistencias"; render(); } }, "Ver todas as verificações")));

    const gEvol = h("div", { class: "grafico" });
    const bs = x.bimestres;
    const cartaoEvol = h("div", { class: "cartao" }, h("h2", {}, "Execução acumulada por bimestre"),
      h("p", { class: "sub" }, "Valores acumulados no exercício"),
      legenda([[CORES[0], "Receita realizada", "linha"], [CORES[1], "Despesa empenhada", "linha"], [CORES[2], "Despesa liquidada", "linha"]]), gEvol,
      h("details", {}, h("summary", {}, "Ver em tabela"), tabela(["Bimestre", "Receita realizada", "Despesa empenhada", "Despesa liquidada", "Despesa paga"],
        bs.map((b) => h("tr", {}, h("td", {}, ORD(b.bimestre)), [b.receita_realizada, b.despesa_empenhada, b.despesa_liquidada, b.despesa_paga].map((v) => h("td", {}, F.brl(v))))))));

    const cartaoRec = h("div", { class: "cartao" }, h("h2", {}, "Receita por origem"),
      h("p", { class: "sub" }, "Barra: realizado até o bimestre. Trilho: previsão atualizada para o ano."),
      barrasH(e.origens.filter((o) => o.realizada || o.previsao_atualizada).map((o) => ({ nome: o.nome, valor: o.realizada || 0, ref: o.previsao_atualizada })),
        { rotuloValor: "Realizado", rotuloRef: "Previsão atualizada" }));
    const cartaoGrp = h("div", { class: "cartao" }, h("h2", {}, "Despesa por grupo de natureza"),
      h("p", { class: "sub" }, "Barra: liquidado. Marca: empenhado. Trilho: dotação atualizada."),
      barrasH(e.grupos.map((g) => ({ nome: g.nome, valor: g.liquidada || 0, ref: g.dotacao_atualizada, marca: g.empenhada })),
        { rotuloValor: "Liquidado", rotuloRef: "Dotação atualizada", rotuloMarca: "Empenhado" }));
    const cartaoFun = h("div", { class: "cartao" }, h("h2", {}, "Despesa por função"),
      h("p", { class: "sub" }, "Barra: liquidado. Marca: empenhado. Trilho: dotação atualizada. Exceto operações intraorçamentárias."),
      barrasH(x.funcoes.slice().sort((a, b) => (b.liquidada || 0) - (a.liquidada || 0)).map((g) => ({ nome: g.nome, valor: g.liquidada || 0, ref: g.dotacao_atualizada, marca: g.empenhada })),
        { rotuloValor: "Liquidado", rotuloRef: "Dotação atualizada", rotuloMarca: "Empenhado" }));

    raiz.append(h("div", { class: "grade duas" }, cartaoAchados, cartaoEvol),
      h("div", { class: "grade duas" }, cartaoRec, cartaoGrp), cartaoFun);
    setTimeout(() => linhas(gEvol, {
      categorias: bs.map((b) => `${ORD(b.bimestre)} bim.`), fmt: F.mi, fmtEixo: (v) => nf({ maximumFractionDigits: 0 }).format(v / 1e6) + " mi",
      series: [
        { nome: "Receita realizada", rotulo: "Receita", cor: CORES[0], pontos: bs.map((b) => b.receita_realizada) },
        { nome: "Despesa empenhada", rotulo: "Empenhada", cor: CORES[1], pontos: bs.map((b) => b.despesa_empenhada) },
        { nome: "Despesa liquidada", rotulo: "Liquidada", cor: CORES[2], pontos: bs.map((b) => b.despesa_liquidada) }],
    }));
    return raiz;
  };

  /* ---------------------------------------------------------- aba: comparativo */
  const comparativo = () => {
    const C = P.comparativo, anos = C.exercicios.map(String), modo = E.comp;
    const cols = modo === "no_bimestre" ? anos : anos.filter((a) => C.linhas[0].fechamento[a] != null);
    const ult = cols[cols.length - 1], ant = cols[cols.length - 2], pri = cols[0];
    const variacao = (l, de, para) => {
      const a = l[modo][de], b = l[modo][para];
      if (a == null || b == null) return h("td", {}, "s/d");
      if (l.tipo === "pct") { const d = b - a; return h("td", { class: d > 0.005 ? "sobe" : d < -0.005 ? "desce" : "" }, nf({ minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: "exceptZero" }).format(d) + " p.p."); }
      if (a <= 0 || b < 0) return h("td", { title: "Variação percentual não se aplica a base negativa ou nula" }, "n/a");
      const d = (b - a) / Math.abs(a) * 100;
      return h("td", { class: d > 0.05 ? "sobe" : d < -0.05 ? "desce" : "" }, nf({ minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: "exceptZero" }).format(d) + "%");
    };
    const corpo = []; let secao = null;
    C.linhas.forEach((l) => {
      if (cols.every((a) => l[modo][a] == null)) return;
      if (l.secao !== secao) { secao = l.secao; corpo.push(h("tr", { class: "secao" }, h("td", { colspan: String(cols.length + (cols.length > 2 ? 3 : 2)) }, secao))); }
      corpo.push(h("tr", {}, h("td", {}, l.nome), cols.map((a) => h("td", {}, l.tipo === "pct" ? F.pct(l[modo][a], 2) : F.brl(l[modo][a]))),
        variacao(l, ant, ult), cols.length > 2 ? variacao(l, pri, ult) : null));
    });
    const g1 = h("div", { class: "grafico" }), g2 = h("div", { class: "grafico" });
    const serie = (campo) => anos.map((a, k) => ({ nome: a, cor: CORES[k], pontos: [1, 2, 3, 4, 5, 6].map((b) => (P.exercicios[a].bimestres.find((x) => x.bimestre === b) || {})[campo] ?? null) }));
    const cats = [1, 2, 3, 4, 5, 6].map((b) => `${ORD(b)} bim.`);
    const eixo = (v) => nf({ maximumFractionDigits: 0 }).format(v / 1e6) + " mi";
    const raiz = h("div", {},
      h("p", { class: "intro" }, `Comparação do exercício de ${anos[2]} com os dois anteriores. No modo de mesmo período, os três exercícios são medidos até o ${ORD(C.bimestre)} bimestre, que é o último relatório disponível de ${anos[2]}. Os valores são nominais, sem correção monetária.`),
      P.inconsistencias.some((a) => a.id === "rcl-coerencia" && a.situacao === "apontamento") ? h("div", { class: "aviso" }, h("strong", {}, "Leitura com ressalva. "),
        `A receita corrente líquida declarada em ${[...new Set(P.inconsistencias.filter((a) => a.id === "rcl-coerencia" && a.situacao === "apontamento").map((a) => a.exercicio))].join(" e ")} é incoerente com a receita corrente do mesmo período, o que distorce nesta tabela a RCL e o percentual de pessoal desse exercício. O detalhe está na aba Inconsistências.`) : null,
      h("div", { class: "barra" }, botoes([["no_bimestre", `Mesmo período (até o ${ORD(C.bimestre)} bimestre)`], ["fechamento", "Exercícios encerrados"]], modo, (v) => { E.comp = v; render(); }, "Base de comparação")),
      h("div", { class: "grade duas" },
        h("div", { class: "cartao" }, h("h2", {}, "Receita realizada acumulada"), h("p", { class: "sub" }, "Por bimestre, em cada exercício"), legenda(anos.map((a, k) => [CORES[k], a, "linha"])), g1),
        h("div", { class: "cartao" }, h("h2", {}, "Despesa liquidada acumulada"), h("p", { class: "sub" }, "Por bimestre, em cada exercício"), legenda(anos.map((a, k) => [CORES[k], a, "linha"])), g2)),
      h("div", { class: "cartao" }, h("h2", {}, modo === "no_bimestre" ? `Indicadores até o ${ORD(C.bimestre)} bimestre` : "Indicadores no fechamento do exercício"),
        h("p", { class: "sub" }, "Variações em percentual; para indicadores em percentual, a diferença aparece em pontos percentuais (p.p.)."),
        tabela(["Indicador", ...cols, `${ult} / ${ant}`, ...(cols.length > 2 ? [`${ult} / ${pri}`] : [])], corpo)));
    setTimeout(() => {
      linhas(g1, { categorias: cats, fmt: F.mi, fmtEixo: eixo, series: serie("receita_realizada") });
      linhas(g2, { categorias: cats, fmt: F.mi, fmtEixo: eixo, series: serie("despesa_liquidada") });
    });
    return raiz;
  };

  /* ---------------------------------------------------------- aba: inconsistências */
  const cartaoAchado = (a) => h("details", { class: "achado " + a.situacao, open: a.situacao === "apontamento" },
    h("summary", {}, h("span", { class: "tit" }, a.titulo), selo(a.situacao), h("span", { class: "per" }, a.periodo)),
    h("div", { class: "corpo" }, h("p", {}, a.descricao),
      a.evidencias.length ? h("dl", {}, a.evidencias.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])) : null,
      a.providencia ? h("p", { class: "meta" }, h("strong", {}, "Providência sugerida: "), a.providencia) : null,
      h("p", { class: "meta" }, h("strong", {}, "Fundamento: "), a.fundamento)));

  const inconsistencias = () => {
    const ano = +E.ano, todos = P.inconsistencias.filter((a) => a.exercicio === ano);
    const lista = E.sit === "todas" ? todos : todos.filter((a) => a.situacao === E.sit);
    const grupos = [...new Set(lista.map((a) => a.grupo))];
    const ordem = { apontamento: 0, atencao: 1, nao_avaliado: 2, regular: 3 };
    return h("div", {},
      h("p", { class: "intro" }, "Verificações automáticas sobre os dados declarados pelo próprio Município. Cada item reproduz um ponto que o controle externo costuma examinar e indica o fundamento legal. Um achado é um indício a conferir na origem, e não um juízo definitivo: a apuração oficial cabe ao Tribunal de Contas, com metodologia e dados próprios."),
      h("div", { class: "barra" }, h("span", { class: "rotulo" }, "Exercício"),
        botoes(P.meta.exercicios.map((a) => [String(a), String(a)]), E.ano, (a) => { E.ano = a; render(); }, "Exercício"),
        h("span", { class: "rotulo" }, "Situação"),
        botoes([["todas", "Todas"], ["apontamento", "Apontamentos"], ["atencao", "Atenção"], ["regular", "Regulares"], ["nao_avaliado", "Não avaliados"]], E.sit, (v) => { E.sit = v; render(); }, "Situação")),
      h("div", { class: "resumo-achados" }, Object.keys(SIT).map((k) => h("div", { class: "cartao" }, selo(k), h("div", { class: "num" }, String(todos.filter((a) => a.situacao === k).length))))),
      lista.length ? grupos.map((g) => h("section", { class: "grupo-achados" }, h("h2", {}, g),
        lista.filter((a) => a.grupo === g).sort((a, b) => ordem[a.situacao] - ordem[b.situacao]).map(cartaoAchado)))
        : h("p", { class: "intro" }, "Nenhuma verificação nesta situação para o exercício selecionado."));
  };

  /* ---------------------------------------------------------- aba: art. 167-A */
  const art167a = () => {
    const A = P.art167a, serie = A.serie, atual = serie[serie.length - 1], i = atual.indice * 100;
    const sit = i > 95 ? "apontamento" : i > 85 ? "atencao" : "regular";
    const min = 70, max = 110, pos = (v) => (Math.max(min, Math.min(max, v)) - min) / (max - min) * 100;
    const g = h("div", { class: "grafico" });
    const frase = i > 95 ? "Acima de 95%: está configurada a hipótese do caput, em que é facultada a adoção dos mecanismos de ajuste fiscal."
      : i > 85 ? "Entre 85% e 95%: as medidas de ajuste podem ser adotadas por ato do Chefe do Executivo, com vigência imediata."
        : "Abaixo de 85%: nenhuma das hipóteses do art. 167-A está configurada.";
    const raiz = h("div", {},
      h("div", { class: "cartao", style: "margin-bottom:14px" }, h("div", { class: "destaque" },
        h("div", {}, h("p", { class: "sub", style: "margin-bottom:6px" }, `12 meses encerrados no ${ORD(atual.bimestre)} bimestre de ${atual.ano}`),
          h("div", { class: "numero" }, F.pct(i, 2)), h("p", { style: "margin:10px 0 8px" }, selo(sit)), h("p", { style: "color:var(--texto-2)" }, frase)),
        h("div", {},
          h("div", { class: "regua", style: `--p85:${pos(85)}%;--p95:${pos(95)}%`, role: "img", "aria-label": `Relação de ${F.pct(i, 2)} em uma régua de ${min}% a ${max}%, com marcos em 85% e 95%` },
            h("span", { class: "ponteiro", style: `left:calc(${pos(i)}% - 1px)`, "data-v": F.pct(i, 2) }),
            h("span", { class: "marca", style: `left:${pos(85)}%` }, "85%"), h("span", { class: "marca", style: `left:${pos(95)}%` }, "95%"),
            h("span", { class: "marca", style: "left:0;transform:none" }, `${min}%`), h("span", { class: "marca", style: "left:auto;right:0;transform:none" }, `${max}%`)),
          tabela(["Componente (12 meses)", "Valor"], [
            h("tr", {}, h("td", {}, "Despesa corrente liquidada"), h("td", {}, F.brl(atual.despesa_corrente_liquidada))),
            h("tr", {}, h("td", {}, "Receita corrente realizada"), h("td", {}, F.brl(atual.receita_corrente))),
            h("tr", {}, h("td", {}, "Folga até 95% da receita corrente"), h("td", {}, F.brl(atual.receita_corrente * 0.95 - atual.despesa_corrente_liquidada)))])))),
      h("div", { class: "cartao", style: "margin-bottom:14px" }, h("h2", {}, "Trajetória bimestral do indicador"),
        h("p", { class: "sub" }, "Despesa corrente sobre receita corrente em janelas móveis de 12 meses, apuradas a cada bimestre (art. 167-A, § 4º)"),
        legenda([[CORES[0], "Com operações intraorçamentárias (indicador principal)", "linha"], [CORES[1], "Sem operações intraorçamentárias", "linha"], ["", "Marcos de 85% e 95%", "linha tracejado"]]), g,
        h("details", { open: true }, h("summary", {}, "Tabela da apuração"),
          tabela(["Período", "Receita corrente", "Despesa corrente liquidada", "Relação", "Sem intraorçamentárias", "Com despesa empenhada", "Situação"],
            serie.slice().reverse().map((p) => { const v = p.indice * 100; return h("tr", {}, h("td", {}, `${ORD(p.bimestre)} bim. de ${p.ano}`), h("td", {}, F.mi(p.receita_corrente)), h("td", {}, F.mi(p.despesa_corrente_liquidada)),
              h("td", {}, h("strong", {}, F.pct(v, 2))), h("td", {}, F.pct(p.indice_exceto_intra * 100, 2)), h("td", {}, F.pct(p.indice_empenhada * 100, 2)), h("td", {}, selo(v > 95 ? "apontamento" : v > 85 ? "atencao" : "regular"))); })))),
      h("div", { class: "cartao texto" }, h("h2", { style: "margin-bottom:10px" }, "O que diz a Constituição e como o painel calcula"),
        h("p", { html: "O <strong>art. 167-A da Constituição</strong>, incluído pela Emenda Constitucional nº 109/2021, manda apurar bimestralmente a relação entre despesas correntes e receitas correntes no período de 12 meses. Quando a relação <strong>supera 95%</strong>, os Poderes e órgãos autônomos do ente ficam autorizados a aplicar o mecanismo de ajuste fiscal, que veda, entre outros atos, a concessão de aumento ou vantagem remuneratória, a criação de cargo ou função que implique aumento de despesa, a admissão de pessoal (salvo reposições), a realização de concurso (salvo para reposição), a criação ou o reajuste de despesa obrigatória acima da inflação e a concessão ou ampliação de benefício tributário." }),
        h("p", { html: "Quando a despesa corrente <strong>supera 85%</strong> da receita corrente sem exceder 95%, as medidas podem ser implementadas, no todo ou em parte, por ato do Chefe do Poder Executivo com vigência imediata, submetido em regime de urgência ao Legislativo (§§ 1º e 2º). Superado o patamar de 95% e enquanto todas as medidas não forem adotadas por todos os Poderes e órgãos, conforme declaração do Tribunal de Contas, o ente fica impedido de receber garantia de outro ente da Federação e de contratar operação de crédito com outro ente (§ 6º)." }),
        h("p", { html: "<strong>Metodologia do painel.</strong> Numerador e denominador vêm do balanço orçamentário (Anexo 1 do RREO). A janela de 12 meses é montada com os valores acumulados: acumulado até o bimestre do ano corrente, mais o total do ano anterior, menos o acumulado do ano anterior até o mesmo bimestre. O indicador principal usa a despesa corrente <strong>liquidada</strong> e inclui as operações intraorçamentárias nos dois termos, o que resulta na leitura mais conservadora. A tabela traz também a apuração sem as intraorçamentárias e com a despesa empenhada; esta última tende a superestimar a relação ao longo do ano, por causa dos empenhos globais e por estimativa emitidos no início do exercício." }),
        h("p", { html: "A Constituição não detalha a fórmula, e a apuração oficial do TCE-MG, feita com os dados do SICOM, pode adotar critérios diferentes (por exemplo, quanto às deduções da receita e aos restos a pagar). O número deste painel serve ao acompanhamento gerencial e deve ser conferido com a metodologia do Tribunal." })));
    setTimeout(() => linhas(g, {
      categorias: serie.map((p) => `${ORD(p.bimestre)}/${String(p.ano).slice(2)}`), fmt: (v) => F.pct(v, 2), fmtEixo: (v) => F.pct(v, 0), minY: Math.min(80, Math.floor(Math.min(...serie.map((p) => p.indice_exceto_intra * 100)) / 5) * 5), maxY: Math.max(100, Math.ceil(Math.max(...serie.map((p) => p.indice * 100)) / 5) * 5),
      limites: [{ valor: 85, nome: "85%" }, { valor: 95, nome: "95%" }], altura: 300,
      series: [{ nome: "Com intraorçamentárias", cor: CORES[0], pontos: serie.map((p) => p.indice * 100) }, { nome: "Sem intraorçamentárias", cor: CORES[1], pontos: serie.map((p) => p.indice_exceto_intra * 100) }],
    }));
    return raiz;
  };

  /* ---------------------------------------------------------- aba: dados do TCE-MG */
  const tceMg = () => {
    const arqs = (TCE && TCE.arquivos) || [], sonda = P.tce_mg.sonda;
    const raiz = h("div", {});
    raiz.append(h("p", { class: "intro" }, "Esta aba recebe os arquivos do Portal de Dados Abertos do TCE-MG referentes ao Município. Tudo o que for colocado na pasta dados/tce-mg do repositório é lido, inventariado e exibido aqui a cada atualização."));
    if (!arqs.length) raiz.append(h("div", { class: "aviso" }, h("strong", {}, "Nenhum arquivo do TCE-MG foi carregado ainda. "),
      "O portal do Tribunal não aceitou conexões vindas do ambiente em nuvem em que o painel foi construído, de modo que a carga inicial precisa ser feita a partir de um computador no Brasil. Enquanto isso, o painel funciona com os relatórios que o Município declara ao Tesouro Nacional (Siconfi), e as verificações que dependem do detalhe do SICOM aparecem como não avaliadas."));
    if (sonda) raiz.append(h("div", { class: "aviso" }, h("strong", {}, "Teste de acesso automático ao portal: "),
      sonda.acessivel ? `o servidor do GitHub alcançou o portal em ${F.data(sonda.data)} (resposta HTTP ${sonda.http}). A coleta automática é viável.`
        : `o servidor do GitHub não alcançou o portal em ${F.data(sonda.data)}. A carga segue manual.`));
    raiz.append(h("div", { class: "cartao texto", style: "margin-bottom:14px" }, h("h2", { style: "margin-bottom:10px" }, "Como carregar os arquivos"),
      h("ol", {},
        h("li", { html: `Acesse <a href="${P.meta.portal_tce_mg}" rel="noopener">${P.meta.portal_tce_mg.replace("https://", "").replace(/\/$/, "")}</a>, selecione o Município de ${P.meta.municipio} e baixe os conjuntos de dados dos exercícios de ${P.meta.exercicios.join(", ")}.` }),
        h("li", { html: "No repositório do GitHub, abra a pasta <code>dados/tce-mg</code>, crie uma subpasta para cada exercício (por exemplo, <code>dados/tce-mg/2026</code>) e envie os arquivos pelo botão Add file, Upload files. São aceitos CSV, TXT, JSON e ZIP." }),
        h("li", {}, "Ao confirmar o envio, o GitHub reprocessa o painel sozinho e esta aba passa a mostrar o inventário, com colunas, totais e amostra de cada arquivo.")),
      h("p", {}, "Com a estrutura real dos arquivos à vista, o passo seguinte é ligar as colunas aos indicadores e às regras de inconsistência que hoje dependem do SICOM, como os mínimos de educação e saúde, o repasse à Câmara, os créditos adicionais por decreto e o detalhe de empenhos, contratos e licitações.")));
    arqs.forEach((a) => raiz.append(h("div", { class: "cartao", style: "margin-bottom:14px" }, h("h2", {}, a.arquivo),
      h("p", { class: "sub" }, a.erro ? a.erro : `${a.exercicio ? "Exercício " + a.exercicio + ". " : ""}${nf().format(a.linhas)} linhas, ${a.colunas.length} colunas, codificação ${a.codificacao}, separador "${a.separador}".`),
      a.colunas && a.colunas.length ? tabela(["Coluna", "Tipo", "Preenchidos", "Distintos", "Soma ou valores mais frequentes"], a.colunas.map((c) => h("tr", {}, h("td", {}, c.nome), h("td", {}, c.tipo),
        h("td", {}, nf().format(c.preenchidos)), h("td", {}, nf().format(c.distintos)),
        h("td", { style: "white-space:normal;text-align:left" }, c.soma != null ? nf({ maximumFractionDigits: 2 }).format(c.soma) : (c.valores || []).map(([k, q]) => `${k} (${q})`).join("; "))))) : null,
      a.amostra && a.amostra.length ? h("details", {}, h("summary", {}, "Amostra das primeiras linhas"), tabela(a.colunas.map((c) => c.nome), a.amostra.map((l) => h("tr", {}, l.map((v) => h("td", {}, v)))))) : null)));
    return raiz;
  };

  /* ---------------------------------------------------------- moldura */
  const ABAS = [["visao", "Visão geral", visao], ["comparativo", "Comparativo de exercícios", comparativo],
    ["inconsistencias", "Inconsistências", inconsistencias], ["art167a", "Art. 167-A", art167a], ["tce", "Dados do TCE-MG", tceMg]];

  const render = () => {
    ocultarDica();
    const nAp = P.inconsistencias.filter((a) => a.exercicio === P.meta.exercicio_corrente && a.situacao === "apontamento").length;
    const nav = $("#abas"); nav.textContent = "";
    ABAS.forEach(([id, nome]) => nav.append(h("button", { class: "aba", role: "tab", type: "button", "aria-selected": String(E.aba === id), onclick: () => { E.aba = id; render(); $("#conteudo").focus({ preventScroll: true }); } },
      nome, id === "inconsistencias" && nAp ? h("span", { class: "conta", title: `${nAp} apontamentos prováveis em ${P.meta.exercicio_corrente}` }, String(nAp)) : null)));
    const alvo = $("#conteudo"); alvo.textContent = "";
    alvo.append(ABAS.find(([id]) => id === E.aba)[2]());
    try { history.replaceState(null, "", "#" + E.aba); } catch (_) { /* sem histórico */ }
  };

  const iniciar = async () => {
    try {
      const [p, t] = await Promise.all([fetch("dados/painel.json", { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch("dados/tce-mg.json", { cache: "no-cache" }).then((r) => r.ok ? r.json() : null).catch(() => null)]);
      P = p; TCE = t;
    } catch (erro) {
      $("#posicao").textContent = "Não foi possível carregar os dados do painel.";
      $("#conteudo").append(h("div", { class: "aviso" }, h("strong", {}, "Dados indisponíveis. "), "O arquivo dados/painel.json não foi encontrado. Execute a coleta e a geração descritas no LEIAME do repositório."));
      return;
    }
    const m = P.meta, x = P.exercicios[m.exercicio_corrente];
    document.title = `Painel Fiscal de ${m.municipio}`;
    $("#titulo").textContent = `Painel Fiscal de ${m.municipio}/${m.uf}`;
    $("#posicao").textContent = `Exercício de ${m.exercicio_corrente}, com dados até o ${ORD(x.bimestre)} bimestre. Atualizado em ${F.data(m.coletado_em)}.`;
    $("#rodape").append(
      h("p", {}, `Fontes: Relatório Resumido de Execução Orçamentária e Relatório de Gestão Fiscal declarados pelo Município ao Tesouro Nacional (Siconfi), coletados em ${F.data(m.coletado_em)}, e arquivos do Portal de Dados Abertos do TCE-MG quando carregados no repositório.`),
      h("p", {}, "Os valores reproduzem o que foi declarado pelo ente e podem ser retificados. As verificações são indícios para o controle interno e não substituem a apuração do Tribunal de Contas do Estado de Minas Gerais."));
    E.ano = String(m.exercicio_corrente);
    const inicial = location.hash.slice(1);
    if (ABAS.some(([id]) => id === inicial)) E.aba = inicial;
    render();
  };

  $("#tema").addEventListener("click", () => {
    const raiz = document.documentElement;
    const escuro = raiz.dataset.theme ? raiz.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    raiz.dataset.theme = escuro ? "light" : "dark";
    try { localStorage.setItem("tema", raiz.dataset.theme); } catch (_) { /* armazenamento indisponível */ }
  });
  try { const t = localStorage.getItem("tema"); if (t) document.documentElement.dataset.theme = t; } catch (_) { /* idem */ }
  let espera;
  addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(() => document.querySelectorAll(".grafico").forEach((g) => g._redesenhar && g._redesenhar()), 150); });
  iniciar();
})();
