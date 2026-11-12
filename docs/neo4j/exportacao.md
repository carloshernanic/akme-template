# Exportação para o Neo4j

**Situação em 12/11/2026:** a exportação grava dados e ontologia em **Cypher puro**, pelo driver oficial, sem plugin no servidor. Testado no Neo4j 2026.10.1 Community; sem plugin, não depende da edição (Aura e Enterprise não testados). A demo carrega, confere, sincroniza e repete sem duplicar num Neo4j 2026.10.1 descartável. Guia de uso passo a passo: [reports/docs_exp_neo4j/README.md](../../reports/docs_exp_neo4j/README.md).

- Por que mudou e o que mudou em cada tarefa: páginas MkDocs em [docs/exportacao-neo4j/](../exportacao-neo4j/index.md) (`uv run --extra docs mkdocs serve`); carga e sincronização em [task-6-carga.md](../exportacao-neo4j/task-6-carga.md), troca na CLI em [task-7-troca.md](../exportacao-neo4j/task-7-troca.md)
- Registro cronológico: [historico.md](historico.md)

**Antes (n10s):** de 05/11/2026 a 11/11/2026, o akme gerava RDF (`docs/publish/neo4j.nt`) e o plugin n10s carregava. A troca e o motivo estão na entrada de 11/11/2026 do [historico.md](historico.md); o teste que levou ao n10s está em [teste-n10s.md](teste-n10s.md). O código antigo fica no histórico do git.

## Como funciona

```
content.yml (contratos, termos, mappings, etapa 5) + schema.ttl + adapter
        ↓
1. plano (dry-run, sem banco): lê cada fonte em blocos; confere chave, tipos e joins;
   conta nós e arestas esperados; lista problemas e avisos; grava docs/publish/neo4j.cypher,
   o esquema para o LLM, docs/publish/neo4j_schema.md, o tutorial do Browser,
   docs/publish/neo4j_guia.html, e as consultas salvas, docs/publish/neo4j_consultas.csv
        ↓
humano lê o resumo (com o que o banco tem hoje, por label, e quantos nós serão apagados) e confirma na CLI
        ↓
2. carga: confere a versão (5.23 ou mais novo) e depois o destino; marca o projeto com carga_atual;
   cria restrições e índices;
   grava nós em lotes de 5.000; grava arestas (o banco resolve o join pelo índice);
   grava as camadas Conceito e Termo e o esquema na marca; tudo com a _carga desta rodada
        ↓
3. sincronização: se carga_atual ainda é esta carga, apaga nós e arestas do projeto com _carga antiga
        ↓
4. conferência: conta no banco por label e por padrão (:Dominio)-[:TIPO]->(:Alcance);
   só contagens, nenhum valor é comparado
```

O código está em `akme/tools/`:

| Módulo | Papel |
|---|---|
| `neo4j_values.py` | Converte cada célula para o tipo aprovado e calcula a identidade `_id` do nó |
| `neo4j_plan.py` | Plano da carga (dry-run): lê em blocos, confere e conta, sem guardar as linhas |
| `neo4j_onto.py` | Camadas `Conceito` e `Termo`: comandos da ontologia, com parâmetros; textos de `_descricao` |
| `neo4j_schema.py` | Esquema descritivo para o LLM, em Markdown, determinístico |
| `neo4j_guide.py` | Tutorial do projeto no Neo4j Browser e consultas salvas, determinísticos, só de navegação |
| `neo4j_load.py` | Proteção do destino, carga, sincronização, conferência, artefato e textos da CLI |

**O modelo no grafo** (desde a Task 11, `name` em todo nó e a camada `Conceito` como espelho do `schema.ttl`; quem carregou com a versão intermediária, de arestas em UPPER_SNAKE, vê na prévia as arestas de nome antigo que a sincronização vai apagar):

