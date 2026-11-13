"""Carga real num Neo4j descartavel, com a demo. Pulado sem AKME_NEO4J_TEST_URI, AKME_NEO4J_TEST_USER e
AKME_NEO4J_TEST_PASSWORD.

ATENCAO: estes testes APAGAM o banco inteiro no inicio de cada teste. Por isso so rodam com as variaveis
AKME_NEO4J_TEST_*, que devem apontar para um banco dedicado a testes, nunca para AKME_NEO4J_URI.
"""
from __future__ import annotations

import csv
import json
import os
import time
from decimal import Decimal
from pathlib import Path

import pytest

from akme.project import Project
from akme.tools import neo4j_load

VARS = ("AKME_NEO4J_TEST_URI", "AKME_NEO4J_TEST_USER", "AKME_NEO4J_TEST_PASSWORD")
pytestmark = pytest.mark.skipif(not all(os.environ.get(v) for v in VARS),
                                reason="Neo4j de teste nao configurado (AKME_NEO4J_TEST_URI/USER/PASSWORD)")

EXPECTED_NODES = {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
EXPECTED_EDGES = {"contem": 17, "pertenceA": 10, "referencia": 17}
DEMO = Path(__file__).resolve().parents[1] / "examples" / "local_demo"


@pytest.fixture
def db(monkeypatch):
    neo4j = pytest.importorskip("neo4j")
    uri, user, password = (os.environ[v] for v in VARS)
    monkeypatch.setenv("AKME_NEO4J_URI", uri)
    monkeypatch.setenv("AKME_NEO4J_USER", user)
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", password)
    monkeypatch.delenv("AKME_NEO4J_DATABASE", raising=False)
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

    time.sleep(0.01)  # carga nova com outra marca de rodada (precisao de milissegundos)
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
    time.sleep(0.01)
    result = _publish(seeded)
    assert result["nodes"]["Cliente"] == 7
    assert result["removed"] == {"nodes": 1, "relationships": 0}
    assert result["verification"] == {"ok": True, "divergences": []}
    assert _count(db, "MATCH (c:Cliente {_id: '3'}) RETURN count(c)") == 0


def test_real_sync_removes_edge_whose_target_changed(seeded, db):
    _publish(seeded)
    path = seeded.root / "data" / "pedidos.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("1001,1,", "1001,3,", 1), encoding="utf-8")
    time.sleep(0.01)
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
    assert _count(db, "MATCH (:Conceito {nome: 'Pedido'})-[r:RELACAO_ONTOLOGIA {nome: 'pertenceA'}]->(:Conceito {nome: 'Cliente'}) "
                      "RETURN count(r)") == 1
    assert _count(db, "MATCH (:Conceito)-[r]->(n) WHERE NOT n:Conceito AND NOT n:Termo RETURN count(r)") == 0, "camadas separadas"
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


def _questions() -> list[tuple[str, str]]:
    """Blocos de examples/local_demo/perguntas_neo4j.cypher: (secao.chave do gabarito, consulta)."""
    path = DEMO / "perguntas_neo4j.cypher"
    blocks: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("// pergunta:"):
            blocks.append((line.split(":", 1)[1].strip(), []))
        elif blocks and line.strip() and not line.lstrip().startswith("//"):
            blocks[-1][1].append(line)
    return [(key, "\n".join(body).strip().rstrip(";")) for key, body in blocks]


def _as_gabarito(got, expected):
    """Valor do grafo no formato do gabarito. Dinheiro (texto com 2 casas no gabarito) vem do grafo em centavos
    inteiros e e comparado exato, sem float; pares [chave, valor] viram dicionario."""
    if isinstance(expected, str):
        assert type(got) is int, f"dinheiro deve vir em centavos inteiros, veio {type(got).__name__}"
        cents = Decimal(expected) * 100
        assert cents == cents.to_integral_value(), f"gabarito com mais de 2 casas: {expected}"
        return expected if got == int(cents) else f"{Decimal(got) / 100:.2f}"
    if isinstance(expected, dict) and isinstance(got, list):
        return {k: v for k, v in got}
    return got


def _same(got, expected) -> bool:
    """Igualdade com o mesmo tipo: 2999.0 nao vale 2999, e 1 nao vale True. Vale tambem dentro de listas e dicionarios."""
    if type(got) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(got) == len(expected) and all(_same(a, b) for a, b in zip(got, expected))
    if isinstance(expected, dict):
        return got.keys() == expected.keys() and all(_same(got[k], expected[k]) for k in expected)
    return got == expected


def test_real_competency_questions(seeded, db):
    """Perguntas do gabarito da demo respondidas por Cypher no grafo carregado, comparadas ao oraculo dos CSVs."""
    gabarito = json.loads((DEMO / "gabarito.json").read_text(encoding="utf-8"))
    assert _publish(seeded)["verification"]["ok"]
    questions = _questions()
    keys = [key for key, _ in questions]
    assert len(keys) == len(set(keys)), "pergunta repetida no arquivo"
    required = {f"{section}.{name}" for section in ("direct_answers", "measures", "traps", "keys_unique")
                for name in gabarito[section]}
    assert required <= set(keys), f"pergunta do gabarito sem consulta: {sorted(required - set(keys))}"
    wrong = []
    for key, query in questions:
        section, name = key.split(".", 1)
        expected = gabarito[section][name]
        records = db.execute_query(query).records
        assert len(records) == 1, f"{key}: a consulta deve devolver uma linha"
        got = _as_gabarito(records[0]["resposta"], expected)
        print(f"{key}: grafo={got!r} gabarito={expected!r}")
        if not _same(got, expected):
            wrong.append((key, got, expected))
    assert wrong == []


def _descricao(project, on):
    from akme.project import read_yaml, write_yaml

    config = read_yaml(project.root / "akme.yml")
    write_yaml(project.root / "akme.yml", {**config, "neo4j": {"descricao_nos_dados": on}})
    return Project(project.root)


def test_real_description_is_off_by_default_and_turning_off_clears_it(seeded, db):
    """Padrao: nenhum no ou aresta de dado com _descricao. Ligar grava; desligar de novo apaga na carga seguinte."""
    data = "n._projeto = 'demo' AND NOT n:Conceito AND NOT n:Termo"
    with_text = (f"MATCH (n) WHERE {data} AND n._descricao IS NOT NULL RETURN count(n)",
                 f"MATCH (n)-[r]->() WHERE {data} AND r._descricao IS NOT NULL RETURN count(r)")
    assert _publish(seeded)["verification"]["ok"]
    assert [_count(db, q) for q in with_text] == [0, 0]
    assert _count(db, "MATCH (c:Conceito {_projeto: 'demo', nome: 'Pedido'}) RETURN c.definicao").startswith("Solicitacao")
    _publish(_descricao(seeded, True))
    assert [_count(db, q) for q in with_text] == [sum(EXPECTED_NODES.values()), sum(EXPECTED_EDGES.values())]
    again = _publish(_descricao(seeded, False))
    assert [_count(db, q) for q in with_text] == [0, 0]
    assert again["removed"] == {"nodes": 0, "relationships": 0}


def test_real_semantic_layer(seeded, db):
    """Com a opcao ligada: _descricao em todo no e aresta de dado, esquema na marca igual ao arquivo, termos ligados;
    repetir remove 0."""
    seeded = _descricao(seeded, True)
    first = _publish(seeded)
    assert first["verification"] == {"ok": True, "divergences": []}
    data = "n._projeto = 'demo' AND NOT n:Conceito AND NOT n:Termo"
    assert _count(db, f"MATCH (n) WHERE {data} RETURN count(n)") == sum(EXPECTED_NODES.values())
    wrong = db.execute_query(f"MATCH (n) WHERE {data} MATCH (c:Conceito {{_projeto: 'demo'}}) WHERE c.nome IN labels(n) "
                             "AND (n._descricao IS NULL OR n._descricao <> c.definicao) RETURN count(n)").records[0][0]
    assert wrong == 0
    assert _count(db, f"MATCH (n) WHERE {data} AND n._descricao IS NOT NULL RETURN count(n)") == sum(EXPECTED_NODES.values())
    edges = {r["t"]: r["d"] for r in db.execute_query(
        f"MATCH (n)-[r]->() WHERE {data} RETURN DISTINCT type(r) AS t, r._descricao AS d").records}
    assert edges == {"contem": "contem", "pertenceA": "pertence a", "referencia": "referencia"}
    stored = _count(db, "MATCH (p:_AkmeProjeto {projeto: 'demo'}) RETURN p.esquema")
    assert stored == (seeded.docs_dir / "publish" / "neo4j_schema.md").read_text(encoding="utf-8")
    assert "### Pedido" in stored and "nao somar apos juntar com: ItemPedido" in stored
    assert _count(db, "MATCH (t:Termo {_projeto: 'demo'}) RETURN count(t)") == 10
    assert _count(db, "MATCH (:Conceito {_projeto: 'demo'})-[:TEM_TERMO]->(t:Termo) RETURN count(t)") == 10
    cliente = db.execute_query("MATCH (:Conceito {nome: 'Cliente'})-[:TEM_TERMO]->(t:Termo {nome: 'cliente'}) "
                               "RETURN t.sinonimos AS s, t.coluna AS c, t._carga AS k").records[0]
    assert cliente["s"] == ["conta", "comprador"] and cliente["c"] == "id_cliente" and cliente["k"] == first["carga"]
    fat = _count(db, "MATCH (c:Conceito {nome: 'Faturamento'}) RETURN c.nao_somar_apos_juntar_com")
    assert fat == ["ItemPedido"]
    constraints = {r["name"] for r in db.execute_query("SHOW CONSTRAINTS YIELD name RETURN name").records}
    assert neo4j_load.TERM_CONSTRAINT_NAME in constraints

    time.sleep(0.01)
    second = _publish(seeded)
    assert second["removed"] == {"nodes": 0, "relationships": 0}
    assert second["verification"]["ok"]
    assert _count(db, "MATCH (t:Termo) RETURN count(t)") == 10
    assert _count(db, "MATCH (p:_AkmeProjeto {projeto: 'demo'}) RETURN p.esquema") == stored, "esquema deterministico"


def test_real_preview_counts_what_sync_removes(seeded, db):
    _publish(seeded)
    path = seeded.root / "data" / "clientes.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line for line in lines if not line.startswith("3,")) + "\n", encoding="utf-8")
    from akme.tools.neo4j_plan import build_plan

    plan = build_plan(seeded)
    preview = neo4j_load.publish_neo4j(seeded, {"project": "demo", "version": "0.1.0"}, dry_run=True, plan=plan)
    state = neo4j_load.destination_state(seeded, plan)
    assert "Termo" not in state["no_banco"] and "Conceito" not in state["no_banco"]
    lines = neo4j_load.preview_lines(preview, state)
    assert "  Cliente: banco 8 -> origem 7, pelo menos 1 serao removidos" in lines
    assert "a sincronizacao apaga pelo menos 1 no(s) deste projeto" in lines


# --- revisao final ---

def test_real_failure_mid_load_then_new_load_converges(seeded, db, monkeypatch):
    from akme.tools.publish import PublishError

    real = neo4j_load._edge_rows
    monkeypatch.setattr(neo4j_load, "_edge_rows", lambda *a: (_ for _ in ()).throw(ValueError("falha simulada")))
    with pytest.raises(PublishError, match="lote 5 de 7 falhou.*4 lote\\(s\\) ja gravado\\(s\\); nada foi apagado"):
        _publish(seeded)
    assert _count(db, "MATCH ()-[r]->() RETURN count(r)") == 0, "falhou na primeira aresta"
    monkeypatch.setattr(neo4j_load, "_edge_rows", real)
    result = _publish(seeded)
    assert result["verification"] == {"ok": True, "divergences": []}
    assert result["removed"] == {"nodes": 0, "relationships": 0}
    assert _count(db, "MATCH (n) WHERE n._projeto = 'demo' AND n._carga <> $c RETURN count(n)", c=result["carga"]) == 0


def test_real_interleaved_loads_do_not_empty_the_database(seeded, db, monkeypatch):
    """A grava tudo; antes de A sincronizar, B roda inteira. A trava faz A desistir sem apagar nada."""
    from akme.tools.neo4j_plan import build_plan
    from akme.tools.publish import PublishError

    real, other = neo4j_load._current, {}

    def current(session, project_name):
        if not other:  # so na primeira conferencia, a de A; a carga B usa a conferencia real
            other["started"] = True
            other["b"] = _publish(seeded)
        return real(session, project_name)

    monkeypatch.setattr(neo4j_load, "_current", current)
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), "2026-01-01T00:00:00.000+00:00")
    assert str(exc.value) == neo4j_load.NEWER_LOAD
    b = other["b"]
    assert b["verification"]["ok"]
    assert _count(db, "MATCH (n) WHERE n._projeto = 'demo' AND NOT n:Conceito AND NOT n:Termo RETURN count(n)") \
        == sum(EXPECTED_NODES.values())
    assert _count(db, "MATCH (m:_AkmeProjeto {projeto: 'demo'}) RETURN m.carga_atual") == b["carga"]
    assert neo4j_load.verify(build_plan(seeded), "demo", 9, 10)["ok"]


