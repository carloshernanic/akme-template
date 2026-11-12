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
   conta nós e arestas esperados; lista problemas e avisos; grava docs/publish/neo4j.cypher
        ↓
humano lê o resumo (com o que o banco tem hoje, por label) e confirma na CLI
        ↓
2. carga: confere o destino; cria restrições e índices; marca o projeto;
   grava nós em lotes de 5.000; grava arestas (o banco resolve o join pelo índice);
   grava a camada Conceito; tudo com a _carga desta rodada
        ↓
3. sincronização: apaga nós e arestas do projeto com _carga antiga
        ↓
4. conferência: conta no banco por label e por padrão (:Dominio)-[:relacao]->(:Alcance)
```

O código está em `akme/tools/`:

| Módulo | Papel |
|---|---|
| `neo4j_values.py` | Converte cada célula para o tipo aprovado e calcula a identidade `_id` do nó |
| `neo4j_plan.py` | Plano da carga (dry-run): lê em blocos, confere e conta, sem guardar as linhas |
| `neo4j_onto.py` | Camada `Conceito`: comandos da ontologia, com parâmetros |
| `neo4j_load.py` | Proteção do destino, carga, sincronização, conferência, artefato e textos da CLI |

**O modelo no grafo:**

- **Nó de dado:** o label é a classe (ex.: `Pedido`). Uma propriedade por coluna preenchida, com o nome original e o tipo da etapa 5, mais `_id` (valores da chave, como `1001/CIM-50`), `_projeto` e `_carga`.
- **Aresta de dado:** o tipo é o nome da relação (ex.: `pertenceA`), do domínio para o alcance. Só a propriedade `_carga`.
- **Camada `Conceito`:** um nó `:Conceito` por classe do `schema.ttl`, com `nome`, `rotulo`, `definicao` e `iri` (métricas acrescentam expressão, unidade, grão e aditividade). `(:Conceito)-[:SUBCLASSE_DE]->(:Conceito)` e uma seta por contrato de relação, com o mesmo nome da relação de dados e as propriedades `rotulo`, `definicao`, `multiplicidade`, `inversa` e `publicada`. As duas camadas não se ligam.
- **Esquema:** uma restrição de unicidade de `_id` por label (`akme_uniq_<Label>`), uma composta para o `Conceito` (`akme_conceito_uniq_projeto_nome`) e um índice por coluna-alvo de join (`akme_idx_<Label>__<coluna>_<hash>`). Sem a restrição, cada `MERGE` varreria o label inteiro.
- **Marca:** `(:_AkmeProjeto {projeto})`, gravada na primeira carga.
- **Dados como parâmetro:** os valores vão sempre em `$rows`, `$projeto` e `$carga`. No texto das consultas só entram identificadores, entre crases.

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
2. O agente ajusta o que exige julgamento, como chave composta ou dinheiro como `float`, e propõe um `add_source` por tabela. Cada proposta é conferida contra a fonte inteira, lida em blocos: chave repetida ou valor que não converte é recusado na hora.
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

Para contar só dados, sem a camada da ontologia, filtre `NOT n:Conceito`.

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
| Parte das linhas de uma relação sem alvo | Avisa; essas linhas ficam sem aresta |
| Medida sem tipo numérico declarado | Avisa; carrega como texto |
| Banco diverge da previsão depois da carga | Erro; os dados continuam gravados |

As recusas de dados acontecem no dry-run, antes de conectar ao banco. As de destino acontecem antes de qualquer gravação.

**Proteção do destino:** a primeira carga num banco vazio grava o nó `(:_AkmeProjeto {projeto})`. Depois disso, o banco só aceita o mesmo projeto, porque a sincronização apaga o que é do projeto e não veio da origem. No Neo4j Community há um banco só, então outro projeto exige outro contêiner, ou limpar este.

**Sincronização:** apaga só nós com `_projeto` igual ao do projeto e `_carga` diferente da atual (com `DETACH DELETE`), e arestas com `_carga` antiga que saem de nós do projeto. Nunca apaga a marca do projeto nem nada de outro projeto, e só roda depois de todos os lotes, da releitura conferida e da ontologia. O resultado traz `removed` com os nós e as arestas apagados.

## Por que este caminho

| Decisão | Motivo | Base |
|---|---|---|
| Neo4j como alvo | Pedido de Gabriel, da McKinsey | Conversa com o usuário |
| Cypher puro, sem plugin | O plugin anterior gravava cada relação como nó; tinha teto de 100 mil linhas; não existe no Aura | Spec de 11/11/2026; decisão de Mateus |
| Ontologia como `Conceito`, com setas de mesmo nome das relações de dados | Quem abre o Browser lê conceitos como nós e relações como setas, sem escrever Cypher | Pedido do colega; decisão de Mateus |
| Leitura em blocos nos quatro adapters, sem teto de linhas | O `olist_order_items_dataset` tem 112.650 linhas | Teste do Olist; decisão de Mateus |
| Restrição única por label antes do `MERGE` | Sem ela, cada `MERGE` varre o label inteiro | Teste descartável de 11/11/2026 |
| Sincronizar a cada carga | O banco fica igual à origem, inclusive linhas apagadas e relações que saíram | Decisão de Mateus |
| Chave e tipo decididos na etapa 5, com sugestão automática | Identidade estável, tipo que não depende dos dados, nada escrito à mão, decisão versionada | Testes automatizados; demo e `teste_acme` |
| Dinheiro como `float` | O Neo4j não tem tipo decimal; não serve para uso contábil | Decisão do usuário |
| Carga só pelo humano, na CLI | A carga altera o banco do cliente | `tests/test_server_publish_guard.py` |

## Provas

a preencher na Task 9

Testes automatizados que já existem: `tests/test_neo4j_values.py`, `tests/test_neo4j_plan.py`, `tests/test_neo4j_onto.py`, `tests/test_neo4j_load.py` (sessão falsa), `tests/test_neo4j_cli.py` e `tests/test_neo4j_integration.py` (banco real, pulado sem `AKME_NEO4J_TEST_*`). Para a demo, `examples/local_demo/verificar_neo4j.py` confere o banco contra os CSVs e o gabarito.

## O que falta

- Aceitação real com o Olist inteiro e com Postgres (Task 9).
- Esquema para o LLM, servidor MCP do Neo4j e perguntas de competência como teste.
- Snowflake e Databricks com leitura em blocos testada só com cursor falso.
- Decidir o destino do alvo `rdf`, cujo YARRRML perde relações e tipos.

**Fora do Neo4j, só anotado:**
- A tool MCP ainda executa `snowflake`, `databricks` e `rdf` sem confirmação.
- `test_optional_adapters_fail_clearly` falha com o `psycopg` instalado.
- `connect` ignora o `.r2rml` do `teste_acme`.

## Fontes

1. Neo4j Operations Manual, [Docker: Introduction](https://neo4j.com/docs/operations-manual/current/docker/introduction/), lida em 05/11/2026.
2. PyPI, [neo4j](https://pypi.org/project/neo4j/), versão 6.4.1.
3. Pesquisa completa: `reports/Exportar ontologia para Neo4j.md`; usos do grafo: `docs/neo4j/usos-do-grafo.md`.
