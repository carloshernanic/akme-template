from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ontology import load_content, load_manifest, save_manifest
from ..project import Project, remove_file, write_text_atomic

# ontologia em branco: classes raiz, content.yml so com as secoes e mappings vazios
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "template"
TEMPLATE_FILES = ("schema.ttl", "content.yml", "mappings.yarrrml.yml")
START_VERSION = "0.1.0"


def summary(project: Project) -> dict[str, int]:
    """Quanto a ontologia atual tem, para o humano ver o que vai perder antes de confirmar."""
    content = load_content(project)
    req = content.get("requirements") or {}
    pending = list(project.pending_dir.glob("*.yml")) if project.pending_dir.exists() else []
    return {
        "competency_questions": len(req.get("competency_questions") or []),
        "use_cases": len(req.get("use_cases") or []),
        "terms": len(content.get("terms") or []),
        "mappings": len(content.get("mappings") or []),
        "pending": len(pending),
    }


def reset_ontology(project: Project) -> dict[str, Any]:
    """Guarda a ontologia atual em backups/ e volta a pasta para o template em branco.
    O manifest.yml fica (base_iri e lista de tools), so a versao volta ao inicio."""
    src = project.ontology_dir
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = project.root / "backups" / f"{src.name}-{stamp}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, backup)
    manifest = load_manifest(project)
    # o template entra primeiro, por cima: se algo falhar depois, a pasta ja tem uma ontologia valida
    for name in TEMPLATE_FILES:
        write_text_atomic(src / name, (TEMPLATE_DIR / name).read_text(encoding="utf-8"))
    keep = {"manifest.yml", "pending", *TEMPLATE_FILES}
    for item in src.iterdir():
        if item.name not in keep:
            shutil.rmtree(item) if item.is_dir() else remove_file(item)
    # a pasta pending fica: no Windows, a pagina e o servidor MCP abertos impedem apagar a pasta, nao os arquivos
    project.pending_dir.mkdir(exist_ok=True)
    for item in project.pending_dir.iterdir():
        if item.name != ".gitkeep":
            shutil.rmtree(item) if item.is_dir() else remove_file(item)
    (project.pending_dir / ".gitkeep").touch()
    if manifest:
        manifest["version"] = START_VERSION
        save_manifest(project, manifest)
    return {"backup": backup.relative_to(project.root).as_posix(), "ontology_dir": src.relative_to(project.root).as_posix()}
