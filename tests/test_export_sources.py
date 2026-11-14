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
    assert {f["key"] for f in view["editable"]} == {"key", "types", "caption"}
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


def test_add_source_with_invisible_character_in_key_is_shown_and_explained(seeded):
    """O BOM grudado no nome aparecia como 'id_pedido' dos dois lados; agora a mensagem o mostra e diz o que fazer."""
    _without_sources(seeded)
    with pytest.raises(EditError) as exc:
        _propose(seeded, {"source": "pedidos", "key": ["﻿id_pedido"]})
    message = str(exc.value)
    assert "coluna inexistente em pedidos: <U+FEFF>id_pedido" in message
    assert "﻿" not in message and "BOM" in message and "sem esse caractere" in message


# --- legenda (caption) decidida na etapa 5 ---

def test_suggestion_proposes_a_name_like_caption(seeded):
    by = {s["source"]: s for s in suggest_sources(seeded)}
    assert by["clientes"]["caption"] == "nm_cliente" and by["clientes"]["payload"]["caption"] == "nm_cliente"
    assert any(n.startswith("legenda: nm_cliente") for n in by["clientes"]["notes"])
    assert by["pedidos"]["caption"] == "" and "caption" not in by["pedidos"]["payload"]
    assert any("nenhuma coluna com cara de nome" in n for n in by["pedidos"]["notes"])


def test_caption_is_checked_shown_and_saved(seeded):
    _without_sources(seeded)
    with pytest.raises(EditError, match="coluna inexistente em pedidos: nao_existe"):
        _propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "caption": "nao_existe"})
    edit = _propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "caption": "status"})
    cap = edit.payload["checked"]["caption"]
    assert cap == {"column": "status", "decided": True, "alone": True, "rows": 10, "filled": 10, "example": "FATURADO"}
    view = present(edit)
    assert {"label": "Legenda", "value": "status", "mono": True} in view["fields"]
    assert any(line.startswith("legenda (decidida): coluna status, preenchida em 10 de 10 linhas") for line in view["observed"]["lines"])
    ontology_write.review_edit(seeded, edit.id, "accept", "maria")
    ontology_write.apply_reviewed(seeded, "maria")
    entry = next(s for s in load_content(seeded)["sources"] if s["source"] == "pedidos")
    assert entry["caption"] == "status"


def test_without_a_caption_the_review_shows_the_automatic_one(seeded):
    _without_sources(seeded)
    named = present(_propose(seeded, {"source": "clientes", "key": ["id_cliente"]}))
    assert {"label": "Legenda", "value": "automática", "mono": False} in named["fields"]
    assert any(line.startswith("legenda (automática): coluna nm_cliente") and "Construtora Horizonte" in line
               for line in named["observed"]["lines"])
    plain = present(_propose(seeded, {"source": "pedidos", "key": ["id_pedido"]}))
    assert any("nenhuma coluna com cara de nome" in line and "Pedido 1001" in line for line in plain["observed"]["lines"])


def test_reviewer_can_change_or_clear_the_caption(seeded):
    _without_sources(seeded)
    edit = _propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "caption": "status"})
    with pytest.raises(EditError, match="coluna inexistente em pedidos: nada"):
        ontology_write.review_edit(seeded, edit.id, "accept", "maria", edits={"caption": "nada"})
    reviewed = ontology_write.review_edit(seeded, edit.id, "accept", "maria", edits={"caption": "nf"})
    assert reviewed.review.edits["caption"] == "nf" and reviewed.review.edits["checked"]["caption"]["column"] == "nf"
    cleared = ontology_write.review_edit(seeded, edit.id, "accept", "maria", edits={"caption": ""})
    assert cleared.review.edits["caption"] == ""
    ontology_write.apply_reviewed(seeded, "maria")
    entry = next(s for s in load_content(seeded)["sources"] if s["source"] == "pedidos")
    assert "caption" not in entry, "legenda vazia nao e gravada: vale a automatica"


def test_sparse_caption_is_an_alert_in_the_review(seeded):
    _without_sources(seeded)
    _rewrite(seeded, "pedidos", "status", ["FATURADO", "", "", "", "", "", "", "", "", ""])
    view = present(_propose(seeded, {"source": "pedidos", "key": ["id_pedido"], "caption": "status"}))
    assert any("está vazia em 9 de 10 linhas" in a for a in view["alerts"])


def test_excluded_source_refuses_a_caption(seeded):
    _without_sources(seeded)
    with pytest.raises(EditError, match="fonte excluida nao pode ter key, types nem caption"):
        _propose(seeded, {"source": "clientes", "exclude": "fora", "caption": "uf"})


def test_reserved_column_is_refused_in_step_5(seeded):
    _without_sources(seeded)
    path = seeded.root / "data" / "clientes.csv"
    header, *rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([header + ",_id", *[r + ",x" for r in rows]]) + "\n", encoding="utf-8")
    with pytest.raises(EditError, match="a coluna _id tem um nome reservado.*Renomeie a coluna na origem"):
        _propose(seeded, {"source": "clientes", "key": ["id_cliente"]})


# --- nomes reservados barrados na etapa em que sao criados (N4) ---

def test_reserved_names_are_refused_when_proposed(seeded):
    propose = ontology_write.propose_edit
    with pytest.raises(EditError, match="o nome de classe Conceito e reservado.*ConceitoRubrica"):
        propose(seeded, "add_class", {"name": "Conceito", "label": "Conceito", "comment": "nota de I a A+"})
    with pytest.raises(EditError, match="o nome de classe Termo e reservado"):
        propose(seeded, "add_class", {"name": "Termo", "label": "Termo", "comment": "c"})
    with pytest.raises(EditError, match="o nome de relacao TEM_TERMO e reservado"):
        propose(seeded, "add_relation", {"name": "TEM_TERMO", "domain": "Pedido", "range": "Cliente", "label": "tem",
                                         "multiplicity": "many_to_one", "no_join_reason": "conceitual"})
    with pytest.raises(EditError, match="a coluna _id tem um nome reservado"):
        propose(seeded, "add_mapping", {"term": "uf", "source": "clientes", "column": "_id"})
    assert propose(seeded, "add_class", {"name": "ConceitoRubrica", "label": "Conceito", "comment": "nota de I a A+"})


def test_validate_warns_about_reserved_names_already_in_the_ontology(seeded):
    from rdflib import OWL, RDF
    from akme.ontology import base_ns, load_graph, save_graph
    from akme.tools.validate import validate

    assert not [f for f in validate(seeded).findings if f.check == "reserved_name"]
    g = load_graph(seeded.schema_path)
    g.add((base_ns(g)["Conceito"], RDF.type, OWL.Class))
    save_graph(g, seeded.schema_path)
    found = [f for f in validate(seeded).findings if f.check == "reserved_name"]
    assert [(f.level, f.subject) for f in found] == [("warning", "Conceito")]
    assert "a exportacao para o Neo4j recusa este nome" in found[0].message
