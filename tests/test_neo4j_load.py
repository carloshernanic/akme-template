"""Carga em Cypher, sincronizacao e conferencia, contra uma sessao falsa que registra (consulta, parametros)."""
from __future__ import annotations

import re

import pytest
from neo4j_fakes import CARGA, CONCEPTS, EXPECTED_EDGES, EXPECTED_NODES, PASSWORD, _FakeSession

from akme.tools import neo4j_load
from akme.tools.neo4j_plan import build_plan
from akme.tools.publish import PublishError



def test_load_order_constraints_nodes_edges_ontology_then_sync(seeded, fake):
    session = fake["session"]
    result = neo4j_load.load(seeded, build_plan(seeded), CARGA)
    order = [session.index(f) for f in ("COLLECT", "CREATE CONSTRAINT", "CREATE INDEX", "db.awaitIndexes",
                                         "MERGE (m:_AkmeProjeto", "MERGE (n:", "MERGE (a)-[e:", "MERGE (c:Conceito",
                                         "DETACH DELETE", "DELETE r")]
    assert order == sorted(order)
    last_node = max(i for i, q in enumerate(session.queries()) if "MERGE (n:" in q)
    first_edge = session.index("MERGE (a)-[e:")
    assert last_node < first_edge, "todas as arestas depois de todos os nos"
    assert session.index("MATCH (a:Conceito") < session.index("DETACH DELETE")
    # 4 fontes com 1 bloco cada, 3 contratos com 1 bloco cada
    assert result["executed"] == 7 and session.unwinds == 7
    assert "removed" in result
    joined = "\n".join(session.queries())
    assert "CREATE CONSTRAINT `akme_uniq_Pedido` IF NOT EXISTS FOR (n:`Pedido`) REQUIRE n._id IS UNIQUE" in joined
    assert "CREATE CONSTRAINT `akme_conceito_uniq_projeto_nome` IF NOT EXISTS FOR (c:Conceito) REQUIRE (c._projeto, c.nome) IS UNIQUE" in joined
    index = neo4j_load._index_name("Cliente", "id_cliente")
    assert f"CREATE INDEX `{index}` IF NOT EXISTS FOR (n:`Cliente`) ON (n.`id_cliente`)" in joined


