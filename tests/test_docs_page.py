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
    assert html.index('src="outras.js"') < html.index('src="review.js"'), "outras propostas carrega antes da revisao"


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


def test_etapa1_tela_de_lacunas_e_salvar():
    js = (DOCS / "etapa1.js").read_text(encoding="utf-8")
    for needle in ("Pedir o dado ao cliente", "Reformular a pergunta", "nenhuma das duas? outras opções", "São coisas diferentes",
                   "Conferir e salvar", "Salvar e aplicar", "Seu nome", '"/api/apply"', 'stage: "requirements"',
                   '"/api/review"', '"/api/propose"', '"add_gap"', '"add_divergence"'):
        assert needle in js, needle
    assert "Em construção" not in js


def test_etapa1_mostra_so_telas_com_itens_e_respeita_o_modo_automatico():
    js = (DOCS / "etapa1.js").read_text(encoding="utf-8")
    for needle in ("function visibleSteps(", "function remaining(", "onCount", "Modo automático", 'dataset.decisionMode === "auto"'):
        assert needle in js, needle
    review = (DOCS / "review.js").read_text(encoding="utf-8")
    assert "onCount: updateE1Count" in review and "e1Has()" in review
    css = (DOCS / "akme.css").read_text(encoding="utf-8")
    assert "body.chat-open .e1-foot" in css, "o rodape da etapa 1 abre espaco para a conversa"


def test_etapa1_tela_do_glossario():
    js = (DOCS / "etapa1.js").read_text(encoding="utf-8")
    for needle in ('"add_glossary"', "Glossário", "Confira cada sigla.", 'data-e1="gl-dec"', 'data-e1="gl-all"', "Não é usada"):
        assert needle in js, needle
    review = (DOCS / "review.js").read_text(encoding="utf-8")
    assert "Conferir e salvar" in review, "a faixa do agente esperando fala do botao da etapa 1"


def test_base_comum_em_portugues_e_sem_ids_crus():
    graph = (DOCS / "graph.js").read_text(encoding="utf-8")
    for velho in ('"relacoes"', "Competency questions", "<h3>Relacoes</h3>", "Sem validate", '"pitfalls"', "Glossario<"):
        assert velho not in graph, velho
    for novo in ("Propósito e perguntas", "mapeamentos", "Armadilhas de modelagem", "Glossário"):
        assert novo in graph, novo
    review = (DOCS / "review.js").read_text(encoding="utf-8")
    assert "function humanMissing" in review and ".map(humanMissing)" in review
    # o banner nomeia o pendente da etapa 1 e leva ate ele, em vez de "Decidir 1 item da etapa 1"
    assert "function pendingLabel" in review and 'data-act="goto"' in review
    css = (DOCS / "akme.css").read_text(encoding="utf-8")
    assert ".rv-section > h3, .panel-section h3, .e1-sub {" in css
    assert ".rv-empty, .e1-empty, .chat-empty {" in css


def test_aba_ontologia_no_padrao():
    graph = (DOCS / "graph.js").read_text(encoding="utf-8")
    assert '"Árvore lateral"' not in graph and "Nenhuma classe escolhida" in graph
    assert "guardada para o teste" in graph and 'class="onto-cq"' in graph and "levelOf(" in graph
    css = (DOCS / "akme.css").read_text(encoding="utf-8")
    assert "grid-template-columns: repeat(6, minmax(0, 1fr))" in css


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


def test_outras_propostas_no_padrao_novo():
    js = (DOCS / "outras.js").read_text(encoding="utf-8")
    for needle in ("window.AkmeOutras", "Conferir e salvar", "Salvar e aplicar", "Aceitar tudo", "Já aplicadas", "ver detalhes", "rever",
                   '"/api/review"', '"/api/propose"', '"/api/apply"', '"update_gap"', '"update_divergence"', '"remove_competency_question"',
                   "Modo automático"):
        assert needle in js, needle
    review = (DOCS / "review.js").read_text(encoding="utf-8")
    assert "window.AkmeOutras" in review and 'id="ou-root"' in review, "review.js monta outras.js e cai na caixa antiga sem ele"


def test_export_copia_outras_js():
    from akme.tools.export import PAGE_FILES
    assert "outras.js" in PAGE_FILES
