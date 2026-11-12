import sys

import pytest

from akme.adapters import load_adapter
from akme.adapters.base import AdapterError
from akme.adapters.local_folder import LocalFolderAdapter


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


def test_optional_adapters_fail_clearly(monkeypatch):
    # simula a ausencia dos pacotes opcionais: com o extra instalado o teste nunca tenta conectar a servico real
    for module in ("psycopg", "snowflake", "snowflake.connector", "databricks", "databricks.sql"):
        monkeypatch.setitem(sys.modules, module, None)
    for name in ("postgres", "snowflake", "databricks"):
        adapter = load_adapter(name, {})
        with pytest.raises(AdapterError, match="uv sync --extra"):
            adapter.list_sources()


def test_csv_row_with_extra_or_missing_columns_is_counted(tmp_path):
    (tmp_path / "t.csv").write_text("id,nome,valor\n1,Ana,10\n2,Bia, Jr,20\n3,Caio\n4,Davi,40\n", encoding="utf-8")
    adapter = LocalFolderAdapter(str(tmp_path))
    rows = [r for block in adapter.iter_rows("t") for r in block]
    assert len(rows) == 4
    assert adapter.ragged["t"] == (2, 3), "duas linhas fora do cabecalho; a primeira e a linha 3 do arquivo"
    list(adapter.iter_rows("t", 1))
    assert adapter.ragged["t"] == (2, 3), "cada leitura recomeca a contagem"


def test_well_formed_csv_has_no_ragged_entry(tmp_path):
    (tmp_path / "t.csv").write_text("id,nome\n1,\"Bia, Jr\"\n", encoding="utf-8")
    adapter = LocalFolderAdapter(str(tmp_path))
    list(adapter.iter_rows("t"))
    assert "t" not in adapter.ragged


def test_xlsx_row_with_value_beyond_header_is_counted(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["id", "nome"])
    ws.append([1, "Ana"])
    ws.append([2, "Bia", "sobra"])
    wb.save(tmp_path / "t.xlsx")
    adapter = LocalFolderAdapter(str(tmp_path))
    list(adapter.iter_rows("t"))
    assert adapter.ragged["t"] == (1, 3)


@pytest.mark.parametrize("batch", [0, -1])
def test_iter_rows_refuses_non_positive_batch(project, batch):
    adapter = load_adapter("local_folder", project.adapter_options())
    with pytest.raises(ValueError, match="batch"):
        next(adapter.iter_rows("pedidos", batch))


def test_blank_csv_line_is_skipped_and_not_ragged(tmp_path):
    (tmp_path / "t.csv").write_text("id,nome\n1,Ana\n\n2,Bia\n\n", encoding="utf-8")
    adapter = LocalFolderAdapter(str(tmp_path))
    rows = [r for block in adapter.iter_rows("t") for r in block]
    assert rows == [{"id": "1", "nome": "Ana"}, {"id": "2", "nome": "Bia"}]
    assert "t" not in adapter.ragged


def test_ragged_multiline_record_points_to_its_first_line(tmp_path):
    (tmp_path / "t.csv").write_text('id,nome\n1,Ana\n2,"Bia\nJr",sobra\n', encoding="utf-8")
    adapter = LocalFolderAdapter(str(tmp_path))
    list(adapter.iter_rows("t"))
    assert adapter.ragged["t"] == (1, 3), "o registro comeca na linha 3 e termina na 4"


def test_blank_line_in_single_column_csv_is_an_empty_record(tmp_path):
    (tmp_path / "t.csv").write_text("id\n1\n\n2\n", encoding="utf-8")
    adapter = LocalFolderAdapter(str(tmp_path))
    rows = [r for block in adapter.iter_rows("t") for r in block]
    assert rows == [{"id": "1"}, {"id": None}, {"id": "2"}], "registro de valor vazio, nao pulado em silencio"
    assert "t" not in adapter.ragged
