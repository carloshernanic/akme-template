from __future__ import annotations

from typing import Any

from .base import SqlAdapter, require


class SnowflakeAdapter(SqlAdapter):
    name = "snowflake"

    def __init__(self, account: str = "", user: str = "", password: str = "", warehouse: str = "",
                 database: str = "", schema: str = "PUBLIC", role: str = "") -> None:
        super().__init__()
        params = dict(account=account, user=user, password=password, warehouse=warehouse,
                      database=database, schema=schema, role=role)
        self.params = {k: v for k, v in params.items() if v}
        self.database = database
        self.schema = schema

    def connect(self) -> Any:
        require("snowflake.connector", "snowflake")
        import snowflake.connector
        return snowflake.connector.connect(**self.params)

    def list_sources(self) -> list[str]:
        rows = self.query(
            f"SELECT table_name FROM {self.database}.information_schema.tables "
            f"WHERE table_schema = '{self.schema}' ORDER BY 1"
        )
        return [r["TABLE_NAME"] for r in rows]

    def read_schema(self, source: str) -> dict[str, Any]:
        rows = self.query(
            f"SELECT column_name, data_type FROM {self.database}.information_schema.columns "
            f"WHERE table_schema = '{self.schema}' AND table_name = '{source}' ORDER BY ordinal_position"
        )
        return {"name": source, "columns": [{"name": r["COLUMN_NAME"], "type": r["DATA_TYPE"]} for r in rows]}

    def read_sample(self, source: str, n: int = 100) -> list[dict[str, Any]]:
        return self.query(f"SELECT * FROM {self.database}.{self.schema}.{source} LIMIT {int(n)}")