def test_real_malformed_csv_is_refused_by_the_plan(seeded, db):
    from akme.tools.publish import PublishError

    path = seeded.root / "data" / "clientes.csv"
    path.write_text(path.read_text(encoding="utf-8") + "9,Bia, Jr,1,SP,2023-01-01,S\n", encoding="utf-8")
    with pytest.raises(PublishError, match="1 linha\\(s\\) de clientes com colunas a mais ou a menos; primeira: linha 10"):
        _publish(seeded)
    assert _count(db, "MATCH (n) RETURN count(n)") == 0


def _with_label(plan, old, new):
    import dataclasses

    plan.sources = [dataclasses.replace(s, label=new) if s.label == old else s for s in plan.sources]
    plan.edges = [dataclasses.replace(e, domain=new if e.domain == old else e.domain, range=new if e.range == old else e.range)
                  for e in plan.edges]
    plan.nodes = {(new if k == old else k): v for k, v in plan.nodes.items()}
    return plan


def test_real_backtick_label_loads_and_unicode_escape_is_refused(seeded, db):
    from akme.tools.neo4j_plan import build_plan
    from akme.tools.publish import PublishError

    escaped = _with_label(build_plan(seeded), "Cliente", "Cli\\u0060ente")
    with pytest.raises(PublishError, match="carga recusada, nada foi gravado: .*identificador"):
        neo4j_load.load(seeded, escaped, "2026-01-01T00:00:00.000+00:00")
    assert _count(db, "MATCH (n) RETURN count(n)") == 0, "recusado antes de conectar"

    plan = _with_label(build_plan(seeded), "Cliente", "Cli`ente")
    neo4j_load.load(seeded, plan, "2026-01-01T00:00:00.000+00:00")
    assert neo4j_load.verify(plan, "demo", 9, 10)["ok"]
    labels = set(_count(db, "MATCH (n) UNWIND labels(n) AS l RETURN collect(DISTINCT l)"))
    assert labels == {"Cli`ente", "Pedido", "ItemPedido", "Produto", "Conceito", "Termo", "_AkmeProjeto"}
    assert _count(db, "MATCH (:Pedido)-[r:pertenceA]->(:`Cli``ente`) RETURN count(r)") == 10


