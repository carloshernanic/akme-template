from __future__ import annotations

import uuid
from typing import Any

import yaml

from ..models import (
    CONTENT_SECTION, CQ_STATUSES, CQ_TYPES, DIVERGENCE_DECISIONS, EVIDENCE_KINDS, GAP_DECISIONS,
    PRIORITIES, REQUIRED_FIELDS, Edit, EditType, now_iso,
)
from ..ontology import add_class, add_relation, class_names, load_content, load_graph, save_content, save_graph
from ..project import Project, read_yaml, write_yaml
from .requirements import cq_references, mirror_reserved, next_id


class EditError(ValueError):
    pass


def _pending_path(project: Project, edit_id: str):
    return project.pending_dir / f"{edit_id}.yml"


def propose_edit(project: Project, type: str, payload: dict[str, Any], rationale: str = "",
                 proposed_by: str = "agent", requirement_id: str | None = None, evidence: str = "") -> Edit:
    try:
        edit_type = EditType(type)
    except ValueError as exc:
        raise EditError(f"tipo de edicao desconhecido: {type}. Opcoes: {[t.value for t in EditType]}") from exc
    missing = [f for f in REQUIRED_FIELDS[edit_type] if not payload.get(f)]
    if missing:
        raise EditError(f"{type} exige os campos: {', '.join(missing)}")
    if edit_type in (EditType.add_class, EditType.add_relation):
        _check_graph_refs(project, edit_type, payload)
    payload = _validate_payload(project, edit_type, payload, proposed_by)
    edit = Edit(
        id=f"{edit_type.value}-{uuid.uuid4().hex[:8]}", type=edit_type, payload=payload,
        rationale=rationale, proposed_by=proposed_by, requirement_id=requirement_id, evidence=evidence,
    )
    project.pending_dir.mkdir(parents=True, exist_ok=True)
    write_yaml(_pending_path(project, edit.id), edit.model_dump(mode="json"))
    return edit


# tipo de edicao -> (lista em requirements, prefixo de id)
_LISTS = {
    EditType.update_competency_question: ("competency_questions", "CQ"),
    EditType.remove_competency_question: ("competency_questions", "CQ"),
    EditType.update_gap: ("gaps", "L"),
    EditType.update_divergence: ("divergences", "D"),
}
_AUTO_ID = {EditType.add_competency_question: "CQ", EditType.add_use_case: "UC",
            EditType.add_gap: "L", EditType.add_divergence: "D"}


def _check_choice(field: str, value: Any, allowed: list[str]) -> None:
    if value not in allowed:
        raise EditError(f"{field} invalido: {value}. Opcoes: {allowed}")


def _check_evidence(items: Any, field: str = "evidence") -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise EditError(f"{field} deve ser uma lista nao vazia de itens com kind")
    for i in items:
        _check_choice(f"{field}.kind", i.get("kind"), list(EVIDENCE_KINDS))
    return items