def test_every_statement_carries_project_and_round(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    for query, params in session.calls:
        if "$carga" in query:
            assert params["carga"] == CARGA
        if "$projeto" in query:
            assert params["projeto"] == "demo"
    ontology = [p for q, p in session.calls if "Conceito" in q and "MERGE" in q]
    assert len(ontology) == 17 and all(p["carga"] == CARGA for p in ontology)


def test_node_rows_have_typed_filled_properties(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    from datetime import date

    rows = {}
    for query, params in session.calls:
        if "MERGE (n:`Cliente`" in query:
            rows.update({r["id"]: r["p"] for r in params["rows"]})
    assert rows["1"]["dt_cadastro"] == date(2023, 1, 15)
    assert rows["1"]["id_cliente"] == "1" and rows["1"]["nm_cliente"] == "Construtora Horizonte"
    items = [r for q, p in session.calls if "MERGE (n:`ItemPedido`" in q for r in p["rows"]]
    first = next(r for r in items if r["id"] == "1001/CIM-50")
    assert first["p"]["qt_itens"] == 100 and first["p"]["vl_item"] == 3290.0
    assert all(v is not None and v != "" for r in items for v in r["p"].values())


def test_edges_match_target_by_join_value_as_stored(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    query, params = next((q, p) for q, p in session.calls if "[e:`pertenceA`]" in q)
    assert "MATCH (a:`Pedido` {_id: r.id}) MATCH (b:`Cliente` {`id_cliente`: r.v})" in query
    assert {"id": "1001", "v": "1"} in params["rows"]


def test_data_goes_only_as_parameters(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    for query in session.queries():
        assert "Construtora" not in query and "CIM-50" not in query


def test_nodes_replace_properties(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    nodes = [q for q in session.queries() if "MERGE (n:" in q]
    assert nodes and all("SET n = r.p" in q and "+=" not in q for q in nodes)


def test_failed_batch_skips_sync(seeded, fake):
    session = fake["use"](_FakeSession(fail_unwind=2))
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    message = str(exc.value)
    assert "lote 2 de 7 falhou" in message and "1 lote(s) ja gravado(s)" in message and "nada foi apagado" in message
    assert "repetir a carga completa e seguro" in message
    assert not any("DELETE" in q for q in session.queries())
    assert not any("MERGE (c:Conceito" in q for q in session.queries())


def test_sync_is_scoped_to_this_project_and_round(seeded, fake):
    session = fake["use"](_FakeSession(deleted=(3, 5)))
    result = neo4j_load.load(seeded, build_plan(seeded), CARGA)
    nodes = next((q, p) for q, p in session.calls if "DETACH DELETE" in q)
    edges = next((q, p) for q, p in session.calls if "DELETE r" in q and "DETACH" not in q)
    for query, params in (nodes, edges):
        assert "n['_projeto'] = $projeto" in query and "<> $carga" in query and "IN TRANSACTIONS OF 5000 ROWS" in query
        assert params == {"projeto": "demo", "carga": CARGA}
    assert "MATCH (n)-[r]->()" in edges[0]
    assert result["removed"] == {"nodes": 3, "relationships": 5 + 5}


def test_legacy_n10s_database_is_refused(seeded, fake):
    session = fake["use"](_FakeSession(state={"total": 40, "legado": True}))
    with pytest.raises(PublishError, match="exportacao antiga \\(n10s\\)") as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert "Nada foi gravado" in str(exc.value)
    assert not any(q.startswith(("CREATE", "MERGE", "UNWIND")) for q in session.queries())


def test_legacy_constraint_alone_marks_the_database_as_legacy(seeded, fake):
    session = fake["use"](_FakeSession(legacy_constraint=True))
    with pytest.raises(PublishError, match="n10s"):
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert not any(q.startswith(("CREATE", "MERGE", "UNWIND")) for q in session.queries())


def test_load_rechecks_destination_before_writing(seeded, fake):
    session = fake["use"](_FakeSession(state={"projetos": ["outro"], "total": 58}))
    with pytest.raises(PublishError, match="projeto outro.*Nada foi gravado"):
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert not any(q.startswith(("CREATE", "MERGE", "UNWIND")) for q in session.queries())


def test_foreign_nodes_are_refused():
    assert check({"projetos": ["demo"], "total": 9, "alheios": 2, "legado": False, "no_banco": {}})[1]


def check(state):
    return neo4j_load.check_destination(state, "demo")


@pytest.mark.parametrize("state,expected", [
    ({"projetos": [], "total": 0, "alheios": 0, "legado": False}, None),
    ({"projetos": ["demo"], "total": 58, "alheios": 0, "legado": False}, None),
    ({"projetos": ["outro"], "total": 58, "alheios": 0, "legado": False}, "projeto outro"),
    ({"projetos": ["demo", "outro"], "total": 90, "alheios": 0, "legado": False}, "mais de um projeto"),
    ({"projetos": [], "total": 43, "alheios": 43, "legado": False}, "sem a marca"),
    ({"projetos": ["demo"], "total": 60, "alheios": 2, "legado": False}, "2 no"),
    ({"projetos": ["demo"], "total": 60, "alheios": 50, "legado": True}, "exportacao antiga (n10s)"),
    ({"projetos": [], "total": 0, "alheios": 0, "legado": True}, "limpe-o com o comando do guia"),
])
def test_destination_rules(state, expected):
    description, refusal = check({**state, "no_banco": {}})
    assert (refusal is None) if expected is None else (expected in refusal)
    assert description


def test_destination_state_reads_without_writing(seeded, fake):
    session = fake["use"](_FakeSession(state={"projetos": ["demo"], "total": 60, "no_banco": {"Cliente": 9, "Antiga": 2}}))
    state = neo4j_load.destination_state(seeded, build_plan(seeded))
    assert state["projetos"] == ["demo"] and state["legado"] is False
    assert state["no_banco"] == {"Antiga": 2, "Cliente": 9, "ItemPedido": 0, "Pedido": 0, "Produto": 0}
    assert not any(re.search(r"\b(CREATE|MERGE|DELETE|SET)\b", q) for q in session.queries())


def test_verify_counts_by_label(seeded, fake):
    session = fake["session"]
    result = neo4j_load.verify(build_plan(seeded), "demo", CONCEPTS)
    assert result == {"ok": True, "divergences": []}
    joined = "\n".join(session.queries())
    assert "(:`Pedido`)-[r:`pertenceA`]->(:`Cliente`)" in joined
    assert "MATCH (n:`Cliente`) WHERE n._projeto = $p" in joined
    assert "MATCH (c:Conceito {_projeto: $p})" in joined
    assert all(p.get("p") == "demo" for q, p in session.calls if "$p" in q)


def test_verify_reports_divergence(seeded, fake):
    fake["use"](_FakeSession(counts={"Cliente": 9, "contem": 0, "Conceito": 8}))
    result = neo4j_load.verify(build_plan(seeded), "demo", CONCEPTS)
    assert result["ok"] is False
    assert "Cliente: esperado 8, encontrado 9" in result["divergences"]
    assert "contem: esperado 17, encontrado 0" in result["divergences"]
    assert "Conceito: esperado 9, encontrado 8" in result["divergences"]


def _model(project):
    return {"project": project.name, "version": "0.1.0"}


def test_dry_run_writes_cypher_artifact_and_does_not_connect(seeded, monkeypatch):
    def must_not_connect(*a, **k):
        raise AssertionError("dry-run nao pode conectar")

    monkeypatch.setattr(neo4j_load, "_driver", must_not_connect)
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)
    artifact = seeded.docs_dir / "publish" / "neo4j.cypher"
    assert r["artifact"] == str(artifact) and artifact.exists()
    text = artifact.read_text(encoding="utf-8")
    assert "Conceito" in text and "NAO EXECUTE" not in text
    assert "UNWIND $rows AS r MERGE (n:`Pedido` {_id: r.id})" in text
    assert "Construtora" not in text, "os dados nao vao para o artefato"
    assert set(r) == {"target", "dry_run", "artifact", "rows", "batches", "executed", "nodes", "relationships",
                      "relations_not_published", "sources_skipped", "problems", "warnings"}
    assert r["dry_run"] and r["executed"] == 0 and r["rows"] == 43 and r["batches"] == 7
    assert r["nodes"] == EXPECTED_NODES and r["relationships"] == EXPECTED_EDGES
    assert not (seeded.docs_dir / "publish" / "neo4j.nt").exists()


def _break_demo(project):
    path = project.root / "data" / "clientes.csv"
    path.write_text(path.read_text(encoding="utf-8") + "1,Repetido,0,SP,2023-01-01,S\n", encoding="utf-8")


def test_artifact_says_do_not_run_when_problems(seeded):
    _break_demo(seeded)
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)
    assert r["problems"]
    text = (seeded.docs_dir / "publish" / "neo4j.cypher").read_text(encoding="utf-8")
    assert text.startswith("// NAO EXECUTE") or "\n// NAO EXECUTE" in text.split("\n\n")[0]
    assert "clientes.id_cliente" in text


def test_load_is_refused_when_plan_has_problems(seeded, fake):
    _break_demo(seeded)
    with pytest.raises(PublishError, match="carga recusada, nada foi gravado"):
        neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=False)
    assert fake["session"].calls == []


def test_publish_loads_then_verifies(seeded, fake):
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=False)
    assert r["executed"] == r["batches"] == 7
    assert r["verification"] == {"ok": True, "divergences": []}
    assert r["removed"] == {"nodes": 0, "relationships": 0}
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", r["carga"])


def test_publish_fails_on_divergence(seeded, fake):
    fake["use"](_FakeSession(counts={"pertenceA": 11}))
    with pytest.raises(PublishError, match="pertenceA: esperado 10, encontrado 11"):
        neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=False)


