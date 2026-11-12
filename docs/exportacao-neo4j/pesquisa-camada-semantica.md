# Pesquisa: camada semântica no grafo

Pesquisa de 12/11/2026. Responde a duas perguntas de Mateus: a descrição de cada entidade não poderia ficar no próprio nó, para navegar e consultar melhor? E por que a exportação usa Cypher puro e não o n10s?

Usei três fontes de evidência: o histórico do repositório (commits e arquivos citados com caminho e linha), fontes primárias na web (documentação da Neo4j, código das bibliotecas, artigos) e um experimento medido no Olist, num contêiner descartável que já foi removido. Cada afirmação traz a fonte. Quando a frase é opinião minha, ela leva o rótulo **(julgamento)**.

> **Decisão de Mateus (12/11/2026):** opção A adotada para navegação: `_descricao` em cada nó e aresta de dado, mesmo sem ganho para o LLM. A opção E (esquema descritivo) foi gravada também no banco, na marca do projeto, para o LLM conseguir lê-la. Os termos (opção D) entraram como nós `Termo`. A opção C ficou de fora. O que foi feito está na [Task 10](task-10-semantica.md).

## Resumo

- **"Antes" a descrição também não ficava no nó de dado.** Em nenhuma versão exportada houve uma propriedade de descrição em `Pedido`, `Cliente` e nas outras classes. Com o n10s, a definição ficava em nós `:Class` separados (`comment`), e o vínculo com os dados era só o label, igual ao que fazemos hoje com `:Conceito`. A "descrição" de que você se lembra é o painel da página de revisão (`akme/static/graph.js:120`), que mostra a classe e os termos dela. Esse painel nunca foi para o Neo4j.
- **As ferramentas de LLM não leem descrição nenhuma por padrão.** O MCP oficial da Neo4j, o `neo4j-graphrag` e o LangChain montam o esquema com APOC e entregam só nomes e tipos. Medi isso no Olist. O texto de `Conceito.definicao` não chega ao LLM a menos que alguém consulte esses nós de propósito ou entregue o esquema pronto ao modelo.
- **Descrição ajuda o LLM, mas de forma modesta.** No BIRD (texto para SQL), as descrições de coluna levaram o GPT-4o de 30,1% para 33,3% de acerto. O conhecimento externo, ligado a cada pergunta, rendeu de +13 a +20 pontos. Na mesma linha, a Neo4j mostra que um esquema menor e filtrado acerta mais do que um esquema longo.
- **Pôr `descricao` em todos os nós (opção A) custa caro e rende pouco.** No Olist, isso aumenta o banco em 81,5 MB (+30%) e adiciona 42 milhões de caracteres repetidos a cada carga. Para o LLM, o ganho é só um trecho de 50 caracteres no esquema "enhanced". A seta `INSTANCIA_DE` (opção C) custa +46,9 MB (+17%), cria supernós (99.441 arestas no `Conceito` Pedido) e não acelera a consulta: as duas formas levam de 1 a 2 ms.
- **Recomendação, em ordem:** (1) gerar com o akme um esquema descritivo para o LLM, junto com a carga, com classes, colunas e termos, métricas, relações e regras; (2) levar os 25 termos para o grafo como nós `:Termo` ligados ao `Conceito`; (3) exigir definição nas relações. A opção A, no máximo, vira uma opção desligada por padrão. A opção C fica de fora.
- **A troca para Cypher foi certa em parte.** O motivo do Aura se confirma, e é o mais forte. O teto de 100 mil linhas era do nosso código (`MAX_ROWS` em `n10s.py`), não do n10s. Relação virar nó era um problema do `onto.import`, e dava para resolvê-lo mantendo o n10s só para os dados. O que se perdeu de fato foi o único gerador de RDF fiel. Para quem consome o grafo, isso pesa pouco **(julgamento)**.

## 1. Como era antes

### 1.1 O rascunho `akme/tools/cypher.py` (até 05/11/2026)

