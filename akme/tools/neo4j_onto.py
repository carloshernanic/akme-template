"""Camada de ontologia no Neo4j, espelho do schema.ttl: um no :Conceito por classe, SUBCLASSE_DE por rdfs:subClassOf,
uma seta RELACAO_ONTOLOGIA {nome} por owl:ObjectProperty (e por par domain/range) e um no
:Termo por termo do content.yml, ligado ao seu Conceito por TEM_TERMO.

Devolve statements (texto Cypher, parametros) deterministicos. Texto vindo do cliente ou da ontologia vai sempre como
parametro; so identificadores (nome da relacao) entram no texto, pelo name() de neo4j_values. A carga (Task 6)
acrescenta $projeto e $carga; render escreve o texto legivel para o artefato de dry-run, sem executar nada.
"""
from __future__ import annotations

import math
import re
from typing import Any

from ..ontology import classes, is_metric_class, load_content, load_graph, relations
from ..project import Project
from .contracts import fanout_sources
from .neo4j_values import name

_FLIP = {"many_to_one": "one_to_many", "one_to_many": "many_to_one"}  # multiplicidade lida ao contrario
ONTOLOGY_TYPE = "RELACAO_ONTOLOGIA"  # tipo unico das setas entre Conceito; o nome da relacao fica em `nome`

Statement = tuple[str, dict[str, Any]]

_CONCEITO = "(c:Conceito {_projeto: $projeto, nome: $nome})"
_A = "(a:Conceito {_projeto: $projeto, nome: $de})"
_B = "(b:Conceito {_projeto: $projeto, nome: $para})"
_TERMO = "(t:Termo {_projeto: $projeto, nome: $nome})"


def descriptions(project: Project) -> tuple[dict[str, str], dict[str, str]]:
    """Texto de `_descricao` nos dados: classe -> rdfs:comment; relacao -> rdfs:comment ou, sem ele, o rdfs:label.
    Sem texto, a classe ou relacao fica de fora (a propriedade nao e gravada)."""
    g = load_graph(project.schema_path)
    nodes = {c["name"]: c["comment"] for c in classes(g) if c["comment"]}
    edges = {r["name"]: r["comment"] or r["label"] for r in relations(g) if r["comment"] or r["label"]}
    return nodes, edges


def join_labels(sources: list[str], labels: dict[str, str]) -> list[str]:
    """Fontes de "nao somar apos juntar com" como labels do grafo; fonte sem no publicado fica nomeada como fonte."""
    return [labels[s] if s in labels else f"fonte {s} (nao publicada)" for s in sources]


def term_entries(content: dict[str, Any], concepts: set[str]) -> list[tuple[str, str, dict[str, Any]]]:
    """(classe, termo, propriedades do no :Termo) dos termos cuja classe e um Conceito exportado, por nome.

    fonte/coluna vem do mapping; com varios mappings, listas fontes/colunas ordenadas pelo par. papel e o do primeiro
    mapping na ordem do content.yml. Campos vazios ficam ausentes.
    """
    by_term: dict[str, list[dict[str, Any]]] = {}
    for m in content["mappings"]:
        by_term.setdefault(m.get("term"), []).append(m)
    out = []
    for term in sorted(content["terms"], key=lambda t: t["name"]):
        cls = term.get("class")
        if cls not in concepts:
            continue
        maps = by_term.get(term["name"], [])
        props: dict[str, Any] = {"nome": term["name"], "name": term["name"]}
        for key, value in (("definicao", term.get("definition")), ("sinonimos", [x for x in term.get("synonyms") or [] if x]),
                           ("unidade", term.get("unit")), ("grao", term.get("grain")),
                           ("aditividade", term.get("additivity"))):
            if value:
                props[key] = value
        pairs = sorted({(m["source"], m["column"]) for m in maps if m.get("source") and m.get("column")})
        if len(pairs) == 1:
            props |= {"fonte": pairs[0][0], "coluna": pairs[0][1]}
        elif pairs:
            props |= {"fontes": [s for s, _ in pairs], "colunas": [c for _, c in pairs]}
        if maps and maps[0].get("role"):
            props["papel"] = maps[0]["role"]
        out.append((cls, term["name"], props))
    return out


def _metric_props(content: dict[str, Any], contracts: list[dict[str, Any]], cls: str,
                  labels: dict[str, str]) -> dict[str, Any]:
    """Contrato da metrica: termo da classe com mapping de papel metric. So os campos presentes.

    Se a classe tiver varios mappings de papel metric, vale o primeiro na ordem do content.yml. As fontes de
    "nao somar apos juntar com" saem como labels do grafo (`labels`: fonte -> label do plano).
    """
    terms = {t["name"]: t for t in content["terms"] if t.get("class") == cls}
    for m in content["mappings"]:
        term = terms.get(m.get("term"))
        if term is None or m.get("role") != "metric":
            continue
        props: dict[str, Any] = {}
        for key, value in (("expressao", m.get("expression")), ("unidade", term.get("unit")),
                           ("grao", term.get("grain")), ("aditividade", term.get("additivity")),
                           ("nao_somar_sobre", list(term.get("non_additive_over") or []))):
            if value:
                props[key] = value
        fan = fanout_sources(contracts, m["source"])
        if fan:
            props["nao_somar_apos_juntar_com"] = join_labels(fan, labels)
        return props
    return {}


