"""Carga em Cypher, sincronizacao e conferencia, contra uma sessao falsa que registra (consulta, parametros)."""
from __future__ import annotations

import re

import pytest
from neo4j_fakes import CARGA, CONCEPTS, EXPECTED_EDGES, EXPECTED_NODES, PASSWORD, TERMS, _FakeSession

from akme.tools import neo4j_load
from akme.tools.neo4j_plan import build_plan
from akme.tools.publish import PublishError



def test_load_order_constraints_nodes_edges_ontology_then_sync(seeded, fake):
    session = fake["session"]
    result = neo4j_load.load(seeded, build_plan(seeded), CARGA)
    order = [session.index(f) for f in ("dbms.components", "COLLECT", "akme_projeto_uniq", "SET m.carga_atual",
                                         "CREATE CONSTRAINT `akme_uniq_",
                                         "CREATE INDEX", "db.awaitIndexes", "MERGE (n:", "MERGE (a)-[e:",
                                         "MERGE (c:Conceito", "MERGE (t:Termo", "SET m.esquema", "m.carga_atual AS",
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
    assert "CREATE CONSTRAINT `akme_termo_uniq_projeto_nome` IF NOT EXISTS FOR (t:Termo) REQUIRE (t._projeto, t.nome) IS UNIQUE" in joined
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
    assert len(ontology) == 19 + TERMS and all(p["carga"] == CARGA for p in ontology)


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
    result = neo4j_load.verify(build_plan(seeded), "demo", CONCEPTS, TERMS)
    assert result == {"ok": True, "divergences": []}
    joined = "\n".join(session.queries())
    assert "(:`Pedido`)-[r:`pertenceA`]->(:`Cliente`)" in joined
    assert "MATCH (n:`Cliente`) WHERE n._projeto = $p" in joined
    assert "MATCH (c:Conceito {_projeto: $p})" in joined
    assert "MATCH (t:Termo {_projeto: $p})" in joined
    assert all(p.get("p") == "demo" for q, p in session.calls if "$p" in q)


def test_verify_reports_divergence(seeded, fake):
    fake["use"](_FakeSession(counts={"Cliente": 9, "contem": 0, "Conceito": 8, "Termo": 3}))
    result = neo4j_load.verify(build_plan(seeded), "demo", CONCEPTS, TERMS)
    assert result["ok"] is False
    assert "Cliente: esperado 8, encontrado 9" in result["divergences"]
    assert "contem: esperado 17, encontrado 0" in result["divergences"]
    assert "Conceito: esperado 9, encontrado 8" in result["divergences"]
    assert "Termo: esperado 10, encontrado 3" in result["divergences"]


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
    assert set(r) == {"target", "dry_run", "artifact", "schema", "guide", "saved_queries",
                      "rows", "batches", "executed", "nodes", "relationships", "descricao",
                      "relations_not_published", "sources_skipped", "problems", "warnings"}
    schema = seeded.docs_dir / "publish" / "neo4j_schema.md"
    assert r["schema"] == str(schema) and schema.read_text(encoding="utf-8").startswith("# Esquema do grafo")
    assert "akme_termo_uniq_projeto_nome" in text and "SET m.esquema = $esquema" in text
    assert "_descricao" in text
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
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+00:00", r["carga"]), "carga em milissegundos"


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
        if "UNWIND $rows" in query:
            raise neo4j.exceptions.ClientError(f"erro com {PASSWORD} no texto")
        return _FakeSession.run(session, query, parameters, **params)

    session.run = run
    with pytest.raises(PublishError, match="lote 1 de 7 falhou") as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert PASSWORD not in str(exc.value) and "0 lote(s) ja gravado(s)" in str(exc.value)


def test_preview_lines_show_database_against_source(seeded):
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)
    plain = "\n".join(neo4j_load.preview_lines(r))
    assert "linhas: 43" in plain and "7 lote(s)" in plain and "Pedido: 10" in plain and "  pertenceA: 10" in plain
    assert "banco" not in plain
    state = {"projetos": ["demo"], "total": 60, "alheios": 0, "legado": False, "no_banco": {"Cliente": 9, "Antiga": 2}}
    lines = neo4j_load.preview_lines(r, state)
    assert "  Cliente: banco 9 -> origem 8, pelo menos 1 serao removidos" in lines
    assert "  Antiga: banco 2 -> origem 0, pelo menos 2 serao removidos" in lines
    assert "  Pedido: banco 0 -> origem 10" in lines
    assert "a sincronizacao apaga pelo menos 3 no(s) deste projeto" in lines
    assert any("a carga apaga deste projeto o que nao vier da origem nesta carga" in line for line in lines)


@pytest.mark.parametrize("uri,browser", [
    ("bolt://127.0.0.1:7687", "http://localhost:7474"),
    ("neo4j+s://abc123.databases.neo4j.io", "https://console.neo4j.io"),
    ("bolt://grafo.cliente.com:7687", "http://grafo.cliente.com:7474"),
])
def test_viewing_lines_point_to_the_browser(seeded, monkeypatch, uri, browser):
    monkeypatch.delenv("AKME_NEO4J_BROWSER_URL", raising=False)
    monkeypatch.setenv("AKME_NEO4J_URI", uri)
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)
    text = "\n".join(neo4j_load.viewing_lines(seeded, r))
    assert browser in text and "neo4j" in text and PASSWORD not in text
    assert "MATCH p = (:Pedido)-[:pertenceA]->(:Cliente) RETURN p LIMIT 50" in text
    assert "MATCH (n)-[r]->(m) WHERE NOT n:Conceito RETURN n, r, m LIMIT 300   // os dados" in text
    assert "MATCH p = (:Conceito)-[:RELACAO_ONTOLOGIA]->(:Conceito) RETURN p   // a ontologia" in text


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
    assert len(names) == len(set(names)) == 4 + 3 + 3
    assert neo4j_load._index_name("Cliente", "id") != neo4j_load._constraint_name("Cliente")
    assert neo4j_load._index_name("A_b", "c") != neo4j_load._index_name("A", "b_c")
    assert neo4j_load._index_name("Conceito", "x") != neo4j_load.CONCEPT_CONSTRAINT_NAME
    assert neo4j_load._constraint_name("Termo") != neo4j_load.TERM_CONSTRAINT_NAME
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
    assert "segredo-do-banco" not in message and "RuntimeError: conexao perdida" in message
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
    with pytest.raises(PublishError, match="ontologia: comando 1 de 40 falhou.*7 lote\\(s\\) ja gravado\\(s\\); nada foi apagado"):
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


