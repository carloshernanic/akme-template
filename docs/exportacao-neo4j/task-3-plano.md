# Task 3: plano da carga (dry-run) lendo em blocos

## O que mudou

Novo módulo `akme/tools/neo4j_plan.py` com `build_plan(project, batch=5000)`. Ele faz o dry-run da carga nova: lê cada fonte uma vez, em blocos, confere chave, tipos e joins, conta os nós e as arestas esperados e lista problemas e avisos. Não conecta ao banco e não guarda as linhas.

As funções `labels_for`, `contract_keys` e `join_columns` (e a leitura da decisão da etapa 5, `_config`) saíram de `akme/tools/n10s.py` e passaram a morar em `neo4j_plan.py`, com o mesmo comportamento. O `n10s.py` agora as importa com os nomes antigos (`_labels`, `_keys`, `_join_columns`), para o exportador antigo e seus testes seguirem funcionando até a Task 7, que o remove. O `neo4j_plan.py` não importa o `n10s.py`.

## Por que ler em blocos

O exportador antigo chamava `read_sample(fonte, 100_001)`: trazia a tabela inteira para a memória e recusava qualquer fonte com mais de 100 mil linhas ("fonte truncada"). No Olist, que soma cerca de 450 mil linhas (só `olist_order_items_dataset` tem 112.650), isso bloqueava a exportação.

O plano usa `iter_rows(fonte, 5000)`, criado na Task 1, e processa um bloco de cada vez. O teto deixa de existir: o que cabe na memória é o resumo de cada fonte, não as linhas.

As colunas vêm do primeiro bloco. Se a fonte estiver vazia, vêm do esquema (`read_schema`), consultado depois que a leitura em blocos terminou. Assim uma chave, um tipo ou um join que cite coluna inexistente é recusado mesmo numa tabela sem linhas.

As fontes são lidas uma depois da outra, e cada leitura termina (ou é fechada) antes da próxima começar. No Postgres o cursor do lado do servidor tem nome fixo, e duas leituras abertas na mesma conexão colidiriam. O adapter é fechado no fim, mesmo se der erro.

## As estruturas

| Estrutura | Campos | Para que serve |
|-----------|--------|----------------|
| `SourcePlan` | `source`, `label`, `key`, `types`, `columns`, `rows` | uma fonte que vira label: a chave aprovada, os tipos válidos, as colunas (do primeiro bloco ou, se a fonte estiver vazia, do esquema) e quantas linhas foram lidas |
| `EdgePlan` | `relation`, `domain`, `range`, `from_source`, `from_column`, `to_source`, `to_column`, `expected` | uma relação publicada: de onde sai, para onde vai e quantas arestas a carga deve criar |
| `Plan` | `project`, `sources`, `edges`, `nodes`, `relationships`, `relations_not_published`, `sources_skipped`, `problems`, `warnings`, `rows` | o resultado inteiro; `nodes` e `relationships` são o que a conferência da Task 6 vai comparar com o banco |

Também ficam no módulo os nomes reservados: `RESERVED_LABELS = ("Conceito", "_AkmeProjeto")` e `RESERVED_PROPS = ("_id", "_projeto", "_carga")`.

## Como as arestas são contadas sem guardar linhas

Durante a leitura, para cada coluna de join da fonte, o plano guarda um `Counter` de quantas linhas têm cada valor (o valor vira texto com `str`; células vazias são ignoradas). Só entram as linhas com a chave completa, porque só elas viram nó.

Para cada contrato com join:

- arestas esperadas = soma, sobre os valores `v` da origem, de `origem[v] × alvo[v]`;
- órfãos = soma de `origem[v]` para os valores que não aparecem no alvo.

Isso dá o mesmo número que o exportador antigo, que juntava as linhas e tirava pares repetidos, porque a chave é única dos dois lados (chave repetida já é problema). Assim, cada par ligado é um par distinto de nós.

Exemplo pequeno, relação `pertenceA` de `pedidos.id_cliente` para `clientes.id_cliente`:

