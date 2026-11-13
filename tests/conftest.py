import functools
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


@functools.lru_cache(maxsize=None)
def _committed(name: str) -> str | None:
    """Texto commitado (git HEAD) de ontology/<name>, lido uma vez por sessao; None sem git."""
    try:
        return subprocess.run(["git", "show", f"HEAD:ontology/{name}"], cwd=ROOT, check=True,
                              capture_output=True, text=True, encoding="utf-8").stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def _template_ontology(target: Path) -> None:
    """Copia o template de ontologia. Prefere a versao commitada (git HEAD) para que uma ontologia
    em andamento na arvore de trabalho nao contamine os testes; sem git, copia a pasta como esta."""
    target.mkdir(parents=True)
    (target / "pending").mkdir()
    for name in TEMPLATE_FILES:
        text = _committed(name)
        if text is None:
            shutil.copy(ROOT / "ontology" / name, target / name)
        else:
            (target / name).write_text(text, encoding="utf-8")


def _demo_project(root: Path) -> Project:
    shutil.copytree(ROOT / "examples" / "local_demo", root / "data")
    _template_ontology(root / "ontology")
    shutil.copy(ROOT / "examples" / "local_demo" / "questions.yml", root / "questions.yml")
    write_yaml(root / "akme.yml", {
        "project": "demo", "adapter": "local_folder",
        "local_folder": {"path": str(root / "data")}, "questions": "questions.yml",
    })
    return Project(root)


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return _demo_project(tmp_path)


@pytest.fixture(scope="session")
def _seeded_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A demo com as edicoes do seed_edits.yml aplicadas, montada uma vez por sessao (as ~50 edicoes passam por
    propose_edit e apply_edit, que releem e regravam o YAML a cada uma: alguns segundos por teste). Nenhum teste
    usa esta pasta direto: `seeded` copia."""
    project = _demo_project(tmp_path_factory.mktemp("seeded_template"))
    for e in read_yaml(ROOT / "examples" / "local_demo" / "seed_edits.yml")["edits"]:
        edit = ontology_write.propose_edit(project, e["type"], e["payload"], e.get("rationale", ""),
                                           "seed", e.get("requirement_id"), e.get("evidence", ""))
        ontology_write.apply_edit(project, edit.id, "tester")
    return project.root


@pytest.fixture
def seeded(_seeded_template: Path, tmp_path: Path) -> Project:
    """Copia propria da demo semeada por teste: os testes continuam isolados (cada um escreve so na sua pasta)."""
    shutil.copytree(_seeded_template, tmp_path, dirs_exist_ok=True)
    config = read_yaml(tmp_path / "akme.yml")
    config["local_folder"]["path"] = str(tmp_path / "data")
    write_yaml(tmp_path / "akme.yml", config)
    return Project(tmp_path)
