from datetime import date, datetime
from decimal import Decimal

import pytest

from akme.adapters.base import AdapterError
from akme.project import Project, read_yaml, write_yaml
from akme.tools import n10s as exporter
from akme.tools.profile import profile
from akme.tools.publish import PublishError, publish


def _script(project) -> str:
    return (project.docs_dir / "publish" / "neo4j.nt").read_text(encoding="utf-8")


NS = "https://akme.example/ontology#"
XSD = "http://www.w3.org/2001/XMLSchema#"


def _triple(s, p, o) -> str:
    return f"<{NS}{s}> <{NS}{p}> {o} ."


def _rewrite_csv(project, name, text):
    (project.root / "data" / name).write_text(text, encoding="utf-8")
    profile(project)


def test_dry_run_writes_schema_data_and_relationships(seeded):
    profile(seeded)
    r = publish(seeded, "neo4j")
    script = _script(seeded)
    assert r["dry_run"] and r["executed"] == 0 and r["batches"] == 1 and r["triples"] > 0
    assert r["nodes"] == {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
    assert r["relationships"] == {"contem": 17, "pertenceA": 10, "referencia": 17}
    assert _triple("Pedido/1001", "pertenceA", f"<{NS}Cliente/1>") in script
    assert f"<{NS}Pedido/1001> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{NS}Pedido> ." in script
    assert _triple("Pedido/1001", "contem", f"<{NS}ItemPedido/1001/CIM-50>") in script


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


def test_composite_key_identifies_items(seeded):
    profile(seeded)
    publish(seeded, "neo4j")
    script = _script(seeded)
    assert _triple("ItemPedido/1001/CIM-50", "qt_itens", f'"100"^^<{XSD}integer>') in script
    assert "_akme_row" not in script


def _item_rows(script: str) -> set[str]:
    """Propriedades de cada item, sem depender da posicao da linha no script."""
    rows = {line for line in script.splitlines() if line.startswith(f"<{NS}ItemPedido/")}
    assert len({line.split()[0] for line in rows}) == 17
    return rows


def test_identity_does_not_depend_on_row_order(seeded):
    profile(seeded)
    publish(seeded, "neo4j")
    before = _script(seeded)
    path = seeded.root / "data" / "itens_pedido.csv"
    header, *rows = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([header, *reversed(rows)]) + "\n", encoding="utf-8")
    publish(seeded, "neo4j")
    after = _script(seeded)
    assert before != after
    assert _item_rows(before) == _item_rows(after)


def test_source_without_key_is_refused(seeded, monkeypatch):
    profile(seeded)
    project = _set_key(seeded, "itens_pedido", None)
    assert any("itens_pedido" in p and "etapa 5" in p for p in publish(project, "neo4j")["problems"])
    _must_not_load(monkeypatch)
    with pytest.raises(PublishError, match="etapa 5"):
        publish(project, "neo4j", dry_run=False)


def test_declared_key_with_unknown_column_is_refused(seeded):
    profile(seeded)
    project = _set_key(seeded, "itens_pedido", ["id_pedido", "nao_existe"])
    assert any("nao_existe" in p for p in publish(project, "neo4j")["problems"])


def test_declared_key_for_unknown_source_is_refused(seeded):
    profile(seeded)
    project = _set_key(seeded, "nao_existe", ["a"])
    assert any("nao_existe" in p for p in publish(project, "neo4j")["problems"])


def test_repeated_composite_key_is_refused(seeded):
    path = seeded.root / "data" / "itens_pedido.csv"
    _rewrite_csv(seeded, "itens_pedido.csv", path.read_text(encoding="utf-8") + "1001,CIM-50,1,1.00\n")
    assert any("itens_pedido.id_pedido+sku" in p and "1001" in p for p in publish(seeded, "neo4j")["problems"])