def test_errors_never_show_password(seeded, fake):
    neo4j = pytest.importorskip("neo4j")
    fake["use"](_FakeSession(error=neo4j.exceptions.ClientError(f"falha de autenticacao com {PASSWORD}")))
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert PASSWORD not in str(exc.value) and "falha" in str(exc.value)


def test_batch_error_never_shows_password(seeded, fake):
    session = fake["use"](_FakeSession(fail_unwind=1))
    import neo4j

    def run(query, parameters=None, **params):
        if query.startswith("UNWIND $rows"):
            raise neo4j.exceptions.ClientError(f"erro com {PASSWORD} no texto")
        return _FakeSession.run(session, query, parameters, **params)

    session.run = run
    with pytest.raises(PublishError, match="lote 1 de 7 falhou") as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert PASSWORD not in str(exc.value) and "0 lote(s) ja gravado(s)" in str(exc.value)


def test_preview_lines_show_database_against_source(seeded):
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)
    plain = "\n".join(neo4j_load.preview_lines(r))
    assert "linhas: 43" in plain and "7 lote(s)" in plain and "Pedido: 10" in plain and "pertenceA: 10" in plain
    assert "banco" not in plain
    state = {"projetos": ["demo"], "total": 60, "alheios": 0, "legado": False, "no_banco": {"Cliente": 9, "Antiga": 2}}
    lines = neo4j_load.preview_lines(r, state)
    assert "  Cliente: banco 9 -> origem 8" in lines and "  Antiga: banco 2 -> origem 0" in lines
    assert "  Pedido: banco 0 -> origem 10" in lines
    assert any("a carga apaga deste projeto o que nao vier da origem nesta carga" in line for line in lines)


