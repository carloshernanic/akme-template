# Task 9: aceitação real (demo, Olist e Postgres)

As Tasks 1 a 8 foram testadas com bancos falsos, a demo pequena e um Neo4j descartável. Esta tarefa roda o exportador em condições reais: a demo, o Olist inteiro (446.873 linhas), um banco carregado pela exportação antiga, um Postgres de verdade e as perguntas de competência respondidas no grafo.

A aceitação foi feita primeiro no commit `d791dff` e **repetida na rodada final de 12/11/2026, sobre o código final** (o `974da8a` mais as correções da rodada: `_descricao` opcional, mensagem do caractere invisível e fixture da suíte). Os números desta página são os da rodada final, os mesmos usados no guia, na [visão geral](index.md) e em [Uso real do grafo](uso-do-grafo.md). Só o passo 4 (banco da exportação antiga) não foi repetido: é da execução de `d791dff`.

**O que é reproduzível e o que é registro:**

- **A aceitação oficial, reproduzível, é a da demo** (`examples/local_demo`): dados, ontologia, gabarito, verificador e perguntas estão no repositório, e qualquer pessoa repete os passos 1, 5, 5a e 5b com os comandos desta página.
- **O Olist é um registro de execução.** Os dados (`examples/olist/`) e a ontologia do Olist (`ontology/` da raiz) **não estão no repositório**, e a carga usou **uma cópia com três correções** que a ontologia da raiz não tem (mapping de `categoria_produto`, `U+FEFF` no contrato `pertenceACategoria` e `add_source` da tabela de tradução; seção 2). Os números do Olist mostram que o exportador aguenta a escala, mas não dá para refazê-los só com o que está commitado.

Arquivos de apoio:

| Arquivo | Para que serve |
|---|---|
| `examples/local_demo/amostra_valores.py` | Sorteia linhas da origem e confere, célula a célula, valor e tipo no Neo4j. Serve para qualquer projeto |
| `examples/local_demo/verificar_neo4j.py` | Confere o grafo da demo contra os CSVs e o gabarito (54 verificações). Lê o modo da `_descricao` do `akme.yml` da pasta atual |
| `examples/local_demo/perguntas_neo4j.cypher` | As perguntas do gabarito da demo escritas em Cypher, com um comentário por pergunta |
| `examples/olist_perguntas_neo4j.cypher` | As três perguntas de competência do Olist em Cypher, para rodar de novo; o pedido da CQ-008 entra por parâmetro (`$pedido`), sem valor de linha no arquivo |
| `tests/test_neo4j_integration.py::test_real_competency_questions` | Carrega a demo, roda cada consulta do arquivo e compara com o `gabarito.json`. Pulado sem `AKME_NEO4J_TEST_*` |
| `tests/test_neo4j_integration.py::test_real_load_from_postgres` | Carga completa da demo a partir de um Postgres real, com contagens, verificador e amostra. Pulado sem `AKME_PG_TEST_DSN` |

## O que cada passo prova

| Passo | O que prova | Por que importa |
|---|---|---|
| 1. Demo em banco vazio, duas cargas, sincronização | A carga grava o previsto, a conferência confirma, repetir não duplica nem apaga, e linha apagada na origem some do grafo | É o caminho do primeiro uso, e a segunda carga é o uso de todo dia |
| 2. Olist completo | O exportador lê tabelas acima do antigo teto de 100 mil linhas, em blocos, e grava um nó por linha e uma aresta por par do join | Era o bloqueio que motivou a troca: o `olist_order_items_dataset` tem 112.650 linhas |
| 3. Sincronização no Olist | Linhas apagadas na origem somem do grafo, com as arestas delas, e nada mais | Sem isso, o grafo fica com dado que o cliente já apagou |
| 4. Banco da exportação antiga | O akme reconhece um banco do n10s e recusa antes de gravar | Quem seguiu o guia antigo tem esse banco; misturar os dois modelos corromperia o grafo |
| 5. Postgres real | A carga completa funciona a partir de um banco, com cursor do lado do servidor, não só com CSV e com o cursor falso dos testes | O cliente real está num banco, não em CSV |
| 5a. Fidelidade de valores | Cada nó sorteado é igual à conversão da carga (`convert` e `node_id`) aplicada à linha da origem: mesmo valor, mesmo tipo, sem propriedade a mais ou a menos. Se o próprio `convert` está certo, quem prova é `tests/test_neo4j_values.py` | Contar nós não prova que os valores chegaram ao banco como a carga os montou |
| 5b. Perguntas de competência | As perguntas do negócio têm a mesma resposta no grafo e nos CSVs | É o uso final: um LLM ou uma pessoa consultando o grafo |

