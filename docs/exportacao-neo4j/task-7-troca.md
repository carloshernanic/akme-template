# Task 7: troca do exportador e remoção do n10s

Esta tarefa liga o exportador em Cypher puro (`akme/tools/neo4j_load.py`, Tasks 3 a 6) ao comando `akme publish --target neo4j` e à tool MCP `publish`, e apaga o exportador antigo (RDF + plugin n10s).

## O que foi ligado

- **`akme/tools/publish.py`:** o alvo `neo4j` importa `publish_neo4j` de `neo4j_load`. O `--release` continua subindo a versão só depois de uma carga sem problemas.
- **CLI (`akme/cli.py`, `_publish_neo4j`):** troca de módulo e passa a ler o estado do banco com `destination_state(project, plan)` para mostrar, por label, `banco <n> -> origem <m>` e o aviso de sincronização.
- **Tool MCP `publish`:** usa o mesmo caminho e **continua só dry-run para o neo4j** (`akme/server.py` não mudou; `tests/test_server_publish_guard.py` passa sem alteração). O motivo é o de antes: a carga altera o banco do cliente e só o humano, na CLI, confirma.

## O que a pessoa vê agora, antes de confirmar

Ordem na CLI: destino, resumo da origem, estado do banco comparado por label, avisos, veredito sobre o banco e só então a pergunta. Se o plano tem problemas, a CLI mostra os problemas e sai com erro sem nem conectar no banco. Se o banco é de outro projeto, tem nós alheios ou é legado do n10s, a CLI recusa sem perguntar. Credenciais nunca aparecem. Depois da carga, mostra como ver o grafo; se o banco divergir do previsto, sai com erro.

Saída real em um banco descartável que já tinha a demo carregada (a resposta foi `n`, então nada foi gravado):

```text
destino: bolt://127.0.0.1:27687
linhas: 43 em 7 lote(s) de dados, mais a ontologia
nos previstos:
  Cliente: 8
  ItemPedido: 17
  Pedido: 10
  Produto: 8
arestas previstas:
  contem: 17
  pertenceA: 10
  referencia: 17
no banco hoje, deste projeto:
  Cliente: banco 8 -> origem 8
  ItemPedido: banco 17 -> origem 17
  Pedido: banco 10 -> origem 10
  Produto: banco 8 -> origem 8
avisos:
  a carga apaga deste projeto o que nao vier da origem nesta carga
banco: projeto demo, sera atualizado
Executar no alvo neo4j? Esta acao altera a plataforma do cliente. [y/N]: n
Aborted.
```

## O que foi removido

- `akme/tools/n10s.py` (exportador RDF + n10s);
- `tests/test_publish_neo4j.py` (674 linhas, testes do exportador antigo);
- o artefato `docs/publish/neo4j.nt`, que não é mais gerado (agora é `neo4j.cypher`);
- a dependência do plugin n10s: o exportador novo só usa Cypher.

Tudo continua no histórico do git. O texto "n10s" sobrou apenas na detecção de banco legado (Task 6), que recusa um banco carregado pela exportação antiga.

Em `tests/test_neo4j_plan.py` saiu `test_shared_names_live_in_the_plan`, que só conferia se o `n10s.py` reaproveitava as funções do plano; sem o módulo, o teste perdeu o objeto.

## Testes portados

