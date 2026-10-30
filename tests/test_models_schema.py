from akme.models import (CQ_STATUSES, CQ_TYPES, DIVERGENCE_DECISIONS, GAP_DECISIONS, ONTOLOGY_TYPES,
                         REQUIRED_FIELDS, STAGE1_TYPES, Edit, EditType, Review)
from akme.ontology import load_content

def test_new_edit_types_and_vocabularies():
    assert EditType("add_gap") in STAGE1_TYPES and EditType.add_class in ONTOLOGY_TYPES
    assert REQUIRED_FIELDS[EditType.add_gap] == ["question", "reason", "missing", "evidence"]
    assert "dismiss" in DIVERGENCE_DECISIONS and "request_from_client" in GAP_DECISIONS
    assert CQ_TYPES[0] == "classificacao_hierarquia" and "reserved" in CQ_STATUSES

def test_edit_carries_optional_review():
    e = Edit(id="x", type=EditType.add_gap, payload={})
    assert e.review is None
    e2 = Edit(id="x", type=EditType.add_gap, payload={}, review=Review(decision="reject", reviewer="ana", reviewed_at="2026-10-30T00:00:00+00:00", reason="duplicada"))
    assert e2.model_dump(mode="json")["review"]["reason"] == "duplicada"

def test_empty_content_has_requirement_sections(project):
    req = load_content(project)["requirements"]
    assert req["use_cases"] == [] and req["gaps"] == [] and req["divergences"] == [] and req["no_use_case"] == ""
