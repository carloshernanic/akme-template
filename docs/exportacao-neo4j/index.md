# Exportação para o Neo4j em Cypher

Esta página resume a troca do exportador do Neo4j na branch `feat/exportacao-neo4j-cypher`. O desenho original foi discutido com Mateus em 11/11/2026; estas páginas registram o que foi decidido e feito em cada tarefa. Tudo foi testado com o Neo4j 2026.10.1 Community local, em Docker; **o Aura não foi testado**.

## Por que mudar

Até a Task 7, o akme gerava RDF e o plugin n10s carregava no Neo4j. Foram registrados três motivos. A [pesquisa de 12/11/2026](pesquisa-camada-semantica.md) (seção 4) mostrou que só o do Aura se sustenta por inteiro. O teto de 100 mil linhas era do nosso código, e relação virar nó era um problema do `onto.import`, que tinha meio-termo:

- **O n10s não existe no Aura.** Depender do plugin limita onde o grafo pode rodar, e o n10s é projeto Labs, sem aprovação para produção. É o motivo que se confirma, e o mais forte.
- **Relações viram nós.** Era um problema do `n10s.onto.import`, que grava cada relação como um nó `Relationship`. Dava para manter o n10s só para os dados e gerar a ontologia em Cypher nosso.
- **Teto de 100 mil linhas.** O teto era do nosso código (`MAX_ROWS` no `n10s.py`), não do n10s. O `olist_order_items_dataset`, com 112.650 linhas, não carregava por causa dele.

O que a troca perdeu de fato foi o único gerador de RDF fiel (chaves, tipos e relações), que estava no `n10s.py`. Para quem consome o grafo, isso pesa pouco; para interoperabilidade RDF, é uma perda real.

## O novo fluxo

Tudo em Cypher puro, pelo driver oficial, sem plugin:

1. **Plano (dry-run):** lê cada fonte em blocos, confere chave, tipos e joins, conta nós e arestas esperados e lista problemas e avisos. Não conecta no banco.
2. **Confirmação:** a pessoa lê o resumo e confirma, na aba **Exportar** da página local ou na CLI. A carga continua só pelo humano; o agente não tem como dispará-la (ver [Correções de 13/11](correcoes-13-11.md)).
3. **Carga:** confere o destino, cria restrições e índices, grava nós, arestas e a camada de ontologia, tudo marcado com a `_carga` da rodada.
4. **Sincronização:** apaga o que é do projeto e tem `_carga` antiga.
5. **Conferência:** conta no banco por label e por padrão `(:Dominio)-[:relacao]->(:Alcance)`.

## O modelo no grafo

- **Nós de dado:** o label é a classe (ex.: `Pedido`). Propriedades: uma por coluna preenchida, mais `_id` (valores da chave), `_projeto`, `_carga`, `name` (a legenda no Browser, desde a Task 11) e, só com `neo4j: {descricao_nos_dados: true}` no `akme.yml`, `_descricao` (a definição da classe; desligada por padrão desde a rodada final).
- **Arestas de dado:** o tipo é o nome exato da relação no `schema.ttl` (ex.: `pertenceA`), do domínio para o alcance, com `_carga` e, com a mesma opção, `_descricao` (a definição da relação ou, sem ela, o rótulo).
- **Camada `Conceito`:** espelho do `schema.ttl`, como o grafo da página do akme: um nó `:Conceito` por classe do domínio (as classes de base do akme, `Entity`, `Metric`, `Relation` e `Rule`, ficam de fora desde 13/11/2026), com `tipo`, `(:Conceito)-[:SUBCLASSE_DE]->(:Conceito)` por subclasse e uma seta `RELACAO_ONTOLOGIA` por relação (inversas incluídas), com o nome em `nome` e `publicada_nos_dados` (desde a Task 11).
- **Termos:** um nó `:Termo` por termo do `content.yml`, ligado por `(:Conceito)-[:TEM_TERMO]->(:Termo)`.
- **Esquema para o LLM:** em `docs/publish/neo4j_schema.md` e na propriedade `esquema` da marca `_AkmeProjeto`.
- **Tutorial do projeto no Browser:** em `docs/publish/neo4j_guia.html`, cinco páginas só de navegação, servido pelo `akme review` em `/neo4j/guia`. Desde 13/11/2026 a primeira página abre pelo mapa das classes (e pelo grafo inteiro, até 500 registros), o "Explorar" parte do registro mais ligado, e o publish gera também `docs/publish/neo4j_estilo.grass` (cor por classe, ontologia em cinza, nome nas setas), importado pelo `:style` do Browser. As perguntas de competência saíram do tutorial e do akme por decisão de Mateus em 12/11/2026; perguntas em português ficam com o console da Aura (caminho não testado pelo akme).
- **Restrição:** `_id` único por label, necessária para o `MERGE` ser viável.