| `pedidos.id_cliente` | linhas | `clientes.id_cliente` | linhas |
|----------------------|--------|-----------------------|--------|
| `1` | 2 | `1` | 1 |
| `2` | 1 | `2` | 1 |
| `9` | 1 | `3` | 1 |

- arestas esperadas = 2×1 (valor `1`) + 1×1 (valor `2`) = **3**;
- órfãos = 1 (o pedido com cliente `9`), que vira o aviso `relacao pertenceA: 1 de 4 linha(s) de pedidos sem alvo em clientes ficam sem aresta`;
- se nenhum dos 4 pedidos encontrasse cliente, seria o problema `relacao pertenceA: nenhuma das 4 linha(s) de pedidos encontra alvo em clientes`.

## Problemas (recusam a carga)

- `o bloco neo4j do akme.yml nao e mais lido: ...` (configuração antiga);
- `etapa 5 exclui fonte inexistente: <fonte>`;
- `fonte <fonte> sem classe associada: ...`;
- `fonte <fonte> citada na ontologia, mas nao existe no adapter`;
- `fonte <fonte> com mais de uma classe: ...`;
- `classe <C> em mais de uma fonte: ...`;
- **novo:** `classe <C> usa nome reservado do akme no Neo4j` (classe da ontologia chamada `Conceito` ou `_AkmeProjeto`);
- `etapa 5 cita fonte inexistente: <fonte>`;
- `etapa 5: tipo desconhecido <tipo> em <fonte>.<coluna>; ...`;
- `fonte <fonte> sem chave e tipos aprovados na etapa 5: ...` (com a variante "ha proposta pendente na pagina de revisao");
- `fonte <fonte> sem chave na decisao da etapa 5`;
- `fonte <fonte>: chave declarada usa coluna inexistente: ...`;
- **novo:** `<fonte>.<coluna> usa nome reservado do akme no Neo4j` (coluna `_id`, `_projeto` ou `_carga`);
- `fonte <fonte>: <n> linha(s) com chave <chave> vazia`;
- `<fonte>.<a+b> repete [...]: duas linhas virariam o mesmo no. Rode akme validate` (até 5 exemplos);
- `etapa 5 cita coluna inexistente: <fonte>.<coluna>`;
- `<fonte>.<coluna> e chave ou join e precisa ser string, nao <tipo>`;
- `<fonte>.<coluna>: <n> valor(es) invalido(s) para <tipo>, exemplo: <valor>` (pela `convert` da Task 2);
- `relacao <r>: coluna do join nao existe nos dados: ...`;
- `relacao <r>: nenhuma das <n> linha(s) de <origem> encontra alvo em <alvo>`.

## Avisos (a carga aceita)

- `<fonte>.<coluna> e medida, mas fica como texto e nao soma: declare o tipo na etapa 5`;
- `relacao <r>: <k> de <n> linha(s) de <origem> sem alvo em <alvo> ficam sem aresta`.

## O que saiu

- O problema `fonte <fonte> truncada: tem mais de 100000 linhas`: não há mais teto.
- O aviso `<fonte>.<coluna> vira a propriedade %... no Neo4j`: ele existia porque o nome da coluna virava parte de um IRI. Em Cypher a propriedade aceita qualquer nome, entre crases.

O texto de todos os outros problemas e avisos é o mesmo do exportador antigo.

## Perfil de memória

Por fonte, o plano guarda:

- um `set` com o `_id` de cada linha com chave completa, para achar chave repetida. É a maior estrutura: uma string por linha. Ele é esvaziado ao fim da fonte;
- até 5 exemplos de chave repetida;
- um `Counter` de valores inválidos por coluna tipada, com o primeiro exemplo;
- um `Counter` por coluna de join, com uma entrada por valor distinto. Esses ficam até o fim, porque as arestas são contadas depois de ler todas as fontes.

Nenhuma linha fica na memória depois do seu bloco. No pior caso, a memória cresce com o número de chaves distintas, não com o tamanho das linhas.

## Como foi testado

Arquivo: `tests/test_neo4j_plan.py` (41 casos, cerca de 70 s, quase todo o tempo na fixture `seeded`).

Portados, com o mesmo nome e a mesma asserção sobre `problems` e `warnings`, agora chamando `build_plan`:

- de `tests/test_publish_neo4j.py`: chave composta, fonte sem chave, chave com coluna inexistente, chave para fonte inexistente, chave composta repetida, parte da chave vazia, valor inválido (data e float), declaração de tipo inválida (5 casos), chave repetida, demo sem problemas, fonte sem classe, fonte excluída, exclusão de fonte inexistente, fonte com duas classes, duas fontes com a mesma classe, chave vazia, todos os problemas juntos, chave estrangeira órfã, relação sem nenhum alvo, coluna de join ausente, medida sem tipo e demo sem avisos;
- de `tests/test_export_sources.py`: fonte aprovada, fonte sem decisão, decisão pendente e bloco `neo4j` antigo no `akme.yml`.

As partes que dependiam do exportador antigo (o texto do `.nt`, `preview_lines`, a carga recusada com `dry_run=False`) ficaram de fora, porque o plano não carrega; elas voltam nas Tasks 6 e 7.

Novos:

- `test_plan_counts_demo`: 8 clientes, 17 itens, 10 pedidos, 8 produtos; 17 `contem`, 10 `pertenceA`, 17 `referencia`; 43 linhas lidas; e os campos de `SourcePlan` e `EdgePlan`.
- `test_no_row_limit`: um `itens_pedido.csv` com 120 mil linhas (gerado na cópia temporária do projeto) vira 120 mil nós, sem problema de truncada, e 120 mil arestas `contem`. Roda em menos de meio segundo.
- `test_plan_reads_each_source_in_blocks`: `iter_rows` é chamado uma vez por fonte com `batch=5000`, e `read_sample` nunca.
- `test_plan_closes_the_adapter_even_on_error`: erro de leitura sobe, e o adapter é fechado.
- `test_empty_source_plans_zero_nodes`: `produtos.csv` só com cabeçalho dá 0 nós, 0 arestas `referencia` e o problema de nenhuma linha com alvo, sem exceção.
- `test_empty_source_still_checks_declared_columns` e `test_empty_source_still_checks_join_columns`: numa fonte só com cabeçalho, chave, tipo e coluna de join inexistentes continuam sendo problema.
- `test_reserved_column_name_is_refused` e `test_reserved_class_name_is_refused`: os nomes reservados.
- `test_shared_names_live_in_the_plan`: o `n10s.py` usa as mesmas funções do plano.

## Evidência de TDD

- RED: `uv run pytest tests/test_neo4j_plan.py -q` falhou na coleta com `ImportError: cannot import name 'neo4j_plan' from 'akme.tools'`.
- GREEN: após implementar, `39 passed`.
- Correção da revisão: com a leitura do esquema desligada, os dois testes novos de fonte vazia falharam; com ela, passaram (`41 passed`). A suíte inteira, com os testes antigos do `n10s`, segue passando (a única falha é a pré-existente `test_optional_adapters_fail_clearly`).

## Revisão

A revisão independente aprovou a tarefa sem pontos críticos nem importantes. Ela confirmou que:

- os textos de problemas e avisos são iguais aos do exportador antigo;
- a contagem de arestas pelos contadores dá o mesmo número do exportador antigo, inclusive quando o join usa uma coluna que não é chave;
- nenhuma linha fica guardada na memória;
- o adapter é fechado mesmo quando a leitura dá erro.

Ponto corrigido: numa fonte vazia, o plano pulava a conferência de colunas, e uma chave, um tipo ou um join com coluna inexistente passava em silêncio. Agora as colunas vêm do esquema da fonte, e há dois testes novos para isso.

Pontos menores adiados:

- a ordem dos exemplos de chave repetida e a ordem dos problemas dentro de uma fonte mudaram (cosmético);
- `test_composite_key_identifies_items` ficou mais fraco que o original, porque o plano não gera o grafo. A identidade no grafo é testada nas Tasks 6 e 7.

Nota: na Task 5 a leitura em blocos de cada fonte (`_read`) foi extraída para `scan_source` e `Scan`, em `neo4j_plan.py`, e o `add_source` passou a usar o mesmo leitor.