def test_preview_without_removal_or_empty_state_does_not_break(seeded):
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)
    empty = neo4j_load.preview_lines(r, {"projetos": [], "total": 0, "alheios": 0, "legado": False,
                                         "no_banco": {label: 0 for label in r["nodes"]}})
    assert not any("removidos" in line or "apaga pelo menos" in line for line in empty)
    other = neo4j_load.preview_lines(r, {"projetos": ["outro"], "total": 5})
    assert "  Pedido: banco 0 -> origem 10" in other


def test_in_db_count_leaves_out_akme_layers():
    assert "'Conceito'" in neo4j_load.IN_DB_QUERY and "'Termo'" in neo4j_load.IN_DB_QUERY


def _descricao_on(project):
    from akme.project import Project, read_yaml, write_yaml

    config = read_yaml(project.root / "akme.yml")
    write_yaml(project.root / "akme.yml", {**config, "neo4j": {"descricao_nos_dados": True}})
    return Project(project.root)


def test_description_is_off_by_default(seeded, fake):
    """Padrao: _descricao fica ausente em nos e arestas de dado (SET com null); a definicao segue no Conceito."""
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    data = [p for q, p in session.calls if "MERGE (n:" in q or "MERGE (a)-[e:" in q]
    assert data and all(p["descricao"] is None for p in data)
    pedido = next(p for q, p in session.calls if "MERGE (c:Conceito" in q and p.get("nome") == "Pedido")
    assert pedido["props"]["definicao"].startswith("Solicitacao de compra"), "a definicao continua no Conceito"


