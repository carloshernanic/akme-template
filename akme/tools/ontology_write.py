from __future__ import annotations

import re
import uuid
from typing import Any

import yaml

from ..models import (
    CONTENT_SECTION, CQ_STATUSES, CQ_TYPES, DIVERGENCE_DECISIONS, EVIDENCE_KINDS, GAP_DECISIONS,
    ONTOLOGY_TYPES, PRIORITIES, REQUIRED_FIELDS, STAGE1_TYPES, Edit, EditType, Review, now_iso,
)
from ..ontology import add_class, add_relation, class_names, load_content, load_graph, save_content, save_graph
from ..project import Project, read_yaml, write_yaml
from .requirements import cq_references, mirror_reserved, next_id, requirements_status


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
    if edit_type in ONTOLOGY_TYPES:
        status = requirements_status(project)
        if status["gate_active"]:
            raise EditError("requisitos nao fechados: " + "; ".join(status["missing"]))
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


_ID_LISTS = {EditType.add_competency_question: "competency_questions", EditType.add_use_case: "use_cases",
             EditType.add_gap: "gaps", EditType.add_divergence: "divergences"}


def _check_new_id(project: Project, edit_type: EditType, new_id: str) -> None:
    prefix = _AUTO_ID[edit_type]
    if not re.fullmatch(rf"{prefix}-\d+", new_id):
        raise EditError(f"id invalido: {new_id}. Use o formato {prefix}-nn")
    applied = {i.get("id") for i in load_content(project)["requirements"][_ID_LISTS[edit_type]]}
    pending = {e.payload.get("id") for e in list_pending(project) if e.type == edit_type}
    if new_id in applied or new_id in pending:
        raise EditError(f"id ja existe: {new_id}")


def _check_choice(field: str, value: Any, allowed: list[str]) -> None:
    if value not in allowed:
        raise EditError(f"{field} invalido: {value}. Opcoes: {allowed}")


_EVIDENCE_FIELDS = {"source": ("path", "locator", "quote"), "conversation": ("who", "when")}
_DIVERGENCE_SOURCE_FIELDS = ("label", "path", "locator", "quote")


def _check_fields(item: dict[str, Any], fields: tuple[str, ...], where: str) -> None:
    missing = [f for f in fields if not str(item.get(f) or "").strip()]
    if missing:
        raise EditError(f"{where} exige os campos: {', '.join(missing)}")


def _check_evidence(items: Any, field: str = "evidence") -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
        raise EditError(f"{field} deve ser uma lista nao vazia de itens com kind")
    for i in items:
        _check_choice(f"{field}.kind", i.get("kind"), list(EVIDENCE_KINDS))
        _check_fields(i, _EVIDENCE_FIELDS[i["kind"]], f"{field} com kind {i['kind']}")
    return items


def _validate_payload(project: Project, edit_type: EditType, payload: dict[str, Any], proposed_by: str) -> dict[str, Any]:
    p = dict(payload)
    if edit_type in _AUTO_ID:
        if not p.get("id"):
            p["id"] = next_id(project, _AUTO_ID[edit_type])
        else:
            _check_new_id(project, edit_type, str(p["id"]))
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
        if not isinstance(p["sources"], list) or len(p["sources"]) < 2 or not all(isinstance(i, dict) for i in p["sources"]):
            raise EditError("sources exige ao menos dois itens")
        for i in p["sources"]:
            _check_fields(i, _DIVERGENCE_SOURCE_FIELDS, "sources")
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


def _find(items: list[dict[str, Any]], item_id: Any) -> dict[str, Any]:
    entry = next((i for i in items if i.get("id") == item_id), None)
    if entry is None:
        raise EditError(f"id nao encontrado: {item_id}")
    return entry


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
    entry = _find(req["competency_questions"], edit.payload["id"])
    diff = _merge_changed(entry, changes)
    if edit.review:
        entry |= {"reviewed_by": edit.review.reviewer, "reviewed_at": edit.review.reviewed_at}
    save_content(project, content)
    mirror_reserved(project)
    return diff


