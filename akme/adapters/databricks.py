from __future__ import annotations

from typing import Any, Iterator

from .base import AdapterError, SqlAdapter, require

SKIP_CATALOGS = ("system", "__databricks_internal")
SKIP_SCHEMAS = ("information_schema",)
# sem limite, o conector tenta de novo por ate 15 minutos quando o SQL Warehouse nao responde, sem mensagem
TIMEOUT = 300
WAREHOUSE_HINT = ("confira se o SQL Warehouse esta ligado e acessivel (host, http_path e token); "
                  "o limite de espera e a opcao timeout do akme.yml, em segundos")


def _unreachable(exc: BaseException) -> bool:
    name = type(exc).__name__
    return isinstance(exc, (TimeoutError, ConnectionError)) or any(w in name for w in ("Timeout", "Retry", "RequestError"))


class DatabricksAdapter(SqlAdapter):
    name = "databricks"

    def __init__(self, host: str = "", http_path: str = "", token: str = "",
                 catalog: str = "", schema: str = "", timeout: int | str = TIMEOUT) -> None:
        super().__init__()
        self.host, self.http_path, self.token = host, http_path, token
        self.timeout = int(timeout or TIMEOUT)
        self.catalog = catalog or ""
        self.schema = schema or ""

    def connect(self) -> Any:
        require("databricks.sql", "databricks")
        from databricks import sql
        try:
            return sql.connect(server_hostname=self.host, http_path=self.http_path, access_token=self.token,
                               _socket_timeout=self.timeout, _retry_stop_after_attempts_duration=self.timeout)
        except Exception as exc:
            raise AdapterError(f"nao conectou ao Databricks: {exc}. {WAREHOUSE_HINT}") from exc

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        try:
            return super().query(sql, params)
        except AdapterError:
            raise
        except Exception as exc:
            if _unreachable(exc):
                raise AdapterError(f"o Databricks nao respondeu: {exc}. {WAREHOUSE_HINT}") from exc
            raise

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
            except AdapterError:
                raise  # pacote opcional ausente: erro claro, nao uma lista vazia de fontes
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
                except AdapterError:
                    raise
                except Exception as exc:
                    cat_entry["error"] = str(exc)
                    result["errors"].append({"where": cat, "error": str(exc)})
                    continue

            for sch in schemas:
                sch_entry: dict[str, Any] = {"name": sch, "tables": []}
                cat_entry["schemas"].append(sch_entry)
                try:
                    rows = self.query(f"SHOW TABLES IN {cat}.{sch}")
                except AdapterError:
                    raise
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
        tables = [t["full_name"] for c in found["catalogs"] for s in c["schemas"] for t in s["tables"]]
        if not tables and found["errors"]:
            # sem isso o erro real (permissao negada, catalogo errado) virava "fonte inexistente" la na frente
            raise AdapterError("nenhuma tabela visivel no Databricks: "
                               + "; ".join(f"{e['where']}: {e['error']}" for e in found["errors"]))
        return tables

    def read_schema(self, source: str) -> dict[str, Any]:
        cat, sch, tbl = self._parse_source(source)
        rows = self.query(f"DESCRIBE TABLE {cat}.{sch}.{tbl}")
        cols = [
            {"name": r["col_name"], "type": r["data_type"]}
            for r in rows
            if r.get("col_name") and not str(r["col_name"]).startswith("#")
        ]
        return {"name": source, "columns": cols}

    def _table_ref(self, source: str) -> str:
        return ".".join(self._parse_source(source))

    def _column_ref(self, column: str) -> str:
        return "`" + column.replace("`", "``") + "`"

    def read_sample(self, source: str, n: int = 100) -> list[dict[str, Any]]:
        cat, sch, tbl = self._parse_source(source)
        return self.query(f"SELECT * FROM {cat}.{sch}.{tbl} LIMIT {int(n)}")

    def iter_rows(self, source: str, batch: int = 5000) -> Iterator[list[dict[str, Any]]]:
        cat, sch, tbl = self._parse_source(source)
        yield from self._iter_query(f"SELECT * FROM {cat}.{sch}.{tbl}", batch)
