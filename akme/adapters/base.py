from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AdapterError(RuntimeError):
    pass


def require(module: str, extra: str) -> None:
    try:
        __import__(module)
    except ImportError as exc:
        raise AdapterError(
            f"o adapter precisa do pacote '{module}'. Instale com: uv sync --extra {extra}"
        ) from exc


class Adapter(ABC):
    name = "base"

    @abstractmethod
    def list_sources(self) -> list[str]: ...

    @abstractmethod
    def read_schema(self, source: str) -> dict[str, Any]: ...

    @abstractmethod
    def read_sample(self, source: str, n: int = 100) -> list[dict[str, Any]]: ...

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

    def execute(self, statement: str) -> Any:
        cur = self.conn.cursor()
        cur.execute(statement)
        cur.close()
        return True

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
