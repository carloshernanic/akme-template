# Task 6: carga, sincronização e conferência

Esta tarefa grava de fato no Neo4j, em Cypher puro e sem plugin. O código está em `akme/tools/neo4j_load.py`. Ele usa o plano da Task 3 (`build_plan`), a conversão da Task 2 (`convert`, `node_id`, `name`) e a camada de ontologia da Task 4 (`ontology_statements`, `render`). A CLI e o `publish.py` ainda chamam o exportador antigo (`n10s.py`): a troca é a Task 7.

## A carga, passo a passo

Tudo acontece numa só sessão do driver, nesta ordem. Cada comando é uma transação implícita (`session.run`).

1. **Proteção do destino.** O akme lê o estado do banco de novo, logo antes de gravar, e recusa com "... Nada foi gravado" se o banco não for vazio nem deste projeto (regras abaixo).
2. **Restrições e índices.**
    - Uma restrição de unicidade por label de classe: `CREATE CONSTRAINT akme_uniq_<Label> IF NOT EXISTS FOR (n:<Label>) REQUIRE n._id IS UNIQUE`.
    - Para `Conceito`, unicidade composta em `(c._projeto, c.nome)`, com o nome `akme_conceito_uniq_projeto_nome`.
    - Um índice por coluna-alvo de join, `akme_idx_<Label>__<coluna>_<hash>`, para resolver as arestas. O `<hash>` são 10 caracteres do SHA-1 do par exato (label, coluna).
    - Depois, `CALL db.awaitIndexes(300)`: as gravações só começam com os índices prontos.

    **Por que a restrição vem antes do `MERGE`:** `MERGE (n:Pedido {_id: ...})` precisa achar o nó pelo `_id`. Sem a restrição, que cria um índice, cada `MERGE` varre o label inteiro. Num lote de 5.000 linhas sobre centenas de milhares de nós, isso é inviável (o teste do design mostrou). Além disso, a restrição garante que duas linhas nunca virem dois nós com o mesmo `_id`.

    Todos os nomes têm o prefixo `akme_` e são determinísticos, então `IF NOT EXISTS` torna a etapa idempotente. Os três prefixos (`akme_uniq_`, `akme_idx_`, `akme_conceito_`) não se cruzam, e o hash impede que dois pares (label, coluna) caiam no mesmo nome. Isso importa porque `IF NOT EXISTS` pula em silêncio um nome que já existe: com o esquema antigo de nomes, uma coluna de join chamada `id` daria ao índice o mesmo nome da restrição, o índice não seria criado e cada aresta varreria o label inteiro.
3. **Marca do projeto:** `MERGE (m:_AkmeProjeto {projeto: $projeto})`.
4. **Nós, fonte a fonte, em blocos de 5.000 linhas** (`iter_rows`):

    ```cypher
    UNWIND $rows AS r MERGE (n:`Pedido` {_id: r.id})
    SET n = r.p, n._id = r.id, n._projeto = $projeto, n._carga = $carga
    ```

    `r.p` traz só as células preenchidas, convertidas pelo tipo aprovado na etapa 5 (texto quando a coluna não tem tipo declarado). Nunca vai `None`. `SET n = r.p` substitui todas as propriedades, então uma célula esvaziada na origem some do nó.
5. **Arestas, por contrato publicado, em blocos da fonte de origem.** As arestas vêm numa segunda passada, depois de todos os nós existirem. Quem resolve o join é o banco:

    ```cypher
    UNWIND $rows AS r MATCH (a:`Pedido` {_id: r.id}) MATCH (b:`Cliente` {`id_cliente`: r.v})
    MERGE (a)-[e:`pertenceA`]->(b) SET e._carga = $carga
    ```

    `r.v` vai como texto, que é exatamente como a coluna do join fica gravada no nó alvo (o plano obriga join e chave a serem `string`). Se as duas formas fossem diferentes, o `MATCH` acharia zero alvos em silêncio. O teste de integração prova que não acha: 10 arestas `pertenceA`, iguais ao plano.
6. **Ontologia:** os comandos de `ontology_statements(project, relações publicadas)`, com `$projeto` e `$carga`.
7. **Sincronização**, só se tudo acima deu certo (seção seguinte).

A conferência (`verify`) roda depois, numa sessão nova, e compara o banco com o plano.

