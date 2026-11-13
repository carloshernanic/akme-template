"""Tutorial do projeto no Neo4j Browser: curto, so navegacao."""
from __future__ import annotations

import csv
import io
import re

from akme.tools.neo4j_guide import guide_html, saved_queries_csv
from akme.tools.neo4j_plan import build_plan


def _slides(text):
    return [s for s in text.split("<slide ")[1:]]


def test_guide_is_deterministic(seeded):
    plan = build_plan(seeded)
    assert guide_html(plan) == guide_html(build_plan(seeded))
    assert saved_queries_csv(plan) == saved_queries_csv(build_plan(seeded))


def test_guide_has_six_short_navigation_slides(seeded):
    text = guide_html(build_plan(seeded))
    assert '<article class="guide"><carousel class="deck container-fluid">' in text
    titles = re.findall(r"<h3>(.*?)</h3>", text)
    assert titles == ["O que tem aqui", "A ontologia", "Os dados", "Explorar", "Como navegar", "Perguntas em portugues"]
    for slide in _slides(text):
        prose = re.sub(r"<pre.*?</pre>", "", slide, flags=re.S)
        prose = re.sub(r"<[^>]+>", " ", prose)
        assert len(" ".join(prose.split())) < 600, "texto curto por slide"
    for forbidden in ("<script", "<iframe", "<svg", "<form"):
        assert forbidden not in text


def test_no_competency_questions_nor_llm_schema_in_the_guide(seeded):
    text = guide_html(build_plan(seeded)) + saved_queries_csv(build_plan(seeded))
    for gone in ("CQ-", "competencia", "p.esquema"):
        assert gone not in text


def test_what_is_here_lists_each_label_with_the_plan_count(seeded):
    first = _slides(guide_html(build_plan(seeded)))[0]
    for label, n in {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}.items():
        assert f"<li><code>{label}</code>: {n}</li>" in first


def test_ontology_map_with_and_without_apoc(seeded):
    plan = build_plan(seeded)
    dry = _slides(guide_html(plan))[1]
    assert "apoc.create.vRelationship(a, r.nome, {}, b)" in dry and "RETURN a, r, b" in dry, "sem banco: as duas"
    with_apoc = _slides(guide_html(plan, apoc=True))[1]
    assert "apoc.create.vRelationship" in with_apoc and "RETURN a, r, b" not in with_apoc
    without = _slides(guide_html(plan, apoc=False))[1]
    assert "apoc.create" not in without and "<code>nome</code>" in without


def test_data_map_explore_and_navigation(seeded):
    slides = _slides(guide_html(build_plan(seeded)))
    assert "CALL db.schema.visualization()" in slides[2] and "'Conceito', 'Termo', '_AkmeProjeto'" in slides[2]
    for label in ("Cliente", "ItemPedido", "Pedido", "Produto"):
        assert f"MATCH (n:{label}) WITH n LIMIT 1\nMATCH p = (n)--(m)\nWHERE NOT m:Conceito\nRETURN p LIMIT 25" in slides[3]
    assert "Colunas" not in slides[3] and "[*1..2]" not in slides[3]
    nav = slides[4]
    assert "tipo de relacao" in nav and "Dois cliques" in nav and "_descricao" not in nav, "padrao: sem _descricao nos dados"
    assert "definicao" in nav and "slide A ontologia" in nav
    assert "RELACAO_ONTOLOGIA</code> = relacao da ontologia" in nav and "Results overview" in nav
    aura = slides[5]
    assert "console.neo4j.io" in aura and "APOC" in aura and "Perguntas em portugues pelo Aura console" in aura
    assert "nao foi testado" in aura and "AuraDB" in aura, "o akme so foi testado com Neo4j local em Docker"


def test_guide_has_no_data_values_nor_clock(seeded):
    text = guide_html(build_plan(seeded)) + saved_queries_csv(build_plan(seeded))
    for value in ("Construtora Horizonte", "12345678000101", "CIM-50", "Cimento CP II", "55010", "2026-07-03"):
        assert value not in text
    assert not re.search(r"\d{4}-\d\d-\d\dT\d\d:\d\d", text)


def test_project_name_is_escaped_in_the_guide(seeded):
    plan = build_plan(seeded)
    plan.project = "o'<b>x"
    text = guide_html(plan)
    assert "<b>x" not in text.replace("<b>x</b>", "") and "o'&lt;b&gt;x" in text
    assert "{_projeto: 'o\\'&lt;b&gt;x'}" in text


def test_saved_queries_csv_has_only_navigation_queries(seeded):
    rows = list(csv.DictReader(io.StringIO(saved_queries_csv(build_plan(seeded)))))
    assert list(rows[0]) == ["name", "description", "query", "id", "parentId", "isFolder", "isProtected"]
    assert rows[0]["name"] == "akme demo" and rows[0]["isFolder"] == "true"
    names = [r["name"] for r in rows[1:]]
    assert names == ["1. A ontologia", "2. Os dados", "Explorar: Cliente", "Explorar: ItemPedido", "Explorar: Pedido",
                     "Explorar: Produto"]
    assert all(r["parentId"] == "0" and r["isFolder"] == "false" for r in rows[1:])


def test_publish_dry_run_writes_the_guide_next_to_the_artifact(seeded):
    from akme.tools.neo4j_load import publish_neo4j

    result = publish_neo4j(seeded, {"project": "demo", "version": "0.1.0"}, dry_run=True)
    guide = seeded.docs_dir / "publish" / "neo4j_guia.html"
    queries = seeded.docs_dir / "publish" / "neo4j_consultas.csv"
    assert result["guide"] == str(guide) and result["saved_queries"] == str(queries)
    assert guide.read_text(encoding="utf-8") == guide_html(build_plan(seeded))
    assert queries.read_text(encoding="utf-8").startswith("name,description,query")
    assert not any(k.startswith("cq_") for k in result)
