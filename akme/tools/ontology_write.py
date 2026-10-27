from __future__ import annotations

import uuid
from typing import Any

import yaml

from ..models import CONTENT_SECTION, REQUIRED_FIELDS, Edit, EditType, now_iso
from ..ontology import add_class, add_relation, class_names, load_content, load_graph, save_content, save_graph
from ..project import Project, read_yaml, write_yaml


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
    edit = Edit(
        id=f"{edit_type.value}-{uuid.uuid4().hex[:8]}", type=edit_type, payload=payload,
        rationale=rationale, proposed_by=proposed_by, requirement_id=requirement_id, evidence=evidence,
    )
    project.pending_dir.mkdir(parents=True, exist_ok=True)
    write_yaml(_pending_path(project, edit.id), edit.model_dump(mode="json"))
    return edit


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


def apply_edit(project: Project, edit_id: str, approved_by: str) -> dict[str, Any]:
    if not approved_by or not approved_by.strip():
        raise EditError("apply_edit exige approved_by com o nome de quem aprovou")
    edit = _load_pending(project, edit_id)
    p = edit.payload
    if edit.type in CONTENT_SECTION:
        content = load_content(project)
        content[CONTENT_SECTION[edit.type]].append(p)
        save_content(project, content)
    elif edit.type == EditType.add_competency_question:
        content = load_content(project)
        cq = {"id": p["id"], "question": p["question"], "priority": p.get("priority", "medium"),
              "status": p.get("status", "proposed"), "source": p.get("source", edit.evidence)}
        content["requirements"]["competency_questions"].append(cq)
        save_content(project, content)
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
    }
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
