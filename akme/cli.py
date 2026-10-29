from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console
from rich.table import Table

from .project import CONFIG_FILE, Project, read_yaml, write_yaml
from .tools import connect as connect_tool
from .tools import eval as eval_tool
from .tools import export as export_tool
from .tools import ontology_write as write_tool
from .tools import profile as profile_tool
from .tools import publish as publish_tool
from .tools import validate as validate_tool

app = typer.Typer(help="AKME: ontologia e camada semantica com LOT + NeOn e humano no loop", no_args_is_help=True)
console = Console()

TEMPLATE_FILES = ("schema.ttl", "content.yml", "manifest.yml")


def _project() -> Project:
    p = Project(".")
    if not p.config:
        console.print(f"[yellow]{CONFIG_FILE} nao encontrado; rode 'akme init'. Usando padroes.[/]")
    return p


def _dump(data: Any) -> None:
    console.print_json(json.dumps(data, ensure_ascii=False, default=str))


@app.command()
def init(adapter: str = typer.Option("local_folder", help="local_folder, postgres, snowflake ou databricks"),
         path: str = typer.Option(None, help="pasta dos dados para local_folder (padrao: data, ou examples/local_demo com --demo)"),
         demo: bool = typer.Option(False, help="usa uma copia da ontologia em examples/local_demo/ontology")) -> None:
    """Cria akme.yml e as pastas de trabalho."""
    config: dict[str, Any] = {"project": Path.cwd().name, "adapter": adapter}
    path = path or ("examples/local_demo" if demo else "data")
    options = {
        "local_folder": {"path": path},
        "postgres": {"dsn": "env:AKME_PG_DSN", "schema": "public"},
        "snowflake": {"account": "env:AKME_SNOWFLAKE_ACCOUNT", "user": "env:AKME_SNOWFLAKE_USER",
                      "password": "env:AKME_SNOWFLAKE_PASSWORD", "warehouse": "env:AKME_SNOWFLAKE_WAREHOUSE",
                      "database": "env:AKME_SNOWFLAKE_DATABASE", "schema": "env:AKME_SNOWFLAKE_SCHEMA"},
        "databricks": {"host": "env:AKME_DATABRICKS_HOST", "http_path": "env:AKME_DATABRICKS_HTTP_PATH",
                       "token": "env:AKME_DATABRICKS_TOKEN", "catalog": "env:AKME_DATABRICKS_CATALOG",
                       "schema": "env:AKME_DATABRICKS_SCHEMA"},
    }
    config[adapter] = options[adapter]
    if demo:
        config["project"] = "local_demo"
        config["ontology_dir"] = "examples/local_demo/ontology"
        config["questions"] = "examples/local_demo/questions.yml"
        target = Path("examples/local_demo/ontology")
        target.mkdir(parents=True, exist_ok=True)
        for name in TEMPLATE_FILES:
            if not (target / name).exists():
                shutil.copy(Path("ontology") / name, target / name)
    write_yaml(Path(CONFIG_FILE), config)
    if adapter == "local_folder":
        Path(path).mkdir(parents=True, exist_ok=True)
    Path(config.get("ontology_dir", "ontology"), "pending").mkdir(parents=True, exist_ok=True)
    Path("docs").mkdir(exist_ok=True)
    console.print(f"[green]{CONFIG_FILE} criado[/] com adapter {adapter}")


@app.command()
def connect() -> None:
    """Testa a conexao com o adapter configurado."""
    _dump(connect_tool.connect(_project()))


@app.command()
def profile(sample_size: int = 500) -> None:
    """Perfila as fontes e grava docs/profile.json."""
    result = profile_tool.profile(_project(), sample_size)
    table = Table(title="Profile", show_lines=False)
    for col in ("fonte", "linhas", "colunas", "chaves candidatas"):
        table.add_column(col)
    for s in result.sources:
        table.add_row(s.name, str(s.rows_sampled), str(len(s.columns)), ", ".join(s.candidate_keys) or "-")
    console.print(table)
    console.print("convencoes:", result.conventions)


@app.command()
def validate(oops: bool = typer.Option(False, help="chama o OOPS! remoto alem dos pitfalls nativos")) -> None:
    """Valida a ontologia e grava docs/validation.json."""
    report = validate_tool.validate(_project(), oops)
    table = Table(title="Validate")
    table.add_column("nivel")
    table.add_column("check")
    table.add_column("mensagem")
    for f in report.findings:
        table.add_row(f.level, f.check, f.message)
    for p in report.pitfalls:
        table.add_row(f"pitfall {p['level']}", f"{p['code']} ({p['source']})", f"{p['subject']}: {p['message']}")
    console.print(table)
    cov = report.coverage
    if cov.get("available"):
        console.print(f"cobertura: {cov['mapped']}/{cov['columns']} colunas mapeadas ({cov['ratio']:.0%})")
    console.print("[green]ok[/]" if report.ok else "[red]erros encontrados[/]")
    raise typer.Exit(code=0 if report.ok else 1)


