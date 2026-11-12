"""Plano da carga no Neo4j (dry-run), sem conectar ao banco.

Le cada fonte uma vez, em blocos e sem teto de linhas, e confere o que a carga perderia ou juntaria errado. Guarda
so o _id de cada linha (para achar chave repetida) e, por coluna de join, quantas linhas tem cada valor: com isso
conta as arestas esperadas sem guardar as linhas. Nada e decidido em silencio: o que recusaria a carga vira
problema, o que a carga aceita mas o humano deve saber vira aviso.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import chain
from typing import Any

from ..adapters import load_adapter
from ..adapters.base import check_batch
from ..ontology import classes, is_metric_class, load_content, load_graph
from ..project import Project
from .export import build_export
from .neo4j_onto import ONTOLOGY_TYPE
from .neo4j_values import TYPES, convert, filled, name, node_id

RESERVED_LABELS = ("Conceito", "Termo", "_AkmeProjeto")
META_TYPES = (ONTOLOGY_TYPE, "SUBCLASSE_DE", "TEM_TERMO")  # tipos de aresta da camada de ontologia
RESERVED_PROPS = ("_id", "_projeto", "_carga", "_descricao")
BATCH = 5000  # linhas por bloco de leitura
EXAMPLES = 5  # exemplos de chave repetida citados no problema


@dataclass(frozen=True)
class SourcePlan:
    source: str
    label: str
    key: list[str]
    types: dict[str, str]
    columns: list[str]
    rows: int
    caption: str | None = None  # coluna que completa a legenda `name` (ver caption_column)
    own_name: bool = False  # a fonte tem coluna `name`: ela vale como legenda; o akme so grava a sua onde ela esta vazia


@dataclass(frozen=True)
class EdgePlan:
    relation: str
    domain: str
    range: str
    from_source: str
    from_column: str
    to_source: str
    to_column: str
    expected: int


@dataclass
class Plan:
    project: str
    sources: list[SourcePlan] = field(default_factory=list)
    edges: list[EdgePlan] = field(default_factory=list)
    nodes: dict[str, int] = field(default_factory=dict)
    relationships: dict[str, int] = field(default_factory=dict)
    relations_not_published: list[str] = field(default_factory=list)
    sources_skipped: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows: int = 0


def join_columns(contracts: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Pares (fonte, coluna) usados em algum join de contrato."""
    return {(c["join"][side]["source"], c["join"][side]["column"]) for c in contracts if c.get("join") for side in ("from", "to")}


def labels_for(data: dict[str, Any], project: Project, sources: list[str], excluded: list[str]) -> tuple[dict[str, str], list[str]]:
    """Cada fonte vira uma classe. Classe ausente, ambigua ou repetida e problema: nao se escolhe em silencio."""
    candidates: dict[str, list[str]] = {}

    def add(source: str, label: str) -> None:
        if label not in candidates.setdefault(source, []):
            candidates[source].append(label)

    for c in data["relation_contracts"]:
        if c.get("join"):
            add(c["join"]["from"]["source"], c["domain"])
            add(c["join"]["to"]["source"], c["range"])
    g = load_graph(project.schema_path)
    term_class = {t["name"]: t.get("class") for t in data["terms"]}
    for m in data["mappings"]:
        cls = term_class.get(m["term"])
        if cls and m.get("role") != "metric" and not is_metric_class(g, cls):
            add(m["source"], cls)

    problems = [f"etapa 5 exclui fonte inexistente: {source}" for source in excluded if source not in sources]
    problems += [f"fonte {source} sem classe associada: mapeie a fonte ou exclua na etapa 5 (add_source com exclude)"
                 for source in sources if source not in candidates and source not in excluded]
    labels: dict[str, str] = {}
    for source, options in sorted(candidates.items()):
        if source in excluded:
            continue
        if source not in sources:
            problems.append(f"fonte {source} citada na ontologia, mas nao existe no adapter")
            continue
        if len(options) > 1:
            problems.append(f"fonte {source} com mais de uma classe: {', '.join(sorted(options))}")
        labels[source] = options[0]
    by_label: dict[str, list[str]] = {}
    for source, label in labels.items():
        by_label.setdefault(label, []).append(source)
    problems += [f"classe {label} em mais de uma fonte: {', '.join(names)}" for label, names in sorted(by_label.items()) if len(names) > 1]
    return labels, problems


def contract_keys(contracts: list[dict[str, Any]]) -> dict[str, str]:
    """A chave de uma fonte e a coluna do lado one nas relacoes com join."""
    keys: dict[str, str] = {}
    for c in contracts:
        join, mult = c.get("join"), c.get("multiplicity")
        if not join or mult == "many_to_many":
            continue
        side = join["from"] if mult == "one_to_many" else join["to"]
        keys.setdefault(side["source"], side["column"])
    return keys


