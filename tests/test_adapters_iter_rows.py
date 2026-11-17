from __future__ import annotations

import os

import pytest

from akme.adapters import load_adapter
from akme.adapters.base import Adapter, AdapterError, SqlAdapter
from akme.adapters.databricks import DatabricksAdapter
from akme.adapters.local_folder import LocalFolderAdapter
from akme.adapters.postgres import PostgresAdapter
from akme.adapters.snowflake import SnowflakeAdapter


class FakeCursor:
    def __init__(self, batches, description=(("id",), ("nome",))):
        self.batches = list(batches)
        self.description = description
        self.sql = None
        self.closed = False

    def execute(self, sql, params=()):
        self.sql = sql

    def fetchmany(self, n):
        return self.batches.pop(0) if self.batches else []

    def close(self):
        self.closed = True


class FakeConn:
    def __init__(self, cursor):
        self.cur = cursor
        self.cursor_kwargs = None
        self.rollbacks = 0

    def cursor(self, **kwargs):
        self.cursor_kwargs = kwargs
        return self.cur

    def rollback(self):
        self.rollbacks += 1


def _fake_cursor():
    return FakeCursor([[(1, "a"), (2, "b")], [(3, "c")], []])


def test_local_csv_in_blocks_matches_read_sample(project):
    ad = load_adapter(project.adapter_name, project.adapter_options())
    blocks = list(ad.iter_rows("itens_pedido", batch=5))
    assert [len(b) for b in blocks] == [5, 5, 5, 2]
    assert [r for b in blocks for r in b] == ad.read_sample("itens_pedido", 1000)


def test_csv_with_bom_has_clean_first_column(tmp_path):
    (tmp_path / "t.csv").write_bytes("﻿id,nome\n1,a\n".encode("utf-8"))
    ad = LocalFolderAdapter(str(tmp_path))
    assert list(ad.read_sample("t")[0]) == ["id", "nome"]
    assert next(ad.iter_rows("t"))[0] == {"id": "1", "nome": "a"}


def test_empty_source_yields_no_block(tmp_path):
    (tmp_path / "v.csv").write_text("id,nome\n", encoding="utf-8")
    assert list(LocalFolderAdapter(str(tmp_path)).iter_rows("v")) == []


def test_base_adapter_iter_rows_raises():
    class Dummy(Adapter):
        name = "dummy"

        def list_sources(self): return []
        def read_schema(self, source): return {}
        def read_sample(self, source, n=100): return []

    with pytest.raises(AdapterError, match="nao le em blocos"):
        next(iter(Dummy().iter_rows("x")))


def test_xlsx_in_blocks(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["id", "nome"])
    ws.append([1, "a"])
    ws.append([2, "b"])
    ws.append([3, "c"])
    wb.save(tmp_path / "p.xlsx")
    ad = LocalFolderAdapter(str(tmp_path))
    blocks = list(ad.iter_rows("p", batch=2))
    assert [len(b) for b in blocks] == [2, 1]
    assert [r for b in blocks for r in b] == ad.read_sample("p")


def test_sql_iter_uses_fetchmany_until_empty():
    class Sql(SqlAdapter):
        name = "sql"

        def connect(self): return FakeConn(cur)
        def list_sources(self): return []
        def read_schema(self, source): return {}
        def read_sample(self, source, n=100): return []

    cur = _fake_cursor()
    blocks = list(Sql()._iter_query("SELECT 1", 2))
    assert blocks == [[{"id": 1, "nome": "a"}, {"id": 2, "nome": "b"}], [{"id": 3, "nome": "c"}]]
    assert cur.closed


def test_postgres_uses_named_cursor():
    cur = _fake_cursor()
    ad = PostgresAdapter(dsn="x")
    ad._conn = FakeConn(cur)
    blocks = list(ad.iter_rows("t", batch=2))
    assert len(blocks) == 2
    first = ad._conn.cursor_kwargs["name"]
    assert first.startswith("akme_iter_") and ad._conn.rollbacks == 1, "transacao de leitura encerrada no fim"
    assert cur.sql == 'SELECT * FROM "public"."t"'
    assert "LIMIT" not in cur.sql


def test_snowflake_and_databricks_iter_without_limit():
    cur = _fake_cursor()
    sf = SnowflakeAdapter(database="DB", schema="SCH")
    sf._conn = FakeConn(cur)
    assert len(list(sf.iter_rows("t", batch=2))) == 2
    assert cur.sql == "SELECT * FROM DB.SCH.t"

    cur2 = _fake_cursor()
    dbx = DatabricksAdapter()
    dbx._conn = FakeConn(cur2)
    assert len(list(dbx.iter_rows("cat.sch.t", batch=2))) == 2
    assert cur2.sql == "SELECT * FROM cat.sch.t"


@pytest.mark.skipif(not os.environ.get("AKME_PG_TEST_DSN"), reason="Postgres real so com AKME_PG_TEST_DSN")
def test_postgres_real_iter_rows():
    pytest.importorskip("psycopg")
    ad = PostgresAdapter(dsn=os.environ["AKME_PG_TEST_DSN"])
    ad.execute("DROP TABLE IF EXISTS akme_iter_teste")
    ad.execute("CREATE TABLE akme_iter_teste AS SELECT g AS id FROM generate_series(1, 12) g")
    try:
        ad.conn.commit()
        blocks = list(ad.iter_rows("akme_iter_teste", batch=5))
        ad.conn.commit()
        assert [len(b) for b in blocks] == [5, 5, 2]
    finally:
        ad.conn.rollback()
        ad.execute("DROP TABLE IF EXISTS akme_iter_teste")
        ad.conn.commit()
        ad.close()


