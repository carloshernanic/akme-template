# Uso real do grafo

Esta página mostra para que serve, na prática, o grafo que o akme grava no Neo4j, e compara o formato novo (Cypher puro) com o antigo (RDF carregado pelo plugin n10s). Toda afirmação vem de uma consulta que rodou em 12/11/2026. Quando um número aparece, a consulta que o produziu está logo acima. Quando o grafo não ajuda, ou quando SQL resolveria com menos esforço, a página diz isso.

**Atualizada na rodada final (12/11/2026)** para o modelo atual do grafo: a camada `Conceito` é um espelho do `schema.ttl`, com uma seta `RELACAO_ONTOLOGIA` por relação (inversas incluídas) e o nome da relação em `nome`; todo nó tem a legenda `name`; `_descricao` nos dados é opcional e vem desligada; e o Browser tem um tutorial do projeto de seis páginas. As seções 1, 2b, 2c, 2d e 2e foram medidas de novo no Olist carregado pelo código final. As seções 2a e 3 são da medição anterior (código de `d791dff`), e o que mudou desde então está anotado nelas.

**O Olist é um registro de execução, não um teste reproduzível:** os dados e a ontologia do Olist não estão no repositório, e o grafo veio de uma cópia com três correções que a ontologia da raiz não tem (ver a [Task 9](task-9-aceitacao.md), seção 2). A aceitação reproduzível é a da demo.

Ambiente: Mac com Apple M5 e 24 GB; Neo4j 2026.10.1 Community em Docker; driver `neo4j` 6.4.1. Os tempos são a mediana de 3 ou 5 rodadas depois de uma rodada de aquecimento, medidos no cliente Python (incluem a ida e volta pela rede local). Os tempos do SQLite vêm de um banco montado a partir dos mesmos CSVs, com índice em cada coluna de join, como referência.

Bancos usados:

| Banco | Conteúdo | Formato |
|---|---|---|
| `akme-neo4j-t6` (porta 27687) | Olist completo, projeto `olist`, 446.873 nós de dado, carregado pelo código final | novo, só leitura nesta página |
| `akme-neo4j-uso-novo` (57687, descartável) | demo `local_demo` | novo, código do commit `d791dff` |
| `akme-neo4j-uso-legado` (47687, descartável, com n10s 2025.06.1) | demo `local_demo` | antigo, código do commit `ec40d71` |

Os comandos usam `$AKME_NEO4J_PASSWORD` no lugar da senha.

## 1. O que tem no grafo do Olist

```cypher
MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS n ORDER BY l;
MATCH (a)-[r]->(b) WHERE NOT a:Conceito
RETURN labels(a)[0] AS de, type(r) AS rel, labels(b)[0] AS para, count(*) AS n ORDER BY rel;
```

| Label | Nós | | Padrão de aresta | Arestas |
|---|---:|---|---|---:|
| `Pedido` | 99.441 | | `(:Pedido)-[:contemItem]->(:ItemPedido)` | 112.650 |
| `ItemPedido` | 112.650 | | `(:Pedido)-[:feitoPorCliente]->(:Cliente)` | 99.441 |
| `Cliente` | 99.441 | | `(:ItemPedido)-[:referenteAoProduto]->(:Produto)` | 112.650 |
| `Avaliacao` | 99.224 | | `(:ItemPedido)-[:vendidoPor]->(:Vendedor)` | 112.650 |
| `Produto` | 32.951 | | `(:Avaliacao)-[:refereSeAoPedido]->(:Pedido)` | 99.224 |
| `Vendedor` | 3.095 | | `(:Produto)-[:pertenceACategoria]->(:CategoriaProduto)` | 32.328 |
| `CategoriaProduto` | 71 | | | |
| `Conceito` (ontologia) | 18 | | `SUBCLASSE_DE` entre conceitos | 14 |
| `Termo` (termos do negócio) | 25 | | `RELACAO_ONTOLOGIA` entre conceitos (7 relações e 7 inversas) | 14 |
| `_AkmeProjeto` (marca) | 1 | | `TEM_TERMO`, do conceito para o termo | 25 |

As contagens de dado são as mesmas das contagens independentes nos CSVs, feitas na [Task 9](task-9-aceitacao.md). No total, o banco tem 446.917 nós e 568.996 arestas. Como as setas da ontologia têm o tipo `RELACAO_ONTOLOGIA`, uma contagem por tipo de dado (`MATCH ()-[r:contemItem]->()`) dá exatamente o número da tabela: 112.650. Até a Task 11, as setas entre conceitos tinham o nome da relação, e essa contagem dava uma a mais.

Em palavras, o caminho principal é:

```
(:Cliente) <-[:feitoPorCliente]- (:Pedido) -[:contemItem]-> (:ItemPedido) -[:referenteAoProduto]-> (:Produto) -[:pertenceACategoria]-> (:CategoriaProduto)
                                    ^                             |
                       [:refereSeAoPedido]                  [:vendidoPor]
                                    |                             v
                              (:Avaliacao)                  (:Vendedor)
```

