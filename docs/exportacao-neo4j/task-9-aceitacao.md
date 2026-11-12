# Task 9: aceitação real (demo, Olist e Postgres)

As Tasks 1 a 8 foram testadas com bancos falsos, a demo pequena e um Neo4j descartável. Esta tarefa roda o exportador em condições reais: o Olist inteiro (446.873 linhas), um banco carregado pela exportação antiga, um Postgres de verdade e as perguntas de competência respondidas no grafo. Nenhum código do produto mudou. Foram criados dois arquivos de apoio e um teste:

| Arquivo | Para que serve |
|---|---|
| `examples/local_demo/amostra_valores.py` | Sorteia linhas da origem e confere, célula a célula, valor e tipo no Neo4j. Serve para qualquer projeto |
| `examples/local_demo/perguntas_neo4j.cypher` | As perguntas do gabarito da demo escritas em Cypher, com um comentário por pergunta |
| `tests/test_neo4j_integration.py::test_real_competency_questions` | Carrega a demo, roda cada consulta do arquivo e compara com o `gabarito.json`. Pulado sem `AKME_NEO4J_TEST_*` |

## O que cada passo prova

| Passo | O que prova | Por que importa |
|---|---|---|
| 1. Demo em banco vazio, duas cargas | A carga grava o previsto, a conferência confirma e repetir não duplica nem apaga | É o caminho do primeiro uso, e a segunda carga é o uso de todo dia |
| 2. Olist completo | O exportador lê tabelas acima do antigo teto de 100 mil linhas, em blocos, e grava um nó por linha e uma aresta por par do join | Era o bloqueio que motivou a troca: o `olist_order_items_dataset` tem 112.650 linhas |
| 3. Sincronização no Olist | Linhas apagadas na origem somem do grafo, com as arestas delas, e nada mais | Sem isso, o grafo fica com dado que o cliente já apagou |
| 4. Banco da exportação antiga | O akme reconhece um banco do n10s e recusa antes de gravar | Quem seguiu o guia antigo tem esse banco; misturar os dois modelos corromperia o grafo |
| 5. Postgres real | A leitura em blocos funciona com cursor do lado do servidor, não só com o cursor falso dos testes | O cliente real está num banco, não em CSV |
| 5a. Fidelidade de valores | Cada nó sorteado é igual à conversão da carga (`convert` e `node_id`) aplicada à linha da origem: mesmo valor, mesmo tipo, sem propriedade a mais ou a menos. Se o próprio `convert` está certo, quem prova é `tests/test_neo4j_values.py` | Contar nós não prova que os valores chegaram ao banco como a carga os montou |
| 5b. Perguntas de competência | As perguntas do negócio têm a mesma resposta no grafo e nos CSVs | É o uso final: um LLM ou uma pessoa consultando o grafo |

## Ambiente

- Mac com Apple M5, 24 GB de memória, macOS 26.3.1; Docker 29.2.0.
- Neo4j 2026.10.1 Community, descartável (`akme-neo4j-t6`, porta 27687), sem plugin. Os contêineres de Mateus (`akme-neo4j` e `akme-neo4j-teste`) não foram usados.
- Python 3.12.13, driver `neo4j` 6.4.1, `psycopg` 3.3.6, uv 0.11.14.
- Código no commit `d791dff` da branch `feat/exportacao-neo4j-cypher`.
- Senhas geradas na hora, guardadas fora do repositório e passadas por variável de ambiente. Os comandos abaixo usam `$AKME_NEO4J_PASSWORD`.

## 1. Demo em banco vazio

Cópia temporária do repositório (`git archive HEAD`), com `akme init --demo` e `akme demo`, que aplica as decisões `add_source` do `seed_edits.yml`. Banco limpo antes (nós, restrições e índices).

```bash
akme init --demo && akme demo
echo y | akme publish --target neo4j --no-dry-run   # duas vezes
uv run --extra neo4j python examples/local_demo/verificar_neo4j.py
```

| Conferência | Resultado |
|---|---|
| 1ª carga | `banco: vazio`, 7 lotes, `removed` 0 nós e 0 arestas, `verification.ok` |
| 2ª carga | `banco: projeto local_demo, sera atualizado`, `banco 8 -> origem 8` em cada label, `removed` 0/0, `verification.ok` |
| `verificar_neo4j.py` | 45 de 45 OK, 216 células comparadas, saída 0 |

