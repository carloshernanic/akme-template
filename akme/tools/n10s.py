"""Publica a ontologia e os dados no Neo4j pelo n10s (neosemantics).

O akme gera RDF correto a partir dos dados e da ontologia: IRI pela chave, valores tipados e as relacoes dos
contratos. O n10s carrega a ontologia (onto.import) e os dados (rdf.import), com nomes limpos (handleVocabUris
IGNORE). Antes da carga, o akme recusa o que perderia dados; depois, confere o banco.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator
from urllib.parse import quote, urlsplit

from ..adapters import load_adapter
from ..adapters.base import require
from ..ontology import base_ns, load_content, load_graph
from ..project import Project
from .export import build_export
from .neo4j_plan import _config
from .neo4j_plan import contract_keys as _keys
from .neo4j_plan import join_columns as _join_columns
from .neo4j_plan import labels_for as _labels
from .publish import PublishError

MAX_ROWS = 100_000
BATCH = 20_000  # triplas por chamada de rdf.import.inline
TYPES = ("string", "integer", "float", "date")
VOCAB = "IGNORE"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
INT64_MAX = 2**63 - 1
_NUMBER = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?$")
_INTEGER = re.compile(r"-?(0|[1-9]\d*)(\.0+)?$")


def name(identifier: str) -> str:
    """Identificador Cypher entre crases, usado nas consultas de conferencia."""
    return "`" + identifier.replace("`", "``") + "`"


def _comment(text: Any) -> str:
    return " ".join(str(text).split())


def _filled(value: Any) -> bool:
    return value not in (None, "")


def iri(ns: str, local: str, keys: list[Any] | tuple[Any, ...] = ()) -> str:
    """IRI em N-Triples. Nome e chave sao codificados para nao quebrar o IRI nem o nome local que o n10s le."""
    return f"<{ns}{quote(str(local), safe='')}" + "".join(f"/{quote(str(k), safe='')}" for k in keys) + ">"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def rdf_literal(kind: str, value: Any) -> str:
    """Literal N-Triples no tipo declarado. Levanta ValueError quando a conversao perderia informacao."""
    if kind == "string":
        return f'"{_escape(str(value))}"^^<{XSD}string>'
    if kind == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return f'"{value.isoformat()}"^^<{XSD}date>'
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if parsed.time() != time.min or parsed.tzinfo:
            raise ValueError(f"data com horario: {value}")
        return f'"{parsed.date().isoformat()}"^^<{XSD}date>'
    if isinstance(value, bool):
        raise ValueError(f"booleano em coluna numerica: {value}")
    text = str(value)
    if kind == "integer" and _INTEGER.match(text) and -INT64_MAX - 1 <= int(text.split(".")[0]) <= INT64_MAX:
        return f'"{int(text.split(".")[0])}"^^<{XSD}integer>'
    if kind == "float" and _NUMBER.match(text):
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"valor invalido para float: {value}") from exc
        return f'"{format(number, "f")}"^^<{XSD}decimal>'
    raise ValueError(f"valor invalido para {kind}: {value}")


def _doc_lines(model: dict[str, Any], labels: dict[str, str]) -> list[str]:
    lines = [f"# {model['project']} {model['version']}: gerado por akme publish --target neo4j, para n10s.rdf.import", ""]
    for src in model["sources"]:
        if src["name"] not in labels:
            continue
        lines.append(f"# {labels[src['name']]} (fonte {src['name']})")
        for c in src["columns"]:
            lines.append(_comment(f"#   {c['column']}: termo {c['term']}. {c['definition']}"))
        for m in src["metrics"]:
            lines.append(_comment(f"# metrica {m['term']} sobre {m['column']}: SQL de origem, nao traduzido: {m['expression']}"
                                  f" | unit={m.get('unit')} grain={m.get('grain')} additivity={m.get('additivity')}"))
            if m.get("do_not_sum_after_join_with"):
                lines.append(_comment("#   nao somar depois de juntar com: " + ", ".join(m["do_not_sum_after_join_with"])))
    lines.append("")
    return lines


def _complete_rows(source: str, rows: list[dict[str, Any]], key: list[str], problems: list[str]) -> list[dict[str, Any]]:
    """Linhas com a chave preenchida. Chave vazia ou repetida vira problema."""
    complete = [r for r in rows if all(_filled(r.get(c)) for c in key)]
    if len(complete) < len(rows):
        problems.append(f"fonte {source}: {len(rows) - len(complete)} linha(s) com chave {', '.join(key)} vazia")
    repeated = [" | ".join(v) for v, n in Counter(tuple(str(r[c]) for c in key) for r in complete).items() if n > 1]
    if repeated:
        problems.append(f"{source}.{'+'.join(key)} repete {repeated[:5]}: duas linhas virariam o mesmo no. Rode akme validate")
    return complete


def _node_triples(ns: str, source: str, label: str, key: list[str], rows: list[dict[str, Any]],
                  column_types: dict[str, str], problems: list[str]) -> list[str]:
    invalid: Counter[str] = Counter()
    examples: dict[str, Any] = {}
    triples = []
    for row in rows:
        subject = iri(ns, label, [row[c] for c in key])
        triples.append(f"{subject} {RDF_TYPE} {iri(ns, label)} .")
        for col, value in row.items():
            if not _filled(value):
                continue
            try:
                triples.append(f"{subject} {iri(ns, col)} {rdf_literal(column_types.get(col, 'string'), value)} .")
            except ValueError:
                invalid[col] += 1
                examples.setdefault(col, value)
    problems += [f"{source}.{col}: {n} valor(es) invalido(s) para {column_types[col]}, exemplo: {examples[col]}" for col, n in invalid.items()]
    return triples


def _edges(ns: str, contracts: list[dict[str, Any]], labels: dict[str, str], rows_by: dict[str, list[dict[str, Any]]],
           keys_by: dict[str, list[str]], problems: list[str], warnings: list[str]) -> tuple[list[str], dict[str, int], list[str]]:
    """Resolve cada join aqui, no Python, e gera uma tripla por par ligado. Chave estrangeira sem alvo e relatada."""
    triples: list[str] = []
    counts: dict[str, int] = {}
    not_published: list[str] = []
    for c in contracts:
        join, relation = c.get("join"), c["relation"]
        if not join or labels.get(join["from"]["source"]) != c["domain"] or labels.get(join["to"]["source"]) != c["range"]:
            not_published.append(relation)
            continue
        a, b = join["from"], join["to"]
        origin_rows, target_rows = rows_by[a["source"]], rows_by[b["source"]]
        absent = [f"{side['source']}.{side['column']}" for side, rows in ((a, origin_rows), (b, target_rows)) if rows and side["column"] not in rows[0]]
        if absent:
            problems.append(f"relacao {relation}: coluna do join nao existe nos dados: {', '.join(absent)}")
            continue
        targets: dict[str, list[str]] = {}
        for r in target_rows:
            if _filled(r.get(b["column"])):
                targets.setdefault(str(r[b["column"]]), []).append(iri(ns, c["range"], [r[k] for k in keys_by[b["source"]]]))
        origins = [r for r in origin_rows if _filled(r.get(a["column"]))]
        pairs = []
        orphans = 0
        for r in origins:
            found = targets.get(str(r[a["column"]]), [])
            orphans += not found
            subject = iri(ns, c["domain"], [r[k] for k in keys_by[a["source"]]])
            pairs += [f"{subject} {iri(ns, relation)} {target} ." for target in found]
        unique = list(dict.fromkeys(pairs))
        counts[relation] = len(unique)
        triples += unique
        if origins and orphans == len(origins):
            problems.append(f"relacao {relation}: nenhuma das {len(origins)} linha(s) de {a['source']} encontra alvo em {b['source']}")
        elif orphans:
            warnings.append(f"relacao {relation}: {orphans} de {len(origins)} linha(s) de {a['source']} sem alvo em {b['source']} ficam sem aresta")
    return triples, counts, not_published


def build(project: Project, model: dict[str, Any]) -> dict[str, Any]:
    data = build_export(project)
    contracts = data["relation_contracts"]
    ns = str(base_ns(load_graph(project.schema_path)))
    excluded, declared, types, config_problems, pending = _config(project)
    joins = _join_columns(contracts)
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    triples: list[str] = []
    nodes: dict[str, int] = {}
    warnings: list[str] = []
    rows_by: dict[str, list[dict[str, Any]]] = {}
    keys_by: dict[str, list[str]] = {}
    try:
        sources = adapter.list_sources()
        labels, problems = _labels(data, project, sources, excluded)
        problems = config_problems + problems
        problems += [f"etapa 5 cita fonte inexistente: {source}" for source in declared if source not in sources]
        problems += [f"etapa 5: tipo desconhecido {kind} em {source}.{column}; use {', '.join(TYPES)}"
                     for source, columns in types.items() for column, kind in columns.items() if kind not in TYPES]
        for source, label in sorted(labels.items()):
            rows = adapter.read_sample(source, MAX_ROWS + 1)
            if len(rows) > MAX_ROWS:
                problems.append(f"fonte {source} truncada: tem mais de {MAX_ROWS} linhas")
                rows = rows[:MAX_ROWS]
            key = declared.get(source) or []
            if source not in declared:
                problems.append(f"fonte {source} sem chave e tipos aprovados na etapa 5: " + (
                    "ha proposta pendente na pagina de revisao" if source in pending
                    else "rode suggest_sources e decida na pagina de revisao"))
            elif not key:
                problems.append(f"fonte {source} sem chave na decisao da etapa 5")
            absent = [c for c in key if rows and c not in rows[0]]
            if absent:
                problems.append(f"fonte {source}: chave declarada usa coluna inexistente: {', '.join(absent)}")
                key = []
            if key:
                rows = _complete_rows(source, rows, key, problems)
            protected = joins | {(source, c) for c in key}
            column_types = {c: kind for c, kind in types.get(source, {}).items() if kind in TYPES}
            problems += [f"etapa 5 cita coluna inexistente: {source}.{c}" for c in column_types if rows and c not in rows[0]]
            problems += [f"{source}.{c} e chave ou join e precisa ser string, nao {kind}"
                         for c, kind in column_types.items() if (source, c) in protected and kind != "string"]
            metrics = sorted({m["column"] for m in data["mappings"] if m["source"] == source and m.get("role") == "metric" and m.get("column")})
            warnings += [f"{source}.{c} e medida, mas fica como texto e nao soma: declare o tipo na etapa 5"
                         for c in metrics if rows and c in rows[0] and column_types.get(c, "string") == "string"]
            renamed = [c for c in (rows[0] if rows else {}) if quote(c, safe="") != c]
            warnings += [f"{source}.{c} vira a propriedade {quote(c, safe='')} no Neo4j, por causa de caracteres especiais" for c in renamed]
            if key:
                triples += _node_triples(ns, source, label, key, rows, column_types, problems)
            nodes[label] = len(rows)
            rows_by[source], keys_by[source] = rows, key
    finally:
        adapter.close()
    edge_sources = {s for s, k in keys_by.items() if k}
    edges, relationships, not_published = _edges(ns, contracts, {s: l for s, l in labels.items() if s in edge_sources},
                                                 rows_by, keys_by, problems, warnings)
    return {"triples": triples + edges, "doc": _doc_lines(model, labels),
            "nodes": dict(sorted(nodes.items())), "relationships": dict(sorted(relationships.items())),
            "relations_not_published": not_published, "sources_skipped": sorted(excluded),
            "problems": problems, "warnings": warnings}


def _connection() -> tuple[str, str, str]:
    values = {var: os.environ.get(var) for var in ("AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD")}
    missing = [var for var, value in values.items() if not value]
    if missing:
        raise RuntimeError("publish neo4j --no-dry-run exige " + ", ".join(missing))
    return values["AKME_NEO4J_URI"], values["AKME_NEO4J_USER"], values["AKME_NEO4J_PASSWORD"]


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
        raise PublishError(f"falha no Neo4j: {exc}") from None


MARKER = "_AkmeProjeto"
# Labels e propriedade como texto: num banco vazio eles ainda nao existem, e o servidor avisaria a cada consulta.
STATE_QUERY = (f"RETURN COLLECT {{ MATCH (m) WHERE '{MARKER}' IN labels(m) RETURN m[$prop] }} AS projetos, "
               "COUNT { MATCH (n) } AS total, "
               f"COUNT {{ MATCH (n) WHERE NONE(l IN labels(n) WHERE l IN ['Resource', '_GraphConfig', '{MARKER}']) }} AS alheios")


def check_destination(state: dict[str, Any], project_name: str) -> tuple[str, str | None]:
    """Descreve o banco e diz por que recusar. So aceita banco vazio ou com a marca deste mesmo projeto."""
    projetos, total, alheios = state["projetos"], state["total"], state["alheios"]
    if not projetos and not total:
        return "vazio", None
    if len(projetos) > 1:
        return f"projetos {', '.join(projetos)}", f"o banco tem mais de um projeto do akme: {', '.join(projetos)}"
    if not projetos:
        return f"{total} no(s) sem marca do akme", f"o banco tem {total} no(s) sem a marca de um projeto do akme; use um banco vazio"
    if projetos[0] != project_name:
        return f"projeto {projetos[0]}", f"o banco ja tem o projeto {projetos[0]}; use outro banco ou limpe este"
    if alheios:
        return f"projeto {project_name}", f"o banco tem {alheios} no(s) que nao vieram do akme nem do n10s"
    return f"projeto {project_name}, sera atualizado", None


def destination_state(project: Project) -> dict[str, Any]:
    """Le o estado do banco antes da confirmacao. Somente leitura."""
    with _driver() as driver:
        return dict(driver.execute_query(STATE_QUERY, prop="projeto", routing_="r").records[0])


def _prepare(session: Any, project: Project) -> None:
    """Confere plugin e destino, cria a unicidade por IRI, marca o projeto e carrega a ontologia."""
    found = list(session.run("SHOW PROCEDURES YIELD name WHERE name IN ['n10s.rdf.import.inline', 'n10s.onto.import.inline'] "
                             "RETURN count(name) AS c"))
    if not found or found[0]["c"] < 2:
        raise PublishError("o servidor nao tem o plugin n10s; instale-o em /plugins (ver docs/neo4j/exportacao.md). Nada foi gravado")
    state = list(session.run(STATE_QUERY, prop="projeto"))[0]
    _, refusal = check_destination(dict(state), project.name)
    if refusal:
        raise PublishError(f"{refusal}. Nada foi gravado")
    session.run("CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE").consume()
    config = {r["param"]: r["value"] for r in session.run("CALL n10s.graphconfig.show() YIELD param, value RETURN param, value")}
    if not config:
        session.run("CALL n10s.graphconfig.init({handleVocabUris: $vocab})", vocab=VOCAB).consume()
    elif config.get("handleVocabUris") != VOCAB:
        raise PublishError(f"o grafo usa handleVocabUris={config.get('handleVocabUris')}, e o akme exige {VOCAB}. Nada foi gravado")
    session.run(f"MERGE (m:{MARKER} {{projeto: $projeto}})", projeto=project.name).consume()
    onto = list(session.run("CALL n10s.onto.import.inline($ttl, 'Turtle') YIELD terminationStatus, extraInfo "
                            "RETURN terminationStatus, extraInfo", ttl=project.schema_path.read_text(encoding="utf-8")))
    if not onto or onto[0]["terminationStatus"] != "OK":
        raise PublishError(f"n10s nao importou a ontologia: {onto[0] if onto else 'sem resposta'}")


def _run(project: Project, batches: list[str]) -> int:
    """Prepara o grafo e importa os lotes. Uma falha diz quantos lotes ja ficaram gravados."""
    with _driver() as driver, driver.session() as session:
        import neo4j  # so existe depois que _driver confirmou o extra

        _prepare(session, project)
        for done, batch in enumerate(batches):
            written = (f"{done} lote(s) anterior(es) ja gravado(s); o grafo pode estar incompleto" if done
                       else "nenhum lote de dados foi gravado; so a ontologia e a configuracao")
            try:
                out = list(session.run("CALL n10s.rdf.import.inline($rdf, 'N-Triples') "
                                       "YIELD terminationStatus, triplesParsed, triplesLoaded, extraInfo "
                                       "RETURN terminationStatus, triplesParsed, triplesLoaded, extraInfo", rdf=batch))
            except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError) as exc:
                raise PublishError(f"lote {done + 1} de {len(batches)} falhou: {exc}. {written}") from None
            expected = batch.count("\n")
            status = out[0] if out else {}
            if status.get("terminationStatus") != "OK" or status.get("triplesLoaded") != expected:
                raise PublishError(f"lote {done + 1} de {len(batches)}: n10s respondeu {status.get('terminationStatus')} e carregou "
                                   f"{status.get('triplesLoaded')} de {expected} triplas ({status.get('extraInfo')}). {written}")
    return len(batches)


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
        "     MATCH (n)-[r]->(m) WHERE NOT n:Class AND NOT n:Relationship RETURN n, r, m LIMIT 300   // os dados",
        "     MATCH p = (:Class)-[:SCO]->(:Class) RETURN p   // a ontologia, com a definicao de cada classe",
        "  Na lateral do Browser, o icone de banco lista labels e relacoes; clique em um para ver os nos.",
    ]


def preview_lines(result: dict[str, Any]) -> list[str]:
    """Resumo que o humano le antes de confirmar a carga."""
    warnings = [f"fonte excluida na etapa 5: {source}" for source in result["sources_skipped"]]
    warnings += [f"relacao nao publicada: {relation}" for relation in result["relations_not_published"]]
    warnings += result["warnings"]
    lines = [f"triplas: {result['triples']} em {result['batches']} lote(s), mais a ontologia", "nos previstos:"]
    lines += [f"  {label}: {n}" for label, n in result["nodes"].items()]
    lines += ["arestas previstas:"]
    lines += [f"  {relation}: {n}" for relation, n in result["relationships"].items()]
    lines += ["avisos:", *[f"  {w}" for w in warnings]] if warnings else ["avisos: nenhum"]
    return lines + (["problemas (a carga sera recusada):", *[f"  {p}" for p in result["problems"]]] if result["problems"] else [])


def _observed(labels: list[str], types: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """Conta no banco, depois da carga, os labels e tipos de aresta previstos. Somente leitura."""
    with _driver() as driver:
        def count(query: str) -> int:
            return driver.execute_query(query, routing_="r").records[0]["c"]

        nodes = {label: count(f"MATCH (n:{name(label)}) WHERE NOT n:Class RETURN count(n) AS c") for label in labels}
        edges = {kind: count(f"MATCH ()-[r:{name(kind)}]->() RETURN count(r) AS c") for kind in types}
    return nodes, edges


def _verify(built: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _observed(list(built["nodes"]), list(built["relationships"]))
    observed = {**nodes, **edges}
    expected = {**built["nodes"], **built["relationships"]}
    divergences = [f"{k}: esperado {n}, encontrado {observed.get(k)}" for k, n in expected.items() if observed.get(k) != n]
    return {"ok": not divergences, "divergences": divergences}


def publish_neo4j(project: Project, model: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    built = build(project, model)
    triples = built["triples"]
    batches = ["\n".join(triples[i:i + BATCH]) + "\n" for i in range(0, len(triples), BATCH)]
    out = project.docs_dir / "publish" / "neo4j.nt"
    header = ["# NAO EXECUTE: a carga seria recusada. Problemas:", *[_comment(f"#   {p}") for p in built["problems"]], ""] if built["problems"] else []
    out.write_text("\n".join(header + built["doc"] + triples) + "\n", encoding="utf-8")
    result = {"target": "neo4j", "dry_run": dry_run, "artifact": str(out), "triples": len(triples), "batches": len(batches),
              "executed": 0, **{k: built[k] for k in ("nodes", "relationships", "relations_not_published", "sources_skipped",
                                                       "problems", "warnings")}}
    if dry_run:
        return result
    if built["problems"]:
        raise PublishError("carga recusada, nada foi gravado: " + "; ".join(built["problems"]))
    result["executed"] = _run(project, batches)
    result["verification"] = _verify(built)
    if not result["verification"]["ok"]:
        raise PublishError("carga executada, mas o banco diverge do previsto: " + "; ".join(result["verification"]["divergences"]))
    return result