## Sincronização: o que apaga e o que nunca apaga

Cada carga tem uma marca de rodada, `_carga`, com a data e a hora em UTC (`2026-11-12T10:00:00+00:00`). Todo nó e toda aresta gravados nesta carga, de dados ou de `Conceito`, recebem essa marca. No fim, dois comandos apagam o que ficou com marca antiga:

```cypher
MATCH (n) WHERE n['_projeto'] = $projeto AND coalesce(n['_carga'], '') <> $carga
CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS

MATCH (n)-[r]->() WHERE n['_projeto'] = $projeto AND coalesce(r['_carga'], '') <> $carga
CALL (r) { DELETE r } IN TRANSACTIONS OF 5000 ROWS
```

**Apaga:**

- nós deste projeto (`_projeto` igual ao nome do projeto) que não foram gravados nesta carga: linhas apagadas na origem, classes que saíram da ontologia e nós `Conceito` de classes removidas;
- arestas que saem de um nó deste projeto e não foram gravadas nesta carga: chave estrangeira que mudou de alvo, relação que saiu da ontologia;
- as arestas presas a um nó apagado (efeito do `DETACH DELETE`).

**Nunca apaga:**

- nada de outro projeto: as duas consultas filtram por `_projeto = $projeto`. De todo modo, a proteção do destino recusa um banco com outro projeto ou com nós alheios;
- a marca `_AkmeProjeto`, que tem a propriedade `projeto` e não `_projeto` (o teste de integração confere que continua uma só);
- nada, se algum lote, a ontologia ou a releitura da origem falhar.

**Regra da falha:** uma falha num lote de dados para tudo, antes da ontologia e da sincronização:

> lote 2 de 7 falhou: <erro>. 1 lote(s) ja gravado(s); nada foi apagado; repetir a carga completa e seguro

Repetir é seguro porque `MERGE` não duplica, e a próxima carga completa regrava tudo com uma marca nova antes de apagar. Valor que não converte para o tipo declarado, encontrado durante a carga, falha como o lote em que está. Se a ontologia falhar, a mensagem é parecida ("ontologia: comando N de M falhou ... nada foi apagado"). Se a própria sincronização falhar no meio, a carga nova já está gravada e só parte do antigo foi apagado; repetir também corrige.

Um erro do adapter no meio da leitura (conexão perdida, por exemplo) segue a mesma regra e a mesma mensagem ("lote X de Y falhou: leitura da origem: ..."). O texto do erro passa por `_safe`, que também troca os valores do adapter que podem ser credencial (os vindos de `env:` e os de chave como `password`, `dsn`, `uri`, `token`).

**Proteção a mais (não estava no brief):** a carga conta as linhas que leu de cada fonte, na passada dos nós e em cada passada de arestas. Se algum número for diferente do plano, a origem mudou entre o plano e a carga, e o akme recusa antes de apagar: "a origem mudou durante a carga: clientes (8 no plano, 7 agora). ... nada foi apagado". Sem isso, uma fonte lida vazia por engano levaria todos os nós daquele label, e uma origem que encolhesse entre a passada dos nós e a das arestas levaria arestas ainda válidas.

