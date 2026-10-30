from akme.ontology import load_content, save_content
from akme.tools.profile import profile
from akme.tools.validate import validate


def test_empty_template_is_valid(project):
    report = validate(project)
    assert report.ok
    assert any(f.check == "profile_missing" for f in report.findings)
    assert report.pitfalls == []


def test_seeded_demo_validates_with_coverage(seeded):
    profile(seeded)
    report = validate(seeded)
    assert report.ok, [f.message for f in report.errors]
    assert report.coverage["mapped"] == 10
    assert report.coverage["by_source"]["pedidos"]["unmapped"] == ["id_cliente", "nf"]
    codes = {(p["code"], p["subject"]) for p in report.pitfalls}
    assert ("P13", "referencia") in codes
    assert ("P13", "pertenceA") not in codes
    assert seeded.validation_path.exists()


def test_detects_broken_references(seeded):
    profile(seeded)
    content = load_content(seeded)
    content["terms"].append({"name": "fantasma", "class": "NaoExiste", "definition": ""})
    content["mappings"].append({"term": "pedido", "source": "pedidos", "column": "coluna_errada"})
    content["precedence"].append({"topic": "cliente ativo", "winner": "erp", "over": "financeiro"})
    save_content(seeded, content)
    report = validate(seeded)
    assert not report.ok
    assert {f.check for f in report.errors} == {"term_class", "mapping_column", "precedence_conflict"}


def test_broken_ttl_is_reported(project):
    project.schema_path.write_text("isto nao e turtle @@", encoding="utf-8")
    report = validate(project)
    assert not report.ok and report.errors[0].check == "ttl_parse"


def test_validate_requirement_rules(project):
    c = load_content(project); r = c["requirements"]
    r["competency_questions"] += [{"id": "CQ-001", "question": "q", "type": "atributos", "concepts": ["X"], "status": "reserved", "priority": "high", "proposed_by": "agent",
                                   "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]},
                                  {"id": "CQ-002", "question": "q", "type": "atributos", "concepts": ["X"], "status": "approved", "proposed_by": "ana",
                                   "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]}]
    r["gaps"].append({"id": "L-01", "question": "q", "reason": "r", "missing": "m", "decision": "open"}); save_content(project, c)
    checks = {(f.level, f.check) for f in validate(project).findings}
    assert {("error", "cq_reserved_without_answer"), ("error", "cq_approved_without_priority"), ("error", "cq_agent_without_source_evidence"), ("warning", "open_gap_or_divergence")} <= checks


def test_validate_warns_without_reserved(seeded):
    c = load_content(seeded)
    for cq in c["requirements"]["competency_questions"]: cq["status"] = "approved"
    save_content(seeded, c)
    assert any(f.check == "no_reserved_cq" for f in validate(seeded).findings)
