# Exportação para o Neo4j em Cypher

Esta página resume a mudança em andamento na branch `feat/exportacao-neo4j-cypher`. O desenho original foi discutido com Mateus em 11/11/2026; estas páginas registram o que foi decidido e feito em cada tarefa.

## Por que mudar

Até a Task 7, o akme gerava RDF e o plugin n10s carregava no Neo4j. Foram registrados três motivos. A [pesquisa de 12/11/2026](pesquisa-camada-semantica.md) (seção 4) mostrou que só o do Aura se sustenta por inteiro. O teto de 100 mil linhas era do nosso código, e relação virar nó era um problema do `onto.import`, que tinha meio-termo:

- **O n10s não existe no Aura.** Depender do plugin limita onde o grafo pode rodar, e o n10s é projeto Labs, sem aprovação para produção. É o motivo que se confirma, e o mais forte.
- **Relações viram nós.** Era um problema do `n10s.onto.import`, que grava cada relação como um nó `Relationship`. Dava para manter o n10s só para os dados e gerar a ontologia em Cypher nosso.
- **Teto de 100 mil linhas.** O teto era do nosso código (`MAX_ROWS` no `n10s.py`), não do n10s. O `olist_order_items_dataset`, com 112.650 linhas, não carregava por causa dele.

O que a troca perdeu de fato foi o único gerador de RDF fiel (chaves, tipos e relações), que estava no `n10s.py`. Para quem consome o grafo, isso pesa pouco; para interoperabilidade RDF, é uma perda real.

## O novo fluxo

Tudo em Cypher puro, pelo driver oficial, sem plugin:

1. **Plano (dry-run):** lê cada fonte em blocos, confere chave, tipos e joins, conta nós e arestas esperados e lista problemas e avisos. Não conecta no banco.
2. **Confirmação:** a pessoa lê o resumo e confirma na CLI. A carga continua só pelo humano.
3. **Carga:** confere o destino, cria restrições e índices, grava nós, arestas e a camada de ontologia, tudo marcado com a `_carga` da rodada.
4. **Sincronização:** apaga o que é do projeto e tem `_carga` antiga.
5. **Conferência:** conta no banco por label e por padrão `(:Dominio)-[:relacao]->(:Alcance)`.

## O modelo no grafo

- **Nós de dado:** o label é a classe (ex.: `Pedido`). Propriedades: uma por coluna preenchida, mais `_id` (valores da chave), `_projeto`, `_carga`, `_descricao` (a definição da classe) e `name` (a legenda no Browser, desde a Task 11).
- **Arestas de dado:** o tipo é o nome exato da relação no `schema.ttl` (ex.: `pertenceA`), do domínio para o alcance, com `_carga` e `_descricao` (a definição da relação ou, sem ela, o rótulo).
- **Camada `Conceito`:** espelho do `schema.ttl`, como o grafo da página do akme: um nó `:Conceito` por classe, `(:Conceito)-[:SUBCLASSE_DE]->(:Conceito)` por subclasse e uma seta `RELACAO_ONTOLOGIA` por relação (inversas incluídas), com o nome em `nome` e `publicada_nos_dados` (desde a Task 11).
- **Termos:** um nó `:Termo` por termo do `content.yml`, ligado por `(:Conceito)-[:TEM_TERMO]->(:Termo)`.
- **Esquema para o LLM:** em `docs/publish/neo4j_schema.md` e na propriedade `esquema` da marca `_AkmeProjeto`.
- **Tutorial do projeto no Browser:** em `docs/publish/neo4j_guia.html`, seis páginas só de navegação, servido pelo `akme review` em `/neo4j/guia`. As perguntas de competência saíram do tutorial e do akme por decisão de Mateus em 12/11/2026; perguntas em português ficam com o console da Aura.
- **Restrição:** `_id` único por label, necessária para o `MERGE` ser viável.

## As tarefas

| # | Tarefa | Status |
|---|--------|--------|
| 1 | Leitura em blocos nos adapters e BOM | concluída (aguardando commit) |
| 2 | Conversão de valores e identidade do nó | concluída (aguardando commit) |
| 3 | Plano da carga (dry-run) lendo em blocos | concluída (aguardando commit) |
| 4 | Camada de ontologia (Conceito) | concluída (aguardando commit) |
| 5 | Validação do `add_source` lendo a fonte inteira | concluída (aguardando commit) |
| 6 | Carga, sincronização e conferência | concluída (aguardando commit) |
| 7 | Ligar o caminho novo e remover o n10s | concluída (aguardando commit) |
| 8 | Documentação, guia e verificador da demo | concluída (aguardando commit) |
| 9 | Aceitação real (demo, Olist e Postgres) | concluída (aguardando commit) |
| 10 | Camada semântica legível no grafo (`_descricao`, esquema para o LLM, termos) | concluída (aguardando commit) |
| 11 | Tutorial curto do projeto no Neo4j Browser (só navegação), camada `Conceito` espelho do TTL e legenda `name` | feita (escopo congelado em 12/11/2026) |