**Duas cargas no mesmo segundo** recebem a mesma `_carga` (a marca tem precisão de segundos). Isso é inofensivo: a segunda não apaga o que a primeira gravou, então no pior caso sobra dado a mais até a carga seguinte. Na revisão final, a marca passou a ter milissegundos e a carga ganhou uma trava contra carga concorrente (ver [a página da exportação](index.md#correcoes-da-revisao-final)).

**O que `removed` conta:** `removed.nodes` é o número de nós apagados. `removed.relationships` é o total de arestas apagadas, somando as dos nós apagados (pelo `DETACH DELETE`) e as arestas antigas entre nós que ficaram. Os números vêm dos contadores do resumo do driver (`summary.counters`), que funcionam com `IN TRANSACTIONS` no Neo4j 2026.10 (conferido no banco real).

`CALL { } IN TRANSACTIONS` exige uma transação implícita. Por isso a carga usa `session.run`, nunca `execute_write`. (Nota da revisão final: desde então, só a sincronização usa `session.run`; blocos, ontologia e restrições passaram a `execute_write`, que repete em erro transitório.)

## Proteção do destino

O estado do banco é lido sem gravar nada (`destination_state`), antes da confirmação, e de novo dentro da carga. Labels e propriedades vão como texto (`'Resource' IN labels(n)`, `n['_projeto']`), para um banco vazio não emitir avisos de "label desconhecido". O estado traz `projetos`, `total`, `alheios`, `legado` e `no_banco` (nós deste projeto por label, sem `Conceito`).

| Banco | Resultado |
|---|---|
| carregado pela exportação antiga (n10s) | recusa: "banco carregado pela exportacao antiga (n10s); limpe-o com o comando do guia" |
| vazio | aceita |
| mais de um projeto do akme | recusa |
| nós sem marca de projeto do akme | recusa: "use um banco vazio" |
| outro projeto | recusa: "use outro banco ou limpe este" |
| este projeto, mais nós alheios | recusa: "N no(s) que nao vieram do akme" |
| só este projeto | aceita e atualiza |

- **Alheio:** nó sem `_projeto` que não seja a marca `_AkmeProjeto`.
- **Legado do n10s:** existe um nó `Resource` ou `_GraphConfig` sem `_projeto`, ou a restrição `n10s_unique_uri`. A restrição sozinha também conta: é o que sobra num banco do qual se apagaram os nós, mas não o esquema. O "sem `_projeto`" é um ajuste meu, para uma classe do cliente chamada `Resource` não ser confundida com o n10s. Não há migração; o guia (Task 8) traz o comando de limpeza.

## O artefato do dry-run: `docs/publish/neo4j.cypher`

O dry-run não conecta ao banco. Ele lê cada fonte uma vez e grava `docs/publish/neo4j.cypher` com:

- o cabeçalho de resumo (linhas lidas, comandos de dados previstos, nós e arestas previstos, avisos) e, se houver problema, "NAO EXECUTE" e a lista de problemas;
- como definir `$projeto` e `$carga` no Browser (`:param`);
- as restrições, os índices e a marca, como comandos;
- os modelos dos comandos de nós, de arestas e da sincronização, como comentário e sem dados;
- os comandos da ontologia com os valores escritos (`render`), legíveis e executáveis.

O resultado de `publish_neo4j` tem as chaves do spec: `target`, `dry_run`, `artifact`, `rows`, `batches`, `executed`, `nodes`, `relationships`, `relations_not_published`, `sources_skipped`, `problems` e `warnings`. Na carga, entram também `carga`, `removed` e `verification`. A chave `triples` saiu, e o `neo4j.nt` não é mais gerado.

## O que a CLI mostra antes de confirmar

`preview_lines(result, state)` monta o resumo que a pessoa lê. A ligação com a CLI é da Task 7.

```
linhas: 43 em 7 lote(s) de dados, mais a ontologia
nos previstos:
  Cliente: 8
  ...
arestas previstas:
  pertenceA: 10
  ...
no banco hoje, deste projeto:
  Cliente: banco 8 -> origem 8
  ItemPedido: banco 0 -> origem 17
  ...
avisos:
  a carga apaga deste projeto o que nao vier da origem nesta carga
```

Labels que estão no banco mas não estão mais na origem aparecem com `origem 0`. Depois da carga, `viewing_lines` diz onde abrir o Browser e traz consultas prontas, entre elas `MATCH (n)-[r]->(m) WHERE NOT n:Conceito RETURN n, r, m LIMIT 300` (os dados) e `MATCH p = (:Conceito)-->(:Conceito) RETURN p` (a ontologia).

## Conferência

`verify(plan, projeto, conceitos)` conta no banco e compara com o plano:

- nós: `MATCH (n:<Label>) WHERE n._projeto = $p RETURN count(n)`;
- arestas: `MATCH (:<Dominio>)-[r:<relacao>]->(:<Alcance>) RETURN count(r)`. O padrão com os dois labels separa as arestas de dados das setas homônimas da camada `Conceito` (o defeito "`pertenceA` 11 em vez de 10" do design);
- conceitos: `MATCH (c:Conceito {_projeto: $p})`, contra o número de classes do `schema.ttl`.

Cada divergência vira uma linha como "Cliente: esperado 8, encontrado 9", e `publish_neo4j` falha com "carga executada, mas o banco diverge do previsto: ...".

## Segurança

- Dados vão sempre como parâmetro (`$rows`, `$projeto`, `$carga`). No texto das consultas só entram identificadores, por `name()`, entre crases. O teste confere que nenhum valor da demo ("Construtora", "CIM-50") aparece numa consulta.
- Credenciais vêm do ambiente (`AKME_NEO4J_URI`, `AKME_NEO4J_USER`, `AKME_NEO4J_PASSWORD`). Toda mensagem de erro passa por `_safe`, que troca a senha e a URI por `***`. `destination()` mostra o endereço sem usuário e senha embutidos.

## Testes contra o Neo4j real

`tests/test_neo4j_integration.py` roda só com `AKME_NEO4J_TEST_URI`, `AKME_NEO4J_TEST_USER` e `AKME_NEO4J_TEST_PASSWORD`. **Ele apaga o banco inteiro (nós, restrições e índices `akme_*`) no início de cada teste**, por isso usa variáveis próprias, que devem apontar para um banco dedicado a testes. Rodado em 12/11/2026 num Neo4j 2026.10.1 descartável, sem plugins, com a demo:

| Teste | O que prova | Resultado |
|---|---|---|
| `test_real_load_matches_plan_and_repeats` | 1ª carga: Cliente 8, ItemPedido 17, Pedido 10, Produto 8; contem 17, pertenceA 10, referencia 17; conferência ok; tipos gravados (data como `date`, `qt_itens` 100 inteiro, `vl_item` 3290.0). 2ª carga: mesmas contagens, mesmo total de nós, `removed` = 0, uma só marca e nenhum nó com `_carga` antiga | 0,58 s e 0,22 s |
| `test_real_sync_removes_deleted_row` | apagar o cliente 3 (sem pedidos) de `clientes.csv`: `removed.nodes` = 1, Cliente 7, conferência ok | 0,23 s e 0,19 s |
| `test_real_sync_removes_edge_whose_target_changed` | o pedido 1001 passa do cliente 1 para o 3: `removed.relationships` = 1 e a aresta nova aponta para o 3 | 0,17 s e 0,22 s |
| `test_real_load_refuses_foreign_nodes_and_deletes_nothing` | um nó alheio recusa a carga e continua no banco | recusado |
| `test_real_legacy_n10s_database_is_refused` | nós `Resource` e `_GraphConfig` recusam com a mensagem do n10s; nada é apagado | recusado |
| `test_real_index_on_join_column_named_id_is_created` | com a coluna de join renomeada para `id`, `SHOW INDEXES` mostra o índice `akme_idx_Cliente__id_<hash>` ONLINE em `id`, sem restrição dona; as restrições `akme_uniq_*` e a do `Conceito` existem; nenhum nome no esquema antigo | 0,58 s |
| `test_real_column_with_space_loads` | coluna `nome cliente` (com espaço) como chave e join: 10 `pertenceA`, conferência ok, propriedade com o nome original | 0,64 s |
| `test_real_ontology_shape` | 9 `Conceito`, 5 `SUBCLASSE_DE`, `(:Conceito {nome:'Pedido'})-[:pertenceA]->(:Conceito {nome:'Cliente'})` e nenhuma aresta entre as camadas | 0,21 s |

Os 8 testes passaram em cerca de 23 s, incluindo a limpeza do banco (nós, e restrições e índices `akme_*`, inclusive de nomes antigos) e a leitura do plano.

## Testes com sessão falsa (`tests/test_neo4j_load.py`)

A sessão falsa registra cada `(consulta, parâmetros)` e responde estado, contagens, `awaitIndexes` e os contadores da sincronização.

- **Ordem:** estado < restrição < índice < `awaitIndexes` < marca < nós < arestas < ontologia < remoção de nós < remoção de arestas; todas as arestas depois de todos os nós; 7 lotes na demo.
- **Parâmetros:** todo comando com `$carga` e `$projeto` recebe os valores da rodada; 17 comandos de ontologia.
- **Valores:** propriedades tipadas e só preenchidas; aresta casada pelo valor do join em texto (`{"id": "1001", "v": "1"}`).
- **Só parâmetros:** nenhum dado da demo no texto das consultas; `SET n = r.p` sem `+=`.
- **Falha:** falha no 2º lote → "lote 2 de 7 falhou", "1 lote(s) ja gravado(s)", "nada foi apagado", sem ontologia e sem `DELETE`. Valor inválido encontrado durante a carga e origem que mudou desde o plano também não apagam nada.
- **Sincronização:** escopo por `_projeto` e `_carga`, `IN TRANSACTIONS OF 5000 ROWS`, `removed` somando as arestas dos dois comandos.
- **Destino:** a tabela de regras (8 casos, com legado), legado pela restrição sozinha, recusa antes de qualquer `CREATE`/`MERGE`/`UNWIND`, estado lido sem gravar.
- **Conferência:** consultas por label e padrão; divergência de nó, aresta e conceito.
- **Publicação:** dry-run grava o artefato e nunca chama `_driver`; "NAO EXECUTE" com problemas; problemas recusam sem conectar; carga seguida de conferência; divergência vira erro.
- **Nomes:** com a coluna de join `id`, os 8 nomes de restrição e índice são distintos; `("A_b","c")` e `("A","b_c")` dão nomes diferentes.
- **Coluna com espaço:** `nome cliente` fica com o nome original em `r.p`, e o índice e a aresta usam a forma entre crases.
- **Falhas que não apagam:** origem que encolhe entre a passada dos nós e a das arestas; erro do adapter no meio da leitura (mensagem de lote, sem o DSN); falha num comando da ontologia.
- **Credenciais:** senha ausente das mensagens de erro de conexão e de lote; URI sem usuário e senha.
- **Textos:** `preview_lines` com e sem estado; `viewing_lines` com o Browser certo e as consultas novas.

## TDD

- **RED:** `tests/test_neo4j_load.py` escrito antes do módulo; a coleta falhou com `ImportError: cannot import name 'neo4j_load'`.
- **GREEN:** `akme/tools/neo4j_load.py` implementado; 35 testes passaram, mais 3 acrescentados depois (valor inválido durante a carga, origem que mudou e `load` chamado com um plano com problemas, que recusa sem conectar). Total: 38. Na rodada de correção, mais 5 (nomes sem colisão, coluna com espaço, origem que encolhe antes das arestas, erro do adapter, falha na ontologia): 43.
- **Integração:** a primeira execução contra o banco real achou um erro no próprio teste: a limpeza com `execute_query` usa transação explícita, e `IN TRANSACTIONS` exige implícita. A limpeza passou a usar `session.run`, a mesma regra que a carga segue.

## Revisão

A revisão independente fez uma leitura adversarial do escopo de remoção e não achou nada que apague dado indevido. Só quatro consultas apagam:

- **`SYNC_NODES`:** `DETACH DELETE` dos nós com `_projeto` igual ao do projeto e `_carga` diferente da atual. Alcança só nós deste projeto (dados e `Conceito`), nunca a marca `_AkmeProjeto`, que não tem `_projeto`.
- **`SYNC_EDGES`:** `DELETE` das arestas que saem de um nó deste projeto e têm `_carga` diferente da atual.
- **Limpeza do teste de integração:** `DETACH DELETE` de todos os nós e `DROP` das restrições e índices `akme_*`. Só roda com `AKME_NEO4J_TEST_*`, num banco dedicado a testes.
- **Nenhuma outra:** a proteção do destino recusa antes de gravar qualquer banco com outro projeto, nós alheios ou legado do n10s, e as duas remoções só rodam depois de todos os lotes, da releitura conferida e da ontologia.

Corrigido nesta rodada:

- colisão de nome entre índice e restrição quando a coluna de join se chama `id` (e entre pares como `A_b`+`c` e `A`+`b_c`): nomes com prefixos disjuntos e hash do par;
- teste de coluna com espaço no nome (`nome cliente`), com sessão falsa e no banco real;
- contagem de linhas também na passada de arestas, com a mesma recusa antes de apagar;
- erro do adapter no meio da carga virou a mensagem de lote, sem credenciais;
- teste de falha na ontologia, que não apaga nada.

Observações, sem mudança:

- O `DETACH DELETE` de um nó antigo do projeto remove também as arestas que chegam nele, inclusive de fora do projeto (que a proteção do destino já não deixa existir).
- Uma aresta criada à mão a partir de um nó do projeto não tem a `_carga` atual, e é apagada na carga seguinte.
