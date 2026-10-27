from __future__ import annotations

from typing import Any

from .base import Adapter, AdapterError

ADAPTERS = {
    "local_folder": "akme.adapters.local_folder:LocalFolderAdapter",
    "postgres": "akme.adapters.postgres:PostgresAdapter",
    "snowflake": "akme.adapters.snowflake:SnowflakeAdapter",
    "databricks": "akme.adapters.databricks:DatabricksAdapter",
}


def load_adapter(name: str, options: dict[str, Any]) -> Adapter:
    if name not in ADAPTERS:
        raise AdapterError(f"adapter desconhecido: {name}. Opcoes: {', '.join(ADAPTERS)}")
    module_name, class_name = ADAPTERS[name].split(":")
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)(**options)


__all__ = ["Adapter", "AdapterError", "ADAPTERS", "load_adapter"]
