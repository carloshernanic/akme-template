"""Carga no Neo4j em Cypher puro, sem plugin: nos, arestas, camada Conceito, sincronizacao e conferencia.

A ordem, numa so sessao: confere o destino; cria restricoes e indices; marca o projeto; grava os nos fonte a fonte,
em blocos; grava as arestas, resolvidas pelo banco pela coluna do join; grava a ontologia; e so entao apaga deste
projeto o que nao veio nesta carga. Dados vao sempre como parametro; so identificadores entram no texto, por name().
Credenciais vem do ambiente e nunca aparecem numa mensagem de erro.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from urllib.parse import urlsplit

from ..adapters import load_adapter
from ..adapters.base import require
from ..ontology import classes, load_content, load_graph
from ..project import Project
from .neo4j_onto import ontology_statements, render
from .neo4j_plan import EdgePlan, Plan, build_plan
from .neo4j_values import convert, filled, name, node_id
from .publish import PublishError

BATCH = 5000
MARKER = "_AkmeProjeto"
LEGACY_LABELS = ("Resource", "_GraphConfig")
LEGACY_CONSTRAINT = "n10s_unique_uri"
CONCEITO = "Conceito"

# Labels e propriedades como texto: num banco vazio eles ainda nao existem, e o servidor avisaria a cada consulta.
STATE_QUERY = (
    f"RETURN COLLECT {{ MATCH (m) WHERE '{MARKER}' IN labels(m) RETURN m[$prop] }} AS projetos, "
    "COUNT { MATCH (n) } AS total, "
    f"COUNT {{ MATCH (n) WHERE n['_projeto'] IS NULL AND NOT '{MARKER}' IN labels(n) }} AS alheios, "
    # legado: no do n10s (sem _projeto), para uma classe do cliente chamada Resource nao ser confundida com ele
    "EXISTS { MATCH (n) WHERE n['_projeto'] IS NULL AND ("
    + " OR ".join(f"'{label}' IN labels(n)" for label in LEGACY_LABELS) + ") } AS legado")
LEGACY_QUERY = f"SHOW CONSTRAINTS YIELD name WHERE name = '{LEGACY_CONSTRAINT}' RETURN count(*) AS c"
IN_DB_QUERY = (f"MATCH (n) WHERE n['_projeto'] = $projeto UNWIND labels(n) AS label WITH label WHERE label <> '{CONCEITO}' "
               "RETURN label, count(*) AS c")

# Sincronizacao: so nos e arestas deste projeto (_projeto) com _carga diferente da atual. A marca _AkmeProjeto tem
# `projeto`, nao `_projeto`, e fica. IN TRANSACTIONS exige transacao implicita: session.run, nunca execute_write.
SYNC_NODES = ("MATCH (n) WHERE n['_projeto'] = $projeto AND coalesce(n['_carga'], '') <> $carga "
              f"CALL (n) {{ DETACH DELETE n }} IN TRANSACTIONS OF {BATCH} ROWS")
SYNC_EDGES = ("MATCH (n)-[r]->() WHERE n['_projeto'] = $projeto AND coalesce(r['_carga'], '') <> $carga "
              f"CALL (r) {{ DELETE r }} IN TRANSACTIONS OF {BATCH} ROWS")


# --- conexao ---------------------------------------------------------------------------------------------------

def _connection() -> tuple[str, str, str]:
    values = {var: os.environ.get(var) for var in ("AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD")}
    missing = [var for var, value in values.items() if not value]
    if missing:
        raise RuntimeError("publish neo4j --no-dry-run exige " + ", ".join(missing))
    return values["AKME_NEO4J_URI"], values["AKME_NEO4J_USER"], values["AKME_NEO4J_PASSWORD"]


_SECRET_KEY = re.compile(r"password|senha|secret|token|dsn|uri|url|key", re.I)


def _adapter_secrets(project: Project) -> list[str]:
    """Valores do adapter que podem ser credencial: os vindos de env: e os de chave com cara de segredo."""
    raw = project.config.get(project.adapter_name, {}) or {}
    return [str(v) for k, v in project.adapter_options().items()
            if isinstance(v, str) and v and (str(raw.get(k, "")).startswith("env:") or _SECRET_KEY.search(k))]


def _safe(error: Any, extra: list[str] | tuple[str, ...] = ()) -> str:
    """Texto do erro sem a senha nem a URI do Neo4j (que pode trazer usuario e senha embutidos) nem os segredos do
    adapter. Os mais longos primeiro, para um segredo que contem outro ser trocado inteiro."""
    text = " ".join(str(error).split())
    secrets = [os.environ.get(var) or "" for var in ("AKME_NEO4J_PASSWORD", "AKME_NEO4J_URI")] + list(extra)
    for secret in sorted({x for x in secrets if len(x) >= 4}, key=len, reverse=True):
        text = text.replace(secret, "***")
    return text


@contextmanager
def _driver() -> Iterator[Any]:
    """Abre o driver e troca erro de conexao ou autenticacao por uma mensagem curta, sem credenciais."""
    require("neo4j", "neo4j")
    uri, user, password = _connection()
    import neo4j

    try:
        with neo4j.GraphDatabase.driver(uri, auth=(user, password)) as driver:
            yield driver
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError) as exc:
        raise PublishError(f"falha no Neo4j: {_safe(exc)}") from None


def destination() -> str:
    """Endereco do banco para mostrar ao humano, sem credenciais embutidas na URI."""
    parts = urlsplit(_connection()[0])
    return f"{parts.scheme}://{parts.hostname}" + (f":{parts.port}" if parts.port else "")


def browser_url() -> str:
    """Onde o humano abre o Neo4j Browser para o banco configurado. Porta HTTP padrao; o Aura usa o console."""
    host = urlsplit(_connection()[0]).hostname or "localhost"
    if host.endswith(".databases.neo4j.io"):
        return "https://console.neo4j.io"
    return "http://localhost:7474" if host in ("127.0.0.1", "localhost", "::1") else f"http://{host}:7474"


# --- destino ---------------------------------------------------------------------------------------------------

def _state(session: Any, plan: Plan) -> dict[str, Any]:
    """Estado do banco, somente leitura: projetos marcados, total, alheios, legado do n10s e nos deste projeto."""
    state = dict(session.run(STATE_QUERY, prop="projeto").single())
    state["legado"] = bool(state["legado"]) or bool(session.run(LEGACY_QUERY).single()["c"])
    found = {r["label"]: r["c"] for r in session.run(IN_DB_QUERY, projeto=plan.project)}
    state["no_banco"] = dict(sorted({**{label: 0 for label in plan.nodes}, **found}.items()))
    return state


def destination_state(project: Project, plan: Plan) -> dict[str, Any]:
    """Le o estado do banco antes da confirmacao. Somente leitura."""
    with _driver() as driver, driver.session() as session:
        return _state(session, plan)


def check_destination(state: dict[str, Any], project_name: str) -> tuple[str, str | None]:
    """Descreve o banco e diz por que recusar. So aceita banco vazio ou com a marca deste mesmo projeto."""
    projetos, total, alheios = state["projetos"], state["total"], state["alheios"]
    if state.get("legado"):
        return "banco da exportacao antiga (n10s)", "banco carregado pela exportacao antiga (n10s); limpe-o com o comando do guia"
    if not projetos and not total:
        return "vazio", None
    if len(projetos) > 1:
        return f"projetos {', '.join(projetos)}", f"o banco tem mais de um projeto do akme: {', '.join(projetos)}"
    if not projetos:
        return f"{total} no(s) sem marca do akme", f"o banco tem {total} no(s) sem a marca de um projeto do akme; use um banco vazio"
    if projetos[0] != project_name:
        return f"projeto {projetos[0]}", f"o banco ja tem o projeto {projetos[0]}; use outro banco ou limpe este"
    if alheios:
        return f"projeto {project_name}", f"o banco tem {alheios} no(s) que nao vieram do akme"
    return f"projeto {project_name}, sera atualizado", None


# --- comandos --------------------------------------------------------------------------------------------------

# Nomes de restricao e indice: prefixos disjuntos (akme_uniq_, akme_idx_, akme_conceito_) e, no indice, um hash do
# par exato (label, coluna), para nenhum par colidir com outro nem com uma restricao (ex.: coluna `id`, ou
# "A_b"+"c" contra "A"+"b_c"). Com IF NOT EXISTS, uma colisao pularia o indice em silencio.

def _constraint_name(label: str) -> str:
    return "akme_uniq_" + label


def _index_name(label: str, column: str) -> str:
    digest = hashlib.sha1(json.dumps([label, column]).encode("utf-8")).hexdigest()[:10]
    return f"akme_idx_{label}__{column}_{digest}"


def _constraint(label: str) -> str:
    return f"CREATE CONSTRAINT {name(_constraint_name(label))} IF NOT EXISTS FOR (n:{name(label)}) REQUIRE n._id IS UNIQUE"


CONCEPT_CONSTRAINT_NAME = "akme_conceito_uniq_projeto_nome"
CONCEPT_CONSTRAINT = (f"CREATE CONSTRAINT {name(CONCEPT_CONSTRAINT_NAME)} IF NOT EXISTS "
                      f"FOR (c:{CONCEITO}) REQUIRE (c._projeto, c.nome) IS UNIQUE")
MARK = f"MERGE (m:{MARKER} {{projeto: $projeto}})"


def _index(label: str, column: str) -> str:
    return f"CREATE INDEX {name(_index_name(label, column))} IF NOT EXISTS FOR (n:{name(label)}) ON (n.{name(column)})"


def _indexes(plan: Plan) -> list[str]:
    return list(dict.fromkeys(_index(e.range, e.to_column) for e in plan.edges))


def _node_query(label: str) -> str:
    return (f"UNWIND $rows AS r MERGE (n:{name(label)} {{_id: r.id}}) "
            "SET n = r.p, n._id = r.id, n._projeto = $projeto, n._carga = $carga")


def _edge_query(edge: EdgePlan) -> str:
    return (f"UNWIND $rows AS r MATCH (a:{name(edge.domain)} {{_id: r.id}}) MATCH (b:{name(edge.range)} {{{name(edge.to_column)}: r.v}}) "
            f"MERGE (a)-[e:{name(edge.relation)}]->(b) SET e._carga = $carga")


def _batches_of(rows: int) -> int:
    return -(-rows // BATCH)


def _predicted(plan: Plan) -> int:
    """Comandos de dados previstos: um por bloco de cada fonte, mais um por bloco da origem de cada contrato."""
    rows = {s.source: s.rows for s in plan.sources}
    return sum(_batches_of(s.rows) for s in plan.sources) + sum(_batches_of(rows.get(e.from_source, 0)) for e in plan.edges)


# --- carga -----------------------------------------------------------------------------------------------------

def _blocks(adapter: Any, source: str) -> Iterator[list[dict[str, Any]]]:
    """Blocos da fonte; o gerador e sempre fechado (no Postgres o cursor tem nome fixo: nunca duas leituras abertas)."""
    blocks = adapter.iter_rows(source, BATCH)
    try:
        yield from blocks
    finally:
        close = getattr(blocks, "close", None)
        if close:
            close()


def _node_rows(block: list[dict[str, Any]], key: list[str], types: dict[str, str]) -> list[dict[str, Any]]:
    """Linha -> {id, p}: p so com celulas preenchidas, convertidas pelo tipo da etapa 5 (texto se nao declarado)."""
    out = []
    for row in block:
        if not all(filled(row.get(c)) for c in key):
            continue  # chave vazia ja e problema no plano; aqui so nao vira no
        props = {col: convert(types.get(col, "string"), value) for col, value in row.items() if filled(value)}
        out.append({"id": node_id([row[c] for c in key]), "p": props})
    return out


def _edge_rows(block: list[dict[str, Any]], key: list[str], column: str) -> list[dict[str, Any]]:
    """Linha da origem -> {id do no de origem, v}: v no mesmo texto gravado na coluna do no alvo (join e string)."""
    return [{"id": node_id([row[c] for c in key]), "v": convert("string", row[column])}
            for row in block if all(filled(row.get(c)) for c in key) and filled(row.get(column))]


def load(project: Project, plan: Plan, carga: str) -> dict[str, Any]:
    """Grava a carga e sincroniza. Qualquer falha antes da sincronizacao deixa tudo que era antigo no banco."""
    if plan.problems:  # tambem aqui, para quem chamar load direto: fonte sem chave colapsaria todos os nos num so
        raise PublishError("carga recusada, nada foi gravado: " + "; ".join(plan.problems))
    keys = {s.source: s.key for s in plan.sources}
    statements = ontology_statements(project, set(plan.relationships))
    total = _predicted(plan)
    with _driver() as driver, driver.session() as session:
        import neo4j  # so existe depois que _driver confirmou o extra

        errors = (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError, ValueError)
        _, refusal = check_destination(_state(session, plan), project.name)
        if refusal:
            raise PublishError(f"{refusal}. Nada foi gravado")

        for label in plan.nodes:
            session.run(_constraint(label)).consume()
        session.run(CONCEPT_CONSTRAINT).consume()
        for index in _indexes(plan):
            session.run(index).consume()
        session.run("CALL db.awaitIndexes(300)").consume()
        session.run(MARK, projeto=project.name).consume()

        done = 0

        def send(query: str, rows: Any) -> None:
            """Monta as linhas do bloco (rows e chamado aqui: valor que nao converte falha como o lote) e grava."""
            nonlocal done
            try:
                session.run(query, rows=rows(), projeto=project.name, carga=carga).consume()
            except errors as exc:
                raise PublishError(f"lote {done + 1} de {total} falhou: {_safe(exc)}. {done} lote(s) ja gravado(s); "
                                   "nada foi apagado; repetir a carga completa e seguro") from None
            done += 1

        planned = {s.source: s.rows for s in plan.sources}
        read: list[tuple[str, int]] = []  # (fonte, linhas lidas) de cada passada: a dos nos e a de cada contrato
        secrets = _adapter_secrets(project)
        try:
            adapter = load_adapter(project.adapter_name, project.adapter_options())
            try:
                for src in plan.sources:
                    query, count = _node_query(src.label), 0
                    for block in _blocks(adapter, src.source):
                        count += len(block)
                        send(query, lambda: _node_rows(block, src.key, src.types))
                    read.append((src.source, count))
                for edge in plan.edges:
                    count = 0
                    for block in _blocks(adapter, edge.from_source):
                        count += len(block)
                        send(_edge_query(edge), lambda: _edge_rows(block, keys[edge.from_source], edge.from_column))
                    read.append((edge.from_source, count))
            finally:
                adapter.close()
        except PublishError:
            raise
        except Exception as exc:  # erro do adapter no meio da leitura: mesma regra do lote, sem credenciais
            raise PublishError(f"lote {done + 1} de {total} falhou: leitura da origem: {_safe(exc, secrets)}. {done} lote(s) "
                               "ja gravado(s); nada foi apagado; repetir a carga completa e seguro") from None

        # a origem mudou entre o plano e a carga (em qualquer passada): apagar agora poderia levar dados que a origem
        # ainda tem, ou arestas validas de uma origem que encolheu entre a passada dos nos e a das arestas
        changed = list(dict.fromkeys(f"{source} ({planned.get(source, 0)} no plano, {n} agora)" for source, n in read
                                     if n != planned.get(source, 0)))
        if changed:
            raise PublishError(f"a origem mudou durante a carga: {', '.join(changed)}. {done} lote(s) ja gravado(s); "
                               "nada foi apagado; repetir a carga completa e seguro")

        for n, statement in enumerate(statements, 1):
            text, params = statement
            try:
                session.run(text, {**params, "projeto": project.name, "carga": carga}).consume()
            except errors as exc:
                raise PublishError(f"ontologia: comando {n} de {len(statements)} falhou: {_safe(exc)}. {done} lote(s) "
                                   "ja gravado(s); nada foi apagado; repetir a carga completa e seguro") from None

        try:
            nodes = session.run(SYNC_NODES, projeto=project.name, carga=carga).consume().counters
            edges = session.run(SYNC_EDGES, projeto=project.name, carga=carga).consume().counters
        except errors as exc:
            raise PublishError(f"sincronizacao falhou: {_safe(exc)}. A carga nova ja esta gravada; parte do que era "
                               "antigo pode nao ter sido apagado; repetir a carga completa e seguro") from None
    # arestas: as de nos apagados (DETACH) mais as antigas entre nos que ficaram
    return {"executed": done, "removed": {"nodes": nodes.nodes_deleted,
                                          "relationships": nodes.relationships_deleted + edges.relationships_deleted}}


# --- conferencia -----------------------------------------------------------------------------------------------

def verify(plan: Plan, project_name: str, concepts: int) -> dict[str, Any]:
    """Conta no banco por label e por padrao (:Dominio)-[:relacao]->(:Alcance) e compara com o plano."""
    with _driver() as driver, driver.session() as session:
        def count(query: str) -> int:
            return session.run(query, p=project_name).single()["c"]

        observed = {label: count(f"MATCH (n:{name(label)}) WHERE n._projeto = $p RETURN count(n) AS c") for label in plan.nodes}
        observed |= {e.relation: count(f"MATCH (:{name(e.domain)})-[r:{name(e.relation)}]->(:{name(e.range)}) RETURN count(r) AS c")
                     for e in plan.edges}
        observed[CONCEITO] = count(f"MATCH (c:{CONCEITO} {{_projeto: $p}}) RETURN count(c) AS c")
    expected = {**plan.nodes, **plan.relationships, CONCEITO: concepts}
    divergences = [f"{k}: esperado {n}, encontrado {observed.get(k)}" for k, n in expected.items() if observed.get(k) != n]
    return {"ok": not divergences, "divergences": divergences}


# --- artefato e publicacao -------------------------------------------------------------------------------------

def _comment(text: Any) -> str:
    return "// " + " ".join(str(text).split())


def _artifact(project: Project, model: dict[str, Any], plan: Plan, batches: int) -> str:
    lines = [_comment(f"{model['project']} {model['version']}: gerado por akme publish --target neo4j (Cypher puro, sem plugin)")]
    if plan.problems:
        lines += [_comment("NAO EXECUTE: a carga seria recusada. Problemas:"), *[_comment(f"  {p}") for p in plan.problems]]
    lines += [_comment(f"linhas lidas: {plan.rows}; comandos de dados previstos: {batches} (blocos de {BATCH} linhas)"),
              _comment("nos previstos: " + (", ".join(f"{k} {n}" for k, n in plan.nodes.items()) or "nenhum")),
              _comment("arestas previstas: " + (", ".join(f"{k} {n}" for k, n in plan.relationships.items()) or "nenhuma"))]
    warnings = _warnings(plan)
    lines += [_comment("avisos:"), *[_comment(f"  {w}") for w in warnings]] if warnings else [_comment("avisos: nenhum")]
    lines += [_comment("parametros: $projeto = nome do projeto; $carga = data e hora UTC da carga. No Browser:"),
              _comment(":param projeto => '" + project.name.replace("\\", "\\\\").replace("'", "\\'") + "'"), _comment(":param carga => '2026-01-01T00:00:00+00:00'"),
              "", _comment("1. restricoes e indices"),
              *[q + ";" for q in [_constraint(label) for label in plan.nodes] + [CONCEPT_CONSTRAINT] + _indexes(plan)],
              "", _comment("2. marca do projeto"), MARK + ";",
              "", _comment("3. nos, por fonte (modelo: $rows = [{id, p}] em blocos, os dados nao estao aqui)"),
              *[_comment(f"{s.source}: {_node_query(s.label)}") for s in plan.sources],
              "", _comment("4. arestas, por contrato (modelo: $rows = [{id, v}] em blocos da origem)"),
              *[_comment(f"{e.relation}: {_edge_query(e)}") for e in plan.edges],
              "", _comment("5. ontologia (camada Conceito)"),
              *[render(s) + ";" for s in ontology_statements(project, set(plan.relationships))],
              "", _comment("6. sincronizacao, so depois de tudo acima dar certo (modelo)"),
              _comment(SYNC_NODES), _comment(SYNC_EDGES)]
    return "\n".join(lines) + "\n"


def _warnings(plan: Plan) -> list[str]:
    return ([f"fonte excluida na etapa 5: {s}" for s in plan.sources_skipped]
            + [f"relacao nao publicada: {r}" for r in plan.relations_not_published] + plan.warnings)


def publish_neo4j(project: Project, model: dict[str, Any], dry_run: bool, plan: Plan | None = None) -> dict[str, Any]:
    """Com `plan`, reaproveita o plano ja montado (a CLI monta um so); a carga confere a origem de novo ao gravar."""
    plan = plan or build_plan(project, BATCH)
    batches = _predicted(plan)
    out = project.docs_dir / "publish" / "neo4j.cypher"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_artifact(project, model, plan, batches), encoding="utf-8")
    result: dict[str, Any] = {
        "target": "neo4j", "dry_run": dry_run, "artifact": str(out), "rows": plan.rows, "batches": batches,
        "executed": 0, "nodes": plan.nodes, "relationships": plan.relationships,
        "relations_not_published": plan.relations_not_published, "sources_skipped": plan.sources_skipped,
        "problems": plan.problems, "warnings": plan.warnings}
    if dry_run:
        return result
    if plan.problems:
        raise PublishError("carga recusada, nada foi gravado: " + "; ".join(plan.problems))
    carga = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["carga"] = carga
    result |= load(project, plan, carga)
    result["verification"] = verify(plan, project.name, len(classes(load_graph(project.schema_path))))
    if not result["verification"]["ok"]:
        raise PublishError("carga executada, mas o banco diverge do previsto: " + "; ".join(result["verification"]["divergences"]))
    return result


# --- textos para o humano --------------------------------------------------------------------------------------

def preview_lines(result: dict[str, Any], state: dict[str, Any] | None = None) -> list[str]:
    """Resumo que o humano le antes de confirmar a carga; com o estado do banco, compara banco e origem por label."""
    warnings = [f"fonte excluida na etapa 5: {s}" for s in result["sources_skipped"]]
    warnings += [f"relacao nao publicada: {r}" for r in result["relations_not_published"]]
    warnings += result["warnings"]
    lines = [f"linhas: {result['rows']} em {result['batches']} lote(s) de dados, mais a ontologia", "nos previstos:"]
    lines += [f"  {label}: {n}" for label, n in result["nodes"].items()]
    lines += ["arestas previstas:"]
    lines += [f"  {relation}: {n}" for relation, n in result["relationships"].items()]
    if state is not None:
        in_db = state.get("no_banco") or {}
        lines += ["no banco hoje, deste projeto:"]
        lines += [f"  {label}: banco {in_db.get(label, 0)} -> origem {result['nodes'].get(label, 0)}"
                  for label in sorted(set(in_db) | set(result["nodes"]))]
        warnings = [*warnings, "a carga apaga deste projeto o que nao vier da origem nesta carga"]
    lines += ["avisos:", *[f"  {w}" for w in warnings]] if warnings else ["avisos: nenhum"]
    return lines + (["problemas (a carga sera recusada):", *[f"  {p}" for p in result["problems"]]] if result["problems"] else [])


def viewing_lines(project: Project, result: dict[str, Any]) -> list[str]:
    """Depois da carga: onde ver o grafo e consultas prontas, montadas com as classes e relacoes deste projeto."""
    contracts = {c["relation"]: c for c in load_content(project)["relation_contracts"]}

    def cy(identifier: str) -> str:  # crases so quando o nome precisa
        return identifier if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier) else name(identifier)

    examples = [f"MATCH p = (:{cy(contracts[r]['domain'])})-[:{cy(r)}]->(:{cy(contracts[r]['range'])}) RETURN p LIMIT 50"
                for r in list(result["relationships"])[:3] if r in contracts]
    return [
        "",
        "Para ver o grafo:",
        f"  1. abra {browser_url()} no navegador (Neo4j Browser)",
        f"  2. entre com o usuario {_connection()[1]} e a senha de AKME_NEO4J_PASSWORD",
        "  3. cole uma consulta no campo do topo e aperte Enter:",
        *[f"     {q}" for q in examples],
        "     MATCH (n)-[r]->(m) WHERE NOT n:Conceito RETURN n, r, m LIMIT 300   // os dados",
        "     MATCH p = (:Conceito)-->(:Conceito) RETURN p   // a ontologia: conceitos e relacoes",
        "  Na lateral do Browser, o icone de banco lista labels e relacoes; clique em um para ver os nos.",
    ]