## Ambiente

- Mac com Apple M5, 24 GB de memória, macOS 26.3.1; Docker 29.2.0, com 7,65 GiB para a VM.
- Neo4j 2026.10.1 Community. Demo e Postgres: contêiner descartável próprio, sem plugin, heap de 1 GB e page cache de 256 MB, criado vazio para cada medida e removido no fim. Olist: o contêiner `akme-neo4j-t6` (portas 27474 e 27687), recriado vazio com APOC e heap de 1 GB, que ficou carregado no fim. Os contêineres `akme-neo4j` e `akme-neo4j-teste` não foram usados.
- Postgres 16.15 (`postgres:16`), descartável, em `127.0.0.1`.
- Python 3.12.13, driver `neo4j` 6.4.1, `psycopg` 3.3.6, uv 0.11.14.
- Senhas geradas na hora, guardadas em arquivos `chmod 600` fora do repositório e passadas por variável de ambiente. Os comandos abaixo usam `$AKME_NEO4J_PASSWORD`.
- **Como medir:** tempo e memória com `/usr/bin/time -l` sobre o executável `akme` do ambiente do projeto (sem o `uv run` na frente), que dá o tempo total e a memória residente máxima do processo (RSS); MB aqui é 10⁶ bytes. Disco com `du -sk /data/databases/neo4j` dentro do contêiner, depois de reiniciá-lo (o reinício força o checkpoint; o Community não tem `db.checkpoint()`), em MiB. Cada medida é de uma execução.

## Números do estado final

Estes são os números que os outros documentos citam. `_descricao` desligada é o padrão (seção "`_descricao` ligada e desligada").

| Base | Nós (de dado) | Arestas (de dado) | Dry-run | 1ª carga, banco vazio | Banco, `_descricao` desligada | Banco, `_descricao` ligada |
|---|---:|---:|---|---|---:|---:|
| Demo | 63 (43) | 64 (44) | 0,39 s, 51 MB | 3,18 s, 85 MB | 1,5 MiB | 1,5 MiB |
| Olist | 446.917 (446.873) | 568.996 (568.943) | 2,24 s, 144 MB | 34,1 s, 356 MB | 443,2 MiB | 507,2 MiB (+14%) |

Além dos dados, o banco tem a camada de ontologia: na demo, 9 `Conceito`, 10 `Termo` e a marca; no Olist, 18 `Conceito`, 25 `Termo`, a marca, 14 setas `RELACAO_ONTOLOGIA` (7 relações e 7 inversas), 14 `SUBCLASSE_DE` e 25 `TEM_TERMO`.

## 1. Demo em banco vazio

Cópia temporária do repositório (`git archive HEAD`, com o código da rodada final por cima), com `akme init --demo` e `akme demo`, que aplica as decisões `add_source` do `seed_edits.yml`. Banco descartável recém-criado.

```bash
akme init --demo && akme demo
akme publish --target neo4j                          # dry-run
echo y | akme publish --target neo4j --no-dry-run    # duas vezes
uv run --extra neo4j python examples/local_demo/verificar_neo4j.py
uv run --extra neo4j python examples/local_demo/amostra_valores.py akme.yml --n 200 --seed 42
```

