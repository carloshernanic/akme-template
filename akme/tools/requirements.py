from __future__ import annotations

import re
from typing import Any

from ..models import STAGE1_TYPES, EditType
from ..ontology import classes, load_content, load_graph
from ..project import Project, read_yaml, write_yaml

# prefixo -> (lista em requirements, tipo de edit pendente, casas decimais)
_IDS = {
    "CQ": ("competency_questions", EditType.add_competency_question, 3),
    "UC": ("use_cases", EditType.add_use_case, 2),
    "L": ("gaps", EditType.add_gap, 2),
    "D": ("divergences", EditType.add_divergence, 2),
}
_INFRA_CLASSES = {"Entity", "Relation", "Rule", "Metric"}


def next_id(project: Project, prefix: str) -> str:
    from .ontology_write import list_pending

    if prefix not in _IDS:
        raise ValueError(f"prefixo desconhecido: {prefix}")
    key, edit_type, width = _IDS[prefix]
    ids = [str(i.get("id", "")) for i in load_content(project)["requirements"][key]]
    ids += [str(e.payload.get("id", "")) for e in list_pending(project) if e.type == edit_type]
    pattern = re.compile(rf"^{prefix}-(\d+)$")
    nums = [int(m.group(1)) for m in (pattern.match(i) for i in ids) if m]
    return f"{prefix}-{(max(nums) if nums else 0) + 1:0{width}d}"


def domain_class_count(project: Project) -> int:
    return sum(1 for c in classes(load_graph(project.schema_path)) if c["name"] not in _INFRA_CLASSES)


def requirements_status(project: Project) -> dict[str, Any]:
    from .ontology_write import list_pending

    r = load_content(project)["requirements"]
    cqs = r["competency_questions"]
    missing: list[str] = []
    if not r["use_cases"] and not str(r.get("no_use_case") or "").strip():
        missing.append("sem caso de uso (ou motivo em requirements.no_use_case)")
    proposed = [c.get("id", "?") for c in cqs if c.get("status") == "proposed"]
    if proposed:
        missing.append(f"CQs ainda em proposed: {', '.join(proposed)}")
    unreviewed = [e.id for e in list_pending(project) if e.type in STAGE1_TYPES and e.review is None]
    if unreviewed:
        missing.append(f"pendentes da etapa 1 sem revisao: {', '.join(unreviewed)}")
    if not any(c.get("status") == "approved" for c in cqs):
        missing.append("nenhuma CQ approved")
    open_items = [i.get("id", "?") for i in list(r["gaps"]) + list(r["divergences"]) if i.get("decision") == "open"]
    if open_items:
        missing.append(f"lacunas ou divergencias em open: {', '.join(open_items)}")
    if not str(r.get("purpose") or "").strip() or not str(r.get("scope") or "").strip():
        missing.append("purpose ou scope vazios")
    closed = not missing
    empty = domain_class_count(project) == 0
    return {"closed": closed, "missing": missing, "ontology_empty": empty, "gate_active": empty and not closed}


def cq_references(project: Project, cq_id: str) -> dict[str, Any]:
    log = read_yaml(project.changelog_path).get("entries") or []
    own = {e["edit_id"] for e in log
           if e.get("requirement_id") == cq_id and e.get("type") == EditType.add_competency_question.value}
    changelog = [e["edit_id"] for e in log if e.get("requirement_id") == cq_id and e["edit_id"] not in own]
    evidence = [e["decision"] for e in load_content(project)["evidence"]
                if e.get("requirement_id") == cq_id and e.get("decision") not in own]
    questions = read_yaml(project.questions_path).get("questions") or []
    return {"changelog": changelog, "evidence": evidence,
            "in_questions": any(q.get("id") == cq_id for q in questions)}


def mirror_reserved(project: Project) -> None:
    cqs = load_content(project)["requirements"]["competency_questions"]
    reserved = {c["id"]: c for c in cqs if c.get("status") == "reserved"}
    not_reserved = {c["id"] for c in cqs if c.get("status") != "reserved"}
    # so remove entradas que a propria ferramenta escreveu (mirrored: true); as escritas a mao ficam
    questions = [q for q in (read_yaml(project.questions_path).get("questions") or [])
                 if not (q.get("mirrored") and q.get("id") in not_reserved)]
    by_id = {q.get("id"): q for q in questions}
    for cid, cq in reserved.items():
        entry = by_id.get(cid)
        if entry is None:
            entry = {"id": cid}
            questions.append(entry)
        entry["question"] = cq.get("question", "")
        entry["answer"] = cq.get("answer", "")
        entry["mirrored"] = True
    write_yaml(project.questions_path, {"questions": questions})


def data_request(project: Project) -> list[dict[str, Any]]:
    return [
        {"id": g.get("id"), "question": g.get("question"), "missing": g.get("missing"),
         "use_cases": g.get("use_cases", [])}
        for g in load_content(project)["requirements"]["gaps"]
        if g.get("decision") == "request_from_client"
    ]