| Teste antigo (`tests/test_publish_neo4j.py`) | Onde está agora |
| --- | --- |
| `test_no_dry_run_requires_connection_settings` | `tests/test_neo4j_cli.py` |
| `test_no_dry_run_without_driver_explains_the_extra` | `tests/test_neo4j_cli.py` |
| `test_cli_shows_destination_and_summary_before_confirming` | `tests/test_neo4j_cli.py` (agora com `banco <n> -> origem <m>`) |
| `test_cli_never_prints_credentials` | `tests/test_neo4j_cli.py` |
| `test_cli_refuses_before_confirming_when_there_are_problems` | `tests/test_neo4j_cli.py` |
| `test_cli_exits_with_error_on_divergence` | `tests/test_neo4j_cli.py` |
| `test_cli_refuses_other_project_without_asking` | `tests/test_neo4j_cli.py` |
| `test_load_rechecks_destination_before_writing` | `tests/test_neo4j_cli.py` (e `tests/test_neo4j_load.py`) |
| `test_viewing_lines_point_to_the_browser` | `tests/test_neo4j_cli.py` (e `tests/test_neo4j_load.py`) |
| `test_cli_tells_where_to_see_the_graph_after_loading` | `tests/test_neo4j_cli.py` |
| `test_release_only_bumps_after_success` | `tests/test_neo4j_cli.py` |
| `test_dry_run_writes_schema_data_and_relationships`, `test_demo_has_no_problems`, `test_demo_has_no_warnings`, chaves, tipos e problemas do plano | cobertos com outro nome em `tests/test_neo4j_plan.py` e `tests/test_neo4j_values.py` (Tasks 2 e 3) |
| `test_load_reports_verification_when_database_matches`, `test_load_fails_when_edges_were_not_created`, `test_load_fails_when_database_has_extra_nodes`, `test_dry_run_does_not_touch_the_database` | cobertos com outro nome em `tests/test_neo4j_load.py` (`test_publish_loads_then_verifies`, `test_publish_fails_on_divergence`, `test_dry_run_writes_cypher_artifact_and_does_not_connect`) |
| `test_load_prepares_n10s_and_imports_ontology_then_data`, `test_load_refuses_server_without_n10s`, `test_load_accepts_graph_already_configured_by_akme`, `test_load_refuses_graph_configured_with_other_names` | obsoletos: testavam o preparo do plugin (`n10s.graphconfig.init`, procedimentos `n10s.*`), que não existe mais |
| `test_import_that_does_not_load_everything_is_an_error`, `test_large_data_is_split_in_batches`, falhas parciais e de conexão | cobertos com outro nome em `tests/test_neo4j_load.py` (lote que falha, conexão, blocos de 5.000 linhas) |
| `test_key_values_are_encoded_in_the_iri`, `test_rdf_literal_*` | obsoletos: codificavam a chave na IRI do RDF; a identidade agora é `node_id` (`tests/test_neo4j_values.py`) |
| `test_truncated_source_is_refused` | obsoleto: a verificação de truncamento do arquivo RDF não existe; a Task 3 lê a fonte inteira em blocos, sem teto de linhas |

Mudança de eficiência: a CLI monta o plano **uma vez** (`build_plan`) e o reaproveita na prévia, em `destination_state` e na carga (`publish_neo4j(..., plan=...)`), em vez de três leituras completas da origem. A carga ainda lê as fontes para gravar e confere se a origem mudou desde o plano. A tool MCP segue montando o próprio plano. `test_cli_builds_the_plan_once` vigia isso.

Testes novos: `test_cli_refuses_alien_and_legacy_destinations_without_asking` (banco com nós sem marca e banco legado) e `test_package_has_no_n10s` (nenhum arquivo `n10s.py` em `akme/` e nenhum `import` de n10s).

## Testes e TDD

`tests/test_neo4j_cli.py` troca a gravação e a conferência por dublês (`load`, `verify`, `destination_state`), então a CLI é exercitada sem banco. Suíte inteira (`uv run pytest -q`): 315 passaram, 10 foram puladas e 2 falharam. Uma falha é a já conhecida `test_optional_adapters_fail_clearly`; a outra era um erro de precedência no meu `test_package_has_no_n10s` (`ROOT / "akme".rglob`), corrigido depois e confirmado passando isolado. Os testes de CLI, plano e do guarda do servidor juntos: 63 passaram antes da correção, mais o teste corrigido.

TDD: os testes da CLI foram escritos junto com a troca de módulo (a mudança na CLI era pequena); o equivalente ao RED é que, com o `n10s.py` presente, `test_package_has_no_n10s` falha e os testes de CLI importam `neo4j_load`, não o módulo antigo.

## Revisão

Revisão aprovada, sem críticos nem importantes. Os 58 testes antigos foram conferidos um a um: portados com o mesmo nome, cobertos com outro nome ou obsoletos junto com o n10s.

Corrigido depois da revisão:

- plano montado uma vez só na CLI (antes eram três leituras completas da origem);
- dublês compartilhados (`_FakeSession`, `PASSWORD`, `CARGA`, fixture `fake`) movidos para `tests/neo4j_fakes.py`, registrados em `tests/conftest.py`, sem um teste importar outro;
- três testes de cobertura em `tests/test_neo4j_load.py` (coluna sem tipo declarado fica texto, `"00123"` não perde o zero, falha de conexão do driver vira erro claro sem credenciais), mais a identidade do nó independente da ordem das linhas.

Nota: o RED não foi capturado separadamente nesta task.
