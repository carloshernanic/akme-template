from __future__ import annotations

from typing import Any

from .base import SqlAdapter, require


class DatabricksAdapter(SqlAdapter):
    name = "databricks"

    def __init__(self, host: str = "", http_path: str = "", token: str = "",
                 catalog: str = "main", schema: str = "default") -> None:
        super().__init__()
        self.host, self.http_path, self.token = host, http_path, token
        self.catalog, self.schema = catalog, schema

    def connect(self) -> Any:
        require("databricks.sql", "databricks")
        from databricks import sql
        return sql.connect(server_hostname=self.host, http_path=self.http_path, access_token=self.token)

    def list_sources(self) -> list[str]:
        rows = self.query(f"SHOW TABLES IN {self.catalog}.{self.schema}")
        return [r["tableName"] for r in rows]

    def read_schema(self, source: str) -> dict[str, Any]:
        rows = self.query(f"DESCRIBE TABLE {self.catalog}.{self.schema}.{source}")
        cols = [
            {"name": r["col_name"], "type": r["data_type"]}
            for r in rows
            if r.get("col_name") and not str(r["col_name"]).startswith("#")
        ]
        return {"name": source, "columns": cols}

    def read_sample(self, source: str, n: int = 100) -> list[dict[str, Any]]:
        return self.query(f"SELECT * FROM {self.catalog}.{self.schema}.{source} LIMIT {int(n)}")