- **Nó de dado:** o label é a classe (ex.: `Pedido`). Uma propriedade por coluna preenchida, com o nome original e o tipo da etapa 5, mais `_id` (valores da chave, como `1001/CIM-50`), `_projeto`, `_carga`, `_descricao` (o `rdfs:comment` da classe, igual a `Conceito.definicao`; ausente se a classe não tiver definição) e `name`, a legenda que o Browser mostra na bolinha: o label, até 8 caracteres de cada valor da chave e o valor da coluna de legenda do plano (a primeira coluna mapeada da fonte, na ordem do `content.yml`, que não é chave nem join), por exemplo `ItemPedido 1001/CIM-50 100`. Se a fonte tiver coluna `name`, ela vale e o akme não grava a sua (o plano avisa).
- **Aresta de dado:** o tipo é o nome exato da relação no `schema.ttl` (ex.: `pertenceA`), do domínio para o alcance. Uma relação com o nome de um tipo da camada de ontologia (`RELACAO_ONTOLOGIA`, `SUBCLASSE_DE`, `TEM_TERMO`) é problema no plano. Propriedades `_carga` e `_descricao`: o `rdfs:comment` da relação ou, enquanto ela não tiver um, o `rdfs:label`; ausente sem nenhum dos dois. `_descricao` entra no mesmo `SET` que grava o nó ou a aresta.
- **Camada `Conceito`:** um nó `:Conceito` por classe do `schema.ttl`, com `nome`, `rotulo`, `definicao` e `iri` (métricas acrescentam expressão, unidade, grão, aditividade, `nao_somar_sobre` e `nao_somar_apos_juntar_com`, este com labels do grafo, ou `fonte <nome> (nao publicada)`). `(:Conceito)-[:SUBCLASSE_DE]->(:Conceito)` por `rdfs:subClassOf` e uma seta `(:Conceito)-[:RELACAO_ONTOLOGIA]->(:Conceito)` por `owl:ObjectProperty` e por par domínio/alcance, inversas incluídas (o mesmo conjunto do grafo da página), com `nome`, `rotulo`, `definicao`, `inversa`, `publicada_nos_dados` e, havendo contrato, `multiplicidade`; a inversa de um contrato tem `inversa_de` e a multiplicidade lida ao contrário. Por terem tipos diferentes dos dados, `db.schema.visualization` desenha só os pares com aresta de dado. `Conceito` e `Termo` têm `name` igual a `nome`. Os dados não se ligam ao `Conceito` por aresta, só pelo label.
- **Camada `Termo`:** um nó `:Termo` por termo do `content.yml` cuja classe é um `Conceito`, com `nome`, `definicao`, `sinonimos`, `unidade`, `grao`, `aditividade`, `fonte` e `coluna` (com vários mappings, as listas `fontes` e `colunas`), `papel`, `_projeto` e `_carga`. Campos vazios ficam ausentes. Ligado por `(:Conceito)-[:TEM_TERMO]->(:Termo)`.
- **Esquema para o LLM:** texto Markdown com, por label, a definição, a chave, cada propriedade com o tipo e o termo, as relações que saem e as métricas; depois o glossário, as regras e as precedências; no topo, como consultar sem confundir as camadas. Gravado em `docs/publish/neo4j_schema.md` (no dry-run e na carga) e na propriedade `esquema` da marca: `MATCH (p:_AkmeProjeto {projeto: $projeto}) RETURN p.esquema`. É determinístico: mesma ontologia e mesmo plano dão o mesmo texto.
- **Esquema do banco:** uma restrição de unicidade de `_id` por label (`akme_uniq_<Label>`), uma composta para o `Conceito` (`akme_conceito_uniq_projeto_nome`), outra para o `Termo` (`akme_termo_uniq_projeto_nome`) e um índice por coluna-alvo de join (`akme_idx_<Label>__<coluna>_<hash>`). Sem a restrição, cada `MERGE` varreria o label inteiro.
- **Marca:** `(:_AkmeProjeto {projeto, name, esquema, carga_atual})`, gravada na primeira carga; `carga_atual` (a carga em andamento, para a trava contra carga concorrente), `name` (`Projeto <nome>`) e `esquema` são regravados a cada carga.
- **Tutorial do Browser:** `docs/publish/neo4j_guia.html`, gerado a cada `publish --target neo4j` (dry-run e carga), determinístico. Seis páginas só de navegação: o que tem aqui (classes com contagem), a ontologia (mapa com os nomes do TTL; setas virtuais com APOC), os dados (`db.schema.visualization` sem a camada de ontologia), explorar (um registro de cada classe e o que está ligado a ele), como navegar e perguntas em português pelo console da Aura. Servido pelo `akme review` em `http://127.0.0.1:8765/neo4j/guia` (CORS só nessa rota e só para as origens do Neo4j Browser); no Browser, `:guide http://127.0.0.1:8765/neo4j/guia`. Ver [Task 11](../exportacao-neo4j/task-11-tutorial.md).
- **Nomes reservados:** os labels `Conceito`, `Termo` e `_AkmeProjeto` e as propriedades `_id`, `_projeto`, `_carga` e `_descricao`. Uma classe ou coluna da origem com um desses nomes é problema no plano, e a carga é recusada.
- **Dados como parâmetro:** os valores vão sempre em `$rows`, `$projeto`, `$carga`, `$descricao` e `$esquema`. No texto das consultas só entram identificadores, entre crases.

