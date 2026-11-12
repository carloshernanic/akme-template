# Task 4: camada de ontologia (Conceito)

## O que mudou

Novo módulo `akme/tools/neo4j_onto.py` com duas funções:

- `ontology_statements(project, published)` devolve a lista de statements `(texto Cypher, parâmetros)` que desenham a ontologia no grafo.
- `render(statement)` escreve um statement como texto legível, com os parâmetros escritos como literais, para o artefato de dry-run `docs/publish/neo4j.cypher`. O akme nunca executa esse texto: quem executa os statements é a carga (Task 6), que acrescenta `$projeto` e `$carga`.

## O que é a camada Conceito e por que existe

O pedido do colega foi ver conceitos como nós e relações como setas no Neo4j Browser, sem escrever Cypher. O `n10s.onto.import` fazia o contrário: cada relação virava um nó `:Relationship`, e a ontologia aparecia como uma nuvem de nós sem sentido de seta.

A camada `Conceito` desenha a ontologia do jeito que se lê:

- um nó `(:Conceito)` por classe (`owl:Class`);
- uma seta `SUBCLASSE_DE` de cada classe para sua superclasse;
- uma seta por contrato de relação, do domínio para o alcance, com o **nome da relação** como tipo (`pertenceA`, `contem`...).

## Como convive com a camada de dados

Os nomes são os mesmos: o nó de dado `(:Pedido)` e o conceito `(:Conceito {nome: 'Pedido'})` usam o nome da classe, e a seta de dado `pertenceA` tem o mesmo tipo da seta de conceito `pertenceA`. Quem lê uma camada reconhece a outra.

Não existe aresta física entre as camadas. Ligar cada nó de dado ao seu conceito dobraria o número de arestas, poluiria o grafo de dados e quebraria a conferência por padrão `(:Dominio)-[:relacao]->(:Alcance)`. A ligação é lógica, pelo nome. Cada nó `Conceito` e cada seta de conceito carregam `_projeto` e `_carga`, como os dados, para a sincronização apagar só o que é do projeto e está velho.

## Os statements, em ordem

A ordem é determinística: classes por nome, depois subclasses, depois contratos por nome da relação.

1. **Classes.** `MERGE (c:Conceito {_projeto: $projeto, nome: $nome}) SET c = $props, c._projeto = $projeto, c._carga = $carga`
2. **Subclasses.** `MATCH` dos dois conceitos, `MERGE (a)-[r:SUBCLASSE_DE]->(b) SET r._carga = $carga`
3. **Contratos.** `MATCH` do domínio e do alcance, `MERGE (a)-[r:`relacao`]->(b) SET r = $props, r._carga = $carga`

Exemplo da demo (`render`, com `$projeto` e `$carga` mantidos como parâmetros da carga):

```cypher
MERGE (c:Conceito {_projeto: $projeto, nome: 'Cliente'}) SET c = {nome: 'Cliente', rotulo: 'Cliente', definicao: 'Pessoa juridica cadastrada que pode fazer pedidos.', iri: 'https://akme.example/ontology#Cliente'}, c._projeto = $projeto, c._carga = $carga
MATCH (a:Conceito {_projeto: $projeto, nome: 'Cliente'}), (b:Conceito {_projeto: $projeto, nome: 'Entity'}) MERGE (a)-[r:SUBCLASSE_DE]->(b) SET r._carga = $carga
MATCH (a:Conceito {_projeto: $projeto, nome: 'Pedido'}), (b:Conceito {_projeto: $projeto, nome: 'Cliente'}) MERGE (a)-[r:`pertenceA`]->(b) SET r = {rotulo: 'pertence a', definicao: '', multiplicidade: 'many_to_one', inversa: 'possuiPedido', publicada: true}, r._carga = $carga
```

A demo gera 9 conceitos, 5 setas `SUBCLASSE_DE` e 3 setas de relação (`contem`, `pertenceA`, `referencia`).

## Propriedades

**No nó `Conceito`:** `nome`, `rotulo`, `definicao` (o comentário da classe no `schema.ttl`), `iri`, mais `_projeto` e `_carga`.

**Na seta de relação:** `rotulo`, `definicao`, `multiplicidade` (do contrato), `inversa` (texto vazio se não houver), `publicada` (a relação está entre as publicadas) e `_carga`.

