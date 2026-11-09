import asyncio

import mcp.types as types
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from akme import server as akme_server
from akme.ontology import load_content
from akme.project import read_yaml
from akme.tools import decision_mode, ontology_write
from akme.tools.decision_mode import ModeError
from akme.tools.stage import current_stage

EV = [{"kind": "source", "path": "data/pedidos.csv", "locator": "coluna status", "quote": "FATURADO"}]


def _cq(project, question="Quantos pedidos por status?"):
    return ontology_write.propose_edit(project, "add_competency_question",
                                       {"question": question, "type": "atributos", "concepts": ["Pedido"], "evidence": EV})


def test_default_is_human_and_not_chosen(project):
    m = decision_mode.read_mode(project)
    assert m["mode"] == "human" and m["chosen"] is False
    st = current_stage(project)
    assert st["decision_mode"]["chosen"] is False
    assert st["checklist"][0]["text"].startswith("Modo de decisão") and st["checklist"][0]["done"] is False


def test_ai_cannot_review_apply_or_reject_in_human_mode(project):
    e = _cq(project)
    with pytest.raises(ModeError):
        ontology_write.review_edit(project, e.id, "accept", "IA", edits={"priority": "high"})
    ontology_write.review_edit(project, e.id, "accept", "Ana", edits={"priority": "high"})
    with pytest.raises(ModeError):
        ontology_write.apply_reviewed(project, "IA")
    with pytest.raises(ModeError):
        ontology_write.apply_edit(project, e.id, "agent")
    with pytest.raises(ModeError):
        ontology_write.reject_edit(project, e.id, "Claude", "nao")
    assert ontology_write.list_pending(project)  # nada mudou


def test_auto_mode_lets_ai_decide_and_signs_with_who_authorized(project):
    decision_mode.set_mode(project, "auto", "Ana")
    a, b = _cq(project), _cq(project, "Qual o ticket medio?")
    ontology_write.review_edit(project, a.id, "accept", "IA", edits={"priority": "medium"})
    ontology_write.review_edit(project, b.id, "reject", "IA", reason="sem evidencia suficiente")
    ontology_write.apply_reviewed(project, "IA")
    signature = "IA (modo automatico, autorizado por Ana)"
    entries = read_yaml(project.changelog_path)["entries"]
    assert entries and all(e.get("approved_by") == signature for e in entries)
    cqs = {c["question"]: c for c in load_content(project)["requirements"]["competency_questions"]}
    assert cqs["Quantos pedidos por status?"]["reviewed_by"] == signature
    assert cqs["Qual o ticket medio?"]["status"] == "rejected"
    st = current_stage(project)
    assert st["decision_mode"]["mode"] == "auto"
    assert any(s["text"].startswith("IA decidiu e aplicou") for s in st["checklist"])


def test_switching_mode_keeps_history_and_rejects_ai_as_authorizer(project):
    decision_mode.set_mode(project, "auto", "Ana")
    decision_mode.set_mode(project, "human", "Bia")
    m = decision_mode.read_mode(project)
    assert m["mode"] == "human" and m["authorized_by"] == "Bia"
    assert m["history"][0]["mode"] == "auto" and m["history"][0]["authorized_by"] == "Ana"
    with pytest.raises(ModeError):
        decision_mode.set_mode(project, "auto", "IA")
    with pytest.raises(ModeError):
        decision_mode.set_mode(project, "turbo", "Ana")


def _call(project, monkeypatch, args, elicitation_callback=None):
    monkeypatch.setenv("AKME_ROOT", str(project.root))

    async def go():
        async with create_connected_server_and_client_session(
                akme_server.mcp, elicitation_callback=elicitation_callback) as client:
            return await client.call_tool("choose_decision_mode", args)
    return asyncio.run(go())


def test_tool_asks_with_a_form_when_harness_supports_it(project, monkeypatch):
    seen = []

    async def answer(context, params):
        seen.append(params.requestedSchema)
        return types.ElicitResult(action="accept", content={"modo": "auto", "nome": "Ana"})

    res = _call(project, monkeypatch, {}, answer)
    assert not res.isError, res.content
    assert res.structuredContent["status"] == "set" and res.structuredContent["mode"] == "auto"
    assert seen[0]["properties"]["modo"]["enum"] == ["human", "auto"]
    assert decision_mode.read_mode(project)["authorized_by"] == "Ana"


def test_tool_falls_back_to_chat_and_accepts_explicit_mode(project, monkeypatch):
    res = _call(project, monkeypatch, {})
    assert res.structuredContent["status"] == "ask_in_chat"
    res = _call(project, monkeypatch, {"mode": "auto", "authorized_by": "Ana"})
    assert res.structuredContent["status"] == "set" and res.structuredContent["mode"] == "auto"
