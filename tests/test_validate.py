from akme.ontology import load_content, save_content
from akme.tools.profile import profile
from akme.tools.validate import validate


def test_empty_template_is_valid(project):
    report = validate(project)
    assert report.ok
    assert any(f.check == "profile_missing" for f in report.findings)
    assert report.pitfalls == []


def test_seeded_demo_validates_with_coverage(seeded):
    profile(seeded)
    report = validate(seeded)
    assert report.ok, [f.message for f in report.errors]
    assert report.coverage["mapped"] == 10
    assert report.coverage["by_source"]["pedidos"]["unmapped"] == ["id_cliente", "nf"]
    codes = {(p["code"], p["subject"]) for p in report.pitfalls}
    assert ("P13", "referencia") in codes
    assert ("P13", "pertenceA") not in codes
    assert seeded.validation_path.exists()


def test_detects_broken_references(seeded):
    profile(seeded)
    content = load_content(seeded)
    content["terms"].append({"name": "fantasma", "class": "NaoExiste", "definition": ""})
    content["mappings"].append({"term": "pedido", "source": "pedidos", "column": "coluna_errada"})
    content["precedence"].append({"topic": "cliente ativo", "winner": "erp", "over": "financeiro"})
    save_content(seeded, content)
    report = validate(seeded)
    assert not report.ok
    assert {f.check for f in report.errors} == {"term_class", "mapping_column", "precedence_conflict"}


def test_broken_ttl_is_reported(project):
    project.schema_path.write_text("isto nao e turtle @@", encoding="utf-8")
    report = validate(project)
    assert not report.ok and report.errors[0].check == "ttl_parse"
