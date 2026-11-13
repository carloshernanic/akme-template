"""Tela Exportar da pagina local: estado da exportacao (.env, plano, banco) e a carga pelo botao."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from akme import review_server
from akme.tools import neo4j_load, neo4j_page
from akme.tools.profile import profile
from neo4j_fakes import PASSWORD

SECRET_URI = "bolt://usuario:segredo-na-uri@host-teste:7687"
ENV = ("AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD", "AKME_NEO4J_BROWSER_URL")


@pytest.fixture
def no_env(monkeypatch):
    for var in ENV:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(neo4j_page, "browser_answers", lambda url, timeout=1.5: True)
    monkeypatch.setattr(neo4j_page, "container_state", lambda: {
        "docker": True, "name": "akme-neo4j", "exists": False, "status": None, "reason": None})


@pytest.fixture
def env(no_env, monkeypatch):
    monkeypatch.setenv("AKME_NEO4J_URI", SECRET_URI)
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)


def _state(monkeypatch, projetos=(), total=0, alheios=0, no_banco=None):
    def state(project, plan):
        return {"projetos": list(projetos), "total": total, "alheios": alheios, "legado": False,
                "no_banco": {label: 0 for label in plan.nodes} | (no_banco or {})}
    monkeypatch.setattr(neo4j_load, "destination_state", state)


def _token(project):
    return neo4j_page.export_status(project, 8765)["token"]


def _fake_load(monkeypatch):
    calls = []

    def load(project, plan, carga):
        calls.append(carga)
        return {"executed": 7, "removed": {"nodes": 12, "relationships": 3}}

    monkeypatch.setattr(neo4j_load, "load", load)
    monkeypatch.setattr(neo4j_load, "verify", lambda plan, name, concepts, terms=None: {"ok": True, "divergences": []})
    monkeypatch.setattr(neo4j_load, "has_apoc", lambda: False)
    return calls


def test_status_without_env_says_what_is_missing_and_still_previews(seeded, no_env):
    profile(seeded)
    st = neo4j_page.export_status(seeded, 8765)
    assert st["env"]["missing"] == ["AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD"]
    assert st["database"] is None and st["viewing"] is None
    assert st["plan"]["total_nodes"] == 43 and st["plan"]["problems"] == []
    assert {n["label"]: n["rows"] for n in st["plan"]["nodes"]} == {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
    assert all(n["linked"] for n in st["plan"]["nodes"])
    assert st["cli"] == "uv run akme publish --target neo4j --no-dry-run"
    docker = "\n".join(st["setup"]["docker"])
    assert "--publish=127.0.0.1:7474:7474 --publish=127.0.0.1:7687:7687" in docker
    assert "guide http://127.0.0.1:8765/neo4j/guia" in docker and "$AKME_NEO4J_PASSWORD" in docker


def test_setup_follows_the_ports_of_the_env(no_env, monkeypatch):
    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://127.0.0.1:17687")
    monkeypatch.setenv("AKME_NEO4J_BROWSER_URL", "http://localhost:17474")
    setup = neo4j_page.setup_lines(9000)
    assert "--publish=127.0.0.1:17474:7474 --publish=127.0.0.1:17687:7687" in "\n".join(setup["docker"])
    assert "AKME_NEO4J_URI=bolt://127.0.0.1:17687" in setup["env"] and "guide http://127.0.0.1:9000/" in "\n".join(setup["docker"])


def test_status_never_carries_credentials(seeded, env, monkeypatch):
    profile(seeded)
    _state(monkeypatch)
    text = json.dumps(neo4j_page.export_status(seeded, 8765))
    assert PASSWORD not in text and "segredo-na-uri" not in text
    assert "bolt://host-teste:7687" in text


def test_status_compares_database_and_source(seeded, env, monkeypatch):
    profile(seeded)
    _state(monkeypatch, projetos=["demo"], total=20, no_banco={"Cliente": 20})
    db = neo4j_page.export_status(seeded, 8765)["database"]
    assert db["connected"] and db["refusal"] is None and db["has_project"]
    assert db["nodes"]["Cliente"] == {"now": 20, "then": 8} and db["removed_nodes"] == 12 and db["large_removal"] == 12


def test_status_reports_refusal_and_connection_error_without_secrets(seeded, env, monkeypatch):
    profile(seeded)
    _state(monkeypatch, projetos=["outro"], total=5)
    db = neo4j_page.export_status(seeded, 8765)["database"]
    assert db["connected"] and "o banco ja tem o projeto outro" in db["refusal"]

    def down(project, plan):
        raise neo4j_load.PublishError(f"falha no Neo4j: recusado em {SECRET_URI} com {PASSWORD}")
    monkeypatch.setattr(neo4j_load, "destination_state", down)
    db = neo4j_page.export_status(seeded, 8765)["database"]
    assert db["connected"] is False and "falha no Neo4j" in db["error"]
    assert PASSWORD not in db["error"] and "segredo-na-uri" not in db["error"]


def test_status_warns_when_the_browser_does_not_answer(seeded, env, monkeypatch):
    profile(seeded)
    _state(monkeypatch)
    monkeypatch.setattr(neo4j_page, "browser_answers", lambda url, timeout=1.5: False)
    viewing = neo4j_page.export_status(seeded, 8765)["viewing"]
    assert viewing["browser_answers"] is False and viewing["guide_command"] == ":guide http://127.0.0.1:8765/neo4j/guia"


def test_status_reads_the_env_file_again(seeded, no_env):
    profile(seeded)
    assert neo4j_page.export_status(seeded, 8765)["env"]["missing"]
    (seeded.root / ".env").write_text("AKME_NEO4J_URI=bolt://127.0.0.1:7687\nAKME_NEO4J_USER=neo4j\n", encoding="utf-8")
    try:
        assert neo4j_page.export_status(seeded, 8765)["env"]["missing"] == ["AKME_NEO4J_PASSWORD"]
        (seeded.root / ".env").write_text("AKME_NEO4J_USER=neo4j\n", encoding="utf-8")  # linha apagada deixa de valer
        assert neo4j_page.export_status(seeded, 8765)["env"]["missing"] == ["AKME_NEO4J_URI", "AKME_NEO4J_PASSWORD"]
    finally:
        import os
        for var in ENV:
            os.environ.pop(var, None)


def test_load_needs_confirmation_and_env(seeded, no_env, monkeypatch):
    profile(seeded)
    calls = _fake_load(monkeypatch)
    with pytest.raises(neo4j_page.LoadRefused) as e:
        neo4j_page.export_load(seeded, 8765, confirmed="true")
    assert e.value.code == 400 and "confirme" in str(e.value)
    with pytest.raises(neo4j_page.LoadRefused) as e:
        neo4j_page.export_load(seeded, 8765, confirmed=True)
    assert e.value.code == 400 and "AKME_NEO4J_PASSWORD" in str(e.value) and calls == []


def test_load_runs_and_reports(seeded, env, monkeypatch):
    profile(seeded)
    calls = _fake_load(monkeypatch)
    _state(monkeypatch)
    out = neo4j_page.export_load(seeded, 8765, confirmed=True, token=_token(seeded))
    assert len(calls) == 1 and out["loaded"] and out["total_nodes"] == 43 and out["total_relationships"] == 44
    assert out["removed"] == {"nodes": 12, "relationships": 3} and out["verification"]["ok"]
    assert PASSWORD not in json.dumps(out)


def test_load_refuses_other_project_problems_and_large_removal(seeded, env, monkeypatch):
    profile(seeded)
    calls = _fake_load(monkeypatch)
    _state(monkeypatch, projetos=["outro"], total=5)
    with pytest.raises(neo4j_page.LoadRefused) as e:
        neo4j_page.export_load(seeded, 8765, confirmed=True, token=_token(seeded))
    assert "o banco ja tem o projeto outro" in str(e.value) and e.value.code == 409

    _state(monkeypatch, projetos=["demo"], total=20, no_banco={"Cliente": 20})
    for typed in (None, "5", ""):
        with pytest.raises(neo4j_page.LoadRefused) as e:
            neo4j_page.export_load(seeded, 8765, confirmed=True, removed=typed, token=_token(seeded))
        assert e.value.extra == {"large_removal": 12} and "digite 12" in str(e.value)
    assert calls == []
    assert neo4j_page.export_load(seeded, 8765, confirmed=True, removed="12", token=_token(seeded))["loaded"]
    assert len(calls) == 1

    (seeded.root / "data" / "clientes.csv").write_text("id_cliente,nm_cliente\n1,a\n1,b\n", encoding="utf-8")
    with pytest.raises(neo4j_page.LoadRefused) as e:
        neo4j_page.export_load(seeded, 8765, confirmed=True, token="qualquer")
    assert e.value.extra.get("problems") and len(calls) == 1


def test_only_one_load_at_a_time(seeded, env, monkeypatch):
    profile(seeded)
    _fake_load(monkeypatch)
    _state(monkeypatch)
    token = _token(seeded)
    assert neo4j_page._LOAD.acquire(blocking=False)
    try:
        with pytest.raises(neo4j_page.LoadRefused) as e:
            neo4j_page.export_load(seeded, 8765, confirmed=True, token=token)
        assert "em andamento" in str(e.value)
        with pytest.raises(neo4j_page.LoadRefused) as e:  # a conferencia tambem espera: as duas escrevem em docs/publish
            neo4j_page.export_status(seeded, 8765)
        assert "em andamento" in str(e.value)
    finally:
        neo4j_page._LOAD.release()
    assert neo4j_page.export_load(seeded, 8765, confirmed=True, token=token)["loaded"]


@pytest.fixture
def server(seeded):
    srv = review_server.start(seeded, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", seeded
    srv.shutdown()
    srv.server_close()


def _post(url, body, origin=None):
    headers = {"Content-Type": "application/json"} | ({"Origin": origin} if origin else {})
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def test_routes_status_and_load(server, env, monkeypatch):
    base, project = server
    profile(project)
    calls = _fake_load(monkeypatch)
    _state(monkeypatch)
    st = json.loads(urllib.request.urlopen(base + "/api/neo4j").read())
    assert st["database"]["connected"] and st["plan"]["total_nodes"] == 43
    assert f"guide {base}/neo4j/guia" in "\n".join(st["setup"]["docker"])
    # a carga so parte da pagina: sem Origin (curl, script) e de outra origem, nada
    assert _post(base + "/api/neo4j/carga", {"confirmed": True})[0] == 403
    assert _post(base + "/api/neo4j/carga", {"confirmed": True}, origin="http://evil.example")[0] == 403
    assert _post(base + "/api/neo4j/carga", {}, origin=base)[0] == 400 and calls == []
    assert _post(base + "/api/neo4j/carga", {"confirmed": True}, origin=base)[1].get("stale") is True, "sem a marca"
    code, out = _post(base + "/api/neo4j/carga", {"confirmed": True, "token": st["token"]}, origin=base)
    assert code == 200 and out["loaded"] and len(calls) == 1
    # outro site aberto no navegador nao dispara a conferencia (ela le as fontes e conecta no banco)
    req = urllib.request.Request(base + "/api/neo4j", headers={"Sec-Fetch-Site": "cross-site"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def test_page_has_the_export_tab(server):
    base, project = server
    from akme.tools.export import export
    export(project)
    page = urllib.request.urlopen(base + "/").read().decode()
    assert 'id="tab-exportar"' in page and 'id="view-exportar"' in page and "exportar.js" in page
    assert urllib.request.urlopen(base + "/exportar.js").status == 200
    assert "neo4j_exportar" in json.loads(urllib.request.urlopen(base + "/api/versao").read())["recursos"]


def test_short_or_placeholder_password_stops_before_connecting(seeded, env, monkeypatch):
    profile(seeded)

    def must_not_connect(project, plan):
        raise AssertionError("senha invalida: nem tenta conectar")
    monkeypatch.setattr(neo4j_load, "destination_state", must_not_connect)
    for bad, flag in (("12345", "password_short"), ("<invente uma senha de 8 caracteres ou mais>", "password_placeholder")):
        monkeypatch.setenv("AKME_NEO4J_PASSWORD", bad)
        st = neo4j_page.export_status(seeded, 8765)
        assert st["env"][flag] is True and st["database"] is None
        if flag == "password_short":
            assert bad not in json.dumps(st["env"]), "a senha nunca sai"


def test_refused_connection_says_the_database_is_off_and_looks_at_the_container(seeded, env, monkeypatch):
    profile(seeded)

    def refused(project, plan):
        raise neo4j_load.PublishError("falha no Neo4j: Couldn't connect to 127.0.0.1:7687 (reason [Errno 61] Connection refused)")
    monkeypatch.setattr(neo4j_load, "destination_state", refused)
    monkeypatch.setattr(neo4j_page, "container_state", lambda: {
        "docker": True, "name": "akme-neo4j", "exists": True, "status": "exited", "reason": "senha_curta"})
    st = neo4j_page.export_status(seeded, 8765)
    assert st["database"]["kind"] == "desligado" and st["container"]["reason"] == "senha_curta" and st["viewing"] is None

    def denied(project, plan):
        raise neo4j_load.PublishError("falha no Neo4j: The client is unauthorized due to authentication failure.")
    monkeypatch.setattr(neo4j_load, "destination_state", denied)
    assert neo4j_page.export_status(seeded, 8765)["database"]["kind"] == "senha"


def test_container_state_reads_docker_without_leaking_the_log(monkeypatch):
    answers = {"version": "27.0", "inspect": "exited\n",
               "logs": "Invalid value for password. The minimum password length is 8 characters.\nsegredo-no-log"}
    monkeypatch.setattr(neo4j_page, "_docker", lambda *a: answers.get(a[0]))
    state = neo4j_page.container_state()
    assert state == {"docker": True, "name": "akme-neo4j", "exists": True, "status": "exited", "reason": "senha_curta"}
    answers["inspect"] = None
    assert neo4j_page.container_state()["exists"] is False
    answers["version"] = None
    assert neo4j_page.container_state()["docker"] is False


def test_load_refuses_when_the_preview_is_no_longer_what_the_human_saw(seeded, env, monkeypatch):
    profile(seeded)
    calls = _fake_load(monkeypatch)
    _state(monkeypatch)
    token = _token(seeded)
    for stale in (None, "", "outra-marca"):
        with pytest.raises(neo4j_page.LoadRefused) as e:
            neo4j_page.export_load(seeded, 8765, confirmed=True, token=stale)
        assert e.value.extra == {"stale": True} and "Conferir de novo" in str(e.value)
    # a origem mudou depois da previa: a marca antiga nao vale mais
    data = seeded.root / "data" / "clientes.csv"
    lines = data.read_text(encoding="utf-8").splitlines()
    data.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(neo4j_page.LoadRefused) as e:
        neo4j_page.export_load(seeded, 8765, confirmed=True, token=token)
    assert e.value.extra.get("stale") or e.value.extra.get("problems")
    # o destino mudou no .env: idem
    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://outro-host:7687")
    with pytest.raises(neo4j_page.LoadRefused):
        neo4j_page.export_load(seeded, 8765, confirmed=True, token=token)
    assert calls == []


def test_failure_after_the_write_started_never_says_nothing_was_written(seeded, env, monkeypatch):
    profile(seeded)
    _fake_load(monkeypatch)
    _state(monkeypatch)
    monkeypatch.setattr(neo4j_load, "verify", lambda plan, name, concepts, terms=None: {
        "ok": False, "divergences": ["contem: esperado 17, encontrado 0"]})
    with pytest.raises(neo4j_page.LoadRefused) as e:
        neo4j_page.export_load(seeded, 8765, confirmed=True, token=_token(seeded))
    assert e.value.extra == {"started": True} and "carga executada, mas o banco diverge" in str(e.value)
    assert "nada foi gravado" not in str(e.value).lower()


def test_password_with_shell_characters_is_refused_before_any_command(seeded, env, monkeypatch):
    profile(seeded)
    monkeypatch.setattr(neo4j_load, "destination_state", lambda project, plan: (_ for _ in ()).throw(AssertionError("nao conecta")))
    for bad in ("Abc$1xyz99", "senha com espaco", "abc#12345", "a&b!cdefgh"):
        monkeypatch.setenv("AKME_NEO4J_PASSWORD", bad)
        st = neo4j_page.export_status(seeded, 8765)
        assert st["env"]["password_chars"] is True and st["database"] is None, bad
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", "Senha_boa-2026.x")
    assert neo4j_page.env_state()["password_chars"] is False


def test_status_keeps_the_guide_of_a_loaded_database(seeded, env, monkeypatch):
    profile(seeded)
    _state(monkeypatch, projetos=["demo"], total=43)
    monkeypatch.setattr(neo4j_load, "has_apoc", lambda: False)
    neo4j_page.export_status(seeded, 8765)
    guide = (seeded.docs_dir / "publish" / "neo4j_guia.html").read_text(encoding="utf-8")
    assert "apoc.create" not in guide, "banco sem APOC: a conferencia nao devolve o guia a forma generica"