| Conferência | Resultado |
|---|---|
| Dry-run | 43 linhas, 7 lotes, `problems` vazio; 0,39 s, 51 MB |
| 1ª carga | `banco: vazio`, 7 lotes, `removed` 0 nós e 0 arestas, `verification.ok`; 3,18 s, 85 MB |
| 2ª carga | `banco: projeto local_demo, sera atualizado`, `banco 8 -> origem 8` em cada label, `removed` 0/0, `verification.ok`; 0,79 s, 85 MB |
| `verificar_neo4j.py` | 54 de 54 OK, 216 células comparadas, saída 0 |
| `amostra_valores.py` | 43 linhas (todas), 256 células (213 da origem e 43 legendas `name`), 0 divergências |
| Sincronização, numa cópia sem o pedido 1010 e sem o cliente 7 | Prévia: `Cliente: banco 8 -> origem 7`, `Pedido: banco 10 -> origem 9`, `contem` e `pertenceA` com 1 a menos. `removed` 2 nós e 2 arestas (o `contem` e o `pertenceA` do pedido; o cliente 7 não tem pedido), `verification.ok`, uma `_carga` só no banco |

## 2. Olist completo (registro de execução)

### A cópia e as três correções

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

O nome da coluna nessa mensagem começa com um caractere invisível, o `U+FEFF`. Na Task 9, a mensagem saía assim, com o caractere escondido, e quem lia via `product_category_name` dos dois lados. Desde a rodada final, ela mostra o caractere e diz o que fazer:

```text
relacao pertenceACategoria: coluna do join nao existe nos dados: product_category_name_translation.<U+FEFF>product_category_name; o nome tem caractere invisivel: <U+FEFF> (BOM, marca de inicio de arquivo). Costuma vir do inicio de um CSV ou de um copiar e colar: reescreva o nome sem esse caractere onde ele foi digitado (contrato ou fonte no content.yml, por proposta na pagina de revisao, ou a proposta do add_source)
```

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
akme publish --target neo4j                     # dry-run
echo y | akme publish --target neo4j --no-dry-run
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

A carga terminou com `banco: vazio`, 205 de 205 lotes, `removed` 0/0 e `verification.ok`. O banco ficou com 446.917 nós (446.873 de dados, 18 `Conceito`, 25 `Termo` e a marca do projeto) e 568.996 arestas, todos com a mesma `_carga`. A segunda carga achou `banco N -> origem N` em todos os labels e tipos de aresta e terminou com `removed` 0/0.

### Tempo e memória

| Medida | Tempo | Memória máxima (RSS) |
|---|---|---|
| Dry-run, lendo 446.873 linhas | 2,24 s | 144 MB |
| 1ª carga, banco vazio | 34,1 s | 356 MB |
| 2ª carga, por cima, `removed` 0/0 | 35,7 s | 413 MB |
| Carga da sincronização (passo 3) | 32,6 s | 421 MB |
| 1ª carga com `_descricao` ligada, banco vazio | 34,8 s | 432 MB |
| Amostra de valores (5a) | 2,8 s | 171 MB |

O contêiner do Neo4j ficou com 1,28 GiB de memória no fim (`docker stats`). Na execução de `d791dff`, a 1ª carga tinha levado 31,4 s com 224 MB. A memória do processo varia bastante de uma execução para outra (de 224 a 432 MB entre as rodadas registradas), e cresce com o tamanho dos blocos de texto que o driver monta; o tempo fica entre 31 e 36 s.

### `_descricao` ligada e desligada

Desde a rodada final, `_descricao` (a definição da classe ou da relação em cada nó e aresta de dado) é **desligada por padrão**. Liga-se no `akme.yml`:

```yaml
neo4j:
  descricao_nos_dados: true
```

Desligada, a definição continua no `Conceito` (`definicao`), no esquema para o LLM e no tutorial; a propriedade fica ausente nos dados, e uma carga desligada por cima de uma ligada a apaga (o `SET` recebe `null`). `_descricao` continua nome reservado nos dois modos.

| Olist, banco vazio | Banco | Arquivo de strings | Tempo da carga |
|---|---:|---:|---:|
| Desligada (padrão) | 443,2 MiB | 192 MiB | 34,1 s |
| Ligada | 507,2 MiB | 256 MiB | 34,8 s |

