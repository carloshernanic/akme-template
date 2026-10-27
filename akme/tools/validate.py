from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef

from ..models import Finding, ValidationReport
from ..ontology import classes, has_license, load_content, local, relations
from ..project import Project, read_yaml
from .profile import load_profile

OOPS_REST = "https://oops.linkeddata.es/rest"
OEG_STATUS = "https://raw.githubusercontent.com/oeg-upm/oeg-service-status/main/services_status.json"
OOPS = Namespace("http://oops.linkeddata.es/def#")
ROOT_CLASSES = {"Entity", "Relation", "Rule", "Metric"}


def _parse_ttl(project: Project, findings: list[Finding]) -> Graph | None:
    g = Graph()
    try:
        g.parse(project.schema_path, format="turtle")
    except Exception as exc:
        findings.append(Finding(level="error", check="ttl_parse", message=f"schema.ttl nao parseia: {exc}"))
        return None
    return g


def _check_terms(content: dict[str, Any], names: set[str], findings: list[Finding]) -> None:
    for t in content["terms"]:
        if t.get("class") not in names:
            findings.append(Finding(level="error", check="term_class", subject=t.get("name", ""),
                                    message=f"termo '{t.get('name')}' aponta para classe inexistente '{t.get('class')}'"))


def _check_mappings(content: dict[str, Any], project: Project, findings: list[Finding]) -> dict[str, Any]:
    prof = load_profile(project)
    term_names = {t["name"] for t in content["terms"]}
    for m in content["mappings"]:
        if m.get("term") not in term_names:
            findings.append(Finding(level="error", check="mapping_term", subject=m.get("term", ""),
                                    message=f"mapping aponta para termo inexistente '{m.get('term')}'"))
    if prof is None:
        findings.append(Finding(level="warning", check="profile_missing",
                                message="docs/profile.json nao existe; rode akme profile para checar mappings e cobertura"))
        return {"available": False}
    columns = {(s.name, c.name) for s in prof.sources for c in s.columns}
    mapped = set()
    for m in content["mappings"]:
        key = (m.get("source"), m.get("column"))
        if key not in columns:
            findings.append(Finding(level="error", check="mapping_column", subject=m.get("term", ""),
                                    message=f"mapping de '{m.get('term')}' aponta para coluna inexistente {key[0]}.{key[1]}"))
        else:
            mapped.add(key)
    by_source = {}
    for s in prof.sources:
        cols = [c.name for c in s.columns]
        covered = [c for c in cols if (s.name, c) in mapped]
        by_source[s.name] = {"columns": len(cols), "mapped": len(covered),
                             "unmapped": [c for c in cols if c not in covered]}
    total = sum(v["columns"] for v in by_source.values())
    done = sum(v["mapped"] for v in by_source.values())
    return {"available": True, "columns": total, "mapped": done,
            "ratio": round(done / total, 3) if total else 0.0, "by_source": by_source}


def _check_precedence(content: dict[str, Any], findings: list[Finding]) -> None:
    seen: dict[str, tuple[str, str]] = {}
    for r in content["precedence"]:
        pair = (str(r.get("winner")), str(r.get("over")))
        key = r.get("topic", "")
        if key in seen and seen[key] == (pair[1], pair[0]):
            findings.append(Finding(level="error", check="precedence_conflict", subject=key,
                                    message=f"precedencia contraditoria para '{key}': {pair[0]} sobre {pair[1]} e o inverso"))
        seen[key] = pair


def _check_questions(content: dict[str, Any], project: Project, findings: list[Finding]) -> None:
    cq_ids = {c.get("id") for c in content["requirements"]["competency_questions"]}
    for q in read_yaml(project.questions_path).get("questions") or []:
        if q.get("id") and q["id"] not in cq_ids:
            findings.append(Finding(level="warning", check="question_without_requirement", subject=q["id"],
                                    message=f"pergunta '{q['id']}' nao esta registrada como competency question em content.yml"))