## 2. Olist completo

### A cópia e as correções

O Olist de Mateus está na raiz, sem commit (`examples/olist/` e a `ontology/` da raiz). Para não mexer nele, tudo rodou numa cópia temporária fora do repositório: os 9 CSVs, a pasta `ontology/` inteira e um `akme.yml` novo.

```yaml
project: olist
adapter: local_folder
local_folder:
  path: data
```

Sem correção nenhuma, o dry-run recusa com 2 problemas:

```text
fonte olist_products_dataset com mais de uma classe: CategoriaProduto, Produto
fonte product_category_name_translation sem chave e tipos aprovados na etapa 5: rode suggest_sources e decida na pagina de revisao
```

Um terceiro problema só aparece depois de corrigir esses dois, porque a relação `pertenceACategoria` nem entra no plano enquanto a fonte tem duas classes:

```text
relacao pertenceACategoria: coluna do join nao existe nos dados: product_category_name_translation.﻿product_category_name
```

O nome da coluna nessa mensagem começa com um caractere invisível, o `U+FEFF`.

As três correções, **só na cópia**:

1. **Mapping de `categoria_produto`.** O termo é da classe `CategoriaProduto`, mas estava mapeado para a tabela de produtos, que já é `Produto`. Uma tabela vira uma classe só, então o plano recusa. A coluna com o nome da categoria também existe na tabela de tradução, que é a fonte natural de `CategoriaProduto`.
2. **`U+FEFF` no contrato `pertenceACategoria`.** O CSV de tradução começa com BOM. Desde a Task 1, o adapter lê com `utf-8-sig` e o BOM não vai para o nome da coluna; o contrato foi gravado antes disso, com o BOM no nome.
3. **`add_source` da tabela de tradução**, com chave `product_category_name` e sem tipos. Feito pelo caminho normal: `propose_edit` e `apply_edit` (aprovado como `aceite-task9`), que conferiu a chave contra a fonte inteira (71 linhas). O `content.yml` ganhou a entrada em `sources` e a evidência, e o `changelog.yml` o registro, no mesmo formato das outras fontes.

```diff
@@ mappings
 - term: categoria_produto
-  source: olist_products_dataset
+  source: product_category_name_translation
   column: product_category_name
   role: dimension
@@ relation_contracts, pertenceACategoria
     to:
       source: product_category_name_translation
-      column: "﻿product_category_name"
+      column: product_category_name
@@ sources
+- source: product_category_name_translation
+  key:
+  - product_category_name
+  types: {}
@@ evidence
+- decision: add_source-7571d7eb
+  source: 'Aceite da Task 9, so na copia: chave do contrato pertenceACategoria; os
+    dois nomes ficam texto.'
+  requirement_id: null
+  approved_by: aceite-task9
```

Geolocalização e pagamentos continuam fora, como a etapa 5 de Mateus decidiu.

**A ontologia da raiz não foi corrigida, de propósito:** o teste de primeiro uso de Mateus vai partir dela como está, sem estas correções.

### Dry-run, carga e conferência

```bash
uv run akme publish --target neo4j                     # dry-run
echo y | uv run akme publish --target neo4j --no-dry-run
```

O dry-run, com as correções: 7 fontes no escopo, 2 excluídas, `problems` vazio, 205 lotes previstos. Os avisos:

- `olist_order_reviews_dataset.order_id` e `olist_orders_dataset.order_delivered_customer_date` são medidas, mas ficam como texto. São os mappings de contagem e de atraso: a contagem não precisa de tipo e o atraso é calculado na consulta, a partir do texto.
- `contemItem`: 775 de 99.441 pedidos não têm item e ficam sem aresta.
- `pertenceACategoria`: 13 de 32.341 produtos com categoria não acham tradução e ficam sem aresta.
- `citaMotivo` não é publicada: não tem join.

Contagens, cada uma conferida contra os CSVs por um script à parte (`csv` da biblioteca padrão, sem o akme):

| Label | Esperado (linhas do CSV) | Plano | Banco |
|---|---|---|---|
| `Pedido` | 99.441 | 99.441 | 99.441 |
| `ItemPedido` | 112.650 | 112.650 | 112.650 |
| `Produto` | 32.951 | 32.951 | 32.951 |
| `Vendedor` | 3.095 | 3.095 | 3.095 |
| `Cliente` | 99.441 | 99.441 | 99.441 |
| `Avaliacao` | 99.224 | 99.224 | 99.224 |
| `CategoriaProduto` | 71 | 71 | 71 |

