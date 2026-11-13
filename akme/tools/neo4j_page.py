"""Tela "Exportar" da pagina local: o estado da exportacao para o Neo4j e a carga pelo botao.

Mesmo caminho da CLI (`akme publish --target neo4j --no-dry-run`), com as mesmas recusas: plano com problema, banco
de outro projeto, remocao grande sem o numero digitado. A carga so parte de um POST da pagina, com a confirmacao do
humano; o agente nao tem tool para ela. Nenhuma credencial sai daqui: da senha, so se esta preenchida.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from dotenv import dotenv_values

from ..project import Project
from . import neo4j_load
from .neo4j_guide import GUIDE_FILE, GUIDE_ROUTE, QUERIES_FILE, STYLE_FILE, linked_labels
from .neo4j_plan import build_plan
from .publish import PublishError, publish

ENV_VARS = ("AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD")
BROWSER_VAR = "AKME_NEO4J_BROWSER_URL"
CLI_COMMAND = "uv run akme publish --target neo4j --no-dry-run"
IMAGE = "neo4j:2026.10.1"
CONTAINER = "akme-neo4j"
DEFAULT_BOLT, DEFAULT_HTTP = 7687, 7474
MIN_PASSWORD = 8  # o Neo4j recusa senha menor e o conteiner morre ao subir
_LOAD = threading.Lock()  # uma carga por vez neste servidor
_STATUS = threading.Lock()  # uma conferencia por vez: ela le as fontes e regrava docs/publish
# a senha tambem e lida pelo shell no comando do Docker (`. ./.env`), que interpreta $, espaco, aspas, #, & e !
# de outro jeito que o akme: com esses caracteres o banco nasceria com uma senha diferente da do .env
SAFE_PASSWORD = re.compile(r"[A-Za-z0-9_.@%+=:,/-]+")


class LoadRefused(Exception):
    """A carga foi recusada ou falhou. `code` e o status HTTP. Sem `started` em `extra`, nada foi gravado; com
    `started`, a gravacao ja tinha comecado e o banco pode ter mudado (a mensagem diz o que aconteceu)."""

    def __init__(self, message: str, code: int = 409, **extra: Any) -> None:
        super().__init__(message)
        self.code, self.extra = code, extra


_FROM_FILE: set[str] = set()  # variaveis do Neo4j que vieram do .env: se a linha sair do arquivo, saem do processo


def reload_env(project: Project) -> None:
    """Le do .env as variaveis do Neo4j de novo: o humano preenche (ou apaga) o arquivo com a pagina aberta e so
    clica em conferir. Linha apagada do arquivo deixa de valer; variavel que veio do terminal nao e mexida."""
    path = project.root / ".env"
    values = dotenv_values(path) if path.exists() else {}
    for var in (*ENV_VARS, BROWSER_VAR):
        if values.get(var) is not None:
            os.environ[var] = values[var]
            _FROM_FILE.add(var)
        elif var in _FROM_FILE:
            os.environ.pop(var, None)
            _FROM_FILE.discard(var)


def _port(url: str, default: int) -> int:
    try:
        return urlsplit(url).port or default
    except ValueError:
        return default


def env_state() -> dict[str, Any]:
    """O que o .env tem. Da senha so se esta preenchida; do endereco, sem credencial embutida."""
    filled = {var: bool(os.environ.get(var, "").strip()) for var in ENV_VARS}
    missing = [var for var, ok in filled.items() if not ok]
    password = os.environ.get("AKME_NEO4J_PASSWORD", "")
    out: dict[str, Any] = {"filled": filled, "missing": missing,
                           "browser_url_set": bool(os.environ.get(BROWSER_VAR, "").strip()),
                           # so o veredito: a senha nunca sai daqui. Placeholder do exemplo tambem nao serve
                           "password_short": bool(password.strip()) and len(password) < MIN_PASSWORD,
                           "password_placeholder": password.strip().startswith("<"),
                           "password_chars": bool(password.strip()) and not password.strip().startswith("<")
                           and not SAFE_PASSWORD.fullmatch(password)}
    if filled["AKME_NEO4J_URI"]:  # direto da variavel: destination() exige as tres preenchidas
        parts = urlsplit(os.environ["AKME_NEO4J_URI"].strip())
        try:
            port = f":{parts.port}" if parts.port else ""
        except ValueError:
            port = ""
        out["destination"] = f"{parts.scheme}://{parts.hostname}{port}"
    return out


def setup_lines(review_port: int) -> dict[str, Any]:
    """Linhas do .env e o `docker run` que cria um Neo4j local com as portas do .env (ou as padrao) e o guia abrindo
    sozinho a cada conexao. A senha nunca aparece: o comando a le do .env no terminal do humano."""
    uri = os.environ.get("AKME_NEO4J_URI", "").strip()
    bolt = _port(uri, DEFAULT_BOLT) if uri else DEFAULT_BOLT
    browser = os.environ.get(BROWSER_VAR, "").strip()
    http = _port(browser, DEFAULT_HTTP) if browser else (DEFAULT_HTTP if bolt == DEFAULT_BOLT else bolt - 213)
    if not 0 < http < 65536:
        http = DEFAULT_HTTP
    env = [f"AKME_NEO4J_URI=bolt://127.0.0.1:{bolt}", "AKME_NEO4J_USER=neo4j",
           "AKME_NEO4J_PASSWORD=<invente uma senha de 8 caracteres ou mais>",
           f"{BROWSER_VAR}=http://localhost:{http}"]
    docker = ["set -a; . ./.env; set +a",
              f'NEO4J_AUTH="neo4j/$AKME_NEO4J_PASSWORD" docker run -d --name {CONTAINER} \\',
              f"  --publish=127.0.0.1:{http}:7474 --publish=127.0.0.1:{bolt}:7687 \\",
              f"  --env NEO4J_AUTH --volume={CONTAINER}-data:/data \\",
              f"  --env NEO4J_browser_post__connect__cmd='guide http://127.0.0.1:{review_port}{GUIDE_ROUTE}' \\",
              f"  {IMAGE}"]
    return {"env": env, "docker": docker, "http_port": http, "bolt_port": bolt}


def _docker(*args: str) -> str | None:
    """Saida de um comando docker de leitura; None se o docker nao existe, nao responde ou o comando falha."""
    try:
        done = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=4, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout + done.stderr if done.returncode == 0 else None


def container_state() -> dict[str, Any]:
    """O conteiner que o comando da tela cria (akme-neo4j): existe? esta rodando? Se parou, por que. Somente
    leitura, e so quando a conexao falha. Do log, so reconhece a recusa de senha curta; nenhum trecho dele sai."""
    if _docker("version", "--format", "{{.Server.Version}}") is None:
        return {"docker": False, "name": CONTAINER, "exists": False, "status": None, "reason": None}
    status = _docker("inspect", "--format", "{{.State.Status}}", CONTAINER)
    if status is None:
        return {"docker": True, "name": CONTAINER, "exists": False, "status": None, "reason": None}
    status = status.strip()
    reason = None
    if status != "running":
        log = _docker("logs", "--tail", "40", CONTAINER) or ""
        if "minimum password length" in log or "at least 8 characters" in log:
            reason = "senha_curta"
    return {"docker": True, "name": CONTAINER, "exists": True, "status": status, "reason": reason}


def browser_answers(url: str, timeout: float = 1.5) -> bool:
    """O Neo4j Browser responde nesse endereco? So enderecos da propria maquina sao testados."""
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost"):
        return True  # console da Aura ou outro host: nao testado, nao acusado
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _safe(project: Project, exc: BaseException) -> str:
    return neo4j_load._safe(exc, neo4j_load._adapter_secrets(project))


def _plan_view(plan: Any, preview: dict[str, Any]) -> dict[str, Any]:
    linked = linked_labels(plan)
    return {
        "project": plan.project,
        "nodes": [{"label": label, "rows": n, "linked": label in linked} for label, n in preview["nodes"].items()],
        "relationships": [{"relation": r, "rows": n} for r, n in preview["relationships"].items()],
        "total_nodes": sum(preview["nodes"].values()), "total_relationships": sum(preview["relationships"].values()),
        "warnings": neo4j_load.warning_lines(preview["sources_skipped"], preview["relations_not_published"],
                                             preview["warnings"]),
        "problems": list(preview["problems"]),
        "concepts_without_data": list(plan.concepts_without_data),
    }


def _database_view(project: Project, plan: Any, preview: dict[str, Any]) -> dict[str, Any]:
    """Conecta e compara banco e origem. Somente leitura."""
    try:
        state = neo4j_load.destination_state(project, plan)
    except (RuntimeError, PublishError) as exc:
        return {"connected": False, "error": _safe(project, exc)}
    except Exception as exc:  # noqa: BLE001 - driver, rede: mensagem curta, sem credencial
        return {"connected": False, "error": f"{type(exc).__name__}: {_safe(project, exc)}"}
    described, refusal = neo4j_load.check_destination(state, project.name)
    nodes = neo4j_load._by_label(preview, state)
    edges = neo4j_load._by_type(preview, state)
    return {
        "connected": True, "described": described, "refusal": refusal,
        "has_project": state["projetos"] == [project.name],
        "nodes": {label: {"now": now, "then": then} for label, (now, then) in nodes.items()},
        "relationships": {t: {"now": now, "then": then} for t, (now, then) in edges.items()},
        "removed_nodes": sum(now - then for now, then in nodes.values() if now > then),
        "removed_relationships": sum(now - then for now, then in edges.values() if now > then),
        "large_removal": neo4j_load.large_removal(preview, state),
    }


def fingerprint(preview: dict[str, Any], database: dict[str, Any] | None) -> str:
    """Marca do que o humano viu na tela: destino, projeto, contagens da origem e do banco. A carga so roda se a
    marca enviada pela pagina for a do plano e do banco de agora; mudou qualquer coisa, a pessoa confere de novo."""
    seen = {"destino": os.environ.get("AKME_NEO4J_URI", ""), "nos": preview["nodes"],
            "arestas": preview["relationships"], "problemas": preview["problems"],
            "banco": {k: (database or {}).get(k) for k in ("described", "refusal", "nodes", "relationships")}}
    return hashlib.sha256(json.dumps(seen, sort_keys=True, default=str).encode()).hexdigest()[:24]


def _rewrite_guide(project: Project, plan: Any) -> None:
    """O dry-run da conferencia regrava o guia na forma generica; com o banco no ar, volta a forma que este banco
    aceita (com ou sem APOC), a mesma que a carga deixa. Melhor esforco: falha aqui nao derruba a tela."""
    try:
        out = project.docs_dir / "publish"
        neo4j_load._write_guide(plan, out / GUIDE_FILE, out / QUERIES_FILE, neo4j_load.has_apoc())
    except Exception:  # noqa: BLE001
        pass


def _viewing(review_port: int) -> dict[str, Any]:
    url = neo4j_load.browser_url()
    return {"browser_url": url, "browser_answers": browser_answers(url),
            "guide_command": f":guide http://127.0.0.1:{review_port}{GUIDE_ROUTE}",
            "user": os.environ.get("AKME_NEO4J_USER", ""),
            "files": {"guide": f"docs/publish/{GUIDE_FILE}", "style": f"docs/publish/{STYLE_FILE}",
                      "queries": f"docs/publish/{QUERIES_FILE}"}}


def export_status(project: Project, review_port: int) -> dict[str, Any]:
    """Tudo o que a tela mostra antes da carga: .env, plano (o mesmo do dry-run, que regrava docs/publish), banco.
    Uma por vez, e nunca durante uma carga (as duas escrevem em docs/publish)."""
    if _LOAD.locked():
        raise LoadRefused("ha uma carga em andamento; confira de novo quando ela terminar")
    with _STATUS:
        return _export_status(project, review_port)


def _export_status(project: Project, review_port: int) -> dict[str, Any]:
    reload_env(project)
    env = env_state()
    out: dict[str, Any] = {"env": env, "setup": setup_lines(review_port), "cli": CLI_COMMAND,
                           "plan": None, "database": None, "viewing": None}
    try:
        plan = build_plan(project)
        preview = publish(project, "neo4j", True, None, plan)
    except Exception as exc:  # noqa: BLE001 - ontologia incompleta, fonte ilegivel: a tela mostra o motivo
        out["plan_error"] = _safe(project, exc)
        return out
    out["plan"] = _plan_view(plan, preview)
    if env["missing"] or env["password_short"] or env["password_placeholder"] or env["password_chars"]:
        return out
    out["database"] = _database_view(project, plan, preview)
    out["token"] = fingerprint(preview, out["database"])
    if not out["database"]["connected"]:  # primeira vez, banco parado, senha recusada: a tela diz qual
        error = out["database"]["error"].lower()
        out["database"]["kind"] = ("senha" if "authentication" in error or "unauthorized" in error
                                   else "desligado" if "refused" in error or "couldn't connect" in error
                                   or "unable to retrieve routing" in error else "outro")
        out["container"] = container_state()
        return out
    if out["database"]["has_project"]:
        _rewrite_guide(project, plan)
    out["viewing"] = _viewing(review_port)
    return out


def export_load(project: Project, review_port: int, confirmed: bool, removed: Any = None,
                token: Any = None) -> dict[str, Any]:
    """A carga pelo botao. `confirmed`: o humano marcou que entendeu; `removed`: o numero digitado quando a
    sincronizacao apaga mais de LARGE_REMOVAL de algum label; `token`: a marca da previa que a pagina mostrou
    (fingerprint). Recusa sem gravar em qualquer divergencia, inclusive se a previa ja nao e a de agora."""
    if confirmed is not True:
        raise LoadRefused("confirme a carga na pagina antes de executar", 400)
    if not _LOAD.acquire(blocking=False):
        raise LoadRefused("ja existe uma carga em andamento; espere ela terminar")
    try:
        reload_env(project)
        missing = env_state()["missing"]
        if missing:
            raise LoadRefused("falta preencher no .env: " + ", ".join(missing), 400)
        try:
            plan = build_plan(project)
            preview = publish(project, "neo4j", True, None, plan)
            if preview["problems"]:
                raise LoadRefused("o plano tem problemas; nada foi gravado", problems=list(preview["problems"]))
            database = _database_view(project, plan, preview)
            if not database["connected"]:
                raise LoadRefused(database["error"], 502)
            if not token or token != fingerprint(preview, database):
                raise LoadRefused("a origem, o banco ou o .env mudaram depois que esta previa foi montada; clique em "
                                  "Conferir de novo e veja a previa atual antes de carregar. Nada foi gravado",
                                  stale=True)
            state = neo4j_load.destination_state(project, plan)
            _, refusal = neo4j_load.check_destination(state, project.name)
            if refusal:
                raise LoadRefused(f"{refusal}. Nada foi gravado")
            expected = neo4j_load.large_removal(preview, state)
            if expected and str(removed if removed is not None else "").strip() != str(expected):
                raise LoadRefused(f"a carga apaga mais de {neo4j_load.LARGE_REMOVAL:.0%} de alguma classe; para "
                                  f"confirmar, digite {expected}. Nada foi gravado", large_removal=expected)
        except LoadRefused:
            raise
        except (RuntimeError, PublishError) as exc:
            raise LoadRefused(_safe(project, exc), 502) from None
        except Exception as exc:  # noqa: BLE001 - CSV em outra codificacao, driver: curto, sem credencial
            raise LoadRefused(f"{type(exc).__name__}: {_safe(project, exc)}", 500) from None
        # daqui em diante a gravacao pode ter comecado: nenhuma falha pode dizer "nada foi gravado"
        try:
            result = publish(project, "neo4j", False, None, plan)
        except (RuntimeError, PublishError) as exc:
            raise LoadRefused(_safe(project, exc), 502, started=True) from None
        except Exception as exc:  # noqa: BLE001
            raise LoadRefused(f"{type(exc).__name__}: {_safe(project, exc)}", 500, started=True) from None
        if result.get("problems"):
            raise LoadRefused("o plano tem problemas; nada foi gravado", problems=list(result["problems"]))
        return {"loaded": True, "nodes": result["nodes"], "relationships": result["relationships"],
                "total_nodes": sum(result["nodes"].values()),
                "total_relationships": sum(result["relationships"].values()),
                "removed": result.get("removed"), "verification": result.get("verification"),
                "viewing": _viewing(review_port)}
    finally:
        _LOAD.release()