def _apply_remove_cq(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
    cq_id = edit.payload["id"]
    refs = cq_references(project, cq_id)
    content, req = _requirements(project)
    entry = _find(req["competency_questions"], cq_id)
    if not refs["changelog"] and not refs["evidence"] and not refs["in_questions"]:
        req["competency_questions"] = [c for c in req["competency_questions"] if c["id"] != cq_id]
    else:
        entry["status"] = "deprecated"
        entry["deprecation_reason"] = edit.payload["reason"]
    save_content(project, content)
    mirror_reserved(project)
    return {}


def _decider(edit: Edit, approved_by: str) -> str:
    return edit.review.reviewer if edit.review and edit.review.decision == "accept" else approved_by


def _apply_add_list(key: str):
    def apply(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
        content, req = _requirements(project)
        item = dict(edit.payload)
        if item.get("decision") != "open":
            item |= {"decided_by": _decider(edit, approved_by), "decided_at": now_iso()}
        req[key].append(item)
        save_content(project, content)
        return {}
    return apply


def _apply_update_list(key: str):
    def apply(project: Project, edit: Edit, approved_by: str) -> dict[str, Any]:
        content, req = _requirements(project)
        changes = {k: v for k, v in edit.payload.items() if k != "id"}
        entry = _find(req[key], edit.payload["id"])
        diff = _merge_changed(entry, changes)
        entry |= {"decided_by": _decider(edit, approved_by), "decided_at": now_iso()}
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


def apply_edit(project: Project, edit_id: str | None = None, approved_by: str = "",
               edit_ids: list[str] | None = None) -> dict[str, Any]:
    if not approved_by or not approved_by.strip():
        raise EditError("apply_edit exige approved_by com o nome de quem aprovou")
    if edit_ids:
        from .batch import apply_batch
        return apply_batch(project, list(edit_ids), approved_by)
    if not edit_id:
        raise EditError("apply_edit exige edit_id ou edit_ids")
    edit = _load_pending(project, edit_id)
    if edit.review and edit.review.decision == "reject" and edit.type != EditType.add_competency_question:
        return reject_edit(project, edit_id, edit.review.reviewer, edit.review.reason) | {"review": edit.review.model_dump()}
    if edit.review:
        edit.payload = _merge_review(edit)
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
    if edit.review:
        entry["review"] = edit.review.model_dump()
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


# chaves que o revisor pode editar, por tipo; demais tipos aceitam so chaves ja presentes no payload
_REVIEW_KEYS = {
    EditType.add_competency_question: {"question", "type", "concepts", "evidence", "use_cases", "priority", "status", "answer"},
    EditType.add_gap: {"decision", "note", "reason"},
    EditType.update_gap: {"decision", "note", "reason"},
    EditType.add_divergence: {"decision", "winner", "reason"},
    EditType.update_divergence: {"decision", "winner", "reason"},
}
_REVIEW_CHOICES = {"type": CQ_TYPES, "status": CQ_STATUSES, "priority": PRIORITIES}


def _check_review_edits(edit: Edit, edits: dict[str, Any]) -> None:
    allowed = _REVIEW_KEYS.get(edit.type, set(edit.payload))
    for key, value in edits.items():
        if key == "id":
            raise EditError("edits nao pode alterar o id")
        if key not in allowed:
            raise EditError(f"edits nao aceita a chave {key} para {edit.type.value}. Opcoes: {sorted(allowed)}")
        if key in _REVIEW_CHOICES and edit.type == EditType.add_competency_question:
            _check_choice(key, value, list(_REVIEW_CHOICES[key]))
        elif key == "evidence":
            _check_evidence(value)
        elif key == "decision" and edit.type in (EditType.add_gap, EditType.update_gap):
            _check_choice("decision", value, list(GAP_DECISIONS))
        elif key == "decision" and edit.type in (EditType.add_divergence, EditType.update_divergence):
            _check_choice("decision", value, list(DIVERGENCE_DECISIONS))


def review_edit(project: Project, edit_id: str, decision: str, reviewer: str,
                edits: dict[str, Any] | None = None, reason: str = "") -> Edit:
    """Grava o bloco review no pendente, sem aplicar nada."""
    edit = _load_pending(project, edit_id)
    if not reviewer or not reviewer.strip():
        raise EditError("review_edit exige reviewer com o nome de quem revisou")
    if edit.type not in STAGE1_TYPES:
        raise EditError(f"revisao na aba so para edicoes da etapa 1: {edit.type.value}")
    _check_choice("decision", decision, ["accept", "reject"])
    if decision == "reject" and edit.type in (EditType.add_gap, EditType.add_divergence):
        alt = "drop" if edit.type == EditType.add_gap else "dismiss"
        raise EditError(f"{edit.type.value} nao aceita reject; use accept com edits.decision {alt}")
    if decision == "reject" and not reason.strip():
        raise EditError("review_edit com decision reject exige reason")
    if edits is not None and not isinstance(edits, dict):
        raise EditError("edits deve ser um objeto")
    edits = dict(edits or {})
    _check_review_edits(edit, edits)
    if decision == "accept" and edit.type == EditType.add_competency_question:
        if edits.get("status", edit.payload.get("status")) not in ("approved", "reserved"):
            edits["status"] = "approved"
        if not edits.get("priority") and not edit.payload.get("priority"):
            raise EditError("aceitar uma CQ exige priority (high, medium ou low)")
    edit.review = Review(decision=decision, reviewer=reviewer, reviewed_at=now_iso(), edits=edits, reason=reason)
    write_yaml(_pending_path(project, edit.id), edit.model_dump(mode="json"))
    return edit


def _merge_review(edit: Edit) -> dict[str, Any]:
    review = edit.review
    p = dict(edit.payload) | review.edits
    if edit.type == EditType.add_competency_question:
        p |= {"reviewed_by": review.reviewer, "reviewed_at": review.reviewed_at}
        if review.decision == "reject":
            p |= {"status": "rejected", "rejection_reason": review.reason}
    return p


def apply_reviewed(project: Project, approved_by: str) -> dict[str, Any]:
    """Aplica em lote os pendentes da etapa 1 com review, em ordem de created_at."""
    if not approved_by or not approved_by.strip():
        raise EditError("apply_reviewed exige approved_by com o nome de quem aprovou")
    from .batch import apply_batch
    reviewed = sorted((e for e in list_pending(project) if e.review and e.type in STAGE1_TYPES),
                      key=lambda e: (e.created_at, e.id))
    return apply_batch(project, [e.id for e in reviewed], approved_by)


def pending_summary(project: Project) -> str:
    return yaml.safe_dump([e.model_dump(mode="json") for e in list_pending(project)], allow_unicode=True, sort_keys=False)