| Aresta | Esperado (join nos CSVs) | Plano | Banco |
|---|---|---|---|
| `contemItem` | 112.650 | 112.650 | 112.650 |
| `vendidoPor` | 112.650 | 112.650 | 112.650 |
| `referenteAoProduto` | 112.650 | 112.650 | 112.650 |
| `feitoPorCliente` | 99.441 | 99.441 | 99.441 |
| `refereSeAoPedido` | 99.224 | 99.224 | 99.224 |
| `pertenceACategoria` | 32.328 | 32.328 | 32.328 |

Dois números pedem explicação:

- **Avaliações:** o `wc -l` do CSV dá 104.720 linhas, porque há comentários com quebra de linha dentro das aspas. São 99.224 registros. `review_id` sozinho não é chave: há 98.410 valores distintos. Por isso a etapa 5 de Mateus aprovou o par (`review_id`, `order_id`), único nos 99.224. A regra C-001 (uma avaliação por pedido) é aplicada na consulta, não na carga, para não perder dado.
- **`pertenceACategoria`:** 32.328 e não 32.951, porque 610 produtos não têm categoria e 13 têm categoria sem tradução (`pc_gamer` e `portateis_cozinha_e_preparadores_de_alimentos`).

A carga terminou com `banco: vazio`, 205 de 205 lotes, `removed` 0/0 e `verification.ok`. O banco ficou com 446.892 nós: 446.873 de dados, 18 `Conceito` e a marca do projeto, todos com a mesma `_carga`.

### Tempo e memória

Medidos com `/usr/bin/time -l`, que dá o tempo total e a memória máxima do processo (RSS).

| Medida | Tempo | Memória máxima |
|---|---|---|
| Dry-run, lendo 446.873 linhas | 2,2 s | 144 MB |
| 1ª carga, banco vazio | 31,4 s | 224 MB |
| 2ª carga, com sincronização | 29,7 s | 212 MB |
| Amostra de valores (5a) | 2,7 s | 160 MB |

O contêiner do Neo4j ficou com 1,193 GiB de memória depois das cargas (`docker stats`).

## 3. Sincronização no Olist

10 avaliações apagadas do CSV da cópia: os 10 primeiros registros de uma linha só, sem comentário, para não tocar em registro com quebra de linha. Um script conferiu que o CSV ficou com 99.214 registros e que os outros continuaram iguais. Antes da carga, as 10 tinham 10 nós e 10 arestas no banco.

| Conferência | Resultado |
|---|---|
| Resumo antes de confirmar | `Avaliacao: banco 99224 -> origem 99214`; os outros labels iguais |
| `removed` | 10 nós e 10 arestas, as `refereSeAoPedido` dessas avaliações |
| `verification` | `ok`, sem divergências |
| Banco depois | 99.214 avaliações; nenhuma das 10; uma `_carga` só |

## 4. Banco da exportação antiga

Contêiner descartável `akme-neo4j-t9-legado` (Neo4j 2026.10.1, portas 37474 e 37687), com o jar do n10s 2025.06.1 montado só para leitura. A versão antiga do akme (commit `ec40d71`) rodou numa `git worktree` temporária e carregou a demo pelo n10s: 59 nós (`Resource`, `Class`, `Relationship`, `_GraphConfig` e os dados), 59 arestas e a restrição `n10s_unique_uri`.

A CLI nova, contra esse banco:

```text
banco: banco da exportacao antiga (n10s)
erro: banco carregado pela exportacao antiga (n10s); limpe-o com o comando do guia. Nada foi gravado
```

Parou antes da pergunta de confirmação, com saída 1. Nós, arestas, restrições, índices e contagem por label ficaram iguais antes e depois (`diff` vazio). Em seguida, o comando de limpeza do guia (subseção "Banco da exportação antiga") deixou o banco vazio, a carga nova achou `banco: vazio` e o verificador da demo terminou com `RESULTADO: todas as verificacoes passaram`. O contêiner, os volumes dele e a worktree foram removidos no fim.

## 5. Postgres real

Contêiner descartável `akme-pg-t9` (`postgres:16`, PostgreSQL 16.15, porta 25432), com `olist_order_items_dataset` carregada por `COPY`, todas as colunas como texto: 112.650 linhas.