Ligada, o banco ficou **64 MiB (+14%) maior** numa base nova. O arquivo de strings do Neo4j cresce em degraus de 64 MiB, então a diferença real está entre um e dois degraus. Na Task 10, regravando por cima de uma carga anterior, a mesma opção tinha custado +123 MB (+43%). Os dois números medem a mesma coisa em condições diferentes: a base nova é o custo de uma carga limpa; a regravação é o que acontece no uso de todo dia, porque o Community não reaproveita logo o espaço liberado. Foi esse custo, para um ganho que serve só a quem clica no nó no Browser (o LLM não lê a propriedade, ver a [Task 10](task-10-semantica.md)), que levou Mateus a desligá-la por padrão. Na demo, os dois modos dão 1,5 MiB, porque o banco é pequeno demais para sair do tamanho inicial dos arquivos. O tempo de carga quase não muda.

## 3. Sincronização no Olist

Numa segunda cópia, 10 avaliações apagadas do CSV: os 10 primeiros registros de uma linha só, sem comentário e sem título, para não tocar em registro com quebra de linha. Um script conferiu que o CSV ficou com 99.214 registros e que os outros continuaram iguais. Antes da carga, as 10 tinham 10 nós e 10 arestas no banco.

| Conferência | Resultado |
|---|---|
| Resumo antes de confirmar | `Avaliacao: banco 99224 -> origem 99214, pelo menos 10 serao removidos`; `refereSeAoPedido` com 10 a menos; os outros iguais |
| `removed` | 10 nós e 10 arestas, as `refereSeAoPedido` dessas avaliações |
| `verification` | `ok`, sem divergências |
| Banco depois | 99.214 avaliações; nenhuma das 10; uma `_carga` só |

Depois, a cópia original foi carregada de novo (`removed` 0/0, as 10 avaliações de volta), e é esse o estado em que o `akme-neo4j-t6` ficou.

## 4. Banco da exportação antiga (Task 9, não repetido)

Contêiner descartável `akme-neo4j-t9-legado` (Neo4j 2026.10.1, portas 37474 e 37687), com o jar do n10s 2025.06.1 montado só para leitura. A versão antiga do akme (commit `ec40d71`) rodou numa `git worktree` temporária e carregou a demo pelo n10s: 59 nós (`Resource`, `Class`, `Relationship`, `_GraphConfig` e os dados), 59 arestas e a restrição `n10s_unique_uri`.

A CLI nova, contra esse banco:

```text
banco: banco da exportacao antiga (n10s)
erro: banco carregado pela exportacao antiga (n10s); limpe-o com o comando do guia. Nada foi gravado
```

Parou antes da pergunta de confirmação, com saída 1. Nós, arestas, restrições, índices e contagem por label ficaram iguais antes e depois (`diff` vazio). Em seguida, o comando de limpeza do guia (subseção "Banco da exportação antiga") deixou o banco vazio, a carga nova achou `banco: vazio` e o verificador da demo terminou com `RESULTADO: todas as verificacoes passaram`. O contêiner, os volumes dele e a worktree foram removidos no fim.

## 5. Postgres real

Contêiner descartável (`postgres:16`, PostgreSQL 16.15), com as quatro tabelas da demo num schema próprio, todas as colunas como texto, carregadas por `COPY` (célula vazia vira `NULL`). O `akme.yml` da cópia da demo trocou o adapter:

```yaml
adapter: postgres
postgres:
  dsn: env:AKME_PG_TEST_DSN
  schema: demo
```

| Conferência | Resultado |
|---|---|
| Carga completa pela CLI, banco Neo4j vazio | 43 linhas, 7 lotes, `banco: vazio`, `removed` 0/0, `verification.ok`; 4,61 s, 90 MB |
| `verificar_neo4j.py` (contra os CSVs da demo) | 54 de 54 OK, saída 0 |
| `amostra_valores.py` (lê do Postgres) | 43 linhas, 256 células, 0 divergências |
| 2ª carga | `removed` 0/0 |
| `test_real_load_from_postgres` | passou (cria o schema `akme_demo_it`, carrega, confere, recarrega e apaga o schema) |