def _validate_payload(project: Project, edit_type: EditType, payload: dict[str, Any], proposed_by: str) -> dict[str, Any]:
    p = dict(payload)
    if edit_type in _AUTO_ID and not p.get("id"):
        p["id"] = next_id(project, _AUTO_ID[edit_type])
    if edit_type == EditType.add_competency_question:
        _check_choice("type", p["type"], list(CQ_TYPES))
        if not isinstance(p["concepts"], list):
            raise EditError("concepts deve ser uma lista nao vazia")
        evidence = _check_evidence(p["evidence"])
        if proposed_by == "agent" and not any(i["kind"] == "source" for i in evidence):
            raise EditError("evidence de uma CQ proposta pelo agente exige ao menos um item com kind source")
        p.setdefault("status", "proposed")
        _check_choice("status", p["status"], list(CQ_STATUSES))
        if p.get("priority"):
            _check_choice("priority", p["priority"], list(PRIORITIES))
    elif edit_type == EditType.add_gap:
        _check_evidence(p["evidence"])
        p.setdefault("decision", "open")
        _check_choice("decision", p["decision"], list(GAP_DECISIONS))
    elif edit_type == EditType.add_divergence:
        if not isinstance(p["sources"], list) or len(p["sources"]) < 2:
            raise EditError("sources exige ao menos dois itens")
        p.setdefault("decision", "open")
        _check_choice("decision", p["decision"], list(DIVERGENCE_DECISIONS))
    elif edit_type in _LISTS:
        key, _ = _LISTS[edit_type]
        if p["id"] not in {i.get("id") for i in load_content(project)["requirements"][key]}:
            raise EditError(f"id nao encontrado em {key}: {p['id']}")
        if edit_type == EditType.update_competency_question:
            if "type" in p:
                _check_choice("type", p["type"], list(CQ_TYPES))
            if "status" in p:
                _check_choice("status", p["status"], list(CQ_STATUSES))
            if "priority" in p:
                _check_choice("priority", p["priority"], list(PRIORITIES))
            if "evidence" in p:
                _check_evidence(p["evidence"])
        elif edit_type == EditType.update_gap:
            _check_choice("decision", p["decision"], list(GAP_DECISIONS))
        elif edit_type == EditType.update_divergence:
            _check_choice("decision", p["decision"], list(DIVERGENCE_DECISIONS))
    return p


def _check_graph_refs(project: Project, edit_type: EditType, payload: dict[str, Any]) -> None:
    names = class_names(load_graph(project.schema_path))
    refs = [payload.get("subclass_of", "Entity")] if edit_type == EditType.add_class else [payload["domain"], payload["range"]]
    unknown = [r for r in refs if r not in names]
    if unknown:
        raise EditError(f"classes nao encontradas no schema.ttl: {', '.join(unknown)}")


def list_pending(project: Project) -> list[Edit]:
    if not project.pending_dir.exists():
        return []
    return [Edit.model_validate(read_yaml(p)) for p in sorted(project.pending_dir.glob("*.yml"))]


def _load_pending(project: Project, edit_id: str) -> Edit:
    path = _pending_path(project, edit_id)
    if not path.exists():
        raise EditError(f"edicao pendente nao encontrada: {edit_id}")
    return Edit.model_validate(read_yaml(path))


def _append_changelog(project: Project, entry: dict[str, Any]) -> None:
    log = read_yaml(project.changelog_path)
    entries = list(log.get("entries") or [])
    entries.append(entry)
    write_yaml(project.changelog_path, {"entries": entries})


def _requirements(project: Project) -> tuple[dict[str, Any], dict[str, Any]]:
    content = load_content(project)
    return content, content["requirements"]