def _config(project: Project) -> tuple[list[str], dict[str, list[str]], dict[str, dict[str, str]], list[str], set[str]]:
    """Chave e tipos aprovados na etapa 5 (secao sources do content.yml). O akme.yml nao guarda mais isso."""
    from .ontology_write import list_pending

    entries = {e["source"]: e for e in load_content(project)["sources"]}
    excluded = sorted(s for s, e in entries.items() if e.get("exclude"))
    keys = {s: [e["key"]] if isinstance(e.get("key"), str) else list(e.get("key") or []) for s, e in entries.items() if not e.get("exclude")}
    types = {s: dict(e.get("types") or {}) for s, e in entries.items() if not e.get("exclude")}
    pending = {e.payload.get("source") for e in list_pending(project) if e.type.value == "add_source"}
    problems = ["o bloco neo4j do akme.yml nao e mais lido: chave e tipos de cada fonte agora sao decididos na etapa 5 "
                "(suggest_sources e add_source); remova o bloco"] if project.config.get("neo4j") else []
    return excluded, keys, types, problems, pending


@dataclass
class Scan:
    """O que uma leitura da fonte deixa na memoria: contagens, exemplos e um _id por linha, nunca as linhas."""
    columns: list[str]
    key: list[str]
    absent: list[str]
    rows: int = 0
    complete: int = 0  # linhas com a chave toda preenchida
    seen: set[str] = field(default_factory=set)
    repeated_ids: set[str] = field(default_factory=set)  # so os _id que aparecem mais de uma vez
    repeated: list[str] = field(default_factory=list)  # exemplos legiveis, no maximo EXAMPLES
    invalid: Counter[str] = field(default_factory=Counter)
    examples: dict[str, Any] = field(default_factory=dict)  # primeiro valor invalido por coluna
    filled: Counter[str] = field(default_factory=Counter)  # valores preenchidos por coluna tipada
    first: dict[str, Any] = field(default_factory=dict)  # primeiro valor preenchido por coluna tipada
    values: dict[str, Counter[str]] = field(default_factory=dict)
    ragged: tuple[int, int] | None = None  # (linhas com colunas a mais ou a menos, numero da primeira no arquivo)


def scan_source(adapter: Any, source: str, declared: list[str], column_types: dict[str, str],
                joins: frozenset[tuple[str, str]] | set[tuple[str, str]] = frozenset(),
                batch: int = BATCH) -> Scan:
    """Uma passada pela fonte inteira, em blocos. E o unico leitor das regras de chave e tipo: o plano da carga e o
    add_source (etapa 5) usam este, entao nao divergem. A chave so e conferida depois do primeiro bloco, que diz
    quais colunas existem. O gerador e esgotado ou fechado antes de voltar (cursor e arquivo nao ficam abertos).
    """
    check_batch(batch)
    blocks = adapter.iter_rows(source, batch)
    try:
        first = next(blocks, None)
        if first:
            columns = list(first[0])
        else:
            # fonte vazia: as colunas vem do esquema, para chave, tipo ou join errado nao passarem em silencio
            columns = [c["name"] for c in adapter.read_schema(source)["columns"]]
        absent = [c for c in declared if columns and c not in columns]
        key = [] if absent else list(declared)
        state = Scan(columns=columns, key=key, absent=absent,
                     values={c: Counter() for s, c in joins if s == source and c in columns})
        typed = {c: kind for c, kind in column_types.items() if kind in TYPES}
        for block in chain([first] if first else [], blocks):
            state.rows += len(block)
            if not key:
                continue
            for row in block:
                if not all(filled(row.get(c)) for c in key):
                    continue
                state.complete += 1
                identity = node_id([row[c] for c in key])
                if identity in state.seen:
                    if identity not in state.repeated_ids:
                        state.repeated_ids.add(identity)
                        if len(state.repeated) < EXAMPLES:
                            state.repeated.append(" | ".join(str(row[c]) for c in key))
                else:
                    state.seen.add(identity)
                for col, kind in typed.items():
                    value = row.get(col)
                    if not filled(value):
                        continue
                    state.filled[col] += 1
                    state.first.setdefault(col, value)
                    if kind == "string":
                        continue  # texto sempre converte
                    try:
                        convert(kind, value)
                    except ValueError:
                        state.invalid[col] += 1
                        state.examples.setdefault(col, value)
                for col, counter in state.values.items():
                    if filled(row.get(col)):
                        counter[str(row[col])] += 1
        state.seen = set()  # so servia para achar repeticao; libera a memoria antes da proxima fonte
        state.ragged = (getattr(adapter, "ragged", None) or {}).get(source)
        return state
    finally:
        close = getattr(blocks, "close", None)
        if close:
            close()