## Referência do exportador

O código está em `akme/tools/`:

| Módulo | Papel |
|---|---|
| `neo4j_values.py` | Converte cada célula para o tipo aprovado e calcula a identidade `_id` do nó |
| `neo4j_plan.py` | Plano da carga (dry-run): lê em blocos, confere e conta, sem guardar as linhas |
| `neo4j_onto.py` | Camadas `Conceito` e `Termo`: comandos da ontologia, com parâmetros; textos de `_descricao` |
| `neo4j_schema.py` | Esquema descritivo para o LLM, em Markdown, determinístico |
| `neo4j_guide.py` | Tutorial do projeto no Neo4j Browser e consultas salvas, determinísticos, só de navegação |
| `neo4j_load.py` | Proteção do destino, carga, sincronização, conferência, artefato e textos da CLI |


**Detalhes do modelo que não estão acima:**

- **Legenda `name`** (regra de 13/11/2026): o valor da coluna de legenda, decidida na etapa 5 (`caption` do `add_source`) ou, sem decisão, uma coluna de texto com cara de nome preenchida em 90% das linhas, por exemplo `Construtora Horizonte`. Sem coluna de legenda, o label, a chave (código longo cortado em 8 caracteres) e a primeira coluna mapeada que não é chave nem join, por exemplo `ItemPedido 1001/CIM-50 100`. Se a fonte tiver coluna `name`, ela vale e o akme não grava a sua (o plano avisa).
- **Esquema do banco:** uma restrição de unicidade de `_id` por label (`akme_uniq_<Label>`), uma composta para o `Conceito` (`akme_conceito_uniq_projeto_nome`), outra para o `Termo` (`akme_termo_uniq_projeto_nome`), `akme_projeto_uniq` para a marca e um índice por coluna-alvo de join (`akme_idx_<Label>__<coluna>_<hash>`).
- **Marca:** `(:_AkmeProjeto {projeto, name, esquema, carga_atual})`, gravada na primeira carga; `carga_atual`, `name` e `esquema` são regravados a cada carga.
- **Nomes reservados:** os labels `Conceito`, `Termo` e `_AkmeProjeto`, as propriedades `_id`, `_projeto`, `_carga` e `_descricao` (nos dois modos da opção) e, como nome de relação, `RELACAO_ONTOLOGIA`, `SUBCLASSE_DE` e `TEM_TERMO`. Uma classe, relação ou coluna da origem com um desses nomes é problema no plano, e a carga é recusada.
- **Dados como parâmetro:** os valores vão sempre em `$rows`, `$projeto`, `$carga`, `$descricao` e `$esquema`. No texto das consultas só entram identificadores, entre crases.

### O que o exportador faz com cada caso

| Caso | Resultado |
|---|---|
| Fonte sem classe, com mais de uma classe ou classe em mais de uma fonte | Recusa |
| Fonte sem chave; chave vazia ou repetida | Recusa |
| Valor que não converte sem perda, como `03/07/2026` em `date` | Recusa |
| Tipo, fonte ou coluna inexistente na configuração; chave ou join com tipo diferente de `string` | Recusa |
| Classe com nome reservado (`Conceito`, `Termo`, `_AkmeProjeto`) ou coluna `_id`, `_projeto`, `_carga` ou `_descricao` (nos dois modos da opção) | Recusa |
| Nome de fonte, coluna ou contrato com caractere invisível (BOM `U+FEFF`, espaço de largura zero, espaço não separável, controle) que não bate com a origem | Recusa, com o caractere marcado como `<U+FEFF>` e o que fazer, no plano, no `add_source` e na conferência dos contratos |
| Bloco `neo4j` do `akme.yml` com outra chave que não `descricao_nos_dados`, ou com valor que não é `true`/`false` | Recusa |
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

### Por que este caminho

