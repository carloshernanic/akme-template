"""Corrigir o que ja foi aplicado: update_mapping, remove_mapping e rename_class."""
from __future__ import annotations

import pytest

from akme.models import EDIT_STAGE, ONTOLOGY_TYPES, EditType
from akme.ontology import class_names, load_content, load_graph
from akme.project import read_yaml
from akme.tools import ontology_write
from akme.tools.ontology_write import EditError
from akme.tools.review_view import present
from akme.tools.validate import validate


def _propose(project, type_, payload):
    return ontology_write.propose_edit(project, type_, payload, proposed_by="agent")


def _mapping(project, index=0):
    return dict(load_content(project)["mappings"][index])


def _key(m):
    return {"term": m["term"], "source": m["source"], "column": m["column"]}


def _other_column(project, m):
    """Uma coluna da mesma tabela que o termo ainda nao usa."""
    used = {x["column"] for x in load_content(project)["mappings"] if x["source"] == m["source"] and x["term"] == m["term"]}
    return next(x["column"] for x in load_content(project)["mappings"] if x["source"] == m["source"] and x["column"] not in used)


def test_the_new_types_belong_to_the_ontology_stages():
    for t, stage in ((EditType.update_mapping, 3), (EditType.remove_mapping, 3), (EditType.rename_class, 2)):
        assert t in ONTOLOGY_TYPES and EDIT_STAGE[t] == stage


def test_update_mapping_changes_the_applied_mapping_with_provenance(seeded):
    before = _mapping(seeded)
    column = _other_column(seeded, before)
    edit = _propose(seeded, "update_mapping", _key(before) | {"set": {"column": column, "note": "coluna certa"}})
    assert edit.payload["before"] == before and edit.payload["after"]["column"] == column
    assert load_content(seeded)["mappings"][0] == before, "propor nao altera a ontologia"
    view = present(edit)
    assert view["group"] == "mapping" and view["stage"] == 3
    assert any(f"{before['column']} → {column}" in f["value"] for f in view["fields"])

    entry = ontology_write.apply_edit(seeded, edit.id, approved_by="maria")
    after = load_content(seeded)["mappings"][0]
    assert after == before | {"column": column, "note": "coluna certa"}
    assert len(load_content(seeded)["mappings"]) == len(read_yaml(seeded.content_path)["mappings"])
    assert entry["before"] == before and entry["after"] == after and entry["approved_by"] == "maria"
    logged = read_yaml(seeded.changelog_path)["entries"][-1]
    assert logged["type"] == "update_mapping" and logged["before"] == before


def test_update_mapping_refusals(seeded):
    m = _mapping(seeded)
    with pytest.raises(EditError, match="nao encontrado"):
        _propose(seeded, "update_mapping", {"term": m["term"], "source": m["source"], "column": "coluna_que_nao_existe", "set": {"note": "x"}})
    with pytest.raises(EditError, match="set nao aceita"):
        _propose(seeded, "update_mapping", _key(m) | {"set": {"tabela": "x"}})
    with pytest.raises(EditError, match="nao muda nada"):
        _propose(seeded, "update_mapping", _key(m) | {"set": {"column": m["column"]}})
    with pytest.raises(EditError, match="termo nao encontrado"):
        _propose(seeded, "update_mapping", _key(m) | {"set": {"term": "termo_inventado"}})
    with pytest.raises(EditError, match="reservado"):
        _propose(seeded, "update_mapping", _key(m) | {"set": {"column": "_id"}})
    with pytest.raises(EditError, match="remove_mapping"):
        _propose(seeded, "update_mapping", _key(m) | {"set": {"source": ""}})
    other = _mapping(seeded, 1)
    with pytest.raises(EditError, match="ja existe o mapping"):
        _propose(seeded, "update_mapping", _key(m) | {"set": _key(other)})
    _propose(seeded, "update_mapping", _key(m) | {"set": {"note": "primeira"}})
    with pytest.raises(EditError, match="correcao pendente"):
        _propose(seeded, "remove_mapping", _key(m) | {"reason": "errado"})


def test_a_correction_decided_on_an_old_mapping_is_not_applied(seeded):
    m = _mapping(seeded)
    edit = _propose(seeded, "update_mapping", _key(m) | {"set": {"note": "nova"}})
    content = load_content(seeded)
    content["mappings"][0]["note"] = "mudou por fora"
    from akme.ontology import save_content
    save_content(seeded, content)
    with pytest.raises(EditError, match="mudou depois da proposta"):
        ontology_write.apply_edit(seeded, edit.id, approved_by="maria")


