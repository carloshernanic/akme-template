import json
import subprocess
import threading
import urllib.error
import urllib.request

import pytest

from akme import review_server
from akme.models import Edit, EditType, Review
from akme.tools import ontology_write
from akme.tools.review_view import present
from akme.tools.stage import current_stage

CQ = {"question": "q", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]}


def test_present_relation_with_observed_and_json_evidence():
    e = Edit(id="add_relation-1", type=EditType.add_relation, evidence='{"kind":"source","path":"p.csv","locator":"col a","quote":"1"}',
             payload={"name": "pertenceA", "domain": "Pedido", "range": "Cliente", "label": "pertence a", "multiplicity": "many_to_one",
                      "join": {"from": {"source": "pedidos", "column": "id_cliente"}, "to": {"source": "clientes", "column": "id_cliente"}},
                      "observed": {"available": True, "multiplicity": "many_to_many", "from": {"rows": 10, "distinct": 9, "nulls": 0, "duplicated": True},
                                   "to": {"rows": 5, "distinct": 4, "nulls": 1, "duplicated": True}, "orphans": 2, "orphan_examples": ["7"], "fanout": True, "truncated": False, "sample": 5000}})
    v = present(e)
    assert v["title"] == "Relação pertenceA" and v["subtitle"] == "Pedido → Cliente" and v["stage"] == 2 and v["group"] == "relation"
    labels = {f["label"]: f["value"] for f in v["fields"]}
    assert labels["Multiplicidade"] == "muitos para um" and labels["Junção"] == "pedidos.id_cliente → clientes.id_cliente"
    assert v["evidence"][0]["path"] == "p.csv" and v["evidence"][0]["quote"] == "1"
    assert any("fanout" in a for a in v["alerts"]) and any("declarada muitos para um" in a for a in v["alerts"])
    assert [f["key"] for f in v["editable"]] == ["label", "comment"] and v["rejectable"] is True


def test_present_covers_every_edit_type():
    samples = {
        EditType.add_class: {"name": "A", "label": "a", "comment": "c"},
        EditType.add_relation: {"name": "r", "domain": "A", "range": "B", "label": "r", "multiplicity": "one_to_one", "no_join_reason": "conceitual"},
        EditType.add_term: {"name": "t", "class": "A", "definition": "d", "unit": "BRL", "grain": "um pedido", "additivity": "additive"},
        EditType.add_mapping: {"term": "t", "source": "s", "column": "c", "role": "metric", "expression": "SUM(x)"},
        EditType.add_constraint: {"term": "t", "rule": "r", "severity": "error"},
        EditType.add_precedence: {"topic": "x", "winner": "a", "over": "b", "reason": "r"},
        EditType.add_source: {"source": "pedidos", "key": ["id_pedido"], "types": {"dt_pedido": "date"}, "class": "Pedido",
                              "checked": {"rows": 10, "types": {"dt_pedido": {"kind": "date", "converted": 10, "filled": 10, "example": "2026-07-03"}}}},
        EditType.add_glossary: {"acronym": "UF", "meaning": "estado"},
        EditType.add_requirement: {"field": "purpose", "value": "p"},
        EditType.add_use_case: {"id": "UC-01", "name": "n", "description": "d"},
        EditType.add_competency_question: {"id": "CQ-001", "question": "q?", "type": "atributos", "concepts": ["X"]},
        EditType.update_competency_question: {"id": "CQ-001", "question": "nova"},
        EditType.remove_competency_question: {"id": "CQ-001", "reason": "r"},
        EditType.add_gap: {"id": "L-01", "question": "g?", "reason": "r", "missing": "m"},
        EditType.update_gap: {"id": "L-01", "decision": "drop"},
        EditType.add_divergence: {"id": "D-01", "topic": "t", "sources": [], "hypothesis": "h"},
        EditType.update_divergence: {"id": "D-01", "decision": "dismiss"},
        EditType.update_mapping: {"term": "t", "source": "s", "column": "c", "set": {"column": "d"},
                                  "before": {"term": "t", "source": "s", "column": "c"}, "after": {"term": "t", "source": "s", "column": "d"}},
        EditType.remove_mapping: {"term": "t", "source": "s", "column": "c", "reason": "tabela errada"},
        EditType.rename_class: {"name": "A", "new_name": "B"},
    }
    assert set(samples) == set(EditType)
    for t, payload in samples.items():
        v = present(Edit(id=f"{t.value}-1", type=t, payload=payload, evidence="reuniao de kickoff"), current={"question": "atual", "topic": "tema"})
        assert v["title"] and v["group"] and v["stage"] in (1, 2, 3, 5), t
        assert v["evidence"][-1] == {"kind": "note", "path": "", "locator": "", "quote": "", "who": "", "when": "", "note": "reuniao de kickoff"}
    assert present(Edit(id="x", type=EditType.add_gap, payload=samples[EditType.add_gap]))["rejectable"] is False
    v = present(Edit(id="x", type=EditType.add_term, payload=samples[EditType.add_term]))
    assert {f["label"]: f["value"] for f in v["fields"]}["Aditividade"] == "aditiva"


