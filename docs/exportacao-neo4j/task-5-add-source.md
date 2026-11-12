# Task 5: validação do `add_source` lendo a fonte inteira

## O que o `add_source` valida

Na etapa 5 o agente propõe, para cada tabela, a chave e os tipos das colunas (`add_source`), ou a exclusão da tabela. Antes de a proposta chegar à página de revisão, `check_source` (em `akme/tools/sources.py`) confere a proposta contra o dado e recusa o que daria erro na carga:

- a fonte existe e tem linhas;
- as colunas da chave e dos tipos existem;
- nenhuma linha tem a chave vazia;
- a chave não se repete (duas linhas virariam o mesmo nó);
- os tipos são conhecidos, e chave ou coluna de join continua `string`;
- todo valor preenchido converte para o tipo declarado (`convert`, o mesmo da carga).

As mensagens de erro (`SourceError`) são as mesmas de antes.

## Por que agora lê a fonte inteira

Antes, a conferência lia uma amostra de no máximo 100.000 linhas (`MAX_ROWS` do exportador antigo). Uma chave repetida na linha 100.001 passava na etapa 5 e só estouraria na carga, ou seria cortada em silêncio. Agora `check_source` percorre a fonte inteira em blocos de 5.000 linhas, com `Adapter.iter_rows` (Task 1), numa única passada.

## Um leitor único

As regras de chave e tipo (chave vazia, chave repetida, conversão por coluna) vivem em um só lugar: `scan_source` e o dataclass `Scan`, em `akme/tools/neo4j_plan.py`. O plano da carga (`build_plan`) e o `check_source` chamam o mesmo leitor, então a etapa 5 e o dry-run não podem discordar sobre o mesmo dado. `check_source` só abre o adapter, confere que a fonte existe e traduz o `Scan` nas mesmas mensagens de erro de sempre.

O alerta da página de revisão "a fonte passa do limite de linhas da carga" desaparece: não existe mais limite, então não há o que avisar. O campo `checked.truncated` saiu do resultado, e `checked.rows` passa a ser o total de linhas da fonte.

## O que continua amostra

`suggest_sources` continua com `read_sample` (até 100.000 linhas). Ele só monta um rascunho de chave e tipos para o agente revisar, e quem decide é o humano na revisão; a conferência definitiva é a do `check_source`, que lê tudo. A única mudança é de importação: usa `labels_for` e `contract_keys` de `neo4j_plan` em vez do `n10s.py`, que sai na Task 7. `sources.py` não cita mais o n10s.

## Perfil de memória

A leitura guarda, por fonte, apenas:

- os `_id` repetidos (só os que aparecem mais de uma vez) e no máximo 5 exemplos legíveis de chave repetida, sem lista sem limite;
- a conversão é pulada para linhas com chave vazia (já recusadas) e para colunas `string` (texto sempre converte).

Além disso:

- um conjunto com o `_id` de cada linha (para achar chave repetida): cresce com o número de linhas, mas é uma string curta por linha, nunca a linha;
- contadores (linhas, chaves vazias, valores preenchidos e inválidos por coluna) e um exemplo por coluna.

As linhas são descartadas bloco a bloco. Uma fonte de 120.000 linhas passa em menos de um segundo no teste. O gerador de blocos é sempre fechado, inclusive em erro, e o adapter também (no Postgres o cursor tem nome fixo, então nunca há duas leituras abertas na mesma conexão; fonte vazia fecha a leitura antes de pedir o esquema).

## Mudança na página de revisão

Em `akme/tools/review_view.py`, `_source_checked` deixa de mostrar a linha "A fonte tem mais linhas do que o limite da carga" e de levantar o alerta. O JS da página (`akme/static/`) não lia `truncated`, então nada mudou lá. O `truncated` de `contracts.py` (amostra da junção entre duas tabelas) é outro assunto e não foi alterado.

## Testes (`tests/test_export_sources.py`)

- `test_check_source_reads_all_rows`: `itens_pedido` com 120.000 linhas e a chave composta repetida só na última; a proposta é recusada com "repete 1 valor". Prova que nada é cortado em 100.000.
- `test_check_source_counts_every_row_and_has_no_truncated`: `checked.rows` é o total e `truncated` não existe.
- `test_check_source_does_not_import_n10s`: o arquivo `sources.py` não contém "n10s".
- Os testes existentes (recusas parametrizadas, data em outro formato, revisão com nova checagem) passam sem mudança. Em `tests/test_review_stage.py` só saiu `truncated` de um dado de exemplo.

## TDD

RED: os três testes novos falharam (a chave repetida na linha 120.000 passava, `truncated` existia, `sources.py` importava o n10s). GREEN: `check_source` reescrito com a leitura em blocos; arquivo de testes verde.

## Revisão

A primeira revisão pediu unificar a leitura com o plano da carga, porque a lógica estava duplicada em `sources.py` e em `neo4j_plan.py`. Feito: um leitor único (`scan_source`), usado pelos dois.

Também ajustado: os exemplos de chave repetida têm limite (contador mais exemplos, sem lista crescente) e a conversão é pulada para linhas de chave vazia e colunas `string`, como no plano.

Diferença deliberada: fonte vazia. O `add_source` mantém a recusa "sem linhas": uma fonte aprovada sem nenhuma linha na etapa 5 quase certamente é engano. O plano da carga não recusa; ele reporta 0 nós e os problemas das relações dessa fonte.