def test_remove_mapping_deletes_only_that_mapping(seeded):
    all_before = load_content(seeded)["mappings"]
    m = dict(all_before[0])
    with pytest.raises(EditError, match="reason"):
        _propose(seeded, "remove_mapping", _key(m))
    edit = _propose(seeded, "remove_mapping", _key(m) | {"reason": "tabela errada"})
    assert present(edit)["title"] == f"Remover o mapping de {m['term']}"
    entry = ontology_write.apply_edit(seeded, edit.id, approved_by="maria")
    assert load_content(seeded)["mappings"] == all_before[1:]
    assert entry["before"] == m and entry["payload"]["reason"] == "tabela errada"


def test_rename_class_changes_schema_and_every_reference(seeded):
    content = load_content(seeded)
    name = next(t["class"] for t in content["terms"] if any(name_ in (c.get("domain"), c.get("range")) for c in content["relation_contracts"] for name_ in [t["class"]]))
    new = name + "Renomeada"
    terms = [t["name"] for t in content["terms"] if t["class"] == name]
    contracts = [c["relation"] for c in content["relation_contracts"] if name in (c["domain"], c["range"])]
    pending_term = _propose(seeded, "add_term", {"name": "termo_pendente", "class": name, "definition": "x"})

    edit = _propose(seeded, "rename_class", {"name": name, "new_name": new, "label": "Rótulo novo"})
    assert name in class_names(load_graph(seeded.schema_path)), "propor nao altera a ontologia"
    assert present(edit)["group"] == "class" and present(edit)["stage"] == 2
    entry = ontology_write.apply_edit(seeded, edit.id, approved_by="maria")

    g = load_graph(seeded.schema_path)
    names = class_names(g)
    assert new in names and name not in names
    assert name + '"' not in seeded.schema_path.read_text(encoding="utf-8").replace(new, "")
    after = load_content(seeded)
    assert [t["name"] for t in after["terms"] if t["class"] == new] == terms and not [t for t in after["terms"] if t["class"] == name]
    assert [c["relation"] for c in after["relation_contracts"] if new in (c["domain"], c["range"])] == contracts
    assert not [c for c in after["relation_contracts"] if name in (c["domain"], c["range"])]
    assert entry["renamed"]["terms"] == len(terms) and entry["renamed"]["relation_contracts"] == len(contracts)
    assert entry["renamed"]["pending"] == 1
    assert ontology_write._load_pending(seeded, pending_term.id).payload["class"] == new
    from akme.ontology import relations
    assert not [r for r in relations(g) if name in (r["domain"], r["range"])]
    report = validate(seeded, check_data=False)
    assert not [f for f in report.findings if f.check == "term_class"]


def test_rename_class_refusals(seeded):
    names = sorted(class_names(load_graph(seeded.schema_path)) - {"Entity", "Relation", "Rule", "Metric"})
    with pytest.raises(EditError, match="classe de base"):
        _propose(seeded, "rename_class", {"name": "Entity", "new_name": "Coisa"})
    with pytest.raises(EditError, match="nao encontrada"):
        _propose(seeded, "rename_class", {"name": "NaoExiste", "new_name": "Coisa"})
    with pytest.raises(EditError, match="ja existe a classe"):
        _propose(seeded, "rename_class", {"name": names[0], "new_name": names[1]})
    with pytest.raises(EditError, match="reservado"):
        _propose(seeded, "rename_class", {"name": names[0], "new_name": "Conceito"})
    with pytest.raises(EditError, match="invalido"):
        _propose(seeded, "rename_class", {"name": names[0], "new_name": "Nome Com Espaco"})
    _propose(seeded, "rename_class", {"name": names[0], "new_name": "NomeNovo"})
    with pytest.raises(EditError, match="troca de nome pendente"):
        _propose(seeded, "rename_class", {"name": names[0], "new_name": "OutroNome"})


def test_validate_warns_when_a_table_gets_terms_of_two_classes(seeded):
    assert not [f for f in validate(seeded, check_data=False).findings if f.check == "source_classes"]
    content = load_content(seeded)
    term_class = {t["name"]: t["class"] for t in content["terms"]}
    first = content["mappings"][0]
    other = next(m for m in content["mappings"] if m["source"] != first["source"] and m.get("role") != "metric"
                 and term_class[m["term"]] != term_class[first["term"]])
    edit = _propose(seeded, "update_mapping", _key(other) | {"set": {"source": first["source"], "column": first["column"]}})
    ontology_write.apply_edit(seeded, edit.id, approved_by="maria")
    found = [f for f in validate(seeded, check_data=False).findings if f.check == "source_classes"]
    assert found and found[0].level == "warning" and found[0].subject == first["source"]
    assert term_class[other["term"]] in found[0].message and "update_mapping" in found[0].message