# --- releitura ---

def test_real_newer_load_mid_blocks_leaves_the_database_as_the_newer_one(seeded, db, monkeypatch):
    """A grava o primeiro bloco; B comeca e termina; o bloco seguinte de A e barrado pela trava e A para sem sujar."""
    from akme.tools.neo4j_plan import build_plan
    from akme.tools.publish import PublishError

    real, state = neo4j_load._node_rows, {"calls": 0}

    def node_rows(*args):
        state["calls"] += 1
        if state["calls"] == 2 and "b" not in state:  # segundo bloco de A: B roda inteira antes
            state["b"] = "rodando"
            state["b"] = _publish(seeded)
        return real(*args)

    monkeypatch.setattr(neo4j_load, "_node_rows", node_rows)
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), "2026-01-01T00:00:00.000+00:00")
    assert str(exc.value) == neo4j_load.NEWER_LOAD
    b = state["b"]
    assert b["verification"]["ok"]
    data = "n._projeto = 'demo' AND NOT n:Conceito AND NOT n:Termo"
    assert _count(db, f"MATCH (n) WHERE {data} RETURN count(n)") == sum(EXPECTED_NODES.values())
    assert _count(db, f"MATCH (n) WHERE {data} AND n._carga <> $c RETURN count(n)", c=b["carga"]) == 0, "nada de A"
    assert _count(db, "MATCH (n)-[r]->() WHERE n._projeto = 'demo' AND r._carga <> $c RETURN count(r)", c=b["carga"]) == 0
    assert neo4j_load.verify(build_plan(seeded), "demo", 9, 10)["ok"]


