from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from ..ontology import classes, load_content, load_graph, relations
from ..project import Project

LOV_SEARCH = "https://lov.linkeddata.es/dataset/lov/api/v2/term/search"


def list_entities(project: Project) -> list[dict[str, Any]]:
    content = load_content(project)
    by_class: dict[str, list[str]] = {}
    for t in content["terms"]:
        by_class.setdefault(t.get("class", ""), []).append(t["name"])
    out = []
    for c in classes(load_graph(project.schema_path)):
        c["terms"] = by_class.get(c["name"], [])
        out.append(c)
    return out


def list_relations(project: Project) -> list[dict[str, Any]]:
    return relations(load_graph(project.schema_path))


def _match(q: str, *fields: Any) -> bool:
    q = q.lower()
    return any(q in str(f).lower() for f in fields if f)


def search_term(project: Project, query: str) -> dict[str, list[dict[str, Any]]]:
    content = load_content(project)
    g = load_graph(project.schema_path)
    return {
        "terms": [t for t in content["terms"] if _match(query, t.get("name"), t.get("definition"), *t.get("synonyms", []))],
        "glossary": [x for x in content["glossary"] if _match(query, x.get("acronym"), x.get("meaning"))],
        "mappings": [m for m in content["mappings"] if _match(query, m.get("term"), m.get("source"), m.get("column"))],
        "classes": [c for c in classes(g) if _match(query, c["name"], c["label"], c["comment"])],
        "relations": [r for r in relations(g) if _match(query, r["name"], r["label"])],
    }


def resolve_acronym(project: Project, acronym: str) -> dict[str, Any] | None:
    for entry in load_content(project)["glossary"]:
        if entry.get("acronym", "").lower() == acronym.lower():
            return entry
    return None


def get_precedence(project: Project, topic: str | None = None) -> list[dict[str, Any]]:
    rules = load_content(project)["precedence"]
    if topic:
        rules = [r for r in rules if _match(topic, r.get("topic"))]
    return rules


def list_competency_questions(project: Project, status: str | None = None) -> list[dict[str, Any]]:
    cqs = load_content(project)["requirements"]["competency_questions"]
    return [c for c in cqs if c.get("status") == status] if status else cqs


def get_requirements(project: Project) -> dict[str, Any]:
    from .requirements import data_request, requirements_status

    return {**load_content(project)["requirements"], "data_request": data_request(project),
            "status": requirements_status(project)}


def search_registry(query: str, limit: int = 10, timeout: int = 10) -> dict[str, Any]:
    url = f"{LOV_SEARCH}?{urllib.parse.urlencode({'q': query, 'page_size': limit})}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"query": query, "available": False, "error": str(exc), "results": []}
    results = [
        {
            "iri": hit.get("_id"),
            "type": (hit.get("_source") or {}).get("type"),
            "vocabulary": ((hit.get("_source") or {}).get("vocabulary.prefix") or [None])[0],
            "score": hit.get("_score"),
        }
        for hit in data.get("results", [])
    ]
    return {"query": query, "available": True, "total": data.get("total_results"), "results": results}
