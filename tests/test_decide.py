import asyncio
from types import SimpleNamespace

import mcp.types as types
from mcp.shared.memory import create_connected_server_and_client_session

from akme import server as akme_server
from akme.ontology import load_content
from akme.tools import decide, ontology_write

EV = [{"kind": "source", "path": "data/pedidos.csv", "locator": "coluna status", "quote": "FATURADO"}]


def _cq(project, question="Quantos pedidos por status?", **extra):
    payload = {"question": question, "type": "atributos", "concepts": ["Pedido"], "evidence": EV} | extra
    return ontology_write.propose_edit(project, "add_competency_question", payload)


def _gap(project, **extra):
    payload = {"question": "Qual a regra de devolucao?", "reason": "nenhum documento", "missing": "regra",
               "evidence": EV} | extra
    return ontology_write.propose_edit(project, "add_gap", payload)


class Script:
    """ask falso: responde cada formulario com a proxima resposta da fila, guardando o que foi perguntado."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.asked = []

    async def __call__(self, message, schema):
        self.asked.append((schema.__name__, message, schema.model_json_schema()))
        action, values = self.answers.pop(0)
        if action != "accept":
            return SimpleNamespace(action=action, data=None)
        defaults = {k: f.default for k, f in schema.model_fields.items() if not f.is_required()}
        return SimpleNamespace(action="accept", data=schema(**(defaults | values)))


def test_one_by_one_records_decisions_and_applies(project):
    a = _cq(project)
    b = _cq(project, "Qual o ticket medio?")
    g = _gap(project)
    ask = Script(
        ("accept", {"nome": "Ana"}),
        ("accept", {"modo": "um_a_um"}),
        ("accept", {"prioridade": "high"}),                               # CQ a: aceita, alta
        ("accept", {"decisao": "rejeitar"}),                              # CQ b: sem motivo, deve perguntar de novo
        ("accept", {"decisao": "rejeitar", "motivo": "fora do escopo"}),
        ("accept", {"decisao": "drop", "nota": "cliente nao tem o dado"}),  # lacuna
        ("accept", {"acao": "aplicar"}),
    )
    out = asyncio.run(decide.run(project, ask, "requirements"))
    assert out["status"] == "applied" and out["approved_by"] == "Ana"
    assert out["decided"] == 3 and out["applied"] >= 2 and out["pending"] == 0
    assert "Para rejeitar, escreva o motivo" in ask.asked[4][1]
    cqs = {c["question"]: c for c in load_content(project)["requirements"]["competency_questions"]}
    first = next(q for q in cqs if q in ask.asked[2][1])   # a ordem segue created_at, que empata no mesmo segundo
    second = next(q for q in cqs if q != first)
    assert cqs[first]["priority"] == "high" and cqs[first]["status"] == "approved"
    assert cqs[second]["status"] == "rejected" and cqs[second]["rejection_reason"] == "fora do escopo"
    assert load_content(project)["requirements"]["gaps"][0]["decision"] == "drop"
    assert not ontology_write.list_pending(project)
    assert {a.id, b.id, g.id}  # ids existiam


def test_accept_all_gives_cq_default_priority_and_sends_gap_without_decision_to_manual(project):
    _cq(project)
    _gap(project)  # sem decisao proposta: vai para o formulario
    ask = Script(
        ("accept", {"modo": "aceitar_todas"}),
        ("accept", {"decisao": "open"}),
        ("accept", {"acao": "depois"}),
    )
    out = asyncio.run(decide.run(project, ask, "requirements", reviewer="Bia"))
    assert out["status"] == "decided" and out["decided"] == 2 and out["ready_to_apply"] == 2
    cq = next(e for e in ontology_write.list_pending(project) if e.type.value == "add_competency_question")
    assert cq.review.edits["priority"] == "medium" and cq.review.reviewer == "Bia"
    assert [n for n, _, _ in ask.asked] == ["Modo", "DecisaoLacuna", "Aplicar"]


def test_decline_skips_and_cancel_stops(project):
    _cq(project)
    _cq(project, "Qual o ticket medio?")
    ask = Script(("accept", {"modo": "um_a_um"}), ("decline", {}), ("cancel", {}))
    out = asyncio.run(decide.run(project, ask, "requirements", reviewer="Ana"))
    assert out["stopped"] is True and len(out["skipped"]) == 1 and out["status"] == "decided"
    assert all(e.review is None for e in ontology_write.list_pending(project))


def test_postpone_and_nothing_to_decide(project):
    _cq(project)
    out = asyncio.run(decide.run(project, Script(("accept", {"modo": "depois"})), "requirements", "Ana"))
    assert out["status"] == "postponed" and out["pending"] == 1
    other = asyncio.run(decide.run(project, Script(), "ontology", "Ana"))
    assert other["status"] == "nothing_to_decide"


def test_form_schemas_only_use_primitive_fields(project):
    """Os formularios precisam passar no validador do SDK (so tipos primitivos, escolhas como enum)."""
    from mcp.server.elicitation import _validate_elicitation_schema
    for e in (_cq(project), _gap(project)):
        schema = decide.form_for(e)
        _validate_elicitation_schema(schema)
        assert schema.model_json_schema()["properties"]["decisao"]["enum"]
    assert "data/pedidos.csv" in decide.describe(e) and "FATURADO" in decide.describe(e)


def test_form_message_is_short_and_details_go_to_decision_field(project):
    """O Claude Code mostra so o comeco da mensagem; a evidencia vai na descricao do campo, que aparece inteira."""
    e = ontology_write.propose_edit(project, "add_requirement", {"field": "users", "value": "analista, gestor"},
                                    rationale="citado no kickoff", evidence='[{"kind": "source", "path": "data/k.pptx", '
                                    '"locator": "slide 2", "quote": "analistas"}]')
    assert len(decide.headline(e, 1, 20).splitlines()) == 2
    info = decide.form_for(e).model_json_schema()["properties"]["decisao"]["description"]
    assert "data/k.pptx · slide 2" in info and "citado no kickoff" in info
    assert "Valor:" not in info  # ja aparece como campo editavel


def _call(project, monkeypatch, elicitation_callback=None):
    monkeypatch.setenv("AKME_ROOT", str(project.root))

    async def go():
        async with create_connected_server_and_client_session(
                akme_server.mcp, elicitation_callback=elicitation_callback) as client:
            res = await client.call_tool("decide_pending", {"stage": "requirements", "reviewer": "Ana"})
            return res
    return asyncio.run(go())


def test_mcp_tool_uses_client_elicitation(project, monkeypatch):
    _cq(project)
    seen = []

    async def answer(context, params):
        seen.append(params.requestedSchema)
        props = params.requestedSchema["properties"]
        if "modo" in props:
            return types.ElicitResult(action="accept", content={"modo": "aceitar_todas"})
        return types.ElicitResult(action="accept", content={"acao": "aplicar", "aprovador": "Ana"})

    res = _call(project, monkeypatch, answer)
    assert not res.isError, res.content
    assert res.structuredContent["status"] == "applied"
    assert seen[0]["properties"]["modo"]["enum"] == ["um_a_um", "aceitar_todas", "depois"]
    assert load_content(project)["requirements"]["competency_questions"][0]["priority"] == "medium"


def test_mcp_tool_falls_back_without_elicitation(project, monkeypatch):
    _cq(project)
    res = _call(project, monkeypatch)
    assert res.structuredContent["status"] == "no_elicitation"
    assert res.structuredContent["items"][0]["type"] == "add_competency_question"
