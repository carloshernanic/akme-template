"""Decisoes do humano pelo proprio chat, via MCP elicitation.

O harness (Claude Code, por exemplo) desenha um formulario para cada pendente e devolve a resposta
para a tool, sem o humano sair do chat. A logica aqui nao depende do MCP: `run` recebe uma corrotina
`ask(message, schema)` com o contrato de `Context.elicit` (resultado com `action` accept, decline ou
cancel e `data` no accept). As decisoes passam por `review_edit` e a aplicacao por `apply_reviewed`,
com as mesmas validacoes da pagina e do chat.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field, create_model

from ..models import ONTOLOGY_TYPES, STAGE1_TYPES, Edit, EditType
from ..project import Project
from .batch import BatchError
from .ontology_write import EditError, apply_reviewed, list_pending, review_edit
from .review_view import EDITABLE, present

Ask = Callable[[str, type[BaseModel]], Awaitable[Any]]

STAGE_TYPES = {"requirements": STAGE1_TYPES, "ontology": ONTOLOGY_TYPES, "all": STAGE1_TYPES | ONTOLOGY_TYPES}
MAX_TRIES = 3
LIST_LIMIT = 30

DECISION = [("aceitar", "Aceitar"), ("rejeitar", "Rejeitar")]
PRIORITY = [("high", "Alta"), ("medium", "Média"), ("low", "Baixa")]
USE = [("approved", "Usar na construção"), ("reserved", "Guardar para o teste (exige resposta esperada)")]
GAP = [("request_from_client", "Pedir o dado ao cliente"), ("reformulate", "Reformular a pergunta"),
       ("drop", "Descartar"), ("open", "Deixar em aberto")]
DIV = [("precedence", "Uma fonte prevalece"), ("distinct_terms", "São conceitos distintos"),
       ("ask_expert", "Perguntar ao especialista"), ("dismiss", "Descartar"), ("open", "Deixar em aberto")]
MODE = [("um_a_um", "Decidir uma a uma"),
        ("aceitar_todas", "Aceitar todas como propostas (CQ sem prioridade fica Média)"),
        ("depois", "Agora não")]
APPLY = [("aplicar", "Aplicar agora na ontologia"), ("depois", "Deixar decidido, aplicar depois")]


def _choice(options: list[tuple[str, str]], default: str | None, title: str, description: str = "") -> tuple[Any, Any]:
    """Campo de escolha: str com enum no JSON Schema (o SDK so aceita tipos primitivos)."""
    extra = {"enum": [v for v, _ in options], "enumNames": [label for _, label in options]}
    if default is None:
        return (str, Field(title=title, description=description or None, json_schema_extra=extra))
    return (str, Field(default=default, title=title, description=description or None, json_schema_extra=extra))


def _text(default: str, title: str, description: str = "") -> tuple[Any, Any]:
    return (str, Field(default=default, title=title, description=description or None))


def _model(name: str, fields: dict[str, tuple[Any, Any]]) -> type[BaseModel]:
    return create_model(name, **fields)  # type: ignore[call-overload]


class ReviewerForm(BaseModel):
    nome: str = Field(title="Seu nome", description="Fica registrado no changelog como quem revisou.")


def _pick(options: list[tuple[str, str]], value: Any, fallback: str) -> str:
    return value if any(v == value for v, _ in options) else fallback


def queue(project: Project, stage: str = "all") -> list[Edit]:
    """Pendentes sem decisao da etapa pedida, na ordem em que foram propostos."""
    if stage not in STAGE_TYPES:
        raise EditError(f"stage invalido: {stage}. Opcoes: {list(STAGE_TYPES)}")
    wanted = STAGE_TYPES[stage]
    return sorted((e for e in list_pending(project) if e.review is None and e.type in wanted),
                  key=lambda e: (e.created_at, e.id))


def describe(edit: Edit, index: int = 0, total: int = 0) -> str:
    """Texto do formulario: o mesmo conteudo do cartao da pagina, em texto corrido."""
    v = present(edit)
    head = f"[{index}/{total}] " if total else ""
    lines = [f"{head}{v['group_label']}" + (f" · {v['subtitle']}" if v["subtitle"] else ""), v["title"], ""]
    for f in v["fields"]:
        lines.append(f"{f['label']}: {f['value']}")
    if v["evidence"]:
        lines.append("")
        lines.append("Evidência:")
        for ev in v["evidence"]:
            where = " · ".join(x for x in (ev.get("path"), ev.get("locator")) if x)
            quote = f' "{ev["quote"]}"' if ev.get("quote") else ""
            who = f"conversa com {ev['who']}" if ev.get("kind") == "conversation" and ev.get("who") else ""
            note = ev.get("note") or ""
            lines.append("- " + " ".join(x for x in (where or who, quote.strip(), note) if x))
    observed = v.get("observed")
    if observed and observed.get("available"):
        lines.append("")
        lines.append("O que o dado mostra:")
        lines.extend(f"- {line}" for line in observed["lines"])
    for alert in v["alerts"]:
        lines.append(f"ATENÇÃO: {alert}")
    if v["rationale"]:
        lines.append("")
        lines.append(f"Por que a IA propôs: {v['rationale']}")
    return "\n".join(lines).strip()


def form_for(edit: Edit) -> type[BaseModel]:
    """Formulario de decisao por tipo de pendente, com os padroes da proposta ja preenchidos."""
    p, t = edit.payload, edit.type
    if t == EditType.add_competency_question:
        return _model("DecisaoCQ", {
            "decisao": _choice(DECISION, "aceitar", "Decisão"),
            "prioridade": _choice(PRIORITY, _pick(PRIORITY, p.get("priority"), "medium"), "Prioridade"),
            "uso": _choice(USE, _pick(USE, p.get("status"), "approved"), "Uso da pergunta"),
            "resposta_esperada": _text(str(p.get("answer") or ""), "Resposta esperada", "Obrigatória para guardar para o teste."),
            "motivo": _text("", "Motivo da rejeição", "Obrigatório para rejeitar."),
        })
    if t in (EditType.add_gap, EditType.update_gap):
        return _model("DecisaoLacuna", {
            "decisao": _choice(GAP, _pick(GAP, p.get("decision"), "request_from_client"), "O que fazer com esta lacuna"),
            "nota": _text(str(p.get("note") or ""), "Explicação", "Obrigatória, exceto para Deixar em aberto."),
        })
    if t in (EditType.add_divergence, EditType.update_divergence):
        labels = [str(s.get("label") or s.get("path") or "") for s in (p.get("sources") or []) if isinstance(s, dict)]
        winners = [(lbl, lbl) for lbl in labels if lbl] or [("", "(sem fontes)")]
        return _model("DecisaoDivergencia", {
            "decisao": _choice(DIV, _pick(DIV, p.get("decision"), "precedence"), "O que fazer com esta divergência"),
            "prevalece": _choice(winners, _pick(winners, p.get("winner"), winners[0][0]), "Fonte que prevalece",
                                 "Usada só quando uma fonte prevalece."),
            "motivo": _text(str(p.get("reason") or ""), "Explicação", "Obrigatória, exceto para Deixar em aberto."),
        })
    fields: dict[str, tuple[Any, Any]] = {"decisao": _choice(DECISION, "aceitar", "Decisão")}
    for spec in EDITABLE.get(t, []):
        value = p.get(spec["key"])
        text = ", ".join(str(x) for x in value) if isinstance(value, list) else str(value or "")
        fields[f"campo_{spec['key']}"] = _text(text, spec["label"], "Ajuste antes de aceitar, se quiser.")
    fields["motivo"] = _text("", "Motivo da rejeição", "Obrigatório para rejeitar.")
    return _model("Decisao", fields)


def record(project: Project, edit: Edit, data: dict[str, Any], reviewer: str) -> str | None:
    """Grava a decisao do formulario no pendente. Devolve a mensagem de erro, ou None se gravou."""
    t = edit.type
    try:
        if t == EditType.add_competency_question:
            if data.get("decisao") == "rejeitar":
                if not str(data.get("motivo") or "").strip():
                    return "Para rejeitar, escreva o motivo."
                review_edit(project, edit.id, "reject", reviewer, reason=data["motivo"].strip())
                return None
            edits: dict[str, Any] = {"priority": data.get("prioridade") or "medium", "status": data.get("uso") or "approved"}
            if edits["status"] == "reserved":
                answer = str(data.get("resposta_esperada") or "").strip()
                if not answer:
                    return "Para guardar para o teste, escreva a resposta esperada."
                edits["answer"] = answer
            review_edit(project, edit.id, "accept", reviewer, edits=edits)
            return None
        if t in (EditType.add_gap, EditType.update_gap):
            choice, note = data.get("decisao"), str(data.get("nota") or "").strip()
            if choice != "open" and not note:
                return "Explique a decisão (só Deixar em aberto dispensa)."
            review_edit(project, edit.id, "accept", reviewer, edits={"decision": choice} | ({"note": note} if note else {}))
            return None
        if t in (EditType.add_divergence, EditType.update_divergence):
            choice, reason = data.get("decisao"), str(data.get("motivo") or "").strip()
            if choice == "precedence" and not data.get("prevalece"):
                return "Escolha a fonte que prevalece."
            if choice != "open" and not reason:
                return "Explique a decisão (só Deixar em aberto dispensa)."
            edits = {"decision": choice} | ({"reason": reason} if reason else {})
            if choice == "precedence":
                edits["winner"] = data["prevalece"]
            review_edit(project, edit.id, "accept", reviewer, edits=edits)
            return None
        if data.get("decisao") == "rejeitar":
            if not str(data.get("motivo") or "").strip():
                return "Para rejeitar, escreva o motivo."
            review_edit(project, edit.id, "reject", reviewer, reason=data["motivo"].strip())
            return None
        edits = {}
        for spec in EDITABLE.get(t, []):
            key = f"campo_{spec['key']}"
            if key not in data:
                continue
            new = str(data[key] or "").strip()
            old = edit.payload.get(spec["key"])
            if spec["kind"] == "list":
                as_list = [x.strip() for x in new.split(",") if x.strip()]
                if as_list != list(old or []):
                    edits[spec["key"]] = as_list
            elif new != str(old or "").strip():
                edits[spec["key"]] = new
        review_edit(project, edit.id, "accept", reviewer, edits=edits or None)
        return None
    except EditError as exc:
        return str(exc)


def accept_as_proposed(project: Project, edits: list[Edit], reviewer: str) -> tuple[list[str], list[Edit]]:
    """O "Aceitar tudo" da pagina: aceita como veio. Lacuna ou divergencia sem decisao proposta,
    ou qualquer item que a validacao recuse, volta para decisao uma a uma."""
    accepted, manual = [], []
    for e in edits:
        p, t = e.payload, e.type
        if t in (EditType.add_gap, EditType.update_gap, EditType.add_divergence, EditType.update_divergence):
            if not p.get("decision") or p["decision"] == "open":  # aberta trava o fechamento dos requisitos
                manual.append(e)
                continue
            data = {"decisao": p["decision"], "nota": p.get("note") or p.get("reason") or "aceita como proposta",
                    "motivo": p.get("reason") or "aceita como proposta", "prevalece": p.get("winner") or ""}
        elif t == EditType.add_competency_question:
            data = {"decisao": "aceitar", "prioridade": _pick(PRIORITY, p.get("priority"), "medium"),
                    "uso": "reserved" if p.get("status") == "reserved" and p.get("answer") else "approved",
                    "resposta_esperada": p.get("answer") or ""}
        else:
            data = {"decisao": "aceitar"}
        (manual.append(e) if record(project, e, data, reviewer) else accepted.append(e.id))
    return accepted, manual


def _short_list(edits: list[Edit]) -> str:
    out = []
    for e in edits[:LIST_LIMIT]:
        v = present(e)
        out.append(f"- {v['title']} ({v['group_label']})")
    if len(edits) > LIST_LIMIT:
        out.append(f"- e mais {len(edits) - LIST_LIMIT}")
    return "\n".join(out)


def fallback(edits: list[Edit]) -> dict[str, Any]:
    """Harness sem elicitation: devolve a fila para o agente decidir com o humano no chat."""
    return {
        "status": "no_elicitation",
        "items": [{"id": e.id, "type": e.type.value, "text": describe(e)} for e in edits],
        "hint": ("Este harness nao desenha formularios. Mostre cada item ao humano no chat (use a ferramenta de "
                 "perguntas do harness, se houver), grave cada resposta com review_edit e, depois do 'aplica' com "
                 "o nome de quem aprova, chame apply_reviewed."),
    }


def _summary(project: Project, stage: str) -> dict[str, Any]:
    from .stage import current_stage
    st = current_stage(project)
    return {"stage": st["label"], "next_step": st["next_step"], "checklist": st["checklist"]}


async def run(project: Project, ask: Ask, stage: str = "all", reviewer: str = "") -> dict[str, Any]:
    """Conduz as decisoes pelo chat: nome do revisor, modo (uma a uma ou aceitar todas), um formulario
    por pendente e, no fim, a confirmacao de aplicar com o nome de quem aprova."""
    todo = queue(project, stage)
    wanted = STAGE_TYPES[stage]
    if not todo and not any(e.review and e.type in wanted for e in list_pending(project)):
        return {"status": "nothing_to_decide"} | _summary(project, stage)

    reviewer = reviewer.strip()
    if not reviewer:
        res = await ask("Antes de decidir: quem está revisando?", ReviewerForm)
        if res.action != "accept" or not res.data.nome.strip():
            return {"status": "cancelled", "decided": 0, "pending": len(todo)}
        reviewer = res.data.nome.strip()

    decided: list[str] = []
    skipped: list[str] = []
    stopped = False
    if todo:
        mode_form = _model("Modo", {"modo": _choice(MODE, "um_a_um", "Como decidir")})
        res = await ask(f"{len(todo)} propostas esperam sua decisão:\n{_short_list(todo)}", mode_form)
        if res.action != "accept" or res.data.modo == "depois":
            return {"status": "postponed", "decided": 0, "pending": len(todo), "reviewer": reviewer}
        if res.data.modo == "aceitar_todas":
            accepted, todo = accept_as_proposed(project, todo, reviewer)
            decided += accepted
        for i, edit in enumerate(todo, 1):
            form, error = form_for(edit), None
            for _ in range(MAX_TRIES):
                message = describe(edit, i, len(todo))
                if error:
                    message = f"Não deu para gravar: {error}\n\n{message}"
                res = await ask(message, form)
                if res.action == "cancel":
                    stopped = True
                    break
                if res.action == "decline":
                    skipped.append(edit.id)
                    break
                error = record(project, edit, res.data.model_dump(), reviewer)
                if error is None:
                    decided.append(edit.id)
                    break
            else:
                skipped.append(edit.id)
            if stopped:
                break

    ready = [e for e in list_pending(project) if e.review and e.type in wanted]
    out: dict[str, Any] = {"reviewer": reviewer, "decided": len(decided), "skipped": skipped,
                           "stopped": stopped, "pending": len(queue(project, stage))}
    if not ready:
        return out | {"status": "decided"} | _summary(project, stage)
    acc = sum(1 for e in ready if e.review.decision == "accept")
    apply_form = _model("Aplicar", {
        "acao": _choice(APPLY, "aplicar", "Aplicar"),
        "aprovador": _text(reviewer, "Quem aprova", "Fica registrado no changelog."),
    })
    res = await ask(f"{acc} aceitas e {len(ready) - acc} rejeitadas prontas para aplicar. O validate roda antes; "
                    f"se surgir erro novo, nada muda." + (f"\n{len(skipped)} ficaram para depois." if skipped else ""),
                    apply_form)
    if res.action != "accept" or res.data.acao != "aplicar" or not res.data.aprovador.strip():
        return out | {"status": "decided", "ready_to_apply": len(ready)} | _summary(project, stage)
    try:
        result = apply_reviewed(project, res.data.aprovador.strip(), stage)
    except BatchError as exc:
        return out | {"status": "apply_failed", "error": str(exc), "new_errors": exc.new_errors} | _summary(project, stage)
    from .export import export
    export(project)
    return out | {
        "status": "applied", "approved_by": res.data.aprovador.strip(),
        "applied": len(result.get("applied") or []), "rejected": len(result.get("rejected") or []),
        "applied_types": (result.get("summary") or {}).get("applied_types") or {},
        "held_by_gate": len(result.get("held_by_gate") or []),
    } | _summary(project, stage)
