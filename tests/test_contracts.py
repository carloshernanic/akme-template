import pytest
from rdflib import OWL, RDF

from akme.adapters import AdapterError
from akme.adapters.local_folder import LocalFolderAdapter
from akme.ontology import base_ns, load_content, load_graph, save_content
from akme.project import read_yaml
from akme.tools import ontology_write
from akme.tools.contracts import observe_join
from akme.tools.ontology_write import EditError
from akme.tools.publish import PublishError, publish, semantic_model
from akme.tools.validate import validate

PERTENCE = {"name": "pertenceA", "domain": "Pedido", "range": "Cliente", "label": "pertence a",
            "join": {"from": {"source": "pedidos", "column": "id_cliente"},
                     "to": {"source": "clientes", "column": "id_cliente"}}}


def _propose(project, type_, payload):
    return ontology_write.propose_edit(project, type_, payload, proposed_by="ana")


def test_relation_requires_multiplicity_and_join_or_reason(seeded):
    with pytest.raises(EditError, match="multiplicity"):
        _propose(seeded, "add_relation", {k: v for k, v in PERTENCE.items() if k != "join"})
    with pytest.raises(EditError, match="multiplicity invalido"):
        _propose(seeded, "add_relation", PERTENCE | {"multiplicity": "varios"})
    with pytest.raises(EditError, match="no_join_reason"):
        _propose(seeded, "add_relation", {k: v for k, v in PERTENCE.items() if k != "join"} | {"multiplicity": "many_to_one"})
    with pytest.raises(EditError, match="join.to exige"):
        _propose(seeded, "add_relation", PERTENCE | {"multiplicity": "many_to_one", "join": {"from": PERTENCE["join"]["from"], "to": {}}})
    with pytest.raises(EditError, match="coluna inexistente"):
        _propose(seeded, "add_relation", PERTENCE | {"multiplicity": "many_to_one",
                                                     "join": PERTENCE["join"] | {"to": {"source": "clientes", "column": "nada"}}})


def test_relation_contradicting_data_is_refused_unless_overridden(seeded):
    with pytest.raises(EditError, match="contradiz o dado"):
        _propose(seeded, "add_relation", PERTENCE | {"multiplicity": "one_to_one"})
    e = _propose(seeded, "add_relation", PERTENCE | {"multiplicity": "one_to_one", "override_reason": "amostra antiga"})
    ontology_write.apply_edit(seeded, e.id, "ana")
    report = validate(seeded)
    mismatch = [f for f in report.findings if f.check == "multiplicity_mismatch"]
    assert mismatch and all(f.level == "warning" for f in mismatch)


def test_applied_relation_stores_observed_contract_and_functional_property(seeded):
    contract = next(c for c in load_content(seeded)["relation_contracts"] if c["relation"] == "pertenceA")
    assert contract["multiplicity"] == "many_to_one" and contract["observed"]["multiplicity"] == "many_to_one"
    assert contract["observed"]["orphans"] == 0 and contract["observed"]["fanout"] is False
    contem = next(c for c in load_content(seeded)["relation_contracts"] if c["relation"] == "contem")
    assert contem["observed"]["fanout"] is True
    g = load_graph(seeded.schema_path)
    ns = base_ns(g)
    assert (ns["pertenceA"], RDF.type, OWL.FunctionalProperty) in g
    assert (ns["compoe"], RDF.type, OWL.FunctionalProperty) in g
    assert (ns["contem"], RDF.type, OWL.FunctionalProperty) not in g


