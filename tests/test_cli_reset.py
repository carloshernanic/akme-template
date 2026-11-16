from typer.testing import CliRunner

from akme.cli import app
from akme.ontology import class_names, load_content, load_graph, load_manifest, save_manifest
from akme.tools import ontology_write
from akme.tools.reset import TEMPLATE_DIR, reset_ontology


def _dirty(project):
    ontology_write.propose_edit(project, "add_glossary", {"acronym": "UF", "meaning": "estado"})
    (project.ontology_dir / "changelog.yml").write_text("entries: []\n", encoding="utf-8")
    m = load_manifest(project)
    m["version"] = "2.3.4"
    save_manifest(project, m)


def test_reset_volta_ao_template_e_guarda_backup(seeded, monkeypatch):
    monkeypatch.chdir(seeded.root)
    _dirty(seeded)
    assert len(class_names(load_graph(seeded.schema_path))) > 4
    result = CliRunner().invoke(app, ["reset", "--yes"])
    assert result.exit_code == 0, result.output
    onto = seeded.ontology_dir
    assert (onto / "schema.ttl").read_text(encoding="utf-8") == (TEMPLATE_DIR / "schema.ttl").read_text(encoding="utf-8")
    assert load_content(seeded)["terms"] == []
    assert not (onto / "changelog.yml").exists()
    assert [p.name for p in (onto / "pending").iterdir()] == [".gitkeep"]
    assert load_manifest(seeded)["version"] == "0.1.0"
    backups = list((seeded.root / "backups").iterdir())
    assert len(backups) == 1
    assert (backups[0] / "changelog.yml").exists()
    assert len(list((backups[0] / "pending").glob("*.yml"))) == 1


def test_reset_sem_confirmar_nao_altera(seeded, monkeypatch):
    monkeypatch.chdir(seeded.root)
    before = seeded.schema_path.read_text(encoding="utf-8")
    result = CliRunner().invoke(app, ["reset"], input="n\n")
    assert result.exit_code == 0, result.output
    assert seeded.schema_path.read_text(encoding="utf-8") == before
    assert not (seeded.root / "backups").exists()


def test_reset_com_pending_em_uso(seeded, monkeypatch):
    # no Windows, quem esta com a pasta aberta (aqui o cwd) impede apaga-la; os arquivos dentro saem
    _dirty(seeded)
    monkeypatch.chdir(seeded.pending_dir)
    reset_ontology(seeded)
    assert [p.name for p in seeded.pending_dir.iterdir()] == [".gitkeep"]
    assert load_content(seeded)["terms"] == []
    assert not (seeded.ontology_dir / "changelog.yml").exists()


def test_template_do_pacote_e_a_ontologia_em_branco(project):
    # o template guardado no pacote tem so as classes raiz e nenhum conteudo
    names = class_names(load_graph(TEMPLATE_DIR / "schema.ttl"))
    assert {"Entity", "Relation", "Rule", "Metric"} <= set(names)
    assert names == class_names(load_graph(project.schema_path))
