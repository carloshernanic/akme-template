"""Tutorial do projeto no Neo4j Browser: curto, so navegacao."""
from __future__ import annotations

import csv
import dataclasses
import io
import re

from akme.tools.neo4j_guide import guide_html, linked_labels, one_record_query, saved_queries_csv, style_grass
from akme.tools.neo4j_plan import build_plan


def _slides(text):
    return [s for s in text.split("<slide ")[1:]]


def test_guide_is_deterministic(seeded):
    plan = build_plan(seeded)
    assert guide_html(plan) == guide_html(build_plan(seeded))
    assert saved_queries_csv(plan) == saved_queries_csv(build_plan(seeded))


def test_guide_has_five_short_navigation_slides(seeded):
    text = guide_html(build_plan(seeded))
    assert '<article class="guide"><carousel class="deck container-fluid">' in text
    titles = re.findall(r"<h3>(.*?)</h3>", text)
    assert titles == ["O que tem aqui", "A ontologia", "Explorar", "Como navegar", "Perguntas em português"]
    for slide in _slides(text):
        prose = re.sub(r"<pre.*?</pre>", "", slide, flags=re.S)
        prose = re.sub(r"<[^>]+>", " ", prose)
        assert len(" ".join(prose.split())) < 700, "texto curto por slide"
    for forbidden in ("<script", "<iframe", "<svg", "<form"):
        assert forbidden not in text


def test_no_competency_questions_nor_llm_schema_in_the_guide(seeded):
    text = guide_html(build_plan(seeded)) + saved_queries_csv(build_plan(seeded))
    for gone in ("CQ-", "competencia", "p.esquema"):
        assert gone not in text


def test_first_slide_opens_with_the_class_map_and_the_whole_graph(seeded):
    plan = build_plan(seeded)
    first = _slides(guide_html(plan))[0]
    assert "CALL db.schema.visualization()" in first and "'Conceito', 'Termo', '_AkmeProjeto'" in first
    assert first.index("db.schema.visualization") < first.index("Registros por classe"), "primeiro o desenho"
    assert "NOT n:Conceito AND NOT n:Termo" in first and "43 registros" in first, "grafo pequeno: tudo de uma vez"
    for label, n in {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}.items():
        assert f"<li><code>{label}</code>: {n}</li>" in first
    plan.nodes["Pedido"] = 5000
    big = _slides(guide_html(plan))[0]
    assert "NOT n:Termo" not in big and "tudo de uma" not in big, "grafo grande: so o mapa"
    assert "<li><code>Pedido</code>: 5.000</li>" in big


def test_ontology_map_with_and_without_apoc(seeded):
    plan = build_plan(seeded)
    dry = _slides(guide_html(plan))[1]
    assert "apoc.create.vRelationship(a, r.nome, {}, b)" in dry and "RETURN a, r, b" in dry, "sem banco: as duas"
    with_apoc = _slides(guide_html(plan, apoc=True))[1]
    assert "apoc.create.vRelationship" in with_apoc and "RETURN a, r, b" not in with_apoc
    without = _slides(guide_html(plan, apoc=False))[1]
    assert "apoc.create" not in without and "<code>nome</code>" in without


def test_concepts_without_data_have_a_query(seeded):
    plan = build_plan(seeded)
    plan.concepts_without_data = []
    assert "publicada_nos_dados" not in guide_html(plan)
    plan.concepts_without_data = ["Banca", "MediaFinal"]
    onto = _slides(guide_html(plan))[1]
    assert "2 conceito(s)" in onto and "WHERE NOT c.publicada_nos_dados" in onto
    assert "4. Conceitos sem dados" in saved_queries_csv(plan)