```bash
AKME_PG_TEST_DSN=postgresql://postgres:$SENHA@127.0.0.1:25432/postgres \
  uv run --extra postgres pytest tests/test_adapters_iter_rows.py -q
```

| Conferência | Resultado |
|---|---|
| `tests/test_adapters_iter_rows.py`, com o teste real | 9 de 9 |
| `iter_rows(batch=5000)` | 112.650 linhas em 23 blocos (22 de 5.000 e 1 de 2.650), em 0,28 s |
| `scan_source` com a chave (`order_id`, `order_item_id`) | 112.650 linhas completas, 0 repetidas, 0 valores inválidos em `price` e `freight_value` como `float` |

O contêiner foi removido com o volume no fim.

## 5a. Fidelidade de valores

```bash
uv run --extra neo4j python examples/local_demo/amostra_valores.py <akme.yml> --n 200 --seed 42
```

Como o script funciona:

1. Monta o plano (`build_plan`) para saber a classe, a chave e os tipos de cada fonte, como a carga.
2. Lê cada fonte inteira pelo adapter do projeto e sorteia até 200 linhas com a chave completa, por amostragem de reservatório com semente fixa.
3. Converte cada célula preenchida com `convert`, pelo tipo aprovado (texto se não declarado).
4. Busca o nó por label e `_id`, no projeto.
5. Compara campo a campo: o mesmo valor e o mesmo tipo Python, e nenhuma propriedade a mais ou a menos além de `_id`, `_projeto` e `_carga`. Duas linhas sorteadas com o mesmo `_id` contam como divergência, e não são juntadas.

As datas voltam do driver como `neo4j.time.Date`; o script chama `to_native()`, que dá um `datetime.date`, antes de comparar. A saída mostra só contagens e nomes de coluna, nunca valores das linhas.

| Projeto | Fontes | Linhas | Células | Divergências |
|---|---|---|---|---|
| Demo | 4 | 43 (todas) | 213 | 0 |
| Olist | 7 | 1.271 | 7.838 | 0 |

No Olist, nenhuma coluna é `date`: as datas têm hora e ficaram texto na etapa 5. A conversão de datas é exercitada na demo (`dt_cadastro`, `dt_pedido`).

**O script acha erro quando há erro.** Com a demo carregada, o banco foi adulterado à mão: uma data virou texto, um preço ganhou um centavo e um nó ganhou uma propriedade a mais. O script achou as 3 divergências (`tipo:dt_cadastro`, `valor:vl_unitario`, `a mais:extra`). Uma carga nova desfez as três, porque cada nó é regravado inteiro com os valores da origem.

## 5b. Perguntas de competência

### Demo

A demo não tem perguntas com resposta em `validation/`. O oráculo dela é o `examples/local_demo/gabarito.json`, que o `oracle.py` calcula dos CSVs sem o exportador. Cada resposta do gabarito virou uma consulta Cypher em `examples/local_demo/perguntas_neo4j.cypher`, com os nomes do grafo. O teste `test_real_competency_questions` carrega a demo, roda cada consulta e compara. Ele falha se alguma resposta do gabarito ficar sem consulta. A comparação exige o mesmo tipo (`2999.0` não vale `2999`), e o dinheiro é somado no Cypher em centavos inteiros, para comparar sem arredondamento de `float`.

| Pergunta | Gabarito | Grafo |
|---|---|---|
| Clientes sem pedido | `3`, `7` | `3`, `7` |
| Produtos do pedido 1001 | ARE-M3 5, ARG-20 10, CIM-50 100 | igual |
| Todo pedido tem um cliente | sim | sim |
| Faturamento (status FATURADO) | 23077.35 | 23077.35 |
| Soma de `qt_itens` | 2999 | 2999 |
| `vl_total` sem filtro | 26797.35 | 26797.35 |
| Armadilha de fan-out, reproduzida | 49819.30 | 49819.30 |
| Chave única em `Cliente`, `ItemPedido`, `Pedido` e `Produto` | sim, nas 4 | sim, nas 4 |

As 11 batem. As duas perguntas de `examples/local_demo/questions.yml` não têm valor no oráculo e ficaram de fora, com o motivo:

- **CQ-002**, clientes ativos sem compra nos últimos 90 dias: a resposta depende de uma data de referência que o oráculo não fixa.
- **CQ-003**, ticket médio por categoria: o grafo responde, mas o `oracle.py` não calcula esse número para comparar.