## Como usar

**Uma vez por máquina:** subir o Neo4j, sem plugin.

```bash
set -a; . ./.env; set +a                         # AKME_NEO4J_URI, USER e PASSWORD
NEO4J_AUTH="neo4j/$AKME_NEO4J_PASSWORD" docker run -d --name akme-neo4j \
  --publish=127.0.0.1:7474:7474 --publish=127.0.0.1:7687:7687 \
  --env NEO4J_AUTH --volume=akme-neo4j-data:/data neo4j:2026.10.1
uv sync --inexact --extra dev --extra neo4j
```

**A cada exportação:**

```bash
uv run akme publish --target neo4j               # dry-run: gera docs/publish/neo4j.cypher
uv run akme publish --target neo4j --no-dry-run  # resumo, estado do banco, confirmação, carga, sincronização e conferência
```

Antes de confirmar, a CLI mostra o destino (sem credenciais), os nós e arestas previstos, por label `banco <n> -> origem <m>` e o aviso de que a carga apaga deste projeto o que não vier da origem. No fim da carga, ela diz onde ver o grafo:
- o endereço do Neo4j Browser: `http://localhost:7474` no Docker local; no Aura, `https://console.neo4j.io`;
- o usuário;
- consultas prontas com as classes e relações do projeto, mais `MATCH (n)-[r]->(m) WHERE NOT n:Conceito RETURN n, r, m LIMIT 300` (os dados) e `MATCH p = (:Conceito)-->(:Conceito) RETURN p` (a ontologia).

**Chave e tipos de cada tabela**, que a ontologia não traz, são decididos na etapa 5, só quando o alvo é o Neo4j:

1. `suggest_sources` monta um rascunho, sem LLM:
   - a chave vem dos contratos de relação ou de uma chave candidata do profile;
   - os tipos vêm do profile; inteiro com nome de identificador fica texto;
   - tabela sem classe vira exclusão.
2. O agente ajusta o que exige julgamento, como chave composta ou dinheiro como `float`, e propõe um `add_source` por tabela. Cada proposta é conferida contra a fonte inteira, lida em blocos: chave repetida, linha com colunas a mais ou a menos ou valor que não converte é recusado na hora. O que o payload sozinho já recusa (tipo desconhecido, `key` com `exclude`, chave ou join com tipo diferente de `string`) é recusado antes da leitura.
3. O humano decide na página de revisão, grupo "Exportação Neo4j", com "Aceitar tudo". Chave e tipos podem ser editados no cartão, e a edição é conferida de novo.
4. As decisões ficam na seção `sources` do `content.yml`, versionada com a ontologia:

```yaml
sources:
- {source: itens_pedido, key: [id_pedido, sku], types: {qt_itens: integer, vl_item: float}}
- {source: fireclaim, exclude: não aparece em nenhuma relação nem mapping da ontologia}
```

A tool MCP só roda em dry-run. Quem executa a carga é o humano, na CLI.

**Consulta de exemplo:**

```cypher
MATCH (:Pedido {id_pedido: '1001'})-[:contem]->(i:ItemPedido)-[:referencia]->(p:Produto)
RETURN p.sku, i.qt_itens
```

Para contar só dados, sem a camada da ontologia, filtre `NOT n:Conceito`. As arestas de dado têm o nome da relação (`contem`); entre os `Conceito`, a mesma relação é uma seta `RELACAO_ONTOLOGIA` com `nome: 'contem'`.

## O que o exportador faz com cada caso

