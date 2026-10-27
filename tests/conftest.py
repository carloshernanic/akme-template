import shutil
from pathlib import Path

import pytest

from akme.project import Project, read_yaml, write_yaml
from akme.tools import ontology_write

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path: Path) -> Project:
    shutil.copytree(ROOT / "examples" / "local_demo", tmp_path / "data")
    shutil.copytree(ROOT / "ontology", tmp_path / "ontology")
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
