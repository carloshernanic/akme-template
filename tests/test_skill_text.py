from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_and_manifest_describe_review_flow():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for needle in ("requirements_status", "apply_reviewed", "akme review", "add_gap", "add_divergence", "add_use_case", "dez CQs", "kind: source"):
        assert needle in skill, needle
    manifest = (ROOT / "ontology" / "manifest.yml").read_text(encoding="utf-8")
    assert "apply_reviewed" in manifest and "requirements_status" in manifest


def test_skill_keeps_six_stages_and_gate_texts():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for n, name in enumerate(("Especificar", "Conceitualizar", "Codificar", "Avaliar", "Publicar", "Manter"), 1):
        assert f"### {n}. {name}" in skill
    assert "### 7." not in skill
    assert "volte à etapa 1" in skill or "volte a etapa 1" in skill
    assert "o eval não testará pelo resultado" in skill or "o eval nao testara pelo resultado" in skill
    assert "no_use_case" in skill and "kind: conversation" in skill


def test_manifest_lists_requirements_and_review_tools():
    import yaml
    manifest = yaml.safe_load((ROOT / "ontology" / "manifest.yml").read_text(encoding="utf-8"))
    tools = {t["name"]: t for t in manifest["tools"]}
    assert "data_request" in tools["requirements"]["description"] and tools["requirements"]["requires_approval"] is False
    assert "akme review" in tools["review"]["description"] and tools["review"]["requires_approval"] is True
    for t in ("add_use_case", "add_gap", "add_divergence", "update_competency_question"):
        assert t in tools["ontology_write"]["description"]


def test_skill_guards_apply_reviewed_and_lists_requirement_checks():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "`apply_reviewed` so pode ser chamado depois" in skill
    assert "`publish`, `apply_edit` e `apply_reviewed`" in skill
    for check in ("cq_reserved_without_answer", "cq_approved_without_priority", "cq_agent_without_source_evidence", "no_reserved_cq", "open_gap_or_divergence"):
        assert check in skill, check


def test_skill_sends_the_human_to_the_page_not_the_file():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "open_review" in skill and "`stage`" in skill
    assert "Salvar e aplicar" in skill and "Aplicar decididas" not in skill
    assert "aponte o humano para `docs/index.html`" not in skill
    assert "Etapa X de 6 concluida" in skill


def test_skill_waits_for_page_and_mirrors_checklist():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "## Roteiro visivel no harness" in skill and "checklist" in skill
    assert skill.count("wait_for_review") >= 5
    assert "Volte para o chat da criacao de ontologia" in skill
    assert "akme wait-review" in skill


def test_skill_asks_decision_mode_first_and_describes_auto_mode():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "## Modo de decisao" in skill and "choose_decision_mode" in skill
    assert 'reviewer: "IA"' in skill and 'approved_by: "IA"' in skill
    assert "--no-dry-run" in skill and "request_from_client" in skill


def test_skill_asks_use_case_on_the_page_first():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "de 2 a 3 casos de uso" in skill
    assert "Primeira rodada: so os casos de uso" in skill and "Segunda rodada" in skill
    assert "Nao pergunte o caso de uso no chat" in skill
    assert "1. Pergunte o caso de uso" not in skill