def test_real_lock_inside_the_sync_command_deletes_nothing(seeded, db, monkeypatch):
    """Checagem em Python contornada; a marca e trocada no banco antes da sincronizacao: o servidor nao apaga nada."""
    from akme.tools.neo4j_plan import build_plan

    _publish(seeded)
    path = seeded.root / "data" / "clientes.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line for line in lines if not line.startswith("3,")) + "\n", encoding="utf-8")
    carga, swapped = "2026-01-01T00:00:00.000+00:00", []

    def current(session, project_name):
        if not swapped:  # outra carga troca a marca entre a checagem e o comando
            db.execute_query("MATCH (m:_AkmeProjeto {projeto: 'demo'}) SET m.carga_atual = 'outra'")
            swapped.append(True)
        return carga

    monkeypatch.setattr(neo4j_load, "_current", current)
    result = neo4j_load.load(seeded, build_plan(seeded), carga)
    assert result["removed"] == {"nodes": 0, "relationships": 0}
    assert _count(db, "MATCH (c:Cliente {_id: '3'}) RETURN count(c)") == 1, "a trava no comando segurou a remocao"
    assert _count(db, "MATCH (n) WHERE n._projeto = 'demo' AND n._carga <> $c AND NOT n:Conceito RETURN count(n)", c=carga) > 0


