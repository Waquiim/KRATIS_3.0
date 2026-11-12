# KRATIS 3.0

Painel de gestão municipal: painel fiscal de Viçosa/MG.

Visão gerencial das contas do Município de Viçosa/MG, mantida inteiramente no GitHub: os dados ficam versionados no repositório, um fluxo do GitHub Actions os atualiza duas vezes por semana e o painel é publicado pelo GitHub Pages. Não há servidor nem banco de dados para administrar.

O painel tem cinco abas. A **Visão geral** resume a execução do exercício (receita, despesa nos três estágios, resultado, RCL, pessoal, restos a pagar, receita por origem e despesa por grupo e por função). O **Comparativo de exercícios** confronta o exercício corrente com os dois anteriores, tanto no mesmo período do ano quanto no fechamento. A aba **Inconsistências** reúne verificações automáticas sobre os pontos que o controle externo costuma examinar, cada uma com situação, evidências, fundamento legal e providência sugerida. A aba **Art. 167-A** traz a relação entre despesa corrente e receita corrente em 12 meses, apurada a cada bimestre, com os marcos de 85% e 95%. A aba **Dados do TCE-MG** inventaria os arquivos do portal de dados abertos do Tribunal colocados no repositório.

## De onde vêm os dados

O painel foi concebido para os dados do [Portal de Dados Abertos do TCE-MG](https://dadosabertos.tce.mg.gov.br/). Ocorre que o servidor do portal recusa conexões vindas dos provedores de nuvem em que o painel foi construído, ao que tudo indica por restrição a acessos de fora do Brasil. Por isso há duas camadas de dados.

A primeira é o **Siconfi**, do Tesouro Nacional, de onde são coletados automaticamente o Relatório Resumido de Execução Orçamentária (bimestral) e o Relatório de Gestão Fiscal (quadrimestral, da Prefeitura e da Câmara), além do extrato de entregas. São declarações do próprio Município, com a mesma origem contábil do que é remetido ao SICOM. É essa camada que hoje alimenta a visão geral, o comparativo, o indicador do art. 167-A e a maior parte das verificações.

A segunda é a pasta `dados/tce-mg`, que recebe os arquivos baixados manualmente do portal do Tribunal. Como a estrutura desses arquivos não pôde ser examinada de antemão, o painel não presume nomes de colunas: ele lê qualquer CSV, TXT ou JSON (inclusive dentro de ZIP), identifica separador, codificação e tipo de cada coluna, soma as colunas numéricas e mostra uma amostra. Com os arquivos reais no repositório, o passo seguinte é ligar as colunas aos indicadores e às verificações que dependem do detalhe do SICOM, hoje listadas como "não avaliadas" (mínimos de educação e de saúde, FUNDEB, repasse à Câmara, créditos adicionais por decreto, empenhos, contratos e licitações).

A cada execução, o fluxo automático também testa se o servidor do GitHub alcança o portal do Tribunal e registra o resultado na aba Dados do TCE-MG. Se o acesso funcionar a partir do GitHub, a coleta do portal poderá ser automatizada.

## Como colocar no ar

1. O fluxo automático só roda a partir do ramo `main`. Se o código estiver em outro ramo, incorpore-o ao `main` (pela página do repositório, em Compare & pull request, e depois Merge).
2. No repositório, abra Settings, Pages e, em Build and deployment, escolha a fonte **GitHub Actions**.
3. Abra a aba Actions, selecione o fluxo "Atualizar e publicar o painel" e clique em Run workflow.

Ao fim da execução, o endereço do painel aparece na própria página do fluxo e em Settings, Pages. Dali em diante a atualização ocorre sozinha às segundas e quintas, e também sempre que algo for alterado em `dados/tce-mg`, no código ou no site. Em repositório privado, o GitHub Pages exige plano pago.

## Como carregar os arquivos do TCE-MG

Baixe do portal os conjuntos de dados de Viçosa para os três exercícios e envie-os pelo próprio site do GitHub (Add file, Upload files) para `dados/tce-mg/2024`, `dados/tce-mg/2025` e `dados/tce-mg/2026`. O painel é reprocessado em seguida.

## Indicador do art. 167-A da Constituição

O art. 167-A, incluído pela Emenda Constitucional nº 109/2021, manda apurar bimestralmente a relação entre despesas correntes e receitas correntes no período de 12 meses. Acima de 95%, fica facultada a adoção dos mecanismos de ajuste fiscal do caput e incidem as vedações do § 6º enquanto as medidas não forem adotadas por todos os Poderes. Entre 85% e 95%, as medidas podem ser adotadas por ato do Chefe do Executivo com vigência imediata (§ 1º).

O painel calcula a relação com o balanço orçamentário (Anexo 1 do RREO). A janela de 12 meses até o bimestre *b* do ano *A* é o acumulado de *A* até *b*, mais o total de *A-1*, menos o acumulado de *A-1* até *b*. O indicador principal usa a despesa corrente liquidada e inclui as operações intraorçamentárias nos dois termos, que é a leitura mais conservadora. São mostradas também a apuração sem as intraorçamentárias e a apuração com a despesa empenhada. A Constituição não detalha a fórmula, de modo que a apuração oficial do TCE-MG pode adotar critérios diferentes; o número do painel serve ao acompanhamento gerencial.

## Verificações da aba Inconsistências

Cada verificação resulta em uma de quatro situações: apontamento provável (indício objetivo de descumprimento ou de dado incoerente), ponto de atenção (risco que pede acompanhamento ou justificativa), regular e não avaliado (depende de dado ainda indisponível). Estão implementadas as seguintes, todas em `painel/regras.py`:

| Grupo | Verificação | Fundamento principal |
|---|---|---|
| Limites | Despesa corrente sobre receita corrente | CF, art. 167-A |
| Limites | Despesa com pessoal do Executivo e do Legislativo | LRF, arts. 19, 20, 22 e 59 |
| Limites | Dívida consolidada líquida | Resolução SF nº 40/2001 |
| Limites | Regra de ouro | CF, art. 167, III |
| Execução | Resultado da execução orçamentária | Lei nº 4.320/1964, art. 48, b |
| Execução | Arrecadação frente à previsão | LRF, art. 9º |
| Execução | Lastro dos créditos adicionais | Lei nº 4.320/1964, arts. 42 e 43 |
| Execução | Despesa empenhada acima da dotação | CF, art. 167, II |
| Execução | Disponibilidade de caixa por fonte | LRF, arts. 8º, 42 e 55, III |
| Execução | Cancelamento de restos a pagar processados | Lei nº 4.320/1964, arts. 36 e 63 |
| Execução | Resultado previdenciário do RPPS | CF, art. 40; LRF, art. 69 |
| Consistência | Coerência da RCL com a receita corrente | LRF, art. 2º, IV |
| Consistência | RCL divergente entre RREO, RGF do Executivo e RGF do Legislativo | LRF, arts. 53 e 55 |
| Consistência | Dívida consolidada no RREO e no RGF | LRF, arts. 53 e 55 |
| Consistência | Cruzamento entre os anexos do RREO | LRF, arts. 52 e 53 |
| Prazos | Entrega do RREO e do RGF | LRF, arts. 52 e 55 |

As verificações trabalham sobre o que o Município declarou. Um achado é um indício a conferir na origem, e não um juízo definitivo: a apuração oficial cabe ao Tribunal de Contas, com metodologia e dados próprios. Sobre os prazos, o Siconfi registra a data do último envio, de modo que um relatório retificado não permite saber se a primeira entrega foi tempestiva.

## Estrutura

```
config.json                 município, código IBGE e número de exercícios comparados
coleta/siconfi.py           baixa RREO, RGF e extrato de entregas do Siconfi
painel/dados.py             leitura dos relatórios e cálculo dos indicadores
painel/regras.py            verificações de inconsistência
painel/tce_mg.py            inventário dos arquivos do TCE-MG
painel/gerar.py             monta site/dados/painel.json
site/                       painel estático (HTML, CSS e JavaScript, sem dependências)
dados/siconfi/              relatórios coletados
dados/tce-mg/               arquivos do portal do TCE-MG, por exercício
tests/                      testes automatizados
.github/workflows/          atualização e publicação automáticas
```

## Rodar no computador

Basta o Python 3.10 ou superior, sem instalar nenhuma biblioteca.

```bash
python3 coleta/siconfi.py
```

```bash
python3 -m painel.gerar
```

```bash
python3 -m unittest discover -s tests
```

```bash
python3 -m http.server 8000 --directory site
```

O painel fica disponível em http://localhost:8000. Para adaptar a outro município, altere o nome e o código IBGE em `config.json`.
