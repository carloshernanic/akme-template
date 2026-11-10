from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "akme" / "static"


def test_index_has_shell_and_loads_modules():
    html = (DOCS / "index.html").read_text(encoding="utf-8")
    for needle in ('id="tab-ontologia"', 'id="tab-revisao"', 'id="view-revisao"', 'id="view-ontologia"', 'id="gate-banner"',
                   'id="stepper"', 'id="rv-nav"', 'href="akme.css"', 'src="ontology.js"', 'src="graph.js"', 'src="etapa1.js"', 'src="review.js"', 'src="app.js"',
                   'brand/akme-symbol-light.svg', 'brand/akme-symbol-dark.svg'):
        assert needle in html, needle
    assert "<style>" not in html, "o CSS vive em akme.css"
    assert html.index('src="etapa1.js"') < html.index('src="review.js"'), "a etapa 1 carrega antes da revisao"


def test_review_js_talks_to_every_endpoint():
    js = (DOCS / "review.js").read_text(encoding="utf-8")
    for needle in ("window.AkmeReview", "/api/review", "/api/propose", "/api/apply", "/api/data", "/api/events", "/api/sources", "akme-reviewer"):
        assert needle in js, needle
    # card enxuto da pergunta: sem o campo Uso, detalhes recolhidos e motivo em botoes
    assert "Usar na construção" not in js and "Guardar para o teste" not in js
    assert 'data-act="details"' in js and 'data-act="why"' in js
    assert 'data-act="mode"' in js, "seletor Etapa 1 / Outras propostas"
    assert '"Ajuste"' not in js


def test_etapa1_js_has_three_screens():
    js = (DOCS / "etapa1.js").read_text(encoding="utf-8")
    for needle in ("window.AkmeEtapa1", "Nada a decidir", "Caso de uso", "Perguntas", "Lacunas e divergências"):
        assert needle in js, needle
    assert "Usar na construção" not in js and "Guardar para o teste" not in js


def test_etapa1_tela_de_perguntas():
    js = (DOCS / "etapa1.js").read_text(encoding="utf-8")
    for needle in ("+ Criar pergunta", "Nova pergunta", "Fora dos casos escolhidos", "Já aplicadas",
                   'data-e1="cq-dec"', 'data-e1="cq-prio"', 'data-e1="cq-why"', "Outro motivo", '"add_competency_question"'):
        assert needle in js, needle


def test_graph_js_exposes_init_and_update():
    js = (DOCS / "graph.js").read_text(encoding="utf-8")
    assert "window.AkmeGraph" in js and "function init(" in js and "function update(" in js
    assert "chip" not in js, "classes antigas de chip foram trocadas por badge"


def test_css_follows_qbds_tokens():
    css = (DOCS / "akme.css").read_text(encoding="utf-8")
    for token in ("--surface-base", "--fill-active", "--text-primary", "--border-focus", "--status-error", "--qb-accent", ":root[data-theme=\"dark\"]"):
        assert token in css, token
    assert "--rad: 0;" in css, "QBDS: cantos retos"
    for component in (".btn", ".badge", ".callout", ".card", ".stepper", ".seg", ".input", ".kv"):
        assert component + " {" in css or component + "," in css, component
    for font in ("fonts/inter-latin.woff2", "fonts/roboto-mono-latin.woff2"):
        assert font in css and (DOCS / font).exists(), font
    assert "googleapis" not in css


def test_export_copies_the_page_into_docs(project):
    from akme.tools.export import export
    out = export(project)
    assert "index.html" in out["page_updated"] and (project.docs_dir / "index.html").exists()
    for f in ("akme.css", "app.js", "graph.js", "review.js", "etapa1.js", "fonts/inter-latin.woff2", "brand/akme-symbol-light.svg"):
        assert (project.docs_dir / f).exists(), f
    assert export(project)["page_updated"] == []
    (project.docs_dir / "akme.css").write_text("alterado", encoding="utf-8")
    assert export(project)["page_updated"] == ["akme.css"]
