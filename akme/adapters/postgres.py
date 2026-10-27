from __future__ import annotations

from typing import Any

from .base import SqlAdapter, require


class PostgresAdapter(SqlAdapter):
    name = "postgres"

    def __init__(self, dsn: str = "", schema: str = "public") -> None:
        super().__init__()
        self.dsn = dsn
        self.schema = schema

    def connect(self) -> Any:
        require("psycopg", "postgres")
        import psycopg
        return psycopg.connect(self.dsn)

    def list_sources(self) -> list[str]:
        rows = self.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY 1",
            (self.schema,),
        )
        return [r["table_name"] for r in rows]

    def read_schema(self, source: str) -> dict[str, Any]:
        rows = self.query(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (self.schema, source),
        )
        return {"name": source, "columns": [{"name": r["column_name"], "type": r["data_type"]} for r in rows]}

    def read_sample(self, source: str, n: int = 100) -> list[dict[str, Any]]:
        return self.query(f'SELECT * FROM "{self.schema}"."{source}" LIMIT {int(n)}')