### Olist

As três perguntas reservadas de `validation/questions.yml` (a da raiz, que não foi alterada), respondidas por Cypher no Olist carregado, antes do passo 3. As consultas aplicam as regras da ontologia:

- C-001: uma avaliação por pedido, a de `review_answer_timestamp` mais recente;
- C-002: cada pedido conta uma vez por categoria ou vendedor, nunca uma vez por item;
- C-003: atraso só para pedido `delivered` com data de entrega.

```cypher
// CQ-006: pior nota media por categoria, entre as com 30 ou mais pedidos avaliados
MATCH (a:Avaliacao)-[:refereSeAoPedido]->(p:Pedido)
WITH p, a ORDER BY a.review_answer_timestamp DESC, a.review_id DESC
WITH p, head(collect(a)) AS a
MATCH (p)-[:contemItem]->(:ItemPedido)-[:referenteAoProduto]->(pr:Produto)
OPTIONAL MATCH (pr)-[:pertenceACategoria]->(c:CategoriaProduto)
WITH DISTINCT coalesce(c.product_category_name, pr.product_category_name, 'sem categoria') AS categoria, p, a
WITH categoria, avg(toFloat(a.review_score)) AS media, count(*) AS pedidos
WHERE pedidos >= 30
RETURN categoria, round(media, 2) AS media, pedidos ORDER BY media ASC LIMIT 3;

// CQ-007: pior nota media por vendedor, entre os com 30 ou mais pedidos avaliados
MATCH (a:Avaliacao)-[:refereSeAoPedido]->(p:Pedido)
WITH p, a ORDER BY a.review_answer_timestamp DESC, a.review_id DESC
WITH p, head(collect(a)) AS a
MATCH (p)-[:contemItem]->(:ItemPedido)-[:vendidoPor]->(v:Vendedor)
WITH DISTINCT v, p, a
WITH v.seller_id AS vendedor, avg(toFloat(a.review_score)) AS media, count(*) AS pedidos
WHERE pedidos >= 30
RETURN vendedor, round(media, 2) AS media, pedidos ORDER BY media ASC LIMIT 1;

// CQ-008: atraso do pedido, por dia; as datas ficaram texto, entao a consulta corta a hora
MATCH (p:Pedido {order_id: '88c588c116fd06fb8e48dd83af88ec4a'})
WITH p, date(left(p.order_delivered_customer_date, 10)) AS entregue,
        date(left(p.order_estimated_delivery_date, 10)) AS estimado
RETURN p.order_status AS status, entregue, estimado,
       CASE WHEN p.order_status = 'delivered' AND p.order_delivered_customer_date IS NOT NULL
            THEN duration.inDays(estimado, entregue).days END AS atraso_dias;
```

| Pergunta | Esperado | Grafo | Resultado |
|---|---|---|---|
| CQ-006 | `moveis_escritorio` | `moveis_escritorio`, 3,62 em 1.263 pedidos; depois `fashion_roupa_feminina` 3,69 e `fashion_roupa_masculina` 3,70 | bate |
| CQ-007 | `1ca7077d890b907f89be8c954a02686a` | o mesmo vendedor, 2,33 em 114 pedidos | bate |
| CQ-008 | atrasou 10 dias (entregue em 2017-12-22, estimado para 2017-12-12) | `delivered`, entregue 2017-12-22, estimado 2017-12-12, 10 dias | bate |

As três batem, com os mesmos números que o changelog registrou quando as respostas foram reservadas a partir dos CSVs. O corte de 30 ou mais pedidos avaliados não está no texto da pergunta: veio da justificativa registrada no changelog. Sem o corte, a pior categoria seria `seguros_e_servicos`, com 2 pedidos. A consulta da CQ-006 não depende da aresta `pertenceACategoria`: o `coalesce` cai para a propriedade `product_category_name` do `Produto` quando a aresta falta. A dependência real é outra: sem a correção 1, a carga nem acontece, porque o dry-run recusa a ontologia da raiz, e não há grafo para consultar.

## O que falhou ou surpreendeu