def test_metric_term_and_mapping_require_contract(seeded):
    base = {"name": "ticket", "class": "Faturamento", "definition": "valor medio por pedido"}
    with pytest.raises(EditError, match="unit, grain, additivity"):
        _propose(seeded, "add_term", base)
    with pytest.raises(EditError, match="additivity invalido"):
        _propose(seeded, "add_term", base | {"unit": "BRL", "grain": "pedido", "additivity": "talvez"})
    with pytest.raises(EditError, match="non_additive_over"):
        _propose(seeded, "add_term", base | {"unit": "BRL", "grain": "pedido", "additivity": "semi_additive"})
    t = _propose(seeded, "add_term", base | {"unit": "BRL", "grain": "pedido", "additivity": "non_additive"})
    ontology_write.apply_edit(seeded, t.id, "ana")
    with pytest.raises(EditError, match="expression"):
        _propose(seeded, "add_mapping", {"term": "ticket", "source": "pedidos", "column": "vl_total"})
    with pytest.raises(EditError, match="role metric"):
        _propose(seeded, "add_mapping", {"term": "ticket", "source": "pedidos", "column": "vl_total", "role": "dimension",
                                         "expression": "AVG(vl_total)"})
    m = _propose(seeded, "add_mapping", {"term": "ticket", "source": "pedidos", "column": "vl_total", "expression": "AVG(vl_total)"})
    assert m.payload["role"] == "metric"
    plain = _propose(seeded, "add_term", {"name": "nf", "class": "Pedido", "definition": "nota fiscal"})
    assert "unit" not in plain.payload


def test_validate_flags_missing_contracts_and_orphans(seeded):
    content = load_content(seeded)
    content["relation_contracts"] = [c for c in content["relation_contracts"] if c["relation"] != "referencia"]
    for t in content["terms"]:
        if t["name"] == "faturamento":
            del t["unit"]
    save_content(seeded, content)
    pedidos = seeded.root / "data" / "pedidos.csv"
    pedidos.write_text(pedidos.read_text(encoding="utf-8") + "2001,999,2026-08-01,,PENDENTE,10.00\n", encoding="utf-8")
    report = validate(seeded)
    checks = {(f.check, f.subject): f.level for f in report.findings}
    assert checks[("relation_without_contract", "referencia")] == "warning"
    assert checks[("metric_without_contract", "faturamento")] == "error"
    assert checks[("join_orphans", "pertenceA")] == "warning"
    assert not report.ok


def test_orphans_look_for_the_keys_in_the_whole_target_when_its_sample_is_truncated(seeded, monkeypatch):
    # com sample=3 a amostra de pedidos tem o cliente 4 e a de clientes nao: comparar so as amostras acusaria orfao
    observed = observe_join(seeded, PERTENCE["join"], sample=3)
    assert observed["truncated"] and observed["orphans"] == 0 and observed["orphans_exact"] is True

    def no_batches(self, source, batch=5000):
        raise AdapterError("nao le em blocos")
    monkeypatch.setattr(LocalFolderAdapter, "iter_rows", no_batches)
    approx = observe_join(seeded, PERTENCE["join"], sample=3)
    assert approx["orphans"] == 1 and approx["orphans_exact"] is False


def test_publish_snowflake_has_keys_relationships_and_fanout(seeded):
    publish(seeded, "snowflake")
    sql = (seeded.docs_dir / "publish" / "snowflake.sql").read_text(encoding="utf-8")
    assert "clientes AS DB.PUBLIC.clientes PRIMARY KEY (id_cliente)" in sql
    assert "RELATIONSHIPS (" in sql and "contem AS itens_pedido (id_pedido) REFERENCES pedidos (id_pedido)" in sql
    assert "pertenceA AS pedidos (id_cliente) REFERENCES clientes (id_cliente)" in sql
    assert "unidade BRL; grao um pedido; aditiva; nao somar apos join com itens_pedido" in sql
    model = semantic_model(seeded)
    metric = next(m for s in model["sources"] for m in s["metrics"])
    assert metric["do_not_sum_after_join_with"] == ["itens_pedido"] and model["relationships_not_published"] == []


def test_publish_refuses_metric_without_expression_before_bump(seeded):
    content = load_content(seeded)
    for m in content["mappings"]:
        if m["term"] == "faturamento":
            del m["expression"]
    save_content(seeded, content)
    with pytest.raises(PublishError, match="faturamento"):
        publish(seeded, "snowflake", release="minor")
    assert "version: 0.1.0" in seeded.manifest_path.read_text(encoding="utf-8")
    assert not any(e.get("release") for e in read_yaml(seeded.changelog_path)["entries"])