| Caso | Resultado |
|---|---|
| Fonte sem classe, com mais de uma classe ou classe em mais de uma fonte | Recusa |
| Fonte sem chave; chave vazia ou repetida | Recusa |
| Valor que não converte sem perda, como `03/07/2026` em `date` | Recusa |
| Tipo, fonte ou coluna inexistente na configuração; chave ou join com tipo diferente de `string` | Recusa |
| Classe com nome reservado (`Conceito`, `_AkmeProjeto`) ou coluna `_id`, `_projeto` ou `_carga` | Recusa |
| Coluna de join ausente, ou relação em que nenhuma linha encontra alvo | Recusa |
| Banco vazio, ou só com este projeto | Aceita; com este projeto, atualiza e sincroniza |
| Banco com outro projeto, com mais de um projeto, com nós sem marca ou com nós que não vieram do akme | Recusa antes da confirmação, e de novo antes de gravar |
| Banco carregado pela exportação antiga (nós `Resource` ou `_GraphConfig` sem `_projeto`, ou a restrição antiga) | Recusa, com o comando de limpeza no guia; não há migração |
| Falha num lote, na ontologia ou na leitura da origem | Erro dizendo o lote e quantos já foram gravados; nada é apagado; repetir é seguro |
| Origem com outro número de linhas que o plano, durante a carga | Recusa antes de apagar |
| Linha de CSV com colunas a mais ou a menos que o cabeçalho, ou linha de XLSX com valor além do cabeçalho | Recusa, com a linha onde começa a primeira |
| Fonte com chave aprovada e nenhuma linha | Recusa: a sincronização apagaria o label inteiro |
| Classe, relação ou coluna de join com barra invertida seguida de `u` ou com caractere de controle | Recusa: o Cypher troca escapes unicode antes do parser, e um deles poderia fechar a crase do identificador |
| Neo4j anterior ao 5.23 | Recusa antes de gravar |
| Outra carga do mesmo projeto começou depois desta | A mais antiga para no bloco seguinte, sem gravar nem apagar mais nada; a mais nova regrava tudo e, na sua sincronização, apaga o que a antiga gravou antes e ela não regravou |
| Remoção prevista acima de 20% de algum label | A CLI pede o número total de remoções digitado; sem ele, nada é gravado |
| Classe de métrica com mais de um mapping de métrica | Avisa; no `Conceito` vale o primeiro |
| Parte das linhas de uma relação sem alvo | Avisa; essas linhas ficam sem aresta |
| Medida sem tipo numérico declarado | Avisa; carrega como texto |
| Banco diverge da previsão depois da carga | Erro; os dados continuam gravados |

As recusas de dados acontecem no dry-run, antes de conectar ao banco. As de destino acontecem antes de qualquer gravação.

**Proteção do destino:** a primeira carga num banco vazio grava o nó `(:_AkmeProjeto {projeto})`. Depois disso, o banco só aceita o mesmo projeto, porque a sincronização apaga o que é do projeto e não veio da origem. No Neo4j Community há um banco só, então outro projeto exige outro contêiner, ou limpar este.

**Sincronização:** apaga só nós com `_projeto` igual ao do projeto e `_carga` diferente da atual (com `DETACH DELETE`), e arestas com `_carga` antiga que saem de nós do projeto. Nunca apaga a marca do projeto nem nada de outro projeto, e só roda depois de todos os lotes, da releitura conferida e da ontologia. O resultado traz `removed` com os nós e as arestas apagados.

**Trava contra carga concorrente:** logo depois de conferir o destino, a carga grava `carga_atual` (a sua `_carga`, com milissegundos) na marca do projeto. Cada bloco de nós e de arestas, cada comando da ontologia (`Conceito`, `Termo`, `SUBCLASSE_DE`, `TEM_TERMO`, setas), a gravação do esquema e cada comando da sincronização começa por `MATCH (m:_AkmeProjeto {projeto: $projeto}) WHERE m.carga_atual = $carga`: se outra carga do projeto trocou a marca, o comando não acha nada e não grava nem apaga nada. Os comandos de gravação devolvem quantas linhas gravaram; zero faz o akme conferir a marca e parar. Assim, uma carga antiga que chega à ontologia depois da nova não recarimba `_carga` nem sobrescreve o `esquema` da nova. Antes de cada comando da sincronização, o akme confere a marca também em Python, só para dar a mensagem clara. Uma restrição `akme_projeto_uniq`, criada antes da marca, impede duas marcas do mesmo projeto. Fica uma janela de milissegundos: um bloco da carga antiga já em andamento quando a nova grava a marca ainda pode terminar (a sincronização da nova apaga o que ele gravou e ela não regravou). Testes de integração: `test_real_newer_load_mid_blocks_leaves_the_database_as_the_newer_one`, `test_real_newer_load_during_the_ontology_leaves_the_newer_one_intact` e `test_real_lock_inside_the_sync_command_deletes_nothing` (a checagem em Python contornada; o servidor não apaga nada).

