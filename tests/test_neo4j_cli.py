"""CLI e tool de publicacao do neo4j: destino e resumo antes de confirmar, recusas, divergencia e onde ver o grafo."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from akme.adapters.base import AdapterError
from akme.cli import app
from akme.tools import neo4j_load
from akme.tools.neo4j_plan import build_plan
from akme.tools.profile import profile
from akme.tools.publish import PublishError, publish
from neo4j_fakes import CARGA, PASSWORD, _FakeSession

ROOT = Path(__file__).resolve().parent.parent
SECRET_URI = "bolt://usuario:segredo-na-uri@host-teste:7687"


def _rewrite_csv(project, name, text):
    (project.root / "data" / name).write_text(text, encoding="utf-8")


def _fake_state(monkeypatch, projetos=(), total=0, alheios=0, legado=False, no_banco=None):
    def state(project, plan):
        return {"projetos": list(projetos), "total": total, "alheios": alheios, "legado": legado,
                "no_banco": {label: 0 for label in plan.nodes} | (no_banco or {})}
    monkeypatch.setattr(neo4j_load, "destination_state", state)


def _fake_load(monkeypatch, ok=True):
    """Troca a gravacao e a conferencia; registra as cargas feitas."""
    calls = []

    def load(project, plan, carga):
        calls.append(carga)
        return {"executed": 7, "removed": {"nodes": 0, "relationships": 0}}

    def verify(plan, project_name, concepts, terms=None):
        return {"ok": ok, "divergences": [] if ok else ["contem: esperado 17, encontrado 0"]}

    monkeypatch.setattr(neo4j_load, "load", load)
    monkeypatch.setattr(neo4j_load, "verify", verify)
    monkeypatch.setattr(neo4j_load, "has_apoc", lambda: False)
    return calls


def _must_not_load(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("carga recusada nao pode gravar")
    monkeypatch.setattr(neo4j_load, "load", must_not_run)


def _cli(seeded, monkeypatch, answer, state=True, no_banco=None):
    profile(seeded)
    monkeypatch.chdir(seeded.root)
    monkeypatch.setenv("AKME_NEO4J_URI", SECRET_URI)
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    if state:
        _fake_state(monkeypatch, projetos=["demo"] if no_banco else (), total=sum((no_banco or {}).values()),
                    no_banco=no_banco)
    return CliRunner().invoke(app, ["publish", "--target", "neo4j", "--no-dry-run"], input=answer)


def test_no_dry_run_requires_connection_settings(seeded, monkeypatch):
    profile(seeded)
    for var in ("AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(neo4j_load, "require", lambda *a: None)
    with pytest.raises(RuntimeError, match="AKME_NEO4J_URI"):
        publish(seeded, "neo4j", dry_run=False)


def test_no_dry_run_without_driver_explains_the_extra(seeded, monkeypatch):
    profile(seeded)

    def missing(*a):
        raise AdapterError("uv sync --extra neo4j")

    monkeypatch.setattr(neo4j_load, "require", missing)
    with pytest.raises(AdapterError, match="--extra neo4j"):
        publish(seeded, "neo4j", dry_run=False)


def test_cli_shows_destination_and_summary_before_confirming(seeded, monkeypatch):
    _must_not_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "n\n")
    before_prompt = result.output.split("Executar no alvo")[0]
    assert "bolt://host-teste:7687" in before_prompt
    assert "Cliente: 8" in before_prompt and "  pertenceA: 10" in before_prompt
    assert "Cliente: banco 0 -> origem 8" in before_prompt
    assert "avisos:" in before_prompt and "a carga apaga deste projeto" in before_prompt
    assert "banco: vazio" in before_prompt
    assert result.exit_code != 0
    assert "erro:" not in result.output


def test_cli_never_prints_credentials(seeded, monkeypatch):
    _must_not_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "n\n")
    assert PASSWORD not in result.output
    assert "segredo-na-uri" not in result.output


def test_cli_refuses_before_confirming_when_there_are_problems(seeded, monkeypatch):
    _rewrite_csv(seeded, "produtos.csv", "sku,ds_produto,categoria,vl_unitario,un_medida\n"
                                         "CIM-50,Cimento,cimento,32.90,SC\n,Sem sku,outros,1.00,UN\n")
    result = _cli(seeded, monkeypatch, "n\n", state=False)  # nem consulta o banco: nao ha _fake_state
    assert "produtos: 1 linha(s) com chave sku vazia" in result.output
    assert "Executar no alvo" not in result.output
    assert result.exit_code == 1
    assert "erro:" not in result.output


def test_cli_exits_with_error_on_divergence(seeded, monkeypatch):
    _fake_load(monkeypatch, ok=False)
    result = _cli(seeded, monkeypatch, "y\n")
    assert result.exit_code == 1
    assert "contem: esperado 17, encontrado 0" in result.output


def test_cli_refuses_other_project_without_asking(seeded, monkeypatch):
    _must_not_load(monkeypatch)
    profile(seeded)
    monkeypatch.chdir(seeded.root)
    monkeypatch.setenv("AKME_NEO4J_URI", SECRET_URI)
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    _fake_state(monkeypatch, projetos=["outro"], total=58)
    result = CliRunner().invoke(app, ["publish", "--target", "neo4j", "--no-dry-run"], input="y\n")
    assert result.exit_code == 1
    assert "Executar no alvo" not in result.output and "projeto outro" in result.output


@pytest.mark.parametrize("kwargs,fragment", [
    ({"total": 43}, "sem a marca"),
    ({"legado": True, "total": 5}, "exportacao antiga (n10s)"),
])
def test_cli_refuses_alien_and_legacy_destinations_without_asking(seeded, monkeypatch, kwargs, fragment):
    _must_not_load(monkeypatch)
    _fake_state(monkeypatch, **kwargs)
    result = _cli(seeded, monkeypatch, "y\n", state=False)
    assert result.exit_code == 1 and "Executar no alvo" not in result.output
    assert fragment in result.output


def test_load_rechecks_destination_before_writing(seeded, fake):
    session = fake["use"](_FakeSession(state={"projetos": ["outro"], "total": 58}))
    with pytest.raises(PublishError, match="projeto outro.*Nada foi gravado"):
        neo4j_load.load(seeded, build_plan(seeded), CARGA)
    assert not any(q.startswith(("CREATE", "MERGE", "UNWIND")) for q in session.queries())


@pytest.mark.parametrize("uri,browser", [
    ("bolt://127.0.0.1:7687", "http://localhost:7474"),
    ("neo4j://localhost:7687", "http://localhost:7474"),
    ("neo4j+s://abc123.databases.neo4j.io", "https://console.neo4j.io"),
    ("bolt://grafo.cliente.com:7687", "http://grafo.cliente.com:7474"),
])
def test_viewing_lines_point_to_the_browser(seeded, monkeypatch, uri, browser):
    monkeypatch.delenv("AKME_NEO4J_BROWSER_URL", raising=False)
    monkeypatch.setenv("AKME_NEO4J_URI", uri)
    monkeypatch.setenv("AKME_NEO4J_USER", "neo4j")
    monkeypatch.setenv("AKME_NEO4J_PASSWORD", PASSWORD)
    text = "\n".join(neo4j_load.viewing_lines(seeded, publish(seeded, "neo4j")))
    assert browser in text and "neo4j" in text and PASSWORD not in text
    assert "MATCH p = (:Pedido)-[:pertenceA]->(:Cliente) RETURN p LIMIT 50" in text
    assert "MATCH p = (:Conceito)-[:RELACAO_ONTOLOGIA]->(:Conceito) RETURN p" in text


def test_cli_tells_where_to_see_the_graph_after_loading(seeded, monkeypatch):
    calls = _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n")
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    after = result.output.split('"verification"')[1]
    assert "Para ver o grafo" in after and "MATCH p = " in after
    assert PASSWORD not in result.output


def test_release_bumps_only_after_a_real_load_succeeds(seeded, monkeypatch):
    import akme.tools.publish as publish_tool
    profile(seeded)
    bumped = []
    monkeypatch.setattr(publish_tool, "bump_version", lambda project, part: bumped.append(part))
    publish(seeded, "neo4j", dry_run=True, release="patch")
    assert bumped == [], "dry-run nao muda a versao"
    _fake_load(monkeypatch, ok=False)
    with pytest.raises(PublishError):
        publish(seeded, "neo4j", dry_run=False, release="patch")
    assert bumped == []
    _fake_load(monkeypatch)
    publish(seeded, "neo4j", dry_run=False, release="patch")
    assert bumped == ["patch"]


def test_package_has_no_n10s():
    assert not list((ROOT / "akme").rglob("n10s.py"))
    # o texto "n10s" fica so na deteccao do banco legado; nenhum modulo importa o antigo
    imports = [line for p in (ROOT / "akme").rglob("*.py") for line in p.read_text(encoding="utf-8").splitlines()
               if re.match(r"\s*(import|from)\s", line) and "n10s" in line]
    assert imports == []


def test_cli_builds_the_plan_once(seeded, monkeypatch):
    from akme.tools import neo4j_plan
    import akme.cli as cli_module

    calls = []
    real = neo4j_plan.build_plan

    def spy(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(neo4j_plan, "build_plan", spy)
    monkeypatch.setattr(neo4j_load, "build_plan", spy)
    monkeypatch.setattr(cli_module.neo4j_plan_tool, "build_plan", spy)
    _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n")
    assert result.exit_code == 0, result.output
    assert len(calls) == 1


# --- revisao final ---

def test_large_removal_needs_the_number_typed(seeded, monkeypatch):
    calls = _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n12\n", no_banco={"Cliente": 20})
    assert result.exit_code == 0, result.output
    assert "Cliente: banco 20 -> origem 8, pelo menos 12 serao removidos" in result.output
    assert "digite 12" in result.output and len(calls) == 1


def test_large_removal_with_wrong_number_writes_nothing(seeded, monkeypatch):
    calls = _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n5\n", no_banco={"Cliente": 20})
    assert result.exit_code == 1 and calls == []
    assert "nada foi gravado" in result.output


def test_small_removal_asks_only_once(seeded, monkeypatch):
    calls = _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n", no_banco={"Cliente": 9})
    assert result.exit_code == 0, result.output
    assert "digite" not in result.output and len(calls) == 1


def test_label_only_in_the_database_counts_as_large_removal(seeded, monkeypatch):
    calls = _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n\n", no_banco={"Cliente": 8, "Antiga": 2})
    assert result.exit_code == 1 and calls == [] and "digite 2" in result.output


def test_unexpected_error_in_the_plan_is_a_short_message(seeded, monkeypatch):
    import akme.cli as cli_module

    _must_not_load(monkeypatch)
    real = cli_module.neo4j_plan_tool.build_plan

    def latin1_then_plan(project, *args):  # o CSV muda depois do profile do _cli: o plano le Latin-1 como UTF-8
        (seeded.root / "data" / "clientes.csv").write_bytes("id_cliente,nm_cliente\n1,Jo\xe3o\n".encode("latin-1"))
        return real(project, *args)

    monkeypatch.setattr(cli_module.neo4j_plan_tool, "build_plan", latin1_then_plan)
    result = _cli(seeded, monkeypatch, "y\n", state=False)
    assert result.exit_code == 1
    assert "erro: UnicodeDecodeError" in result.output
    assert "Traceback" not in result.output and isinstance(result.exception, SystemExit)


def test_unexpected_driver_error_never_shows_credentials(seeded, monkeypatch):
    _must_not_load(monkeypatch)

    def broken(project, plan):
        raise OSError(f"falha ao falar com {SECRET_URI} usando {PASSWORD}")

    profile(seeded)
    monkeypatch.setattr(neo4j_load, "destination_state", broken)
    result = _cli(seeded, monkeypatch, "y\n", state=False)
    assert result.exit_code == 1 and "erro: OSError" in result.output
    assert PASSWORD not in result.output and "segredo-na-uri" not in result.output


def test_second_confirmation_at_end_of_input_writes_nothing(seeded, monkeypatch):
    calls = _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n", no_banco={"Cliente": 20})  # stdin acaba antes do numero
    assert result.exit_code != 0 and calls == []


# --- Task 11: tutorial do projeto no Browser ---

def test_cli_after_loading_tells_how_to_open_the_guide(seeded, monkeypatch):
    _fake_load(monkeypatch)
    result = _cli(seeded, monkeypatch, "y\n")
    assert result.exit_code == 0, result.output
    after = result.output.split('"verification"')[1]
    assert ":guide http://127.0.0.1:8765/neo4j/guia" in after
    assert "NEO4J_browser_post__connect__cmd='guide http://127.0.0.1:8765/neo4j/guia'" in after
    assert "com consulta" not in after and "RETURN p.esquema" not in after, "nada de CQ nem de esquema para o humano"


def test_cli_dry_run_writes_the_guide_and_tells_how_to_open_it(seeded, monkeypatch):
    from typer.testing import CliRunner

    from akme.cli import app

    monkeypatch.chdir(seeded.root)
    result = CliRunner().invoke(app, ["publish", "--target", "neo4j"])
    assert result.exit_code == 0, result.output
    assert (seeded.docs_dir / "publish" / "neo4j_guia.html").is_file()
    assert ":guide http://127.0.0.1:8765/neo4j/guia" in result.output and "akme review" in result.output
    assert "com consulta" not in result.output