Cada nó guarda as colunas da linha de origem com o nome original (`order_status`, `price`, `review_score`), no tipo decidido na etapa 5: `price` e `freight_value` são `FLOAT`, `review_score` e as medidas do produto são `INTEGER`, e as datas do Olist ficaram texto (decisão da etapa 5, para não perder a hora). Além delas, há `_id` (a chave), `_projeto`, `_carga` e `name`, a legenda que o Browser mostra na bolinha (o label, o começo da chave e uma coluna descritiva). `_descricao`, a definição da classe repetida em cada nó, só existe com `neo4j: {descricao_nos_dados: true}` no `akme.yml`; neste banco, carregado com o padrão, nenhum nó ou aresta de dado a tem. Há uma restrição de unicidade em `_id` por label e um índice em cada coluna usada nos joins (por exemplo, `Pedido(order_id)`).

## 2. Usos reais, cada um com a consulta que rodou

### a) Pergunta de vários saltos: onde se concentram as notas baixas

**Pergunta de negócio:** em que UF de vendedor a proporção de pedidos com nota 1 ou 2 é maior? Regras das CQs do Olist: uma avaliação por pedido (a mais recente) e cada pedido conta uma vez por UF.

```cypher
MATCH (a:Avaliacao)-[:refereSeAoPedido]->(p:Pedido)
WITH p, a ORDER BY a.review_answer_timestamp DESC, a.review_id DESC
WITH p, head(collect(a)) AS a
MATCH (p)-[:contemItem]->(:ItemPedido)-[:vendidoPor]->(v:Vendedor)
WITH DISTINCT v.seller_state AS uf, p, a.review_score <= 2 AS negativa
WITH uf, count(*) AS pedidos, sum(CASE WHEN negativa THEN 1 ELSE 0 END) AS negativos
WHERE pedidos >= 1000
RETURN uf, pedidos, negativos, round(100.0 * negativos / pedidos, 1) AS pct_negativos
ORDER BY pct_negativos DESC;
```

| UF do vendedor | Pedidos | Nota 1 ou 2 | % |
|---|---:|---:|---:|
| SP | 69.643 | 10.338 | 14,8 |
| RJ | 4.318 | 612 | 14,2 |
| PR | 7.615 | 1.065 | 14,0 |
| SC | 3.644 | 498 | 13,7 |
| MG | 7.872 | 984 | 12,5 |
| RS | 1.971 | 194 | 9,8 |

Tempo: **400 ms** no Neo4j (medido com o código de `d791dff`; a consulta não usa nada que mudou depois). A mesma consulta em SQL (`ROW_NUMBER()` para a última avaliação, dois `JOIN` e `DISTINCT`) deu exatamente os mesmos números no SQLite em **206 ms**.

Uma variação cruza dois ramos do mesmo pedido: a UF do cliente (`feitoPorCliente`) contra as UFs dos vendedores (`contemItem`, `vendidoPor`).

```cypher
MATCH (a:Avaliacao)-[:refereSeAoPedido]->(p:Pedido)
WITH p, max([a.review_answer_timestamp, a.review_id, a.review_score])[2] AS nota
MATCH (p)-[:feitoPorCliente]->(c:Cliente)
WITH p, nota, c.customer_state AS uf_cli
MATCH (p)-[:contemItem]->(:ItemPedido)-[:vendidoPor]->(v:Vendedor)
WITH p, nota, uf_cli, collect(DISTINCT v.seller_state) AS ufs_vend
WITH CASE WHEN ufs_vend = [uf_cli] THEN 'mesma UF' WHEN uf_cli IN ufs_vend THEN 'misto' ELSE 'outra UF' END AS rota, nota
RETURN rota, count(*) AS pedidos,
       round(100.0 * sum(CASE WHEN nota <= 2 THEN 1 ELSE 0 END) / count(*), 1) AS pct_negativos ORDER BY rota;
```

| Rota | Pedidos | % nota 1 ou 2 |
|---|---:|---:|
| mesma UF | 35.110 | 11,8 |
| outra UF | 62.564 | 15,4 |
| misto (vendedores dentro e fora da UF do cliente) | 243 | 45,3 |

Tempo: **468 ms** (uma rodada). Isso é uma associação, não uma causa: pedidos com vendedores em várias UFs costumam ter vários itens, e isso também pode baixar a nota.

**O grafo ajuda ou não?** Ajuda na escrita: a consulta segue o desenho da seção 1, com os nomes das relações da ontologia, sem que quem escreve precise saber quais colunas fazem cada join (`order_id`, `seller_id`, `customer_id`). Para um LLM, isso diminui a chance de juntar pela coluna errada. Não ajuda no desempenho: neste volume, o SQLite com índices foi cerca de duas vezes mais rápido, e as duas linguagens precisam da mesma disciplina contra contagem duplicada (o `DISTINCT` e a "última avaliação"). O grafo não resolve sozinho a armadilha de contar o pedido uma vez por item.