def test_empty_part_of_composite_key_is_refused(seeded):
    path = seeded.root / "data" / "itens_pedido.csv"
    _rewrite_csv(seeded, "itens_pedido.csv", path.read_text(encoding="utf-8") + "1001,,1,1.00\n")
    assert any("chave id_pedido, sku vazia" in p for p in publish(seeded, "neo4j")["problems"])


def test_declared_types_are_written(seeded):
    publish(seeded, "neo4j")
    script = _script(seeded)
    assert _triple("Pedido/1001", "id_pedido", f'"1001"^^<{XSD}string>') in script
    assert _triple("Cliente/1", "cnpj", f'"12345678000101"^^<{XSD}string>') in script
    assert _triple("Pedido/1001", "nf", f'"55010"^^<{XSD}string>') in script
    assert _triple("Pedido/1001", "vl_total", f'"4120.50"^^<{XSD}decimal>') in script
    assert _triple("Pedido/1001", "dt_pedido", f'"2026-07-03"^^<{XSD}date>') in script
    assert _triple("Cliente/1", "dt_cadastro", f'"2023-01-15"^^<{XSD}date>') in script
    assert _triple("Cliente/1", "fl_ativo", f'"S"^^<{XSD}string>') in script


def _set_types(project, types):
    def change(entries):
        for source, entry in entries.items():
            entry["types"] = types.get(source, {})
        for source in set(types) - set(entries):
            entries[source] = {"source": source, "key": ["a"], "types": types[source]}
    return _edit_sources(project, change)


def test_undeclared_column_keeps_the_original_text(seeded):
    publish(_set_types(seeded, {}), "neo4j")
    script = _script(seeded)
    assert _triple("Pedido/1001", "vl_total", f'"4120.50"^^<{XSD}string>') in script


def test_type_does_not_depend_on_the_data(seeded):
    path = seeded.root / "data" / "pedidos.csv"
    _rewrite_csv(seeded, "pedidos.csv", path.read_text(encoding="utf-8").replace(",55010,", ",00123,"))
    script = (publish(seeded, "neo4j"), _script(seeded))[1]
    assert f'"00123"^^<{XSD}string>' in script and f'"55011"^^<{XSD}string>' in script


@pytest.mark.parametrize("old,new,message", [
    ("2026-07-03", "03/07/2026", "pedidos.dt_pedido: 1 valor(es) invalido(s) para date"),
    ("4120.50", "4.120,50", "pedidos.vl_total: 1 valor(es) invalido(s) para float"),
])
def test_invalid_value_is_refused(seeded, monkeypatch, old, new, message):
    path = seeded.root / "data" / "pedidos.csv"
    _rewrite_csv(seeded, "pedidos.csv", path.read_text(encoding="utf-8").replace(old, new, 1).replace('4.120,50', '"4.120,50"'))
    assert any(message in p for p in publish(seeded, "neo4j")["problems"])
    _must_not_load(monkeypatch)
    with pytest.raises(PublishError, match="invalido"):
        publish(seeded, "neo4j", dry_run=False)


@pytest.mark.parametrize("types,fragment", [
    ({"nao_existe": {"a": "string"}}, "nao_existe"),
    ({"pedidos": {"nao_existe": "string"}}, "nao_existe"),
    ({"pedidos": {"status": "booleano"}}, "booleano"),
    ({"pedidos": {"id_cliente": "integer"}}, "id_cliente"),
    ({"itens_pedido": {"sku": "date"}}, "sku"),
])
def test_invalid_type_declaration_is_refused(seeded, types, fragment):
    assert any(fragment in p for p in publish(_set_types(seeded, types), "neo4j")["problems"])