def test_sql_iter_refuses_non_positive_batch():
    ad = PostgresAdapter("dsn")
    ad._conn = FakeConn(_fake_cursor())
    with pytest.raises(ValueError, match="batch"):
        next(ad.iter_rows("t", 0))


def test_postgres_cursor_name_is_unique_per_read():
    ad = PostgresAdapter(dsn="x")
    ad._conn = FakeConn(_fake_cursor())
    list(ad.iter_rows("t", batch=2))
    first = ad._conn.cursor_kwargs["name"]
    ad._conn.cur = _fake_cursor()
    list(ad.iter_rows("t", batch=2))
    assert ad._conn.cursor_kwargs["name"] != first


def test_postgres_read_closed_early_still_ends_the_transaction():
    cur = _fake_cursor()
    ad = PostgresAdapter(dsn="x")
    ad._conn = FakeConn(cur)
    blocks = ad.iter_rows("t", batch=2)
    next(blocks)
    blocks.close()
    assert cur.closed and ad._conn.rollbacks == 1


class KeysCursor:
    """Cursor falso para query(): devolve as chaves do IN que existem em `table`."""
    def __init__(self, table):
        self.table, self.sqls, self.description = table, [], (("k",),)

    def execute(self, sql, params=()):
        self.sqls.append(sql)
        inside = sql[sql.index(" IN (") + 5:-1]
        self.rows = [(int(v.strip("'")),) for v in inside.split(", ") if int(v.strip("'")) in self.table]

    def fetchall(self):
        return self.rows

    def close(self):
        pass


@pytest.mark.parametrize("adapter, table_ref, col_ref", [
    (DatabricksAdapter(), "cat.sch.t", "`id`"),
    (SnowflakeAdapter(database="DB", schema="SCH"), "DB.SCH.t", '"id"'),
    (PostgresAdapter(schema="public"), '"public"."t"', '"id"'),
])
def test_sql_find_keys_asks_only_for_the_keys_in_blocks(adapter, table_ref, col_ref):
    cur = KeysCursor(table=set(range(0, 2000, 2)))
    adapter._conn = FakeConn(cur)
    wanted = {str(i) for i in range(1100)}
    found = adapter.find_keys("cat.sch.t" if isinstance(adapter, DatabricksAdapter) else "t", "id", wanted)
    assert found == {str(i) for i in range(0, 1100, 2)}
    assert len(cur.sqls) == 3, "1100 chaves em blocos de 500"
    assert all(s.startswith(f"SELECT DISTINCT {col_ref} AS k FROM {table_ref} WHERE {col_ref} IN (") for s in cur.sqls)
    assert "SELECT *" not in " ".join(cur.sqls)


def test_find_keys_escapes_quotes():
    cur = FakeCursor([])
    cur.fetchall = lambda: []
    dbx = DatabricksAdapter()
    dbx._conn = FakeConn(cur)
    assert dbx.find_keys("c.s.t", "id", {"o'brien"}) == set()
    assert "IN ('o''brien')" in cur.sql


def test_databricks_with_schema_shows_the_real_error_not_an_empty_list(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "databricks", None)
    monkeypatch.setitem(sys.modules, "databricks.sql", None)
    with pytest.raises(AdapterError, match="uv sync --inexact --extra databricks"):
        DatabricksAdapter(catalog="workspace", schema="olist").list_sources()

    dbx = DatabricksAdapter(catalog="workspace", schema="olist")
    def denied(sql, params=()):
        raise RuntimeError("PERMISSION_DENIED: User does not have USE SCHEMA")
    monkeypatch.setattr(dbx, "query", denied)
    with pytest.raises(AdapterError, match="PERMISSION_DENIED"):
        dbx.list_sources()


def test_databricks_connect_has_a_time_limit_and_explains_the_warehouse(monkeypatch):
    import sys
    import types
    calls = []
    fake = types.ModuleType("databricks.sql")
    fake.connect = lambda **kw: calls.append(kw) or object()
    pkg = types.ModuleType("databricks")
    pkg.sql = fake
    monkeypatch.setitem(sys.modules, "databricks", pkg)
    monkeypatch.setitem(sys.modules, "databricks.sql", fake)
    DatabricksAdapter(host="h", http_path="p", token="t", timeout="60").connect()
    assert calls[0]["_socket_timeout"] == 60 and calls[0]["_retry_stop_after_attempts_duration"] == 60

    def refused(**kw):
        raise OSError("connection refused")
    fake.connect = refused
    with pytest.raises(AdapterError, match="SQL Warehouse esta ligado"):
        DatabricksAdapter(host="h").connect()

    class MaxRetryDurationError(Exception):
        pass
    dbx = DatabricksAdapter()
    def slow(self, sql, params=()):
        raise MaxRetryDurationError("retry duration exceeded")
    monkeypatch.setattr(SqlAdapter, "query", slow)
    with pytest.raises(AdapterError, match="nao respondeu.*SQL Warehouse"):
        dbx.query("SELECT 1")
