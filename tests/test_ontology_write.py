import pytest

from akme.ontology import load_content, load_graph, class_names, relations
from akme.project import read_yaml
from akme.tools import ontology_read, ontology_write
from akme.tools.ontology_write import EditError


def test_propose_requires_fields(project):
    with pytest.raises(EditError, match="exige os campos"):
        ontology_write.propose_edit(project, "add_term", {"name": "x"})
    with pytest.raises(EditError, match="desconhecido"):
        ontology_write.propose_edit(project, "drop_everything", {})


def test_propose_does_not_touch_ontology(project):
    before = project.content_path.read_text(encoding="utf-8")
    edit = ontology_write.propose_edit(project, "add_glossary", {"acronym": "UF", "meaning": "estado"})
    assert (project.pending_dir / f"{edit.id}.yml").exists()
    assert project.content_path.read_text(encoding="utf-8") == before
    assert [e.id for e in ontology_write.list_pending(project)] == [edit.id]


def test_apply_requires_approver_and_records_provenance(project):
    edit = ontology_write.propose_edit(project, "add_glossary", {"acronym": "UF", "meaning": "estado"},
                                       requirement_id="CQ-001", evidence="glossario.md")
    with pytest.raises(EditError, match="approved_by"):
        ontology_write.apply_edit(project, edit.id, "")
    entry = ontology_write.apply_edit(project, edit.id, "maria")
    content = load_content(project)
    assert content["glossary"][0]["acronym"] == "UF"
    assert content["evidence"][0]["decision"] == edit.id and content["evidence"][0]["approved_by"] == "maria"
    assert read_yaml(project.changelog_path)["entries"][0]["edit_id"] == edit.id
    assert entry["requirement_id"] == "CQ-001"
    assert ontology_write.list_pending(project) == []
    assert ontology_read.resolve_acronym(project, "uf")["meaning"] == "estado"


def test_class_and_relation_go_to_ttl(project):
    with pytest.raises(EditError, match="nao encontradas"):
        ontology_write.propose_edit(project, "add_relation", {"name": "temX", "domain": "Nada", "range": "Entity", "label": "x"})
    c = ontology_write.propose_edit(project, "add_class", {"name": "Pedido", "label": "Pedido", "comment": "compra"})
    ontology_write.apply_edit(project, c.id, "maria")
    r = ontology_write.propose_edit(project, "add_relation", {"name": "pertenceA", "domain": "Pedido", "range": "Entity",
                                                              "label": "pertence a", "inverse_of": "possui"})
    ontology_write.apply_edit(project, r.id, "maria")
    g = load_graph(project.schema_path)
    assert "Pedido" in class_names(g)
    rels = {x["name"]: x for x in relations(g)}
    assert rels["pertenceA"]["domain"] == ["Pedido"] and rels["pertenceA"]["inverse_of"] == ["possui"]
    assert rels["possui"]["domain"] == ["Entity"]


def test_reject_edit(project):
    edit = ontology_write.propose_edit(project, "add_term", {"name": "x", "class": "Entity", "definition": "y"})
    ontology_write.reject_edit(project, edit.id, "joao", "duplicado")
    assert ontology_write.list_pending(project) == []
    assert read_yaml(project.changelog_path)["entries"][0]["status"] == "rejected"
    assert load_content(project)["terms"] == []