| Decisão | Motivo | Base |
|---|---|---|
| Neo4j como alvo | Pedido de Gabriel, da McKinsey | Conversa com o usuário |
| Cypher puro, sem plugin | O n10s não existe no Aura e é projeto Labs, sem aprovação para produção. Os outros dois motivos registrados na spec não eram do n10s (ver [Por que mudar](#por-que-mudar)) | Spec de 11/11/2026; pesquisa de 12/11/2026; decisão de Mateus |
| Ontologia como `Conceito`, espelho do `schema.ttl`, com uma seta `RELACAO_ONTOLOGIA` por relação (nome em `nome`) | Quem abre o Browser lê conceitos como nós e relações como setas, sem escrever Cypher; o tipo próprio evita que o mapa nativo desenhe ligações de dado que não existem | Pedido do colega; decisões de Mateus (Task 11) |
| `_descricao` nos dados desligada por padrão | +14% a +43% de disco no Olist para um texto que já está no `Conceito` e no esquema | Medição da Task 10 e da rodada final; decisão de Mateus |
| Leitura em blocos nos quatro adapters, sem teto de linhas | O `olist_order_items_dataset` tem 112.650 linhas | Teste do Olist; decisão de Mateus |
| Restrição única por label antes do `MERGE` | Sem ela, cada `MERGE` varre o label inteiro | Teste descartável de 11/11/2026 |
| Sincronizar a cada carga | As contagens do banco batem com as da origem lida nesta carga, inclusive linhas apagadas e relações que saíram. A conferência só conta; a comparação de valores existe só na amostra da demo (`examples/local_demo/amostra_valores.py`) | Decisão de Mateus |
| Chave e tipo decididos na etapa 5, com sugestão automática | Identidade estável, tipo que não depende dos dados, nada escrito à mão, decisão versionada | Testes automatizados; demo e `teste_acme` |
| Dinheiro como `float` | O Neo4j não tem tipo decimal; não serve para uso contábil | Decisão do usuário |
| Carga só pelo humano, na CLI | A carga altera o banco do cliente | `tests/test_server_publish_guard.py` |

### Limites conhecidos

- **Sem tipo `datetime`.** A etapa 5 só tem `string`, `integer`, `float` e `date`. Datas com hora (todas as do Olist) ficam texto, e toda conta com elas corta a hora na consulta (`date(left(p.order_delivered_customer_date, 10))`). É a lacuna que mais pesa no uso. Vírgula decimal também é recusada para `float`.
- **Carga sempre completa, sem incremental.** Cada carga lê a origem inteira e regrava todos os nós e arestas; no Olist, cerca de 34 s.
- **Memória do plano proporcional ao número de chaves.** O plano não guarda as linhas, mas guarda um `_id` por linha da tabela que está lendo e uma contagem por valor de cada coluna de join: 144 MB no Olist (446 mil linhas); a extrapolação para 10 milhões de linhas dá de 1,5 a 2 GB.
- **A sincronização varre todos os nós.** Ela e as consultas de estado filtram por `_projeto` e `_carga`, que não têm índice: no Olist, 0,2 s por consulta; cresce com o banco.
- **Aura não testado.** Nem Enterprise. Tudo o que estas páginas afirmam vale para o Neo4j local em Docker.
- **`_descricao` ligada custa disco**, e a das arestas costuma ser só o rótulo, porque a ontologia não exige definição nas relações.

### O que falta

- Corrigir na ontologia do Olist da raiz as três pendências que a aceitação corrigiu só na cópia (ver a [Task 9](task-9-aceitacao.md)).
- Servidor MCP do Neo4j e perguntas de competência como teste (o esquema para o LLM foi feito na Task 10).
- Exigir definição em `add_relation` e checar relações sem definição no validador; hoje a `_descricao` das arestas costuma ser só o rótulo.
- Snowflake e Databricks com leitura em blocos testada só com cursor falso.
- Decidir o destino do alvo `rdf`, cujo YARRRML perde relações e tipos.
- Decidir se a aresta sem definição, com `_descricao` ligada, deve receber o rótulo ou ficar sem a propriedade (decisão de Mateus).
- Testar no Aura (depende de Mateus criar a instância).
- Unificar como CSV e XLSX aparam espaços (hoje só a planilha apara).
- Aviso de grafo desconectado no dry-run, correção de mappings (`update_mapping`, `remove_mapping`, `rename_class`) e perguntas de competência em Cypher como teste: ver [Correções de 13/11](correcoes-13-11.md).

**Fora do Neo4j, só anotado:**

- A tool MCP ainda executa `snowflake`, `databricks` e `rdf` sem confirmação.
- `connect` ignora o `.r2rml` do `teste_acme`.

## As tarefas

| # | Tarefa | Status |
|---|--------|--------|
| 1 | Leitura em blocos nos adapters e BOM | commitada (até `974da8a`) |
| 2 | Conversão de valores e identidade do nó | commitada (até `974da8a`) |
| 3 | Plano da carga (dry-run) lendo em blocos | commitada (até `974da8a`) |
| 4 | Camada de ontologia (Conceito) | commitada (até `974da8a`) |
| 5 | Validação do `add_source` lendo a fonte inteira | commitada (até `974da8a`) |
| 6 | Carga, sincronização e conferência | commitada (até `974da8a`) |
| 7 | Ligar o caminho novo e remover o n10s | commitada (até `974da8a`) |
| 8 | Documentação, guia e verificador da demo | commitada (até `974da8a`) |
| 9 | Aceitação real (demo, Olist e Postgres) | commitada (até `974da8a`); repetida na rodada final sobre o código final |
| 10 | Camada semântica legível no grafo (`_descricao`, esquema para o LLM, termos) | commitada (até `974da8a`) |
| 11 | Tutorial curto do projeto no Neo4j Browser (só navegação), camada `Conceito` espelho do TTL e legenda `name` | commitada (até `974da8a`; escopo congelado em 12/11/2026) |
| — | Rodada final de correções (abaixo) | aguardando commit |
| — | [Correções de 13/11](correcoes-13-11.md): nomes reservados, legenda na etapa 5, tutorial pelo mapa das classes, estilo de cores e aba Exportar | feita em 13/11/2026 |

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
- **I6.** A justificativa da troca (então em `docs/neo4j/exportacao.md`, hoje na seção [Por que este caminho](#por-que-este-caminho)) cita só o motivo que se sustenta (Aura; n10s é projeto Labs).
- **M11.** O guia traz um só método e um só número de memória (o da Task 10).
- **M12.** A linha "Documentação das colunas" de [Uso real do grafo](uso-do-grafo.md) passou a refletir o estado depois da Task 10.
- **Ledger.** O guia explica que editar a origem entre a prévia e a carga muda o banco, mas não o resumo aprovado.

**Deixado como limite documentado (no guia, em "Limites conhecidos", ou em "O que falta"):**

- **I8.** Sem tipo `datetime`: carimbos ficam como texto e vírgula decimal é recusada para `float`. Mudaria os tipos da etapa 5.
- **M4.** A memória do plano cresce com o número de chaves; o guia dá a ordem de grandeza.
- **M6.** A sincronização e as consultas de estado varrem todos os nós.
- **M7 e M8.** Opção para desligar `_descricao` (feita na rodada final: desligada por padrão) e o que fazer com a aresta sem definição (continua decisão de Mateus).
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

## Rodada final de correções (12/11/2026, aguardando commit)

Depois de uma revisão externa do `974da8a`, Mateus pediu uma rodada única de correções, sem novas revisões depois. O que mudou:

- **`_descricao` desligada por padrão.** Liga-se com `neo4j: {descricao_nos_dados: true}` no `akme.yml`. Desligada, a propriedade fica ausente nos nós e arestas de dado e some de uma carga anterior; a definição continua no `Conceito`, no esquema para o LLM e no tutorial, e `_descricao` continua nome reservado. Motivo: o custo em disco no Olist (+14% numa base nova, +43% regravando por cima) para um texto que o LLM não lê. Verificador, amostra, esquema, tutorial e mensagens da CLI seguem o modo, com testes unitários e de integração dos dois. O nome da opção fica dentro do bloco `neo4j`, que já era do alvo, e diz onde a descrição vai: nos dados (o `Conceito` tem a definição de qualquer jeito).
- **Caractere invisível visível.** Quando um nome de fonte, coluna ou contrato tem BOM (`U+FEFF`), espaço de largura zero, espaço não separável ou caractere de controle, o plano, o `add_source` e a conferência dos contratos escrevem `<U+FEFF>` no lugar e dizem o que fazer. Antes, a mensagem mostrava `product_category_name` dos dois lados.
- **Suíte mais rápida.** A fixture `seeded` aplicava as cerca de 50 edições da demo (cada uma relê e regrava o YAML) em todo teste que a usava, uns 2 s por teste. Agora a demo semeada é montada uma vez por sessão e copiada para a pasta de cada teste, que continua isolado. A suíte inteira caiu de minutos para menos de um minuto (números no relatório da rodada).
- **Aceitação repetida no código final** ([Task 9](task-9-aceitacao.md)): a demo é a aceitação reproduzível; o Olist é registro de execução, com dados e ontologia fora do repositório e uma cópia com três correções.
- **Postgres até o Neo4j:** carga completa da demo a partir de um Postgres 16 descartável, conferida por contagens, verificador e amostra; virou o teste opcional `test_real_load_from_postgres` (pulado sem `AKME_PG_TEST_DSN`).
- **Perguntas do Olist em arquivo:** `examples/olist_perguntas_neo4j.cypher`, com o pedido da CQ-008 como parâmetro.
- **Documentos:** [Uso real do grafo](uso-do-grafo.md) reescrita para o modelo atual; "Limites conhecidos" do guia e desta página com a falta de `datetime`, a carga sempre completa, a memória do plano, a sincronização que varre os nós e o Aura não testado.
- **Pasta `docs/neo4j/` removida** por pedido de Mateus. O que ela tinha de atual (módulos, nomes reservados, casos, decisões, limites e o que falta) foi para esta página; as provas estão na [Task 9](task-9-aceitacao.md). Os registros antigos (`historico.md`, `teste-n10s`) ficam no histórico do git.