def test_nodes_and_edges_carry_the_description_when_turned_on(seeded, fake):
    project = _descricao_on(seeded)
    session = fake["session"]
    neo4j_load.load(project, build_plan(project), CARGA)
    nodes = {q: p for q, p in session.calls if "MERGE (n:" in q}
    assert nodes and all("n._descricao = $descricao" in q for q in nodes)
    pedido = next(p for q, p in nodes.items() if "MERGE (n:`Pedido`" in q)
    assert pedido["descricao"] == "Solicitacao de compra de um cliente, com status e valor total."
    edge = next(p for q, p in session.calls if "[e:`pertenceA`]" in q)
    assert edge["descricao"] == "pertence a"
    assert all("e._descricao = $descricao" in q for q, _ in session.calls if "MERGE (a)-[e:" in q)
    for query in session.queries():
        assert "Solicitacao de compra" not in query, "a descricao vai como parametro"


def test_class_without_definition_sends_no_description(seeded, fake):
    from rdflib import RDFS
    from akme.ontology import base_ns, load_graph, save_graph

    project = _descricao_on(seeded)
    g = load_graph(project.schema_path)
    g.remove((base_ns(g)["Produto"], RDFS.comment, None))
    save_graph(g, project.schema_path)
    session = fake["session"]
    neo4j_load.load(project, build_plan(project), CARGA)
    produto = next(p for q, p in session.calls if "MERGE (n:`Produto`" in q)
    assert produto["descricao"] is None, "SET com null deixa a propriedade ausente"


@pytest.mark.parametrize("on", [False, True])
def test_artifact_schema_guide_and_viewing_follow_the_option(seeded, monkeypatch, on):
    """Artefato, esquema para o LLM, tutorial e mensagem final dizem a mesma coisa nos dois modos."""
    project = _descricao_on(seeded) if on else seeded
    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://127.0.0.1:7687")
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", "x")
    r = neo4j_load.publish_neo4j(project, _model(project), dry_run=True)
    assert r["descricao"] is on
    artifact = (project.docs_dir / "publish" / "neo4j.cypher").read_text(encoding="utf-8")
    schema = (project.docs_dir / "publish" / "neo4j_schema.md").read_text(encoding="utf-8")
    guide = (project.docs_dir / "publish" / "neo4j_guia.html").read_text(encoding="utf-8")
    viewing = "\n".join(neo4j_load.viewing_lines(project, r))
    if on:
        assert "$descricao = definicao da classe" in artifact
        assert "`_descricao` a definicao da classe (no no)" in schema
        assert "<code>_descricao</code> traz a definicao da classe" in guide
        assert "_descricao, no painel de propriedades" in viewing
    else:
        assert "$descricao = null" in artifact and "descricao_nos_dados" in artifact
        assert "nao tem `_descricao`" in schema and "`definicao` do `Conceito`" in schema
        assert "_descricao" not in guide and "slide A ontologia" in guide
        assert "_descricao" not in viewing and "Conceito" in viewing


def test_schema_goes_to_the_marker_before_sync(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    query, params = next((q, p) for q, p in session.calls if "SET m.esquema" in q)
    assert query == ("MATCH (m:_AkmeProjeto {projeto: $projeto}) WHERE m.carga_atual = $carga "
                     "SET m.esquema = $esquema RETURN count(*) AS gravadas")
    assert params["esquema"].startswith("# Esquema do grafo") and params["projeto"] == "demo"
    assert session.index("SET m.esquema") < session.index("DETACH DELETE")
    from akme.tools.neo4j_schema import llm_schema
    assert params["esquema"] == llm_schema(seeded, build_plan(seeded))


def test_load_writes_the_schema_file_too(seeded, fake):
    neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=False)
    assert (seeded.docs_dir / "publish" / "neo4j_schema.md").exists()


def test_browser_url_can_be_configured(monkeypatch):
    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://127.0.0.1:27687")
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    monkeypatch.delenv("AKME_NEO4J_BROWSER_URL", raising=False)
    assert neo4j_load.browser_url() == "http://localhost:7474"
    monkeypatch.setenv("AKME_NEO4J_BROWSER_URL", "http://localhost:27474")
    assert neo4j_load.browser_url() == "http://localhost:27474"


# --- revisao final ---

