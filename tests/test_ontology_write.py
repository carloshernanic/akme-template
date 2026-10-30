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


def test_cq_requires_type_concepts_and_source_evidence(project):
    base = {"question": "q", "type": "atributos", "concepts": ["X"]}
    with pytest.raises(EditError, match="exige os campos"):
        ontology_write.propose_edit(project, "add_competency_question", base)
    with pytest.raises(EditError, match="source"):
        ontology_write.propose_edit(project, "add_competency_question", base | {"evidence": [{"kind": "conversation", "who": "ana", "when": "x"}]}, proposed_by="agent")
    e = ontology_write.propose_edit(project, "add_competency_question", base | {"evidence": [{"kind": "conversation", "who": "ana", "when": "x"}]}, proposed_by="ana")
    assert e.payload["id"] == "CQ-001" and e.payload["status"] == "proposed"


def test_update_and_remove_cq(seeded):
    u = ontology_write.propose_edit(seeded, "update_competency_question", {"id": "CQ-002", "status": "approved", "priority": "low"})
    ontology_write.apply_edit(seeded, u.id, "ana")
    cq = next(c for c in load_content(seeded)["requirements"]["competency_questions"] if c["id"] == "CQ-002")
    assert cq["status"] == "approved" and cq["priority"] == "low"
    questions = {q["id"]: q for q in read_yaml(seeded.questions_path)["questions"]}
    assert "CQ-002" not in questions and questions["CQ-003"]["expects"]
    entry = read_yaml(seeded.changelog_path)["entries"][-1]; assert entry["before"]["status"] == "reserved" and entry["after"]["status"] == "approved"
    r = ontology_write.propose_edit(seeded, "remove_competency_question", {"id": "CQ-002", "reason": "duplicada"})
    ontology_write.apply_edit(seeded, r.id, "ana")
    cq = next(c for c in load_content(seeded)["requirements"]["competency_questions"] if c["id"] == "CQ-002")
    assert cq["status"] == "deprecated"


def test_remove_orphan_cq_deletes(project):
    e = ontology_write.propose_edit(project, "add_competency_question", {"question": "q", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]}, proposed_by="ana")
    ontology_write.apply_edit(project, e.id, "ana")
    r = ontology_write.propose_edit(project, "remove_competency_question", {"id": "CQ-001", "reason": "erro"})
    ontology_write.apply_edit(project, r.id, "ana")
    assert load_content(project)["requirements"]["competency_questions"] == []


def test_gap_and_divergence_lifecycle(project):
    g = ontology_write.propose_edit(project, "add_gap", {"question": "q", "reason": "r", "missing": "m", "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]})
    ontology_write.apply_edit(project, g.id, "ana")
    with pytest.raises(EditError, match="sources"):
        ontology_write.propose_edit(project, "add_divergence", {"topic": "t", "sources": [{"label": "A", "path": "a", "locator": "1", "quote": "x"}]})
    d = ontology_write.propose_edit(project, "add_divergence", {"topic": "t", "sources": [{"label": "A", "path": "a", "locator": "1", "quote": "x"}, {"label": "B", "path": "b", "locator": "2", "quote": "y"}]})
    ontology_write.apply_edit(project, d.id, "ana")
    u = ontology_write.propose_edit(project, "update_divergence", {"id": "D-01", "decision": "precedence", "winner": "A", "reason": "normativo"})
    ontology_write.apply_edit(project, u.id, "ana")
    req = load_content(project)["requirements"]
    assert req["gaps"][0]["id"] == "L-01" and req["gaps"][0]["decision"] == "open"
    assert req["divergences"][0]["decision"] == "precedence" and req["divergences"][0]["decided_by"] == "ana"
