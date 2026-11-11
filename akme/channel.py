"""Canal do Claude Code (channels): leva a conversa da pagina de revisao para a sessao do agente.

O servidor MCP declara `claude/channel` e, a cada mensagem que o consultor escreve na pagina,
manda `notifications/claude/channel` para a sessao; o agente responde pela tool `reply`.
Tambem avisa quando o humano aplica a rodada na pagina (o agente nao precisa ficar preso em
`wait_for_review`) e repassa os pedidos de permissao de tool (`claude/channel/permission`) para
a pagina, que devolve permitir ou negar.

A pagina e servida por outro processo (`akme review`); os dois se falam pelo log de
`akme.tools.chat`. Sem a flag de canal no Claude Code, as notificacoes sao descartadas por ele
e o servidor funciona como antes.
"""
from __future__ import annotations

from typing import Any

import anyio
from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage
from mcp.types import JSONRPCMessage, JSONRPCNotification, JSONRPCRequest

from .project import Project
from .tools import chat

CHANNEL_CAPS: dict[str, dict[str, Any]] = {"claude/channel": {}, "claude/channel/permission": {}}
CHANNEL_EVENT = "notifications/claude/channel"
PERMISSION_REQUEST = "notifications/claude/channel/permission_request"
PERMISSION_VERDICT = "notifications/claude/channel/permission"
POLL = 0.5

# vira True quando a primeira mensagem da pagina chega a sessao: dali em diante o humano esta na
# pagina e nao ve o terminal, entao formularios do harness (elicitation) nao devem ser usados
_state = {"active": False}


def is_active() -> bool:
    return _state["active"]


def _message(method: str, params: dict[str, Any]) -> SessionMessage:
    return SessionMessage(JSONRPCMessage(JSONRPCNotification(jsonrpc="2.0", method=method, params=params)))


def _round_state(project: Project) -> dict[str, Any] | None:
    from .tools.review_round import read_round
    return read_round(project)


def handle_incoming(project: Project, msg: Any) -> bool:
    """Trata o pedido de permissao do Claude Code (o SDK nao conhece esse metodo) e marca a atividade
    do agente a cada tools/call. True se consumiu a mensagem."""
    if not isinstance(msg, SessionMessage):
        return False
    root = msg.message.root
    if isinstance(root, JSONRPCRequest) and root.method == "tools/call":
        try:
            chat.mark_activity(project, str((root.params or {}).get("name") or ""))
        except OSError:
            pass  # o sinal e so visual: nunca derruba a chamada
        return False
    if not (isinstance(root, JSONRPCNotification) and root.method == PERMISSION_REQUEST):
        return False
    p = root.params or {}
    request_id = str(p.get("request_id") or "")
    if request_id:
        chat.append(project, "permission", str(p.get("description") or ""), request_id=request_id,
                    tool_name=str(p.get("tool_name") or ""), input_preview=str(p.get("input_preview") or ""))
    return True


def outgoing(project: Project, items: list[dict[str, Any]]) -> list[SessionMessage]:
    """Converte as mensagens novas do log nas notificacoes que vao para o Claude Code."""
    out: list[SessionMessage] = []
    for it in items:
        role = it.get("role")
        if role == "human":
            meta = {"chat_id": "pagina", "message_id": str(it.get("id") or "")}
            if it.get("author"):
                meta["author"] = str(it["author"])
            out.append(_message(CHANNEL_EVENT, {"content": str(it.get("text") or ""), "meta": meta}))
        elif role == "verdict" and it.get("behavior") in ("allow", "deny") and it.get("request_id"):
            out.append(_message(PERMISSION_VERDICT, {"request_id": str(it["request_id"]),
                                                     "behavior": it["behavior"]}))
    return out


def round_event(before: dict[str, Any] | None, after: dict[str, Any] | None) -> SessionMessage | None:
    """Avisa o agente quando a rodada aberta passa de waiting para applied."""
    if not (before and after) or before.get("id") != after.get("id"):
        return None
    if before.get("status") != "waiting" or after.get("status") != "applied":
        return None
    text = (f"O humano aplicou a rodada {after.get('id')} na pagina (aprovado por {after.get('approved_by')}): "
            f"{after.get('applied', 0)} aplicadas, {after.get('rejected', 0)} rejeitadas, "
            f"{after.get('held_by_gate', 0)} retidas. Vale como aprovacao: siga para o proximo passo.")
    meta = {"chat_id": "pagina", "kind": "round_applied", "round_id": str(after.get("id") or "")}
    return _message(CHANNEL_EVENT, {"content": text, "meta": meta})


async def _pump(project: Project, read_stream, forward) -> None:
    async with forward:
        async for msg in read_stream:
            if handle_incoming(project, msg):
                continue
            await forward.send(msg)


async def _watch(project: Project, write_stream) -> None:
    offset = chat.size(project)  # so o que chegar depois que a sessao abriu
    last_round = _round_state(project)
    while True:
        await anyio.sleep(POLL)
        items, offset = chat.read_from(project, offset)
        if any(i.get("role") == "human" for i in items):
            _state["active"] = True
        for m in outgoing(project, items):
            await write_stream.send(m)
        current = _round_state(project)
        ev = round_event(last_round, current)
        if ev is not None:
            await write_stream.send(ev)
        last_round = current


async def run_stdio(server, project_factory) -> None:
    """Igual ao `FastMCP.run_stdio_async`, com o canal: declara as capacidades experimentais,
    intercepta os pedidos de permissao e manda os eventos da pagina."""
    lowlevel = server._mcp_server
    options = lowlevel.create_initialization_options(experimental_capabilities=CHANNEL_CAPS)
    project = project_factory()
    try:
        # sessao nova do agente = conversa nova na pagina; o log antigo fica como historico
        chat.append(project, "event", "nova sessao do agente", kind="session_start")
    except OSError:
        pass
    async with stdio_server() as (read_stream, write_stream):
        forward, inner = anyio.create_memory_object_stream(100)
        async with anyio.create_task_group() as tg:
            tg.start_soon(_pump, project, read_stream, forward)
            tg.start_soon(_watch, project, write_stream)
            await lowlevel.run(inner, write_stream, options)
            tg.cancel_scope.cancel()