def test_load_claims_the_marker_right_after_checking_the_destination(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    claim, params = next((q, p) for q, p in session.calls if "SET m.carga_atual" in q)
    assert claim == "MERGE (m:_AkmeProjeto {projeto: $projeto}) SET m.carga_atual = $carga, m.name = 'Projeto ' + $projeto"
    assert params == {"projeto": "demo", "carga": CARGA}
    assert session.index("COLLECT") < session.index("SET m.carga_atual") < session.index("CREATE CONSTRAINT `akme_uniq_")
    reads = [i for i, q in enumerate(session.queries()) if "m.carga_atual AS" in q]
    assert len(reads) == 2, "confere a carga atual antes de cada comando da sincronizacao"
    assert reads[0] < session.index("DETACH DELETE") < reads[1] < session.index("DELETE r")


def test_newer_load_on_the_same_project_blocks_the_sync(seeded, fake):
    session = fake["use"](_FakeSession(other_load_at=1))
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert str(exc.value) == "outra carga deste projeto comecou depois desta; nada foi apagado. Rode a carga de novo"
    assert not any("DELETE" in q for q in session.queries())


def test_newer_load_between_the_two_sync_commands_stops_before_the_edges(seeded, fake):
    session = fake["use"](_FakeSession(other_load_at=2, deleted=(3, 0)))
    with pytest.raises(PublishError, match="outra carga deste projeto comecou durante a sincronizacao") as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert "Rode a carga de novo" in str(exc.value)
    assert any("DETACH DELETE" in q for q in session.queries())
    assert not any("DELETE r" in q for q in session.queries())


def test_writes_go_through_managed_transactions_and_sync_does_not(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    written = set(session.written)
    for query in session.queries():
        if query.startswith(("CREATE CONSTRAINT", "CREATE INDEX", "MERGE", "MATCH (a:Conceito")) or "UNWIND $rows" in query \
                or "SET m.esquema" in query or "SET m.carga_atual" in query:
            assert query in written, f"sem execute_write: {query[:60]}"
        if "IN TRANSACTIONS" in query:
            assert query not in written, "IN TRANSACTIONS exige transacao implicita"
    assert sum(1 for q in session.written if "UNWIND $rows" in q) == 7


def test_old_neo4j_is_refused_before_writing(seeded, fake):
    session = fake["use"](_FakeSession(version="5.20.0"))
    with pytest.raises(PublishError, match="Neo4j 5.20.0.*5.23 ou mais novo.*Nada foi gravado"):
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert not any(q.startswith(("CREATE", "MERGE", "UNWIND")) for q in session.queries())


@pytest.mark.parametrize("version,ok", [("5.23.0", True), ("5.26.12", True), ("5.27-aura", True),
                                        ("2026.10.1", True), ("5.22.0", False), ("4.4.30", False)])
def test_version_rule(version, ok):
    assert neo4j_load.supported_version(version) is ok


def test_database_name_comes_from_the_environment(seeded, fake, monkeypatch):
    monkeypatch.setenv("AKME_NEO4J_DATABASE", "vendas")
    neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=False)
    assert fake["session_kwargs"] and all(k == {"database": "vendas"} for k in fake["session_kwargs"])


def test_without_database_name_uses_the_default(seeded, fake):
    neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=False)
    assert fake["session_kwargs"] and all(k == {} for k in fake["session_kwargs"])


def test_load_refuses_identifier_with_unicode_escape_without_connecting(seeded, fake):
    import dataclasses

    plan = build_plan(seeded)
    plan.sources = [dataclasses.replace(s, label="Cli\\u0060ente") if s.label == "Cliente" else s for s in plan.sources]
    plan.nodes = {("Cli\\u0060ente" if k == "Cliente" else k): v for k, v in plan.nodes.items()}
    with pytest.raises(PublishError, match="carga recusada, nada foi gravado: .*identificador"):
        neo4j_load.load(seeded, plan, CARGA)
    assert fake["session"].calls == []