Veja a [Task 1](task-1-adapters.md), a [Task 2](task-2-valores.md), a [Task 3](task-3-plano.md), a [Task 4](task-4-ontologia.md), a [Task 5](task-5-add-source.md), a [Task 6](task-6-carga.md), a [Task 7](task-7-troca.md), a [Task 8](task-8-docs.md), a [Task 9](task-9-aceitacao.md), a [Task 10](task-10-semantica.md) e a [Task 11](task-11-tutorial.md) para o que já mudou.

Para o que o grafo novo permite fazer, com consultas medidas no Olist e a comparação com o formato antigo (inclusive o que piorou), veja [Uso real do grafo](uso-do-grafo.md).

Para onde guardar a descrição de cada entidade (no nó, em `Conceito` ou num esquema para o LLM), com custos medidos no Olist, e para a revisão da troca do n10s pelo Cypher, veja [Pesquisa: camada semântica no grafo](pesquisa-camada-semantica.md).

Para como apresentar o grafo a quem não sabe Cypher (Browser, guia do projeto, consultas salvas, Bloom pelo console da Aura, painéis) e para o protótipo testado no Olist, veja [Pesquisa: como ver o grafo](pesquisa-visualizacao.md).

## Correções da revisão final

A revisão final da branch, de 12/11/2026, apontou 0 problemas críticos, 9 importantes e 14 menores. Numa rodada única de correções, ficou assim.

**Corrigido, com teste:**

- **Linha com colunas a mais ou a menos (I1).** O adapter da pasta local conta essas linhas no CSV e no XLSX e guarda o número da primeira; o plano recusa com `N linha(s) de <fonte> com colunas a mais ou a menos; primeira: linha X`. Antes, a linha era ajustada em silêncio e os valores entravam deslocados.
- **Duas cargas ao mesmo tempo (I2).** A carga grava `carga_atual` na marca do projeto logo depois de conferir o destino (com uma restrição `akme_projeto_uniq` criada antes), e cada bloco de nós e de arestas e cada comando da sincronização só grava ou apaga se a marca ainda tiver esse valor: a condição está no próprio comando Cypher, provada em banco real; uma checagem em Python dá a mensagem clara. A carga mais antiga para no primeiro bloco barrado. Se trocou, para com `outra carga deste projeto comecou depois desta; nada foi apagado. Rode a carga de novo`. A `_carga` passou a ter milissegundos.
- **Origem que encolhe por engano (I3).** Fonte com chave aprovada e nenhuma linha é problema no plano. Na CLI, se a remoção prevista passar de 20% do que um label tem no banco, é preciso digitar o número total de remoções; sem isso, nada é gravado. O guia diz que o nome do projeto é a identidade do grafo.
- **Escape unicode em identificador (I4).** `name()` recusa identificador com barra invertida seguida de `u` ou com caractere de controle, e o plano transforma a recusa em problema. Um teste de integração confirma que um label com crase carrega certo e que um com o escape é recusado antes de conectar.
- **Nova tentativa em erro transitório (I7).** Blocos de nós e de arestas, comandos da ontologia, restrições, índices e a marca são gravados com `execute_write`; só a sincronização (`CALL ... IN TRANSACTIONS`) fica em `session.run`.
- **Testes com banco real (I9).** `scripts/test-neo4j.sh` sobe um Neo4j descartável, roda os testes de integração e remove o contêiner. Entraram quatro testes novos: falha no meio seguida de nova carga, duas cargas intercaladas, CSV malformado e identificador com escape. Última execução: 15 de 15.
- **Erros inesperados na CLI (M1, M10).** `UnicodeDecodeError`, `csv.Error` e erros do driver de banco viram uma linha `erro: <Tipo>: <mensagem>`, sem traceback e sem credencial. O erro do adapter durante a carga também cita o tipo da exceção.
- **Versão mínima (M2).** Antes de gravar, a carga lê `dbms.components()` e recusa Neo4j anterior ao 5.23.
- **Banco nomeado (M5).** `AKME_NEO4J_DATABASE`, opcional, vale para todas as sessões, inclusive nos scripts da demo (`verificar_neo4j.py` e `amostra_valores.py`).
- **Avisos do driver.** As conexões do akme desligam só a família `UNRECOGNIZED` de notificações (`notifications_disabled_classifications`), a do 01N52; avisos de depreciação e de desempenho continuam vindo, e o logger do processo não é alterado. Antes, num banco vazio, a carga imprimia três avisos longos (`01N52`, propriedade `_projeto` inexistente) no meio da confirmação.
- **Linha em branco no CSV.** É pulada, como fazem o módulo `csv` e o pandas, e não conta como linha malformada. Exceção, desde o `/code-review`: num CSV de uma coluna só, ela é um registro com valor vazio.
- **`_id` codificado (M9).** O esquema para o LLM avisa que `_id` usa percent-encoding e que, para filtrar, se usa a coluna original.
- **Versão em dry-run (M13).** `publish(..., dry_run=True, release=...)` não muda mais a versão no alvo `neo4j`.
- **Várias métricas por classe.** O plano avisa que, no `Conceito`, vale o primeiro mapping.
- **Itens do ledger.** `batch` menor ou igual a zero é recusado nos adapters e no plano; `test_optional_adapters_fail_clearly` simula a ausência dos pacotes opcionais e não conecta a serviço real. Para esse teste passar, o adapter do Databricks deixou de engolir a falta do pacote ao listar fontes.

