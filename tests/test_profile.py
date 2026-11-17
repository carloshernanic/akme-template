from akme.tools import profile as profile_mod
from akme.tools.profile import load_profile, profile


def test_profile_types_keys_and_conventions(project):
    result = profile(project)
    by_name = {s.name: s for s in result.sources}
    pedidos = {c.name: c for c in by_name["pedidos"].columns}
    assert pedidos["id_pedido"].type == "integer" and pedidos["id_pedido"].candidate_key
    assert pedidos["dt_pedido"].type == "date"
    assert pedidos["vl_total"].type == "number"
    assert pedidos["nf"].nulls == 3
    assert pedidos["status"].cardinality == "low"
    assert "identifier" in pedidos["id_cliente"].conventions
    assert "monetary" in pedidos["vl_total"].conventions
    assert by_name["clientes"].candidate_keys == ["id_cliente", "nm_cliente", "cnpj"]
    assert result.conventions["naming_style"] == "snake_case"
    assert {"UF", "SKU", "NF", "CNPJ"} <= set(result.conventions["acronyms_found"])
    assert project.profile_path.exists()
    assert load_profile(project).adapter == "local_folder"


def test_profile_skips_list_sources_when_sources_selected(project, monkeypatch):
    real = profile_mod.load_adapter(project.adapter_name, project.adapter_options())

    def fail_list_sources():
        raise AssertionError("list_sources nao deve ser chamado quando houver selecao explicita")

    monkeypatch.setattr(real, "list_sources", fail_list_sources)
    monkeypatch.setattr(profile_mod, "load_adapter", lambda *a, **kw: real)

    result = profile(project, sources=["pedidos", "pedidos"])
    assert [s.name for s in result.sources] == ["pedidos"]

    project.config["profile_sources"] = ["clientes"]
    result_cfg = profile(project)
    assert [s.name for s in result_cfg.sources] == ["clientes"]
