import shutil
import subprocess
from pathlib import Path

import pytest

from neo4j_fakes import fake  # noqa: F401  (fixture compartilhada dos testes do Neo4j)

from akme.project import Project, read_yaml, write_yaml
from akme.tools import ontology_write

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_review_server_probe(monkeypatch):
    """A mensagem do guia na CLI pergunta ao `akme review` da porta 8765 se ele esta atualizado; nos testes, nenhum
    teste depende de um servidor real nessa porta (o da maquina pode estar no ar)."""
    from akme.tools import neo4j_guide

    monkeypatch.setattr(neo4j_guide, "_stale_lines", lambda port: [])
TEMPLATE_FILES = ("schema.ttl", "content.yml", "manifest.yml")


def _template_ontology(target: Path) -> None:
    """Copia o template de ontologia. Prefere a versao commitada (git HEAD) para que uma ontologia
    em andamento na arvore de trabalho nao contamine os testes; sem git, copia a pasta como esta."""
    target.mkdir(parents=True)
    (target / "pending").mkdir()
    for name in TEMPLATE_FILES:
        try:
            text = subprocess.run(["git", "show", f"HEAD:ontology/{name}"], cwd=ROOT, check=True,
                                  capture_output=True, text=True, encoding="utf-8").stdout
        except (OSError, subprocess.CalledProcessError):
            shutil.copy(ROOT / "ontology" / name, target / name)
            continue
        (target / name).write_text(text, encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Project:
    shutil.copytree(ROOT / "examples" / "local_demo", tmp_path / "data")
    _template_ontology(tmp_path / "ontology")
    shutil.copy(ROOT / "examples" / "local_demo" / "questions.yml", tmp_path / "questions.yml")
    write_yaml(tmp_path / "akme.yml", {
        "project": "demo", "adapter": "local_folder",
        "local_folder": {"path": str(tmp_path / "data")}, "questions": "questions.yml",
    })
    return Project(tmp_path)


@pytest.fixture
def seeded(project: Project) -> Project:
    for e in read_yaml(ROOT / "examples" / "local_demo" / "seed_edits.yml")["edits"]:
        edit = ontology_write.propose_edit(project, e["type"], e["payload"], e.get("rationale", ""),
                                           "seed", e.get("requirement_id"), e.get("evidence", ""))
        ontology_write.apply_edit(project, edit.id, "tester")
    return project
