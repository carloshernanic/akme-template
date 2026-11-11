from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..adapters import load_adapter
from ..project import Project

REQUIRED = ("host", "http_path", "token")


def missing_credentials(project: Project) -> list[str]:
    """Credenciais do Databricks que estao vazias depois de resolver `env:` do akme.yml."""
    opts = project.adapter_options()
    return [k for k in REQUIRED if not opts.get(k)]


def discover_catalog(project: Project) -> dict[str, Any]:
    """Lista todos os catalogos, schemas e tabelas da conta e grava em docs/databricks_catalog.json.

    Ignora `catalog` e `schema` do akme.yml de proposito: o inventario e da conta inteira.
    """
    if project.adapter_name != "databricks":
        raise ValueError(f"inventario de catalogos so existe para o adapter databricks (atual: {project.adapter_name})")
    missing = missing_credentials(project)
    if missing:
        raise ValueError(f"credenciais do Databricks vazias: {', '.join(missing)}")
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        found = adapter.discover()
    finally:
        adapter.close()
    schemas = [s for c in found["catalogs"] for s in c["schemas"]]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": project.adapter_options().get("host"),
        "summary": {"catalogs": len(found["catalogs"]), "schemas": len(schemas),
                    "tables": sum(len(s["tables"]) for s in schemas), "errors": len(found["errors"])},
        "catalogs": found["catalogs"],
        "errors": found["errors"],
    }
    project.catalog_path.parent.mkdir(parents=True, exist_ok=True)
    project.catalog_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

