"""Camada de ontologia no Neo4j: statements deterministicos, sem texto do cliente na consulta."""
from __future__ import annotations

from akme.project import read_yaml, write_yaml
from akme.tools.neo4j_onto import descriptions, ontology_statements, render

PUBLISHED = {"contem", "pertenceA", "referencia"}
LABELS = {"clientes": "Cliente", "itens_pedido": "ItemPedido", "pedidos": "Pedido", "produtos": "Produto"}


def test_demo_ontology_draws_concepts_and_arrows(seeded):
    sts = ontology_statements(seeded, PUBLISHED)
    texts = [s for s, _ in sts]
    assert sum("MERGE (c:Conceito" in t for t in texts) == 9
    assert sum(":SUBCLASSE_DE]" in t for t in texts) == 5
    # espelho do schema.ttl: uma seta RELACAO_ONTOLOGIA por relacao, inversas incluidas (5 na demo)
    arrows = {p["rel"]: p for t, p in sts if ":RELACAO_ONTOLOGIA {nome: $rel}]" in t}
    assert sorted(arrows) == ["contem", "pertenceA", "pertenceAoPedido", "possuiPedido", "referencia"]
    assert all(t.endswith("SET r = $props, r._carga = $carga") for t in texts if "RELACAO_ONTOLOGIA" in t)
    assert arrows["pertenceA"]["props"] == {"nome": "pertenceA", "rotulo": "pertence a", "definicao": "",
                                            "multiplicidade": "many_to_one", "inversa": "possuiPedido",
                                            "publicada_nos_dados": True}
    assert arrows["possuiPedido"]["props"] == {"nome": "possuiPedido", "rotulo": "possuiPedido", "definicao": "",
                                               "inversa": "pertenceA", "publicada_nos_dados": False,
                                               "inversa_de": "pertenceA", "multiplicidade": "one_to_many"}
    assert (arrows["possuiPedido"]["de"], arrows["possuiPedido"]["para"]) == ("Cliente", "Pedido")
    assert not any("`pertenceA`" in t for t in texts), "o nome da relacao vai como parametro, nao como tipo"


def test_statements_are_deterministic(seeded):
    assert ontology_statements(seeded, set()) == ontology_statements(seeded, set())


def test_order_is_classes_then_subclasses_then_relations(seeded):
    texts = [t for t, _ in ontology_statements(seeded, set())]
    kinds = ["c" if "MERGE (c:" in t else "s" if ":SUBCLASSE_DE]" in t else "r" for t in texts]
    assert kinds == sorted(kinds, key={"c": 0, "s": 1, "r": 2}.get)
    names = [p["nome"] for t, p in ontology_statements(seeded, set()) if "MERGE (c:" in t]
    assert names == sorted(names)
    rels = [t for t in texts if t.endswith("r._carga = $carga") and "SUBCLASSE_DE" not in t]
    assert rels == sorted(rels)


def test_no_client_text_inside_query(seeded):
    sts = ontology_statements(seeded, set())
    assert all("Pessoa juridica" not in t for t, _ in sts)
    assert any("Pessoa juridica" in p["props"].get("definicao", "") for _, p in sts if "props" in p)


def test_unpublished_relation_is_marked(seeded):
    sts = ontology_statements(seeded, set())
    arrows = [p for t, p in sts if "RELACAO_ONTOLOGIA" in t]
    assert len(arrows) == 5 and all(p["props"]["publicada_nos_dados"] is False for p in arrows)


def test_metric_concept_carries_contract(seeded):
    sts = ontology_statements(seeded, set(), LABELS)
    fat = next(p for t, p in sts if p.get("nome") == "Faturamento")["props"]
    assert fat["expressao"] == "SUM(CASE WHEN status = 'FATURADO' THEN vl_total END)"
    assert (fat["unidade"], fat["grao"], fat["aditividade"]) == ("BRL", "um pedido", "additive")
    assert fat["nao_somar_apos_juntar_com"] == ["ItemPedido"], "cita o label do grafo, nao a tabela"
    cli = next(p for t, p in sts if p.get("nome") == "Cliente")["props"]
    assert "expressao" not in cli and "unidade" not in cli


