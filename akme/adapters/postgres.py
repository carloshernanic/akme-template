from __future__ import annotations

import uuid
from typing import Any, Iterator

from .base import SqlAdapter, require


class PostgresAdapter(SqlAdapter):
    name = "postgres"

    def __init__(self, dsn: str = "", schema: str = "public") -> None:
        super().__init__()
        self._reading = 0  # leituras em blocos abertas nesta conexao
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

    def iter_rows(self, source: str, batch: int = 5000) -> Iterator[list[dict[str, Any]]]:
        """Cursor do lado do servidor, com nome unico por leitura (duas leituras abertas nao colidem). No fim, a
        ultima leitura aberta desfaz a transacao que o cursor abriu: a conexao nao fica "idle in transaction"."""
        self._reading += 1
        try:
            yield from self._iter_query(f'SELECT * FROM "{self.schema}"."{source}"', batch,
                                        cursor=self.conn.cursor(name=f"akme_iter_{uuid.uuid4().hex}"))
        finally:
            self._reading -= 1
            if not self._reading and self._conn is not None:
                try:
                    self._conn.rollback()
                except Exception:  # conexao ja quebrada: o erro que importa e o da leitura, que segue
                    pass