@pytest.mark.parametrize("kind,value,expected", [
    ("string", "00123", f'"00123"^^<{XSD}string>'),
    ("string", True, f'"True"^^<{XSD}string>'),
    ("string", 'a"b\nc', f'"a\\"b\\nc"^^<{XSD}string>'),
    ("integer", "100", f'"100"^^<{XSD}integer>'),
    ("integer", 100, f'"100"^^<{XSD}integer>'),
    ("integer", 100.0, f'"100"^^<{XSD}integer>'),
    ("float", "4120.50", f'"4120.50"^^<{XSD}decimal>'),
    ("float", Decimal("4120.50"), f'"4120.50"^^<{XSD}decimal>'),
    ("float", 7, f'"7"^^<{XSD}decimal>'),
    ("float", 0.00001, f'"0.00001"^^<{XSD}decimal>'),
    ("date", "2026-07-03", f'"2026-07-03"^^<{XSD}date>'),
    ("date", date(2026, 7, 3), f'"2026-07-03"^^<{XSD}date>'),
    ("date", datetime(2026, 7, 3), f'"2026-07-03"^^<{XSD}date>'),
])
def test_rdf_literal_accepts(kind, value, expected):
    assert exporter.rdf_literal(kind, value) == expected


@pytest.mark.parametrize("kind,value", [
    ("integer", "007"), ("integer", "1.5"), ("integer", str(2**63)), ("integer", True), ("integer", "abc"),
    ("float", "nan"), ("float", "inf"), ("float", "4.120,50"), ("float", True),
    ("date", "03/07/2026"), ("date", datetime(2026, 7, 3, 12, 30)), ("date", "abc"),
])
def test_rdf_literal_refuses_what_would_lose_information(kind, value):
    with pytest.raises(ValueError):
        exporter.rdf_literal(kind, value)


def test_key_values_are_encoded_in_the_iri():
    assert exporter.iri("https://x#", "Item", ["a b", "c/d"]) == "<https://x#Item/a%20b/c%2Fd>"


def test_metric_rule_is_documented_not_translated(seeded):
    profile(seeded)
    publish(seeded, "neo4j")
    script = _script(seeded)
    assert "# metrica faturamento" in script
    assert "SUM(CASE WHEN status = 'FATURADO' THEN vl_total END)" in script
    assert "nao somar depois de juntar com: itens_pedido" in script


def test_duplicate_key_is_refused_instead_of_merging_rows(seeded):
    _rewrite_csv(seeded, "clientes.csv", "id_cliente,nm_cliente,cnpj,uf,dt_cadastro,fl_ativo\n"
                                         "1,A,1,SP,2023-01-15,S\n1,B,2,MG,2023-01-15,S\n")
    assert any("clientes.id_cliente" in p for p in publish(seeded, "neo4j")["problems"])
    with pytest.raises(PublishError, match="id_cliente"):
        publish(seeded, "neo4j", dry_run=False)


