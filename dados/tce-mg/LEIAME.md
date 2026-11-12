# Arquivos do Portal de Dados Abertos do TCE-MG

Coloque aqui os arquivos baixados de https://dadosabertos.tce.mg.gov.br/ para o
Município, em uma subpasta por exercício:

    dados/tce-mg/2024/
    dados/tce-mg/2025/
    dados/tce-mg/2026/

São lidos arquivos CSV, TXT e JSON, inclusive dentro de ZIP. A cada envio o
painel é reprocessado e a aba "Dados do TCE-MG" passa a mostrar o inventário
de cada arquivo (colunas, tipos, totais e amostra).

O arquivo `.sonda.json`, quando existe, é gravado pelo fluxo automático e
registra se o servidor do GitHub conseguiu alcançar o portal do Tribunal.