### b) As perguntas de competência CQ-006, CQ-007 e CQ-008

As três consultas estão em `examples/olist_perguntas_neo4j.cypher`, com o pedido da CQ-008 como parâmetro (`$pedido`). Rodaram de novo no Olist carregado pelo código final, e cada resposta foi conferida contra a mesma conta em pandas sobre os CSVs:

| CQ | Pergunta | Resposta no grafo | Bate com o gabarito e com o pandas | Tempo |
|---|---|---|---|---:|
| CQ-006 | Categoria com pior nota média (30 ou mais pedidos avaliados) | `moveis_escritorio`, 3,62 em 1.263 pedidos | sim | 526 ms |
| CQ-007 | Vendedor com pior nota média (30 ou mais pedidos) | o vendedor do gabarito, 2,33 em 114 pedidos | sim | 380 ms |
| CQ-008 | O pedido da pergunta atrasou, e quanto? | `delivered`, 10 dias de atraso | sim | 2 ms |

Os identificadores do vendedor e do pedido estão em `validation/questions.yml`; esta página não os repete.

A CQ-007 em SQL deu a mesma resposta no SQLite em 288 ms. A CQ-008 é uma busca por chave: o plano do Neo4j (`EXPLAIN`) mostra `NodeIndexSeek` no índice `Pedido(order_id)` que a carga criou. As CQ-006 e CQ-007 dependem do corte de 30 pedidos, que está só no `rationale` do changelog. Quem avaliar um LLM com elas precisa informar esse corte.

### c) Explorar a vizinhança de um pedido

No Neo4j Browser, o uso mais natural é abrir um nó e expandir. A consulta abaixo é o que se cola no Browser para ver o pedido da CQ-008 e tudo até dois saltos (antes, `:param pedido => '<order_id da pergunta>'`):

```cypher
MATCH path = (p:Pedido {order_id: $pedido})-[*1..2]-()
RETURN path
```

Para medir o tamanho da vizinhança, contamos os nós distintos por label em cada distância:

```cypher
MATCH (p:Pedido {order_id: $pedido})-[*1..N]-(x)
RETURN labels(x)[0] AS label, count(DISTINCT x) AS nos
```

| Até | Nós alcançados | Tempo |
|---|---|---:|
| 1 salto | 1 `Avaliacao`, 1 `Cliente`, 1 `ItemPedido` | 3 ms |
| 2 saltos | mais 1 `Produto` e 1 `Vendedor` | 2 ms |
| 3 saltos | mais 1 `CategoriaProduto` e 3 outros `ItemPedido` do mesmo vendedor ou produto | 3 ms |
| 4 saltos | **754 `Produto`** (os da mesma categoria) e 3 outros `Pedido` | 3 ms |

O grau dos vendedores mostra por que a exploração precisa de limite: o maior vendedor tem **2.033** itens, a média é 36,4 e a mediana é 8 (`COUNT { (v)<-[:vendidoPor]-() }`, 5 ms).

**O grafo ajuda ou não?** Aqui ajuda de verdade. Ver o pedido, o cliente, a avaliação, o item, o produto e o vendedor num desenho só, clicando, é difícil de reproduzir com SQL, que exigiria uma consulta por tabela. O custo é que, a partir do terceiro salto, os nós de categoria e de vendedor grande espalham a vizinhança. No Browser, convém expandir um nó por vez em vez de pedir `[*1..4]`.

Para quem não escreve Cypher, o tutorial do projeto no Browser (`:guide http://127.0.0.1:8765/neo4j/guia`, servido pelo `akme review`) traz esse caminho pronto, em seis páginas só de navegação: o que tem no banco, a ontologia, os dados, explorar um registro de cada classe, como navegar e perguntas em português pelo console da Aura (este último, não testado). Ver a [Task 11](task-11-tutorial.md).

Nesse desenho, porém, o nó `Pedido` não mostra a definição de "Pedido": os nós de dado não têm aresta para a camada `Conceito`, e `_descricao` vem desligada por padrão. A definição está no `Conceito` de mesmo nome e no esquema para o LLM. Veja o item d.

### d) A ontologia como contexto para um LLM

A camada `Conceito` é o que um LLM, ou uma pessoa nova no projeto, pode ler antes de escrever uma consulta. Esta consulta devolve, para cada classe, a definição, a superclasse, as setas que saem dela, com multiplicidade e inversa, e a regra da métrica:

```cypher
MATCH (c:Conceito {_projeto: 'olist'})
OPTIONAL MATCH (c)-[r:RELACAO_ONTOLOGIA]->(d:Conceito)
OPTIONAL MATCH (c)-[:SUBCLASSE_DE]->(pai:Conceito)
WITH c, pai, collect(CASE WHEN r IS NULL THEN null ELSE
       '(:' + c.nome + ')-[:' + r.nome + ']->(:' + d.nome + ') ' + r.multiplicidade
       + coalesce(' inversa=' + nullif(r.inversa, ''), '')
       + CASE WHEN r.publicada_nos_dados THEN '' ELSE ' (sem dados)' END END) AS setas
RETURN c.nome AS classe, pai.nome AS subclasse_de, c.definicao AS definicao, setas,
       CASE WHEN c.aditividade IS NULL THEN null ELSE
       {grao: c.grao, aditividade: c.aditividade, unidade: c.unidade, expressao: c.expressao,
        nao_somar_apos_juntar_com: c.nao_somar_apos_juntar_com} END AS regra_metrica
ORDER BY classe;
```

Tempo: 3 ms, 18 linhas. Trechos do que volta:

- `Pedido` (subclasse de `Entity`): "Compra feita por um cliente no marketplace, com status e datas de compra, aprovação, postagem, entrega e entrega estimada." Setas: `(:Pedido)-[:contemItem]->(:ItemPedido) one_to_many inversa=pertenceAoPedido`, `(:Pedido)-[:feitoPorCliente]->(:Cliente) many_to_one inversa=fezPedido` e a inversa `(:Pedido)-[:temAvaliacao]->(:Avaliacao) one_to_many inversa=refereSeAoPedido (sem dados)`: a inversa aparece como seta própria, com a multiplicidade lida ao contrário, e "sem dados" porque a aresta de dado só existe no sentido do contrato.
- `AvaliacaoNegativa` (subclasse de `Avaliacao`): "Avaliação com nota 1 ou 2."
- `Avaliacao`: `(:Avaliacao)-[:citaMotivo]->(:MotivoAvaliacao) many_to_many inversa=citadoEm (sem dados)`. A relação existe na ontologia, mas não tem dados no grafo.
- `AtrasoEntrega` (subclasse de `Metric`): grão "um pedido", `non_additive`, unidade "dias", expressão SQL de origem e `nao_somar_apos_juntar_com: [olist_order_items_dataset, olist_order_reviews_dataset]`.
- `NotaMedia`: grão "uma avaliação por pedido", `non_additive`. `QuantidadeAvaliacoes`: `additive`.

Os nomes e tipos das propriedades vêm do procedimento nativo `CALL db.schema.nodeTypeProperties()`, que no Olist levou 666 ms, porque varre o banco. A camada `Conceito` não repete essa informação.

**O que um LLM aprende daí e não aprenderia só dos dados:** que o sentido de `contemItem` é Pedido → ItemPedido e que um pedido tem vários itens (`one_to_many`), o que já avisa do risco de multiplicar linhas; que "avaliação negativa" quer dizer nota 1 ou 2; que `citaMotivo` não tem dados; e que `AtrasoEntrega` não pode ser somado depois de juntar com itens ou avaliações.

**A armadilha que a regra evita, com números do Olist.** O atraso é uma medida por pedido. Somá-lo depois de descer para os itens conta cada pedido uma vez por item:

```cypher
// certo: uma vez por pedido entregue
MATCH (p:Pedido) WHERE p.order_status = 'delivered' AND p.order_delivered_customer_date IS NOT NULL
WITH p, duration.inDays(date(left(p.order_estimated_delivery_date, 10)),
                        date(left(p.order_delivered_customer_date, 10))).days AS atraso
RETURN count(*) AS linhas, round(avg(atraso), 3) AS atraso_medio, sum(atraso) AS soma_atraso;

// errado: a mesma conta depois de MATCH (p)-[:contemItem]->(:ItemPedido)
MATCH (p:Pedido)-[:contemItem]->(:ItemPedido)
WHERE p.order_status = 'delivered' AND p.order_delivered_customer_date IS NOT NULL
WITH p, duration.inDays(date(left(p.order_estimated_delivery_date, 10)),
                        date(left(p.order_delivered_customer_date, 10))).days AS atraso
RETURN count(*) AS linhas, round(avg(atraso), 3) AS atraso_medio, sum(atraso) AS soma_atraso;
```

| Conta | Linhas | Atraso médio (dias) | Soma do atraso (dias) | % atrasados | Tempo |
|---|---:|---:|---:|---:|---:|
| Certa (por pedido) | 96.470 | −11,876 | −1.145.667 | 6,77 | 151 ms |
| Depois de juntar com itens | 110.189 | −12,029 | **−1.325.468** | 6,59 | 226 ms |
| Depois de juntar com avaliações | 96.353 | −11,917 | −1.148.220 | | 206 ms |

