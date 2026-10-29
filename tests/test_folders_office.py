import sys
from datetime import date

import pytest

from akme.adapters import load_adapter
from akme.adapters.base import AdapterError
from akme.project import Project, write_yaml
from akme.tools.connect import connect, read_document
from akme.tools.profile import profile

openpyxl = pytest.importorskip("openpyxl")
docx = pytest.importorskip("docx")
pptx = pytest.importorskip("pptx")


def _xlsx(path, sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for row in rows:
            ws.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


@pytest.fixture
def folder(tmp_path):
    data = tmp_path / "data"
    (data / "vendas" / "2026").mkdir(parents=True)
    (data / "itens.csv").write_text("id,qt\n1,2\n2,\n", encoding="utf-8")
    _xlsx(data / "vendas" / "2026" / "pedidos.xlsx", {
        "Janeiro": [[None], ["id_pedido", "dt_pedido", "valor", "valor", None],
                    [1, date(2026, 1, 3), 10.5, 1, None], [2, date(2026, 1, 9), 20.0, 2, None]],
        "Fevereiro": [["id_pedido", "dt_pedido"], [3, date(2026, 2, 1)]],
    })
    _xlsx(data / "vendas" / "clientes.xlsx", {"Planilha1": [["id_cliente", "uf"], [1, "SP"], [2, "MG"]]})
    (data / "vendas" / "~$pedidos.xlsx").write_bytes(b"lock")
    (data / ".oculta").mkdir()
    (data / ".oculta" / "segredo.csv").write_text("a\n1\n", encoding="utf-8")

    d = docx.Document()
    d.add_paragraph("Glossario do cliente. UF significa unidade federativa.")
    d.add_page_break()
    d.add_paragraph("Regras: faturamento so com status FATURADO.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "sigla", "significado"
    t.cell(1, 0).text, t.cell(1, 1).text = "NF", "nota fiscal"
    (data / "docs" / "contratos").mkdir(parents=True)
    d.save(data / "docs" / "contratos" / "dicionario.docx")

    p = pptx.Presentation()
    s1 = p.slides.add_slide(p.slide_layouts[1])
    s1.shapes.title.text = "Kickoff"
    s1.placeholders[1].text = "Pergunta: faturamento por UF"
    s1.notes_slide.notes_text_frame.text = "cliente quer visao trimestral"
    s2 = p.slides.add_slide(p.slide_layouts[5])
    s2.shapes.title.text = "Fontes"
    tbl = s2.shapes.add_table(2, 2, pptx.util.Inches(1), pptx.util.Inches(2), pptx.util.Inches(4), pptx.util.Inches(1)).table
    tbl.cell(0, 0).text, tbl.cell(0, 1).text = "sistema", "dono"
    tbl.cell(1, 0).text, tbl.cell(1, 1).text = "ERP", "TI"
    p.save(data / "docs" / "kickoff.pptx")

    write_yaml(tmp_path / "akme.yml", {"adapter": "local_folder", "local_folder": {"path": str(data)}})
    return tmp_path


def adapter(folder, **opts):
    return load_adapter("local_folder", {"path": str(folder / "data"), **opts})


def test_subfolders_and_sheets_become_sources(folder):
    a = adapter(folder)
    assert a.list_sources() == ["itens", "vendas__2026__pedidos__fevereiro", "vendas__2026__pedidos__janeiro", "vendas__clientes"]
    assert a.source_location("vendas__2026__pedidos__janeiro")["path"] == "vendas/2026/pedidos.xlsx"
    assert a.source_location("vendas__2026__pedidos__janeiro")["sheet"] == "Janeiro"
    assert a.source_location("vendas__clientes")["sheet"] == "Planilha1"
    assert adapter(folder, recursive=False).list_sources() == ["itens"]


def test_xlsx_header_and_values(folder):
    a = adapter(folder)
    cols = [c["name"] for c in a.read_schema("vendas__2026__pedidos__janeiro")["columns"]]
    assert cols == ["id_pedido", "dt_pedido", "valor", "valor_2"]
    rows = a.read_sample("vendas__2026__pedidos__janeiro", 10)
    assert rows[0] == {"id_pedido": 1, "dt_pedido": "2026-01-03", "valor": 10.5, "valor_2": 1}
    assert len(a.read_sample("vendas__2026__pedidos__janeiro", 1)) == 1
    assert a.read_sample("itens", 10)[1] == {"id": "2", "qt": None}


def test_multiple_roots_resolve_collisions(folder):
    extra = folder / "extra"
    extra.mkdir()
    (extra / "itens.csv").write_text("id\n9\n", encoding="utf-8")
    a = load_adapter("local_folder", {"path": [str(folder / "data"), str(extra)]})
    assert {"itens", "extra__itens"} <= set(a.list_sources())
    assert a.read_sample("extra__itens", 5) == [{"id": "9"}]


def test_documents_are_split_by_page_and_slide(folder):
    docs = {d["name"]: d for d in adapter(folder).read_docs()}
    assert set(docs) == {"docs/contratos/dicionario.docx", "docs/kickoff.pptx"}
    pages = docs["docs/contratos/dicionario.docx"]["pages"]
    assert [p["label"] for p in pages] == ["pagina 1", "pagina 2"]
    assert "UF significa" in pages[0]["text"] and "NF | nota fiscal" in pages[1]["text"]
    slides = docs["docs/kickoff.pptx"]["pages"]
    assert [s["label"] for s in slides] == ["slide 1", "slide 2"]
    assert "Notas: cliente quer visao trimestral" in slides[0]["text"]
    assert "ERP | TI" in slides[1]["text"]


def test_read_document_tool(folder):
    p = Project(folder)
    index = read_document(p, "docs/contratos/dicionario.docx")
    assert index["pages"] == 2 and "text" not in index
    assert [i["label"] for i in index["index"]] == ["pagina 1", "pagina 2"]
    page = read_document(p, "docs/contratos/dicionario.docx", 2)
    assert "FATURADO" in page["text"] and "Glossario" not in page["text"]
    with pytest.raises(ValueError, match="2 paginas"):
        read_document(p, "docs/contratos/dicionario.docx", 3)
    with pytest.raises(ValueError, match="nao encontrado"):
        read_document(p, "nao_existe.docx")


def test_profile_and_connect_report_origin_and_pages(folder):
    p = Project(folder)
    result = profile(p)
    by_name = {s.name: s for s in result.sources}
    jan = by_name["vendas__2026__pedidos__janeiro"]
    assert jan.origin == "vendas/2026/pedidos.xlsx#Janeiro"
    cols = {c.name: c for c in jan.columns}
    assert cols["dt_pedido"].type == "date" and cols["id_pedido"].candidate_key
    assert by_name["itens"].origin == "itens.csv"
    assert {d["name"]: d["pages"] for d in result.docs} == {"docs/contratos/dicionario.docx": 2, "docs/kickoff.pptx": 2}
    assert {"UF", "NF", "ERP"} <= set(result.conventions["acronyms_found"])
    assert {"name": "docs/kickoff.pptx", "pages": 2} in connect(p)["docs"]


def test_missing_office_extra_is_explicit(folder, monkeypatch):
    for module in ("openpyxl", "docx", "pptx"):
        monkeypatch.setitem(sys.modules, module, None)
    a = adapter(folder)
    with pytest.raises(AdapterError, match="--extra office"):
        a.list_sources()
    docs = {d["name"]: d["text"] for d in a.read_docs()}
    assert "extra 'office'" in docs["docs/contratos/dicionario.docx"]
    assert "extra 'office'" in docs["docs/kickoff.pptx"]


def test_find_in_sources_cites_documents_and_tables(folder):
    from akme.tools.connect import find_in_sources

    p = Project(folder)
    uf = find_in_sources(p, "UF", case_sensitive=True)
    docs = {(d["document"], d["page"]) for d in uf["documents"]}
    assert docs == {("docs/contratos/dicionario.docx", 1), ("docs/kickoff.pptx", 1)}
    hit = next(d for d in uf["documents"] if d["document"] == "docs/contratos/dicionario.docx")
    assert hit["path"].endswith("data/docs/contratos/dicionario.docx")
    assert "UF significa unidade federativa" in hit["excerpt"]
    assert uf["tables"] == []
    col = next(t for t in find_in_sources(p, "UF")["tables"] if t["column"] == "uf")
    assert col["in_header"] and col["source"] == "vendas__clientes" and col["sheet"] == "Planilha1"

    sp = find_in_sources(p, "SP")
    values = next(t for t in sp["tables"] if t["column"] == "uf" and not t["in_header"])
    assert values["matches"] == 1 and values["rows"] == [1] and values["values"] == ["SP"]
    assert values["path"].endswith("data/vendas/clientes.xlsx")

    assert find_in_sources(p, "Pergunta")["documents"][0]["label"] == "slide 1"
    assert not find_in_sources(p, "Uf", case_sensitive=True)["found"]
    assert not find_in_sources(p, "fatura")["found"]
    assert find_in_sources(p, "fatura", whole_word=False)["found"]
    capped = find_in_sources(p, "a", whole_word=False, max_hits=2)
    assert len(capped["documents"]) == 2 and capped["truncated"]
