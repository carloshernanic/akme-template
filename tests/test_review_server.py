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


def test_neo4j_guide_route_serves_the_guide_with_cors(server):
    base, project = server
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(base + "/neo4j/guia")
    assert e.value.code == 404 and "publish --target neo4j" in json.loads(e.value.read())["error"]
    path = project.docs_dir / "publish" / "neo4j_guia.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<article class=\"guide\">ola</article>", encoding="utf-8")
    req = urllib.request.Request(base + "/neo4j/guia", headers={"Origin": "http://localhost:7474"})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:7474", "reflete a origem, nunca *"
        assert "Origin" in resp.headers["Vary"]
        assert resp.headers["Content-Type"].startswith("text/html")
        assert resp.read().decode() == "<article class=\"guide\">ola</article>"
    # preflight (navegador que pede permissao para rede local) tambem responde com CORS
    opt = urllib.request.Request(base + "/neo4j/guia", method="OPTIONS",
                                 headers={"Origin": "https://console.neo4j.io", "Access-Control-Request-Method": "GET"})
    with urllib.request.urlopen(opt) as resp:
        assert resp.status == 204 and resp.headers["Access-Control-Allow-Origin"] == "https://console.neo4j.io"
        assert resp.headers["Access-Control-Allow-Private-Network"] == "true"


@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost:8765", "http://127.0.0.1:9999", "null"])
def test_guide_cors_refuses_other_origins(server, origin):
    base, project = server
    path = project.docs_dir / "publish" / "neo4j_guia.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("guia", encoding="utf-8")
    for method in ("GET", "OPTIONS"):
        req = urllib.request.Request(base + "/neo4j/guia", method=method, headers={"Origin": origin})
        with urllib.request.urlopen(req) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") is None
            assert resp.headers.get("Access-Control-Allow-Private-Network") is None


def test_guide_cors_accepts_the_configured_browser_port(server, monkeypatch):
    base, project = server
    monkeypatch.setenv("AKME_NEO4J_BROWSER_URL", "http://localhost:17474")
    path = project.docs_dir / "publish" / "neo4j_guia.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("guia", encoding="utf-8")
    for origin in ("http://localhost:17474", "http://127.0.0.1:17474", "https://127.0.0.1:7474"):
        req = urllib.request.Request(base + "/neo4j/guia", headers={"Origin": origin})
        with urllib.request.urlopen(req) as resp:
            assert resp.headers["Access-Control-Allow-Origin"] == origin


def test_head_on_the_guide_route_answers_like_get(server):
    base, project = server
    path = project.docs_dir / "publish" / "neo4j_guia.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("guia", encoding="utf-8")
    with urllib.request.urlopen(urllib.request.Request(base + "/neo4j/guia", method="HEAD")) as resp:
        assert resp.status == 200 and resp.headers["Content-Length"] == "4" and resp.read() == b""


def test_version_route_and_header(server):
    from akme import __version__
    base, _ = server
    with urllib.request.urlopen(base + "/api/versao") as resp:
        assert json.loads(resp.read()) == {"akme": __version__, "recursos": list(review_server.FEATURES)}
        assert resp.headers["X-Akme-Versao"] == __version__
    port = int(base.rsplit(":", 1)[1])
    assert review_server.stale_message(port) is None


def test_stale_server_is_detected_and_never_killed(server, monkeypatch):
    """Servidor de codigo antigo: responde /api/status, mas nao tem /api/versao (ou nao lista os recursos)."""
    import subprocess
    base, project = server
    port = int(base.rsplit(":", 1)[1])
    monkeypatch.setattr(review_server, "server_info", lambda port, timeout=1.0: None)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("nao sobe outro")))
    message = review_server.stale_message(port)
    assert message and "desatualizado" in message and "uv run akme review" in message
    with pytest.raises(RuntimeError, match="desatualizado"):
        review_server.ensure_running(project, port)
    monkeypatch.setattr(review_server, "server_info", lambda port, timeout=1.0: {"akme": "0.1.0", "recursos": []})
    assert review_server.stale_message(port)
    with urllib.request.urlopen(base + "/api/status") as resp:
        assert resp.status == 200, "o servidor antigo continua no ar: o akme so avisa"


def test_cli_review_says_the_server_is_stale(server, monkeypatch):
    from typer.testing import CliRunner

    from akme.cli import app
    base, project = server
    port = int(base.rsplit(":", 1)[1])
    monkeypatch.chdir(project.root)
    monkeypatch.setattr(review_server, "server_info", lambda port, timeout=1.0: None)
    for args in (["review", "--no-open", "--port", str(port)], ["review", "--background", "--no-open", "--port", str(port)]):
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 1 and "desatualizado" in result.output and "uv run akme review" in result.output


def test_stale_server_shows_in_the_guide_lines(monkeypatch):
    from akme.tools import neo4j_guide
    monkeypatch.undo()  # sem o duble do conftest: usa o _stale_lines real
    monkeypatch.setattr(review_server, "stale_message", lambda port: f"{review_server.STALE}; porta {port}")
    assert any("desatualizado" in line for line in neo4j_guide.guide_lines())


def test_cors_only_on_the_guide_route(server):
    base, _ = server
    with urllib.request.urlopen(urllib.request.Request(base + "/api/status", headers={"Origin": "http://x"})) as resp:
        assert resp.headers.get("Access-Control-Allow-Origin") is None


def test_guide_route_still_checks_the_host(server):
    base, project = server
    path = project.docs_dir / "publish" / "neo4j_guia.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    req = urllib.request.Request(base + "/neo4j/guia", headers={"Host": "evil.example:80"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def test_data_lists_profiled_columns_and_reviewer_corrects_mappings(server):
    from akme.ontology import load_content
    from akme.tools.profile import profile

    base, project = server
    assert _get(base + "/api/data")["source_columns"] == {}
    profile(project)
    cols = _get(base + "/api/data")["source_columns"]
    m = load_content(project)["mappings"][0]
    assert m["column"] in cols[m["source"]]
    other = next(c for c in cols[m["source"]] if c != m["column"])
    key = {"term": m["term"], "source": m["source"], "column": m["column"]}
    code, out = _post(base + "/api/propose", {"type": "update_mapping", "reviewer": "ana", "payload": key | {"set": {"note": "conferido"}}})
    assert code == 200 and out["proposed_by"] == "ana" and out["review"]["decision"] == "accept"
    # a segunda correcao do mesmo mapping volta com o motivo, e nada fica orfao em pending/
    n = len(ontology_write.list_pending(project))
    code, out = _post(base + "/api/propose", {"type": "remove_mapping", "reviewer": "ana", "payload": key | {"reason": "x"}})
    assert code == 400 and "correcao pendente" in out["error"]
    assert len(ontology_write.list_pending(project)) == n
    # trocar para uma coluna em que o termo ja esta mapeado: o erro do servidor chega para a pagina mostrar
    m2 = load_content(project)["mappings"][1]
    col2 = next(c for c in cols[m2["source"]] if c != m2["column"])
    extra = {k: v for k, v in m2.items() if k not in ("column", "note")} | {"column": col2}
    ontology_write.apply_edit(project, ontology_write.propose_edit(project, "add_mapping", extra).id, "tester")
    code, out = _post(base + "/api/propose", {"type": "update_mapping", "reviewer": "ana",
                                              "payload": {"term": m2["term"], "source": m2["source"], "column": m2["column"], "set": {"column": col2}}})
    assert code == 400 and "ja existe o mapping" in out["error"]
    assert len(ontology_write.list_pending(project)) == n
