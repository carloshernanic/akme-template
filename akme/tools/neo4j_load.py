"""Carga no Neo4j em Cypher puro, sem plugin: nos, arestas, camada Conceito, sincronizacao e conferencia.

A ordem, numa so sessao: confere a versao do Neo4j e o destino; marca o projeto com a carga em andamento
(`carga_atual`, a trava contra carga concorrente); cria restricoes e indices; grava os nos fonte a fonte, em blocos;
grava as arestas, resolvidas pelo banco pela coluna do join; grava a ontologia (Conceito, Termo) e o esquema para o
LLM na marca; e so entao, se nenhuma outra carga do projeto comecou depois desta, apaga deste projeto o que nao veio
nesta carga. Todo comando de dado, da ontologia e do esquema comeca pela trava (`_LOCK`): depois que uma carga mais
nova troca `carga_atual`, a antiga nao grava mais nada. Toda gravacao fora a sincronizacao usa transacao gerenciada (execute_write), que o driver repete em erro
transitorio; repetir e seguro porque tudo e MERGE. Cada no e aresta de dado leva
`_descricao` (definicao da classe ou da relacao) no mesmo SET que o grava. Dados vao sempre como parametro; so identificadores entram no texto, por name().
Credenciais vem do ambiente e nunca aparecem numa mensagem de erro.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from urllib.parse import urlsplit

from ..adapters import load_adapter
from ..adapters.base import require
from ..ontology import classes, load_content, load_graph
from ..project import Project
from .neo4j_onto import _literal, descriptions, ontology_statements, render, term_entries
from .neo4j_plan import EdgePlan, Plan, SourcePlan, build_plan, identifier_problems
from .neo4j_guide import GUIDE_FILE, QUERIES_FILE, guide_html, guide_lines, saved_queries_csv
from .neo4j_schema import llm_schema
from .neo4j_values import caption, convert, filled, name, node_id
from .publish import PublishError

BATCH = 5000
MARKER = "_AkmeProjeto"
LEGACY_LABELS = ("Resource", "_GraphConfig")
LEGACY_CONSTRAINT = "n10s_unique_uri"
CONCEITO = "Conceito"
TERMO = "Termo"

# Labels e propriedades como texto: num banco vazio eles ainda nao existem, e o servidor avisaria a cada consulta.
STATE_QUERY = (
    f"RETURN COLLECT {{ MATCH (m) WHERE '{MARKER}' IN labels(m) RETURN m[$prop] }} AS projetos, "
    "COUNT { MATCH (n) } AS total, "
    f"COUNT {{ MATCH (n) WHERE n['_projeto'] IS NULL AND NOT '{MARKER}' IN labels(n) }} AS alheios, "
    # legado: no do n10s (sem _projeto), para uma classe do cliente chamada Resource nao ser confundida com ele
    "EXISTS { MATCH (n) WHERE n['_projeto'] IS NULL AND ("
    + " OR ".join(f"'{label}' IN labels(n)" for label in LEGACY_LABELS) + ") } AS legado")
LEGACY_QUERY = f"SHOW CONSTRAINTS YIELD name WHERE name = '{LEGACY_CONSTRAINT}' RETURN count(*) AS c"
IN_DB_QUERY = (f"MATCH (n) WHERE n['_projeto'] = $projeto UNWIND labels(n) AS label "
               f"WITH label WHERE NOT label IN ['{CONCEITO}', '{TERMO}'] RETURN label, count(*) AS c")
# arestas de dado deste projeto por tipo (as da camada de ontologia saem de :Conceito e ficam de fora)
EDGES_IN_DB_QUERY = (f"MATCH (n)-[r]->() WHERE n['_projeto'] = $projeto AND NOT n:{CONCEITO} AND NOT n:{TERMO} "
                     "RETURN type(r) AS tipo, count(r) AS c")

# Sincronizacao: so nos e arestas deste projeto (_projeto) com _carga diferente da atual. A marca _AkmeProjeto tem
# `projeto`, nao `_projeto`, e fica. IN TRANSACTIONS exige transacao implicita: session.run, nunca execute_write.
# A trava contra carga concorrente vai no proprio comando: sem a marca com carga_atual = $carga, o MATCH nao acha
# nada e o comando nao apaga nada. A checagem em Python antes de cada comando so da a mensagem clara.
_LOCK = f"MATCH (m:{MARKER} {{projeto: $projeto}}) WHERE m.carga_atual = $carga "
SYNC_NODES = (_LOCK + "MATCH (n) WHERE n['_projeto'] = $projeto AND coalesce(n['_carga'], '') <> $carga "
              f"CALL (n) {{ DETACH DELETE n }} IN TRANSACTIONS OF {BATCH} ROWS")
SYNC_EDGES = (_LOCK + "MATCH (n)-[r]->() WHERE n['_projeto'] = $projeto AND coalesce(r['_carga'], '') <> $carga "
              f"CALL (r) {{ DELETE r }} IN TRANSACTIONS OF {BATCH} ROWS")

# Trava contra carga concorrente: a carga grava a sua marca de rodada na marca do projeto logo depois de conferir o
# destino e, antes de cada comando da sincronizacao, confere que nenhuma carga mais nova a trocou.
# `name` e a legenda da marca no Browser (sem ela, a legenda seria o esquema inteiro)
CLAIM = f"MERGE (m:{MARKER} {{projeto: $projeto}}) SET m.carga_atual = $carga, m.name = 'Projeto ' + $projeto"
# sem restricao, duas primeiras cargas simultaneas num banco vazio poderiam criar duas marcas com o MERGE
MARKER_CONSTRAINT_NAME = "akme_projeto_uniq"
CURRENT_QUERY = f"MATCH (m:{MARKER} {{projeto: $projeto}}) RETURN m.carga_atual AS carga"
NEWER_LOAD = "outra carga deste projeto comecou depois desta; nada foi apagado. Rode a carga de novo"
NEWER_LOAD_MID_SYNC = ("outra carga deste projeto comecou durante a sincronizacao; os nos antigos ja foram apagados, "
                       "as arestas antigas nao. Rode a carga de novo")

# COLLECT {} exige 5.6 e CALL (n) {} IN TRANSACTIONS exige 5.23: abaixo disso a carga gravaria tudo e falharia so
# na sincronizacao
VERSION_QUERY = "CALL dbms.components() YIELD versions RETURN versions[0] AS versao LIMIT 1"
MIN_VERSION = (5, 23)
NOTIFICATIONS_OFF = ["UNRECOGNIZED"]


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


def version_refusal(version: Any) -> str | None:
    """Por que recusar a versao do servidor (5.26.0, 5.27-aura, 2026.10.1), ou None se atende a MIN_VERSION."""
    found = re.match(r"(\d+)\.(\d+)", str(version))
    if not found:
        return f"versao nao reconhecida do Neo4j: {version}; a carga exige Neo4j 5.23 ou mais novo"
    if (int(found.group(1)), int(found.group(2))) < MIN_VERSION:
        return f"o Neo4j {version} e antigo: a carga exige Neo4j 5.23 ou mais novo"
    return None


def supported_version(version: Any) -> bool:
    return version_refusal(version) is None


def _session(driver: Any) -> Any:
    """Sessao no banco de AKME_NEO4J_DATABASE, se definida; sem ela, o banco padrao do servidor."""
    database = os.environ.get("AKME_NEO4J_DATABASE", "").strip()
    return driver.session(database=database) if database else driver.session()


def _write(session: Any, query: str, params: dict[str, Any] | None = None) -> Any:
    """Um comando numa transacao gerenciada: o driver repete em erro transitorio (troca de lider, conexao cortada)."""
    def work(tx: Any) -> Any:
        return tx.run(query, params or {}).consume()
    return session.execute_write(work)


def _write_rows(session: Any, query: str, params: dict[str, Any]) -> int:
    """Bloco de dados numa transacao gerenciada; devolve quantas linhas o comando gravou (0 se a trava barrou)."""
    def work(tx: Any) -> int:
        record = tx.run(query, params).single()
        return record["gravadas"] if record else 0
    return session.execute_write(work)


def _current(session: Any, project_name: str) -> Any:
    record = session.run(CURRENT_QUERY, projeto=project_name).single()
    return record["carga"] if record else None


@contextmanager
def _driver() -> Iterator[Any]:
    """Abre o driver e troca erro de conexao ou autenticacao por uma mensagem curta, sem credenciais."""
    require("neo4j", "neo4j")
    uri, user, password = _connection()
    import neo4j

    try:
        # so a familia UNRECOGNIZED (ex.: 01N52, propriedade _projeto inexistente num banco vazio) e desligada;
        # avisos de depreciacao e desempenho continuam vindo
        with neo4j.GraphDatabase.driver(uri, auth=(user, password), notifications_disabled_classifications=NOTIFICATIONS_OFF) as driver:
            yield driver
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError) as exc:
        raise PublishError(f"falha no Neo4j: {_safe(exc)}") from None


def destination() -> str:
    """Endereco do banco para mostrar ao humano, sem credenciais embutidas na URI."""
    parts = urlsplit(_connection()[0])
    return f"{parts.scheme}://{parts.hostname}" + (f":{parts.port}" if parts.port else "")


def browser_url() -> str:
    """Onde o humano abre o Neo4j Browser. AKME_NEO4J_BROWSER_URL, se definida, vale (Docker com outra porta HTTP);
    sem ela, a porta HTTP padrao no host do Bolt, e o console no Aura."""
    configured = os.environ.get("AKME_NEO4J_BROWSER_URL", "").strip()
    if configured:
        return configured
    host = urlsplit(_connection()[0]).hostname or "localhost"
    if host.endswith(".databases.neo4j.io"):
        return "https://console.neo4j.io"
    return "http://localhost:7474" if host in ("127.0.0.1", "localhost", "::1") else f"http://{host}:7474"


# --- destino ---------------------------------------------------------------------------------------------------

def _state(session: Any, plan: Plan) -> dict[str, Any]:
    """Estado do banco, somente leitura: projetos marcados, total, alheios, legado do n10s, nos deste projeto por label e
    arestas de dado deste projeto por tipo."""
    state = dict(session.run(STATE_QUERY, prop="projeto").single())
    state["legado"] = bool(state["legado"]) or bool(session.run(LEGACY_QUERY).single()["c"])
    found = {r["label"]: r["c"] for r in session.run(IN_DB_QUERY, projeto=plan.project)}
    state["no_banco"] = dict(sorted({**{label: 0 for label in plan.nodes}, **found}.items()))
    edges = {r["tipo"]: r["c"] for r in session.run(EDGES_IN_DB_QUERY, projeto=plan.project)}
    state["arestas_no_banco"] = dict(sorted({**{e.relation: 0 for e in plan.edges}, **edges}.items()))
    return state


def _check_version(session: Any) -> None:
    """Consulta simples (vale em qualquer versao) antes de STATE_QUERY, que usa COLLECT {} (5.6+): servidor antigo
    recebe a recusa clara, nao um erro de sintaxe."""
    refusal = version_refusal(session.run(VERSION_QUERY).single()["versao"])
    if refusal:
        raise PublishError(f"{refusal}. Nada foi gravado")


def destination_state(project: Project, plan: Plan) -> dict[str, Any]:
    """Le o estado do banco antes da confirmacao. Somente leitura; confere a versao primeiro."""
    with _driver() as driver, _session(driver) as session:
        _check_version(session)
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


MARKER_CONSTRAINT = (f"CREATE CONSTRAINT {name(MARKER_CONSTRAINT_NAME)} IF NOT EXISTS "
                     f"FOR (m:{MARKER}) REQUIRE m.projeto IS UNIQUE")
CONCEPT_CONSTRAINT_NAME = "akme_conceito_uniq_projeto_nome"
CONCEPT_CONSTRAINT = (f"CREATE CONSTRAINT {name(CONCEPT_CONSTRAINT_NAME)} IF NOT EXISTS "
                      f"FOR (c:{CONCEITO}) REQUIRE (c._projeto, c.nome) IS UNIQUE")
TERM_CONSTRAINT_NAME = "akme_termo_uniq_projeto_nome"
TERM_CONSTRAINT = (f"CREATE CONSTRAINT {name(TERM_CONSTRAINT_NAME)} IF NOT EXISTS "
                   f"FOR (t:{TERMO}) REQUIRE (t._projeto, t.nome) IS UNIQUE")
# esquema para o LLM na marca: so leitura para quem consulta, sobrescrito a cada carga (a marca nao tem _carga);
# com a trava, uma carga antiga nao sobrescreve o esquema da mais nova
SCHEMA_SET = _LOCK + "SET m.esquema = $esquema RETURN count(*) AS gravadas"


def _index(label: str, column: str) -> str:
    return f"CREATE INDEX {name(_index_name(label, column))} IF NOT EXISTS FOR (n:{name(label)}) ON (n.{name(column)})"


def _indexes(plan: Plan) -> list[str]:
    return list(dict.fromkeys(_index(e.range, e.to_column) for e in plan.edges))


# $descricao e o texto da classe ou da relacao, igual em todo o bloco; null (sem definicao) deixa a propriedade ausente
# Cada bloco comeca pela trava (_LOCK): depois que outra carga do projeto troca carga_atual, o bloco nao grava nada
# e devolve gravadas = 0; a carga entao confere a marca e para, sem sujar o que a mais nova gravou.
def _node_query(label: str) -> str:
    return (_LOCK + f"WITH m UNWIND $rows AS r MERGE (n:{name(label)} {{_id: r.id}}) "
            "SET n = r.p, n._id = r.id, n._projeto = $projeto, n._carga = $carga, n._descricao = $descricao "
            "RETURN count(*) AS gravadas")


def _edge_query(edge: EdgePlan) -> str:
    return (_LOCK + f"WITH m UNWIND $rows AS r MATCH (a:{name(edge.domain)} {{_id: r.id}}) "
            f"MATCH (b:{name(edge.range)} {{{name(edge.to_column)}: r.v}}) "
            f"MERGE (a)-[e:{name(edge.relation)}]->(b) SET e._carga = $carga, e._descricao = $descricao "
            "RETURN count(*) AS gravadas")


def _labels(plan: Plan) -> dict[str, str]:
    """Fonte -> label de cada fonte que vira no: o que cita o grafo em "nao somar apos juntar com"."""
    return {s.source: s.label for s in plan.sources}


def _locked(text: str) -> str:
    """Comando da ontologia com a trava na frente: depois que outra carga do projeto troca carga_atual, ele nao grava
    nada (nem carimba _carga sobre o que a mais nova gravou) e devolve gravadas = 0."""
    return _LOCK + "WITH m " + text + " RETURN count(*) AS gravadas"


def _ontology(project: Project, plan: Plan) -> list[tuple[str, dict[str, Any]]]:
    return [(_locked(text), params) for text, params in ontology_statements(project, set(plan.relationships), _labels(plan))]


def _batches_of(rows: int) -> int:
    return -(-rows // BATCH)


def _predicted(plan: Plan) -> int:
    """Comandos de dados previstos: um por bloco de cada fonte, mais um por bloco da origem de cada contrato."""
    rows = {s.source: s.rows for s in plan.sources}
    return sum(_batches_of(s.rows) for s in plan.sources) + sum(_batches_of(rows.get(e.from_source, 0)) for e in plan.edges)


# --- carga -----------------------------------------------------------------------------------------------------

def _blocks(adapter: Any, source: str) -> Iterator[list[dict[str, Any]]]:
    """Blocos da fonte; o gerador e fechado mesmo quando a carga para no meio (cursor e arquivo nao ficam abertos)."""
    blocks = adapter.iter_rows(source, BATCH)
    try:
        yield from blocks
    finally:
        close = getattr(blocks, "close", None)
        if close:
            close()


def _node_rows(block: list[dict[str, Any]], src: SourcePlan) -> list[dict[str, Any]]:
    """Linha -> {id, p}: p so com celulas preenchidas, convertidas pelo tipo da etapa 5 (texto se nao declarado), mais
    a legenda `name` (neo4j_values.caption). Quando a fonte tem coluna `name`, vale a da origem; o akme so grava a sua
    nas linhas em que essa coluna esta vazia (sem isso o no ficaria sem legenda no Browser)."""
    out = []
    key, types = src.key, src.types
    for row in block:
        if not all(filled(row.get(c)) for c in key):
            continue  # chave vazia ja e problema no plano; aqui so nao vira no
        props = {col: convert(types.get(col, "string"), value) for col, value in row.items() if filled(value)}
        if not src.own_name or not filled(row.get("name")):
            props["name"] = caption(src.label, [row[c] for c in key], row.get(src.caption) if src.caption else None)
        out.append({"id": node_id([row[c] for c in key]), "p": props})
    return out


def _edge_rows(block: list[dict[str, Any]], key: list[str], column: str) -> list[dict[str, Any]]:
    """Linha da origem -> {id do no de origem, v}: v no mesmo texto gravado na coluna do no alvo (join e string)."""
    return [{"id": node_id([row[c] for c in key]), "v": convert("string", row[column])}
            for row in block if all(filled(row.get(c)) for c in key) and filled(row.get(column))]


def load(project: Project, plan: Plan, carga: str) -> dict[str, Any]:
    """Grava a carga e sincroniza. Qualquer falha antes da sincronizacao deixa tudo que era antigo no banco."""
    # tambem aqui, para quem chamar load direto: fonte sem chave colapsaria todos os nos num so, e um identificador
    # recusado por name() quebraria a carga no meio
    problems = plan.problems or identifier_problems(plan, load_content(project)["relation_contracts"])
    if problems:
        raise PublishError("carga recusada, nada foi gravado: " + "; ".join(problems))
    keys = {s.source: s.key for s in plan.sources}
    statements = _ontology(project, plan) + [(SCHEMA_SET, {"esquema": llm_schema(project, plan)})]
    node_text, edge_text = descriptions(project)
    total = _predicted(plan)
    with _driver() as driver, _session(driver) as session:
        import neo4j  # so existe depois que _driver confirmou o extra

        errors = (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError, ValueError)
        _check_version(session)  # antes do estado: STATE_QUERY usa COLLECT {}, que servidor antigo nem entende
        _, refusal = check_destination(_state(session, plan), project.name)
        if refusal:
            raise PublishError(f"{refusal}. Nada foi gravado")
        _write(session, MARKER_CONSTRAINT)
        _write(session, CLAIM, {"projeto": project.name, "carga": carga})

        for label in plan.nodes:
            _write(session, _constraint(label))
        _write(session, CONCEPT_CONSTRAINT)
        _write(session, TERM_CONSTRAINT)
        for index in _indexes(plan):
            _write(session, index)
        session.run("CALL db.awaitIndexes(300)").consume()

        done = 0

        def send(query: str, rows: Any, descricao: str | None) -> None:
            """Monta as linhas do bloco (rows e chamado aqui: valor que nao converte falha como o lote) e grava."""
            nonlocal done
            try:
                block = rows()
                written = _write_rows(session, query, {"rows": block, "projeto": project.name, "carga": carga,
                                                       "descricao": descricao})
                # 0 com linhas: a trava barrou (outra carga) ou, numa aresta, nenhum alvo; a marca decide
                stolen = block and not written and _current(session, project.name) != carga
            except errors as exc:
                raise PublishError(f"lote {done + 1} de {total} falhou: {_safe(exc)}. {done} lote(s) ja gravado(s); "
                                   "nada foi apagado; repetir a carga completa e seguro") from None
            if stolen:
                raise PublishError(NEWER_LOAD)
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
                        send(query, lambda: _node_rows(block, src), node_text.get(src.label))
                    read.append((src.source, count))
                # arestas depois de todos os nos; uma leitura por fonte de origem, com os contratos dela em cada
                # bloco, na ordem do plano (deterministico: mesmos comandos e contagens de uma passada por contrato)
                by_origin: dict[str, list[EdgePlan]] = {}
                for edge in plan.edges:
                    by_origin.setdefault(edge.from_source, []).append(edge)
                for origin, edges in by_origin.items():
                    count = 0
                    for block in _blocks(adapter, origin):
                        count += len(block)
                        for edge in edges:
                            send(_edge_query(edge), lambda: _edge_rows(block, keys[origin], edge.from_column),
                                 edge_text.get(edge.relation))
                    read.append((origin, count))
            finally:
                adapter.close()
        except PublishError:
            raise
        except Exception as exc:  # erro do adapter no meio da leitura: mesma regra do lote, sem credenciais
            raise PublishError(f"lote {done + 1} de {total} falhou: leitura da origem: {type(exc).__name__}: "
                               f"{_safe(exc, secrets)}. {done} lote(s) "
                               "ja gravado(s); nada foi apagado; repetir a carga completa e seguro") from None

        # a origem mudou entre o plano e a carga (em qualquer passada): apagar agora poderia levar dados que a origem
        # ainda tem, ou arestas validas de uma origem que encolheu entre a passada dos nos e a das arestas
        changed = list(dict.fromkeys(f"{source} ({planned.get(source, 0)} no plano, {n} agora)" for source, n in read
                                     if n != planned.get(source, 0)))
        if changed:
            raise PublishError(f"a origem mudou durante a carga: {', '.join(changed)}. {done} lote(s) ja gravado(s); "
                               "nada foi apagado; repetir a carga completa e seguro")

        # ontologia e esquema, com a trava em cada comando: 0 gravado com a marca trocada = outra carga comecou
        for n, statement in enumerate(statements, 1):
            text, params = statement
            try:
                written = _write_rows(session, text, {**params, "projeto": project.name, "carga": carga})
                stolen = not written and _current(session, project.name) != carga
            except errors as exc:
                raise PublishError(f"ontologia: comando {n} de {len(statements)} falhou: {_safe(exc)}. {done} lote(s) "
                                   "ja gravado(s); nada foi apagado; repetir a carga completa e seguro") from None
            if stolen:
                raise PublishError(NEWER_LOAD)

        # sincronizacao: IN TRANSACTIONS exige transacao implicita (session.run); antes de cada comando, a trava
        if _current(session, project.name) != carga:
            raise PublishError(NEWER_LOAD)
        failed = "sincronizacao falhou: {}. A carga nova ja esta gravada; parte do que era antigo pode nao ter sido " \
                 "apagado; repetir a carga completa e seguro"
        try:
            nodes = session.run(SYNC_NODES, projeto=project.name, carga=carga).consume().counters
            stolen = _current(session, project.name) != carga
        except errors as exc:
            raise PublishError(failed.format(_safe(exc))) from None
        if stolen:  # a trava do comando pode ter barrado SYNC_NODES: sem nada apagado, a mensagem e a de antes
            raise PublishError(NEWER_LOAD_MID_SYNC if nodes.nodes_deleted else NEWER_LOAD)
        try:
            edges = session.run(SYNC_EDGES, projeto=project.name, carga=carga).consume().counters
        except errors as exc:
            raise PublishError(failed.format(_safe(exc))) from None
    # arestas: as de nos apagados (DETACH) mais as antigas entre nos que ficaram
    return {"executed": done, "removed": {"nodes": nodes.nodes_deleted,
                                          "relationships": nodes.relationships_deleted + edges.relationships_deleted}}


# --- conferencia -----------------------------------------------------------------------------------------------

def verify(plan: Plan, project_name: str, concepts: int, terms: int | None = None) -> dict[str, Any]:
    """Conta no banco por label e por padrao (:Dominio)-[:relacao]->(:Alcance) e compara com o plano. Com `terms`,
    confere tambem os nos :Termo do projeto."""
    with _driver() as driver, _session(driver) as session:
        def count(query: str) -> int:
            return session.run(query, p=project_name).single()["c"]

        observed = {label: count(f"MATCH (n:{name(label)}) WHERE n._projeto = $p RETURN count(n) AS c") for label in plan.nodes}
        observed |= {e.relation: count(f"MATCH (:{name(e.domain)})-[r:{name(e.relation)}]->(:{name(e.range)}) RETURN count(r) AS c")
                     for e in plan.edges}
        observed[CONCEITO] = count(f"MATCH (c:{CONCEITO} {{_projeto: $p}}) RETURN count(c) AS c")
        if terms is not None:
            observed[TERMO] = count(f"MATCH (t:{TERMO} {{_projeto: $p}}) RETURN count(t) AS c")
    expected = {**plan.nodes, **plan.relationships, CONCEITO: concepts} | ({TERMO: terms} if terms is not None else {})
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
    warnings = warning_lines(plan.sources_skipped, plan.relations_not_published, plan.warnings)
    lines += [_comment("avisos:"), *[_comment(f"  {w}") for w in warnings]] if warnings else [_comment("avisos: nenhum")]
    lines += [_comment("parametros: $projeto = nome do projeto; $carga = data e hora UTC da carga. No Browser:"),
              _comment(":param projeto => " + _literal(project.name)),
              _comment(":param carga => '2026-01-01T00:00:00.000+00:00'")]
    try:
        commands = [
            "", _comment("1. marca do projeto com a carga em andamento (trava contra carga concorrente)"),
            MARKER_CONSTRAINT + ";", CLAIM + ";",
            "", _comment("2. restricoes e indices"),
            *[q + ";" for q in [_constraint(label) for label in plan.nodes] + [CONCEPT_CONSTRAINT, TERM_CONSTRAINT] + _indexes(plan)],
            "", _comment("3. nos, por fonte (modelo: $rows = [{id, p}] em blocos, os dados nao estao aqui;"),
            _comment("   $descricao = definicao da classe, ou null sem definicao)"),
            *[_comment(f"{s.source}: {_node_query(s.label)}") for s in plan.sources],
            "", _comment("4. arestas, por contrato (modelo: $rows = [{id, v}] em blocos da origem;"),
            _comment("   $descricao = definicao da relacao, ou o rotulo enquanto ela nao tiver definicao)"),
            *[_comment(f"{e.relation}: {_edge_query(e)}") for e in plan.edges],
            "", _comment("5. ontologia (camadas Conceito e Termo) e esquema para o LLM na marca"),
            *[render(s) + ";" for s in _ontology(project, plan)],
            _comment(f"{SCHEMA_SET}   // $esquema = texto de docs/publish/neo4j_schema.md"),
            "", _comment("6. sincronizacao, so depois de tudo acima dar certo e se m.carga_atual ainda for $carga (modelo)"),
            _comment(CURRENT_QUERY), _comment(SYNC_NODES), _comment(SYNC_EDGES)]
    except ValueError:  # identificador recusado por name(): ja esta nos problemas, e nenhum comando sai
        commands = ["", _comment("comandos omitidos: ha identificador recusado (veja os problemas acima)")]
    return "\n".join(lines + commands) + "\n"


def warning_lines(skipped: list[str], not_published: list[str], warnings: list[str]) -> list[str]:
    """Avisos do plano, iguais no artefato e na previa da CLI."""
    return ([f"fonte excluida na etapa 5: {s}" for s in skipped]
            + [f"relacao nao publicada: {r}" for r in not_published] + list(warnings))


def publish_neo4j(project: Project, model: dict[str, Any], dry_run: bool, plan: Plan | None = None) -> dict[str, Any]:
    """Com `plan`, reaproveita o plano ja montado (a CLI monta um so); a carga confere a origem de novo ao gravar."""
    plan = plan or build_plan(project, BATCH)
    batches = _predicted(plan)
    out = project.docs_dir / "publish" / "neo4j.cypher"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_artifact(project, model, plan, batches), encoding="utf-8")
    schema = out.with_name("neo4j_schema.md")
    schema.write_text(llm_schema(project, plan), encoding="utf-8")
    # tutorial do projeto no Browser e consultas salvas: a cada publicacao, carga ou dry-run; depois da carga, de novo,
    # com o mapa da ontologia na forma que o banco aceita (com ou sem APOC)
    guide, queries = out.with_name(GUIDE_FILE), out.with_name(QUERIES_FILE)
    _write_guide(plan, guide, queries, None)
    result: dict[str, Any] = {
        "target": "neo4j", "dry_run": dry_run, "artifact": str(out), "schema": str(schema), "guide": str(guide),
        "saved_queries": str(queries),
        "rows": plan.rows, "batches": batches,
        "executed": 0, "nodes": plan.nodes, "relationships": plan.relationships,
        "relations_not_published": plan.relations_not_published, "sources_skipped": plan.sources_skipped,
        "problems": plan.problems, "warnings": plan.warnings}
    if dry_run:
        return result
    if plan.problems:
        raise PublishError("carga recusada, nada foi gravado: " + "; ".join(plan.problems))
    carga = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    result["carga"] = carga
    result |= load(project, plan, carga)
    concepts = {c["name"] for c in classes(load_graph(project.schema_path))}
    result["verification"] = verify(plan, project.name, len(concepts), len(term_entries(load_content(project), concepts)))
    if not result["verification"]["ok"]:
        raise PublishError("carga executada, mas o banco diverge do previsto: " + "; ".join(result["verification"]["divergences"]))
    _write_guide(plan, guide, queries, has_apoc())
    return result


def _write_guide(plan: Plan, guide: Path, queries: Path, apoc: bool | None) -> None:
    guide.write_text(guide_html(plan, apoc), encoding="utf-8")
    queries.write_text(saved_queries_csv(plan, apoc), encoding="utf-8")


APOC_QUERY = "SHOW FUNCTIONS YIELD name WHERE name = 'apoc.create.vRelationship' RETURN count(*) AS c"


def has_apoc() -> bool:
    """O banco tem apoc.create.vRelationship (o mapa da ontologia do guia desenha setas com o nome do TTL). Leitura."""
    with _driver() as driver, _session(driver) as session:
        return bool(session.run(APOC_QUERY).single()["c"])


# --- textos para o humano --------------------------------------------------------------------------------------

LARGE_REMOVAL = 0.2  # fracao do label no banco acima da qual a CLI pede o numero digitado


def _by_label(result: dict[str, Any], state: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """label -> (nos deste projeto no banco hoje, nos previstos da origem)."""
    in_db = state.get("no_banco") or {}
    return {label: (in_db.get(label, 0), result["nodes"].get(label, 0)) for label in sorted(set(in_db) | set(result["nodes"]))}


def large_removal(result: dict[str, Any], state: dict[str, Any]) -> int:
    """Total previsto de nos removidos quando algum label perde mais de LARGE_REMOVAL do que tem no banco; 0 senao.
    Pega a origem truncada por engano (extracao que falhou) antes que a sincronizacao apague o label."""
    labels = _by_label(result, state)
    if not any(now > then and now - then > LARGE_REMOVAL * now for now, then in labels.values()):
        return 0
    return sum(now - then for now, then in labels.values() if now > then)


def _by_type(result: dict[str, Any], state: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """tipo de aresta -> (arestas deste projeto no banco hoje, arestas previstas da origem)."""
    in_db = state.get("arestas_no_banco") or {}
    planned = result["relationships"]
    return {t: (in_db.get(t, 0), planned.get(t, 0)) for t in sorted(set(in_db) | set(planned))}


def _compare(rows: dict[str, tuple[int, int]], unit: str) -> tuple[list[str], int]:
    """Linhas "banco N -> origem M", com "pelo menos K serao removidos" quando o banco tem mais."""
    lines, removed = [], 0
    for key, (now, then) in rows.items():
        line = f"  {key}: banco {now} -> origem {then}"
        if now > then:
            line += f", pelo menos {now - then} serao {unit}"
            removed += now - then
        lines.append(line)
    return lines, removed


def preview_lines(result: dict[str, Any], state: dict[str, Any] | None = None) -> list[str]:
    """Resumo que o humano le antes de confirmar a carga; com o estado do banco, compara banco e origem por label e
    por tipo de aresta."""
    warnings = warning_lines(result["sources_skipped"], result["relations_not_published"], result["warnings"])
    lines = [f"linhas: {result['rows']} em {result['batches']} lote(s) de dados, mais a ontologia", "nos previstos:"]
    lines += [f"  {label}: {n}" for label, n in result["nodes"].items()]
    lines += ["arestas previstas:"]
    lines += [f"  {relation}: {n}" for relation, n in result["relationships"].items()]
    if state is not None:
        # so leitura; "pelo menos": um no com o mesmo label e _id diferente tambem sai, e isso a contagem nao ve
        node_lines, removed = _compare(_by_label(result, state), "removidos")
        lines += ["no banco hoje, deste projeto:", *node_lines]
        if removed:
            lines.append(f"a sincronizacao apaga pelo menos {removed} no(s) deste projeto")
        if "arestas_no_banco" in state:
            edge_lines, gone = _compare(_by_type(result, state), "removidas")
            lines += ["arestas no banco hoje, deste projeto (por tipo):", *edge_lines]
            if gone:
                lines.append(f"a sincronizacao apaga pelo menos {gone} aresta(s) deste projeto")
            renamed = sorted(t for t, (now, then) in _by_type(result, state).items() if now and t not in result["relationships"])
            if renamed:
                warnings = [*warnings, f"tipo(s) de aresta no banco que esta carga nao grava: {', '.join(renamed)} (relacao "
                            "renomeada ou excluida); consultas, paineis e integracoes com esse nome deixam de achar arestas"]
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
        "     MATCH p = (:Conceito)-[:RELACAO_ONTOLOGIA]->(:Conceito) RETURN p   // a ontologia: o nome de cada seta esta em `nome`",
        "     MATCH p = (:Conceito)-[:TEM_TERMO]->(:Termo) RETURN p   // os termos de cada conceito",
        "  Clique num no de dado: _descricao, no painel de propriedades, traz a definicao da classe.",
        "  Na lateral do Browser (icone de banco), clicar num tipo de relacao traz setas com as duas pontas;",
        "  clicar num label traz so bolinhas soltas. Dois cliques numa bolinha trazem os vizinhos.",
        *guide_lines(),
    ]
