# Task 11: tutorial do projeto no Neo4j Browser

Pedido de Mateus em 12/11/2026, depois da crítica do João (o Browser mostra bolinhas soltas e exige Cypher): um tutorial gerado sempre que alguém publica, sobre o projeto que for. Base: [Pesquisa: como ver o grafo](pesquisa-visualizacao.md) e o protótipo feito à mão para o Olist.

A task passou por três decisões de Mateus no mesmo dia, registradas em [Decisões de 12/11/2026](#decisoes-de-12112026). Esta página descreve o estado final da Task 11. O escopo está congelado.

!!! note "Mudança de 13/11/2026"
    Na correção G7/G8 o guia passou de seis para cinco páginas: "Os dados" entrou na primeira, que agora abre pelo mapa das classes e, até 500 registros, pelo grafo inteiro; o "Explorar" parte do registro mais ligado de cada classe; e o publish gera `docs/publish/neo4j_estilo.grass`. As perguntas de competência continuam fora do guia (decisão 3, abaixo). O texto desta página não foi reescrito; o guia atual está na seção 4.1 de `reports/docs_exp_neo4j/README.md`.

## O que muda

- **Tutorial curto a cada `publish --target neo4j`, dry-run ou carga.** `docs/publish/neo4j_guia.html`, ao lado de `neo4j.cypher` e `neo4j_schema.md`, no formato de guia do Neo4j Browser (`<article class="guide">`, um `<slide>` por página, blocos que rodam com um clique). Seis páginas, só de navegação, com duas ou três linhas de texto cada:
    1. **O que tem aqui:** cada label de dado com a contagem do plano, uma linha cada.
    2. **A ontologia:** o mapa das classes, relações e subclasses com os nomes do TTL. Com APOC, `apoc.create.vRelationship(a, r.nome, {}, b)` desenha setas virtuais, sem gravar nada. Sem APOC, a consulta devolve as setas `RELACAO_ONTOLOGIA` e a página diz como escolher `nome` como legenda. Depois da carga, o akme pergunta ao banco se a função existe e põe só a forma que funciona; no dry-run, as duas.
    3. **Os dados:** `CALL db.schema.visualization()` sem `Conceito`, `Termo` e `_AkmeProjeto`.
    4. **Explorar:** um bloco por label de dado, "um registro e tudo o que está ligado a ele", sempre caminhos, nunca nós soltos.
    5. **Como navegar:** clicar num tipo de relação, dois cliques numa bolinha, o painel de propriedades com `_descricao` (desde a rodada final, só com a opção `descricao_nos_dados`; sem ela, o slide manda ver a definição no `Conceito`). Também: seta `RELACAO_ONTOLOGIA` = relação da ontologia; o nome do TTL está em `nome`. Para ver o nome na seta, no painel *Results overview*, clique no chip `RELACAO_ONTOLOGIA` e escolha `nome` como legenda (o Browser guarda a escolha).
    6. **Perguntas em português:** o Query do console da Aura, com o gerador de Cypher (precisa de APOC), apontando para a seção "Perguntas em portugues pelo Aura console" do guia de uso (`reports/docs_exp_neo4j/README.md`).
- **Consultas salvas:** `docs/publish/neo4j_consultas.csv`, com as consultas de navegação do guia (a ontologia, os dados e uma por label), no formato que o painel *Queries → Upload* do Browser 2026.10 importa.
- **Arestas de dado com o nome exato do TTL** (`feitoPorCliente`), do domínio para o alcance.
- **Camada de ontologia como espelho do `schema.ttl`.** Um `Conceito` por classe, `SUBCLASSE_DE` por `rdfs:subClassOf` e uma seta `RELACAO_ONTOLOGIA` por `owl:ObjectProperty` e por par domínio/alcance, inversas incluídas. Cada seta tem `nome`, `rotulo`, `definicao`, `inversa`, `publicada_nos_dados` e a `multiplicidade` do contrato. Na inversa de um contrato vão `inversa_de` e a multiplicidade lida ao contrário. No Olist são 18 classes e 14 relações, como na página.
- **Nomes reservados:** uma relação chamada `RELACAO_ONTOLOGIA`, `SUBCLASSE_DE` ou `TEM_TERMO` é problema no plano.
- **Legenda `name` em todo nó.** Dado: `<Label> <até 8 caracteres de cada valor da chave> <coluna de legenda>`, por exemplo `ItemPedido 1001/CIM-50 100`. `Conceito` e `Termo`: o próprio nome. Marca: `Projeto <nome>`. Se a fonte tiver coluna `name`, ela vale; o akme só grava a sua nas linhas em que ela está vazia (o plano avisa).
- **Prévia por tipo de aresta:** banco, origem e "pelo menos N removidas", com aviso de tipo que a carga não grava mais.
- **Abrir o guia:** `akme review` serve o arquivo em `http://127.0.0.1:8765/neo4j/guia`, com CORS só para as origens do Neo4j Browser. No Browser: `:guide http://127.0.0.1:8765/neo4j/guia`. A CLI diz isso no fim do dry-run e da carga, com a linha opcional do `docker run` que abre o guia a cada conexão, e avisa quando o `akme review` no ar é de código antigo.
- **Esquema do LLM:** continua gravado em `docs/publish/neo4j_schema.md` e na marca do projeto, mas a mensagem final da CLI não manda mais o humano lê-lo; o guia de uso o cita só na seção do LLM.

## Decisões de 12/11/2026

1. **Nome do TTL nos dados (cerca de 18:35).** A primeira versão gravava as arestas de dado em UPPER_SNAKE (`PERTENCE_A`) para o mapa nativo não desenhar setas falsas. Depois de ver o mapa, Mateus pediu o nome exato do TTL nos dados e um tipo único, `RELACAO_ONTOLOGIA`, entre os `Conceito`. Os tipos continuam diferentes, e o mapa nativo continua sem setas falsas.
2. **Camada `Conceito` como espelho do TTL.** A primeira versão só desenhava os contratos (7 setas no Olist); a página do akme mostra 14 relações. O mapa do guia e a camada `Conceito` passaram a mostrar o mesmo que a página.
3. **Tutorial só de navegação, sem perguntas de competência.** A segunda versão tinha uma página por CQ, com o campo `cypher` proposto pelo agente, conferido no propose e com `EXPLAIN` na carga, e a contagem "N de M com consulta". Mateus achou o tutorial pesado demais. As perguntas de competência saíram do tutorial e do akme inteiro: o campo `cypher`, a conferência, o `EXPLAIN`, a contagem e o passo do `SKILL.md`. Perguntas em português ficam com o gerador de Cypher do console da Aura.

## Por quê

- **Legenda:** sem `name`, o Browser escolhe a primeira propriedade em ordem alfabética, que era `_carga`, igual em todos os nós. Por isso a legenda começa pelo label e pelo início da chave, que distingue cada nó.
- **Tipos diferentes entre ontologia e dados:** com o mesmo tipo em `Conceito` e nos dados, `db.schema.visualization` desenhava 24 setas no Olist, 18 delas falsas (ex.: `Pedido -contemItem-> Conceito`).
- **Tutorial curto:** quem abre o Browser quer ver o grafo; texto longo e uma página por pergunta afastam a pessoa de negócio, que é o público do tutorial.

## Como

- `akme/tools/neo4j_values.py`: `caption` (legenda).
- `akme/tools/neo4j_plan.py`: `type_problems` (nome de relação reservado); `caption_column`; `SourcePlan.caption` e `own_name`.
- `akme/tools/neo4j_load.py`: aresta de dado com o nome da relação; `name` em cada linha; `CLAIM` grava `name` na marca, ainda com a trava `carga_atual`; prévia por label e por tipo de aresta; grava o guia e o CSV no dry-run e de novo depois da carga, com `has_apoc()`.
- `akme/tools/neo4j_onto.py`: `name` em `Conceito` e `Termo`; setas `RELACAO_ONTOLOGIA {nome}` para toda relação do TTL.
- `akme/tools/neo4j_schema.py`: o bloco "Como consultar" explica o nome do TTL, `RELACAO_ONTOLOGIA` e `name`; cada aresta diz como ler a inversa.
- `akme/tools/neo4j_guide.py`: `guide_html(plan, apoc)`, `map_query`, `saved_queries_csv`, `guide_lines`.
- `akme/review_server.py`: rota `/neo4j/guia` (GET, HEAD e OPTIONS) com CORS só para as origens do Browser; `/api/versao` e cabeçalho `X-Akme-Versao`; `stale_message` e `ensure_running` reconhecem um servidor de código antigo, sem encerrá-lo.

O CORS vale só para `http(s)://127.0.0.1` e `localhost` na porta 7474 e na porta de `AKME_NEO4J_BROWSER_URL`, a própria origem dessa variável e `https://console.neo4j.io`. O servidor devolve a origem pedida, nunca `*`.

## Testes

- Unitários: `tests/test_neo4j_guide.py` (seis páginas curtas, sem CQ nem esquema do LLM, contagens, mapa com e sem APOC, explorar, como navegar, Aura, CSV só de navegação, determinístico, sem valor de dado); `test_neo4j_plan.py`, `test_neo4j_onto.py`, `test_neo4j_load.py`, `test_neo4j_schema.py`, `test_neo4j_values.py`, `test_review_server.py` e `test_neo4j_cli.py`.
- Integração (`scripts/test-neo4j.sh`): nomes do TTL e mapa nativo sem setas falsas; camada `Conceito` com o mesmo número de classes, relações e subclasses do `schema.ttl` da demo; prévia por tipo de aresta e a carga que apaga as de nome antigo; guia regravado depois da carga para o banco sem APOC, com toda consulta do CSV rodando e devolvendo resultado; legenda distinta em todo nó; verificadores da demo.

## Limites

- **Quem carregou com a versão UPPER_SNAKE** tem arestas `PERTENCE_A` no banco. A próxima carga mostra na prévia quantas serão removidas e avisa; a sincronização as apaga e grava as de nome do TTL.
- **Legenda automática:** usa a primeira coluna mapeada que não é chave nem join, sem julgamento. No Olist, Avaliação usa o texto livre do comentário e Cliente usa outro identificador. Fica só no banco.
- **APOC sem teste real:** o contêiner de teste não tem APOC; o mapa com setas virtuais e o gerador de Cypher do console da Aura não rodaram aqui.
- **Guia local:** `127.0.0.1:8765` só funciona na máquina do `akme review`.
- **CSV das consultas salvas:** o formato é o que o Browser 2026.10 exporta, testado no protótipo, sem documentação oficial.
- **Console da Aura:** não testamos `:guide` no console nem o `Access-Control-Allow-Private-Network` no Chrome.