def test_real_unknown_property_notice_is_not_logged(db, caplog):
    import logging

    import neo4j

    caplog.set_level(logging.DEBUG, logger="neo4j")
    query = "MATCH (n) WHERE n.propriedade_que_nunca_existiu_akme IS NOT NULL RETURN count(n) AS c"
    uri, user, password = (os.environ[v] for v in VARS)
    with neo4j.GraphDatabase.driver(uri, auth=(user, password)) as plain, plain.session() as session:
        notes = session.run(query).consume().gql_status_objects
    assert any(s.gql_status == "01N52" for s in notes), "controle: sem a opcao, o servidor avisa"
    caplog.clear()
    with neo4j_load._driver() as driver, neo4j_load._session(driver) as session:
        notes = session.run(query).consume().gql_status_objects
    assert not any(s.gql_status == "01N52" for s in notes)
    assert not any("01N52" in r.getMessage() or "does not exist" in r.getMessage() for r in caplog.records)


def test_real_newer_load_during_the_ontology_leaves_the_newer_one_intact(seeded, db, monkeypatch):
    """A grava os dados; antes do primeiro comando da ontologia de A, B roda inteira. A trava barra a ontologia de
    A: nada da ontologia de B e recarimbado, o esquema e o de B e o banco fica igual ao de B."""
    from akme.tools.neo4j_plan import build_plan
    from akme.tools.publish import PublishError

    real, state = neo4j_load._write_rows, {}

    def write_rows(session, query, params):
        if "MERGE (c:Conceito" in query and "b" not in state:
            state["b"] = "rodando"
            state["b"] = _publish(seeded)
        return real(session, query, params)

    monkeypatch.setattr(neo4j_load, "_write_rows", write_rows)
    with pytest.raises(PublishError) as exc:
        neo4j_load.load(seeded, build_plan(seeded), "2026-01-01T00:00:00.000+00:00")
    assert str(exc.value) == neo4j_load.NEWER_LOAD
    b = state["b"]
    assert b["verification"]["ok"]
    assert _count(db, "MATCH (n) WHERE n._projeto = 'demo' AND n._carga <> $c RETURN count(n)", c=b["carga"]) == 0
    assert _count(db, "MATCH (n)-[r]->() WHERE n._projeto = 'demo' AND r._carga <> $c RETURN count(r)", c=b["carga"]) == 0
    assert _count(db, "MATCH (m:_AkmeProjeto {projeto: 'demo'}) RETURN m.carga_atual") == b["carga"]
    assert _count(db, "MATCH (m:_AkmeProjeto {projeto: 'demo'}) RETURN m.esquema").startswith("# Esquema do grafo")
    assert neo4j_load.verify(build_plan(seeded), "demo", 9, 10)["ok"]


