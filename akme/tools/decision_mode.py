"""Quem decide as propostas: o humano (padrao) ou a IA, com autorizacao registrada.

No modo `auto`, o humano autoriza no inicio que a IA decida e aplique as propostas em nome dele.
A escolha fica em `ontology/decision_mode.yml` (versionado, com historico) e cada aplicacao feita
pela IA leva no changelog quem autorizou. Fora do modo `auto`, o servidor recusa revisao ou
aplicacao em nome da IA: o agente nao consegue se autoaprovar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import now_iso
from ..project import Project, read_yaml, write_yaml
from .ontology_write import EditError

MODES = ("human", "auto")
MODE_FILE = "decision_mode.yml"
# nomes que o agente usa para si; qualquer um deles conta como "a IA esta decidindo"
AI_NAMES = {"ia", "ai", "agent", "agente", "claude", "llm"}


class ModeError(EditError):
    pass


def mode_path(project: Project) -> Path:
    return project.ontology_dir / MODE_FILE


def read_mode(project: Project) -> dict[str, Any]:
    """Modo atual. Sem arquivo, o projeto esta no modo humano e a escolha ainda nao foi feita."""
    path = mode_path(project)
    data = read_yaml(path) if path.exists() else {}
    mode = data.get("mode") if data.get("mode") in MODES else "human"
    return {"mode": mode, "chosen": bool(data.get("mode")), "authorized_by": data.get("authorized_by") or "",
            "authorized_at": data.get("authorized_at") or "", "history": list(data.get("history") or [])}


def set_mode(project: Project, mode: str, authorized_by: str) -> dict[str, Any]:
    if mode not in MODES:
        raise ModeError(f"modo invalido: {mode}. Opcoes: {list(MODES)}")
    who = (authorized_by or "").strip()
    if not who or is_ai_name(who):
        raise ModeError("informe o nome da pessoa que escolhe o modo (nao pode ser a IA)")
    current = read_mode(project)
    history = current["history"]
    if current["chosen"]:
        history.append({"mode": current["mode"], "authorized_by": current["authorized_by"],
                        "authorized_at": current["authorized_at"], "until": now_iso()})
    data = {"mode": mode, "authorized_by": who, "authorized_at": now_iso(), "history": history}
    write_yaml(mode_path(project), data)
    return read_mode(project)


def is_ai_name(name: str) -> bool:
    n = (name or "").strip().lower()
    return n in AI_NAMES or n.startswith("ia (")


def ai_signature(project: Project) -> str:
    m = read_mode(project)
    return f"IA (modo automatico, autorizado por {m['authorized_by']})"


def resolve_actor(project: Project, name: str, action: str) -> str:
    """Nome que vai para review e changelog. Um nome humano passa como veio. Um nome da IA so passa no
    modo auto e vira a assinatura completa com quem autorizou; fora dele, a operacao e recusada."""
    if not is_ai_name(name):
        return name
    if read_mode(project)["mode"] != "auto":
        raise ModeError(f"{action} em nome da IA so vale no modo automatico; no modo humano quem decide e a pessoa")
    return ai_signature(project)


MODE_OPTIONS = [("human", "Eu decido cada proposta"),
                ("auto", "A IA decide tudo e eu reviso no fim (publicar no alvo continua comigo)")]
QUESTION = ("Como você quer conduzir a criação da ontologia? No modo automático a IA aceita, ajusta ou "
            "rejeita cada proposta e aplica em seu nome, com o seu nome registrado no changelog como quem autorizou.")


def mode_form():
    from pydantic import Field, create_model
    current = MODE_OPTIONS[0][0]
    return create_model("ModoDeDecisao", **{
        "modo": (str, Field(default=current, title="Quem decide",
                            json_schema_extra={"enum": [v for v, _ in MODE_OPTIONS],
                                               "enumNames": [label for _, label in MODE_OPTIONS]})),
        "nome": (str, Field(title="Seu nome", description="Fica registrado como quem escolheu o modo.")),
    })


def summary(project: Project) -> dict[str, Any]:
    m = read_mode(project)
    out = {"mode": m["mode"], "chosen": m["chosen"], "authorized_by": m["authorized_by"],
           "authorized_at": m["authorized_at"]}
    if m["mode"] == "auto":
        out["how"] = ("Decida cada pendente com review_edit usando reviewer 'IA' e aplique com apply_reviewed usando "
                      "approved_by 'IA'; o servidor grava a assinatura com quem autorizou. Publicar no alvo continua "
                      "exigindo confirmacao humana.")
    return out


async def choose(project: Project, ask, supports_forms: bool, mode: str = "", authorized_by: str = "") -> dict[str, Any]:
    """Grava o modo informado ou, sem ele, pergunta ao humano por formulario (MCP elicitation)."""
    if mode:
        set_mode(project, mode, authorized_by)
        return {"status": "set"} | summary(project)
    if not supports_forms:
        return {"status": "ask_in_chat", "question": QUESTION,
                "options": {v: label for v, label in MODE_OPTIONS},
                "hint": "Pergunte no chat e chame choose_decision_mode de novo com mode e authorized_by."}
    res = await ask(QUESTION, mode_form())
    if res.action != "accept":
        return {"status": "cancelled"} | summary(project)
    set_mode(project, res.data.modo, res.data.nome)
    return {"status": "set"} | summary(project)
