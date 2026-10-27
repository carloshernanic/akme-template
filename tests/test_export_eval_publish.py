import json

from akme.tools.eval import check_assertion, evaluate
from akme.tools.export import export
from akme.tools.profile import profile
from akme.tools.publish import publish
from akme.tools.validate import validate
from akme.ontology import load_graph


def test_export_writes_json_mermaid_and_yarrrml(seeded):
    profile(seeded)
    validate(seeded)
    result = export(seeded)
    data = json.loads((seeded.docs_dir / "ontology.json").read_text(encoding="utf-8"))
    assert {c["name"] for c in data["classes"]} >= {"Entity", "Cliente", "Pedido", "Faturamento"}
    assert any(r["name"] == "pertenceA" for r in data["relations"])
    assert len(data["terms"]) == 10 and len(data["mappings"]) == 10
    assert data["requirements"]["competency_questions"][0]["id"] == "CQ-001"
    assert data["validation"]["ok"] is True
    mmd = (seeded.docs_dir / "ontology.mmd").read_text(encoding="utf-8")
    assert "Pedido --> Cliente : pertenceA" in mmd and "Metric <|-- Faturamento" in mmd
    assert (seeded.docs_dir / "ontology.js").read_text(encoding="utf-8").startswith("window.AKME_DATA = ")
    assert "pedidos" in result["yarrrml"] or (seeded.ontology_dir / "mappings.yarrrml.yml").exists()


def test_structural_eval(seeded):
    g = load_graph(seeded.schema_path)
    assert check_assertion(g, "Pedido pertenceA Cliente")[0]
    assert check_assertion(g, "Faturamento subclassOf Metric")[0]
    assert not check_assertion(g, "Cliente pertenceA Pedido")[0]
    assert not check_assertion(g, "Pedido type Class extra")[0]
    result = evaluate(seeded)
    assert result["summary"] == {"questions": 3, "structural_pass": 3, "structural_fail": 0}


def test_eval_with_callable(seeded):
    def answer(question, context):
        return "use vl_total e categoria" if context else "nao sei"
    result = evaluate(seeded, answer)
    assert result["summary"]["with_correct"] == 2 and result["summary"]["without_correct"] == 0


def test_publish_dry_run_targets(seeded):
    y = publish(seeded, "yaml")
    assert (seeded.docs_dir / "publish" / "semantic.yml").exists() and y["sources"] == 4
    s = publish(seeded, "snowflake")
    sql = (seeded.docs_dir / "publish" / "snowflake.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE SEMANTIC VIEW" in sql and "METRICS" in sql and s["executed"] == 0
    d = publish(seeded, "databricks", release="minor")
    sql = (seeded.docs_dir / "publish" / "databricks.sql").read_text(encoding="utf-8")
    assert "ALTER COLUMN vl_total COMMENT" in sql and d["dry_run"]
    assert "version: 0.2.0" in seeded.manifest_path.read_text(encoding="utf-8")
    r = publish(seeded, "rdf")
    assert r["materialized"] is False and (seeded.ontology_dir / "mappings.yarrrml.yml").exists()
