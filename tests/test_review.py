import pytest
from akme.ontology import load_content, save_content
from akme.tools import ontology_write
from akme.tools.batch import BatchError
from akme.tools.ontology_write import EditError

CQ = {"question": "q", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]}

def test_review_requires_reviewer_reason_and_existing_pending(project):
    e = ontology_write.propose_edit(project, "add_competency_question", CQ)
    with pytest.raises(EditError, match="reviewer"): ontology_write.review_edit(project, e.id, "accept", "")
    with pytest.raises(EditError, match="reason"): ontology_write.review_edit(project, e.id, "reject", "ana")
    with pytest.raises(EditError, match="nao encontrada"): ontology_write.review_edit(project, "add_gap-deadbeef", "accept", "ana")
    r = ontology_write.review_edit(project, e.id, "accept", "ana", edits={"question": "editada", "priority": "high", "status": "approved"})
    assert r.review.reviewer == "ana" and ontology_write.list_pending(project)[0].review.edits["question"] == "editada"

def test_apply_reviewed_merges_edits_and_records_rejections(project):
    a = ontology_write.propose_edit(project, "add_competency_question", CQ)
    b = ontology_write.propose_edit(project, "add_competency_question", CQ | {"question": "outra"})
    c = ontology_write.propose_edit(project, "add_competency_question", CQ | {"question": "sem revisao"})
    ontology_write.review_edit(project, a.id, "accept", "ana", edits={"priority": "high", "status": "approved", "question": "editada"})
    ontology_write.review_edit(project, b.id, "reject", "ana", reason="fora do caso de uso")
    out = ontology_write.apply_reviewed(project, "ana")
    cqs = {x["id"]: x for x in load_content(project)["requirements"]["competency_questions"]}
    assert cqs[a.payload["id"]]["question"] == "editada" and cqs[a.payload["id"]]["reviewed_by"] == "ana"
    assert cqs[b.payload["id"]]["status"] == "rejected" and cqs[b.payload["id"]]["rejection_reason"] == "fora do caso de uso"
    assert out["summary"]["cqs_accepted"] == 1 and out["summary"]["cqs_rejected"] == 1 and out["summary"]["cqs_edited"] == 1
    assert [e.id for e in ontology_write.list_pending(project)] == [c.id]

def test_batch_aborts_on_new_error_and_tolerates_preexisting(seeded):
    content = load_content(seeded); content["mappings"][0]["column"] = "nao_existe"; save_content(seeded, content)  # erro pre-existente
    from akme.tools.profile import profile; profile(seeded)
    ok = ontology_write.propose_edit(seeded, "add_competency_question", CQ); ontology_write.review_edit(seeded, ok.id, "accept", "ana", edits={"priority": "low", "status": "approved"})
    out = ontology_write.apply_reviewed(seeded, "ana")
    assert out["summary"]["cqs_accepted"] == 1 and any(f["check"] == "mapping_column" for f in out["preexisting_errors"])
    bad = ontology_write.propose_edit(seeded, "add_competency_question", CQ | {"question": "reservada sem resposta"}); ontology_write.review_edit(seeded, bad.id, "accept", "ana", edits={"priority": "low", "status": "reserved"})
    before = seeded.content_path.read_text(encoding="utf-8")
    with pytest.raises(BatchError) as exc: ontology_write.apply_reviewed(seeded, "ana")
    assert exc.value.new_errors and seeded.content_path.read_text(encoding="utf-8") == before
    assert [e.id for e in ontology_write.list_pending(seeded)] == [bad.id]


def test_review_accepts_stage2_and_apply_reviewed_filters_by_stage(seeded):
    cls = ontology_write.propose_edit(seeded, "add_class", {"name": "Fornecedor", "label": "Fornecedor", "comment": "c"})
    with pytest.raises(EditError, match="nao aceita a chave"): ontology_write.review_edit(seeded, cls.id, "accept", "ana", edits={"name": "Outro"})
    ontology_write.review_edit(seeded, cls.id, "accept", "ana", edits={"comment": "fornece produtos"})
    cq = ontology_write.propose_edit(seeded, "add_competency_question", CQ); ontology_write.review_edit(seeded, cq.id, "accept", "ana", edits={"priority": "low"})
    out = ontology_write.apply_reviewed(seeded, "ana", stage="requirements")
    assert [e.id for e in ontology_write.list_pending(seeded)] == [cls.id]
    assert out["summary"]["applied_types"] == {"add_competency_question": 1}
    with pytest.raises(EditError, match="stage"): ontology_write.apply_reviewed(seeded, "ana", stage="tudo")
    out = ontology_write.apply_reviewed(seeded, "ana")
    assert out["summary"]["applied_types"] == {"add_class": 1} and out["held_by_gate"] == []
    from akme.ontology import load_graph, classes
    assert next(c for c in classes(load_graph(seeded.schema_path)) if c["name"] == "Fornecedor")["comment"] == "fornece produtos"


def test_rejected_stage2_review_is_discarded_on_apply(seeded):
    term = ontology_write.propose_edit(seeded, "add_term", {"name": "x", "class": "Cliente", "definition": "y"})
    ontology_write.review_edit(seeded, term.id, "reject", "ana", reason="duplicado")
    out = ontology_write.apply_reviewed(seeded, "ana", stage="ontology")
    assert out["rejected"] and ontology_write.list_pending(seeded) == []
    from akme.project import read_yaml
    assert read_yaml(seeded.changelog_path)["entries"][-1]["status"] == "rejected"
    assert all(t["name"] != "x" for t in load_content(seeded)["terms"])


