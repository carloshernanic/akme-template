"""Dubles compartilhados dos testes do Neo4j: sessao falsa que registra (consulta, parametros) e a fixture `fake`."""
from __future__ import annotations

import re

import pytest

PASSWORD = "senha-que-nao-pode-aparecer"
EXPECTED_NODES = {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
EXPECTED_EDGES = {"contem": 17, "pertenceA": 10, "referencia": 17}
CONCEPTS = 9
CARGA = "2026-11-12T10:00:00+00:00"


class _Counters:
    def __init__(self, nodes=0, relationships=0):
        self.nodes_deleted, self.relationships_deleted = nodes, relationships


class _Summary:
    def __init__(self, counters):
        self.counters = counters


class _Result:
    def __init__(self, rows, counters=None):
        self.rows, self.counters = rows, counters or _Counters()

    def __iter__(self):
        return iter(self.rows)

    def single(self):
        return self.rows[0] if self.rows else None

    def consume(self):
        return _Summary(self.counters)


class _FakeSession:
    """Simula o Neo4j: responde estado, contagens e awaitIndexes; registra cada consulta com os parametros."""

    def __init__(self, state=None, legacy_constraint=False, fail_unwind=None, counts=None, error=None, deleted=(0, 0)):
        self.state = {"projetos": [], "total": 0, "alheios": 0, "legado": False, **(state or {})}
        self.legacy_constraint, self.fail_unwind, self.error, self.deleted = legacy_constraint, fail_unwind, error, deleted
        self.counts = {**EXPECTED_NODES, **EXPECTED_EDGES, "Conceito": CONCEPTS, **(counts or {})}
        self.calls: list[tuple[str, dict]] = []
        self.unwinds = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def queries(self) -> list[str]:
        return [q for q, _ in self.calls]

    def index(self, fragment: str) -> int:
        return next(i for i, q in enumerate(self.queries()) if fragment in q)

    def run(self, query, parameters=None, **params):
        import neo4j

        params = {**(parameters or {}), **params}
        self.calls.append((query, params))
        if self.error:
            raise self.error
        if "COLLECT" in query:
            return _Result([{k: v for k, v in self.state.items() if k in ("projetos", "total", "alheios", "legado")}])
        if "SHOW CONSTRAINTS" in query:
            return _Result([{"c": int(self.legacy_constraint)}])
        if "UNWIND labels(n)" in query:
            return _Result([{"label": k, "c": v} for k, v in self.state.get("no_banco", {}).items()])
        if query.startswith("UNWIND $rows"):
            self.unwinds += 1
            if self.unwinds == self.fail_unwind:
                raise neo4j.exceptions.ClientError("regra violada")
            return _Result([])
        if "DETACH DELETE" in query:
            return _Result([], _Counters(self.deleted[0], self.deleted[1]))
        if "DELETE r" in query:
            return _Result([], _Counters(0, self.deleted[1]))
        if "count(" in query:
            m = re.search(r"\[r:`([^`]+)`\]", query) or re.search(r"\((?:n|c):`?([A-Za-z_]+)`?", query)
            return _Result([{"c": self.counts[m.group(1)]}])
        return _Result([])


@pytest.fixture
def fake(monkeypatch):
    neo4j = pytest.importorskip("neo4j")
    holder = {"session": _FakeSession()}

    class Driver:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def session(self, **kwargs):
            return holder["session"]

    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://host:7687")
    monkeypatch.setenv("AKME_NEO4J_USER", "x")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    monkeypatch.setattr(neo4j.GraphDatabase, "driver", lambda *a, **k: Driver())

    def use(session):
        holder["session"] = session
        return session

    holder["use"] = use
    return holder