Atraso negativo quer dizer que o pedido chegou antes do previsto. A soma errada é 15,7% maior em valor absoluto. A média quase não muda, porque o número de itens pouco depende do atraso. Mesmo assim, o resultado está errado, e nada no resultado avisa. Juntar com avaliações tem dois efeitos ao mesmo tempo: o `MATCH` descarta os pedidos sem avaliação e duplica os que têm duas. No SQLite, os mesmos dois cálculos deram os mesmos 96.470 e −1.145.667 (12 ms), e 110.189 e −1.325.468 (61 ms). Ou seja, SQL tem exatamente a mesma armadilha.

O mesmo acontece com a nota média: uma avaliação por pedido dá **4,0864** (98.673 pedidos). Pesando cada pedido pelo número de itens, que é o que acontece ao descer para `ItemPedido` antes de tirar a média, dá **4,0329** (111.708 linhas), em 214 ms.

Na demo, a armadilha é maior, porque o valor fica no pedido: o faturamento certo é **23.077,35**. Somado depois de `(:Pedido)-[:contem]->(:ItemPedido)`, vira **49.819,30**, 2,16 vezes o certo. O `Conceito` `Faturamento` da demo traz `nao_somar_apos_juntar_com: ['itens_pedido']`.

**Limites desta camada (verificados no Olist antes da Task 10):**

> **Atualização (Tasks 10 e 11 e rodada final, 12/11/2026):** o limite 4 foi resolvido e os limites 1 e 3, em parte. Do 1: a Task 10 pôs `_descricao` em cada nó e aresta de dado, e a rodada final a deixou opcional, desligada por padrão; continua sem aresta até o `Conceito`. Do 3: os 25 termos viraram nós `Termo` ligados ao `Conceito`, mas as perguntas de competência continuam fora do grafo. Do 4: a regra cita labels (`["ItemPedido", "Avaliacao"]` no `AtrasoEntrega`); e o glossário, as regras e as precedências vão no esquema para o LLM, gravado em `docs/publish/neo4j_schema.md` e na propriedade `esquema` da marca do projeto. Os limites 2 e 5 continuam. Detalhes em [Task 10](task-10-semantica.md).

1. **(Em parte: `_descricao` no nó é opcional; a seta continua de fora.)** **Os nós de dado não têm ligação com o `Conceito`.** `MATCH (n)-[r]-(c:Conceito) WHERE NOT n:Conceito AND NOT n:Termo RETURN count(r)` dá **0** no banco atual. A camada semântica é um subgrafo separado, ligado aos dados só pela convenção label = `Conceito.nome`. Com o padrão, quem clica num `Pedido` no Browser não vê a definição; o tutorial manda olhar o `Conceito`. Um LLM só a encontra se souber dessa convenção ou ler o esquema.
2. **As setas entre conceitos têm rótulo, mas a definição está vazia.** As 14 setas `RELACAO_ONTOLOGIA` (7 relações e 7 inversas) têm `rotulo` e as 14 têm `definicao = ''`; 6 têm `publicada_nos_dados`. O exportador é fiel à origem: o `schema.ttl` do Olist declara 14 `owl:ObjectProperty` (7 relações e 7 inversas) e nenhuma tem `rdfs:comment`, e o `add_relation` não exige um. A lacuna está antes da exportação.
3. **(Resolvido na Task 10, exceto as perguntas de competência.)** **Os termos do `content.yml` não são exportados.** Os 25 termos do Olist (significado de cada coluna, definição, sinônimos) não chegam ao grafo. Só as propriedades dos termos de métrica entram no nó `Conceito` da métrica. Também não entram o glossário, as restrições e regras (4 `constraints`), a precedência (3 entradas) nem as perguntas de competência (8 `requirements`).
4. **(Resolvido na Task 10.)** **A regra cita tabelas, não labels.** `nao_somar_apos_juntar_com` guarda nomes de fonte (`olist_order_items_dataset`), e o grafo não registra em lugar nenhum que essa fonte virou o label `ItemPedido`. O LLM precisa deduzir a correspondência pelo nome.
5. **As subclasses não marcam os dados.** `AvaliacaoNegativa` existe como `Conceito`, mas nenhum nó de dado tem esse label. Quem consulta precisa aplicar a definição ("nota 1 ou 2") por conta própria.

### e) Atualização e sincronização: o que `_carga` permite perguntar

```cypher
MATCH (n) WHERE n._projeto = 'olist'
RETURN n._carga AS carga, CASE WHEN n:Conceito THEN 'Conceito' ELSE 'dado' END AS camada, count(*) AS nos;
MATCH ()-[r]->() RETURN r._carga AS carga, count(*) AS arestas;
```

| Camada | `_carga` distintas | Nós | Arestas |
|---|---:|---:|---:|
| dado | 1 | 446.873 | |
| `Conceito` | 1 | 18 | |
| `Termo` | 1 | 25 | |
| (todas as arestas) | 1 | | 568.996 |

