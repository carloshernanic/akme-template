import pytest

from akme.adapters import load_adapter
from akme.adapters.base import AdapterError


def test_local_folder_end_to_end(project):
    adapter = load_adapter("local_folder", project.adapter_options())
    assert adapter.list_sources() == ["clientes", "itens_pedido", "pedidos", "produtos"]
    schema = adapter.read_schema("pedidos")
    assert [c["name"] for c in schema["columns"]][:3] == ["id_pedido", "id_cliente", "dt_pedido"]
    rows = adapter.read_sample("pedidos", 3)
    assert len(rows) == 3 and rows[2]["nf"] is None
    docs = adapter.read_docs()
    assert any(d["name"] == "glossario.md" and "UF" in d["text"] for d in docs)


def test_missing_source_and_folder(project):
    adapter = load_adapter("local_folder", project.adapter_options())
    with pytest.raises(AdapterError):
        adapter.read_schema("inexistente")
    with pytest.raises(AdapterError):
        load_adapter("local_folder", {"path": "nao/existe"})


def test_optional_adapters_fail_clearly():
    for name in ("postgres", "snowflake", "databricks"):
        adapter = load_adapter(name, {})
        with pytest.raises(AdapterError, match="uv sync --extra"):
            adapter.list_sources()