@pytest.mark.parametrize("uri,browser", [
    ("bolt://127.0.0.1:7687", "http://localhost:7474"),
    ("neo4j+s://abc123.databases.neo4j.io", "https://console.neo4j.io"),
    ("bolt://grafo.cliente.com:7687", "http://grafo.cliente.com:7474"),
])
def test_viewing_lines_point_to_the_browser(seeded, monkeypatch, uri, browser):
    monkeypatch.setenv("AKME_NEO4J_URI", uri)
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)
    text = "\n".join(neo4j_load.viewing_lines(seeded, r))
    assert browser in text and "neo4j" in text and PASSWORD not in text
    assert "MATCH p = (:Pedido)-[:pertenceA]->(:Cliente) RETURN p LIMIT 50" in text
    assert "MATCH (n)-[r]->(m) WHERE NOT n:Conceito RETURN n, r, m LIMIT 300   // os dados" in text
    assert "MATCH p = (:Conceito)-->(:Conceito) RETURN p   // a ontologia: conceitos e relacoes" in text


def test_destination_hides_credentials_in_uri(monkeypatch):
    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://usuario:segredo@host-teste:7687")
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    assert neo4j_load.destination() == "bolt://host-teste:7687"


def test_invalid_value_found_during_load_fails_as_a_batch(seeded, fake):
    session = fake["session"]
    plan = build_plan(seeded)
    path = seeded.root / "data" / "clientes.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("2023-01-15", "nao-e-data"), encoding="utf-8")
    with pytest.raises(PublishError, match="lote 1 de 7 falhou.*0 lote\\(s\\) ja gravado\\(s\\); nada foi apagado"):
        neo4j_load.load(seeded, plan, CARGA)
    assert not any("DELETE" in q for q in session.queries())