As três camadas têm a mesma `_carga`, a da última carga (UTC, com milissegundos: `2026-11-13T00:55:17.372+00:00`). Tempos: 211 ms e 133 ms. Não há índice em `_carga`, então a consulta varre o banco.

O que dá para perguntar: "de quando é este dado?" e "o banco inteiro veio da mesma carga?". Neste banco, sim: uma única `_carga`. O que não dá: histórico. Como a sincronização apaga o que tem `_carga` antiga, só sobra a última carga. Perguntas como "o que mudou desde ontem?" ou "quais pedidos foram apagados na origem?" não têm resposta no grafo. A contagem do que foi removido aparece só na saída da CLI (`removed`). Na [Task 9](task-9-aceitacao.md), a remoção de 10 avaliações da origem apareceu como `removed {nodes: 10, relationships: 10}`, e os nós sumiram do banco.

O teste na demo, descrito na seção 3, mostra o outro lado da sincronização: ela apaga também o que alguém acrescentou à mão.

## 3. Antes × depois, na demo

Medido com o código de `d791dff`, antes das Tasks 10 e 11. Desde então, a demo nova tem também 10 nós `Termo`, a legenda `name` em todo nó, as inversas como setas `RELACAO_ONTOLOGIA` (63 nós e 64 arestas no total, contra 53 e 52 abaixo) e as consultas sobre a ontologia usam `RELACAO_ONTOLOGIA` com o nome em `nome`; as consultas sobre os dados não mudaram. As duas versões carregaram a mesma demo (`init --demo`, `demo`, `publish --target neo4j --no-dry-run`), cada uma no seu banco descartável. A antiga gravou 300 triplas num lote (1,4 s de CLI). A nova gravou 43 linhas em 7 comandos (2,1 s de CLI). As duas conferências terminaram com `ok`.

### Mesmas perguntas, mesmas respostas

As 11 consultas de `examples/local_demo/perguntas_neo4j.cypher` rodaram **sem mudar uma letra** nos dois bancos. Todas deram a mesma resposta (`clientes_sem_pedido ['3','7']`, `faturamento 2307735` centavos, `qt_itens 2999`, armadilha `4981930` centavos etc.), com 1,3 a 2,1 ms cada nos dois. Na demo, a diferença de tempo é ruído.

Isso acontece porque o exportador antigo usava `handleVocabUris: IGNORE`: os labels já eram os nomes das classes, as propriedades já tinham o nome da coluna, sem prefixo, e as arestas já tinham o nome da relação. As células de dado também são as mesmas: **213** nos dois bancos, propriedade a propriedade. Para perguntas sobre dados, o formato novo não muda a consulta. As diferenças estão na ontologia, na escala e na sincronização.

### Onde as consultas diferem

| Pergunta | Formato antigo | Formato novo |
|---|---|---|
| Que relações saem de `Pedido`? | `MATCH (r:Relationship)-[:DOMAIN]->(:Class {name:'Pedido'}), (r)-[:RANGE]->(alvo:Class) RETURN r.name, alvo.name, r.propCharacteristics` | `MATCH (:Conceito {nome:'Pedido'})-[r:RELACAO_ONTOLOGIA]->(alvo:Conceito) RETURN r.nome, alvo.nome, r.multiplicidade, r.inversa` (desde a Task 11; antes, `-[r]->` com `type(r)`) |
| Resultado | `contem → ItemPedido` (sem característica), `pertenceA → Cliente` (`Functional`) | `contem → ItemPedido one_to_many`, inversa `pertenceAoPedido`; `pertenceA → Cliente many_to_one`, inversa `possuiPedido` |
| Tempo | 2,4 ms | 2,5 ms |
| Como somar `Faturamento`? | `MATCH (c:Class {name:'Faturamento'}) RETURN c.comment` → só a definição. As outras chaves do nó: `[]` | `MATCH (c:Conceito {nome:'Faturamento'}) RETURN c.definicao, c.grao, c.aditividade, c.nao_somar_apos_juntar_com` → definição, `um pedido`, `additive`, `['itens_pedido']` |
| Tempo | 2,3 ms | 2,1 ms |
| Só os dados, sem a ontologia | `WHERE NOT n:Class AND NOT n:Relationship AND NOT n:_GraphConfig AND NOT n:_AkmeProjeto` e `[l IN labels(n) WHERE l <> 'Resource'][0]`, porque todo nó tem também o label `Resource` | `WHERE NOT n:Conceito AND NOT n:_AkmeProjeto` e `labels(n)[0]` |
| Pedido pela chave | `{uri: 'https://akme.example/ontology#Pedido/1001'}` (ou `{id_pedido: '1001'}`) | `{_id: '1001'}` (ou `{id_pedido: '1001'}`) |

