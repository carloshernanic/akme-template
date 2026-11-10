"""Conversa entre a pagina de revisao e o agente, pelo canal do Claude Code (channels).

A pagina e o servidor MCP rodam em processos diferentes; os dois se falam por um log em
`ontology/pending/chat.jsonl`, uma mensagem por linha. Papeis:
- `human`: o consultor escreveu na pagina; o servidor MCP repassa ao agente como evento do canal
- `agent`: resposta do agente, gravada pela tool `reply`
- `event`: aviso do sistema ao agente (ex.: rodada aplicada na pagina)
- `permission`: o Claude Code pede permissao para uma tool; a pagina mostra permitir ou negar
- `verdict`: a resposta do consultor a um `permission`; o servidor MCP devolve ao Claude Code
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from ..models import now_iso
from ..project import Project

CHAT_FILE = "chat.jsonl"
ACTIVITY_FILE = "activity.json"
ROLES = {"human", "agent", "event", "permission", "verdict"}
MAX_TEXT = 20_000
_lock = threading.Lock()


def chat_path(project: Project) -> Path:
    return project.pending_dir / CHAT_FILE


def append(project: Project, role: str, text: str = "", **extra: Any) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"papel invalido: {role}")
    text = str(text or "").strip()
    if role in ("human", "agent") and not text:
        raise ValueError("mensagem vazia")
    if len(text) > MAX_TEXT:
        raise ValueError(f"mensagem com mais de {MAX_TEXT} caracteres")
    entry = {"id": uuid.uuid4().hex[:12], "role": role, "text": text, "at": now_iso()} | extra
    path = chat_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _lock, path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return entry


def read_from(project: Project, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    """Le as mensagens a partir do byte `offset`. Devolve as mensagens e o offset novo.
    Uma linha ainda sem quebra de linha (escrita pela metade) fica para a proxima leitura."""
    path = chat_path(project)
    try:
        size = path.stat().st_size
    except OSError:
        return [], 0
    if offset > size:  # log apagado ou truncado: recomeca
        offset = 0
    with path.open("rb") as fh:
        fh.seek(offset)
        raw = fh.read()
    end = raw.rfind(b"\n") + 1
    out: list[dict[str, Any]] = []
    for line in raw[:end].splitlines():
        try:
            item = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(item, dict):
            out.append(item)
    return out, offset + end


def size(project: Project) -> int:
    try:
        return chat_path(project).stat().st_size
    except OSError:
        return 0


def activity_path(project: Project) -> Path:
    return project.pending_dir / ACTIVITY_FILE


def mark_activity(project: Project, tool: str) -> None:
    """O agente chamou uma tool do akme: a pagina mostra que ele esta trabalhando."""
    path = activity_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"tool": str(tool)[:80], "at": now_iso()}), encoding="utf-8")
    tmp.replace(path)


def read_activity(project: Project) -> dict[str, Any]:
    try:
        data = json.loads(activity_path(project).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