# --- Task 11: nomes do TTL, espelho da ontologia, legenda name e guia -------------------------------------------

def test_real_ttl_names_and_the_native_map_has_no_false_arrows(seeded, db):
    first = _publish(seeded)
    assert first["verification"]["ok"]
    data = {(r["a"], r["t"], r["b"]): r["c"] for r in db.execute_query(
        "MATCH (a)-[r]->(b) WHERE NOT a:Conceito AND NOT a:Termo "
        "RETURN labels(a)[0] AS a, type(r) AS t, labels(b)[0] AS b, count(r) AS c").records}
    assert data == {("Pedido", "pertenceA", "Cliente"): 10, ("Pedido", "contem", "ItemPedido"): 17,
                    ("ItemPedido", "referencia", "Produto"): 17}
    # o mapa nativo: setas de dado so entre os pares do plano, com o nome do TTL; as setas entre Conceito tem outro
    # tipo (RELACAO_ONTOLOGIA) e nao viram setas falsas entre labels de dado
    drawn = sorted((r["a"], r["t"], r["b"]) for r in db.execute_query(
        "CALL db.schema.visualization() YIELD relationships UNWIND relationships AS r "
        "WITH startNode(r).name AS a, type(r) AS t, endNode(r).name AS b "
        "WHERE NOT a IN ['Conceito', 'Termo', '_AkmeProjeto'] RETURN a, t, b").records)
    assert drawn == sorted(data)
    time.sleep(0.01)
    second = _publish(seeded)
    assert second["removed"] == {"nodes": 0, "relationships": 0}


def test_real_ontology_layer_mirrors_the_schema_ttl(seeded, db):
    from akme.ontology import classes, load_graph, relations

    _publish(seeded)
    g = load_graph(seeded.schema_path)
    names = {c["name"] for c in classes(g)}
    arrows = sorted((d, r["name"], x) for r in relations(g) for d in set(r["domain"]) for x in set(r["range"])
                    if d in names and x in names)
    subclasses = sorted((c["name"], p) for c in classes(g) for p in set(c["subclass_of"]) if p in names)
    assert _count(db, "MATCH (c:Conceito {_projeto: 'demo'}) RETURN count(c)") == len(names)
    got = sorted((r["a"], r["n"], r["b"]) for r in db.execute_query(
        "MATCH (a:Conceito)-[r:RELACAO_ONTOLOGIA]->(b:Conceito) RETURN a.nome AS a, r.nome AS n, b.nome AS b").records)
    assert got == arrows and len(arrows) == 5, "inversas incluidas, como no grafo da pagina"
    got_sub = sorted((r["a"], r["b"]) for r in db.execute_query(
        "MATCH (a:Conceito)-[:SUBCLASSE_DE]->(b:Conceito) RETURN a.nome AS a, b.nome AS b").records)
    assert got_sub == subclasses
    flags = {r["n"]: (r["p"], r["i"]) for r in db.execute_query(
        "MATCH (:Conceito)-[r:RELACAO_ONTOLOGIA]->(:Conceito) RETURN r.nome AS n, r.publicada_nos_dados AS p, "
        "r.inversa_de AS i").records}
    assert flags["pertenceA"] == (True, None) and flags["possuiPedido"] == (False, "pertenceA")
    assert _count(db, "MATCH (:Conceito)-[r]->(:Conceito) WHERE NOT type(r) IN ['RELACAO_ONTOLOGIA', 'SUBCLASSE_DE'] "
                      "RETURN count(r)") == 0