**Campos de métrica.** Se a classe é de métrica (descende de `Metric`), o nó ganha, só quando existem, os campos do contrato de métrica: `expressao` (do mapping de papel `metric` do termo da classe), `unidade`, `grao` e `aditividade` e `nao_somar_sobre` (do termo; `nao_somar_sobre` é a lista de dimensões de `non_additive_over`, obrigatória numa métrica semi-aditiva) e `nao_somar_apos_juntar_com`, uma lista com as fontes cujo join repetiria as linhas da métrica. No `Faturamento` da demo: `expressao = SUM(CASE WHEN status = 'FATURADO' THEN vl_total END)`, `unidade = BRL`, `grao = um pedido`, `aditividade = additive`, `nao_somar_apos_juntar_com = ['itens_pedido']`.

**Inversas são propriedade, não seta.** `pertenceA` guarda `inversa: 'possuiPedido'`. Desenhar `possuiPedido` como segunda seta duplicaria cada relação sem informação nova. Se o `content.yml` tiver contratos para os dois lados, fica só a seta do primeiro por nome, e a propriedade `inversa` dela sempre aponta o outro lado, mesmo que o contrato mantido não declare `inverse_of`. Relações cujo domínio ou alcance não é classe da ontologia ficam de fora.

## Determinismo e parâmetros

Entradas iguais geram listas iguais (a comparação é por igualdade de lista). Texto do cliente ou da ontologia (rótulo, definição, expressão, nome da classe) vai sempre como parâmetro, nunca dentro do texto da consulta; no texto entram só identificadores, pelo `name()` (crase dobrada), como o nome da relação. No `render`, strings saem entre aspas simples com `\'` e `\\` escapados, booleanos como `true`/`false`, listas `[...]`, mapas `{k: v}` (chave entre crases se não for identificador simples) e `None` como `null`; `nan` sai como `0.0/0.0`, `+inf` como `1.0/0.0` e `-inf` como `-1.0/0.0`, para o artefato continuar Cypher válido. Parâmetros que não estão no statement, como `$projeto` e `$carga`, ficam como estão.

## Como ver no Neo4j Browser

```cypher
MATCH p=(:Conceito)-->(:Conceito) RETURN p
```

## Testes (`tests/test_neo4j_onto.py`)

| Teste | O que prova |
|-------|-------------|
| `test_demo_ontology_draws_concepts_and_arrows` | 9 conceitos, 5 `SUBCLASSE_DE`, 3 contratos sem inversas, propriedades de `pertenceA` |
| `test_statements_are_deterministic` | duas chamadas dão a mesma lista |
| `test_order_is_classes_then_subclasses_then_relations` | ordem e ordenação por nome |
| `test_no_client_text_inside_query` | definição do cliente só aparece em parâmetros |
| `test_unpublished_relation_is_marked` | `publicada` falso quando nada foi publicado |
| `test_metric_concept_carries_contract` | campos de métrica no `Faturamento`, ausentes em `Cliente` |
| `test_names_with_backtick_are_quoted` | relação com crase sai como `` `tem``x` `` |
| `test_contract_outside_ontology_classes_is_skipped` | contrato com alcance inexistente fica de fora |
| `test_semi_additive_metric_carries_dimensions` | `nao_somar_sobre` aparece só quando o termo declara `non_additive_over` |
| `test_inverse_pair_with_both_contracts_keeps_one_arrow_pointing_to_the_other` | par inverso com contrato nos dois lados: uma seta, `inversa` aponta o outro lado |
| `test_render_nan_and_inf_are_valid_cypher` | nan e inf viram expressões Cypher válidas |
| `test_render_writes_literals` / `test_render_maps_lists_bools_and_keeps_run_params` | escrita dos literais e dos parâmetros da carga |

## TDD

RED: os testes foram escritos antes do módulo e falharam por `ModuleNotFoundError`. GREEN: com o módulo, os 13 testes passam. Um teste do plano (relação com crase no `schema.ttl`) não era viável, porque a crase não cabe num IRI Turtle; o caso passou a viver só no contrato do `content.yml`.

## Revisão

Aprovada sem críticos nem importantes.

Corrigidos nesta rodada:

- dimensões de métrica semi-aditiva (`nao_somar_sobre`) no conceito de métrica;
- ligação do par inverso preservada: a seta mantida aponta o outro lado em `inversa`;
- `nan` e `inf` no artefato `neo4j.cypher` viram Cypher válido.

Adiados:

- várias métricas na mesma classe: vale a primeira, na ordem do `content.yml`;
- relação de contrato ausente do `schema.ttl` fica sem rótulo e sem definição (o `validate` cobre).