def ragged_problem(source: str, ragged: tuple[int, int]) -> str:
    """Texto da recusa de linha malformada, igual no plano e no add_source (etapa 5)."""
    return f"{ragged[0]} linha(s) de {source} com colunas a mais ou a menos; primeira: linha {ragged[1]}"


def identifier_problems(plan: Plan, contracts: list[dict[str, Any]]) -> list[str]:
    """Nomes que entram no texto do Cypher (labels, relacoes, colunas do join) e que name() recusa."""
    names = ([(f"classe {label}", label) for label in plan.nodes]
             + [(f"relacao {c['relation']}", c["relation"]) for c in contracts if c.get("relation")]
             + [(f"coluna do join {e.to_source}.{e.to_column}", e.to_column) for e in plan.edges])
    problems = []
    for shown, identifier in dict.fromkeys(names):
        try:
            name(identifier)
        except ValueError as exc:
            problems.append(f"{shown}: {exc}")
    return problems


def type_problems(contracts: list[dict[str, Any]]) -> list[str]:
    """Relacao com o nome de um tipo da camada de ontologia (RELACAO_ONTOLOGIA, SUBCLASSE_DE, TEM_TERMO) juntaria
    arestas de dado com as setas entre Conceito no mesmo tipo: vira problema."""
    return [f"relacao {r} tem o nome de um tipo reservado da camada de ontologia do akme; renomeie a relacao"
            for r in sorted({c["relation"] for c in contracts if c.get("relation")}) if r in META_TYPES]


def caption_column(mappings: list[dict[str, Any]], source: str, key: list[str], joins: set[tuple[str, str]],
                   columns: list[str]) -> str | None:
    """Coluna que completa a legenda `name` de cada no: a primeira coluna mapeada da fonte, na ordem do content.yml,
    que existe nos dados e nao e chave nem join (identificadores ja estao no inicio da legenda)."""
    for m in mappings:
        column = m.get("column")
        if m.get("source") == source and column in columns and column not in key and (source, column) not in joins:
            return column
    return None


def metric_warnings(data: dict[str, Any], graph: Any) -> list[str]:
    """Classe de metrica com varios mappings de papel metric: no Conceito vale so o primeiro na ordem do content.yml."""
    term_class = {t["name"]: t.get("class") for t in data["terms"]}
    by_class: dict[str, list[dict[str, Any]]] = {}
    for m in data["mappings"]:
        cls = term_class.get(m.get("term"))
        if cls and m.get("role") == "metric" and is_metric_class(graph, cls):
            by_class.setdefault(cls, []).append(m)
    return [f"classe {cls} tem {len(maps)} mappings de metrica; no Conceito vale o primeiro "
            f"({maps[0]['term']} em {maps[0].get('source')}.{maps[0].get('column')})"
            for cls, maps in sorted(by_class.items()) if len(maps) > 1]


def _edges(plan: Plan, contracts: list[dict[str, Any]], labels: dict[str, str], read: dict[str, Scan]) -> None:
    """Arestas esperadas por contrato, das contagens por valor: soma de origem[v] * alvo[v]. Vale porque a chave e
    unica dos dois lados (chave repetida ja e problema), entao cada par ligado e distinto."""
    counts: dict[str, int] = {}
    for c in contracts:
        join, relation = c.get("join"), c["relation"]
        if not join or labels.get(join["from"]["source"]) != c["domain"] or labels.get(join["to"]["source"]) != c["range"]:
            plan.relations_not_published.append(relation)
            continue
        a, b = join["from"], join["to"]
        sides = ((a, read[a["source"]]), (b, read[b["source"]]))
        absent = [f"{side['source']}.{side['column']}" for side, r in sides if r.columns and side["column"] not in r.columns]
        if absent:
            plan.problems.append(f"relacao {relation}: coluna do join nao existe nos dados: {', '.join(absent)}")
            continue
        origin = read[a["source"]].values.get(a["column"], Counter())
        target = read[b["source"]].values.get(b["column"], Counter())
        expected = sum(n * target[v] for v, n in origin.items() if v in target)
        orphans = sum(n for v, n in origin.items() if v not in target)
        total = sum(origin.values())
        counts[relation] = expected
        plan.edges.append(EdgePlan(relation, c["domain"], c["range"], a["source"], a["column"], b["source"], b["column"], expected))
        if total and orphans == total:
            plan.problems.append(f"relacao {relation}: nenhuma das {total} linha(s) de {a['source']} encontra alvo em {b['source']}")
        elif orphans:
            plan.warnings.append(f"relacao {relation}: {orphans} de {total} linha(s) de {a['source']} sem alvo em {b['source']} ficam sem aresta")
    plan.relationships = dict(sorted(counts.items()))


