from __future__ import annotations

from typing import Any

from .base import SqlAdapter, require

SKIP_CATALOGS = ("system", "__databricks_internal")
SKIP_SCHEMAS = ("information_schema",)

class DatabricksAdapter(SqlAdapter):
    name = "databricks"

    def __init__(self, host: str = "", http_path: str = "", token: str = "",
                 catalog: str = "", schema: str = "") -> None:
        super().__init__()
        self.host, self.http_path, self.token = host, http_path, token
        self.catalog = catalog or ""
        self.schema = schema or ""

    def connect(self) -> Any:
        require("databricks.sql", "databricks")
        from databricks import sql
        return sql.connect(server_hostname=self.host, http_path=self.http_path, access_token=self.token)

    def _parse_source(self, source: str) -> tuple[str, str, str]:
        parts = source.split(".")
        if len(parts) == 3:
            return parts[0], parts[1], parts[2]
        if len(parts) == 2:
            return self.catalog or "main", parts[0], parts[1]
        return self.catalog or "main", self.schema or "default", source

    def discover(self, catalog: str = "", schema: str = "") -> dict[str, Any]:
        """Percorre catalogos, schemas e tabelas visiveis para o token.

        Sem `catalog` (ou `schema`), varre todos. Falhas de permissao num catalogo ou
        schema ficam registradas em `error` e nao interrompem a varredura.
        """
        result: dict[str, Any] = {"catalogs": [], "errors": []}
        if catalog:
            catalogs = [catalog]
        else:
            try:
                catalogs = [r["catalog"] for r in self.query("SHOW CATALOGS")
                            if r.get("catalog") and r["catalog"] not in SKIP_CATALOGS]
            except Exception as exc:
                result["errors"].append({"where": "SHOW CATALOGS", "error": str(exc)})
                return result

        for cat in catalogs:
            cat_entry: dict[str, Any] = {"name": cat, "schemas": []}
            result["catalogs"].append(cat_entry)
            if schema:
                schemas = [schema]
            else:
                try:
                    schemas = [r["databaseName"] for r in self.query(f"SHOW SCHEMAS IN {cat}")
                               if r.get("databaseName") and r["databaseName"] not in SKIP_SCHEMAS]
                except Exception as exc:
                    cat_entry["error"] = str(exc)
                    result["errors"].append({"where": cat, "error": str(exc)})
                    continue

            for sch in schemas:
                sch_entry: dict[str, Any] = {"name": sch, "tables": []}
                cat_entry["schemas"].append(sch_entry)
                try:
                    rows = self.query(f"SHOW TABLES IN {cat}.{sch}")
                except Exception as exc:
                    sch_entry["error"] = str(exc)
                    result["errors"].append({"where": f"{cat}.{sch}", "error": str(exc)})
                    continue
                sch_entry["tables"] = [
                    {"name": r["tableName"], "full_name": f"{cat}.{sch}.{r['tableName']}",
                     "is_temporary": bool(r.get("isTemporary", False))}
                    for r in rows if r.get("tableName")
                ]
        return result

    def list_sources(self) -> list[str]:
        found = self.discover(self.catalog, self.schema)
        return [t["full_name"] for c in found["catalogs"] for s in c["schemas"] for t in s["tables"]]

    def read_schema(self, source: str) -> dict[str, Any]:
        cat, sch, tbl = self._parse_source(source)
        rows = self.query(f"DESCRIBE TABLE {cat}.{sch}.{tbl}")
        cols = [
            {"name": r["col_name"], "type": r["data_type"]}
            for r in rows
            if r.get("col_name") and not str(r["col_name"]).startswith("#")
        ]
        return {"name": source, "columns": cols}

    def read_sample(self, source: str, n: int = 100) -> list[dict[str, Any]]:
        cat, sch, tbl = self._parse_source(source)
        return self.query(f"SELECT * FROM {cat}.{sch}.{tbl} LIMIT {int(n)}")
