"""Canal do Claude Code: a conversa da pagina chega ao agente e a resposta volta para a pagina."""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from akme import channel, review_server
from akme.tools import chat
from akme.tools.review_round import close_round, open_round


def test_chat_log_reads_from_offset_and_skips_half_written_line(project):
    a = chat.append(project, "human", "oi", author="Ana")
    items, off = chat.read_from(project, 0)
    assert [i["id"] for i in items] == [a["id"]] and off == chat.size(project)
    with chat.chat_path(project).open("a", encoding="utf-8") as fh:
        fh.write('{"role": "agent"')  # linha sem quebra: ainda sendo escrita
    assert chat.read_from(project, off) == ([], off)
    with pytest.raises(ValueError):
        chat.append(project, "human", "   ")
    with pytest.raises(ValueError):
        chat.append(project, "intruso", "x")


def test_outgoing_maps_human_and_verdict_to_notifications(project):
    items = [chat.append(project, "human", "mapeie vendas", author="Ana"),
             chat.append(project, "agent", "ok"),
             chat.append(project, "verdict", request_id="abcde", behavior="allow")]
    msgs = [m.message.root for m in channel.outgoing(project, items)]
    assert [m.method for m in msgs] == [channel.CHANNEL_EVENT, channel.PERMISSION_VERDICT]
    assert msgs[0].params["content"] == "mapeie vendas"
    assert msgs[0].params["meta"]["author"] == "Ana" and msgs[0].params["meta"]["chat_id"] == "pagina"
    assert msgs[1].params == {"request_id": "abcde", "behavior": "allow"}


def test_round_event_only_on_waiting_to_applied(project):
    before = open_round(project)
    assert channel.round_event(before, before) is None
    after = close_round(project, {"applied": [1, 2], "rejected": [], "summary": {}}, "Ana", "page")
    ev = channel.round_event(before, after).message.root
    assert ev.params["meta"]["kind"] == "round_applied" and "Ana" in ev.params["content"]
    assert channel.round_event(None, after) is None


@pytest.fixture
def server(project):
    srv = review_server.start(project, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", project
    srv.shutdown()
    srv.server_close()


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_page_chat_routes(server):
    base, project = server
    assert _post(base + "/api/chat", {"text": ""})[0] == 400
    code, sent = _post(base + "/api/chat", {"text": "oi agente", "author": "Ana"})
    assert code == 200 and sent["role"] == "human"
    got = json.loads(urllib.request.urlopen(base + "/api/chat?offset=0&timeout=0").read())
    assert [i["text"] for i in got["items"]] == ["oi agente"]
    again = json.loads(urllib.request.urlopen(base + f"/api/chat?offset={got['offset']}&timeout=0").read())
    assert again["items"] == []
    # permissao: so responde pedido que existe, uma vez, com allow ou deny
    assert _post(base + "/api/chat/permission", {"request_id": "abcde", "behavior": "allow"})[0] == 404
    chat.append(project, "permission", "rodar testes", request_id="abcde", tool_name="Bash")
    assert _post(base + "/api/chat/permission", {"request_id": "abcde", "behavior": "talvez"})[0] == 400
    assert _post(base + "/api/chat/permission", {"request_id": "abcde", "behavior": "allow"})[0] == 200
    assert _post(base + "/api/chat/permission", {"request_id": "abcde", "behavior": "deny"})[0] == 409


def _send(proc, msg):
    proc.stdin.write((json.dumps(msg) + "\n").encode())
    proc.stdin.flush()


def _reader(proc, out):
    for line in proc.stdout:
        try:
            out.put(json.loads(line))
        except ValueError:
            pass


def _wait(out, pred, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            msg = out.get(timeout=0.5)
        except queue.Empty:
            continue
        if pred(msg):
            return msg
    raise AssertionError("mensagem esperada nao chegou")


def test_stdio_server_speaks_the_channel_protocol(project):
    """Fala JSON-RPC cru com `akme serve`, como o Claude Code faz."""
    env = os.environ | {"AKME_ROOT": str(project.root)}
    proc = subprocess.Popen([sys.executable, "-m", "akme", "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env, cwd=str(project.root))
    out: queue.Queue = queue.Queue()
    threading.Thread(target=_reader, args=(proc, out), daemon=True).start()
    try:
        _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {"elicitation": {}}, "clientInfo": {"name": "teste", "version": "0"}}})
        init = _wait(out, lambda m: m.get("id") == 1)
        assert init["result"]["capabilities"]["experimental"] == channel.CHANNEL_CAPS
        assert "reply" in init["result"]["instructions"]
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        # pagina -> agente
        chat.append(project, "human", "comece pela etapa 1", author="Ana")
        ev = _wait(out, lambda m: m.get("method") == channel.CHANNEL_EVENT)
        assert ev["params"]["content"] == "comece pela etapa 1" and ev["params"]["meta"]["author"] == "Ana"

        # com o humano na pagina, a escolha de modo nao abre formulario no terminal
        _send(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "choose_decision_mode", "arguments": {}}})
        res = _wait(out, lambda m: m.get("id") == 4 or m.get("method") == "elicitation/create")
        assert res.get("id") == 4, "abriu formulario no terminal"
        assert "ask_in_chat" in res["result"]["content"][0]["text"]

        # agente -> pagina
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "reply", "arguments": {"text": "Comecando."}}})
        _wait(out, lambda m: m.get("id") == 2)
        assert [i["text"] for i in chat.read_from(project, 0)[0] if i["role"] == "agent"] == ["Comecando."]

        # pedido de permissao -> pagina -> veredito -> Claude Code
        _send(proc, {"jsonrpc": "2.0", "method": channel.PERMISSION_REQUEST, "params": {
            "request_id": "fghij", "tool_name": "Bash", "description": "rodar pytest", "input_preview": "uv run pytest"}})
        deadline = time.monotonic() + 10
        while not any(i["role"] == "permission" for i in chat.read_from(project, 0)[0]):
            assert time.monotonic() < deadline, "pedido de permissao nao chegou ao log"
            time.sleep(0.2)
        chat.append(project, "verdict", request_id="fghij", behavior="deny")
        verdict = _wait(out, lambda m: m.get("method") == channel.PERMISSION_VERDICT)
        assert verdict["params"] == {"request_id": "fghij", "behavior": "deny"}

        # o servidor continua atendendo tools normais
        _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "stage", "arguments": {}}})
        assert "result" in _wait(out, lambda m: m.get("id") == 3)
    finally:
        proc.kill()
        proc.wait()