def native_pitfalls(g: Graph) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cls = classes(g)
    rels = relations(g)
    connected = {n for r in rels for n in r["domain"] + r["range"]}
    connected |= {p for c in cls for p in c["subclass_of"]}
    for c in cls:
        if c["name"] not in ROOT_CLASSES and not c["subclass_of"] and c["name"] not in connected:
            out.append(_pitfall("P04", "important", c["name"], "classe sem subClassOf nem relacoes"))
        if not c["label"] or not c["comment"]:
            out.append(_pitfall("P08", "minor", c["name"], "classe sem rdfs:label ou rdfs:comment"))
        if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", c["name"]):
            out.append(_pitfall("P22", "minor", c["name"], "nome de classe fora do padrao PascalCase"))
    for r in rels:
        if not r["domain"] or not r["range"]:
            out.append(_pitfall("P11", "important", r["name"], "propriedade sem domain ou range"))
        if not r["label"]:
            out.append(_pitfall("P08", "minor", r["name"], "propriedade sem rdfs:label"))
        if not r["inverse_of"]:
            out.append(_pitfall("P13", "minor", r["name"], "relacao sem inversa declarada"))
        if not re.fullmatch(r"[a-z][A-Za-z0-9]*", r["name"]):
            out.append(_pitfall("P22", "minor", r["name"], "nome de propriedade fora do padrao lowerCamelCase"))
    if not has_license(g):
        out.append(_pitfall("P41", "important", "ontology", "ontologia sem dcterms:license"))
    return out


def _pitfall(code: str, level: str, subject: str, message: str) -> dict[str, Any]:
    return {"code": code, "level": level, "subject": subject, "message": message, "source": "native"}


def oops_status(timeout: int = 8) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(OEG_STATUS, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"known": False, "error": str(exc)}
    entry = data.get("oops") if isinstance(data, dict) else None
    if entry is None and isinstance(data, list):
        entry = next((e for e in data if str(e.get("name", "")).lower().startswith("oops")), None)
    if not entry:
        return {"known": False}
    code = entry.get("status_http_code") or entry.get("status_code")
    return {"known": True, "http_code": code, "up": str(code) == "200"}


def oops_scan(ttl: str, timeout: int = 30) -> dict[str, Any]:
    status = oops_status()
    if status.get("known") and not status.get("up"):
        return {"available": False, "reason": f"OOPS! fora do ar segundo oeg-service-status (http {status.get('http_code')})", "pitfalls": []}
    body = (
        '<?xml version="1.0" encoding="UTF-8"?><OOPSRequest><OntologyUrl></OntologyUrl>'
        f"<OntologyContent><![CDATA[{ttl}]]></OntologyContent><Pitfalls></Pitfalls>"
        "<OutputFormat>RDF/XML</OutputFormat></OOPSRequest>"
    ).encode("utf-8")
    req = urllib.request.Request(OOPS_REST, data=body, headers={"Content-Type": "application/xml"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        return {"available": False, "reason": str(exc), "pitfalls": []}
    g = Graph()
    try:
        g.parse(data=raw, format="xml")
    except Exception as exc:
        return {"available": False, "reason": f"resposta invalida: {exc}", "pitfalls": []}
    pitfalls = []
    for p in g.subjects(RDF.type, OOPS.pitfall):
        affected = [local(a) for a in g.objects(p, OOPS.hasAffectedElement)]
        pitfalls.append({
            "code": str(g.value(p, OOPS.hasCode) or ""),
            "level": str(g.value(p, OOPS.hasImportanceLevel) or "").lower(),
            "subject": ", ".join(affected),
            "message": str(g.value(p, OOPS.hasName) or ""),
            "source": "oops",
        })
    return {"available": True, "pitfalls": pitfalls}


def validate(project: Project, oops: bool = False) -> ValidationReport:
    findings: list[Finding] = []
    content = load_content(project)
    g = _parse_ttl(project, findings)
    pitfalls: list[dict[str, Any]] = []
    oops_result = None
    if g is not None:
        _check_terms(content, {c["name"] for c in classes(g)}, findings)
        pitfalls = native_pitfalls(g)
        if oops:
            oops_result = oops_scan(project.schema_path.read_text(encoding="utf-8"))
            pitfalls += oops_result.get("pitfalls", [])
    coverage = _check_mappings(content, project, findings)
    _check_precedence(content, findings)
    _check_questions(content, project, findings)
    report = ValidationReport(
        ok=not any(f.level == "error" for f in findings),
        findings=findings, coverage=coverage, pitfalls=pitfalls, oops=oops_result,
    )
    project.validation_path.parent.mkdir(parents=True, exist_ok=True)
    project.validation_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report