Na Task 9, o mesmo Postgres tinha sido testado só na leitura, com o `olist_order_items_dataset` (112.650 linhas): `iter_rows(batch=5000)` leu 23 blocos em 0,28 s, e o `scan_source` com a chave (`order_id`, `order_item_id`) achou 0 repetidas e 0 valores inválidos.

## 5a. Fidelidade de valores

```bash
uv run --extra neo4j python examples/local_demo/amostra_valores.py <akme.yml> --n 200 --seed 42
```

Como o script funciona:

1. Monta o plano (`build_plan`) para saber a classe, a chave e os tipos de cada fonte, como a carga.
2. Lê cada fonte inteira pelo adapter do projeto e sorteia até 200 linhas com a chave completa, por amostragem de reservatório com semente fixa.
3. Converte cada célula preenchida com `convert`, pelo tipo aprovado (texto se não declarado), e calcula a legenda `name` pela mesma regra da carga.
4. Busca o nó por label e `_id`, no projeto.
5. Compara campo a campo: o mesmo valor e o mesmo tipo Python, e nenhuma propriedade a mais ou a menos além de `_id`, `_projeto` e `_carga` (e `_descricao`, só com a opção ligada; desligada, uma `_descricao` no nó conta como propriedade a mais). Duas linhas sorteadas com o mesmo `_id` contam como divergência, e não são juntadas.

As datas voltam do driver como `neo4j.time.Date`; o script chama `to_native()`, que dá um `datetime.date`, antes de comparar. A saída mostra só contagens e nomes de coluna, nunca valores das linhas.

| Projeto | Fontes | Linhas | Células | Divergências |
|---|---|---|---|---|
| Demo | 4 | 43 (todas) | 256 | 0 |
| Olist | 7 | 1.271 | 9.109 | 0 |

As células incluem a legenda `name` (uma por nó), que não existia na execução de `d791dff` (213 e 7.838 células). No Olist, nenhuma coluna é `date`: as datas têm hora e ficaram texto na etapa 5. A conversão de datas é exercitada na demo (`dt_cadastro`, `dt_pedido`).

**O script acha erro quando há erro** (execução de `d791dff`). Com a demo carregada, o banco foi adulterado à mão: uma data virou texto, um preço ganhou um centavo e um nó ganhou uma propriedade a mais. O script achou as 3 divergências (`tipo:dt_cadastro`, `valor:vl_unitario`, `a mais:extra`). Uma carga nova desfez as três, porque cada nó é regravado inteiro com os valores da origem.

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

### Olist (registro de execução)

As três perguntas reservadas de `validation/questions.yml` (a da raiz, que não foi alterada) estão em `examples/olist_perguntas_neo4j.cypher`. Na rodada final, o arquivo rodou no Olist carregado pelo código final, e cada resposta foi comparada com a mesma conta feita em pandas sobre os CSVs da cópia, sem o akme. As consultas aplicam as regras da ontologia:

- C-001: uma avaliação por pedido, a de `review_answer_timestamp` mais recente;
- C-002: cada pedido conta uma vez por categoria ou vendedor, nunca uma vez por item;
- C-003: atraso só para pedido `delivered` com data de entrega.

| Pergunta | Grafo | Grafo = pandas | Bate com a resposta reservada |
|---|---|---|---|
| CQ-006, pior nota média por categoria | `moveis_escritorio`, 3,62 em 1.263 pedidos; depois `fashion_roupa_feminina` 3,69 (39) e `fashion_roupa_masculina` 3,70 (111) | sim | sim |
| CQ-007, pior nota média por vendedor | o vendedor da resposta reservada, 2,33 em 114 pedidos | sim | sim |
| CQ-008, atraso do pedido da pergunta | `delivered`, 10 dias de atraso | sim | sim |

O identificador do vendedor e o do pedido estão em `validation/questions.yml`; esta página não os repete. O corte de 30 ou mais pedidos avaliados não está no texto da pergunta: veio da justificativa registrada no changelog. Sem o corte, a pior categoria seria `seguros_e_servicos`, com 2 pedidos. A consulta da CQ-006 não depende da aresta `pertenceACategoria`: o `coalesce` cai para a propriedade `product_category_name` do `Produto` quando a aresta falta. A dependência real é outra: sem a correção 1, a carga nem acontece, porque o dry-run recusa a ontologia da raiz, e não há grafo para consultar.

