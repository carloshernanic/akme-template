"""Chave e tipos de cada fonte, decididos na etapa 5 antes de exportar para o Neo4j."""
from __future__ import annotations

import csv
import time
from pathlib import Path

import pytest

from akme.models import EditType
from akme.ontology import load_content
from akme.project import Project, read_yaml, write_yaml
from akme.tools import ontology_write
from akme.tools.ontology_write import EditError
from akme.tools.publish import publish
from akme.tools.review_view import present
from akme.tools.sources import suggest_sources
from akme.tools.stage import current_stage


def _without_sources(project):
    content = load_content(project)
    content["sources"] = []
    write_yaml(project.content_path, content)


def _propose(project, payload):
    return ontology_write.propose_edit(project, "add_source", payload, proposed_by="agent")


def _rewrite(project, source, column, values):
    path = project.root / "data" / f"{source}.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row, value in zip(rows, values):
        row[column] = value
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_demo_seed_brings_approved_sources(seeded):
    sources = {s["source"]: s for s in load_content(seeded)["sources"]}
    assert set(sources) == {"clientes", "pedidos", "itens_pedido", "produtos"}
    assert sources["itens_pedido"]["key"] == ["id_pedido", "sku"]
    assert sources["pedidos"]["types"] == {"dt_pedido": "date", "vl_total": "float"}


def test_suggestion_uses_contracts_profile_and_identifier_names(seeded):
    by = {s["source"]: s for s in suggest_sources(seeded)}
    assert by["pedidos"]["key"] == ["id_pedido"] and "contrato" in by["pedidos"]["key_from"]
    assert by["pedidos"]["types"] == {"dt_pedido": "date", "vl_total": "float"}
    assert "nf" not in by["pedidos"]["types"], "nf tem nome de identificador e fica texto"
    assert "cnpj" not in by["clientes"]["types"] and by["clientes"]["types"]["dt_cadastro"] == "date"
    assert by["itens_pedido"]["types"] == {"qt_itens": "integer", "vl_item": "float"}
    assert not by["itens_pedido"]["key"], "sem chave simples: o agente precisa propor a composta"
    assert all(s["payload"] for s in by.values() if s["key"]), "rascunho pronto para propose_edit quando ha chave"


def test_suggestion_excludes_source_without_class(seeded):
    (seeded.root / "data" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    by = {s["source"]: s for s in suggest_sources(seeded)}
    assert by["extra"]["payload"] == {"source": "extra", "exclude": by["extra"]["payload"]["exclude"]}
    assert "relacao" in by["extra"]["payload"]["exclude"]


def test_proposal_is_checked_against_data(seeded):
    _without_sources(seeded)
    edit = _propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "types": {"dt_pedido": "date", "vl_total": "float"}})
    checked = edit.payload["checked"]
    assert checked["rows"] == 10 and checked["types"]["dt_pedido"]["converted"] == 10
    assert edit.type == EditType.add_source


@pytest.mark.parametrize("payload,message", [
    ({"source": "nao_existe", "key": ["x"]}, "fonte inexistente"),
    ({"source": "pedidos"}, "key ou exclude"),
    ({"source": "pedidos", "key": ["nao_existe"]}, "coluna inexistente"),
    ({"source": "pedidos", "key": ["id_cliente"]}, "repete"),
    ({"source": "pedidos", "key": ["id_pedido"], "types": {"id_cliente": "integer"}}, "chave ou join"),
    ({"source": "pedidos", "key": ["id_pedido"], "types": {"status": "float"}}, "nao convertem"),
    ({"source": "pedidos", "key": ["id_pedido"], "types": {"vl_total": "money"}}, "tipo desconhecido"),
    ({"source": "pedidos", "key": ["id_pedido"], "exclude": "x"}, "nao pode ter key"),
])
def test_bad_proposal_is_refused(seeded, payload, message):
    with pytest.raises(EditError, match=message):
        _propose(seeded, payload)


def test_date_with_other_format_is_refused_with_example(seeded):
    _without_sources(seeded)
    _rewrite(seeded, "pedidos", "dt_pedido", ["03/07/2026"])
    with pytest.raises(EditError, match="03/07/2026"):
        _propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "types": {"dt_pedido": "date"}})


def test_second_pending_for_same_source_is_refused(seeded):
    _without_sources(seeded)
    _propose(seeded, {"source": "pedidos", "key": ["id_pedido"]})
    with pytest.raises(EditError, match="ja tem proposta pendente"):
        _propose(seeded, {"source": "pedidos", "key": ["id_pedido"]})


def test_apply_replaces_the_entry_of_the_source(seeded):
    edit = _propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "types": {"dt_pedido": "date"}})
    ontology_write.apply_edit(seeded, edit.id, "maria")
    entries = [s for s in load_content(seeded)["sources"] if s["source"] == "pedidos"]
    assert len(entries) == 1 and entries[0]["types"] == {"dt_pedido": "date"} and "checked" not in entries[0]


def test_review_can_change_key_and_types_and_is_rechecked(seeded):
    _without_sources(seeded)
    edit = _propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "types": {}})
    with pytest.raises(EditError, match="nao convertem"):
        ontology_write.review_edit(seeded, edit.id, "accept", "maria", edits={"types": "status: float"})
    ontology_write.review_edit(seeded, edit.id, "accept", "maria", edits={"types": "dt_pedido: date, vl_total: float"})
    ontology_write.apply_reviewed(seeded, "maria")
    entry = next(s for s in load_content(seeded)["sources"] if s["source"] == "pedidos")
    assert entry["types"] == {"dt_pedido": "date", "vl_total": "float"}