def test_names_with_backtick_are_quoted(project):
    # a crase nao cabe num IRI do schema.ttl; so o contrato do content.yml pode carrega-la
    content = read_yaml(project.content_path)
    content["relation_contracts"] = [{"relation": "tem`x", "domain": "Entity", "range": "Entity",
                                      "multiplicity": "many_to_one"}]
    write_yaml(project.content_path, content)
    sts = ontology_statements(project, {"tem`x"})
    # a camada e espelho do schema.ttl: contrato sem relacao no TTL nao ganha seta; o nome nunca entra no texto
    assert not any("tem`x" in t for t, _ in sts)
    assert not any(p.get("rel") == "tem`x" for _, p in sts)


def test_contract_outside_ontology_classes_is_skipped(project):
    content = read_yaml(project.content_path)
    content["relation_contracts"] = [{"relation": "liga", "domain": "Entity", "range": "Fantasma",
                                      "multiplicity": "many_to_one"}]
    write_yaml(project.content_path, content)
    assert not any("`liga`" in t for t, _ in ontology_statements(project, set()))


def test_render_writes_literals():
    assert render(("MERGE (c:Conceito {nome: $nome})", {"nome": "O'Brien"})) == "MERGE (c:Conceito {nome: 'O\\'Brien'})"


def test_render_maps_lists_bools_and_keeps_run_params():
    st = ("MATCH (a {_projeto: $projeto}) SET r = $props, r._carga = $carga",
          {"props": {"a": True, "b": None, "c": ["x", "y\\z"], "d b": 3}})
    assert render(st) == ("MATCH (a {_projeto: $projeto}) SET r = {a: true, b: null, c: ['x', 'y\\\\z'], `d b`: 3}, "
                          "r._carga = $carga")


def test_semi_additive_metric_carries_dimensions(seeded):
    content = read_yaml(seeded.content_path)
    term = next(t for t in content["terms"] if t["name"] == "faturamento")
    term["additivity"], term["non_additive_over"] = "semi_additive", ["tempo", "regiao"]
    write_yaml(seeded.content_path, content)
    fat = next(p for t, p in ontology_statements(seeded, set()) if p.get("nome") == "Faturamento")["props"]
    assert fat["nao_somar_sobre"] == ["tempo", "regiao"]
    base = next(p for t, p in ontology_statements(seeded, set()) if p.get("nome") == "Pedido")["props"]
    assert "nao_somar_sobre" not in base


def test_inverse_pair_with_both_contracts_draws_both_arrows_like_the_ttl(seeded):
    content = read_yaml(seeded.content_path)
    # contratos dos dois lados: o primeiro por nome (pertenceA) sem inverse_of, o outro com
    for c in content["relation_contracts"]:
        if c["relation"] == "pertenceA":
            c.pop("inverse_of")
    content["relation_contracts"].append({"relation": "possuiPedido", "domain": "Cliente", "range": "Pedido",
                                          "inverse_of": "pertenceA", "multiplicity": "one_to_many"})
    write_yaml(seeded.content_path, content)
    sts = ontology_statements(seeded, PUBLISHED)
    arrows = {p["rel"]: p["props"] for t, p in sts if "RELACAO_ONTOLOGIA" in t}
    assert arrows["pertenceA"]["inversa"] == "possuiPedido" and arrows["possuiPedido"]["inversa"] == "pertenceA"
    assert arrows["possuiPedido"]["multiplicidade"] == "one_to_many" and "inversa_de" not in arrows["possuiPedido"]
    assert arrows["possuiPedido"]["publicada_nos_dados"] is False


def test_render_nan_and_inf_are_valid_cypher():
    assert render(("RETURN $v", {"v": [float("nan"), float("inf"), float("-inf")]})) == \
        "RETURN [0.0/0.0, 1.0/0.0, -1.0/0.0]"


def test_metric_join_source_not_published_is_named_as_source(seeded):
    labels = {k: v for k, v in LABELS.items() if k != "itens_pedido"}
    fat = next(p for t, p in ontology_statements(seeded, set(), labels) if p.get("nome") == "Faturamento")["props"]
    assert fat["nao_somar_apos_juntar_com"] == ["fonte itens_pedido (nao publicada)"]


def _terms(sts):
    return {p["nome"]: p["props"] for t, p in sts if t.startswith("MERGE (t:Termo")}


