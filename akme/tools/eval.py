from __future__ import annotations

import importlib
import re
from typing import Any, Callable

from rdflib import OWL, RDFS, Graph

from ..ontology import base_ns, classes, load_content, load_graph, relations
from ..project import Project, read_yaml

AnswerFn = Callable[[str, str | None], str]

TEST = re.compile(r"^(\S+)\s+(type|subclassOf|disjointWith|\S+)\s+(?:some\s+)?(\S+)$")


def load_questions(project: Project) -> list[dict[str, Any]]:
    return list(read_yaml(project.questions_path).get("questions") or [])


def _superclasses(g: Graph, name: str) -> set[str]:
    ns = base_ns(g)
    seen, stack = set(), [ns[name]]
    while stack:
        node = stack.pop()
        for parent in g.objects(node, RDFS.subClassOf):
            label = str(parent).rsplit("#", 1)[-1]
            if label not in seen:
                seen.add(label)
                stack.append(parent)
    return seen


def check_assertion(g: Graph, assertion: str) -> tuple[bool, str]:
    m = TEST.match(assertion.strip())
    if not m:
        return False, "sintaxe invalida; use 'A type Class', 'A subclassOf B', 'A disjointWith B' ou 'A prop B'"
    subject, pred, obj = m.groups()
    ns = base_ns(g)
    names = {c["name"] for c in classes(g)}
    if pred == "type":
        if obj != "Class":
            return False, "so 'type Class' e suportado"
        return subject in names, "" if subject in names else f"classe {subject} nao existe"
    if pred == "subclassOf":
        ok = obj in _superclasses(g, subject)
        return ok, "" if ok else f"{subject} nao e subclasse de {obj}"
    if pred == "disjointWith":
        ok = (ns[subject], OWL.disjointWith, ns[obj]) in g or (ns[obj], OWL.disjointWith, ns[subject]) in g
        return ok, "" if ok else f"{subject} e {obj} nao sao disjuntos"
    rel = next((r for r in relations(g) if r["name"] == pred), None)
    if rel is None:
        return False, f"relacao {pred} nao existe"
    dom_ok = subject in rel["domain"] or any(d in _superclasses(g, subject) for d in rel["domain"])
    rng_ok = obj in rel["range"] or any(r in _superclasses(g, obj) for r in rel["range"])
    if dom_ok and rng_ok:
        return True, ""
    return False, f"{pred} liga {rel['domain']} a {rel['range']}, nao {subject} a {obj}"


def structural_tests(project: Project, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    g = load_graph(project.schema_path)
    rows = []
    for q in questions:
        results = [(a, *check_assertion(g, a)) for a in q.get("expects") or []]
        rows.append({
            "id": q.get("id"), "question": q.get("question"),
            "structural": "n/a" if not results else ("pass" if all(ok for _, ok, _ in results) else "fail"),
            "details": [{"assertion": a, "ok": ok, "note": note} for a, ok, note in results],
        })
    return rows


def ontology_context(project: Project) -> str:
    g = load_graph(project.schema_path)
    content = load_content(project)
    lines = ["Classes:"] + [f"- {c['name']}: {c['comment']}" for c in classes(g)]
    lines += ["Relacoes:"] + [f"- {r['name']} ({', '.join(r['domain'])} -> {', '.join(r['range'])})" for r in relations(g)]
    lines += ["Termos:"] + [f"- {t['name']} [{t.get('class')}]: {t.get('definition', '')}" for t in content["terms"]]
    lines += ["Mappings:"] + [f"- {m['term']} = {m['source']}.{m['column']}" for m in content["mappings"]]
    lines += ["Glossario:"] + [f"- {x['acronym']}: {x['meaning']}" for x in content["glossary"]]
    lines += ["Precedencia:"] + [f"- {p['topic']}: {p['winner']} prevalece sobre {p['over']}" for p in content["precedence"]]
    return "\n".join(lines)


def _matches(answer: str, gold: str | None) -> bool | None:
    if gold is None:
        return None
    return gold.strip().lower() in (answer or "").strip().lower()


def evaluate(project: Project, answer_fn: AnswerFn | None = None) -> dict[str, Any]:
    questions = load_questions(project)
    rows = structural_tests(project, questions)
    if answer_fn is not None:
        context = ontology_context(project)
        for q, row in zip(questions, rows):
            without = answer_fn(q["question"], None)
            with_ = answer_fn(q["question"], context)
            row.update({
                "without_ontology": without, "with_ontology": with_,
                "without_correct": _matches(without, q.get("answer")),
                "with_correct": _matches(with_, q.get("answer")),
            })
    structural = [r["structural"] for r in rows if r["structural"] != "n/a"]
    summary: dict[str, Any] = {
        "questions": len(rows),
        "structural_pass": structural.count("pass"),
        "structural_fail": structural.count("fail"),
    }
    if answer_fn is not None:
        summary["without_correct"] = sum(1 for r in rows if r.get("without_correct"))
        summary["with_correct"] = sum(1 for r in rows if r.get("with_correct"))
    return {"rows": rows, "summary": summary}


def load_callable(spec: str) -> AnswerFn:
    module_name, _, func_name = spec.partition(":")
    if not func_name:
        raise ValueError("use o formato modulo:funcao, ex: meu_agente:responder")
    return getattr(importlib.import_module(module_name), func_name)
