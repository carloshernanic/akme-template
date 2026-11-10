"""Servidor local da pagina de revisao (`akme review`). Somente 127.0.0.1.

Rotas de leitura: /api/status, /api/stage, /api/pending, /api/requirements, /api/data, /api/sources,
/api/events, /api/round, /api/chat. Rotas de escrita: /api/review (grava a decisao no pendente), /api/propose (o revisor
cria ou altera um requisito), /api/apply (aplica em lote as decididas, com nome de quem aprova), /api/chat
(mensagem do consultor para o agente, pelo canal) e /api/chat/permission (permitir ou negar uma tool).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .models import now_iso
from .ontology import load_content
from .project import Project
from .tools import chat, ontology_read, ontology_write
from .tools.batch import BatchError
from .tools.connect import find_in_sources
from .tools.export import build_export, export
from .tools.ontology_write import EditError, apply_reviewed, propose_edit, review_edit
from .tools.requirements import cq_references, requirements_status
from .tools.review_view import present
from .tools.review_round import read_round, round_path
from .tools.stage import current_stage

PROPOSE_TYPES = {
    "add_competency_question", "update_competency_question", "remove_competency_question",
    "update_gap", "update_divergence", "add_use_case", "add_requirement",
}
CQ_TYPES_WITH_REFS = {"update_competency_question", "remove_competency_question"}
EVENTS_MAX_WAIT = 25.0
REQUEST_ID_CHARS = set("abcdefghijkmnopqrstuvwxyz")  # 5 letras, sem l (contrato do canal)


def _current(content: dict[str, Any], key: str, item_id: Any) -> dict[str, Any] | None:
    for item in content["requirements"].get(key, []):
        if item.get("id") == item_id:
            return item
    return None


def _pending_view(project: Project) -> list[dict[str, Any]]:
    content = load_content(project)
    out = []
    for edit in ontology_write.list_pending(project):
        item = edit.model_dump(mode="json")
        etype, item_id = item["type"], (item.get("payload") or {}).get("id")
        current = None
        if etype in CQ_TYPES_WITH_REFS:
            item["references"] = cq_references(project, item_id)
            current = _current(content, "competency_questions", item_id)
        elif etype == "update_gap":
            current = _current(content, "gaps", item_id)
        elif etype == "update_divergence":
            current = _current(content, "divergences", item_id)
        item["current"] = current
        item["view"] = present(edit, current)
        out.append(item)
    return out


def state_token(project: Project) -> str:
    """Assinatura do estado em disco que a pagina observa: pendentes, conteudo, schema, validate."""
    h = hashlib.sha1()
    paths: list[Path] = [project.content_path, project.schema_path, project.changelog_path,
                         project.validation_path, project.questions_path, round_path(project)]
    if project.pending_dir.exists():
        paths += sorted(project.pending_dir.glob("*.yml"))
    for p in paths:
        try:
            st = p.stat()
            h.update(f"{p.name}:{st.st_mtime_ns}:{st.st_size};".encode())
        except OSError:
            h.update(f"{p.name}:-;".encode())
    return h.hexdigest()[:16]


class _HttpError(Exception):
    def __init__(self, code: int, message: str, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra or {}


def make_handler(project: Project):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(project.docs_dir), **kwargs)

        def log_message(self, format, *args):  # noqa: A002
            if os.environ.get("AKME_REVIEW_LOG") == "1":
                super().log_message(format, *args)

        def _json(self, code: int, data: Any) -> None:
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length < 0 or length > 1_000_000:
                    raise _HttpError(400, "Content-Length invalido")
                data = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, UnicodeDecodeError):
                raise _HttpError(400, "corpo JSON invalido")
            if not isinstance(data, dict):
                raise _HttpError(400, "corpo deve ser um objeto JSON")
            return data

        def _allowed_hosts(self) -> set[str]:
            port = self.server.server_address[1]
            return {f"127.0.0.1:{port}", f"localhost:{port}"}

        def _host_ok(self) -> bool:
            if self.headers.get("Host") not in self._allowed_hosts():
                self._json(403, {"error": "host nao permitido"})
                return False
            return True

        def _static_ok(self) -> bool:
            raw = urlparse(self.path).path
            if ".." in raw.replace("\\", "/").split("/"):
                self._json(403, {"error": "caminho recusado"})
                return False
            return True

        def list_directory(self, path):  # noqa: ARG002 - nunca lista diretorios
            self._json(404, {"error": "rota nao encontrada"})
            return None

        def end_headers(self):
            # a pagina e o JS mudam a cada export; nunca servir do cache do navegador
            if not urlparse(self.path).path.startswith("/api/"):
                self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def do_GET(self):  # noqa: N802
            try:
                self._get()
            except Exception as exc:  # noqa: BLE001 - responde JSON em vez de derrubar a conexao
                self._json(500, {"error": str(exc)})

        def _get(self):
            url = urlparse(self.path)
            if not self._host_ok():
                return
            try:
                if url.path == "/api/status":
                    return self._json(200, requirements_status(project) | {"token": state_token(project)})
                if url.path == "/api/stage":
                    return self._json(200, current_stage(project))
                if url.path == "/api/round":
                    return self._json(200, read_round(project) or {})
                if url.path == "/api/pending":
                    return self._json(200, _pending_view(project))
                if url.path == "/api/requirements":
                    return self._json(200, ontology_read.get_requirements(project))
                if url.path == "/api/data":
                    data = build_export(project)
                    data["pending"] = _pending_view(project)
                    data["stage"] = current_stage(project)
                    data["round"] = read_round(project) or {}
                    data["token"] = state_token(project)
                    return self._json(200, data)
                if url.path == "/api/events":
                    return self._json(200, self._events(parse_qs(url.query)))
                if url.path == "/api/chat":
                    return self._json(200, self._chat_poll(parse_qs(url.query)))
                if url.path == "/api/sources":
                    q = parse_qs(url.query)
                    query = (q.get("q") or [""])[0]
                    cs = (q.get("case_sensitive") or ["false"])[0].lower() in ("1", "true", "yes")
                    return self._json(200, find_in_sources(project, query, case_sensitive=cs))
                if url.path.startswith("/api/"):
                    return self._json(404, {"error": "rota nao encontrada"})
            except (EditError, ValueError) as exc:
                return self._json(400, {"error": str(exc)})
            if not self._static_ok():
                return
            if url.path in ("", "/") and not (project.docs_dir / "index.html").is_file():
                body = ("<!doctype html><meta charset=utf-8><title>akme review</title>"
                        "<p>docs/index.html ainda nao existe; rode <code>akme export</code>.</p>").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def _events(self, q: dict[str, list[str]]) -> dict[str, Any]:
            """Long-polling: devolve quando o estado em disco muda em relacao a `since` ou no timeout."""
            since = (q.get("since") or [""])[0]
            try:
                wait = min(float((q.get("timeout") or [str(EVENTS_MAX_WAIT)])[0]), EVENTS_MAX_WAIT)
            except ValueError:
                wait = EVENTS_MAX_WAIT
            deadline = time.monotonic() + max(wait, 0.0)
            token = state_token(project)
            while since and token == since and time.monotonic() < deadline:
                time.sleep(0.5)
                token = state_token(project)
            return {"token": token, "changed": bool(since) and token != since}

        def _chat_poll(self, q: dict[str, list[str]]) -> dict[str, Any]:
            """Long-polling do chat: devolve as mensagens depois do byte `offset` (ou espera ate o timeout)."""
            try:
                offset = max(int((q.get("offset") or ["0"])[0]), 0)
                wait = min(float((q.get("timeout") or ["0"])[0]), EVENTS_MAX_WAIT)
            except ValueError:
                raise ValueError("offset e timeout devem ser numeros")
            deadline = time.monotonic() + max(wait, 0.0)
            items, new_offset = chat.read_from(project, offset)
            while not items and time.monotonic() < deadline:
                time.sleep(0.3)
                items, new_offset = chat.read_from(project, offset)
            return {"items": items, "offset": new_offset}

        def _chat_send(self, body: dict[str, Any]) -> dict[str, Any]:
            author = str(body.get("author") or "").strip()[:80]
            return chat.append(project, "human", str(body.get("text") or ""), author=author)

        def _chat_permission(self, body: dict[str, Any]) -> dict[str, Any]:
            request_id, behavior = str(body.get("request_id") or ""), body.get("behavior")
            if behavior not in ("allow", "deny"):
                raise _HttpError(400, "behavior deve ser allow ou deny")
            if len(request_id) != 5 or not set(request_id) <= REQUEST_ID_CHARS:
                raise _HttpError(400, "request_id invalido")
            items, _ = chat.read_from(project, 0)
            if not any(i.get("role") == "permission" and i.get("request_id") == request_id for i in items):
                raise _HttpError(404, "pedido de permissao nao encontrado")
            if any(i.get("role") == "verdict" and i.get("request_id") == request_id for i in items):
                raise _HttpError(409, "pedido de permissao ja respondido")
            author = str(body.get("author") or "").strip()[:80]
            return chat.append(project, "verdict", "", request_id=request_id, behavior=behavior, author=author)

        def do_HEAD(self):  # noqa: N802
            if self._host_ok() and self._static_ok():
                super().do_HEAD()

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            if not self._host_ok():
                return
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {f"http://{h}" for h in self._allowed_hosts()}:
                return self._json(403, {"error": "origin nao permitido"})
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._json(400, {"error": "Content-Type deve ser application/json"})
            try:
                if path == "/api/review":
                    return self._json(200, self._review(self._body()))
                if path == "/api/propose":
                    return self._json(200, self._propose(self._body()))
                if path == "/api/apply":
                    return self._json(200, self._apply(self._body()))
                if path == "/api/chat":
                    return self._json(200, self._chat_send(self._body()))
                if path == "/api/chat/permission":
                    return self._json(200, self._chat_permission(self._body()))
                return self._json(404, {"error": "rota nao encontrada"})
            except _HttpError as exc:
                return self._json(exc.code, {"error": exc.message} | exc.extra)
            except BatchError as exc:
                return self._json(409, {"error": str(exc), "new_errors": exc.new_errors})
            except EditError as exc:
                code = 404 if "nao encontrada" in str(exc) else 400
                return self._json(code, {"error": str(exc)})
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001 - responde JSON em vez de derrubar a conexao
                return self._json(500, {"error": str(exc)})

        def _review(self, body: dict[str, Any]) -> dict[str, Any]:
            edits = body.get("edits")
            if edits is not None and not isinstance(edits, dict):
                raise _HttpError(400, "edits deve ser um objeto")
            edit = review_edit(
                project, str(body.get("edit_id", "")), str(body.get("decision", "")),
                str(body.get("reviewer") or ""), edits=edits or None,
                reason=str(body.get("reason") or ""),
            )
            return edit.model_dump(mode="json") | {"view": present(edit)}

        def _propose(self, body: dict[str, Any]) -> dict[str, Any]:
            etype, reviewer = body.get("type"), str(body.get("reviewer") or "").strip()
            if etype not in PROPOSE_TYPES:
                raise _HttpError(400, f"tipo nao permitido: {etype}")
            if not reviewer:
                raise _HttpError(400, "reviewer obrigatorio")
            payload = body.get("payload")
            if not isinstance(payload, dict):
                raise _HttpError(400, "payload deve ser um objeto")
            payload = dict(payload)
            if etype == "add_competency_question" and not payload.get("evidence"):
                payload["evidence"] = [{"kind": "conversation", "who": reviewer, "when": now_iso(),
                                        "note": "criada na pagina de revisao"}]
            edit = propose_edit(project, etype, payload, proposed_by=reviewer)
            try:
                return review_edit(project, edit.id, "accept", reviewer).model_dump(mode="json")
            except EditError:
                (project.pending_dir / f"{edit.id}.yml").unlink(missing_ok=True)
                raise

        def _apply(self, body: dict[str, Any]) -> dict[str, Any]:
            """Aplica em lote as decididas. O nome de quem aprova e obrigatorio e fica no changelog."""
            approved_by = str(body.get("approved_by") or "").strip()
            if not approved_by:
                raise _HttpError(400, "approved_by obrigatorio")
            stage = str(body.get("stage") or "all")
            out = apply_reviewed(project, approved_by, stage, via="page")
            export(project)
            out["stage_after"] = current_stage(project)
            return out

    return Handler


def start(project: Project, port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(project))


def url_for(port: int) -> str:
    return f"http://127.0.0.1:{port}/"


def is_running(port: int, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url_for(port) + "api/status", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def ensure_running(project: Project, port: int = 8765, open_browser: bool = False, wait: float = 15.0) -> str:
    """Garante um `akme review` servindo em `port` (reaproveita o que ja estiver no ar) e devolve a URL.
    O processo novo e desacoplado do chamador, para o agente poder subir a pagina e seguir."""
    url = url_for(port)
    if not is_running(port):
        kwargs: dict[str, Any] = {"cwd": str(project.root), "stdin": subprocess.DEVNULL,
                                  "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, "-m", "akme", "review", "--no-open", "--port", str(port)], **kwargs)
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline and not is_running(port, 0.5):
            time.sleep(0.25)
        if not is_running(port, 0.5):
            raise RuntimeError(f"akme review nao respondeu em {url} depois de {wait:.0f}s")
    if open_browser:
        webbrowser.open(url)
    return url


def serve(project: Project, port: int = 8765, open_browser: bool = True) -> None:
    server = start(project, port)
    url = url_for(server.server_address[1])
    print(f"akme review em {url} (Ctrl+C para sair)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