def _merge_changed(entry: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    before = {k: entry.get(k) for k in changes}
    entry.update(changes)
    return {"before": before, "after": dict(changes)}


def _apply_use_case(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
    content, req = _requirements(project)
    req["use_cases"].append(edit.payload)
    save_content(project, content)
    return {}


def _apply_add_cq(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
    content, req = _requirements(project)
    req["competency_questions"].append(dict(edit.payload) | {"proposed_by": edit.proposed_by})
    save_content(project, content)
    mirror_reserved(project)
    return {}


def _apply_update_cq(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
    content, req = _requirements(project)
    changes = {k: v for k, v in edit.payload.items() if k != "id"}
    entry = next(c for c in req["competency_questions"] if c["id"] == edit.payload["id"])
    diff = _merge_changed(entry, changes)
    save_content(project, content)
    mirror_reserved(project)
    return diff


def _apply_remove_cq(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
    cq_id = edit.payload["id"]
    refs = cq_references(project, cq_id)
    content, req = _requirements(project)
    if not refs["changelog"] and not refs["evidence"] and not refs["in_questions"]:
        req["competency_questions"] = [c for c in req["competency_questions"] if c["id"] != cq_id]
    else:
        entry = next(c for c in req["competency_questions"] if c["id"] == cq_id)
        entry["status"] = "deprecated"
        entry["deprecation_reason"] = edit.payload["reason"]
    save_content(project, content)
    mirror_reserved(project)
    return {}


def _apply_add_list(key: str):
    def apply(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
        content, req = _requirements(project)
        item = dict(edit.payload)
        if item.get("decision") != "open":
            item |= {"decided_by": approved_by, "decided_at": now_iso()}
        req[key].append(item)
        save_content(project, content)
        return {}
    return apply


def _apply_update_list(key: str):
    def apply(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
        content, req = _requirements(project)
        changes = {k: v for k, v in edit.payload.items() if k != "id"}
        entry = next(i for i in req[key] if i["id"] == edit.payload["id"])
        diff = _merge_changed(entry, changes)
        entry |= {"decided_by": approved_by, "decided_at": now_iso()}
        save_content(project, content)
        return diff
    return apply


_APPLY_REQ = {
    EditType.add_use_case: _apply_use_case,
    EditType.add_competency_question: _apply_add_cq,
    EditType.update_competency_question: _apply_update_cq,
    EditType.remove_competency_question: _apply_remove_cq,
    EditType.add_gap: _apply_add_list("gaps"),
    EditType.add_divergence: _apply_add_list("divergences"),
    EditType.update_gap: _apply_update_list("gaps"),
    EditType.update_divergence: _apply_update_list("divergences"),
}


def apply_edit(project: Project, edit_id: str, approved_by: str) -> dict[str, Any]:
    if not approved_by or not approved_by.strip():
        raise EditError("apply_edit exige approved_by com o nome de quem aprovou")
    edit = _load_pending(project, edit_id)
    p = edit.payload
    extra: dict[str, Any] = {}
    if edit.type in CONTENT_SECTION:
        content = load_content(project)
        content[CONTENT_SECTION[edit.type]].append(p)
        save_content(project, content)
    elif edit.type in _APPLY_REQ:
        extra = _APPLY_REQ[edit.type](project, edit, approved_by)
    elif edit.type == EditType.add_requirement:
        content = load_content(project)
        field, value = p["field"], p["value"]
        if isinstance(content["requirements"].get(field), list):
            content["requirements"][field].append(value)
        else:
            content["requirements"][field] = value
        save_content(project, content)
    elif edit.type == EditType.add_class:
        g = load_graph(project.schema_path)
        add_class(g, p["name"], p["label"], p["comment"], p.get("subclass_of", "Entity"))
        save_graph(g, project.schema_path)
    elif edit.type == EditType.add_relation:
        g = load_graph(project.schema_path)
        add_relation(g, p["name"], p["domain"], p["range"], p["label"], p.get("comment", ""), p.get("inverse_of"))
        save_graph(g, project.schema_path)
    entry = {
        "edit_id": edit.id, "type": edit.type.value, "proposed_by": edit.proposed_by,
        "approved_by": approved_by, "applied_at": now_iso(), "requirement_id": edit.requirement_id,
        "evidence": edit.evidence, "rationale": edit.rationale, "payload": p,
    } | extra
    _append_changelog(project, entry)
    content = load_content(project)
    content["evidence"].append({
        "decision": edit.id, "source": edit.evidence or edit.rationale,
        "requirement_id": edit.requirement_id, "approved_by": approved_by, "date": entry["applied_at"],
    })
    save_content(project, content)
    _pending_path(project, edit_id).unlink()
    return entry


def reject_edit(project: Project, edit_id: str, rejected_by: str, reason: str = "") -> dict[str, Any]:
    edit = _load_pending(project, edit_id)
    entry = {"edit_id": edit.id, "type": edit.type.value, "status": "rejected",
             "rejected_by": rejected_by, "reason": reason, "rejected_at": now_iso()}
    _append_changelog(project, entry)
    _pending_path(project, edit_id).unlink()
    return entry


def pending_summary(project: Project) -> str:
    return yaml.safe_dump([e.model_dump(mode="json") for e in list_pending(project)], allow_unicode=True, sort_keys=False)
