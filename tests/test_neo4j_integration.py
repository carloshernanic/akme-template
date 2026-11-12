"""Carga real num Neo4j descartavel, com a demo. Pulado sem AKME_NEO4J_TEST_URI, AKME_NEO4J_TEST_USER e
AKME_NEO4J_TEST_PASSWORD.

ATENCAO: estes testes APAGAM o banco inteiro no inicio de cada teste. Por isso so rodam com as variaveis
AKME_NEO4J_TEST_*, que devem apontar para um banco dedicado a testes, nunca para AKME_NEO4J_URI.
"""
from __future__ import annotations

import os
import time

import pytest

from akme.project import Project
from akme.tools import neo4j_load

VARS = ("AKME_NEO4J_TEST_URI", "AKME_NEO4J_TEST_USER", "AKME_NEO4J_TEST_PASSWORD")
pytestmark = pytest.mark.skipif(not all(os.environ.get(v) for v in VARS),
                                reason="Neo4j de teste nao configurado (AKME_NEO4J_TEST_URI/USER/PASSWORD)")

EXPECTED_NODES = {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
EXPECTED_EDGES = {"contem": 17, "pertenceA": 10, "referencia": 17}


@pytest.fixture
def db(monkeypatch):
    neo4j = pytest.importorskip("neo4j")
    uri, user, password = (os.environ[v] for v in VARS)
    monkeypatch.setenv("AKME_NEO4J_URI", uri)
    monkeypatch.setenv("AKME_NEO4J_USER", user)
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", password)
    driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
    # Banco dedicado a testes (AKME_NEO4J_TEST_URI): comeca vazio. Nunca fazer isto fora desse banco.
    # IN TRANSACTIONS exige transacao implicita (session.run), nao execute_query.
    with driver.session() as session:
        session.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS").consume()
        # e o esquema criado pelo akme (inclusive nomes antigos), para cada teste ver as restricoes e indices que cria
        for record in list(session.run("SHOW CONSTRAINTS YIELD name WHERE name STARTS WITH 'akme_' RETURN name")):
            session.run(f"DROP CONSTRAINT {neo4j_load.name(record['name'])} IF EXISTS").consume()
        for record in list(session.run("SHOW INDEXES YIELD name, owningConstraint "
                                       "WHERE name STARTS WITH 'akme_' AND owningConstraint IS NULL RETURN name")):
            session.run(f"DROP INDEX {neo4j_load.name(record['name'])} IF EXISTS").consume()
    yield driver
    driver.close()


def _count(driver, query, **params):
    return driver.execute_query(query, params).records[0][0]


def _publish(project):
    start = time.perf_counter()
    result = neo4j_load.publish_neo4j(project, {"project": project.name, "version": "0.1.0"}, dry_run=False)
    result["_segundos"] = round(time.perf_counter() - start, 2)
    print(f"\ncarga: {result['_segundos']} s, executed={result['executed']}, removed={result['removed']}")
    return result


def test_real_load_matches_plan_and_repeats(seeded, db):
    first = _publish(seeded)
    assert first["verification"] == {"ok": True, "divergences": []}
    assert first["nodes"] == EXPECTED_NODES and first["relationships"] == EXPECTED_EDGES
    assert first["executed"] == first["batches"] == 7
    assert first["removed"] == {"nodes": 0, "relationships": 0}
    assert _count(db, "MATCH ()-[r:pertenceA]->() WHERE NOT startNode(r):Conceito RETURN count(r)") == 10
    assert _count(db, "MATCH (m:_AkmeProjeto {projeto: 'demo'}) RETURN count(m)") == 1
    typed = db.execute_query("MATCH (c:Cliente {_id: '1'}) RETURN c.dt_cadastro AS d, c.nm_cliente AS n, "
                             "c._projeto AS p, c._carga AS k").records[0]
    assert str(typed["d"]) == "2023-01-15" and typed["n"] == "Construtora Horizonte" and typed["p"] == "demo"
    assert typed["k"] == first["carga"]
    item = db.execute_query("MATCH (i:ItemPedido {_id: '1001/CIM-50'}) RETURN i.qt_itens AS q, i.vl_item AS v").records[0]
    assert item["q"] == 100 and item["v"] == 3290.0
    total = _count(db, "MATCH (n) RETURN count(n)")

    time.sleep(1.1)  # carga nova com outra marca de rodada (precisao de segundos)
    second = _publish(seeded)
    assert second["carga"] != first["carga"]
    assert second["verification"] == {"ok": True, "divergences": []}
    assert second["removed"] == {"nodes": 0, "relationships": 0}
    assert _count(db, "MATCH (n) RETURN count(n)") == total
    assert _count(db, "MATCH (m:_AkmeProjeto) RETURN count(m)") == 1, "a marca nao e apagada nem duplicada"
    assert _count(db, "MATCH (n) WHERE n._projeto = 'demo' AND n._carga <> $c RETURN count(n)", c=second["carga"]) == 0


def test_real_sync_removes_deleted_row(seeded, db):
    _publish(seeded)
    path = seeded.root / "data" / "clientes.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line for line in lines if not line.startswith("3,")) + "\n", encoding="utf-8")
    time.sleep(1.1)
    result = _publish(seeded)
    assert result["nodes"]["Cliente"] == 7
    assert result["removed"] == {"nodes": 1, "relationships": 0}
    assert result["verification"] == {"ok": True, "divergences": []}
    assert _count(db, "MATCH (c:Cliente {_id: '3'}) RETURN count(c)") == 0


def test_real_sync_removes_edge_whose_target_changed(seeded, db):
    _publish(seeded)
    path = seeded.root / "data" / "pedidos.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("1001,1,", "1001,3,", 1), encoding="utf-8")
    time.sleep(1.1)
    result = _publish(seeded)
    assert result["removed"] == {"nodes": 0, "relationships": 1}
    assert result["verification"]["ok"]
    assert _count(db, "MATCH (:Pedido {_id: '1001'})-[:pertenceA]->(c:Cliente) RETURN c._id") == "3"


def test_real_load_refuses_foreign_nodes_and_deletes_nothing(seeded, db):
    from akme.tools.publish import PublishError

    db.execute_query("CREATE (:Alheio {nome: 'de outra pessoa'})")
    with pytest.raises(PublishError, match="nao vieram do akme|sem a marca"):
        _publish(seeded)
    assert _count(db, "MATCH (n) RETURN count(n)") == 1


def test_real_ontology_shape(seeded, db):
    _publish(seeded)
    assert _count(db, "MATCH (c:Conceito {_projeto: 'demo'}) RETURN count(c)") == 9
    assert _count(db, "MATCH (:Conceito)-[r:SUBCLASSE_DE]->(:Conceito) RETURN count(r)") == 5
    assert _count(db, "MATCH (:Conceito {nome: 'Pedido'})-[r:pertenceA]->(:Conceito {nome: 'Cliente'}) "
                      "RETURN count(r)") == 1
    assert _count(db, "MATCH (:Conceito)-[r]->(n) WHERE NOT n:Conceito RETURN count(r)") == 0, "camadas separadas"
    assert _count(db, "MATCH (n)-[r]->(:Conceito) WHERE NOT n:Conceito RETURN count(r)") == 0


def test_real_legacy_n10s_database_is_refused(seeded, db):
    from akme.tools.publish import PublishError

    db.execute_query("CREATE (:Resource {uri: 'urn:x'}), (:_GraphConfig {_handleVocabUris: 'IGNORE'})")
    with pytest.raises(PublishError, match="exportacao antiga \\(n10s\\)"):
        _publish(seeded)
    assert _count(db, "MATCH (n) RETURN count(n)") == 2


def _rename_column(project, old, new):
    for path in (project.content_path, project.root / "data" / "clientes.csv", project.root / "data" / "pedidos.csv"):
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    return Project(project.root)


def test_real_index_on_join_column_named_id_is_created(seeded, db):
    project = _rename_column(seeded, "id_cliente", "id")
    result = _publish(project)
    assert result["verification"]["ok"] and result["relationships"]["pertenceA"] == 10
    indexes = {r["name"]: r for r in db.execute_query(
        "SHOW INDEXES YIELD name, labelsOrTypes, properties, state, owningConstraint RETURN *").records}
    index = neo4j_load._index_name("Cliente", "id")
    assert index in indexes and indexes[index]["properties"] == ["id"] and indexes[index]["state"] == "ONLINE"
    assert indexes[index]["owningConstraint"] is None
    constraints = {r["name"] for r in db.execute_query("SHOW CONSTRAINTS YIELD name RETURN name").records}
    assert {"akme_uniq_Cliente", "akme_uniq_Pedido", "akme_uniq_ItemPedido", "akme_uniq_Produto",
            neo4j_load.CONCEPT_CONSTRAINT_NAME} <= constraints
    assert not any(n.startswith("akme_") and n.endswith("_id") for n in constraints | set(indexes)), "nomes antigos"


def test_real_column_with_space_loads(seeded, db):
    project = _rename_column(seeded, "id_cliente", "nome cliente")
    result = _publish(project)
    assert result["verification"]["ok"] and result["relationships"]["pertenceA"] == 10
    assert _count(db, "MATCH (c:Cliente {_id: '1'}) RETURN c.`nome cliente`") == "1"