- **O `U+FEFF` aparece em etapas.** Na ontologia da raiz, o dry-run mostra 2 problemas; o terceiro só aparece depois. E a mensagem desse terceiro traz o caractere invisível sem marcá-lo: quem lê vê `product_category_name` nos dois lados e pode não entender a diferença. Fica como sugestão para o primeiro uso de Mateus: a mensagem poderia escrever o `U+FEFF` de forma visível.
- **Memória bem abaixo do que o guia avisava.** A versão anterior do guia dizia que o driver podia passar de 1 GB numa tabela de centenas de milhares de linhas com texto acentuado. No Olist inteiro, com os comentários das avaliações, o processo ficou em 224 MB de memória residente máxima. O guia foi corrigido com este número.
- **O dry-run é rápido:** 2,2 s para ler as 446.873 linhas. A carga leva cerca de 30 s, quase tudo esperando o Neo4j.
- **Endereço do Browser fixo.** No fim da carga, a CLI indica `http://localhost:7474`, mas neste teste o Browser estava na 27474, porque o contêiner era outro. É o comportamento previsto (porta padrão), e não afeta o guia, que usa a 7474.
- **O jar antigo funciona no Neo4j novo.** O n10s 2025.06.1 carregou no Neo4j 2026.10.1 sem erro. O passo 4 reproduziu de fato o banco de quem seguiu o guia antigo.
- **`psycopg` instalado no ambiente.** O `uv run --extra postgres` instalou o `psycopg` no ambiente do projeto. Com ele, `test_optional_adapters_fail_clearly` falha, como já estava anotado.

## Limites

- Uma máquina só, com Docker local. Aura e Enterprise não foram testados.
- O Postgres foi testado só na leitura (adapter e `scan_source`), com uma tabela. A carga completa no Neo4j a partir do Postgres não foi rodada.
- A amostra de valores sorteia 200 linhas por fonte, não todas. Na demo, cobre todas; no Olist, cerca de 0,3%.
- A amostra compara o grafo com o mesmo `convert` e o mesmo `node_id` que a carga usa. Ela prova que o nó é igual à conversão da carga aplicada à origem, e que nada se perdeu ou sobrou no caminho até o banco. Não prova que o `convert` em si está certo; isso é coberto por `tests/test_neo4j_values.py`.
- Fonte do plano sem chave não vira nó e é pulada pela amostra, com uma linha `PULADA` na saída. Neste teste, nenhuma fonte foi pulada.
- As perguntas do Olist foram respondidas por consultas avulsas, guardadas só na cópia temporária e nesta página. Só as da demo viraram teste automático.
- Tempo e memória são de uma execução, sem repetição.

## Testes

- `uv run --extra neo4j pytest tests/test_neo4j_integration.py -q`, com `AKME_NEO4J_TEST_*` no Neo4j descartável: 9 de 9. Sem as variáveis: 9 pulados.
- `uv run pytest -q`: 321 passaram, 11 foram pulados e 1 falhou, a já conhecida `test_optional_adapters_fail_clearly` (5 min 23 s), com o `psycopg` instalado e sem `AKME_NEO4J_TEST_*`.
- `uv run --extra docs mkdocs build --strict`: sem avisos.

## Revisão

A revisão independente aprovou a tarefa, sem problemas críticos nem importantes.

- **Números rastreados:** cada número desta página foi conferido contra o comando que o produziu, no relatório da tarefa.
- **Amostra de valores:** compara tipo e valor exatos e pegou as três adulterações feitas de propósito.
- **Corte de 30 pedidos:** foi registrado no changelog e aprovado por Mateus antes desta execução, quando as respostas foram reservadas. Não é um ajuste para a resposta bater.

Corrigido depois da revisão:

- **CQ-006:** o parágrafo diz que a consulta cai para a propriedade do `Produto` quando falta a aresta, e que a dependência real da correção 1 é a carga acontecer.
- **O que a amostra prova:** a tabela dos passos e os limites dizem que ela confere o nó contra a conversão da carga, e que o `convert` em si é coberto por `tests/test_neo4j_values.py`.
- **Teste das perguntas da demo:** exige o mesmo tipo em inteiros e booleanos, e compara dinheiro em centavos inteiros, sem `float`.
- **`amostra_valores.py`:** avisa com `PULADA` a fonte sem chave, e conta como divergência duas linhas sorteadas com o mesmo `_id`.
- **Passo 4 e memória do contêiner:** o resultado do verificador e o `docker stats` estão como foram registrados.
- **Guia:** o aviso de memória em "Limites conhecidos" passou a citar o número medido no Olist.
