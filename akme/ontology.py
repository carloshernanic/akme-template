from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS

from .project import Project, read_yaml, write_yaml

DEFAULT_BASE = "https://akme.example/ontology#"

EMPTY_CONTENT: dict[str, Any] = {
    "requirements": {
        "purpose": "", "scope": "", "users": [], "use_cases": [], "no_use_case": "",
        "competency_questions": [], "gaps": [], "divergences": [],
    },
    "terms": [],
    "mappings": [],
    "constraints": [],
    "glossary": [],
    "precedence": [],
    "evidence": [],
}


def load_graph(path: Path) -> Graph:
    g = Graph()
    g.parse(path, format="turtle")
    return g


def save_graph(g: Graph, path: Path) -> None:
    path.write_text(g.serialize(format="turtle"), encoding="utf-8")


def base_ns(g: Graph) -> Namespace:
    for prefix, ns in g.namespaces():
        if prefix == "akme":
            return Namespace(str(ns))
    return Namespace(DEFAULT_BASE)


def local(iri: Any) -> str:
    s = str(iri)
    for sep in ("#", "/"):
        if sep in s:
            s = s.rsplit(sep, 1)[1]
    return s


def _text(g: Graph, s: URIRef, p: URIRef) -> str:
    v = g.value(s, p)
    return str(v) if v is not None else ""


def classes(g: Graph) -> list[dict[str, Any]]:
    out = []
    for c in sorted(set(g.subjects(RDF.type, OWL.Class)), key=str):
        if isinstance(c, URIRef):
            out.append({
                "name": local(c),
                "iri": str(c),
                "label": _text(g, c, RDFS.label),
                "comment": _text(g, c, RDFS.comment),
                "subclass_of": [local(p) for p in g.objects(c, RDFS.subClassOf) if isinstance(p, URIRef)],
            })
    return out


def relations(g: Graph) -> list[dict[str, Any]]:
    out = []
    for p in sorted(set(g.subjects(RDF.type, OWL.ObjectProperty)), key=str):
        out.append({
            "name": local(p),
            "iri": str(p),
            "label": _text(g, p, RDFS.label),
            "comment": _text(g, p, RDFS.comment),
            "domain": [local(d) for d in g.objects(p, RDFS.domain)],
            "range": [local(r) for r in g.objects(p, RDFS.range)],
            "inverse_of": [local(i) for i in g.objects(p, OWL.inverseOf)],
        })
    return out


def class_names(g: Graph) -> set[str]:
    return {c["name"] for c in classes(g)}


def add_class(g: Graph, name: str, label: str, comment: str, subclass_of: str = "Entity") -> URIRef:
    ns = base_ns(g)
    c = ns[name]
    g.add((c, RDF.type, OWL.Class))
    g.add((c, RDFS.subClassOf, ns[subclass_of]))
    g.add((c, RDFS.label, Literal(label, lang="pt")))
    g.add((c, RDFS.comment, Literal(comment, lang="pt")))
    return c


def add_relation(g: Graph, name: str, domain: str, range_: str, label: str,
                 comment: str = "", inverse_of: str | None = None) -> URIRef:
    ns = base_ns(g)
    p = ns[name]
    g.add((p, RDF.type, OWL.ObjectProperty))
    g.add((p, RDFS.domain, ns[domain]))
    g.add((p, RDFS.range, ns[range_]))
    g.add((p, RDFS.label, Literal(label, lang="pt")))
    if comment:
        g.add((p, RDFS.comment, Literal(comment, lang="pt")))
    if inverse_of:
        inv = ns[inverse_of]
        if (inv, RDF.type, OWL.ObjectProperty) not in g:
            g.add((inv, RDF.type, OWL.ObjectProperty))
            g.add((inv, RDFS.domain, ns[range_]))
            g.add((inv, RDFS.range, ns[domain]))
            g.add((inv, RDFS.label, Literal(inverse_of, lang="pt")))
        g.add((p, OWL.inverseOf, inv))
        g.add((inv, OWL.inverseOf, p))
    return p


def ontology_iri(g: Graph) -> URIRef | None:
    for o in g.subjects(RDF.type, OWL.Ontology):
        return o
    return None


def has_license(g: Graph) -> bool:
    o = ontology_iri(g)
    return o is not None and g.value(o, DCTERMS.license) is not None


def load_content(project: Project) -> dict[str, Any]:
    data = read_yaml(project.content_path)
    content: dict[str, Any] = {}
    for key, default in EMPTY_CONTENT.items():
        value = data.get(key)
        if isinstance(default, dict):
            merged = dict(default)
            merged.update(value or {})
            content[key] = merged
        else:
            content[key] = list(value or [])
    return content


def save_content(project: Project, content: dict[str, Any]) -> None:
    write_yaml(project.content_path, content)


def load_manifest(project: Project) -> dict[str, Any]:
    return read_yaml(project.manifest_path)


def save_manifest(project: Project, manifest: dict[str, Any]) -> None:
    write_yaml(project.manifest_path, manifest)
