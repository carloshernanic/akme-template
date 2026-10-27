from __future__ import annotations

from typing import Any

from ..adapters import load_adapter
from ..project import Project


def connect(project: Project) -> dict[str, Any]:
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        result = adapter.test_connection()
        result["docs"] = [d["name"] for d in adapter.read_docs()]
        return result
    finally:
        adapter.close()
