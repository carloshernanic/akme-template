# Glossario e convencoes da distribuidora (material do cliente)

## Siglas
- UF: unidade federativa, sigla de dois caracteres do estado.
- SKU: codigo unico do produto no catalogo.
- NF: numero da nota fiscal emitida no faturamento. Pedido sem NF ainda nao foi faturado.
- CNPJ: cadastro nacional da pessoa juridica, sem mascara.

## Convencoes de nomes
- Prefixo dt_: datas no formato ISO (AAAA-MM-DD).
- Prefixo vl_: valores em reais (BRL), com ponto decimal.
- Prefixo qt_: quantidades na unidade de medida do produto.
- Prefixo fl_: flags com S ou N.

## Regras implicitas
- Faturamento considera apenas pedidos com status FATURADO.
- O financeiro define cliente ativo como quem tem pedido faturado nos ultimos 180 dias; o ERP usa o campo fl_ativo. Quando divergem, vale o financeiro.