def build_plan(project: Project, batch: int = BATCH) -> Plan:
    """Le todas as fontes em blocos e devolve o plano da carga, com problemas (recusam) e avisos (aceitam)."""
    check_batch(batch)
    data = build_export(project)
    contracts = data["relation_contracts"]
    excluded, declared, types, config_problems, pending = _config(project)
    joins = join_columns(contracts)
    plan = Plan(project=project.name, sources_skipped=sorted(excluded))
    reserved = [c["name"] for c in classes(load_graph(project.schema_path)) if c["name"] in RESERVED_LABELS]
    read: dict[str, Scan] = {}
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        sources = adapter.list_sources()
        labels, label_problems = labels_for(data, project, sources, excluded)
        problems = plan.problems
        problems += config_problems + label_problems
        problems += [f"classe {name} usa nome reservado do akme no Neo4j" for name in reserved]
        problems += [f"etapa 5 cita fonte inexistente: {source}" for source in declared if source not in sources]
        problems += [f"etapa 5: tipo desconhecido {kind} em {source}.{column}; use {', '.join(TYPES)}"
                     for source, columns in types.items() for column, kind in columns.items() if kind not in TYPES]
        for source, label in sorted(labels.items()):
            if source not in declared:
                problems.append(f"fonte {source} sem chave e tipos aprovados na etapa 5: " + (
                    "ha proposta pendente na pagina de revisao" if source in pending
                    else "rode suggest_sources e decida na pagina de revisao"))
            elif not declared[source]:
                problems.append(f"fonte {source} sem chave na decisao da etapa 5")
            column_types = {c: kind for c, kind in types.get(source, {}).items() if kind in TYPES}
            state = scan_source(adapter, source, declared.get(source) or [], column_types, joins, batch)
            key, columns = state.key, state.columns
            if state.ragged:
                problems.append(ragged_problem(source, state.ragged))
            if declared.get(source) and not state.rows:
                # origem truncada por engano (extracao que falhou) apagaria o label inteiro na sincronizacao
                problems.append(f"fonte {source} sem linhas: a carga apagaria do banco todos os nos de {label}; "
                                "confira a extracao ou exclua a fonte na etapa 5")
            if state.absent:
                problems.append(f"fonte {source}: chave declarada usa coluna inexistente: {', '.join(state.absent)}")
            problems += [f"{source}.{c} usa nome reservado do akme no Neo4j" for c in columns if c in RESERVED_PROPS]
            if key and state.complete < state.rows:
                problems.append(f"fonte {source}: {state.rows - state.complete} linha(s) com chave {', '.join(key)} vazia")
            if state.repeated:
                problems.append(f"{source}.{'+'.join(key)} repete {state.repeated}: duas linhas virariam o mesmo no. Rode akme validate")
            protected = joins | {(source, c) for c in key}
            problems += [f"etapa 5 cita coluna inexistente: {source}.{c}" for c in column_types if columns and c not in columns]
            problems += [f"{source}.{c} e chave ou join e precisa ser string, nao {kind}"
                         for c, kind in column_types.items() if (source, c) in protected and kind != "string"]
            metrics = sorted({m["column"] for m in data["mappings"] if m["source"] == source and m.get("role") == "metric" and m.get("column")})
            plan.warnings += [f"{source}.{c} e medida, mas fica como texto e nao soma: declare o tipo na etapa 5"
                              for c in metrics if c in columns and column_types.get(c, "string") == "string"]
            problems += [f"{source}.{col}: {n} valor(es) invalido(s) para {column_types[col]}, exemplo: {state.examples[col]}"
                         for col, n in state.invalid.items()]
            plan.nodes[label] = state.complete if key else state.rows
            plan.rows += state.rows
            own_name = "name" in columns
            if own_name:
                plan.warnings.append(f"fonte {source} tem coluna name: ela vale como legenda dos nos de {label} no "
                                     "Browser; o akme so grava a sua nas linhas com name vazio")
            caption = caption_column(data["mappings"], source, list(key), joins, columns)
            plan.sources.append(SourcePlan(source, label, list(key), column_types, columns, state.rows, caption, own_name))
            read[source] = state
    finally:
        adapter.close()
    plan.nodes = dict(sorted(plan.nodes.items()))
    edge_labels = {s.source: s.label for s in plan.sources if s.key}
    _edges(plan, contracts, edge_labels, read)
    plan.problems += identifier_problems(plan, contracts) + type_problems(contracts)
    plan.warnings += metric_warnings(data, load_graph(project.schema_path))
    return plan
