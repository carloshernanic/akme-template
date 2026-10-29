from __future__ import annotations

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