- **Nunca foi commitado.** `git log --all -- akme/tools/cypher.py` não retorna nada. O relatório de pesquisa o chama de "rascunho não commitado" (`reports/Exportar ontologia para Neo4j.md:230`), e `docs/neo4j/historico.md:26` registra que ele foi substituído pelo n10s em 05/11/2026.
- **Descrições ficavam só em comentários do script.** Segundo o relatório: "O rascunho grava termos e métricas só como comentários no script, e comentários não vão para o banco; quem conectar ao Neo4j verá `fl_ativo` sem saber que o financeiro define 'ativo' de outra forma" (`reports/Exportar ontologia para Neo4j.md`, seção "Converter tabelas em grafo não cria camada semântica"). Como o arquivo não está no git, não há como conferir o código em si. Essa é a única descrição que restou dele.

### 1.2 O exportador com n10s (`5c6b924`, 09/11/2026, até `a154516`)

- **Configuração:** `n10s.graphconfig.init({handleVocabUris: 'IGNORE'})`, sem `handleRDFTypes` (`git show 5c6b924:akme/tools/n10s.py`, linhas 28 e 365). Na documentação do n10s, o padrão de `handleRDFTypes` é `LABELS`: "rdf:type statements are imported as node labels". O vínculo como aresta só existe com `NODES` ou `LABELS_AND_NODES` ([n10s, referência de configuração](https://neo4j.com/labs/neosemantics/4.3/reference/)).
- **Instância:** `rdf:type` virava label. O teste registrou o nó `Pedido` com as colunas e `uri`, e com os labels `["Pedido", "Resource"]`, sem descrição e sem aresta para a classe (`docs/neo4j/teste-n10s/P1_R2.json`, chaves `exemplo_no_pedido` e `labels_dos_nos`).
- **Classe:** o `n10s.onto.import` criava `(:Class {name, label, uri, comment})`. O `comment` era o `rdfs:comment` do `schema.ttl`. Exemplo do teste: `{"comment": "Solicitacao de compra de um cliente, com status e valor total.", "label": "Pedido"}` (`P1_R2.json`, chaves `C2_class_props` e `C7_definicao`). As relações viravam nós `:Relationship`, ligados por `DOMAIN` e `RANGE` (`docs/neo4j/historico.md:13`).
- **Conclusão:** a descrição ficava num nó separado, e a junção com os dados era por nome (`Class.name` = label). É o mesmo desenho do `:Conceito` de hoje, com outros nomes.

### 1.3 A página de revisão (`akme/static/graph.js`)

- **O painel da classe** mostra `c.comment || "sem descrição"` (`akme/static/graph.js:120`). Desde o primeiro commit era `"sem descricao"`, sem acento (`c2e9e83`). Logo abaixo vêm "Termos e mapeamentos", com a definição, os sinônimos e as colunas de cada termo (`graph.js:123-126`).
- **É um grafo de classes, não de instâncias.** Ele junta, na tela, a definição da classe com a das colunas. Nenhuma exportação para o Neo4j fez isso.

### 1.4 Hoje (`neo4j_onto.py`)

- **`Conceito`:** um nó por classe, com `nome`, `rotulo`, `definicao` e `iri`. As métricas acrescentam `expressao`, `unidade`, `grao`, `aditividade`, `nao_somar_sobre` e `nao_somar_apos_juntar_com` (`akme/tools/neo4j_onto.py:57-62`, `25-45`).
- **Setas:** `SUBCLASSE_DE` e uma seta por contrato, com `rotulo`, `definicao`, `multiplicidade`, `inversa` e `publicada` (`neo4j_onto.py:81-88`).
- **Relações sem definição:** a `definicao` das setas está vazia no Olist. Os 14 blocos `owl:ObjectProperty` do `schema.ttl` não têm `rdfs:comment` (conferido na cópia de aceitação), porque `add_relation` não exige `comment` (`akme/models.py:82`, ao contrário de `add_class` na linha 81).
- **As duas camadas não se ligam**, por decisão documentada (`docs/neo4j/exportacao.md:42`).
- **O que não vai para o grafo:** os 25 termos, o glossário, as restrições, a precedência e as perguntas de competência. Isso contradiz a decisão anterior do relatório, "A + B", que previa nós `:Term` e `:Metric` gerados (`reports/Exportar ontologia para Neo4j.md`, seção "Converter tabelas...", tabela de opções). Das duas metades, só a das métricas foi feita, como propriedades do `Conceito`.

| Versão | Descrição da classe | Descrição da coluna (termo) | Instância → classe |
|---|---|---|---|
| `cypher.py` (não commitado) | Comentário no script, fora do banco | Comentário no script | Label |
| n10s (`5c6b924`) | `(:Class).comment`, nó separado | Comentário no `.nt`, fora do banco (`n10s.py:138-150`) | Label (`handleRDFTypes` padrão) |
| Cypher atual | `(:Conceito).definicao`, nó separado | Não exportada | Label; sem aresta |
| Página de revisão | Painel da classe | No mesmo painel | Não se aplica (só classes) |

## 2. Para que serve a camada semântica no grafo

Os consumidores pedidos são três: um LLM que escreve Cypher (text2cypher ou GraphRAG), um agente pelo MCP somente leitura e usuários de negócio que, segundo Mateus, "dependem da IA, não escrevem Cypher". Para os três, a camada serve para dizer o que cada label, propriedade e seta significa, e como não errar: métrica, grão e o que não pode ser somado. Os fatos já estão nos nós de dado.

### 2.1 O que as ferramentas de LLM realmente leem

Rodei as três bibliotecas contra o Olist carregado (seção 3.3) e li o código delas:

| Ferramenta | Consulta | O que entrega ao LLM |
|---|---|---|
| MCP oficial da Neo4j (`neo4j/mcp`, Go), tool `get-schema` | `CALL apoc.meta.schema({sample: $sampleSize})` ([get_schema_handler.go](https://raw.githubusercontent.com/neo4j/mcp/main/internal/tools/cypher/get_schema_handler.go)) | Label ou tipo, nome e tipo de cada propriedade, setas com direção. "The response includes no descriptions or counts" |
| `mcp-neo4j-cypher` 0.6.0, `get_neo4j_schema` | A mesma `apoc.meta.schema` (`server.py:86`), depois `clean_schema` guarda só `type`, `indexed`, `labels` e `direction` (`server.py:88-140`) | Nomes e tipos |
| `neo4j-graphrag` 1.24.0, `get_schema` (padrão do `Text2CypherRetriever` quando não se passa `neo4j_schema`, `retrievers/text2cypher.py:163-164`) | `apoc.meta.data` (`schema.py:31-56`) | `Label {prop: TIPO}` e padrões `(:A)-[:r]->(:B)` |
| `neo4j-graphrag` com `is_enhanced=True` e `langchain-neo4j` 0.11.0 com `enhanced_schema=True` (que reutiliza o mesmo `format_schema`) | Também amostra valores: `substring(toString(n.prop), 0, 50)` (`schema.py:568-569`) | Exemplo ou lista de até 10 valores, **cortados em 50 caracteres** |

O que cada uma devolveu para o grafo atual (medido):

- **Esquema padrão (3.359 caracteres):** traz `Conceito {definicao: STRING, rotulo: STRING, ...}`, só o tipo, sem o texto. Traz também `(:Conceito)-[:contemItem]->(:Conceito)` ao lado de `(:Pedido)-[:contemItem]->(:ItemPedido)`. Com isso, o LLM vê o mesmo tipo de seta nas duas camadas. Um `MATCH ()-[:contemItem]->()` sem label passa a contar uma aresta da ontologia. É um risco real para contagens **(julgamento: não medi o efeito sobre um LLM)**.
- **Esquema enhanced (6.989 caracteres):** uma única definição aparece, como exemplo cortado: `definicao: STRING Example: "Dias entre a data estimada de entrega e a data de "`.
- **Conclusão:** em nenhuma configuração padrão a definição de `Pedido` ou o significado de `review_score` chega ao LLM. Isso vale para as opções A, B e C. Todas as ferramentas exigem APOC Core. Ele vem no Aura ([Aura, APOC support](https://neo4j.com/docs/aura/platform/apoc/)) e na imagem Docker, em `/var/lib/neo4j/labs` (visto no contêiner). No Community é preciso ligá-lo com `NEO4J_PLUGINS='["apoc"]'`.

### 2.2 Descrições melhoram o acerto? O que a literatura mede

- **Text2Cypher e esquema:** a Neo4j comparou o esquema enhanced, o base e versões podadas no dataset Text2Cypher 2024 (22.093 exemplos de treino e 2.471 de teste, Llama-3.1-8B). Prompts mais longos tiveram desempenho pior, e o melhor resultado veio do esquema podado por correspondência exata ([Ozsoy, Neo4j, 08/04/2025](https://neo4j.com/blog/developer/schema-representation-in-text2cypher/); [arXiv 2505.05118](https://arxiv.org/abs/2505.05118)). **O estudo não testa descrições.** Não achei estudo de Text2Cypher que isole o efeito de descrever labels ou propriedades.
- **Texto para SQL, descrições de coluna:** no BIRD dev, o GPT-4o acertou 30,13% sem descrições, 31,34% com as do BIRD, 33,28% com descrições "gold" e 36,78% com as geradas pelo Qwen2. O Mixtral foi de 17,5% para 27,2% com gold ([Wretblad et al., 2024, arXiv 2408.04691, Tabela 3](https://arxiv.org/html/2408.04691v3)). Colunas com nomes pouco informativos ganham mais. É o nosso caso: `review_score`, `product_name_lenght` e `order_delivered_customer_date`.
- **Texto para SQL, conhecimento externo por pergunta:** o GPT-4 foi de 30,90% para 46,35% (+15,45) no dev e de 34,88% para 54,89% (+20,01) no teste ([Li et al., NeurIPS 2023, BIRD, Tabela 2](https://arxiv.org/html/2305.03111)). Atenção: esse conhecimento é uma dica escrita para cada pergunta, não a descrição do esquema. O equivalente mais próximo no akme são as CQs aprovadas com a resposta e os contratos de métrica **(julgamento)**.
- **O que concluo (julgamento):** descrever colunas e métricas tem ganho medido e moderado, e o que mais ajuda é contexto específico para a pergunta. Despejar texto em todo nó não é a forma de levar isso ao LLM, porque as ferramentas não o leem e um esquema longo piora o acerto.

### 2.3 Navegação humana

- **Neo4j Browser:** ferramenta de desenvolvedor, sempre parte de uma consulta (`docs/neo4j/usos-do-grafo.md`, 1.4). Ao clicar num nó, o painel mostra as propriedades dele, então só a opção A mostraria a descrição sem um passo a mais **(julgamento, a partir do uso; não medi)**.
- **Bloom e Explore:** a perspectiva define categorias, propriedades visíveis e estilo, inclusive a legenda (caption) ([Bloom, perspectivas](https://neo4j.com/docs/bloom-user-guide/current/bloom-perspectives/bloom-perspectives/)). A página não diz se a perspectiva guarda uma descrição da categoria. Não testado por nós.
- **Descrição nativa:** o Neo4j não tem lugar para descrever label, tipo de relação ou propriedade. A sintaxe de esquema (restrições, índices e graph types) não tem `COMMENT` nem descrição, e graph types são Enterprise e Cypher 25, a partir de 2026.02 ([Cypher Manual, schema syntax](https://neo4j.com/docs/cypher-manual/current/schema/syntax/)). Com isso, a opção F (lugar nativo) não existe.
- **Ontologia como nós ao lado dos dados** é o padrão que a própria Neo4j mostrou: Barrasa guarda o schema.org como nós ligados por subclasse e usa isso para inferir ("loans" voltam numa busca por "financial product"), não para navegação nem para o LLM ([Barrasa, Neo4j, 2020](https://neo4j.com/blog/knowledge-graph/ontologies-in-neo4j-semantics-and-knowledge-graphs/)).

## 3. Onde guardar a descrição

### 3.1 As opções

- **A.** Propriedade `descricao` em cada nó (e aresta) de dado, copiada do conceito.
- **B.** Metagrafo separado: a camada `Conceito` de hoje.
- **C.** B mais uma aresta `(:Pedido)-[:INSTANCIA_DE]->(:Conceito)` por nó.
- **D.** B mais os termos como nós `(:Termo {nome, definicao, sinonimos, coluna, unidade})-[:DESCREVE]->(:Conceito)`.
- **E.** Esquema descritivo gerado pelo akme ao lado da carga, por exemplo `docs/publish/neo4j_schema.md` ou `.json`, entregue ao LLM pelo parâmetro `neo4j_schema` do `Text2CypherRetriever` (`text2cypher.py:116`) ou por uma tool ou recurso MCP.
- **F.** Lugar nativo do Neo4j: não existe (2.3).

### 3.2 Comparação

Custos medidos no Olist (446.873 nós de dado e 568.964 arestas, dos quais 18 são `Conceito`). Os itens marcados (julgamento) não foram medidos.

| | Usuário no Browser | O que o LLM lê por padrão | Disco (medido) | Escrita (medida) | Definição muda: escritas | Riscos |
|---|---|---|---|---|---|---|
| **A** | Vê a descrição ao clicar no nó | Esquema padrão: nada. Enhanced: 50 caracteres por label | **+81,5 MB (+30%)**: de 274,0 para 355,5 MB; strings de 16,9 para 98,3 MB | ~2,7 s líquidos para gravar em todos; +42,2 milhões de caracteres por carga pelo Bolt | 99.441 para `Pedido`. Mas a carga já regrava todo nó (`SET n = r.p`, `neo4j_load.py:181-182`), então o custo vira bytes, não comandos | Mistura metadado com coluna (o LLM pode filtrar por `descricao`); polui `properties(n)`; não serve para as setas (definição vazia) |
| **B** (hoje) | Precisa consultar `Conceito` à parte | Só o tipo `definicao: STRING`; o texto não chega | 18 nós, desprezível | Já incluso na carga (~30 s no total) | 1 nó | Setas com o mesmo nome nas duas camadas confundem padrões sem label (2.1) |
| **C** | Expandir o nó mostra o `Conceito`; expandir o `Conceito` traz até 99.441 vizinhos (79 ms no banco; o Browser corta a exibição) | 7 padrões novos `(:X)-[:INSTANCIA_DE]->(:Conceito)` no esquema, sem texto | **+46,9 MB (+17%)**: de 274,0 para 320,9 MB (arestas com `_carga`) | ~3,8 s líquidos por carga | 1 nó | Supernós; padrões extras no esquema; conferência e consultas genéricas precisam excluir a seta |
| **D** | Consulta `Termo` ligado ao `Conceito` | Só nomes e tipos, como B | ~25 nós e 25 setas (estimado; julgamento) | Desprezível (julgamento) | 1 nó | Mais um label no esquema; precisa sair da conferência |
| **E** | Não muda (o arquivo é para o LLM e para quem lê) | Tudo o que for passado: definição, colunas, métricas, regras, exemplos | Fora do banco | Gerado no dry-run, sem rede | 1 arquivo, regenerado | Precisa ser entregue ao LLM: as ferramentas não o acham sozinhas |

**Consulta "qual a definição deste pedido?"** (mediana de 200 execuções, dbHits pelo `PROFILE`):

| Forma | Mediana | p95 | dbHits |
|---|---|---|---|
| B, junção por label (`c.nome IN labels(p)`) | 1,17 ms | 2,59 ms | 7 |
| B, nome fixo | 2,35 ms (inclui o aquecimento da primeira série) | 3,84 ms | 6 |
| C, seta `INSTANCIA_DE` | 1,05 ms | 1,80 ms | 9 |

As diferenças estão abaixo de 1,5 ms e dentro do ruído. A seta não traz ganho de consulta.

**Determinismo:** as cinco opções são determinísticas, todas derivadas de `schema.ttl` e `content.yml`.

**Sincronização:** em A e C, a descrição ou a seta precisa entrar no mesmo lote da carga para receber a `_carga`. Senão, a sincronização (`SYNC_NODES` e `SYNC_EDGES`, `neo4j_load.py:48-51`) apaga a seta. Em B, D e E a fonte é uma só.

### 3.3 Como medi

- **Ambiente:** contêiner `akme-neo4j-pesquisa`, `neo4j:2026.10.1` Community, em `127.0.0.1:58474/58687`. A porta 57687 pedida já estava ocupada por outro contêiner (`akme-neo4j-uso-novo`), que não foi tocado.
- **Carga:** o Olist veio da cópia de aceitação, pela CLI (`publish --target neo4j --no-dry-run`). A carga levou 31,4 s e 29,7 s numa segunda base limpa, e a conferência deu `ok: true`.
- **Disco:** `du -sk /data/databases/neo4j` depois de desligar o banco (o desligamento faz o checkpoint), lido por um contêiner auxiliar. Medi a partir de uma base recém-carregada em cada caso (A e C, cada um na sua).
- **Pré-alocação:** os arquivos crescem em blocos. A conta pelos registros dá cerca de 70 MB para A (546.314 blocos de string de 128 B) e cerca de 15 MB de registros de aresta para C (446.873 × 34 B), mais as propriedades `_carga`. Os números do `du` incluem essa pré-alocação.
- **Tempos líquidos:** descontado 0,94 s de partida do `cypher-shell`.
- **Esquemas:** `neo4j-graphrag` 1.24.0, `mcp-neo4j-cypher` 0.6.0 e `langchain-neo4j` 0.11.0, num venv temporário já apagado, com APOC Core 2026.10.1 ligado.
- **Limpeza:** o contêiner e o volume foram removidos.

## 4. Por que Cypher e não n10s, e se foi certo

### 4.1 Os motivos registrados

Fontes: `docs/neo4j/historico.md:11-18`, `docs/exportacao-neo4j/index.md` (seção "Por que mudar") e o desenho da mudança. A decisão foi de Mateus, em 11/11/2026, depois do teste ("pode ser").

| Motivo | O que a evidência diz | Avaliação |
|---|---|---|
| O n10s não existe no Aura | "Only available for Neo4j self-hosted (CE and EE) and is **not** available in Aura" ([n10s](https://neo4j.com/labs/neosemantics/)). Além disso, é projeto Labs, "not intended or approved for use in production" (`reports/...:44`, citando o LABS_DISCLAIMER), e a última versão mira o 2025.06 | **Procede.** É o motivo mais forte, porque o grafo deve virar aplicação e poder rodar no Aura do cliente |
| Teto de 100 mil linhas | O teto era `MAX_ROWS = 100_000` e `read_sample(source, MAX_ROWS + 1)` **no nosso** `n10s.py` (`5c6b924`, linhas 25 e 259-262). O `4b1e167` já tinha trocado a leitura pelo plano em blocos enquanto o `n10s.py` ainda existia | **Não procede como motivo contra o n10s.** O limite era nosso e dava para corrigir no mesmo caminho |
| Relações viravam nós (`Relationship`, `DOMAIN` e `RANGE`) | É o comportamento do `onto.import` (`historico.md:13`, teste C2) | **Procede para o `onto.import`**, mas existia meio-termo: dados por `rdf.import` e ontologia em Cypher nosso. O relatório já dizia que o T-box "pode ser gerado em Cypher simples pelo exportador, sem n10s" (`reports/...:26`) |
| Pedido do colega: conceitos como nós e relações como setas | Atendido pela camada `Conceito` | **Procede, mas não exigia sair do n10s** (ver a linha acima) |

### 4.2 O que o n10s dava e o que se perdeu

| Item | Com n10s | Hoje | Importa para LLM e usuário? |
|---|---|---|---|
| Descrição no nó de dado | Não (seção 1.2) | Não | Nada mudou |
| Instância → classe | Label (`handleRDFTypes` padrão) | Label | Nada mudou |
| Definição da classe no banco | `Class.comment` | `Conceito.definicao` | Equivalente |
| URI por nó (`uri`) | Sim | Não; `iri` só no `Conceito`, `_id` nos dados | Pouco: nenhum dos consumidores usa URI (julgamento) |
| RDF de ida e volta | O n10s exportava RDF; o `n10s.py` tinha o único gerador de RDF fiel (chaves, tipos e relações) | O gerador foi apagado por decisão de Mateus (desenho, linha 36); o alvo `rdf` continua com os defeitos do R1 (`docs/neo4j/teste-n10s.md`: itens identificados pela quantidade, sem relações, sem tipos) | Para o grafo, não. Para interoperabilidade (Morph-KGC, SPARQL, outro triplestore), **é uma perda real**, recuperável pelo `5c6b924` |
| Inferência por hierarquia | `n10s.inference.nodesLabelled` devolveu os 43 nós (teste C7) | `SUBCLASSE_DE` só entre conceitos; os nós de dado não têm labels de ancestrais | Pouco no Olist: as subclasses de `Avaliacao` (positiva, neutra, negativa) não têm nós de dado. Pode importar em outro domínio |
| SHACL | Só funcionava com `SHORTEN`, não com `IGNORE` (teste C8) | Não | Nada mudou na prática |
| Vocabulário padrão | `Resource`, `Class`, `SCO` | Nomes em português, próprios | Neutro |

### 4.3 Veredito (julgamento)

**A decisão foi certa no resultado e fraca em parte do argumento.**

- **Certa no resultado:** Aura e o aviso de "não aprovado para produção" bastam para não depender de plugin numa aplicação real. O caminho atual também trouxe sincronização e conferência contra a fonte inteira.
- **Fraca no argumento:** dois dos quatro motivos (o teto e a forma da ontologia) não eram do n10s, e o registro os apresenta como se fossem. Vale corrigir o `historico.md`.
- **O custo real** foi apagar o gerador de RDF fiel. Isso não afeta o grafo nem o LLM, mas enfraquece o alvo `rdf`.
- **Na pergunta deste estudo**, onde fica a descrição, a troca **não mudou nada**: nos dois caminhos a definição mora num nó separado e não chega ao LLM.

## 5. Recomendação

Em ordem de prioridade. Os itens 1 a 3 cabem numa próxima branch, porque mudam o que a carga grava ou acrescentam saídas. Esta branch só documenta.

1. **E: esquema descritivo para o LLM, gerado pelo akme** (prioridade alta)
    - **Por quê:** é o único caminho em que a definição chega ao modelo (2.1). É também o que a literatura apoia: descrição de coluna mais esquema enxuto (2.2).
    - **Conteúdo:** os labels com a definição; cada propriedade com o termo, a definição, os sinônimos e a unidade; as setas com direção, multiplicidade e inversa; as métricas com expressão, grão, aditividade e "não somar após juntar com"; o glossário; a precedência; as CQs aprovadas como exemplos.
    - **Exclusões:** `Conceito`, `_AkmeProjeto` e `_id`, `_projeto` e `_carga` ficam de fora dos padrões. O `construct_schema` do LangChain já aceita exclusão de tipos (`langchain_neo4j/chains/graph_qa/cypher.py:47-75`).
    - **Onde:** em `akme/tools/neo4j_load.py`, gravar ao lado de `docs/publish/neo4j.cypher` a partir de `semantic_model` (`akme/tools/publish.py:42`), que já reúne colunas, definições, métricas, glossário, precedência e exemplos. Expor também como recurso ou tool no `akme/server.py`.
    - **Custo:** zero no banco.
2. **D: termos como nós `:Termo`** (prioridade média)
    - **Formato:** `(:Termo {nome, definicao, sinonimos, coluna, unidade})-[:DESCREVE]->(:Conceito)`, a partir de `terms` e `mappings` do `content.yml`.
    - **Por quê:** quem só tiver o MCP somente leitura, sem o arquivo do item 1, pode ler a semântica com uma consulta. A documentação deve dizer "consulte `Conceito` e `Termo` antes de escrever Cypher". Isso também cumpre a decisão "A + B" do relatório, que ficou pela metade.
    - **Onde:** `akme/tools/neo4j_onto.py` mais a contagem em `verify` (`neo4j_load.py:320-335`).
    - **Custo:** desprezível.
3. **Exigir `comment` em `add_relation`** (prioridade média)
    - **Onde:** `akme/models.py:82` e o `SKILL.md`, na etapa que cria relações.
    - **Por quê:** hoje todas as setas têm `definicao` vazia.
4. **A como opção, desligada por padrão** (prioridade baixa)
    - **Formato:** `descricao_no_no: true` na etapa 5, para quem navega pelo Browser.
    - **Custo:** +30% de disco e +42 MB por carga no Olist. Não melhora o LLM.
5. **C: não fazer**
    - **Por quê:** custa +17% de disco, cria supernós e acrescenta padrões ao esquema, sem ganho de consulta (3.2). O vínculo por label já é exato e indexado.
6. **Corrigir o registro e decidir o RDF**
    - **Registro:** em `docs/neo4j/historico.md`, deixar claro que o teto de 100 mil linhas era do nosso código e que relação virar nó era um problema do `onto.import`.
    - **RDF:** decidir se o gerador de RDF fiel do `5c6b924` volta para o alvo `rdf`.

**Para decidir com Mateus e Gabriel:**

- **Entrega do esquema:** o LLM consumidor vai receber o esquema do akme (item 1), ou só conectará o MCP oficial? Se for só o MCP oficial, o item 2 vira prioridade e a documentação precisa ensinar a ler `Conceito` e `Termo`.
- **Browser:** Gabriel quer ver a descrição ao clicar no nó? Se quiser, o item 4 entra, com o custo medido.
- **Separação das camadas:** as setas da ontologia devem continuar com o mesmo nome das de dado? Isso ajuda a leitura humana, mas mistura os padrões no esquema que o LLM vê (2.1).

## 6. Fontes

**Repositório**

- `git show 5c6b924:akme/tools/n10s.py` (linhas 25, 28, 138-150, 259-262, 350-370); `4b1e167`; `a154516`; `c2e9e83`
- `akme/tools/neo4j_onto.py`, `akme/tools/neo4j_load.py`, `akme/tools/publish.py`, `akme/models.py:81-82`, `akme/static/graph.js:105-130`
- `docs/neo4j/historico.md`, `docs/neo4j/teste-n10s.md`, `docs/neo4j/teste-n10s/P1_R2.json`, `docs/neo4j/exportacao.md`, `docs/neo4j/usos-do-grafo.md`, `reports/Exportar ontologia para Neo4j.md`

**Código de terceiros (lido e executado)**

- [neo4j/mcp, get_schema_handler.go](https://raw.githubusercontent.com/neo4j/mcp/main/internal/tools/cypher/get_schema_handler.go) e [repositório](https://github.com/neo4j/mcp)
- `mcp-neo4j-cypher` 0.6.0 (`server.py`), `neo4j-graphrag` 1.24.0 (`schema.py`, `retrievers/text2cypher.py`), `langchain-neo4j` 0.11.0 (`graphs/neo4j_graph.py`, `chains/graph_qa/cypher.py`), instalados do PyPI em 12/11/2026

**Documentação da Neo4j**

- [n10s](https://neo4j.com/labs/neosemantics/); [n10s, configuração](https://neo4j.com/labs/neosemantics/4.3/reference/)
- [Cypher Manual, schema syntax](https://neo4j.com/docs/cypher-manual/current/schema/syntax/)
- [Aura, APOC support](https://neo4j.com/docs/aura/platform/apoc/)
- [Bloom, perspectivas](https://neo4j.com/docs/bloom-user-guide/current/bloom-perspectives/bloom-perspectives/)
- [Barrasa, Ontologies in Neo4j](https://neo4j.com/blog/knowledge-graph/ontologies-in-neo4j-semantics-and-knowledge-graphs/)
- [Ozsoy, The impact of schema representation in the Text2Cypher task](https://neo4j.com/blog/developer/schema-representation-in-text2cypher/)

**Artigos**

- [Enhancing Text2Cypher with Schema Filtering, arXiv 2505.05118](https://arxiv.org/abs/2505.05118)
- [Wretblad et al., Synthetic SQL Column Descriptions and Their Impact on Text-to-SQL Performance, arXiv 2408.04691](https://arxiv.org/html/2408.04691v3)
- [Li et al., BIRD, NeurIPS 2023, arXiv 2305.03111](https://arxiv.org/html/2305.03111)

## 7. Limites

- **Sem teste com LLM:** não medi o efeito de A, B, C, D ou E sobre um LLM real escrevendo Cypher. Os ganhos citados vêm de texto para SQL (BIRD), não de Cypher, e o estudo de Text2Cypher não testa descrições. O teste certo é o já previsto: as CQs do Olist em três configurações (`reports/...`, seção "O ganho se mede pelo acerto").
- **Browser, Bloom e Explore:** o que cada um mostra ao clicar e expandir vem da documentação e do uso, não de uma medição nesta pesquisa. O Bloom e o Explore não foram abertos.
- **Disco:** os números do `du` incluem a pré-alocação em blocos do formato de registro do Community. Os valores lógicos estão na seção 3.3. No Enterprise ou no Aura (formato `block`), os números seriam outros.
- **Uma base só:** o Olist tem 7 labels de dado com definição. Num domínio com hierarquia povoada, C e a inferência do n10s pesariam de outro jeito.
- **`cypher.py`:** o arquivo não está no git. O que se diz dele vem do relatório e do `historico.md`.
- **De passagem:** o texto de "Para ver o grafo" depois da carga mostra `http://localhost:7474` mesmo quando o Bolt está noutra porta (`neo4j_load.py:104-109`). É um detalhe fora do escopo desta pesquisa.
