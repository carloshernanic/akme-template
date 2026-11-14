"""Esquema descritivo para o LLM: texto deterministico, a partir da ontologia e do plano, sem conectar ao banco."""
from __future__ import annotations

from akme.project import read_yaml, write_yaml
from akme.tools.neo4j_plan import build_plan
from akme.tools.neo4j_schema import llm_schema


def test_schema_is_deterministic(seeded):
    plan = build_plan(seeded)
    assert llm_schema(seeded, plan) == llm_schema(seeded, build_plan(seeded))


def test_schema_has_how_to_query_block_first(seeded):
    text = llm_schema(seeded, build_plan(seeded))
    how = text.index("## Como consultar")
    assert how < text.index("### Pedido")
    block = text[how:text.index("## Labels de dado")]
    for name in ("`Conceito`", "`Termo`", "`_AkmeProjeto`", "`_id`", "`_projeto`", "`_carga`", "`_descricao`"):
        assert name in block
    assert "NOT n:Conceito" in block
    assert "MATCH (p:_AkmeProjeto {projeto: $projeto}) RETURN p.esquema" in block


def test_schema_describes_label_properties_terms_and_relations(seeded):
    text = llm_schema(seeded, build_plan(seeded))
    pedido = text[text.index("### Pedido"):text.index("### Produto")]
    assert "Solicitacao de compra de um cliente, com status e valor total." in pedido
    assert "chave: `id_pedido`" in pedido
    assert "`dt_pedido` (date)" in pedido and "`vl_total` (float)" in pedido and "`nf` (string)" in pedido
    assert "termo `status_pedido`: Situacao do pedido (FATURADO, PENDENTE ou CANCELADO)." in pedido
    assert "`(:Pedido)-[:pertenceA]->(:Cliente)`" in pedido and "many_to_one" in pedido and "rotulo \"pertence a\"" in pedido
    assert "10 aresta(s)" in pedido
    cliente = text[text.index("### Cliente"):text.index("### ItemPedido")]
    assert "termo `cliente`: Pessoa juridica cadastrada na distribuidora.; sinonimos: conta, comprador" in cliente


def test_schema_metric_cites_graph_labels(seeded):
    text = llm_schema(seeded, build_plan(seeded))
    pedido = text[text.index("### Pedido"):text.index("### Produto")]
    assert "metrica `Faturamento`" in pedido
    assert "SUM(CASE WHEN status = 'FATURADO' THEN vl_total END)" in pedido
    assert "unidade BRL" in pedido and "grao um pedido" in pedido and "aditividade additive" in pedido
    assert "nao somar apos juntar com: ItemPedido" in pedido
    assert "itens_pedido" not in pedido.split("metrica `Faturamento`")[1].split("\n")[0]


def test_schema_has_glossary_rules_and_precedence(seeded):
    text = llm_schema(seeded, build_plan(seeded))
    assert "## Glossario" in text and "- UF: Unidade federativa (convencao: duas letras maiusculas)" in text
    assert "## Regras" in text and "considerar apenas pedidos com status FATURADO" in text
    assert "## Precedencias" in text and "cliente ativo: vale financeiro sobre erp" in text


def test_schema_marks_unpublished_metric_join_source(seeded):
    content = read_yaml(seeded.content_path)
    content["sources"] = [s for s in content["sources"] if s["source"] != "itens_pedido"] + [
        {"source": "itens_pedido", "exclude": True}]
    write_yaml(seeded.content_path, content)
    text = llm_schema(seeded, build_plan(seeded))
    assert "nao somar apos juntar com: fonte itens_pedido (nao publicada)" in text


def test_schema_has_no_timestamp(seeded):
    import re

    text = llm_schema(seeded, build_plan(seeded))
    assert not re.search(r"\d{4}-\d\d-\d\dT\d\d:\d\d", text)
    assert "Construtora" not in text, "nenhum valor de linha da origem"