@app.command()
def publish(target: str = typer.Option("yaml", help="yaml, snowflake, databricks ou rdf"),
            dry_run: bool = typer.Option(True, help="--no-dry-run executa no alvo"),
            release: str = typer.Option(None, help="patch, minor, major ou versao explicita")) -> None:
    """Gera (ou executa) a publicacao da camada semantica. Dry-run por padrao."""
    if not dry_run and not typer.confirm(f"Executar no alvo {target}? Esta acao altera a plataforma do cliente."):
        raise typer.Abort()
    _dump(publish_tool.publish(_project(), target, dry_run, release))


@app.command(name="eval")
def eval_cmd(callable: str = typer.Option(None, "--callable", help="modulo:funcao que responde (pergunta, contexto)")) -> None:
    """Roda as perguntas de validation/questions.yml com e sem ontologia."""
    fn = eval_tool.load_callable(callable) if callable else None
    result = eval_tool.evaluate(_project(), fn)
    table = Table(title="Eval")
    cols = ["id", "pergunta", "estrutural"] + (["sem ontologia", "com ontologia"] if fn else [])
    for c in cols:
        table.add_column(c)
    for r in result["rows"]:
        row = [str(r["id"]), str(r["question"]), r["structural"]]
        if fn:
            row += [_mark(r.get("without_correct"), r.get("without_ontology")), _mark(r.get("with_correct"), r.get("with_ontology"))]
        table.add_row(*row)
    console.print(table)
    console.print(result["summary"])


def _mark(correct: bool | None, answer: str | None) -> str:
    prefix = "" if correct is None else ("[green]ok[/] " if correct else "[red]x[/] ")
    return prefix + (answer or "")[:60]


@app.command()
def export() -> None:
    """Gera docs/ontology.json e demais artefatos derivados."""
    _dump(export_tool.export(_project()))


@app.command()
def seed(file: Path, approved_by: str = typer.Option(..., help="quem aprova cada edicao da lista")) -> None:
    """Propoe e aplica uma lista de edicoes de um YAML. Util para demos e migracoes ja revisadas."""
    project = _project()
    edits = read_yaml(file).get("edits") or []
    for e in edits:
        edit = write_tool.propose_edit(project, e["type"], e["payload"], e.get("rationale", ""),
                                       e.get("proposed_by", "seed"), e.get("requirement_id"), e.get("evidence", ""))
        write_tool.apply_edit(project, edit.id, approved_by)
    console.print(f"[green]{len(edits)} edicoes aplicadas[/] aprovadas por {approved_by}")


@app.command()
def pending() -> None:
    """Lista as edicoes aguardando aprovacao."""
    console.print(write_tool.pending_summary(_project()) or "nenhuma edicao pendente")


@app.command()
def apply(edit_id: str, approved_by: str = typer.Option(..., help="nome de quem aprovou")) -> None:
    """Aplica uma edicao pendente apos aprovacao humana."""
    _dump(write_tool.apply_edit(_project(), edit_id, approved_by))


@app.command()
def demo() -> None:
    """Roda a demo local: connect, profile, seed, validate, export."""
    project = _project()
    _dump(connect_tool.connect(project))
    profile_tool.profile(project)
    seed_file = Path("examples/local_demo/seed_edits.yml")
    if seed_file.exists() and not read_yaml(project.content_path).get("terms"):
        for e in read_yaml(seed_file).get("edits") or []:
            edit = write_tool.propose_edit(project, e["type"], e["payload"], e.get("rationale", ""),
                                           e.get("proposed_by", "seed"), e.get("requirement_id"), e.get("evidence", ""))
            write_tool.apply_edit(project, edit.id, "demo")
    report = validate_tool.validate(project)
    console.print(f"validate: {'ok' if report.ok else 'erros'}, {len(report.pitfalls)} pitfalls, cobertura {report.coverage.get('ratio')}")
    _dump(export_tool.export(project))
    console.print("abra docs/index.html para ver o grafo")


@app.command()
def serve() -> None:
    """Sobe o servidor MCP (stdio)."""
    from .server import main
    main()


if __name__ == "__main__":
    app()