def test_no_dry_run_requires_connection_settings(seeded, monkeypatch):
    profile(seeded)
    for var in ("AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(exporter, "require", lambda *a: None)
    with pytest.raises(RuntimeError, match="AKME_NEO4J_URI"):
        publish(seeded, "neo4j", dry_run=False)


def test_no_dry_run_without_driver_explains_the_extra(seeded, monkeypatch):
    profile(seeded)
    def missing(*a):
        raise AdapterError("uv sync --extra neo4j")
    monkeypatch.setattr(exporter, "require", missing)
    with pytest.raises(AdapterError, match="--extra neo4j"):
        publish(seeded, "neo4j", dry_run=False)


EXPECTED_NODES = {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
EXPECTED_EDGES = {"contem": 17, "pertenceA": 10, "referencia": 17}


def _fake_load(monkeypatch, nodes=None, edges=None):
    monkeypatch.setattr(exporter, "_run", lambda project, batches: len(batches))
    monkeypatch.setattr(exporter, "_observed", lambda labels, types: (nodes or EXPECTED_NODES, edges or EXPECTED_EDGES))


def test_load_reports_verification_when_database_matches(seeded, monkeypatch):
    profile(seeded)
    _fake_load(monkeypatch)
    r = publish(seeded, "neo4j", dry_run=False)
    assert r["executed"] == r["batches"]
    assert r["verification"] == {"ok": True, "divergences": []}


def test_load_fails_when_edges_were_not_created(seeded, monkeypatch):
    profile(seeded)
    _fake_load(monkeypatch, edges={"contem": 0, "pertenceA": 10, "referencia": 17})
    with pytest.raises(PublishError, match="contem: esperado 17, encontrado 0"):
        publish(seeded, "neo4j", dry_run=False)


def test_load_fails_when_database_has_extra_nodes(seeded, monkeypatch):
    profile(seeded)
    _fake_load(monkeypatch, nodes={**EXPECTED_NODES, "Cliente": 9})
    with pytest.raises(PublishError, match="Cliente: esperado 8, encontrado 9"):
        publish(seeded, "neo4j", dry_run=False)


def test_dry_run_does_not_touch_the_database(seeded, monkeypatch):
    profile(seeded)
    def must_not_run(*args):
        raise AssertionError("dry-run nao pode acessar o banco")
    monkeypatch.setattr(exporter, "_run", must_not_run)
    monkeypatch.setattr(exporter, "_observed", must_not_run)
    assert "verification" not in publish(seeded, "neo4j")


def _cli(seeded, monkeypatch, answer):
    from typer.testing import CliRunner
    from akme.cli import app
    profile(seeded)
    monkeypatch.chdir(seeded.root)
    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://usuario:segredo-na-uri@host-teste:7687")
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", "senha-que-nao-pode-aparecer")
    if not getattr(exporter.destination_state, "_fake", False):
        _fake_state(monkeypatch)
    return CliRunner().invoke(app, ["publish", "--target", "neo4j", "--no-dry-run"], input=answer)


def _fake_state(monkeypatch, projetos=(), total=0, alheios=0):
    def state(project):
        return {"projetos": list(projetos), "total": total, "alheios": alheios}
    state._fake = True
    monkeypatch.setattr(exporter, "destination_state", state)


def test_cli_shows_destination_and_summary_before_confirming(seeded, monkeypatch):
    def must_not_run(*args):
        raise AssertionError("recusar a confirmacao nao pode gravar")
    monkeypatch.setattr(exporter, "_run", must_not_run)
    result = _cli(seeded, monkeypatch, "n\n")
    before_prompt = result.output.split("Executar no alvo")[0]
    assert "bolt://host-teste:7687" in before_prompt
    assert "Cliente: 8" in before_prompt and "pertenceA: 10" in before_prompt
    assert "avisos: nenhum" in before_prompt
    assert "banco: vazio" in before_prompt
    assert result.exit_code != 0
    assert "erro:" not in result.output


def test_cli_never_prints_credentials(seeded, monkeypatch):
    result = _cli(seeded, monkeypatch, "n\n")
    assert "senha-que-nao-pode-aparecer" not in result.output
    assert "segredo-na-uri" not in result.output


def test_cli_refuses_before_confirming_when_there_are_problems(seeded, monkeypatch):
    _rewrite_csv(seeded, "produtos.csv", "sku,ds_produto,categoria,vl_unitario,un_medida\n"
                                         "CIM-50,Cimento,cimento,32.90,SC\n,Sem sku,outros,1.00,UN\n")
    result = _cli(seeded, monkeypatch, "n\n")
    assert "produtos: 1 linha(s) com chave sku vazia" in result.output
    assert "Executar no alvo" not in result.output
    assert result.exit_code == 1
    assert "erro:" not in result.output


def test_cli_exits_with_error_on_divergence(seeded, monkeypatch):
    _fake_load(monkeypatch, edges={"contem": 0, "pertenceA": 10, "referencia": 17})
    result = _cli(seeded, monkeypatch, "y\n")
    assert result.exit_code == 1
    assert "contem: esperado 17, encontrado 0" in result.output


def _must_not_load(monkeypatch):
    def must_not_run(*args):
        raise AssertionError("carga recusada nao pode acessar o banco")
    monkeypatch.setattr(exporter, "_run", must_not_run)
    monkeypatch.setattr(exporter, "_observed", must_not_run)


def _add_mapping(monkeypatch, mapping):
    real = exporter.build_export
    def patched(project):
        data = real(project)
        data["mappings"] = [*data["mappings"], mapping]
        return data
    monkeypatch.setattr(exporter, "build_export", patched)


def test_demo_has_no_problems(seeded):
    profile(seeded)
    assert publish(seeded, "neo4j")["problems"] == []


def test_source_without_class_is_refused(seeded, monkeypatch):
    profile(seeded)
    (seeded.root / "data" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    assert any("extra" in p and "sem classe" in p for p in publish(seeded, "neo4j")["problems"])
    _must_not_load(monkeypatch)
    with pytest.raises(PublishError, match="extra"):
        publish(seeded, "neo4j", dry_run=False)


def test_source_can_be_excluded_explicitly(seeded):
    profile(seeded)
    (seeded.root / "data" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    project = _edit_sources(seeded, lambda entries: entries.update(extra={"source": "extra", "exclude": "fora do escopo"}))
    r = publish(project, "neo4j")
    assert r["problems"] == [] and r["sources_skipped"] == ["extra"]
    assert any("fonte excluida na etapa 5: extra" in line for line in exporter.preview_lines(r))
    assert r["nodes"] == EXPECTED_NODES


def test_excluding_unknown_source_is_a_problem(seeded):
    profile(seeded)
    project = _edit_sources(seeded, lambda entries: entries.update(nao_existe={"source": "nao_existe", "exclude": "x"}))
    assert any("nao_existe" in p for p in publish(project, "neo4j")["problems"])


def test_source_with_two_classes_is_refused(seeded, monkeypatch):
    profile(seeded)
    _add_mapping(monkeypatch, {"term": "uf", "source": "pedidos", "column": "status", "role": "dimension"})
    assert any("pedidos" in p and "Cliente" in p and "Pedido" in p for p in publish(seeded, "neo4j")["problems"])
    _must_not_load(monkeypatch)
    with pytest.raises(PublishError, match="pedidos"):
        publish(seeded, "neo4j", dry_run=False)


def test_two_sources_with_same_class_are_refused(seeded, monkeypatch):
    profile(seeded)
    (seeded.root / "data" / "clientes2.csv").write_text("id_cliente,uf\n99,SP\n", encoding="utf-8")
    _add_mapping(monkeypatch, {"term": "uf", "source": "clientes2", "column": "uf", "role": "dimension"})
    assert any("Cliente" in p and "clientes" in p and "clientes2" in p for p in publish(seeded, "neo4j")["problems"])
    _must_not_load(monkeypatch)
    with pytest.raises(PublishError, match="clientes2"):
        publish(seeded, "neo4j", dry_run=False)


def test_truncated_source_is_refused(seeded, monkeypatch):
    profile(seeded)
    monkeypatch.setattr(exporter, "MAX_ROWS", 3)
    _must_not_load(monkeypatch)
    with pytest.raises(PublishError, match="truncada"):
        publish(seeded, "neo4j", dry_run=False)


def test_empty_key_is_refused(seeded, monkeypatch):
    _rewrite_csv(seeded, "produtos.csv", "sku,ds_produto,categoria,vl_unitario,un_medida\n"
                                         "CIM-50,Cimento,cimento,32.90,SC\n,Sem sku,outros,1.00,UN\n")
    _must_not_load(monkeypatch)
    with pytest.raises(PublishError, match="chave sku vazia"):
        publish(seeded, "neo4j", dry_run=False)


def test_all_problems_are_listed_together(seeded):
    (seeded.root / "data" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    _rewrite_csv(seeded, "produtos.csv", "sku,ds_produto,categoria,vl_unitario,un_medida\n,Sem sku,outros,1.00,UN\n")
    problems = publish(seeded, "neo4j")["problems"]
    assert any("extra" in p for p in problems) and any("chave sku vazia" in p for p in problems)


def test_orphan_foreign_key_is_a_warning(seeded):
    path = seeded.root / "data" / "pedidos.csv"
    _rewrite_csv(seeded, "pedidos.csv", path.read_text(encoding="utf-8").replace("\n1001,1,", "\n1001,999,", 1))
    r = publish(seeded, "neo4j")
    assert r["relationships"]["pertenceA"] == 9
    assert r["problems"] == []
    assert any("pertenceA: 1 de 10" in w for w in r["warnings"])
    assert any("pertenceA: 1 de 10" in line for line in exporter.preview_lines(r))


def test_relation_without_any_match_is_refused(seeded):
    path = seeded.root / "data" / "clientes.csv"
    text = path.read_text(encoding="utf-8").splitlines()
    _rewrite_csv(seeded, "clientes.csv", "\n".join([text[0]] + [f"x{line}" for line in text[1:]]) + "\n")
    assert any("pertenceA" in p and "nenhuma" in p for p in publish(seeded, "neo4j")["problems"])


def test_join_column_missing_in_data_is_refused(seeded):
    path = seeded.root / "data" / "pedidos.csv"
    _rewrite_csv(seeded, "pedidos.csv", path.read_text(encoding="utf-8").replace("id_cliente", "cliente", 1))
    assert any("pertenceA" in p and "id_cliente" in p for p in publish(seeded, "neo4j")["problems"])


def test_metric_column_without_type_is_a_warning(seeded):
    r = publish(_set_types(seeded, {}), "neo4j")
    assert any("pedidos.vl_total" in w and "nao soma" in w for w in r["warnings"])


def test_demo_has_no_warnings(seeded):
    assert publish(seeded, "neo4j")["warnings"] == []


def test_script_with_problems_says_so(seeded):
    (seeded.root / "data" / "extra.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    publish(seeded, "neo4j")
    assert _script(seeded).startswith("# NAO EXECUTE")


def test_release_only_bumps_after_success(seeded, monkeypatch):
    import akme.tools.publish as publish_tool
    profile(seeded)
    bumped = []
    monkeypatch.setattr(publish_tool, "bump_version", lambda project, part: bumped.append(part))
    _fake_load(monkeypatch, edges={"contem": 0, "pertenceA": 10, "referencia": 17})
    with pytest.raises(PublishError):
        publish(seeded, "neo4j", dry_run=False, release="patch")
    assert bumped == []
    _fake_load(monkeypatch)
    publish(seeded, "neo4j", dry_run=False, release="patch")
    assert bumped == ["patch"]


class _FakeSession:
    """Simula o servidor com n10s: responde as consultas de preparo e registra as importacoes."""
    def __init__(self, fail_import=None, procedures=True, vocab=None, status="OK", lose=0, projetos=(), total=0, alheios=0):
        self.state = {"projetos": list(projetos), "total": total, "alheios": alheios}
        self.imports, self.fail_import, self.procedures, self.vocab, self.status, self.lose = 0, fail_import, procedures, vocab, status, lose
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def run(self, statement, **params):
        import neo4j
        self.calls.append(statement)
        if "_AkmeProjeto" in statement and "COLLECT" in statement:
            return _Result([dict(self.state)])
        if "MERGE (m:_AkmeProjeto" in statement:
            self.marked = params["projeto"]
            return _Result([])
        if "SHOW PROCEDURES" in statement:
            return _Result([{"c": 2 if self.procedures else 0}])
        if "graphconfig.show" in statement:
            return _Result([{"param": "handleVocabUris", "value": self.vocab}] if self.vocab else [])
        if "graphconfig.init" in statement:
            self.vocab = params["vocab"]
        if "onto.import.inline" in statement:
            return _Result([{"terminationStatus": "OK", "extraInfo": ""}])
        if "rdf.import.inline" in statement:
            self.imports += 1
            if self.imports == self.fail_import:
                raise neo4j.exceptions.ClientError("regra violada")
            n = params["rdf"].count("\n")
            return _Result([{"terminationStatus": self.status, "triplesParsed": n, "triplesLoaded": n - self.lose, "extraInfo": "detalhe"}])
        return _Result([])


class _Result:
    def __init__(self, rows):
        self.rows = rows
    def data(self):
        return self.rows
    def consume(self):
        return None
    def __iter__(self):
        return iter(self.rows)


def _fake_driver(monkeypatch, session=None, error=None):
    neo4j = pytest.importorskip("neo4j")
    class Driver:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def session(self, **kwargs):
            if error:
                raise error
            return session
    monkeypatch.setenv("AKME_NEO4J_URI", "bolt://host:7687")
    monkeypatch.setenv("AKME_NEO4J_USER", "x")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", "senha-que-nao-pode-aparecer")
    monkeypatch.setattr(neo4j.GraphDatabase, "driver", lambda *a, **k: Driver())


def _batches(n=3):
    return [f"<urn:a{i}> <urn:p> <urn:b> .\n" for i in range(n)]


def test_load_prepares_n10s_and_imports_ontology_then_data(seeded, monkeypatch):
    session = _FakeSession()
    _fake_driver(monkeypatch, session=session)
    assert exporter._run(seeded, _batches(2)) == 2
    joined = "\n".join(session.calls)
    assert "n10s_unique_uri" in joined and "onto.import.inline" in joined
    assert session.marked == seeded.config["project"]
    assert next(i for i, c in enumerate(session.calls) if "COLLECT" in c) < next(i for i, c in enumerate(session.calls) if c.startswith("CREATE"))
    order = [c.split("(")[0] for c in session.calls if c.startswith("CALL n10s.")]
    assert order == ["CALL n10s.graphconfig.show", "CALL n10s.graphconfig.init", "CALL n10s.onto.import.inline",
                     "CALL n10s.rdf.import.inline", "CALL n10s.rdf.import.inline"]
    assert all("<urn:" not in c for c in session.calls), "os dados vao como parametro, nao no texto da consulta"


def test_load_refuses_server_without_n10s(seeded, monkeypatch):
    session = _FakeSession(procedures=False)
    _fake_driver(monkeypatch, session=session)
    with pytest.raises(PublishError, match="n10s"):
        exporter._run(seeded, _batches())
    assert session.imports == 0


def test_load_accepts_graph_already_configured_by_akme(seeded, monkeypatch):
    session = _FakeSession(vocab="IGNORE")
    _fake_driver(monkeypatch, session=session)
    assert exporter._run(seeded, _batches(1)) == 1
    assert not any("graphconfig.init" in c for c in session.calls)


def test_load_refuses_graph_configured_with_other_names(seeded, monkeypatch):
    session = _FakeSession(vocab="SHORTEN")
    _fake_driver(monkeypatch, session=session)
    with pytest.raises(PublishError, match="handleVocabUris"):
        exporter._run(seeded, _batches())
    assert session.imports == 0


@pytest.mark.parametrize("kwargs,message", [({"status": "KO"}, "KO"), ({"lose": 1}, "carregou 0 de 1")])
def test_import_that_does_not_load_everything_is_an_error(seeded, monkeypatch, kwargs, message):
    _fake_driver(monkeypatch, session=_FakeSession(**kwargs))
    with pytest.raises(PublishError, match=message):
        exporter._run(seeded, _batches(1))


def test_partial_load_failure_says_what_was_written(seeded, monkeypatch):
    _fake_driver(monkeypatch, session=_FakeSession(fail_import=2))
    with pytest.raises(PublishError, match="lote 2 de 3.*1 lote") as exc:
        exporter._run(seeded, _batches(3))
    assert "senha-que-nao-pode-aparecer" not in str(exc.value)


def test_failure_on_first_batch_says_nothing_was_written(seeded, monkeypatch):
    _fake_driver(monkeypatch, session=_FakeSession(fail_import=1))
    with pytest.raises(PublishError, match="nenhum lote de dados"):
        exporter._run(seeded, _batches(2))


def test_connection_failure_becomes_a_clear_error(seeded, monkeypatch):
    neo4j = pytest.importorskip("neo4j")
    _fake_driver(monkeypatch, error=neo4j.exceptions.ServiceUnavailable("sem servico"))
    with pytest.raises(PublishError, match="sem servico"):
        exporter._run(seeded, _batches(1))


def test_large_data_is_split_in_batches(seeded, monkeypatch):
    profile(seeded)
    monkeypatch.setattr(exporter, "BATCH", 10)
    r = publish(seeded, "neo4j")
    assert r["batches"] == -(-r["triples"] // 10)


@pytest.mark.parametrize("state,expected", [
    ({"projetos": [], "total": 0, "alheios": 0}, None),
    ({"projetos": ["demo"], "total": 58, "alheios": 0}, None),
    ({"projetos": ["outro"], "total": 58, "alheios": 0}, "projeto outro"),
    ({"projetos": ["demo", "outro"], "total": 90, "alheios": 0}, "mais de um projeto"),
    ({"projetos": [], "total": 43, "alheios": 0}, "sem a marca"),
    ({"projetos": ["demo"], "total": 60, "alheios": 2}, "2 no"),
])
def test_destination_is_refused_unless_empty_or_same_project(state, expected):
    description, refusal = exporter.check_destination(state, "demo")
    assert (refusal is None) if expected is None else (expected in refusal)
    assert description


def test_cli_refuses_other_project_without_asking(seeded, monkeypatch):
    _must_not_load(monkeypatch)
    _fake_state(monkeypatch, projetos=["outro"], total=58)
    result = _cli(seeded, monkeypatch, "y\n")
    assert result.exit_code == 1
    assert "Executar no alvo" not in result.output and "projeto outro" in result.output


def test_load_rechecks_destination_before_writing(seeded, monkeypatch):
    session = _FakeSession(projetos=["outro"], total=58)
    _fake_driver(monkeypatch, session=session)
    with pytest.raises(PublishError, match="projeto outro.*Nada foi gravado"):
        exporter._run(seeded, _batches(1))
    assert not any(c.startswith(("CREATE", "MERGE", "CALL n10s")) for c in session.calls)


@pytest.mark.parametrize("uri,browser", [
    ("bolt://127.0.0.1:7687", "http://localhost:7474"),
    ("neo4j://localhost:7687", "http://localhost:7474"),
    ("neo4j+s://abc123.databases.neo4j.io", "https://console.neo4j.io"),
    ("bolt://grafo.cliente.com:7687", "http://grafo.cliente.com:7474"),
])
def test_viewing_lines_point_to_the_browser(seeded, monkeypatch, uri, browser):
    monkeypatch.setenv("AKME_NEO4J_URI", uri)
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", "senha-que-nao-pode-aparecer")
    text = "\n".join(exporter.viewing_lines(seeded, publish(seeded, "neo4j")))
    assert browser in text and "neo4j" in text and "senha-que-nao-pode-aparecer" not in text
    assert "MATCH p = (:Pedido)-[:pertenceA]->(:Cliente) RETURN p LIMIT 50" in text
    assert ":SCO" in text and "NOT n:Class" in text


def test_cli_tells_where_to_see_the_graph_after_loading(seeded, monkeypatch):
    _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n")
    assert result.exit_code == 0, result.output
    after = result.output.split('"verification"')[1]
    assert "Para ver o grafo" in after and "MATCH p = " in after
