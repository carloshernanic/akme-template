from __future__ import annotations

import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from ..models import EditType
from ..project import CONFIG_FILE, Project, write_yaml
from .ontology_write import EditError, apply_edit, list_pending
from .validate import validate

_EDITED_CQ_FIELDS = ("question", "type", "concepts", "answer")


class BatchError(EditError):
    def __init__(self, message: str, new_errors: list[dict[str, Any]] | None = None) -> None:
        self.new_errors = list(new_errors or [])
        detail = "; ".join(f"{e['check']} {e['subject']}: {e['message']}" for e in self.new_errors)
        super().__init__(f"{message}: {detail}" if detail else message)


def stage(project: Project) -> Project:
    """Copia ontology_dir, questions e profile para um diretorio temporario e devolve um Project apontando para ele."""
    tmp = Path(tempfile.mkdtemp(prefix="akme-batch-"))
    ontology = tmp / "ontology"
    questions = tmp / project.questions_path.name
    docs = tmp / "docs"
    shutil.copytree(project.ontology_dir, ontology)
    if project.questions_path.exists():
        shutil.copy2(project.questions_path, questions)
    docs.mkdir()
    if project.profile_path.exists():
        shutil.copy2(project.profile_path, docs / project.profile_path.name)
    config: dict[str, Any] = {"project": project.name, "adapter": project.adapter_name}
    options = dict(project.config.get(project.adapter_name) or {})
    if project.adapter_name == "local_folder" and options.get("path"):
        options["path"] = str(project.resolve(str(options["path"])))
    config[project.adapter_name] = options
    config |= {"ontology_dir": str(ontology), "questions": str(questions), "docs_dir": str(docs)}
    write_yaml(tmp / CONFIG_FILE, config)
    return Project(tmp)


def promote(staging: Project, project: Project) -> None:
    """Substitui ontology_dir e questions do projeto pelos da copia e atualiza docs/validation.json."""
    target = project.ontology_dir
    incoming = target.with_name(target.name + ".akme-new")
    if incoming.exists():
        shutil.rmtree(incoming)
    shutil.copytree(staging.ontology_dir, incoming)
    shutil.rmtree(target)
    incoming.rename(target)
    if staging.questions_path.exists():
        project.questions_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staging.questions_path, project.questions_path)
    validate(project)


def _key(f: dict[str, Any]) -> tuple[str, str, str]:
    return (f["check"], f["subject"], f["message"])


def _summary(edits: list[Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    s: dict[str, Any] = {"cqs_accepted": 0, "cqs_rejected": 0, "cqs_edited": 0, "cqs_created_by_human": 0,
                         "gaps": Counter(), "divergences": Counter(), "applied_types": Counter()}
    for edit, entry in zip(edits, results):
        if entry.get("status") == "rejected":
            continue
        s["applied_types"][edit.type.value] += 1
        review = edit.review
        if edit.type == EditType.add_competency_question:
            if review and review.decision == "reject":
                s["cqs_rejected"] += 1
            else:
                s["cqs_accepted"] += 1
                if review and any(k in review.edits and review.edits[k] != edit.payload.get(k) for k in _EDITED_CQ_FIELDS):
                    s["cqs_edited"] += 1
            if edit.proposed_by != "agent":
                s["cqs_created_by_human"] += 1
        elif edit.type in (EditType.add_gap, EditType.update_gap):
            s["gaps"][entry["payload"].get("decision")] += 1
        elif edit.type in (EditType.add_divergence, EditType.update_divergence):
            s["divergences"][entry["payload"].get("decision")] += 1
    s["gaps"], s["divergences"], s["applied_types"] = dict(s["gaps"]), dict(s["divergences"]), dict(s["applied_types"])
    return s


def apply_batch(project: Project, edit_ids: list[str], approved_by: str) -> dict[str, Any]:
    """Aplica as edicoes numa copia, valida e so promove se nao surgir erro novo."""
    if not approved_by or not approved_by.strip():
        raise EditError("apply_edit exige approved_by com o nome de quem aprovou")
    pending = {e.id: e for e in list_pending(project)}
    missing = [i for i in edit_ids if i not in pending]
    if missing:
        raise EditError(f"edicao pendente nao encontrada: {', '.join(missing)}")
    edits = [pending[i] for i in edit_ids]
    staging = stage(project)
    try:
        before = [f.model_dump() for f in validate(staging).findings if f.level == "error"]
        results: list[dict[str, Any]] = []
        for edit_id in edit_ids:
            try:
                results.append(apply_edit(staging, edit_id, approved_by))
            except Exception as exc:  # noqa: BLE001 - qualquer falha aborta o lote sem promover
                raise BatchError(f"lote abortado em {edit_id}: {exc}") from exc
        known = {_key(f) for f in before}
        new_errors = [f.model_dump() for f in validate(staging).findings
                      if f.level == "error" and _key(f.model_dump()) not in known]
        if new_errors:
            raise BatchError("lote abortado, erros novos no validate", new_errors)
        promote(staging, project)
    finally:
        shutil.rmtree(staging.root, ignore_errors=True)
    return {
        "applied": [r for r in results if r.get("status") != "rejected"],
        "rejected": [r for r in results if r.get("status") == "rejected"],
        "preexisting_errors": before,
        "summary": _summary(edits, results),
    }