def test_present_applies_reviewer_edits():
    e = Edit(id="add_class-1", type=EditType.add_class, payload={"name": "A", "label": "a", "comment": "c"})
    e.review = Review(decision="accept", reviewer="ana", reviewed_at="2026-11-03T00:00:00+00:00", edits={"comment": "editado"})
    assert {f["label"]: f["value"] for f in present(e)["fields"]}["Comentário"] == "editado"


def test_stage_starts_at_one_on_an_empty_project(project):
    st = current_stage(project)
    assert st["number"] == 1 and st["requirements_closed"] is False and st["stages"][0]["status"] == "active"
    assert any("caso de uso" in m for m in st["missing"]) and st["next_step"]


def test_stage_moves_with_the_project(seeded):
    st = current_stage(seeded)  # demo: requisitos fechados, classes, termos e mappings, validate ainda nao rodou
    assert st["number"] == 4 and st["counts"]["mappings"] > 0 and st["stages"][2]["status"] == "completed"
    from akme.tools.profile import profile
    from akme.tools.validate import validate
    profile(seeded)
    validate(seeded)
    assert current_stage(seeded)["number"] == 5
    (seeded.docs_dir / "publish").mkdir(parents=True, exist_ok=True)
    (seeded.docs_dir / "publish" / "x.sql").write_text("x")
    assert current_stage(seeded)["number"] == 6
    cls = ontology_write.propose_edit(seeded, "add_class", {"name": "Fornecedor", "label": "f", "comment": "c"})
    st = current_stage(seeded)
    assert st["number"] == 2 and st["pending_by_stage"][2] == 1 and st["undecided"] == 1 and "Decida" in st["next_step"]
    ontology_write.review_edit(seeded, cls.id, "accept", "ana")
    assert current_stage(seeded)["undecided"] == 0