def test_explore_starts_from_the_most_connected_record(seeded):
    plan = build_plan(seeded)
    slides = _slides(guide_html(plan))
    for label in ("Cliente", "ItemPedido", "Pedido", "Produto"):
        assert (f"MATCH (n:{label}) WITH n ORDER BY COUNT {{ (n)--() }} DESC LIMIT 1\nMATCH p = (n)--(m)\n"
                "WHERE NOT m:Conceito\nRETURN p LIMIT 25") in slides[2]
    assert linked_labels(plan) == {"Cliente", "ItemPedido", "Pedido", "Produto"}
    assert one_record_query("Penalidade", linked=False) == "MATCH (n:Penalidade)\nRETURN n LIMIT 25"
    plan.edges = []  # classe sem relacao nos dados: sem setas, e o guia avisa
    loose = _slides(guide_html(plan))
    assert "<li><code>Cliente</code>: 8 (sem ligações)</li>" in loose[0]
    assert "MATCH (n:Cliente)\nRETURN n LIMIT 25" in loose[2] and "(sem ligações: só os registros)" in loose[2]


def test_navigation_and_aura_slides(seeded):
    slides = _slides(guide_html(build_plan(seeded)))
    nav = slides[3]
    assert "tipo de relação" in nav and "Dois cliques" in nav and "_descricao" not in nav, "padrao: sem _descricao nos dados"
    assert "definicao" in nav and "página A ontologia" in nav
    assert "RELACAO_ONTOLOGIA</code> = relação da ontologia" in nav
    assert "<code>:style</code>" in nav and "docs/publish/neo4j_estilo.grass" in nav
    aura = slides[4]
    assert "console.neo4j.io" in aura and "APOC" in aura and "Perguntas em portugues pelo Aura console" in aura
    assert "não foi testado" in aura and "AuraDB" in aura, "o akme so foi testado com Neo4j local em Docker"


def test_style_has_one_color_per_class_and_grey_ontology(seeded):
    plan = build_plan(seeded)
    text = style_grass(plan)
    assert text == style_grass(build_plan(seeded))
    colors = re.findall(r"node\.(\w+) \{\n  color: (#\w+);\n  diameter: (\d+)px;\n  caption: \"\{name\}\";", text)
    by = {label: (color, int(d)) for label, color, d in colors}
    assert set(by) == {"Cliente", "ItemPedido", "Pedido", "Produto", "Conceito", "Termo", "_AkmeProjeto"}
    data = [by[k][0] for k in ("Cliente", "ItemPedido", "Pedido", "Produto")]
    assert len(set(data)) == 4, "uma cor por classe"
    assert {by[k][0] for k in ("Conceito", "Termo", "_AkmeProjeto")} == {"#C8CDD3"} and "#C8CDD3" not in data
    assert 'relationship.RELACAO_ONTOLOGIA {\n  caption: "{nome}";\n}' in text
    # so o que o Browser 2026.10 importa
    props = set(re.findall(r"^  ([a-z-]+):", text, flags=re.M))
    assert props <= {"caption", "color", "diameter", "shaft-width"}
    plan.sources[0] = dataclasses.replace(plan.sources[0], label="Nome Com Espaco")
    assert "Nome Com Espaco" not in style_grass(plan), "seletor do GraSS nao alcanca: fica com a cor padrao"


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
    assert names[:3] == ["1. O mapa das classes", "2. O grafo inteiro", "3. A ontologia"]
    assert names[-4:] == ["Explorar: Cliente", "Explorar: ItemPedido", "Explorar: Pedido", "Explorar: Produto"]
    assert set(names[3:-4]) <= {"4. Conceitos sem dados"}
    assert all(r["parentId"] == "0" and r["isFolder"] == "false" for r in rows[1:])


def test_publish_dry_run_writes_the_guide_next_to_the_artifact(seeded):
    from akme.tools.neo4j_load import publish_neo4j

    result = publish_neo4j(seeded, {"project": "demo", "version": "0.1.0"}, dry_run=True)
    guide = seeded.docs_dir / "publish" / "neo4j_guia.html"
    queries = seeded.docs_dir / "publish" / "neo4j_consultas.csv"
    assert result["guide"] == str(guide) and result["saved_queries"] == str(queries)
    assert guide.read_text(encoding="utf-8") == guide_html(build_plan(seeded))
    assert queries.read_text(encoding="utf-8").startswith("name,description,query")
    style = seeded.docs_dir / "publish" / "neo4j_estilo.grass"
    assert result["style"] == str(style) and style.read_text(encoding="utf-8") == style_grass(build_plan(seeded))
    assert not any(k.startswith("cq_") for k in result)
