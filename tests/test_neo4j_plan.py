"""Plano da carga no Neo4j (dry-run): le cada fonte em blocos, sem teto de linhas, e lista problemas e avisos."""
from __future__ import annotations

import pytest

from akme.adapters.local_folder import LocalFolderAdapter
from akme.ontology import load_content, save_content
from akme.project import Project, read_yaml, write_yaml
from akme.tools import neo4j_plan
from akme.tools import ontology_write
from akme.tools.neo4j_plan import build_plan
from akme.tools.profile import profile

EXPECTED_NODES = {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
EXPECTED_EDGES = {"contem": 17, "pertenceA": 10, "referencia": 17}


def _rewrite_csv(project, name, text):
    (project.root / "data" / name).write_text(text, encoding="utf-8")
    profile(project)


def _edit_sources(project, change):
    """Altera a secao sources aprovada no content.yml, como se outra decisao da etapa 5 tivesse sido aplicada."""
    content = read_yaml(project.content_path)
    entries = {s["source"]: s for s in content.get("sources") or []}
    change(entries)
    content["sources"] = list(entries.values())
    write_yaml(project.content_path, content)
    return Project(project.root)


def _set_key(project, source, key):
    def change(entries):
        if key is None:
            entries.pop(source)
        else:
            entries.setdefault(source, {"source": source, "types": {}})["key"] = key
    return _edit_sources(project, change)


def _set_types(project, types):
    def change(entries):
        for source, entry in entries.items():
            entry["types"] = types.get(source, {})
        for source in set(types) - set(entries):
            entries[source] = {"source": source, "key": ["a"], "types": types[source]}
    return _edit_sources(project, change)


def _add_mapping(monkeypatch, mapping):
    real = neo4j_plan.build_export
    def patched(project):
        data = real(project)
        data["mappings"] = [*data["mappings"], mapping]
        return data
    monkeypatch.setattr(neo4j_plan, "build_export", patched)


# --- portados de tests/test_publish_neo4j.py (dry-run) ---

def test_composite_key_identifies_items(seeded):
    profile(seeded)
    p = build_plan(seeded)
    items = next(s for s in p.sources if s.source == "itens_pedido")
    assert items.key == ["id_pedido", "sku"] and items.label == "ItemPedido"
    assert p.nodes["ItemPedido"] == 17 and p.problems == []


def test_source_without_key_is_refused(seeded):
    profile(seeded)
    project = _set_key(seeded, "itens_pedido", None)
    assert any("itens_pedido" in p and "etapa 5" in p for p in build_plan(project).problems)


def test_declared_key_with_unknown_column_is_refused(seeded):
    profile(seeded)
    project = _set_key(seeded, "itens_pedido", ["id_pedido", "nao_existe"])
    assert any("nao_existe" in p for p in build_plan(project).problems)


def test_declared_key_for_unknown_source_is_refused(seeded):
    profile(seeded)
    project = _set_key(seeded, "nao_existe", ["a"])
    assert any("nao_existe" in p for p in build_plan(project).problems)


def test_repeated_composite_key_is_refused(seeded):
    path = seeded.root / "data" / "itens_pedido.csv"
    _rewrite_csv(seeded, "itens_pedido.csv", path.read_text(encoding="utf-8") + "1001,CIM-50,1,1.00\n")
    assert any("itens_pedido.id_pedido+sku" in p and "1001" in p for p in build_plan(seeded).problems)


def test_empty_part_of_composite_key_is_refused(seeded):
    path = seeded.root / "data" / "itens_pedido.csv"
    _rewrite_csv(seeded, "itens_pedido.csv", path.read_text(encoding="utf-8") + "1001,,1,1.00\n")
    assert any("chave id_pedido, sku vazia" in p for p in build_plan(seeded).problems)


@pytest.mark.parametrize("old,new,message", [
    ("2026-07-03", "03/07/2026", "pedidos.dt_pedido: 1 valor(es) invalido(s) para date"),
    ("4120.50", "4.120,50", "pedidos.vl_total: 1 valor(es) invalido(s) para float"),
])
def test_invalid_value_is_refused(seeded, old, new, message):
    path = seeded.root / "data" / "pedidos.csv"
    _rewrite_csv(seeded, "pedidos.csv", path.read_text(encoding="utf-8").replace(old, new, 1).replace('4.120,50', '"4.120,50"'))
    assert any(message in p for p in build_plan(seeded).problems)


@pytest.mark.parametrize("types,fragment", [
    ({"nao_existe": {"a": "string"}}, "nao_existe"),
    ({"pedidos": {"nao_existe": "string"}}, "nao_existe"),
    ({"pedidos": {"status": "booleano"}}, "booleano"),
    ({"pedidos": {"id_cliente": "integer"}}, "id_cliente"),
    ({"itens_pedido": {"sku": "date"}}, "sku"),
])
def test_invalid_type_declaration_is_refused(seeded, types, fragment):
    assert any(fragment in p for p in build_plan(_set_types(seeded, types)).problems)


def test_duplicate_key_is_refused_instead_of_merging_rows(seeded):
    _rewrite_csv(seeded, "clientes.csv", "id_cliente,nm_cliente,cnpj,uf,dt_cadastro,fl_ativo\n"
                                         "1,A,1,SP,2023-01-15,S\n1,B,2,MG,2023-01-15,S\n")
    assert any("clientes.id_cliente" in p for p in build_plan(seeded).problems)


def test_demo_has_no_problems(seeded):
    profile(seeded)
    assert build_plan(seeded).problems == []


def test_source_without_class_is_refused(seeded):
    profile(seeded)
    (seeded.root / "data" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    assert any("extra" in p and "sem classe" in p for p in build_plan(seeded).problems)


def test_source_can_be_excluded_explicitly(seeded):
    profile(seeded)
    (seeded.root / "data" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    project = _edit_sources(seeded, lambda entries: entries.update(extra={"source": "extra", "exclude": "fora do escopo"}))
    p = build_plan(project)
    assert p.problems == [] and p.sources_skipped == ["extra"]
    assert p.nodes == EXPECTED_NODES


def test_excluding_unknown_source_is_a_problem(seeded):
    profile(seeded)
    project = _edit_sources(seeded, lambda entries: entries.update(nao_existe={"source": "nao_existe", "exclude": "x"}))
    assert any("nao_existe" in p for p in build_plan(project).problems)


def test_source_with_two_classes_is_refused(seeded, monkeypatch):
    profile(seeded)
    _add_mapping(monkeypatch, {"term": "uf", "source": "pedidos", "column": "status", "role": "dimension"})
    assert any("pedidos" in p and "Cliente" in p and "Pedido" in p for p in build_plan(seeded).problems)


def test_two_sources_with_same_class_are_refused(seeded, monkeypatch):
    profile(seeded)
    (seeded.root / "data" / "clientes2.csv").write_text("id_cliente,uf\n99,SP\n", encoding="utf-8")
    _add_mapping(monkeypatch, {"term": "uf", "source": "clientes2", "column": "uf", "role": "dimension"})
    assert any("Cliente" in p and "clientes" in p and "clientes2" in p for p in build_plan(seeded).problems)


def test_empty_key_is_refused(seeded):
    _rewrite_csv(seeded, "produtos.csv", "sku,ds_produto,categoria,vl_unitario,un_medida\n"
                                         "CIM-50,Cimento,cimento,32.90,SC\n,Sem sku,outros,1.00,UN\n")
    assert any("produtos: 1 linha(s) com chave sku vazia" in p for p in build_plan(seeded).problems)


def test_all_problems_are_listed_together(seeded):
    (seeded.root / "data" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    _rewrite_csv(seeded, "produtos.csv", "sku,ds_produto,categoria,vl_unitario,un_medida\n,Sem sku,outros,1.00,UN\n")
    problems = build_plan(seeded).problems
    assert any("extra" in p for p in problems) and any("chave sku vazia" in p for p in problems)


def test_orphan_foreign_key_is_a_warning(seeded):
    path = seeded.root / "data" / "pedidos.csv"
    _rewrite_csv(seeded, "pedidos.csv", path.read_text(encoding="utf-8").replace("\n1001,1,", "\n1001,999,", 1))
    p = build_plan(seeded)
    assert p.relationships["pertenceA"] == 9
    assert p.problems == []
    assert any("pertenceA: 1 de 10" in w for w in p.warnings)


def test_relation_without_any_match_is_refused(seeded):
    path = seeded.root / "data" / "clientes.csv"
    text = path.read_text(encoding="utf-8").splitlines()
    _rewrite_csv(seeded, "clientes.csv", "\n".join([text[0]] + [f"x{line}" for line in text[1:]]) + "\n")
    assert any("pertenceA" in p and "nenhuma" in p for p in build_plan(seeded).problems)


def test_join_column_missing_in_data_is_refused(seeded):
    path = seeded.root / "data" / "pedidos.csv"
    _rewrite_csv(seeded, "pedidos.csv", path.read_text(encoding="utf-8").replace("id_cliente", "cliente", 1))
    assert any("pertenceA" in p and "id_cliente" in p for p in build_plan(seeded).problems)


def test_metric_column_without_type_is_a_warning(seeded):
    p = build_plan(_set_types(seeded, {}))
    assert any("pedidos.vl_total" in w and "nao soma" in w for w in p.warnings)


def test_demo_has_no_warnings(seeded):
    assert build_plan(seeded).warnings == []


# --- portados de tests/test_export_sources.py ---

def _propose(project, payload):
    return ontology_write.propose_edit(project, "add_source", payload, proposed_by="agent")


def test_export_reads_approved_sources(seeded):
    p = build_plan(seeded)
    assert not p.problems and p.nodes["ItemPedido"] == 17


def test_export_refuses_source_without_approved_entry(seeded):
    content = load_content(seeded)
    content["sources"] = [s for s in content["sources"] if s["source"] != "produtos"]
    write_yaml(seeded.content_path, content)
    assert any("produtos" in p and "etapa 5" in p for p in build_plan(seeded).problems)


def test_export_says_when_decision_is_pending(seeded):
    content = load_content(seeded)
    content["sources"] = [s for s in content["sources"] if s["source"] != "produtos"]
    write_yaml(seeded.content_path, content)
    _propose(seeded, {"source": "produtos", "key": ["sku"]})
    assert any("produtos" in p and "pendente" in p for p in build_plan(seeded).problems)


def test_old_neo4j_block_in_config_is_refused(seeded):
    config = read_yaml(seeded.root / "akme.yml")
    write_yaml(seeded.root / "akme.yml", {**config, "neo4j": {"keys": {"pedidos": "id_pedido"}}})
    p = build_plan(Project(seeded.root))
    assert any("akme.yml" in x and "neo4j" in x for x in p.problems)


# --- novos ---

def test_plan_counts_demo(seeded):
    p = build_plan(seeded)
    assert p.nodes == EXPECTED_NODES
    assert p.relationships == EXPECTED_EDGES and p.rows == 43
    assert p.project == "demo" and p.relations_not_published == [] and p.sources_skipped == []
    assert sum(s.rows for s in p.sources) == 43
    edges = {e.relation: e for e in p.edges}
    assert edges["pertenceA"].from_source == "pedidos" and edges["pertenceA"].to_source == "clientes"
    assert edges["referencia"].expected == 17 and edges["referencia"].from_column == "sku"
    pedidos = next(s for s in p.sources if s.source == "pedidos")
    assert pedidos.types == {"dt_pedido": "date", "vl_total": "float"} and "nf" in pedidos.columns


def test_no_row_limit(seeded):
    lines = ["id_pedido,sku,qt_itens,vl_item"] + [f"1001,SKU-{i},1,1.00" for i in range(120_000)]
    (seeded.root / "data" / "itens_pedido.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    p = build_plan(seeded)
    assert not any("truncada" in x for x in p.problems)
    assert p.nodes["ItemPedido"] == 120_000
    assert p.relationships["contem"] == 120_000
    # os SKU novos nao existem em produtos: aresta referencia nenhuma, e isso e problema, nao excecao
    assert any("referencia" in x and "nenhuma das 120000" in x for x in p.problems)


def test_plan_reads_each_source_in_blocks(seeded, monkeypatch):
    calls = []
    real = LocalFolderAdapter.iter_rows

    def spy(self, source, batch=5000):
        calls.append((source, batch))
        return real(self, source, batch)

    def must_not_sample(*args, **kwargs):
        raise AssertionError("o plano le em blocos, nao por amostra")

    monkeypatch.setattr(LocalFolderAdapter, "iter_rows", spy)
    monkeypatch.setattr(LocalFolderAdapter, "read_sample", must_not_sample)
    build_plan(seeded)
    assert sorted(calls) == [("clientes", 5000), ("itens_pedido", 5000), ("pedidos", 5000), ("produtos", 5000)]


def test_plan_closes_the_adapter_even_on_error(seeded, monkeypatch):
    closed = []

    def boom(self, source, batch=5000):
        raise RuntimeError("falha de leitura")
        yield  # pragma: no cover

    monkeypatch.setattr(LocalFolderAdapter, "iter_rows", boom)
    monkeypatch.setattr(LocalFolderAdapter, "close", lambda self: closed.append(True))
    with pytest.raises(RuntimeError, match="falha de leitura"):
        build_plan(seeded)
    assert closed == [True]


def test_empty_source_plans_zero_nodes(seeded):
    (seeded.root / "data" / "produtos.csv").write_text("sku,ds_produto,categoria,vl_unitario,un_medida\n", encoding="utf-8")
    p = build_plan(seeded)
    assert p.nodes["Produto"] == 0
    assert p.relationships["referencia"] == 0
    assert any("relacao referencia: nenhuma das 17 linha(s) de itens_pedido encontra alvo em produtos" == x for x in p.problems)


def test_empty_source_still_checks_declared_columns(seeded):
    (seeded.root / "data" / "produtos.csv").write_text("sku,ds_produto,categoria,vl_unitario,un_medida\n", encoding="utf-8")
    project = _set_types(_set_key(seeded, "produtos", ["nao_existe"]), {"produtos": {"vl_nao_existe": "float"}})
    problems = build_plan(project).problems
    assert "fonte produtos: chave declarada usa coluna inexistente: nao_existe" in problems
    assert "etapa 5 cita coluna inexistente: produtos.vl_nao_existe" in problems


def test_empty_source_still_checks_join_columns(seeded):
    (seeded.root / "data" / "produtos.csv").write_text("cod,ds_produto\n", encoding="utf-8")
    project = _set_key(seeded, "produtos", ["cod"])
    assert any("referencia" in p and "produtos.sku" in p for p in build_plan(project).problems)


def test_reserved_column_name_is_refused(seeded):
    path = seeded.root / "data" / "clientes.csv"
    header, *rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([header + ",_id", *[r + ",x" for r in rows]]) + "\n", encoding="utf-8")
    assert any(p.startswith("fonte clientes: a coluna _id tem um nome reservado") and "Renomeie a coluna na origem" in p
               for p in build_plan(seeded).problems)


def test_reserved_class_name_is_refused(seeded):
    from rdflib import OWL, RDF
    from akme.ontology import base_ns, load_graph, save_graph

    g = load_graph(seeded.schema_path)
    g.add((base_ns(g)["Conceito"], RDF.type, OWL.Class))
    save_graph(g, seeded.schema_path)
    assert any(p.startswith("o nome de classe Conceito e reservado") for p in build_plan(seeded).problems)


def test_reserved_descricao_column_is_refused(seeded):
    path = seeded.root / "data" / "clientes.csv"
    header, *rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([header + ",_descricao", *[r + ",x" for r in rows]]) + "\n", encoding="utf-8")
    assert any(p.startswith("fonte clientes: a coluna _descricao tem um nome reservado") for p in build_plan(seeded).problems)


def test_reserved_termo_class_name_is_refused(seeded):
    from rdflib import OWL, RDF
    from akme.ontology import base_ns, load_graph, save_graph

    g = load_graph(seeded.schema_path)
    g.add((base_ns(g)["Termo"], RDF.type, OWL.Class))
    save_graph(g, seeded.schema_path)
    assert any(p.startswith("o nome de classe Termo e reservado") for p in build_plan(seeded).problems)


# --- revisao final ---

def test_csv_row_with_extra_columns_is_a_problem(seeded):
    path = seeded.root / "data" / "clientes.csv"
    path.write_text(path.read_text(encoding="utf-8") + "9,Bia, Jr,1,SP,2023-01-01,S\n", encoding="utf-8")
    problems = build_plan(seeded).problems
    assert "1 linha(s) de clientes com colunas a mais ou a menos; primeira: linha 10" in problems


def test_source_with_key_and_no_rows_is_a_problem(seeded):
    (seeded.root / "data" / "produtos.csv").write_text("sku,ds_produto,categoria,vl_unitario,un_medida\n", encoding="utf-8")
    problems = build_plan(seeded).problems
    assert any(p.startswith("fonte produtos sem linhas") and "Produto" in p for p in problems)


def test_identifier_with_unicode_escape_is_a_problem(seeded):
    project = _rename_join_column(seeded, "id_cliente", "id\\u0060x")
    problems = build_plan(project).problems
    assert any("id\\u0060x" in p and "identificador" in p for p in problems)


def _rename_join_column(project, old, new):
    for path in (project.content_path, project.root / "data" / "clientes.csv", project.root / "data" / "pedidos.csv"):
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    return Project(project.root)


def test_class_with_two_metric_mappings_warns_that_the_first_wins(seeded, monkeypatch):
    _add_mapping(monkeypatch, {"term": "faturamento", "source": "pedidos", "column": "vl_total", "role": "metric",
                               "expression": "SUM(vl_total)"})
    warnings = build_plan(seeded).warnings
    assert any("Faturamento" in w and "2 mappings de metrica" in w and "vale o primeiro" in w for w in warnings)


@pytest.mark.parametrize("batch", [0, -5])
def test_plan_refuses_non_positive_batch(seeded, batch):
    with pytest.raises(ValueError, match="batch"):
        build_plan(seeded, batch)


# --- Task 11: nomes reservados e legenda ---

def _add_contract(project, relation, base="pertenceA"):
    content = read_yaml(project.content_path)
    contract = next(c for c in content["relation_contracts"] if c["relation"] == base)
    content["relation_contracts"].append({**contract, "relation": relation, "inverse_of": ""})
    write_yaml(project.content_path, content)
    return Project(project.root)


@pytest.mark.parametrize("reserved", ["RELACAO_ONTOLOGIA", "SUBCLASSE_DE", "TEM_TERMO"])
def test_relation_named_like_an_ontology_layer_type_is_a_problem(seeded, reserved):
    p = build_plan(_add_contract(seeded, reserved))
    assert any(reserved in x and "reservado" in x for x in p.problems)


def test_names_that_only_differ_in_case_are_not_a_problem(seeded):
    p = build_plan(_add_contract(seeded, "pertence_a"))
    assert not any("pertence_a" in x for x in p.problems), "o tipo e o nome exato: pertenceA e pertence_a nao colidem"


def test_caption_prefers_a_name_like_column_and_falls_back_to_the_first_mapped_one(seeded):
    sources = {s.source: s for s in build_plan(seeded).sources}
    # coluna com cara de nome (nm_, ds_), bem preenchida: a legenda e so o valor dela
    assert (sources["clientes"].caption, sources["clientes"].caption_alone) == ("nm_cliente", True)
    assert (sources["produtos"].caption, sources["produtos"].caption_alone) == ("ds_produto", True)
    # sem coluna com cara de nome: a primeira mapeada que nao e chave nem join completa "Label chave"
    assert (sources["pedidos"].caption, sources["pedidos"].caption_alone) == ("dt_pedido", False)
    assert (sources["itens_pedido"].caption, sources["itens_pedido"].caption_alone) == ("qt_itens", False)
    assert not any(s.own_name for s in sources.values())


def _present(**counts):
    from collections import Counter
    return Counter(counts)


def test_caption_choice_skips_sparse_columns_and_identifiers():
    from akme.tools.neo4j_plan import caption_choice

    maps = [{"source": "projetos", "column": "tipo", "term": "tipo_projeto"},
            {"source": "projetos", "column": "projeto_id", "term": "codigo_projeto"},
            {"source": "projetos", "column": "projeto", "term": "nome_projeto"}]
    cols = ["projeto_id", "projeto", "tipo", "orientador"]
    joins = {("projetos", "orientador")}
    # o termo nome_projeto da a cara de nome a coluna `projeto`; `tipo`, preenchida em 1 de 31, nao vira legenda
    assert caption_choice(maps, "projetos", ["projeto_id"], joins, cols, {},
                          _present(projeto_id=31, projeto=31, tipo=1, orientador=31), 31) == ("projeto", True)
    # coluna com cara de nome mas quase vazia nao serve; a mapeada pouco preenchida tambem nao completa a legenda
    sparse = [{"source": "t", "column": "apelido_nome", "term": "apelido"}, {"source": "t", "column": "tipo", "term": "tipo"}]
    assert caption_choice(sparse, "t", ["id"], set(), ["id", "apelido_nome", "tipo"], {},
                          _present(id=10, apelido_nome=2, tipo=3), 10) == (None, False)
    # a chave que e o proprio nome vale como legenda; identificador (cd_, id_) e numero nao
    named = [{"source": "e", "column": "estudante", "term": "nome_estudante"}]
    assert caption_choice(named, "e", ["estudante"], set(), ["estudante"], {}, _present(estudante=5), 5) == ("estudante", True)
    assert caption_choice([], "c", ["cd_nome"], set(), ["cd_nome", "nm_total"], {"nm_total": "float"},
                          _present(cd_nome=5, nm_total=5), 5) == (None, False)


def test_caption_decided_in_step_5_wins_and_a_missing_column_is_a_problem(seeded):
    content = load_content(seeded)
    for entry in content["sources"]:
        if entry["source"] == "pedidos":
            entry["caption"] = "status"
        if entry["source"] == "produtos":
            entry["caption"] = "nao_existe"
    save_content(seeded, content)
    plan = build_plan(seeded)
    sources = {s.source: s for s in plan.sources}
    assert (sources["pedidos"].caption, sources["pedidos"].caption_alone) == ("status", True)
    assert "etapa 5: a legenda de produtos cita coluna inexistente: nao_existe" in plan.problems


def test_template_project_name_is_a_warning(seeded):
    assert not any("akme-template" in w for w in build_plan(seeded).warnings)
    config = seeded.root / "akme.yml"
    text = config.read_text(encoding="utf-8")
    import re as _re
    config.write_text(_re.sub(r"(?m)^project:.*$", "project: akme-template", text), encoding="utf-8")
    from akme.project import Project
    plan = build_plan(Project(seeded.root))
    assert any("ainda se chama akme-template" in w and "antes da primeira carga" in w for w in plan.warnings)


def test_source_with_name_column_keeps_it_and_warns(seeded):
    path = seeded.root / "data" / "produtos.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    _rewrite_csv(seeded, "produtos.csv", "\n".join([lines[0] + ",name"] + [line + ",nome do cliente" for line in lines[1:]]) + "\n")
    p = build_plan(seeded)
    produtos = next(s for s in p.sources if s.source == "produtos")
    assert produtos.own_name and not p.problems
    assert any("produtos" in w and "name" in w and "legenda" in w for w in p.warnings)


# --- rodada final: caractere invisivel e opcao _descricao ---

def test_join_column_with_bom_is_shown_and_explained(seeded):
    content = read_yaml(seeded.content_path)
    contract = next(c for c in content["relation_contracts"] if c["relation"] == "pertenceA")
    contract["join"]["to"]["column"] = "﻿" + contract["join"]["to"]["column"]
    write_yaml(seeded.content_path, content)
    problem = next(p for p in build_plan(seeded).problems if p.startswith("relacao pertenceA"))
    assert "clientes.<U+FEFF>id_cliente" in problem, problem
    assert "﻿" not in problem and "BOM" in problem and "invisivel" in problem


def test_key_column_with_invisible_character_is_shown(seeded):
    content = read_yaml(seeded.content_path)
    entry = next(s for s in content["sources"] if s["source"] == "produtos")
    entry["key"] = ["sku​"]
    write_yaml(seeded.content_path, content)
    problem = next(p for p in build_plan(seeded).problems if "chave declarada" in p)
    assert "sku<U+200B>" in problem and "​" not in problem and "invisivel" in problem


def test_descricao_on_data_is_off_by_default(seeded):
    assert build_plan(seeded).descricao is False


@pytest.mark.parametrize("value,expected", [(True, True), (False, False)])
def test_neo4j_block_turns_descricao_on(seeded, value, expected):
    config = read_yaml(seeded.root / "akme.yml")
    write_yaml(seeded.root / "akme.yml", {**config, "neo4j": {"descricao_nos_dados": value}})
    plan = build_plan(Project(seeded.root))
    assert plan.descricao is expected and not any("akme.yml" in x for x in plan.problems)


def test_neo4j_option_that_is_not_boolean_is_refused(seeded):
    config = read_yaml(seeded.root / "akme.yml")
    write_yaml(seeded.root / "akme.yml", {**config, "neo4j": {"descricao_nos_dados": "sim"}})
    plan = build_plan(Project(seeded.root))
    assert any("neo4j.descricao_nos_dados" in x and "true ou false" in x for x in plan.problems)


def test_old_keys_next_to_the_new_option_are_still_refused(seeded):
    config = read_yaml(seeded.root / "akme.yml")
    write_yaml(seeded.root / "akme.yml", {**config, "neo4j": {"descricao_nos_dados": True, "keys": {"pedidos": "id_pedido"}}})
    plan = build_plan(Project(seeded.root))
    assert any("akme.yml" in x and "keys" in x and "etapa 5" in x for x in plan.problems)


def test_caption_choice_needs_a_column_that_tells_records_apart():
    """Coluna com cara de nome que repete demais (cidade do cliente, categoria do produto) nao vira legenda sozinha."""
    from akme.tools.neo4j_plan import caption_choice

    cols = ["id_cliente", "nm_cidade", "uf"]
    args = ([], "clientes", ["id_cliente"], set(), cols, {}, _present(id_cliente=100, nm_cidade=100, uf=100), 100)
    assert caption_choice(*args, distinct={"nm_cidade": 0.05}) == (None, False)
    assert caption_choice(*args, distinct={"nm_cidade": 0.97}) == ("nm_cidade", True)
    assert caption_choice(*args) == ("nm_cidade", True), "sem a medida, vale a regra antiga"
    # mapeada e repetitiva: completa `Label chave`, nao substitui
    maps = [{"source": "clientes", "column": "nm_cidade", "term": "cidade"}]
    assert caption_choice(maps, *args[1:], distinct={"nm_cidade": 0.05}) == ("nm_cidade", False)
    # a decisao da etapa 5 vale sempre
    assert caption_choice(*args, declared="nm_cidade", distinct={"nm_cidade": 0.05}) == ("nm_cidade", True)


def test_scan_measures_distinct_values_with_bounded_memory(seeded, monkeypatch):
    monkeypatch.setattr(neo4j_plan, "DISTINCT_CAP", 5)
    plan = build_plan(seeded)
    assert not plan.problems
    data = seeded.root / "data" / "clientes.csv"
    rows = ["id_cliente,nm_cliente,cnpj,uf,dt_cadastro,fl_ativo"] + [f"{i},Loja,1,SP,2026-01-01,1" for i in range(1, 41)]
    data.write_text("\n".join(rows) + "\n", encoding="utf-8")
    src = next(s for s in build_plan(seeded).sources if s.source == "clientes")
    assert (src.caption, src.caption_alone) != ("nm_cliente", True), "40 clientes com o mesmo nome: nao distingue"
