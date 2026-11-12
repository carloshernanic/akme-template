# Exportação para o Neo4j em Cypher

Esta página resume a mudança em andamento na branch `feat/exportacao-neo4j-cypher`. O design completo está em `docs/superpowers/specs/2026-11-11-exportacao-neo4j-cypher-design.md`.

## Por que mudar

Hoje o akme gera RDF e o plugin n10s carrega no Neo4j. Apareceram três problemas:

- **Relações viram nós.** O `n10s.onto.import` grava cada relação como um nó `Relationship`. Quem abre o grafo vê relações como entidades, e não como setas.
- **Teto de 100 mil linhas.** O exportador lê cada tabela inteira em memória e recusa tabelas maiores. O `olist_order_items_dataset` tem 112.650 linhas e não carrega.
- **O n10s não existe no Aura.** Depender do plugin limita onde o grafo pode rodar.

## O novo fluxo

Tudo em Cypher puro, pelo driver oficial, sem plugin:

1. **Plano (dry-run):** lê cada fonte em blocos, confere chave, tipos e joins, conta nós e arestas esperados e lista problemas e avisos. Não conecta no banco.
2. **Confirmação:** a pessoa lê o resumo e confirma na CLI. A carga continua só pelo humano.
3. **Carga:** confere o destino, cria restrições e índices, grava nós, arestas e a camada de ontologia, tudo marcado com a `_carga` da rodada.
4. **Sincronização:** apaga o que é do projeto e tem `_carga` antiga.
5. **Conferência:** conta no banco por label e por padrão `(:Dominio)-[:relacao]->(:Alcance)`.

## O modelo no grafo

- **Nós de dado:** o label é a classe (ex.: `Pedido`). Propriedades: uma por coluna preenchida, mais `_id` (valores da chave), `_projeto` e `_carga`.
- **Arestas de dado:** o tipo é o nome da relação (ex.: `pertenceA`), do domínio para o alcance.
- **Camada `Conceito`:** um nó `:Conceito` por classe da ontologia, com `(:Conceito)-[:SUBCLASSE_DE]->(:Conceito)` e uma seta por relação, com o mesmo nome da relação de dados.
- **Restrição:** `_id` único por label, necessária para o `MERGE` ser viável.

## As 9 tarefas

| # | Tarefa | Status |
|---|--------|--------|
| 1 | Leitura em blocos nos adapters e BOM | concluída (aguardando commit) |
| 2 | Conversão de valores e identidade do nó | concluída (aguardando commit) |
| 3 | Plano da carga (dry-run) lendo em blocos | concluída (aguardando commit) |
| 4 | Camada de ontologia (Conceito) | concluída (aguardando commit) |
| 5 | Validação do `add_source` lendo a fonte inteira | concluída (aguardando commit) |
| 6 | Carga, sincronização e conferência | concluída (aguardando commit) |
| 7 | Ligar o caminho novo e remover o n10s | concluída (aguardando commit) |
| 8 | Documentação, guia e verificador da demo | a fazer |
| 9 | Aceitação real (demo, Olist e Postgres) | a fazer |

Veja a [Task 1](task-1-adapters.md), a [Task 2](task-2-valores.md), a [Task 3](task-3-plano.md), a [Task 4](task-4-ontologia.md), a [Task 5](task-5-add-source.md) a [Task 6](task-6-carga.md) e a [Task 7](task-7-troca.md) para o que já mudou.
