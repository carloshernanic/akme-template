"""Rodada de revisao: o vai e volta entre o agente no chat e o humano na pagina.

`open_review` abre uma rodada (`ontology/pending/round.json`, status `waiting`). Quando o humano
aplica as decisoes, pela pagina ou pelo chat, `close_round` marca `applied` com quem aprovou e o
resumo. `wait_for_review` bloqueia ate isso acontecer (ou ate o timeout), para o agente seguir
sozinho sem o humano precisar escrever "revisei" no chat.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from ..models import now_iso
from ..project import Project, write_text_atomic

ROUND_FILE = "round.json"
WAIT_DEFAULT = 540.0
WAIT_MAX = 1800.0


def round_path(project: Project) -> Path:
    return project.pending_dir / ROUND_FILE


def read_round(project: Project) -> dict[str, Any] | None:
    path = round_path(project)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write(project: Project, data: dict[str, Any]) -> None:
    write_text_atomic(round_path(project), json.dumps(data, ensure_ascii=False, indent=2))


def open_round(project: Project) -> dict[str, Any]:
    """Abre uma rodada nova, ou reaproveita a que ja esta esperando (o id continua o mesmo)."""
    from .ontology_write import list_pending

    pending = list_pending(project)
    current = read_round(project)
    if current and current.get("status") == "waiting":
        data = current
    else:
        data = {"id": "R-" + uuid.uuid4().hex[:8], "status": "waiting", "opened_at": now_iso()}
    data |= {"pending": len(pending), "undecided": sum(1 for e in pending if e.review is None)}
    _write(project, data)
    return data


def close_round(project: Project, result: dict[str, Any], approved_by: str, via: str) -> dict[str, Any] | None:
    """Marca a rodada aberta como aplicada. Sem rodada esperando, nao faz nada."""
    current = read_round(project)
    if not current or current.get("status") != "waiting":
        return None
    summary = result.get("summary") or {}
    current |= {
        "status": "applied", "applied_at": now_iso(), "approved_by": approved_by, "via": via,
        "applied": len(result.get("applied") or []), "rejected": len(result.get("rejected") or []),
        "applied_types": summary.get("applied_types") or {},
        "held_by_gate": len(result.get("held_by_gate") or []),
    }
    _write(project, current)
    return current


def wait_for_review(project: Project, round_id: str | None = None, timeout: float = WAIT_DEFAULT,
                    poll: float = 1.0) -> dict[str, Any]:
    """Espera o humano aplicar a rodada aberta. Devolve `applied` com o resumo, `nothing_pending`
    quando os pendentes acabaram sem passar pela pagina (decididos no chat), `no_round` quando nao
    ha rodada aberta, ou `waiting` no timeout (chame de novo)."""
    from .ontology_write import list_pending
    from .stage import current_stage

    timeout = max(0.0, min(float(timeout), WAIT_MAX))
    deadline = time.monotonic() + timeout
    while True:
        current = read_round(project)
        if current is None or (round_id and current.get("id") != round_id):
            return {"status": "no_round", "round": current,
                    "hint": "Chame open_review antes para abrir uma rodada de revisao."}
        if current.get("status") == "applied":
            st = current_stage(project)
            return {"status": "applied", "round": current, "pending_left": len(list_pending(project)),
                    "stage": st["label"],
                    "next_step": st["next_step"], "checklist": st["checklist"]}
        pending = list_pending(project)
        if not pending:
            # o lote apaga os pendentes antes de close_round gravar applied: espera um pouco a rodada fechar
            grace = time.monotonic() + 3.0
            while time.monotonic() < grace and (read_round(project) or {}).get("status") == "waiting":
                time.sleep(0.1)
            if (read_round(project) or {}).get("status") == "applied":
                continue
            st = current_stage(project)
            return {"status": "nothing_pending", "round": current, "stage": st["label"],
                    "next_step": st["next_step"], "checklist": st["checklist"]}
        if time.monotonic() >= deadline:
            return {"status": "waiting", "round": current, "pending": len(pending),
                    "undecided": sum(1 for e in pending if e.review is None),
                    "hint": "O humano ainda nao aplicou. Chame wait_for_review de novo com o mesmo round_id."}
        time.sleep(poll)