**Nova tentativa em erro transitório:** cada bloco de nós e de arestas, cada comando da ontologia e cada restrição ou índice é gravado numa transação gerenciada (`execute_write`), que o driver repete em erro transitório. Repetir é seguro porque tudo é `MERGE`. Só os dois comandos da sincronização (`CALL ... IN TRANSACTIONS`) usam transação implícita, como o Neo4j exige.

**Conferência:** conta nós por label, arestas por padrão `(:Dominio)-[:relacao]->(:Alcance)`, `Conceito` e `Termo`. Não compara valores; `verification.ok` quer dizer que as contagens do banco batem com as da origem lida nesta carga.

## Por que este caminho

| Decisão | Motivo | Base |
|---|---|---|
| Neo4j como alvo | Pedido de Gabriel, da McKinsey | Conversa com o usuário |
| Cypher puro, sem plugin | O n10s não existe no Aura e é projeto Labs, sem aprovação para produção. Os outros dois motivos registrados na spec não eram do n10s (ver [a página da exportação](../exportacao-neo4j/index.md#por-que-mudar)) | Spec de 11/11/2026; pesquisa de 12/11/2026; decisão de Mateus |
| Ontologia como `Conceito`, com setas de mesmo nome das relações de dados | Quem abre o Browser lê conceitos como nós e relações como setas, sem escrever Cypher | Pedido do colega; decisão de Mateus |
| Leitura em blocos nos quatro adapters, sem teto de linhas | O `olist_order_items_dataset` tem 112.650 linhas | Teste do Olist; decisão de Mateus |
| Restrição única por label antes do `MERGE` | Sem ela, cada `MERGE` varre o label inteiro | Teste descartável de 11/11/2026 |
| Sincronizar a cada carga | As contagens do banco batem com as da origem lida nesta carga, inclusive linhas apagadas e relações que saíram. A conferência só conta; a comparação de valores existe só na amostra da demo (`examples/local_demo/amostra_valores.py`) | Decisão de Mateus |
| Chave e tipo decididos na etapa 5, com sugestão automática | Identidade estável, tipo que não depende dos dados, nada escrito à mão, decisão versionada | Testes automatizados; demo e `teste_acme` |
| Dinheiro como `float` | O Neo4j não tem tipo decimal; não serve para uso contábil | Decisão do usuário |
| Carga só pelo humano, na CLI | A carga altera o banco do cliente | `tests/test_server_publish_guard.py` |

## Provas

**Testes de integração com Neo4j real:** `scripts/test-neo4j.sh` sobe um `neo4j:2026.10.1` descartável em `127.0.0.1`, com senha aleatória num arquivo `chmod 600` que nunca é impresso, roda `tests/test_neo4j_integration.py` e remove o contêiner e o volume no fim. Última execução: 12/11/2026, depois do `/code-review`, 19 de 19 passaram (inclusive falha no meio seguida de nova carga, duas cargas intercaladas, CSV malformado e label com crase ou com escape unicode). Sem o script (ou sem as variáveis `AKME_NEO4J_TEST_*`), esses testes são pulados.

Aceitação real de 12/11/2026 (Task 9), num Mac com Apple M5 e 24 GB, macOS 26.3.1, Docker 29.2.0, Neo4j 2026.10.1 Community descartável, Python 3.12.13 e driver `neo4j` 6.4.1. Detalhes, comandos e o que cada passo prova em [task-9-aceitacao.md](../exportacao-neo4j/task-9-aceitacao.md).

**Demo, banco vazio, duas cargas:**

| Conferência | Resultado |
|---|---|
| 1ª carga | `verification.ok`, 7 lotes, `removed` 0/0, banco `vazio` |
| 2ª carga | `verification.ok`, `removed` 0/0, banco `projeto local_demo, sera atualizado` |
| `verificar_neo4j.py` | 45 de 45 OK, 216 células, saída 0 |
| Amostra de valores (5a) | 43 linhas, 213 células preenchidas, 0 divergências |
| Perguntas do gabarito (5b) | 11 de 11 batem (`test_real_competency_questions`) |

**Olist completo**, numa cópia temporária com três correções só na cópia (mapping de `categoria_produto`, `U+FEFF` no contrato `pertenceACategoria` e o `add_source` da tabela de tradução; ver a página da Task 9). Sem as correções, o dry-run recusa com 2 problemas, como esperado.

| Label | Esperado (linhas do CSV) | Plano | Banco |
|---|---|---|---|
| `Pedido` | 99.441 | 99.441 | 99.441 |
| `ItemPedido` | 112.650 | 112.650 | 112.650 |
| `Produto` | 32.951 | 32.951 | 32.951 |
| `Vendedor` | 3.095 | 3.095 | 3.095 |
| `Cliente` | 99.441 | 99.441 | 99.441 |
| `Avaliacao` | 99.224 | 99.224 | 99.224 |
| `CategoriaProduto` | 71 | 71 | 71 |

O CSV de avaliações tem 104.720 linhas físicas porque há comentários com quebra de linha; são 99.224 registros, e a chave aprovada é o par (`review_id`, `order_id`), único nos 99.224.

| Aresta | Esperado (join nos CSVs) | Plano | Banco |
|---|---|---|---|
| `contemItem` | 112.650 | 112.650 | 112.650 |
| `vendidoPor` | 112.650 | 112.650 | 112.650 |
| `referenteAoProduto` | 112.650 | 112.650 | 112.650 |
| `feitoPorCliente` | 99.441 | 99.441 | 99.441 |
| `refereSeAoPedido` | 99.224 | 99.224 | 99.224 |
| `pertenceACategoria` | 32.328 | 32.328 | 32.328 |

`pertenceACategoria` tem 32.328 e não 32.951: 610 produtos não têm categoria e 13 têm categoria sem tradução (`pc_gamer` e `portateis_cozinha_e_preparadores_de_alimentos`); o dry-run avisa os 13. São 18 `Conceito`, uma `_carga` e 446.892 nós no banco (446.873 de dados, 18 conceitos e a marca).

| Medida, Olist | Tempo | Memória máxima (RSS) |
|---|---|---|
| Dry-run (lê 446.873 linhas) | 2,2 s | 144 MB |
| 1ª carga, banco vazio | 31,4 s | 224 MB |
| 2ª carga, com sincronização | 29,7 s | 212 MB |
| Amostra de valores (5a) | 2,7 s | 160 MB |

Medido com `/usr/bin/time -l`. O contêiner do Neo4j ficou com 1,193 GiB de memória depois das cargas (`docker stats`).

**Sincronização no Olist:** 10 avaliações apagadas do CSV da cópia e carga de novo: `removed` = 10 nós e 10 arestas `refereSeAoPedido`, `verification.ok`, 99.214 avaliações no banco, nenhuma das 10 restante.

**Banco da exportação antiga:** contêiner descartável com o n10s, carregado pela versão `ec40d71` (59 nós, 59 arestas, restrição `n10s_unique_uri`). A CLI nova parou antes da confirmação com `erro: banco carregado pela exportacao antiga (n10s); limpe-o com o comando do guia. Nada foi gravado` e saída 1. Contagens, restrições e índices iguais antes e depois. Com o comando de limpeza do guia, a carga seguinte achou `banco: vazio` e o verificador terminou com `RESULTADO: todas as verificacoes passaram`.

**Postgres 16 real:** `olist_order_items_dataset` carregada com `COPY` (112.650 linhas); `tests/test_adapters_iter_rows.py` 9 de 9 com `AKME_PG_TEST_DSN`; `iter_rows(batch=5000)` leu 112.650 linhas em 23 blocos, em 0,28 s, pelo cursor do lado do servidor; o `scan_source` com a chave (`order_id`, `order_item_id`) achou 0 repetidas e 0 valores inválidos em `price` e `freight_value`.

**Fidelidade de valores (5a)**, `examples/local_demo/amostra_valores.py <akme.yml> --n 200 --seed 42`: até 200 linhas por fonte, sorteadas da fonte inteira, comparadas célula a célula com valor e tipo exatos contra a conversão da carga (`convert` e `node_id`) aplicada à origem. A correção do `convert` em si é coberta por `tests/test_neo4j_values.py`.

| Projeto | Linhas | Células | Divergências |
|---|---|---|---|
| Demo | 43 | 213 | 0 |
| Olist | 1.271 | 7.838 | 0 |

As datas voltam do driver como `neo4j.time.Date` e são comparadas depois de `to_native()` (`datetime.date`). No Olist não há coluna `date` (as datas têm hora e ficaram texto na etapa 5); as datas são exercitadas na demo. O script foi conferido com o banco adulterado de propósito (tipo trocado, valor alterado e propriedade a mais): achou as 3 divergências.

**Perguntas de competência (5b):**

- **Demo:** as 11 respostas do `gabarito.json` (`direct_answers`, `measures`, `traps` e `keys_unique`), com as consultas em `examples/local_demo/perguntas_neo4j.cypher`, batem no grafo. As perguntas CQ-002 e CQ-003 de `examples/local_demo/questions.yml` não têm valor no oráculo: a CQ-002 depende de uma data de referência ("últimos 90 dias") que o oráculo não fixa, e a CQ-003 (ticket médio por categoria) não foi calculada pelo `oracle.py`.
- **Olist**, as três perguntas reservadas de `validation/questions.yml`, respondidas por Cypher no grafo carregado:

| Pergunta | Esperado | Grafo | Resultado |
|---|---|---|---|
| CQ-006, pior nota média por categoria | `moveis_escritorio` | `moveis_escritorio`, 3,62 em 1.263 pedidos | bate |
| CQ-007, pior nota média por vendedor | `1ca7077d890b907f89be8c954a02686a` | o mesmo, 2,33 em 114 pedidos | bate |
| CQ-008, atraso do pedido `88c588c1...` | atrasou 10 dias (entregue em 2017-12-22, estimado para 2017-12-12) | `delivered`, 2017-12-22, 2017-12-12, 10 dias | bate |

As consultas aplicam as regras C-001 (uma avaliação por pedido, a mais recente), C-002 (cada pedido uma vez por grupo) e C-003 (atraso só para `delivered` com data de entrega). CQ-006 e CQ-007 usam o corte de 30 ou mais pedidos avaliados, registrado no changelog quando as respostas foram reservadas; sem o corte, a pior categoria seria `seguros_e_servicos`, com 2 pedidos.

Testes automatizados que já existem: `tests/test_neo4j_values.py`, `tests/test_neo4j_plan.py`, `tests/test_neo4j_onto.py`, `tests/test_neo4j_load.py` (sessão falsa), `tests/test_neo4j_cli.py` e `tests/test_neo4j_integration.py` (banco real, pulado sem `AKME_NEO4J_TEST_*`; rode com `scripts/test-neo4j.sh`). Para a demo, `examples/local_demo/verificar_neo4j.py` confere o banco contra os CSVs e o gabarito.

## O que falta

- Corrigir na ontologia do Olist da raiz as três pendências que a aceitação corrigiu só na cópia (ver a página da Task 9).
- Servidor MCP do Neo4j e perguntas de competência como teste (o esquema para o LLM foi feito na Task 10).
- Exigir definição em `add_relation` e checar relações sem definição no validador; hoje a `_descricao` das arestas costuma ser só o rótulo.
- Snowflake e Databricks com leitura em blocos testada só com cursor falso.
- Decidir o destino do alvo `rdf`, cujo YARRRML perde relações e tipos.
- Tipo `datetime` na etapa 5: hoje carimbos de data e hora ficam como texto, e vírgula decimal é recusada para `float` (muda os tipos da etapa 5).
- Opção para desligar `_descricao` nos dados, e decidir se a aresta sem definição deve receber o rótulo ou ficar sem `_descricao` (decisões de Mateus).
- Unificar como CSV e XLSX aparam espaços (hoje só a planilha apara).
- Legenda `name` decidida por fonte na etapa 5; hoje é a regra automática ou a coluna `name` da origem.

**Fora do Neo4j, só anotado:**
- A tool MCP ainda executa `snowflake`, `databricks` e `rdf` sem confirmação.
- `connect` ignora o `.r2rml` do `teste_acme`.

## Fontes

1. Neo4j Operations Manual, [Docker: Introduction](https://neo4j.com/docs/operations-manual/current/docker/introduction/), lida em 05/11/2026.
2. PyPI, [neo4j](https://pypi.org/project/neo4j/), versão 6.4.1.
3. Pesquisa completa: `reports/Exportar ontologia para Neo4j.md`; usos do grafo: `docs/neo4j/usos-do-grafo.md`.