def test_real_preview_shows_edge_types_that_this_load_drops(seeded, db):
    """Banco com arestas de um nome que a origem nao grava mais (relacao renomeada, ou carga da Task 11 com
    UPPER_SNAKE): a previa conta por tipo e avisa; a sincronizacao apaga as antigas."""
    from akme.tools.neo4j_plan import build_plan

    _publish(seeded)
    db.execute_query("MATCH (a:Pedido)-[r:pertenceA]->(b:Cliente) CREATE (a)-[n:PERTENCE_A]->(b) SET n = properties(r)")
    plan = build_plan(seeded)
    preview = neo4j_load.publish_neo4j(seeded, {"project": "demo", "version": "0.1.0"}, dry_run=True, plan=plan)
    lines = neo4j_load.preview_lines(preview, neo4j_load.destination_state(seeded, plan))
    assert "  PERTENCE_A: banco 10 -> origem 0, pelo menos 10 serao removidas" in lines
    assert "  pertenceA: banco 10 -> origem 10" in lines
    assert any("PERTENCE_A" in line and "nao grava" in line for line in lines)
    time.sleep(0.01)
    result = _publish(seeded)
    assert result["removed"] == {"nodes": 0, "relationships": 10}
    assert _count(db, "MATCH (:Pedido)-[r:PERTENCE_A]->(:Cliente) RETURN count(r)") == 0
    assert _count(db, "MATCH (:Pedido)-[r:pertenceA]->(:Cliente) RETURN count(r)") == 10


def test_real_load_rewrites_the_guide_for_this_database(seeded, db):
    result = _publish(seeded)
    assert not any(k.startswith("cq_") for k in result)
    guide = (seeded.docs_dir / "publish" / "neo4j_guia.html").read_text(encoding="utf-8")
    assert guide.count("<slide ") == 6
    assert "apoc.create" not in guide and "RETURN a, r, b" in guide, "o banco de teste nao tem APOC"
    assert neo4j_load.has_apoc() is False
    with (seeded.docs_dir / "publish" / "neo4j_consultas.csv").open(encoding="utf-8", newline="") as f:
        queries = [(r["name"], r["query"]) for r in csv.DictReader(f) if r["query"]]
    assert len(queries) == 2 + 4
    for name, query in queries:  # toda consulta do guia roda neste banco e devolve algo
        assert db.execute_query(query).records, name


def test_real_every_node_has_a_distinguishing_caption(seeded, db):
    _publish(seeded)
    rows = db.execute_query("MATCH (n) WHERE n._projeto = 'demo' AND NOT n:Conceito AND NOT n:Termo "
                            "RETURN labels(n)[0] AS l, n.name AS name").records
    assert len(rows) == sum(EXPECTED_NODES.values())
    assert all(r["name"] and r["name"].startswith(r["l"] + " ") for r in rows)
    assert len({r["name"] for r in rows}) == len(rows)
    assert _count(db, "MATCH (c:Conceito {nome: 'Pedido'}) RETURN c.name") == "Pedido"
    assert _count(db, "MATCH (t:Termo {nome: 'uf'}) RETURN t.name") == "uf"
    assert _count(db, "MATCH (m:_AkmeProjeto {projeto: 'demo'}) RETURN m.name") == "Projeto demo"
    assert _count(db, "MATCH (c:Cliente {_id: '1'}) RETURN c.name") == "Cliente 1 SP"


