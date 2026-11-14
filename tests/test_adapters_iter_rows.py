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