def ontology_statements(project: Project, published: set[str], labels: dict[str, str] | None = None) -> list[Statement]:
    """`published`: relacoes com aresta de dado; `labels`: fonte -> label do plano (fonte ausente = nao publicada)."""
    labels = labels or {}
    g = load_graph(project.schema_path)
    content = load_content(project)
    contracts = content["relation_contracts"]
    cls_list = sorted(classes(g), key=lambda c: c["name"])
    names = {c["name"] for c in cls_list}
    rels = {r["name"]: r for r in relations(g)}
    out: list[Statement] = []

    for c in cls_list:
        props: dict[str, Any] = {"nome": c["name"], "name": c["name"], "rotulo": c["label"], "definicao": c["comment"],
                                 "iri": c["iri"]}
        if is_metric_class(g, c["name"]):
            props |= _metric_props(content, contracts, c["name"], labels)
        out.append((f"MERGE {_CONCEITO} SET c = $props, c._projeto = $projeto, c._carga = $carga",
                    {"nome": c["name"], "props": props}))

    for c in cls_list:
        for parent in sorted(set(c["subclass_of"])):
            if parent in names:
                out.append((f"MATCH {_A}, {_B} MERGE (a)-[r:SUBCLASSE_DE]->(b) SET r._carga = $carga",
                            {"de": c["name"], "para": parent}))

    # espelho do schema.ttl, como o grafo da ontologia da pagina (graph.js): uma seta por owl:ObjectProperty e por par
    # (domain, range) de classes, inversas incluidas. O contrato acrescenta multiplicidade; a inversa de um contrato
    # recebe a multiplicidade lida ao contrario e `inversa_de`. So relacao publicada tem aresta de dado.
    by_contract = {c["relation"]: c for c in contracts}
    inverse_of: dict[str, str] = {}
    for r in rels.values():
        for other in r["inverse_of"]:
            inverse_of.setdefault(r["name"], other)
            inverse_of.setdefault(other, r["name"])
    for c in contracts:
        if c.get("inverse_of"):
            inverse_of[c["relation"]] = c["inverse_of"]
            inverse_of.setdefault(c["inverse_of"], c["relation"])
    arrows: list[tuple[str, str, str, dict[str, Any]]] = []
    for rel in sorted(rels):
        info = rels[rel]
        inverse = inverse_of.get(rel, "")
        props: dict[str, Any] = {"nome": rel, "rotulo": info.get("label", ""), "definicao": info.get("comment", ""),
                                 "inversa": inverse, "publicada_nos_dados": rel in published}
        if rel in by_contract:
            props["multiplicidade"] = by_contract[rel].get("multiplicity") or ""
        elif inverse in by_contract:
            props["inversa_de"] = inverse
            multiplicity = by_contract[inverse].get("multiplicity") or ""
            props["multiplicidade"] = _FLIP.get(multiplicity, multiplicity)
        for dom in sorted(set(info["domain"])):
            for rng in sorted(set(info["range"])):
                if dom in names and rng in names:
                    arrows.append((rel, dom, rng, props))
    for rel, dom, rng, props in arrows:
        # tipo unico RELACAO_ONTOLOGIA com o nome em `nome`: a aresta de dado usa o nome da relacao como tipo, e tipos
        # diferentes evitam que o mapa nativo (db.schema.visualization) desenhe setas entre labels de dado que nao existem
        out.append((f"MATCH {_A}, {_B} MERGE (a)-[r:{ONTOLOGY_TYPE} {{nome: $rel}}]->(b) SET r = $props, r._carga = $carga",
                    {"de": dom, "para": rng, "rel": rel, "props": props}))

    for cls, term, props in term_entries(content, names):
        out.append((f"MERGE {_TERMO} SET t = $props, t._projeto = $projeto, t._carga = $carga",
                    {"nome": term, "props": props}))
        out.append(("MATCH (c:Conceito {_projeto: $projeto, nome: $classe}), " + _TERMO
                    + " MERGE (c)-[l:TEM_TERMO]->(t) SET l._carga = $carga", {"classe": cls, "nome": term}))
    return out


_SIMPLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_TOKEN = re.compile(r"`(?:[^`]|``)*`|\$(\w+)")


def _literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and not math.isfinite(value):  # nan e inf nao tem literal em Cypher
        return "0.0/0.0" if math.isnan(value) else ("1.0/0.0" if value > 0 else "-1.0/0.0")
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_literal(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k if _SIMPLE.match(k) else name(k)}: {_literal(v)}" for k, v in value.items()) + "}"
    text = str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")
    return "'" + text + "'"


def render(statement: Statement) -> str:
    """Texto Cypher com os parametros como literais, para o artefato. $projeto e $carga ficam como estao."""
    text, params = statement

    def swap(m: re.Match[str]) -> str:
        key = m.group(1)
        return m.group(0) if key is None or key not in params else _literal(params[key])

    return _TOKEN.sub(swap, text)
