import json, threading, urllib.request, urllib.error
import pytest
from akme import review_server
from akme.tools import ontology_write

@pytest.fixture
def server(seeded):
    srv = review_server.start(seeded, port=0); t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", seeded
    srv.shutdown()
    srv.server_close()

def _get(url): return json.loads(urllib.request.urlopen(url).read())
def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp: return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")

def test_status_pending_and_static(server):
    base, project = server
    assert _get(base + "/api/status")["closed"] is True
    assert urllib.request.urlopen(base + "/").status == 200
    assert urllib.request.urlopen(base + "/api/pending").status == 200
    with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(base + "/../akme.yml")
    assert e.value.code in (403, 404)

def test_review_and_propose_endpoints(server):
    base, project = server
    e = ontology_write.propose_edit(project, "add_competency_question", {"question": "q", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]})
    assert _post(base + "/api/review", {"edit_id": e.id, "decision": "accept", "reviewer": "", "edits": {}})[0] == 400
    assert _post(base + "/api/review", {"edit_id": "add_gap-deadbeef", "decision": "accept", "reviewer": "ana"})[0] == 404
    assert _post(base + "/api/review", {"edit_id": e.id, "decision": "accept", "reviewer": "ana", "edits": {"priority": "high", "status": "approved"}})[0] == 200
    assert ontology_write.list_pending(project)[0].review.reviewer == "ana"
    assert _post(base + "/api/propose", {"type": "add_class", "payload": {}, "reviewer": "ana"})[0] == 400
    code, _ = _post(base + "/api/propose", {"type": "add_competency_question", "reviewer": "ana", "payload": {"question": "minha", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "conversation", "who": "ana", "when": "hoje"}], "priority": "low", "status": "approved"}})
    assert code == 200 and any(p.proposed_by == "ana" and p.review and p.review.decision == "accept" for p in ontology_write.list_pending(project))

def _raw(url, method="POST", headers=None, body=b"{}"):
    req = urllib.request.Request(url, data=body if method == "POST" else None, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req) as resp: return resp.status
    except urllib.error.HTTPError as e: return e.code

def test_rejects_cross_origin_and_bad_content_type(server):
    base, _ = server
    assert _raw(base + "/api/review", headers={"Content-Type": "text/plain"}) == 400
    assert _raw(base + "/api/review", headers={"Content-Type": "application/json", "Origin": "http://evil.example"}) == 403
    assert _raw(base + "/api/status", method="GET", headers={"Host": "evil.example"}) == 403

def test_propose_failure_leaves_no_orphan(server, monkeypatch):
    base, project = server
    before = [p.id for p in ontology_write.list_pending(project)]
    def boom(*a, **k): raise ontology_write.EditError("x")
    monkeypatch.setattr(review_server, "review_edit", boom)
    code, _ = _post(base + "/api/propose", {"type": "add_competency_question", "reviewer": "ana", "payload": {"question": "z", "type": "atributos", "concepts": ["X"]}})
    assert code == 400
    assert [p.id for p in ontology_write.list_pending(project)] == before


def test_cli_review_exports_before_serving(project, monkeypatch):
    from typer.testing import CliRunner

    from akme import review_server
    from akme.cli import app

    monkeypatch.chdir(project.root)
    called = {}
    monkeypatch.setattr(review_server, "serve", lambda project, port, open_browser: called.update(port=port, open=open_browser))
    result = CliRunner().invoke(app, ["review", "--no-open", "--port", "8799"])
    assert result.exit_code == 0, result.output
    assert called == {"port": 8799, "open": False}
    assert (project.root / "docs" / "ontology.js").exists()

def test_static_checks_host_and_hides_directories(server):
    base, project = server
    assert _raw(base + "/", method="GET", headers={"Host": "evil.example"}) == 403
    assert _raw(base + "/index.html", method="HEAD", headers={"Host": "evil.example"}) == 403
    (project.docs_dir / "sub").mkdir(parents=True, exist_ok=True); (project.docs_dir / "sub" / "a.txt").write_text("x")
    assert _raw(base + "/sub/", method="GET") == 404

def test_bad_edits_and_unexpected_errors_return_json(server, monkeypatch):
    base, project = server
    e = ontology_write.propose_edit(project, "add_competency_question", {"question": "q", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]})
    code, body = _post(base + "/api/review", {"edit_id": e.id, "decision": "accept", "reviewer": "ana", "edits": ["x"]})
    assert code == 400 and "edits" in body["error"]
    def boom(*a, **k): raise RuntimeError("quebrou")
    monkeypatch.setattr(review_server, "review_edit", boom)
    code, body = _post(base + "/api/review", {"edit_id": e.id, "decision": "accept", "reviewer": "ana"})
    assert code == 500 and "quebrou" in body["error"]