def test_source_that_changed_since_the_plan_skips_sync(seeded, fake):
    session = fake["session"]
    plan = build_plan(seeded)
    path = seeded.root / "data" / "clientes.csv"
    path.write_text("\n".join(path.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(PublishError, match="a origem mudou durante a carga: clientes \\(8 no plano, 7 agora\\).*nada foi apagado"):
        neo4j_load.load(seeded, plan, CARGA)
    assert not any("DELETE" in q for q in session.queries())
    assert not any("MERGE (c:Conceito" in q for q in session.queries())


def test_load_called_with_problems_does_not_connect(seeded, fake):
    plan = build_plan(seeded)
    plan.problems.append("fonte x sem chave")
    with pytest.raises(PublishError, match="carga recusada, nada foi gravado: fonte x sem chave"):
        neo4j_load.load(seeded, plan, CARGA)
    assert fake["session"].calls == []


def _rename_column(project, old, new):
    """Renomeia a coluna nos CSVs e no content.yml (chave, join e mappings), como se a origem se chamasse assim."""
    from akme.project import Project

    for path in (project.content_path, project.root / "data" / "clientes.csv", project.root / "data" / "pedidos.csv"):
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    return Project(project.root)


def _names(queries):
    return [re.match(r"CREATE (?:CONSTRAINT|INDEX) `([^`]+)`", q).group(1) for q in queries if q.startswith("CREATE ")]


def test_index_and_constraint_names_never_collide(seeded, fake):
    project = _rename_column(seeded, "id_cliente", "id")
    plan = build_plan(project)
    assert not plan.problems and any(e.to_column == "id" for e in plan.edges)
    session = fake["session"]
    neo4j_load.load(project, plan, CARGA)
    names = _names(session.queries())
    assert len(names) == len(set(names)) == 4 + 1 + 3
    assert neo4j_load._index_name("Cliente", "id") != neo4j_load._constraint_name("Cliente")
    assert neo4j_load._index_name("A_b", "c") != neo4j_load._index_name("A", "b_c")
    assert neo4j_load._index_name("Conceito", "x") != neo4j_load.CONCEPT_CONSTRAINT_NAME
    assert any(q.startswith("CREATE INDEX") and "FOR (n:`Cliente`) ON (n.`id`)" in q for q in session.queries())


def test_column_with_space_keeps_its_name(seeded, fake):
    project = _rename_column(seeded, "id_cliente", "nome cliente")
    plan = build_plan(project)
    assert not plan.problems and plan.relationships["pertenceA"] == 10
    session = fake["session"]
    neo4j_load.load(project, plan, CARGA)
    rows = [r for q, p in session.calls if "MERGE (n:`Cliente`" in q for r in p["rows"]]
    assert rows[0]["p"]["nome cliente"] == "1" and "nome_cliente" not in rows[0]["p"]
    index = next(q for q in session.queries() if q.startswith("CREATE INDEX") and "`Cliente`" in q)
    assert "ON (n.`nome cliente`)" in index
    edge, params = next((q, p) for q, p in session.calls if "[e:`pertenceA`]" in q)
    assert "MATCH (b:`Cliente` {`nome cliente`: r.v})" in edge and {"id": "1001", "v": "1"} in params["rows"]


class _ShrinkingAdapter:
    """Adapter real da pasta, mas a segunda leitura de pedidos (a das arestas) vem com uma linha a menos."""

    def __init__(self, real, fail=None):
        self.real, self.reads, self.fail = real, {}, fail

    def iter_rows(self, source, batch=5000):
        self.reads[source] = self.reads.get(source, 0) + 1
        if self.fail:
            raise RuntimeError(self.fail)
        for block in self.real.iter_rows(source, batch):
            yield block[:-1] if source == "pedidos" and self.reads[source] == 2 else block

    def close(self):
        self.real.close()


def test_origin_that_shrinks_before_the_edge_pass_skips_sync(seeded, fake, monkeypatch):
    real = neo4j_load.load_adapter
    monkeypatch.setattr(neo4j_load, "load_adapter", lambda name, opts: _ShrinkingAdapter(real(name, opts)))
    session = fake["session"]
    with pytest.raises(PublishError, match="a origem mudou durante a carga: pedidos \\(10 no plano, 9 agora\\).*nada foi apagado"):
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert not any("DELETE" in q for q in session.queries())


def test_adapter_error_mid_load_is_a_batch_failure_without_secrets(seeded, fake, monkeypatch):
    from akme.project import Project, read_yaml, write_yaml

    config = read_yaml(seeded.root / "akme.yml")
    config["local_folder"]["dsn"] = "env:AKME_TEST_DSN"
    write_yaml(seeded.root / "akme.yml", config)
    monkeypatch.setenv("AKME_TEST_DSN", "postgresql://u:segredo-do-banco@h/db")
    project = Project(seeded.root)
    plan = build_plan(seeded)
    real = neo4j_load.load_adapter
    monkeypatch.setattr(neo4j_load, "load_adapter", lambda name, opts: _ShrinkingAdapter(
        real(name, {"path": opts["path"]}), fail="conexao perdida com postgresql://u:segredo-do-banco@h/db"))
    session = fake["session"]
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(project, plan, CARGA)
    message = str(exc.value)
    assert "lote 1 de 7 falhou" in message and "0 lote(s) ja gravado(s); nada foi apagado" in message
    assert "segredo-do-banco" not in message and "conexao perdida" in message
    assert not any("DELETE" in q for q in session.queries())


def test_ontology_failure_skips_sync(seeded, fake):
    neo4j = pytest.importorskip("neo4j")
    session = fake["session"]
    original = session.run

    def run(query, parameters=None, **params):
        if "MERGE (c:Conceito" in query:
            session.calls.append((query, {**(parameters or {}), **params}))
            raise neo4j.exceptions.ClientError("ontologia quebrada")
        return original(query, parameters, **params)

    session.run = run
    with pytest.raises(PublishError, match="ontologia: comando 1 de 17 falhou.*7 lote\\(s\\) ja gravado\\(s\\); nada foi apagado"):
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert not any("DELETE" in q for q in session.queries())


def _clientes_rows(session):
    return {r["id"]: r["p"] for q, p in session.calls if "MERGE (n:`Cliente`" in q for r in p["rows"]}


def _without_declared_types(project):
    from akme.project import Project, read_yaml, write_yaml

    content = read_yaml(project.content_path)
    for entry in content.get("sources") or []:
        entry["types"] = {}
    write_yaml(project.content_path, content)
    return Project(project.root)


def test_undeclared_column_stays_original_text(seeded, fake):
    project = _without_declared_types(seeded)
    neo4j_load.load(project, build_plan(project), CARGA)
    row = _clientes_rows(fake["session"])["1"]
    assert row["dt_cadastro"] == "2023-01-15" and isinstance(row["dt_cadastro"], str)
    assert row["cnpj"] == "12345678000101"


def test_type_does_not_depend_on_the_data(seeded, fake):
    project = _without_declared_types(seeded)
    path = project.root / "data" / "clientes.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("12345678000101", "00123"), encoding="utf-8")
    neo4j_load.load(project, build_plan(project), CARGA)
    assert _clientes_rows(fake["session"])["1"]["cnpj"] == "00123"


def test_node_identity_does_not_depend_on_row_order(seeded, fake):
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    before = _clientes_rows(fake["session"])
    path = seeded.root / "data" / "clientes.csv"
    head, *rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([head, *reversed(rows)]) + "\n", encoding="utf-8")
    again = fake["use"](_FakeSession())
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert _clientes_rows(again) == before


def test_driver_connection_failure_becomes_a_clear_error(seeded, fake, monkeypatch):
    neo4j = pytest.importorskip("neo4j")

    def unreachable(*a, **k):
        raise neo4j.exceptions.ServiceUnavailable(f"nao conectou com {PASSWORD}")

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", unreachable)
    with pytest.raises(PublishError, match="falha no Neo4j") as exc:
        neo4j_load.verify(build_plan(seeded), "demo", CONCEPTS)
    assert PASSWORD not in str(exc.value)
    with pytest.raises(PublishError, match="falha no Neo4j") as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert PASSWORD not in str(exc.value)
