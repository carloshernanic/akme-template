"""Dubles compartilhados dos testes do Neo4j: sessao falsa que registra (consulta, parametros) e a fixture `fake`."""
from __future__ import annotations

import re

import pytest

PASSWORD = "senha-que-nao-pode-aparecer"
EXPECTED_NODES = {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
EXPECTED_EDGES = {"contem": 17, "pertenceA": 10, "referencia": 17}
CONCEPTS = 5  # classes do dominio da demo; as de base do akme nao viram Conceito
TERMS = 10
CARGA = "2026-11-12T10:00:00.000+00:00"


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


class _Tx:
    """Transacao gerenciada falsa: repassa a consulta a sessao e marca que ela foi gravada por execute_write."""

    def __init__(self, session):
        self.session = session

    def run(self, query, parameters=None, **params):
        result = self.session.run(query, parameters, **params)  # busca run na hora: testes trocam session.run
        self.session.written.append(query)
        return result


class _FakeSession:
    """Simula o Neo4j: responde estado, versao, carga atual, contagens e awaitIndexes; registra cada consulta com os
    parametros. `written` guarda as consultas gravadas por execute_write (transacao gerenciada, com nova tentativa).
    `other_load_at`: na n-esima leitura da carga atual da marca, responde a carga de outra execucao (corrida)."""

    def __init__(self, state=None, legacy_constraint=False, fail_unwind=None, counts=None, error=None, deleted=(0, 0),
                 version="2026.10.1", other_load_at=None, other_load_after_unwind=None, apoc=False):
        self.state = {"projetos": [], "total": 0, "alheios": 0, "legado": False, **(state or {})}
        self.legacy_constraint, self.fail_unwind, self.error, self.deleted = legacy_constraint, fail_unwind, error, deleted
        self.counts = {**EXPECTED_NODES, **EXPECTED_EDGES, "Conceito": CONCEPTS, "Termo": TERMS, **(counts or {})}
        self.calls: list[tuple[str, dict]] = []
        self.written: list[str] = []
        self.unwinds = 0
        self.version, self.other_load_at = version, other_load_at
        self.claimed, self.current_reads = None, 0
        self.apoc = apoc  # o banco tem apoc.create.vRelationship (mapa da ontologia do guia)
        # depois de N blocos de dados, outra carga troca a marca: os blocos seguintes nao gravam (trava do bloco)
        self.other_load_after_unwind = other_load_after_unwind

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def queries(self) -> list[str]:
        return [q for q, _ in self.calls]

    def index(self, fragment: str) -> int:
        return next(i for i, q in enumerate(self.queries()) if fragment in q)

    def execute_write(self, work, *args, **kwargs):
        return work(_Tx(self), *args, **kwargs)

    def run(self, query, parameters=None, **params):
        import neo4j

        params = {**(parameters or {}), **params}
        self.calls.append((query, params))
        if self.error:
            raise self.error
        if "COLLECT" in query:
            return _Result([{k: v for k, v in self.state.items() if k in ("projetos", "total", "alheios", "legado")}])
        if "dbms.components" in query:
            return _Result([{"versao": self.version}])
        if "SET m.carga_atual" in query:
            self.claimed = params.get("carga")
            return _Result([])
        if "m.carga_atual AS" in query:
            self.current_reads += 1
            other = self.other_load_at is not None and self.current_reads >= self.other_load_at
            return _Result([{"carga": "outra-carga" if other else self.claimed}])
        if "SHOW CONSTRAINTS" in query:
            return _Result([{"c": int(self.legacy_constraint)}])
        if "SHOW FUNCTIONS" in query:
            return _Result([{"c": int(self.apoc)}])
        if "type(r) AS tipo" in query:
            return _Result([{"tipo": k, "c": v} for k, v in self.state.get("arestas_no_banco", {}).items()])
        if "UNWIND labels(n)" in query:
            return _Result([{"label": k, "c": v} for k, v in self.state.get("no_banco", {}).items()])
        if "UNWIND $rows" in query:
            self.unwinds += 1
            if self.unwinds == self.fail_unwind:
                raise neo4j.exceptions.ClientError("regra violada")
            if self.other_load_after_unwind is not None and self.unwinds > self.other_load_after_unwind:
                self.claimed = "outra-carga"
            locked = "m.carga_atual = $carga" in query and self.claimed != params.get("carga")
            return _Result([{"gravadas": 0 if locked else len(params.get("rows") or [])}])
        if "AS gravadas" in query:  # comando da ontologia ou do esquema, tambem com a trava
            locked = "m.carga_atual = $carga" in query and self.claimed != params.get("carga")
            return _Result([{"gravadas": 0 if locked else 1}])
        if "DETACH DELETE" in query:
            return _Result([], _Counters(self.deleted[0], self.deleted[1]))
        if "DELETE r" in query:
            return _Result([], _Counters(0, self.deleted[1]))
        if "count(" in query:
            m = re.search(r"\[r:`([^`]+)`\]", query) or re.search(r"\((?:n|c|t):`?([A-Za-z_]+)`?", query)
            return _Result([{"c": self.counts[m.group(1)]}])
        return _Result([])


@pytest.fixture
def fake(monkeypatch):
    neo4j = pytest.importorskip("neo4j")
    holder = {"session": _FakeSession(), "session_kwargs": [], "driver_kwargs": []}

    class Driver:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def session(self, **kwargs):
            holder["session_kwargs"].append(kwargs)
            return holder["session"]

    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://host:7687")
    monkeypatch.setenv("AKME_NEO4J_USER", "x")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    monkeypatch.delenv("AKME_NEO4J_DATABASE", raising=False)
    def driver(*a, **k):
        holder["driver_kwargs"].append(k)
        return Driver()

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", driver)

    def use(session):
        holder["session"] = session
        return session

    holder["use"] = use
    return holder