def test_sync_commands_carry_the_lock_in_the_same_query(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    for fragment in ("DETACH DELETE", "DELETE r"):
        query = next(q for q in session.queries() if fragment in q and (fragment != "DELETE r" or "DETACH" not in q))
        assert query.startswith("MATCH (m:_AkmeProjeto {projeto: $projeto}) WHERE m.carga_atual = $carga ")
        assert query.index("m.carga_atual = $carga") < query.index("CALL (")


def test_driver_notifications_are_silenced(seeded, fake):
    neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=False)
    assert fake["driver_kwargs"]
    assert fake["driver_kwargs"]
    assert all(k == {"auth": ("x", PASSWORD), "notifications_disabled_classifications": ["UNRECOGNIZED"]}
               for k in fake["driver_kwargs"]), "so a familia UNRECOGNIZED; nada de OFF"


def test_real_driver_accepts_the_notification_setting():
    neo4j = pytest.importorskip("neo4j")
    # so cria o driver (nao conecta): um nome de opcao errado levantaria aqui
    driver = neo4j.GraphDatabase.driver("bolt://127.0.0.1:1", auth=("u", "p"),
                                        notifications_disabled_classifications=neo4j_load.NOTIFICATIONS_OFF)
    driver.close()


def test_block_after_a_newer_load_claims_the_marker_stops_the_load(seeded, fake):
    session = fake["use"](_FakeSession(other_load_after_unwind=2))
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert str(exc.value) == neo4j_load.NEWER_LOAD
    assert session.unwinds == 3, "para no primeiro bloco barrado"
    assert not any("DELETE" in q for q in session.queries())
    assert not any("MERGE (c:Conceito" in q for q in session.queries())