def _script(name):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, DEMO / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("on", [False, True])
def test_real_demo_checkers_pass_after_a_load(seeded, db, monkeypatch, capsys, on):
    """verificar_neo4j.py (contra os CSVs e o gabarito) e amostra_valores.py (valor, tipo e legenda), nos dois modos
    da _descricao; o verificador le o modo do akme.yml da pasta atual, como na demo."""
    project = _descricao(seeded, on)
    _publish(project)
    monkeypatch.chdir(project.root)
    checker = _script("verificar_neo4j")
    monkeypatch.setattr(checker, "PROJETO", "demo")
    assert checker.main() == 0, capsys.readouterr().out
    out = capsys.readouterr().out
    assert ("_descricao igual a Conceito.definicao" in out) is on and ("opcao desligada" in out) is not on
    sample = _script("amostra_valores")
    monkeypatch.setattr("sys.argv", ["amostra_valores.py", str(project.root / "akme.yml"), "--n", "50"])
    assert sample.main() == 0, capsys.readouterr().out
    # o modo errado no verificador falha: ele confere o que o akme.yml diz, nao o que o banco tem
    monkeypatch.setattr(checker, "DESCRICAO", not on)
    assert checker.main() == 1


# --- rodada final: carga completa a partir de um Postgres real ---

PG_SCHEMA = "akme_demo_it"


@pytest.mark.skipif(not os.environ.get("AKME_PG_TEST_DSN"), reason="Postgres real so com AKME_PG_TEST_DSN")
def test_real_load_from_postgres(seeded, db, monkeypatch, capsys):
    """Do Postgres ao Neo4j: as 4 tabelas da demo num schema proprio (colunas texto, celula vazia vira NULL), o
    adapter postgres no akme.yml, a carga completa, as contagens do plano e o verificador da demo contra os CSVs.
    ATENCAO: apaga e recria o schema akme_demo_it do banco de AKME_PG_TEST_DSN."""
    psycopg = pytest.importorskip("psycopg")
    from akme.project import read_yaml, write_yaml

    dsn = os.environ["AKME_PG_TEST_DSN"]
    with psycopg.connect(dsn) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {PG_SCHEMA} CASCADE")
        conn.execute(f"CREATE SCHEMA {PG_SCHEMA}")
        for table in ("clientes", "itens_pedido", "pedidos", "produtos"):
            path = DEMO / f"{table}.csv"
            with path.open(encoding="utf-8-sig", newline="") as f:
                header = next(csv.reader(f))
            columns = ", ".join(f'"{c}" text' for c in header)
            conn.execute(f'CREATE TABLE {PG_SCHEMA}."{table}" ({columns})')
            with conn.cursor().copy(f'COPY {PG_SCHEMA}."{table}" FROM STDIN WITH (FORMAT csv, HEADER true)') as copy:
                copy.write(path.read_bytes().removeprefix(b"\xef\xbb\xbf"))
    try:
        monkeypatch.setenv("AKME_PG_TEST_DSN_LOAD", dsn)
        config = read_yaml(seeded.root / "akme.yml")
        config.pop("local_folder")
        write_yaml(seeded.root / "akme.yml", {**config, "adapter": "postgres",
                                              "postgres": {"dsn": "env:AKME_PG_TEST_DSN_LOAD", "schema": PG_SCHEMA}})
        project = Project(seeded.root)
        result = _publish(project)
        assert result["verification"] == {"ok": True, "divergences": []}
        assert result["nodes"] == EXPECTED_NODES and result["relationships"] == EXPECTED_EDGES
        assert result["rows"] == 43 and result["removed"] == {"nodes": 0, "relationships": 0}
        monkeypatch.chdir(project.root)
        checker = _script("verificar_neo4j")
        monkeypatch.setattr(checker, "PROJETO", "demo")
        assert checker.main() == 0, capsys.readouterr().out
        assert "RESULTADO: todas as verificacoes passaram" in capsys.readouterr().out
        sample = _script("amostra_valores")
        monkeypatch.setattr("sys.argv", ["amostra_valores.py", str(project.root / "akme.yml"), "--n", "50"])
        assert sample.main() == 0, capsys.readouterr().out
        assert _publish(project)["removed"] == {"nodes": 0, "relationships": 0}
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {PG_SCHEMA} CASCADE")
