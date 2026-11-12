"""Camada de ontologia no Neo4j: um no :Conceito por classe, SUBCLASSE_DE e uma seta por contrato de relacao.

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

Statement = tuple[str, dict[str, Any]]

_CONCEITO = "(c:Conceito {_projeto: $projeto, nome: $nome})"
_A = "(a:Conceito {_projeto: $projeto, nome: $de})"
_B = "(b:Conceito {_projeto: $projeto, nome: $para})"


def _metric_props(content: dict[str, Any], contracts: list[dict[str, Any]], cls: str) -> dict[str, Any]:
    """Contrato da metrica: termo da classe com mapping de papel metric. So os campos presentes.

    Se a classe tiver varios mappings de papel metric, vale o primeiro na ordem do content.yml.
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
            props["nao_somar_apos_juntar_com"] = fan
        return props
    return {}


def ontology_statements(project: Project, published: set[str]) -> list[Statement]:
    g = load_graph(project.schema_path)
    content = load_content(project)
    contracts = content["relation_contracts"]
    cls_list = sorted(classes(g), key=lambda c: c["name"])
    names = {c["name"] for c in cls_list}
    rels = {r["name"]: r for r in relations(g)}
    out: list[Statement] = []

    for c in cls_list:
        props: dict[str, Any] = {"nome": c["name"], "rotulo": c["label"], "definicao": c["comment"], "iri": c["iri"]}
        if is_metric_class(g, c["name"]):
            props |= _metric_props(content, contracts, c["name"])
        out.append((f"MERGE {_CONCEITO} SET c = $props, c._projeto = $projeto, c._carga = $carga",
                    {"nome": c["name"], "props": props}))

    for c in cls_list:
        for parent in sorted(set(c["subclass_of"])):
            if parent in names:
                out.append((f"MATCH {_A}, {_B} MERGE (a)-[r:SUBCLASSE_DE]->(b) SET r._carga = $carga",
                            {"de": c["name"], "para": parent}))

    kept: dict[str, dict[str, Any]] = {}
    arrows: list[tuple[str, str, str, dict[str, Any]]] = []
    for contract in sorted(contracts, key=lambda x: x["relation"]):
        rel, dom, rng = contract["relation"], contract.get("domain"), contract.get("range")
        if dom not in names or rng not in names:
            continue
        inverse = contract.get("inverse_of") or ""
        if inverse in kept:  # a inversa e propriedade da seta ja desenhada, nao ganha seta propria
            kept[inverse]["inversa"] = rel  # e a seta mantida sempre aponta o outro lado
            continue
        info = rels.get(rel, {})
        props = {"rotulo": info.get("label", ""), "definicao": info.get("comment", ""),
                 "multiplicidade": contract.get("multiplicity") or "", "inversa": inverse,
                 "publicada": rel in published}
        kept[rel] = props
        arrows.append((rel, dom, rng, props))
    for rel, dom, rng, props in arrows:
        out.append((f"MATCH {_A}, {_B} MERGE (a)-[r:{name(rel)}]->(b) SET r = $props, r._carga = $carga",
                    {"de": dom, "para": rng, "props": props}))
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