No banco antigo, nenhum nó tem propriedade de aditividade, grão ou "não somar": `MATCH (n) WHERE any(k IN keys(n) WHERE k CONTAINS 'additiv' OR k CONTAINS 'somar' OR k CONTAINS 'grain') RETURN count(n)` dá **0**. A regra existia só como comentário no arquivo `neo4j.nt` do dry-run, e um LLM que consultasse o banco não a encontrava. A ontologia antiga gravava cada relação como nó (`:Relationship`, 5 nós com setas `DOMAIN` e `RANGE`), incluindo as inversas como nós soltos (`pertenceAoPedido`, `possuiPedido`), sem ligação explícita com a relação de que são inversas.

### Escala: o Olist no exportador antigo

O dry-run da versão antiga (`ec40d71`) numa cópia do projeto Olist **recusa a carga** (e a mensagem do BOM, no código final, marca o caractere como `<U+FEFF>`):

- `fonte olist_order_items_dataset truncada: tem mais de 100000 linhas` (teto `MAX_ROWS = 100_000`);
- `fonte product_category_name_translation: chave declarada usa coluna inexistente: product_category_name` (o leitor antigo não tirava o BOM do CSV, e a coluna virou `%EF%BB%BFproduct_category_name`);
- por causa do corte em 100 mil itens, `contemItem: 11868 de 99441 linha(s) ... sem alvo`, e `pertenceACategoria` nem entra.

O dry-run antigo levou **9,5 s**, com pico de **4,09 GB** de memória (RSS), e escreveu um `neo4j.nt` de **736 MB** (3.775.798 triplas). O novo, no mesmo Olist, levou 2,24 s, com 144 MB, e não aponta nenhum problema ([Task 9](task-9-aceitacao.md), código final). A carga nova completa levou 34,1 s, com pico de 356 MB no processo do akme.

### Sincronização e enriquecimento manual (medido na demo)

Na origem: o cliente 3 foi apagado, a `uf` do cliente 1 foi esvaziada e o `vl_unitario` do `CIM-50` mudou de 32,90 para 33,50. Depois, as duas versões recarregaram.

| Depois de recarregar | Antigo | Novo |
|---|---|---|
| Clientes no banco | 8 (o 3 continua) | 7 |
| `uf` do cliente 1 | `SP` (valor velho) | ausente, como na origem |
| `vl_unitario` do `CIM-50` | 33,5 | 33,5 |
| Resultado da CLI | grava e depois sai com erro: `o banco diverge do previsto: Cliente: esperado 7, encontrado 8` | `removed {nodes: 1}`, conferência `ok` |

Depois, uma propriedade manual (`anotacao_manual`) foi posta num cliente nos dois bancos, e o banco novo ganhou uma aresta manual (`revisadoPor`). Depois de mais uma carga:

| | Antigo | Novo |
|---|---|---|
| Propriedade manual no nó do akme | mantida | **apagada** (`SET n = r.p` troca todas as propriedades) |
| Aresta manual saindo de nó do akme | não testado | **apagada** (`removed {relationships: 1}`) |

Recarregar sem mudar nada não alterou nenhum dos dois bancos: o antigo ficou com 59 nós e 59 arestas, e o novo com 53 nós e 52 arestas, com `removed 0/0`. Os dois artefatos de dry-run saem idênticos byte a byte de uma rodada para outra (`cmp`).

### Dimensão a dimensão

