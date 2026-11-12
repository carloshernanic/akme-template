"""Camada de ontologia no Neo4j: statements deterministicos, sem texto do cliente na consulta."""
from __future__ import annotations

from akme.project import read_yaml, write_yaml
from akme.tools.neo4j_onto import ontology_statements, render

PUBLISHED = {"contem", "pertenceA", "referencia"}


def test_demo_ontology_draws_concepts_and_arrows(seeded):
    sts = ontology_statements(seeded, PUBLISHED)
    texts = [s for s, _ in sts]
    assert sum("MERGE (c:Conceito" in t for t in texts) == 9
    assert sum(":SUBCLASSE_DE]" in t for t in texts) == 5
    assert sum(t.endswith("SET r = $props, r._carga = $carga") for t in texts) == 3
    pert = next(p for t, p in sts if "`pertenceA`" in t)
    assert pert["props"] == {"rotulo": "pertence a", "definicao": "", "multiplicidade": "many_to_one",
                             "inversa": "possuiPedido", "publicada": True}
    assert not any("possuiPedido`]" in t or "pertenceAoPedido`]" in t for t in texts)


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
    arrows = [p for t, p in sts if t.endswith("SET r = $props, r._carga = $carga")]
    assert len(arrows) == 3 and all(p["props"]["publicada"] is False for p in arrows)


def test_metric_concept_carries_contract(seeded):
    sts = ontology_statements(seeded, set())
    fat = next(p for t, p in sts if p.get("nome") == "Faturamento")["props"]
    assert fat["expressao"] == "SUM(CASE WHEN status = 'FATURADO' THEN vl_total END)"
    assert (fat["unidade"], fat["grao"], fat["aditividade"]) == ("BRL", "um pedido", "additive")
    assert fat["nao_somar_apos_juntar_com"] == ["itens_pedido"]
    cli = next(p for t, p in sts if p.get("nome") == "Cliente")["props"]
    assert "expressao" not in cli and "unidade" not in cli


def test_names_with_backtick_are_quoted(project):
    # a crase nao cabe num IRI do schema.ttl; so o contrato do content.yml pode carrega-la
    content = read_yaml(project.content_path)
    content["relation_contracts"] = [{"relation": "tem`x", "domain": "Entity", "range": "Entity",
                                      "multiplicity": "many_to_one"}]
    write_yaml(project.content_path, content)
    texts = [t for t, _ in ontology_statements(project, {"tem`x"})]
    assert any("[r:`tem``x`]" in t for t in texts)


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


def test_inverse_pair_with_both_contracts_keeps_one_arrow_pointing_to_the_other(seeded):
    content = read_yaml(seeded.content_path)
    # contratos dos dois lados: o primeiro por nome (pertenceA) sem inverse_of, o outro com
    for c in content["relation_contracts"]:
        if c["relation"] == "pertenceA":
            c.pop("inverse_of")
    content["relation_contracts"].append({"relation": "possuiPedido", "domain": "Cliente", "range": "Pedido",
                                          "inverse_of": "pertenceA", "multiplicity": "one_to_many"})
    write_yaml(seeded.content_path, content)
    sts = ontology_statements(seeded, PUBLISHED)
    assert not any("`possuiPedido`" in t for t, _ in sts)
    pert = next(p for t, p in sts if "`pertenceA`" in t)
    assert pert["props"]["inversa"] == "possuiPedido"


def test_render_nan_and_inf_are_valid_cypher():
    assert render(("RETURN $v", {"v": [float("nan"), float("inf"), float("-inf")]})) == \
        "RETURN [0.0/0.0, 1.0/0.0, -1.0/0.0]"
