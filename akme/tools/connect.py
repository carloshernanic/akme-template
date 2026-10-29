from __future__ import annotations

import re
from typing import Any

from ..adapters import load_adapter
from ..project import Project


def connect(project: Project) -> dict[str, Any]:
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        result = adapter.test_connection()
        result["docs"] = [{"name": d["name"], "pages": len(d.get("pages") or [d])} for d in adapter.read_docs()]
        return result
    finally:
        adapter.close()


def read_document(project: Project, name: str, page: int | None = None) -> dict[str, Any]:
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        doc = adapter.read_doc(name)
        if doc is None:
            names = [d["name"] for d in adapter.read_docs()]
            raise ValueError(f"documento nao encontrado: {name}. Documentos: {', '.join(names) or 'nenhum'}")
    finally:
        adapter.close()
    pages = doc.get("pages") or [{"label": "pagina 1", "text": doc["text"]}]
    if page is None:
        result: dict[str, Any] = {"name": name, "pages": len(pages),
                                  "index": [{"page": i, "label": p["label"], "chars": len(p["text"])}
                                            for i, p in enumerate(pages, 1)]}
        if len(pages) == 1:
            result["text"] = pages[0]["text"]
        return result
    if not 1 <= page <= len(pages):
        raise ValueError(f"{name} tem {len(pages)} paginas; pedido: {page}")
    return {"name": name, "page": page, "pages": len(pages), "label": pages[page - 1]["label"],
            "text": pages[page - 1]["text"]}


def _excerpt(text: str, start: int, end: int, width: int = 90) -> str:
    left, right = max(0, start - width), min(len(text), end + width)
    snippet = " ".join(text[left:right].split())
    return ("..." if left else "") + snippet + ("..." if right < len(text) else "")


def find_in_sources(project: Project, query: str, whole_word: bool = True, case_sensitive: bool = False,
                    max_hits: int = 50, sample_size: int = 5000) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("query vazia")
    body = re.escape(query.strip())
    pattern = re.compile(rf"(?<!\w){body}(?!\w)" if whole_word else body, 0 if case_sensitive else re.IGNORECASE)
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    documents: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    truncated = False
    try:
        for doc in adapter.read_docs():
            pages = doc.get("pages") or [{"label": "pagina 1", "text": doc["text"]}]
            for number, page in enumerate(pages, 1):
                for match in pattern.finditer(page["text"]):
                    if len(documents) >= max_hits:
                        truncated = True
                        break
                    documents.append({"document": doc["name"], "path": doc.get("path", doc["name"]),
                                      "page": number, "label": page["label"],
                                      "excerpt": _excerpt(page["text"], match.start(), match.end())})
        for source in adapter.list_sources():
            loc = adapter.source_location(source) or {}
            where = {"source": source, "path": loc["file"].as_posix() if loc.get("file") else source,
                     "sheet": loc.get("sheet")}
            rows = adapter.read_sample(source, sample_size)
            columns = list(rows[0]) if rows else [c["name"] for c in adapter.read_schema(source)["columns"]]
            for column in columns:
                if pattern.search(column):
                    tables.append({**where, "column": column, "in_header": True, "matches": 0, "rows": [], "values": []})
                hits = [(i, str(r[column])) for i, r in enumerate(rows, 1)
                        if r.get(column) is not None and pattern.search(str(r[column]))]
                if hits:
                    values = list(dict.fromkeys(v for _, v in hits))
                    tables.append({**where, "column": column, "in_header": False, "matches": len(hits),
                                   "rows": [i for i, _ in hits[:5]], "values": values[:5]})
    finally:
        adapter.close()
    return {"query": query, "whole_word": whole_word, "case_sensitive": case_sensitive,
            "documents": documents, "tables": tables, "truncated": truncated,
            "found": bool(documents or tables)}