@pytest.fixture
def server(seeded):
    srv = review_server.start(seeded, port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", seeded
    srv.shutdown()
    srv.server_close()


def _get(url):
    return json.loads(urllib.request.urlopen(url).read())


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_pending_carries_view_and_stage_and_data_endpoints(server):
    base, project = server
    ontology_write.propose_edit(project, "add_class", {"name": "Fornecedor", "label": "Fornecedor", "comment": "c"})
    pend = _get(base + "/api/pending")
    assert pend[0]["view"]["title"] == "Classe Fornecedor" and pend[0]["view"]["group"] == "class"
    st = _get(base + "/api/stage")
    assert st["number"] == 2 and st["label"].startswith("Etapa 2 de 6")
    data = _get(base + "/api/data")
    assert data["classes"] and data["pending"][0]["view"] and data["stage"]["number"] == 2 and data["token"]
    assert _get(base + "/api/status")["token"] == data["token"]


def test_events_report_change(server):
    base, project = server
    tok = _get(base + "/api/events?timeout=0")["token"]
    assert _get(base + f"/api/events?since={tok}&timeout=0") == {"token": tok, "changed": False}
    ontology_write.propose_edit(project, "add_glossary", {"acronym": "NFe", "meaning": "nota"})
    out = _get(base + f"/api/events?since={tok}&timeout=2")
    assert out["changed"] is True and out["token"] != tok


def test_review_and_apply_stage2_from_page(server):
    base, project = server
    cls = ontology_write.propose_edit(project, "add_class", {"name": "Fornecedor", "label": "Fornecedor", "comment": "c"})
    term = ontology_write.propose_edit(project, "add_term", {"name": "ruim", "class": "Cliente", "definition": "d"})
    code, body = _post(base + "/api/review", {"edit_id": cls.id, "decision": "accept", "reviewer": "ana", "edits": {"comment": "fornece"}})
    assert code == 200 and body["view"]["fields"][-1]["value"] == "fornece"
    assert _post(base + "/api/review", {"edit_id": term.id, "decision": "reject", "reviewer": "ana", "reason": "duplicado"})[0] == 200
    assert _post(base + "/api/apply", {"approved_by": "", "stage": "all"})[0] == 400
    assert _post(base + "/api/apply", {"approved_by": "ana", "stage": "errado"})[0] == 400
    code, out = _post(base + "/api/apply", {"approved_by": "ana", "stage": "ontology"})
    assert code == 200 and out["summary"]["applied_types"] == {"add_class": 1} and len(out["rejected"]) == 1
    assert out["stage_after"]["number"] >= 3 and ontology_write.list_pending(project) == []
    assert (project.docs_dir / "ontology.js").exists()


def test_apply_reports_batch_error_as_conflict(server, monkeypatch):
    base, project = server
    from akme.tools.batch import BatchError

    def boom(*a, **k):
        raise BatchError("lote abortado", [{"check": "x", "subject": "y", "message": "z"}])
    monkeypatch.setattr(review_server, "apply_reviewed", boom)
    code, body = _post(base + "/api/apply", {"approved_by": "ana"})
    assert code == 409 and body["new_errors"][0]["check"] == "x"


def test_cli_review_background_prints_url(project, monkeypatch):
    from typer.testing import CliRunner

    from akme import review_server as rs
    from akme.cli import app
    monkeypatch.chdir(project.root)
    monkeypatch.setattr(rs, "ensure_running", lambda project, port, open_browser: f"http://127.0.0.1:{port}/")
    result = CliRunner().invoke(app, ["review", "--background", "--no-open", "--port", "8799"])
    assert result.exit_code == 0 and "http://127.0.0.1:8799/" in result.output
    result = CliRunner().invoke(app, ["stage"])
    assert result.exit_code == 0 and "Especificar" in result.output


def test_ensure_running_reuses_live_server(server, monkeypatch):
    base, project = server
    port = int(base.rsplit(":", 1)[1])

    def no_spawn(*a, **k):
        raise AssertionError("nao deveria subir outro servidor")
    monkeypatch.setattr(subprocess, "Popen", no_spawn)
    assert review_server.ensure_running(project, port) == f"http://127.0.0.1:{port}/"


def test_evidence_text_accepts_several_json_objects_and_notes():
    from akme.tools.review_view import _parse_evidence_text
    two = '{"kind":"source","path":"a.csv","locator":"l1","quote":"x"}; {"kind":"source","path":"b.pdf","locator":"p3","quote":"y"}'
    out = _parse_evidence_text(two)
    assert [i["path"] for i in out] == ["a.csv", "b.pdf"]
    assert _parse_evidence_text("reuniao de kickoff") == [{"kind": "note", "note": "reuniao de kickoff"}]
    mixed = _parse_evidence_text('[{"kind":"source","path":"a","locator":"1","quote":"q"}] e conversa com a Ana')
    assert mixed[0]["path"] == "a" and mixed[1] == {"kind": "note", "note": "e conversa com a Ana"}
    assert _parse_evidence_text("{nao e json") == [{"kind": "note", "note": "{nao e json"}]
    e = Edit(id="x", type=EditType.add_term, payload={"name": "t", "class": "A", "definition": "d"}, evidence=two)
    assert [i["kind"] for i in present(e)["evidence"]] == ["source", "source"]