def test_data_blocks_start_with_the_lock(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    blocks = [q for q in session.queries() if "UNWIND $rows" in q]
    assert len(blocks) == 7 and all(q.startswith(neo4j_load._LOCK + "WITH m UNWIND $rows") for q in blocks)


def test_lock_that_stopped_the_node_sync_gives_the_nothing_deleted_message(seeded, fake):
    fake["use"](_FakeSession(other_load_at=2, deleted=(0, 0)))
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert str(exc.value) == neo4j_load.NEWER_LOAD


def test_unrecognized_version_is_refused(seeded, fake):
    session = fake["use"](_FakeSession(version="aura"))
    with pytest.raises(PublishError, match="versao nao reconhecida do Neo4j: aura.*Nada foi gravado"):
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert not any(q.startswith(("CREATE", "MERGE")) for q in session.queries())


def test_marker_constraint_comes_before_the_claim(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert "CREATE CONSTRAINT `akme_projeto_uniq` IF NOT EXISTS FOR (m:_AkmeProjeto) REQUIRE m.projeto IS UNIQUE" \
        in session.queries()
    assert session.index("akme_projeto_uniq") < session.index("SET m.carga_atual")
    text = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)["artifact"]
    from pathlib import Path
    artifact = Path(text).read_text(encoding="utf-8")
    assert artifact.index("akme_projeto_uniq") < artifact.index("SET m.carga_atual")


# --- /code-review ---

def test_ontology_and_schema_commands_carry_the_lock(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    onto = [q for q in session.queries() if ("Conceito" in q or "Termo" in q) and "MERGE" in q or "SET m.esquema" in q]
    assert len(onto) == 19 + 2 * TERMS + 1
    assert all(q.startswith(neo4j_load._LOCK) and q.endswith("RETURN count(*) AS gravadas") for q in onto)
    assert all(q in session.written for q in onto)


def test_newer_load_during_the_ontology_stops_without_touching_it(seeded, fake):
    session = fake["session"]
    original = session.run
    seen = []

    def run(query, parameters=None, **params):
        if "MERGE (c:Conceito" in query and not seen:  # outra carga troca a marca antes do primeiro Conceito
            seen.append(query)
            session.claimed = "outra-carga"
        return original(query, parameters, **params)

    session.run = run
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert str(exc.value) == neo4j_load.NEWER_LOAD
    assert sum(1 for q in session.queries() if "MERGE (c:Conceito" in q) == 1, "para no primeiro comando barrado"
    assert not any("SET m.esquema" in q for q in session.queries())
    assert not any("DELETE" in q for q in session.queries())


def test_version_is_checked_before_the_state_query(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert session.index("dbms.components") < session.index("COLLECT")


def test_old_neo4j_never_receives_the_state_query(seeded, fake):
    session = fake["use"](_FakeSession(version="4.4.30"))
    with pytest.raises(PublishError, match="Neo4j 4.4.30.*5.23 ou mais novo.*Nada foi gravado"):
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert not any("COLLECT" in q for q in session.queries())


def test_destination_state_refuses_old_neo4j_before_the_state_query(seeded, fake):
    session = fake["use"](_FakeSession(version="5.4.0"))
    with pytest.raises(PublishError, match="Neo4j 5.4.0.*5.23 ou mais novo"):
        neo4j_load.destination_state(seeded, build_plan(seeded))
    assert session.queries() == [neo4j_load.VERSION_QUERY]


class _CountingAdapter:
    def __init__(self, real):
        self.real, self.reads = real, []

    def iter_rows(self, source, batch=5000):
        self.reads.append(source)
        yield from self.real.iter_rows(source, batch)

    def close(self):
        self.real.close()


def test_edge_pass_reads_each_origin_once(seeded, fake, monkeypatch):
    real, holder = neo4j_load.load_adapter, {}

    def counting(name, opts):
        holder["a"] = _CountingAdapter(real(name, opts))
        return holder["a"]

    monkeypatch.setattr(neo4j_load, "load_adapter", counting)
    session = fake["session"]
    result = neo4j_load.load(seeded, build_plan(seeded), CARGA)
    reads = holder["a"].reads
    assert reads.count("pedidos") == 2, "nos + uma passada para contem e pertenceA juntos"
    assert reads.count("itens_pedido") == 2 and reads.count("clientes") == 1 and reads.count("produtos") == 1
    assert result["executed"] == 7 and session.unwinds == 7
    edges = [p for q, p in session.calls if "MERGE (a)-[e:" in q]
    assert sum(len(p["rows"]) for p in edges) == 10 + 10 + 17, "uma linha da origem por contrato"
    order = [re.search(r"\[e:`(\w+)`\]", q).group(1) for q in session.queries() if "MERGE (a)-[e:" in q]
    plan = build_plan(seeded)
    grouped = [e.relation for o in dict.fromkeys(e.from_source for e in plan.edges) for e in plan.edges if e.from_source == o]
    assert order == grouped == ["pertenceA", "contem", "referencia"], "deterministico: ordem do plano, agrupada pela origem"


def test_preview_and_artifact_share_the_warning_list(seeded):
    r = neo4j_load.publish_neo4j(seeded, _model(seeded), dry_run=True)
    r = {**r, "sources_skipped": ["extra"], "relations_not_published": ["solta"], "warnings": ["cuidado"]}
    lines = neo4j_load.preview_lines(r)
    start = lines.index("avisos:")
    assert lines[start + 1:start + 4] == ["  fonte excluida na etapa 5: extra", "  relacao nao publicada: solta", "  cuidado"]
    assert neo4j_load.warning_lines(["extra"], ["solta"], ["cuidado"]) == [
        "fonte excluida na etapa 5: extra", "relacao nao publicada: solta", "cuidado"]


def test_project_name_is_escaped_as_a_cypher_literal(seeded, monkeypatch):
    from akme.project import Project, read_yaml, write_yaml
    from akme.tools.neo4j_onto import _literal

    config = read_yaml(seeded.root / "akme.yml")
    config["project"] = "d'emo\\x\rz"
    write_yaml(seeded.root / "akme.yml", config)
    project = Project(seeded.root)
    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://127.0.0.1:7687")
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    r = neo4j_load.publish_neo4j(project, _model(project), dry_run=True)
    artifact = (project.docs_dir / "publish" / "neo4j.cypher").read_text(encoding="utf-8")
    assert f"// :param projeto => {_literal(project.name)}\n" in artifact
    assert "\\r" in _literal(project.name)
    text = "\n".join(neo4j_load.viewing_lines(project, r))
    assert "p.esquema" not in text, "o esquema e para o LLM; a mensagem ao humano nao manda le-lo"


def test_demo_checker_expects_every_constraint_the_load_creates(seeded):
    import importlib.util
    from pathlib import Path

    pytest.importorskip("neo4j")
    path = Path(__file__).resolve().parents[1] / "examples" / "local_demo" / "verificar_neo4j.py"
    spec = importlib.util.spec_from_file_location("verificar_neo4j", path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    plan = build_plan(seeded)
    created = sorted([neo4j_load.MARKER_CONSTRAINT_NAME, neo4j_load.CONCEPT_CONSTRAINT_NAME, neo4j_load.TERM_CONSTRAINT_NAME]
                     + [neo4j_load._constraint_name(label) for label in plan.nodes])
    assert checker.CONSTRAINTS == created


# --- Task 11: nome do TTL nas arestas de dado, RELACAO_ONTOLOGIA entre Conceito e legenda name ---

def test_data_edges_use_the_exact_relation_name(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    edges = [q for q in session.queries() if "MERGE (a)-[e:" in q]
    assert sorted(re.search(r"\[e:`(\w+)`\]", q).group(1) for q in edges) == ["contem", "pertenceA", "referencia"]
    arrows = [(q, p) for q, p in session.calls if "MATCH (a:Conceito" in q and "SUBCLASSE_DE" not in q]
    assert arrows and all("[r:RELACAO_ONTOLOGIA {nome: $rel}]" in q for q, _ in arrows)
    assert sorted(p["rel"] for _, p in arrows) == ["contem", "pertenceA", "pertenceAoPedido", "possuiPedido", "referencia"]


def test_every_data_node_gets_a_distinguishing_name(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    rows = {r["id"]: r["p"] for q, p in session.calls if "MERGE (n:" in q for r in p["rows"]}
    assert rows["1"]["name"] == "Cliente 1 SP"
    assert rows["1001"]["name"] == "Pedido 1001 2026-07-03"
    assert rows["1001/CIM-50"]["name"] == "ItemPedido 1001/CIM-50 100"
    assert rows["CIM-50"]["name"] == "Produto CIM-50 cimento"
    items = [r["p"]["name"] for q, p in session.calls if "MERGE (n:`ItemPedido`" in q for r in p["rows"]]
    assert len(set(items)) == len(items)


def test_source_name_column_is_respected(seeded, fake):
    from akme.tools.profile import profile

    path = seeded.root / "data" / "produtos.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0] + ",name"] + [line + ",Nome da origem" for line in lines[1:]]) + "\n", encoding="utf-8")
    profile(seeded)
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    rows = [r["p"] for q, p in session.calls if "MERGE (n:`Produto`" in q for r in p["rows"]]
    assert rows and all(r["name"] == "Nome da origem" for r in rows)


def test_empty_source_name_gets_the_akme_caption(seeded, fake):
    from akme.tools.profile import profile

    path = seeded.root / "data" / "produtos.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    names = ["Nome da origem" if i % 2 else "" for i in range(len(lines) - 1)]
    path.write_text("\n".join([lines[0] + ",name"] + [f"{line},{n}" for line, n in zip(lines[1:], names)]) + "\n",
                    encoding="utf-8")
    profile(seeded)
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    rows = [r["p"] for q, p in session.calls if "MERGE (n:`Produto`" in q for r in p["rows"]]
    assert rows and all(r["name"] for r in rows)
    assert {r["name"] == "Nome da origem" for r in rows} == {True, False}
    assert all(r["name"].startswith("Produto ") for r in rows if r["name"] != "Nome da origem")


def test_marker_gets_a_caption_in_the_claim(seeded, fake):
    session = fake["session"]
    neo4j_load.load(seeded, build_plan(seeded), CARGA)
    claim = next(q for q in session.queries() if "SET m.carga_atual" in q)
    assert "m.name = 'Projeto ' + $projeto" in claim


def test_verify_counts_data_edges_by_relation_name(seeded, fake):
    fake["use"](_FakeSession(counts={"pertenceA": 10, "contem": 17, "referencia": 17}))
    result = neo4j_load.verify(build_plan(seeded), "demo", CONCEPTS, TERMS)
    assert result == {"ok": True, "divergences": []}
    joined = "\n".join(fake["session"].queries())
    assert "(:`Pedido`)-[r:`pertenceA`]->(:`Cliente`)" in joined