def test_terms_become_nodes_linked_to_their_concept(seeded):
    sts = ontology_statements(seeded, PUBLISHED, LABELS)
    terms = _terms(sts)
    assert len(terms) == 10
    assert terms["cliente"] == {"nome": "cliente", "name": "cliente", "definicao": "Pessoa juridica cadastrada na distribuidora.",
                                "sinonimos": ["conta", "comprador"], "fonte": "clientes", "coluna": "id_cliente",
                                "papel": "dimension"}
    assert terms["faturamento"] == {"nome": "faturamento", "name": "faturamento", "definicao": "Soma do valor total dos pedidos faturados.",
                                    "unidade": "BRL", "grao": "um pedido", "aditividade": "additive",
                                    "fonte": "pedidos", "coluna": "vl_total", "papel": "metric"}
    assert "sinonimos" not in terms["uf"], "campo vazio fica ausente"
    links = [(p["classe"], p["nome"]) for t, p in sts if ":TEM_TERMO]" in t]
    assert sorted(links) == sorted((("Cliente", "cliente"), ("Cliente", "uf"), ("Cliente", "cliente_ativo"),
                                    ("Pedido", "pedido"), ("Pedido", "data_pedido"), ("Pedido", "status_pedido"),
                                    ("Faturamento", "faturamento"), ("Produto", "produto"), ("Produto", "categoria"),
                                    ("ItemPedido", "quantidade")))
    for text, _ in sts:
        if "Termo" in text:
            assert "$carga" in text and "$projeto" in text
    merge = next(t for t, _ in sts if t.startswith("MERGE (t:Termo"))
    assert merge == "MERGE (t:Termo {_projeto: $projeto, nome: $nome}) SET t = $props, t._projeto = $projeto, t._carga = $carga"
    texts = [t for t, _ in sts]
    last_concept = max(i for i, t in enumerate(texts) if "MERGE (c:Conceito" in t)
    assert all(i > last_concept for i, t in enumerate(texts) if "Termo" in t), "termos depois dos conceitos"


def test_term_with_several_mappings_lists_sources_and_columns(seeded):
    content = read_yaml(seeded.content_path)
    content["mappings"].append({"term": "cliente", "source": "pedidos", "column": "id_cliente", "role": "dimension"})
    write_yaml(seeded.content_path, content)
    cliente = _terms(ontology_statements(seeded, PUBLISHED, LABELS))["cliente"]
    assert cliente["fontes"] == ["clientes", "pedidos"] and cliente["colunas"] == ["id_cliente", "id_cliente"]
    assert "fonte" not in cliente and "coluna" not in cliente


def test_term_outside_exported_concepts_is_skipped(seeded):
    content = read_yaml(seeded.content_path)
    content["terms"].append({"name": "solto", "class": "Fantasma", "definition": "x"})
    content["terms"].append({"name": "sem_classe", "definition": "y"})
    write_yaml(seeded.content_path, content)
    terms = _terms(ontology_statements(seeded, PUBLISHED, LABELS))
    assert "solto" not in terms and "sem_classe" not in terms


def test_descriptions_come_from_the_ontology(seeded):
    nodes, edges = descriptions(seeded)
    assert nodes["Pedido"] == "Solicitacao de compra de um cliente, com status e valor total."
    assert edges["pertenceA"] == "pertence a", "sem rdfs:comment, vale o rotulo"


def test_descriptions_prefer_comment_and_skip_empty(seeded):
    from rdflib import Literal, RDFS
    from akme.ontology import base_ns, load_graph, save_graph

    g = load_graph(seeded.schema_path)
    ns = base_ns(g)
    g.add((ns["contem"], RDFS.comment, Literal("Pedido contem os seus itens.", lang="pt")))
    g.remove((ns["Produto"], RDFS.comment, None))
    g.remove((ns["referencia"], RDFS.label, None))
    save_graph(g, seeded.schema_path)
    nodes, edges = descriptions(seeded)
    assert edges["contem"] == "Pedido contem os seus itens."
    assert "Produto" not in nodes and "referencia" not in edges


def test_concepts_and_terms_get_a_caption_and_arrows_say_if_published(seeded):
    sts = ontology_statements(seeded, {"pertenceA"})
    conceito = next(p for t, p in sts if "MERGE (c:Conceito" in t and p["nome"] == "Pedido")
    assert conceito["props"]["name"] == "Pedido"
    termo = next(p for t, p in sts if "MERGE (t:Termo" in t and p["nome"] == "uf")
    assert termo["props"]["name"] == "uf"
    arrows = {p["rel"]: p["props"] for t, p in sts if "RELACAO_ONTOLOGIA" in t}
    assert arrows["pertenceA"]["publicada_nos_dados"] is True
    assert arrows["contem"]["publicada_nos_dados"] is False, "sem aresta de dado"
    assert not any("tipo_no_grafo" in props for props in arrows.values())