## O que falhou ou surpreendeu

- **O `U+FEFF` aparece em etapas.** Na ontologia da raiz, o dry-run mostra 2 problemas; o terceiro só aparece depois. Na Task 9, a mensagem desse terceiro trazia o caractere invisível sem marcá-lo. **Corrigido na rodada final:** o plano, o `add_source` e a conferência dos contratos marcam BOM, espaço de largura zero, espaço não separável e caracteres de controle como `<U+FEFF>` e dizem o que fazer (seção 2).
- **Memória.** A versão anterior do guia dizia que o driver podia passar de 1 GB numa tabela de centenas de milhares de linhas com texto acentuado. No Olist inteiro, o processo ficou entre 224 e 432 MB de memória residente máxima, conforme a execução. O guia cita o número do estado final.
- **O dry-run é rápido:** 2,2 s para ler as 446.873 linhas. A carga leva cerca de 34 s, quase tudo esperando o Neo4j.
- **O custo de `_descricao` depende de como se mede:** +14% numa base nova, +43% regravando por cima (Task 10). O arquivo de strings cresce em degraus de 64 MiB.
- **Endereço do Browser.** No fim da carga, a CLI indica `http://localhost:7474`, a menos que `AKME_NEO4J_BROWSER_URL` diga outro; nesta rodada ela apontou para a porta do contêiner usado.
- **O jar antigo funciona no Neo4j novo** (Task 9). O n10s 2025.06.1 carregou no Neo4j 2026.10.1 sem erro. O passo 4 reproduziu de fato o banco de quem seguiu o guia antigo.

## Limites

- Uma máquina só, com Docker local. **Aura e Enterprise não foram testados.**
- O Olist não é reproduzível com o que está no repositório (dados e ontologia de fora, cópia com três correções). A aceitação reproduzível é a da demo.
- O Postgres foi testado com as quatro tabelas da demo (carga completa) e com uma tabela do Olist (só leitura). Snowflake e Databricks, só com cursor falso.
- A amostra de valores sorteia 200 linhas por fonte, não todas. Na demo, cobre todas; no Olist, cerca de 0,3%.
- A amostra compara o grafo com o mesmo `convert` e o mesmo `node_id` que a carga usa. Ela prova que o nó é igual à conversão da carga aplicada à origem, e que nada se perdeu ou sobrou no caminho até o banco. Não prova que o `convert` em si está certo; isso é coberto por `tests/test_neo4j_values.py`.
- Fonte do plano sem chave não vira nó e é pulada pela amostra, com uma linha `PULADA` na saída. Neste teste, nenhuma fonte foi pulada.
- Só as perguntas da demo viraram teste automático. As do Olist estão em `examples/olist_perguntas_neo4j.cypher`, para rodar à mão num grafo do Olist.
- Tempo, memória e disco são de uma execução cada, sem repetição.

## Testes

Na rodada final:

- `scripts/test-neo4j.sh` (Neo4j descartável, sem Postgres): 27 passaram, 1 pulado (o do Postgres), em 31 s; com o Postgres descartável também configurado (`AKME_PG_TEST_DSN`), `tests/test_neo4j_integration.py` passou 28 de 28.
- `uv run pytest -q`: 472 passaram, 30 foram pulados (os de banco real), em 49 s.
- `uv run --extra docs mkdocs build --strict`: sem avisos.

## Revisão

A revisão independente da Task 9 aprovou a tarefa, sem problemas críticos nem importantes.

- **Números rastreados:** cada número desta página foi conferido contra o comando que o produziu, no relatório da tarefa (rodada final: `.superpowers/sdd/2026-11-11-exportacao-neo4j-cypher/rodada-final-report.md`).
- **Amostra de valores:** compara tipo e valor exatos e pegou as três adulterações feitas de propósito.
- **Corte de 30 pedidos:** foi registrado no changelog e aprovado por Mateus antes desta execução, quando as respostas foram reservadas. Não é um ajuste para a resposta bater.
