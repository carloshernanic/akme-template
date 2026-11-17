from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator


class AdapterError(RuntimeError):
    pass


def require(module: str, extra: str) -> None:
    try:
        __import__(module)
    except ImportError as exc:
        raise AdapterError(
            f"o adapter precisa do pacote '{module}'. Instale com: uv sync --inexact --extra {extra} (o --inexact mantem os outros extras instalados)"
        ) from exc


def check_batch(batch: int) -> None:
    """Bloco de zero linhas faria a fonte parecer vazia (e a sincronizacao do Neo4j apagaria o label inteiro)."""
    if batch <= 0:
        raise ValueError(f"batch deve ser positivo, recebi {batch}")


def _text_key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


KEYS_PER_QUERY = 500


class Adapter(ABC):
    name = "base"

    @abstractmethod
    def list_sources(self) -> list[str]: ...

    @abstractmethod
    def read_schema(self, source: str) -> dict[str, Any]: ...

    @abstractmethod
    def read_sample(self, source: str, n: int = 100) -> list[dict[str, Any]]: ...

    def iter_rows(self, source: str, batch: int = 5000) -> Iterator[list[dict[str, Any]]]:
        raise AdapterError(f"o adapter {self.name} nao le em blocos")

    def find_keys(self, source: str, column: str, keys: set[str]) -> set[str]:
        """Quais das `keys` existem em source.column (comparadas como texto). Aqui le a fonte em blocos e para quando
        acha todas; os adapters SQL perguntam so pelas chaves procuradas."""
        found: set[str] = set()
        for rows in self.iter_rows(source):
            found |= {k for k in (_text_key(r.get(column)) for r in rows) if k in keys}
            if found == keys:
                break
        return found

    def read_docs(self) -> list[dict[str, Any]]:
        return []

    def read_doc(self, name: str) -> dict[str, Any] | None:
        return next((d for d in self.read_docs() if d["name"] == name), None)

    def source_location(self, source: str) -> dict[str, Any] | None:
        return None

    def test_connection(self) -> dict[str, Any]:
        return {"adapter": self.name, "ok": True, "sources": self.list_sources()}

    def execute(self, statement: str) -> Any:
        raise AdapterError(f"o adapter {self.name} nao executa comandos")

    def close(self) -> None:
        return None


class SqlAdapter(Adapter):
    def __init__(self) -> None:
        self._conn: Any = None

    @abstractmethod
    def connect(self) -> Any: ...

    @property
    def conn(self) -> Any:
        if self._conn is None:
            self._conn = self.connect()
        return self._conn

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        cur.close()
        return [dict(zip(cols, r)) for r in rows]

    def _iter_query(self, sql: str, batch: int, cursor: Any = None) -> Iterator[list[dict[str, Any]]]:
        check_batch(batch)
        cur = cursor if cursor is not None else self.conn.cursor()
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            while True:
                rows = cur.fetchmany(batch)
                if not rows:
                    break
                yield [dict(zip(cols, r)) for r in rows]
        finally:
            cur.close()

    def _table_ref(self, source: str) -> str:
        raise AdapterError(f"o adapter {self.name} nao monta o nome da tabela")

    def _column_ref(self, column: str) -> str:
        return '"' + column.replace('"', '""') + '"'

    def find_keys(self, source: str, column: str, keys: set[str]) -> set[str]:
        """Pergunta ao banco so pelas chaves procuradas, em blocos, sem ler a tabela inteira."""
        found: set[str] = set()
        col, table, wanted = self._column_ref(column), self._table_ref(source), sorted(keys)
        for i in range(0, len(wanted), KEYS_PER_QUERY):
            values = ", ".join("'" + k.replace("'", "''") + "'" for k in wanted[i:i + KEYS_PER_QUERY])
            rows = self.query(f"SELECT DISTINCT {col} AS k FROM {table} WHERE {col} IN ({values})")
            found |= {k for k in (_text_key(next(iter(r.values()), None)) for r in rows) if k in keys}
        return found

    def execute(self, statement: str) -> Any:
        cur = self.conn.cursor()
        cur.execute(statement)
        cur.close()
        return True

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
