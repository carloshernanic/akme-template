from akme.ontology import load_content, save_content
from akme.project import read_yaml, write_yaml
from akme.tools import ontology_write, requirements as rq


def _cq(id, status, answer=None, **k):
    d = {"id": id, "question": f"q {id}", "type": "atributos", "concepts": ["X"], "status": status,
         "priority": "high", "evidence": [{"kind": "source", "path": "a.md", "locator": "pagina 1", "quote": "x"}]}
    if answer:
        d["answer"] = answer
    return d | k


def test_next_id_counts_applied_and_pending(project):
    c = load_content(project); c["requirements"]["competency_questions"].append(_cq("CQ-004", "approved")); save_content(project, c)
    assert rq.next_id(project, "CQ") == "CQ-005"
    ontology_write.propose_edit(project, "add_competency_question", _cq("CQ-007", "proposed"))
    assert rq.next_id(project, "CQ") == "CQ-008"
    assert rq.next_id(project, "UC") == "UC-01" and rq.next_id(project, "L") == "L-01"


def test_status_lists_every_missing_condition_on_empty_project(project):
    s = rq.requirements_status(project)
    assert s["closed"] is False and s["ontology_empty"] is True and s["gate_active"] is True
    assert len(s["missing"]) == 3  # caso de uso, nenhuma CQ approved, purpose/scope; pendentes e abertas so entram quando ha itens


def test_status_closes_with_use_case_approved_cq_purpose_scope(project):
    c = load_content(project); r = c["requirements"]
    r["use_cases"].append({"id": "UC-01", "name": "n", "description": "d"}); r["purpose"] = "p"; r["scope"] = "s"
    r["competency_questions"].append(_cq("CQ-001", "approved")); save_content(project, c)
    assert rq.requirements_status(project)["closed"] is True
    r["gaps"].append({"id": "L-01", "question": "q", "reason": "r", "missing": "m", "decision": "open"}); save_content(project, c)
    s = rq.requirements_status(project); assert s["closed"] is False and any("L-01" in m for m in s["missing"])


def test_mirror_reserved_merges_and_preserves_expects(project):
    write_yaml(project.questions_path, {"questions": [{"id": "CQ-002", "question": "old", "expects": ["Cliente type Class"]}, {"id": "ZZ", "question": "orfa"}]})
    c = load_content(project); c["requirements"]["competency_questions"] += [_cq("CQ-002", "reserved", "financeiro"), _cq("CQ-003", "reserved", "categoria"), _cq("CQ-001", "approved")]; save_content(project, c)
    rq.mirror_reserved(project)
    q = {x["id"]: x for x in read_yaml(project.questions_path)["questions"]}
    assert q["CQ-002"]["expects"] == ["Cliente type Class"] and q["CQ-002"]["question"] == "q CQ-002" and q["CQ-002"]["answer"] == "financeiro"
    assert "CQ-003" in q and "ZZ" in q and "CQ-001" not in q


def test_cq_references_on_seeded(seeded):
    assert rq.cq_references(seeded, "CQ-001")["changelog"]  # classes e termos do seed apontam para CQ-001


def test_cq_references_and_data_request_on_empty(project):
    assert rq.cq_references(project, "CQ-999") == {"changelog": [], "evidence": [], "in_questions": False}
    assert rq.data_request(project) == []