def test_review_page_shows_export_group_with_data_check(seeded):
    _without_sources(seeded)
    view = present(_propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "types": {"dt_pedido": "date"}}))
    assert view["group"] == "source" and view["group_label"] == "Exportação Neo4j" and view["stage"] == 5
    assert view["title"] == "Tabela pedidos" and "Pedido" in view["subtitle"]
    assert any("10 de 10" in line for line in view["observed"]["lines"])
    assert {f["key"] for f in view["editable"]} == {"key", "types"}
    excluded = present(_propose(seeded, {"source": "clientes", "exclude": "fora do escopo"}))
    assert "fora" in excluded["subtitle"]


def test_stage_five_lists_pending_export_decisions(seeded):
    _without_sources(seeded)
    _propose(seeded, {"source": "pedidos", "key": ["id_pedido"]})
    stage = current_stage(seeded)
    assert stage["pending_by_stage"][5] == 1


def test_export_reads_approved_sources(seeded):
    r = publish(seeded, "neo4j")
    assert not r["problems"] and r["nodes"]["ItemPedido"] == 17


def test_export_refuses_source_without_approved_entry(seeded):
    content = load_content(seeded)
    content["sources"] = [s for s in content["sources"] if s["source"] != "produtos"]
    write_yaml(seeded.content_path, content)
    r = publish(seeded, "neo4j")
    assert any("produtos" in p and "etapa 5" in p for p in r["problems"])


def test_export_says_when_decision_is_pending(seeded):
    content = load_content(seeded)
    content["sources"] = [s for s in content["sources"] if s["source"] != "produtos"]
    write_yaml(seeded.content_path, content)
    _propose(seeded, {"source": "produtos", "key": ["sku"]})
    r = publish(seeded, "neo4j")
    assert any("produtos" in p and "pendente" in p for p in r["problems"])


def test_old_neo4j_block_in_config_is_refused(seeded):
    config = read_yaml(seeded.root / "akme.yml")
    write_yaml(seeded.root / "akme.yml", {**config, "neo4j": {"keys": {"pedidos": "id_pedido"}}})
    r = publish(Project(seeded.root), "neo4j")
    assert any("akme.yml" in p and "neo4j" in p for p in r["problems"])


def test_stage_five_checklist_tracks_neo4j_decisions(seeded):
    from akme.tools.stage import checklist

    step = lambda: next(s for s in checklist(seeded, 5) if s["text"].startswith("Neo4j"))  # noqa: E731
    assert step()["done"] is True, "demo ja traz as quatro tabelas decididas"
    _without_sources(seeded)
    assert step()["done"] is None, "sem Neo4j no projeto, o passo nao cobra nada"
    _propose(seeded, {"source": "pedidos", "key": ["id_pedido"]})
    assert step()["done"] is False


def test_check_source_reads_all_rows(seeded):
    """Antes a conferencia lia so 100 mil linhas: chave repetida na linha 100.001 passava."""
    _without_sources(seeded)
    path = seeded.root / "data" / "itens_pedido.csv"
    with path.open(encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    assert header[:2] == ["id_pedido", "sku"]
    extra = [""] * (len(header) - 2)
    total = 120_000
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for i in range(total - 1):
            writer.writerow([f"P{i}", "S1", *extra])
        writer.writerow(["P0", "S1", *extra])  # repete a primeira, na ultima linha
    start = time.perf_counter()
    with pytest.raises(EditError, match="repete 1 valor"):
        _propose(seeded, {"source": "itens_pedido", "key": ["id_pedido", "sku"]})
    assert time.perf_counter() - start < 30


def test_check_source_counts_every_row_and_has_no_truncated(seeded):
    _without_sources(seeded)
    checked = _propose(seeded, {"source": "pedidos", "key": ["id_pedido"]}).payload["checked"]
    assert checked["rows"] == 10 and "truncated" not in checked


def test_check_source_does_not_import_n10s():
    import akme.tools.sources as s

    assert "n10s" not in Path(s.__file__).read_text(encoding="utf-8")


def test_check_source_refuses_ragged_rows_like_the_plan(seeded):
    _without_sources(seeded)
    path = seeded.root / "data" / "clientes.csv"
    path.write_text(path.read_text(encoding="utf-8") + "9,Bia, Jr,1,SP,2023-01-01,S\n", encoding="utf-8")
    with pytest.raises(EditError, match="1 linha\\(s\\) de clientes com colunas a mais ou a menos; primeira: linha 10"):
        _propose(seeded, {"source": "clientes", "key": ["id_cliente"]})


@pytest.mark.parametrize("payload,message", [
    ({"source": "pedidos", "key": ["id_pedido"], "types": {"vl_total": "money"}}, "tipo desconhecido"),
    ({"source": "pedidos", "key": ["id_pedido"], "exclude": "x"}, "nao pode ter key"),
    ({"source": "pedidos"}, "key ou exclude"),
    ({"source": "pedidos", "key": ["id_pedido"], "types": {"id_cliente": "integer"}}, "chave ou join"),
])
def test_cheap_payload_errors_come_before_reading_the_source(seeded, monkeypatch, payload, message):
    import akme.tools.sources as sources

    def must_not_read(*a, **k):
        raise AssertionError("leu a fonte inteira antes de conferir o payload")

    monkeypatch.setattr(sources, "scan_source", must_not_read)
    with pytest.raises(EditError, match=message):
        _propose(seeded, payload)
