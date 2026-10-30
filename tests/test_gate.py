import pytest
from akme.tools import ontology_write, requirements as rq
from akme.tools.ontology_write import EditError


def test_gate_blocks_classes_until_requirements_closed(project):
    with pytest.raises(EditError, match="requisitos nao fechados"):
        ontology_write.propose_edit(project, "add_class", {"name": "Cliente", "label": "Cliente", "comment": "c"})
    for t, p in [("add_use_case", {"name": "n", "description": "d"}),
                 ("add_requirement", {"field": "purpose", "value": "p"}), ("add_requirement", {"field": "scope", "value": "s"}),
                 ("add_competency_question", {"question": "q", "type": "atributos", "concepts": ["X"], "status": "approved", "priority": "high",
                                              "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]})]:
        e = ontology_write.propose_edit(project, t, p, proposed_by="ana")
        ontology_write.apply_edit(project, e.id, "ana")
    assert rq.requirements_status(project)["closed"] is True
    ontology_write.propose_edit(project, "add_class", {"name": "Cliente", "label": "Cliente", "comment": "c"})


def test_gate_inactive_once_ontology_has_domain_classes(seeded):
    ontology_write.propose_edit(seeded, "add_competency_question", {"question": "nova", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]}, proposed_by="ana")
    assert rq.requirements_status(seeded)["closed"] is False and rq.requirements_status(seeded)["gate_active"] is False
    ontology_write.propose_edit(seeded, "add_class", {"name": "Transportadora", "label": "Transportadora", "comment": "c"})


def test_demo_seed_closes_gate_before_first_class(seeded):
    from akme.project import read_yaml
    entries = read_yaml(seeded.changelog_path)["entries"]
    first_class = next(i for i, e in enumerate(entries) if e["type"] == "add_class")
    types_before = {e["type"] for e in entries[:first_class]}
    assert {"add_use_case", "add_competency_question", "add_gap", "add_divergence"} <= types_before
