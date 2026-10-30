"""Servidor local da pagina de revisao (`akme review`). Somente 127.0.0.1."""
from __future__ import annotations

import json
import os
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .models import now_iso
from .ontology import load_content
from .project import Project
from .tools import ontology_read, ontology_write
from .tools.connect import find_in_sources
from .tools.ontology_write import EditError, propose_edit, review_edit
from .tools.requirements import cq_references, requirements_status

PROPOSE_TYPES = {
    "add_competency_question", "update_competency_question", "remove_competency_question",
    "update_gap", "update_divergence", "add_use_case", "add_requirement",
}
CQ_TYPES_WITH_REFS = {"update_competency_question", "remove_competency_question"}


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
        if etype in CQ_TYPES_WITH_REFS:
            item["references"] = cq_references(project, item_id)
            item["current"] = _current(content, "competency_questions", item_id)
        elif etype == "update_gap":
            item["current"] = _current(content, "gaps", item_id)
        elif etype == "update_divergence":
            item["current"] = _current(content, "divergences", item_id)
        out.append(item)
    return out


class _HttpError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def make_handler(project: Project):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(project.docs_dir), **kwargs)

        def log_message(self, format, *args):  # noqa: A002
            if os.environ.get("AKME_REVIEW_LOG") == "1":
                super().log_message(format, *args)

        def _json(self, code: int, data: Any) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
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
                    return self._json(200, requirements_status(project))
                if url.path == "/api/pending":
                    return self._json(200, _pending_view(project))
                if url.path == "/api/requirements":
                    return self._json(200, ontology_read.get_requirements(project))
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
                return self._json(404, {"error": "rota nao encontrada"})
            except _HttpError as exc:
                return self._json(exc.code, {"error": exc.message})
            except EditError as exc:
                code = 404 if "nao encontrada" in str(exc) else 400
                return self._json(code, {"error": str(exc)})
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
            return edit.model_dump(mode="json")

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

    return Handler


def start(project: Project, port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(project))


def serve(project: Project, port: int = 8765, open_browser: bool = True) -> None:
    server = start(project, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"akme review em {url} (Ctrl+C para sair)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