| Dimensão | Veredito | Por quê (evidência) |
|---|---|---|
| Forma do modelo de dados | igual | Mesmo label, mesmas propriedades, mesmas arestas e 213 células nos dois; 11 de 11 consultas idênticas. O antigo tinha a mais o label `Resource` e a propriedade `uri` |
| Plugin no servidor | melhor | O antigo exigia o n10s em `/plugins` e `procedures.unrestricted`; o novo roda num Neo4j sem plugin (`akme-neo4j-uso-novo`) |
| Aura | provavelmente melhor, **não testado** | O n10s não existe no Aura (decisão registrada no [índice](index.md)); o novo não usa plugin, mas só foi carregado no Neo4j local em Docker |
| Teto de linhas, Olist | melhor | Antigo: recusa, com teto de 100 mil, 4,09 GB e 9,5 s no dry-run. Novo: 446.873 linhas, 144 MB e 2,24 s no dry-run; carga em 34,1 s, com 356 MB |
| Tipos de valor | igual | `DATE`, `FLOAT` e `INTEGER` nos dois, na demo; os dois seguem os tipos da etapa 5 |
| Nomes das relações | igual nos dados, melhor na ontologia | Dados: `contem`, `pertenceA` e `referencia` nos dois. Ontologia: o antigo grava a relação como nó `:Relationship`; o novo, como seta `RELACAO_ONTOLOGIA` com o nome da relação em `nome` (o mesmo desenho do grafo da página do akme) |
| Ontologia no grafo | melhor | Multiplicidade, inversa, grão, aditividade e `nao_somar_apos_juntar_com` agora estão no banco; no antigo, 0 nós com regra de métrica |
| Ontologia ligada aos dados | igual (nenhum dos dois) | 0 arestas entre dado e `Conceito`; no antigo também não há aresta entre dado e `Class` |
| Documentação das colunas | **melhor** (depois da Task 10) | Medido antes da Task 10, era pior: o `neo4j.nt` antigo trazia um comentário por coluna (`# uf: termo uf. Estado do endereço...`, 9 linhas com "termo" na demo) e o `neo4j.cypher` não tinha nenhum. Depois da Task 10, `docs/publish/neo4j_schema.md` traz termo, definição e sinônimos por coluna, o banco tem um nó `:Termo` por termo ligado ao seu `Conceito`, e o esquema fica também na marca `_AkmeProjeto` |
| Legenda no Browser | melhor (Task 11) | Todo nó tem `name` (label, começo da chave e uma coluna descritiva), e o tutorial de seis páginas mostra o caminho; o antigo mostrava o `uri` |
| Sincronização | melhor, com um custo | Novo: apaga da origem o que sumiu (cliente 3, `uf` vazia). Antigo: mantém o dado velho e só acusa a divergência depois de gravar |
| Enriquecimento manual | **pior** | Uma propriedade ou aresta posta à mão num nó do projeto some na carga seguinte; no antigo, a propriedade manual ficava |
| Risco de apagar | **pior** | Se a origem vier incompleta numa carga (por exemplo, uma tabela truncada por engano), o novo apaga do Neo4j o que faltou. O plano de dry-run mostra "banco 8 → origem 7" antes da confirmação, mas a decisão é de quem confirma. Depois da revisão final: fonte com chave e sem linhas é recusada no plano, e remoção acima de 20% de algum label exige digitar o número de remoções |
| Idempotência | igual | Recarregar sem mudança: contagens iguais nos dois; `removed 0/0` no novo |
| Determinismo do artefato | igual | `cmp` de dois dry-runs: idênticos nos dois formatos |
| Tamanho do artefato | melhor | Demo: 7,3 KB (`.cypher`, só modelos de comando) contra 43,7 KB (`.nt`, com os dados); Olist: o `.nt` antigo tinha 736 MB |
| Interoperabilidade RDF e URIs | **pior** | O antigo dava a cada nó de dado um IRI (`https://akme.example/ontology#Pedido/1010`) e gerava N-Triples tipadas que qualquer ferramenta RDF lia. O novo não tem `uri` nos dados (só o `Conceito` guarda `iri`), e o gerador RDF do `n10s.py` foi apagado (418 linhas, commit `a154516`). O alvo `publish --target rdf` (Morph-KGC) continua, mas só a partir de `local_folder` |
| Inversas | melhor | O antigo tinha a inversa como nó solto, sem ligação. O novo (desde a Task 11) grava a inversa como seta `RELACAO_ONTOLOGIA` própria, com `inversa_de` e a multiplicidade lida ao contrário, e cada seta guarda a sua inversa em `inversa` |
| Tempo de consulta | igual | Na demo, 1 a 3 ms nos dois; no Olist, só o novo carrega, então não há comparação |

## 4. Limites

- Uma máquina (Apple M5, 24 GB), uma tarde, Neo4j Community local em Docker. Nada foi medido no Aura, em Enterprise ou em cluster.
- O Olist é registro de execução: dados e ontologia fora do repositório, carga numa cópia com três correções.
- O "antes × depois" é só na demo, com 43 linhas. No Olist, o antigo não carrega, então a comparação ali é só do dry-run.
- Os tempos de consulta são de cache quente (mediana depois de um aquecimento), sem carga concorrente. Durante esta medição, o contêiner do Olist foi encerrado uma vez por falta de memória da VM do Docker (`OOMKilled`), com outros contêineres abertos. Foi reiniciado, os dados estavam intactos e as consultas foram refeitas uma de cada vez. Isso mostra que o tamanho de memória do Neo4j merece atenção numa máquina compartilhada.
- A comparação com SQL usou SQLite em arquivo local, com índices. Não é Postgres, Snowflake nem Databricks, e serve só como ordem de grandeza.
- Não foi medido: um LLM de verdade lendo a camada `Conceito` e escrevendo consultas (a seção 2d mostra o que ele leria, não o que ele faria); escrita concorrente; consultas com `shortestPath` ou algoritmos de grafo (GDS); custo de memória do Neo4j por label; o tempo de carga do formato antigo no Olist, que nem chega a carregar.
- Os limites da camada semântica estão na seção 2d. A Task 10 tratou a descrição no nó, os termos, o glossário, as regras, as precedências e a regra que citava tabela. Continuam: relações sem definição na ontologia de origem, perguntas de competência fora do grafo e subclasses que não marcam os dados.
- As associações da seção 2a (UF e nota) são descritivas. Não foram controladas por número de itens, categoria ou período.