**Corrigido, só no texto:**

- **I5.** "O banco fica igual à origem" virou "as contagens do banco batem com as da origem lida nesta carga"; o guia diz que a comparação de valores existe só na amostra da demo (`examples/local_demo/amostra_valores.py`).
- **I6.** A justificativa da troca em `docs/neo4j/exportacao.md` cita só o motivo que se sustenta (Aura; n10s é projeto Labs) e aponta para esta página.
- **M11.** O guia traz um só método e um só número de memória (o da Task 10).
- **M12.** A linha "Documentação das colunas" de [Uso real do grafo](uso-do-grafo.md) passou a refletir o estado depois da Task 10.
- **Ledger.** O guia explica que editar a origem entre a prévia e a carga muda o banco, mas não o resumo aprovado.

**Deixado como limite documentado (no guia, em "Limites conhecidos", ou em "O que falta"):**

- **I8.** Sem tipo `datetime`: carimbos ficam como texto e vírgula decimal é recusada para `float`. Mudaria os tipos da etapa 5.
- **M4.** A memória do plano cresce com o número de chaves; o guia dá a ordem de grandeza.
- **M6.** A sincronização e as consultas de estado varrem todos os nós.
- **M7 e M8.** Opção para desligar `_descricao` e o que fazer com a aresta sem definição: decisões de Mateus.
- **M14.** CSV e XLSX aparam espaços de forma diferente.
- **Task 11** (`name` em todo nó, guia do Browser; por decisões de Mateus em 12/11/2026, as arestas em UPPER_SNAKE foram revertidas, a camada `Conceito` virou espelho do TTL e as perguntas de competência saíram do tutorial e do akme): aprovada em 12/11/2026 e feita depois; ver [Task 11](task-11-tutorial.md).

### /code-review

O `/code-review` da árvore de trabalho (12/11/2026) apontou 10 achados. Todos foram corrigidos com teste:

- **Verificador da demo.** `examples/local_demo/verificar_neo4j.py` não esperava a restrição `akme_projeto_uniq` e falhava depois de toda carga boa. A lista agora sai ordenada, e um teste confere que ela é igual às restrições que a carga cria.
- **Trava na ontologia.** Os comandos de `Conceito`, `Termo`, `SUBCLASSE_DE`, `TEM_TERMO`, as setas e a gravação do esquema começam pela trava (`_LOCK`) e devolvem quantos gravaram. Uma carga antiga que chegasse à ontologia depois da nova recarimbava `_carga` e sobrescrevia `esquema`, e então a sincronização da nova apagava a ontologia. Agora o primeiro comando barrado para a carga com `outra carga deste projeto comecou depois desta`. O caso tem teste de integração.
- **Versão antes do estado.** A consulta de estado usa `COLLECT {}`, e servidor antigo devolvia erro de sintaxe. A versão (`dbms.components()`) passa a ser lida antes, na carga e no estado que a CLI mostra antes da confirmação.
- **`add_source` com linha malformada.** A etapa 5 recusa, com o mesmo texto do plano, a fonte que tem linha com colunas a mais ou a menos.
- **CSV de uma coluna.** A linha em branco vira um registro de valor vazio e segue o caminho normal, como chave vazia. Com duas colunas ou mais, continua pulada.
- **Payload antes da leitura.** `key` com `exclude`, falta de `key`, tipo desconhecido e chave ou join com tipo diferente de `string` são recusados antes de ler a fonte inteira.
- **Uma leitura por fonte de origem (era o M3).** Os contratos são agrupados pela fonte de origem, e cada bloco lido manda as arestas de todos eles. A ordem e as contagens não mudam: continua um comando por contrato e por bloco.
- **Cursor do Postgres.** Cada leitura usa um nome único (`akme_iter_<uuid>`). No fim, a última leitura aberta desfaz a transação de leitura, e a conexão não fica "idle in transaction". O fechamento especial da fonte vazia no `scan_source` saiu.
- **Script de integração.** Ctrl+C e `TERM` limpam e saem com 130; a pasta criada pelo `mktemp` é removida no fim.
- **Duplicações.** A prévia da CLI e o artefato usam a mesma lista de avisos (`warning_lines`), e o nome do projeto no artefato e nas consultas prontas é escrito por `neo4j_onto._literal`, que também escapa quebra de linha.