def test_inverse_with_its_own_published_edge_is_not_told_to_walk_backwards(seeded):
    content = read_yaml(seeded.content_path)
    content["relation_contracts"].append({"relation": "possuiPedido", "domain": "Cliente", "range": "Pedido",
                                          "inverse_of": "pertenceA", "multiplicity": "one_to_many",
                                          "join": {"from": {"source": "clientes", "column": "id_cliente"},
                                                   "to": {"source": "pedidos", "column": "id_cliente"}}})
    write_yaml(seeded.content_path, content)
    plan = build_plan(seeded)
    assert {"pertenceA", "possuiPedido"} <= set(plan.relationships)
    text = llm_schema(seeded, plan)
    line = next(x for x in text.splitlines() if "[:pertenceA]->" in x)
    assert "inversa: possuiPedido (tem aresta propria no grafo: `[:possuiPedido]`)" in line and "ao contrario" not in line
    contem = next(x for x in text.splitlines() if "[:contem]->" in x)
    assert ("inversa: pertenceAoPedido (sem aresta propria; e esta aresta lida ao contrario: "
            "`(:ItemPedido)<-[:contem]-(:Pedido)`)") in contem


def test_how_to_query_example_uses_a_label_of_this_plan(seeded):
    plan = build_plan(seeded)
    text = llm_schema(seeded, plan)
    assert "como `(:Cliente)`" in text, "o primeiro label do plano, em ordem"
    for s in plan.sources:
        object.__setattr__(s, "label", {"Cliente": "Conta", "Pedido": "Ordem"}.get(s.label, s.label))
    text = llm_schema(seeded, plan)
    how = text[text.index("## Como consultar"):text.index("## Labels de dado")]
    assert "Pedido" not in how and "como `(:Conta)`" in how


def test_schema_says_id_is_encoded(seeded):
    from akme.tools.neo4j_plan import build_plan
    from akme.tools.neo4j_schema import llm_schema

    text = llm_schema(seeded, build_plan(seeded))
    assert "percent-encoding" in text and "para filtrar, use a coluna original" in text


def test_schema_explains_relation_names_the_ontology_layer_and_the_name_caption(seeded):
    text = llm_schema(seeded, build_plan(seeded))
    how = text[text.index("## Como consultar"):text.index("## Labels de dado")]
    assert "nome exato da relacao na ontologia" in how and "`RELACAO_ONTOLOGIA`" in how and "`nome`" in how
    assert "publicada_nos_dados" in how and "inversa_de" in how
    assert "`name` e a legenda" in how
    assert "UPPER" not in text and "tipo_no_grafo" not in text


# --- auditoria de 13/11: regras sem id, conceitos sem dado, colunas de juncao, legenda ---

def test_rule_without_id_starts_with_the_term(seeded):
    content = read_yaml(seeded.content_path)
    content["constraints"] = [{"term": "valor_total", "rule": "Nao pode ser negativo."},
                              {"id": "R-01", "term": "uf", "severity": "error", "rule": "Duas letras."},
                              {"rule": "Regra solta."}]
    write_yaml(seeded.content_path, content)
    text = llm_schema(seeded, build_plan(seeded))
    assert "- termo valor_total: Nao pode ser negativo." in text
    assert "- R-01 (termo uf, severidade error): Duas letras." in text
    assert "- Regra solta." in text
    assert "-  (" not in text and "- :" not in text


def test_schema_lists_concepts_without_data(seeded):
    from akme.ontology import add_class, load_graph, save_graph

    assert "## Conceitos sem dados no grafo" not in llm_schema(seeded, build_plan(seeded))
    g = load_graph(seeded.schema_path)
    add_class(g, "SituacaoCliente", "Situacao", "Ativo, suspenso ou encerrado.", "Entity")
    save_graph(g, seeded.schema_path)
    text = llm_schema(seeded, build_plan(seeded))
    block = text[text.index("## Conceitos sem dados no grafo"):]
    assert "- `SituacaoCliente` (entidade): Ativo, suspenso ou encerrado." in block
    assert "`Entity`" not in block and "`Faturamento`" not in block, "classe de base e metrica publicada ficam de fora"


def test_join_column_points_to_the_edge_and_caption_is_named(seeded):
    text = llm_schema(seeded, build_plan(seeded))
    pedido = text[text.index("### Pedido"):text.index("### Produto")]
    assert "coluna de juncao: repete o que a aresta `[:pertenceA]` ja diz; para chegar em `(:Cliente)`, siga a aresta" in pedido
    cliente = text[text.index("### Cliente"):text.index("### ItemPedido")]
    assert "- legenda (`name`): o valor de `nm_cliente`" in cliente
    assert "coluna de juncao" not in cliente, "a chave do lado de chegada nao e repeticao"
    assert "legenda (`name`)" not in pedido, "sem coluna de legenda sozinha, a linha nao aparece"