def test_accept_cq_without_status_defaults_to_approved_and_needs_priority(project):
    e = ontology_write.propose_edit(project, "add_competency_question", CQ)
    with pytest.raises(EditError, match="priority"): ontology_write.review_edit(project, e.id, "accept", "ana")
    ontology_write.review_edit(project, e.id, "accept", "ana", edits={"priority": "medium"})
    ontology_write.apply_reviewed(project, "ana")
    cq = load_content(project)["requirements"]["competency_questions"][0]
    assert cq["status"] == "approved" and cq["priority"] == "medium"


def test_review_refuses_reject_for_gap_and_divergence_and_id_in_edits(project):
    g = ontology_write.propose_edit(project, "add_gap", {"question": "q", "reason": "r", "missing": "m", "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]})
    with pytest.raises(EditError, match="ignore"): ontology_write.review_edit(project, g.id, "reject", "ana", reason="nao")
    d = ontology_write.propose_edit(project, "add_divergence", {"topic": "t", "sources": [{"label": "A", "path": "a", "locator": "1", "quote": "x"}, {"label": "B", "path": "b", "locator": "2", "quote": "y"}]})
    with pytest.raises(EditError, match="dismiss"): ontology_write.review_edit(project, d.id, "reject", "ana", reason="nao")
    c = ontology_write.propose_edit(project, "add_competency_question", CQ)
    with pytest.raises(EditError, match="id"): ontology_write.review_edit(project, c.id, "accept", "ana", edits={"id": "CQ-900", "priority": "low"})


def test_batch_wraps_missing_target_and_promotes_nothing(project):
    c = load_content(project); c["requirements"]["competency_questions"].append(CQ | {"id": "CQ-050", "status": "approved", "priority": "low"}); save_content(project, c)
    rm = ontology_write.propose_edit(project, "remove_competency_question", {"id": "CQ-050", "reason": "erro"})
    up = ontology_write.propose_edit(project, "update_competency_question", {"id": "CQ-050", "question": "nova"})
    from akme.tools.batch import apply_batch
    before = project.content_path.read_text(encoding="utf-8")
    with pytest.raises(BatchError, match="id nao encontrado"): apply_batch(project, [rm.id, up.id], "ana")
    assert project.content_path.read_text(encoding="utf-8") == before and len(ontology_write.list_pending(project)) == 2


def test_batch_wraps_unexpected_exception(project, monkeypatch):
    from akme.tools import batch
    e = ontology_write.propose_edit(project, "add_competency_question", CQ)
    def boom(*a, **k): raise KeyError("campo")
    monkeypatch.setattr(batch, "apply_edit", boom)
    with pytest.raises(BatchError, match="campo"): batch.apply_batch(project, [e.id], "ana")


def test_update_cq_stamps_reviewer(seeded):
    u = ontology_write.propose_edit(seeded, "update_competency_question", {"id": "CQ-001", "question": "reescrita"})
    ontology_write.review_edit(seeded, u.id, "accept", "bia")
    ontology_write.apply_reviewed(seeded, "ana")
    cq = next(c for c in load_content(seeded)["requirements"]["competency_questions"] if c["id"] == "CQ-001")
    assert cq["question"] == "reescrita" and cq["reviewed_by"] == "bia" and cq["reviewed_at"]


def test_evidence_items_need_content(project):
    with pytest.raises(EditError, match="locator|quote"):
        ontology_write.propose_edit(project, "add_competency_question", CQ | {"evidence": [{"kind": "source", "path": "a"}]})
    with pytest.raises(EditError, match="when"):
        ontology_write.propose_edit(project, "add_competency_question", CQ | {"evidence": [{"kind": "conversation", "who": "a"}]}, proposed_by="ana")
    with pytest.raises(EditError, match="quote"):
        ontology_write.propose_edit(project, "add_divergence", {"topic": "t", "sources": [{"label": "A", "path": "a", "locator": "1"}, {"label": "B", "path": "b", "locator": "2", "quote": "y"}]})


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="atributo somente-leitura de diretorio e do Windows")
def test_apply_reviewed_promotes_over_readonly_pending_dir(project):
    import os, stat
    os.chmod(project.pending_dir, stat.S_IREAD)  # attrib +R, como num checkout que herdou o atributo
    e = ontology_write.propose_edit(project, "add_competency_question", CQ)
    ontology_write.review_edit(project, e.id, "accept", "ana", edits={"priority": "low"})
    out = ontology_write.apply_reviewed(project, "ana")
    assert out["summary"]["cqs_accepted"] == 1 and ontology_write.list_pending(project) == []


def test_batch_without_new_relation_does_not_read_the_joins(seeded, monkeypatch):
    from akme.tools import batch, validate as validate_mod
    def must_not_read(*a, **k):
        raise AssertionError("lote sem relacao nova nao confere o join no banco")
    monkeypatch.setattr(validate_mod, "observe_join", must_not_read)
    t = ontology_write.propose_edit(seeded, "add_term", {"name": "nf", "class": "Pedido", "definition": "nota fiscal"})
    batch.apply_batch(seeded, [t.id], "ana")
    calls = []
    monkeypatch.setattr(validate_mod, "observe_join", lambda *a, **k: calls.append(1) or {"available": False, "reason": "x"})
    r = ontology_write.propose_edit(seeded, "add_relation", {"name": "atendidoPor", "domain": "Pedido", "range": "Cliente",
                                                            "label": "atendido por", "multiplicity": "many_to_one",
                                                            "no_join_reason": "conceitual"})
    batch.apply_batch(seeded, [r.id], "ana")
    assert calls, "lote com relacao nova confere o join"
