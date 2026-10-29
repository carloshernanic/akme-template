from __future__ import annotations

from typing import Any

import yaml

from ..adapters import load_adapter
from ..models import now_iso
from ..ontology import load_content, load_manifest, save_manifest
from ..project import Project, read_yaml, write_yaml
from .export import build_export, to_yarrrml

TARGETS = ("yaml", "snowflake", "databricks", "rdf")


def _q(text: str) -> str:
    return (text or "").replace("'", "''")


def semantic_model(project: Project) -> dict[str, Any]:
    data = build_export(project)
    terms = {t["name"]: t for t in data["terms"]}
    by_source: dict[str, dict[str, Any]] = {}
    for m in data["mappings"]:
        t = terms.get(m["term"], {})
        src = by_source.setdefault(m["source"], {"name": m["source"], "columns": [], "metrics": []})
        col = {"column": m["column"], "term": m["term"], "class": t.get("class"), "definition": t.get("definition", "")}
        if t.get("class") == "Metric" or m.get("role") == "metric":
            col["expression"] = m.get("expression", f"SUM({m['column']})")
            src["metrics"].append(col)
        else:
            src["columns"].append(col)
    return {
        "project": data["project"], "version": data["version"], "sources": list(by_source.values()),
        "relations": data["relations"], "glossary": data["glossary"], "precedence": data["precedence"],
        "examples": [c for c in data["requirements"]["competency_questions"] if c.get("status") == "approved"],
    }


def render_yaml(model: dict[str, Any]) -> str:
    return yaml.safe_dump(model, allow_unicode=True, sort_keys=False)


def render_snowflake(model: dict[str, Any], project: Project) -> list[str]:
    opts = project.adapter_options()
    db, schema = opts.get("database", "DB"), opts.get("schema", "PUBLIC")
    name = f"{db}.{schema}.{model['project'].upper()}_SEMANTIC"
    tables, dims, metrics, comments = [], [], [], []
    for s in model["sources"]:
        fq = f"{db}.{schema}.{s['name']}"
        tables.append(f"    {s['name']} AS {fq}")
        for c in s["columns"]:
            dims.append(f"    {s['name']}.{c['term']} AS {c['column']} COMMENT '{_q(c['definition'])}'")
            comments.append(f"COMMENT ON COLUMN {fq}.{c['column']} IS '{_q(c['definition'])}';")
        for c in s["metrics"]:
            metrics.append(f"    {s['name']}.{c['term']} AS {c['expression']} COMMENT '{_q(c['definition'])}'")
    stmt = [f"CREATE OR REPLACE SEMANTIC VIEW {name}", "  TABLES (", ",\n".join(tables), "  )"]
    if dims:
        stmt += ["  DIMENSIONS (", ",\n".join(dims), "  )"]
    if metrics:
        stmt += ["  METRICS (", ",\n".join(metrics), "  )"]
    stmt.append(f"  COMMENT = 'AKME {model['project']} v{model['version']}';")
    return ["\n".join(stmt)] + comments


def render_databricks(model: dict[str, Any], project: Project) -> list[str]:
    opts = project.adapter_options()
    catalog, schema = opts.get("catalog", "main"), opts.get("schema", "default")
    out = []
    for s in model["sources"]:
        fq = f"{catalog}.{schema}.{s['name']}"
        out.append(f"COMMENT ON TABLE {fq} IS 'AKME {model['project']} v{model['version']}';")
        for c in s["columns"] + s["metrics"]:
            out.append(f"ALTER TABLE {fq} ALTER COLUMN {c['column']} COMMENT '{_q(c['term'])}: {_q(c['definition'])}';")
    return out


def render_rdf(project: Project, dry_run: bool) -> dict[str, Any]:
    data = build_export(project)
    yarrrml, skipped = to_yarrrml(project, data)
    path = project.ontology_dir / "mappings.yarrrml.yml"
    write_yaml(path, yarrrml)
    if dry_run:
        return {"yarrrml": str(path), "materialized": False, "skipped": skipped}
    if project.adapter_name != "local_folder":
        raise RuntimeError("publish rdf materializa apenas a partir de local_folder; para bancos use o Morph-KGC direto com db_url")
    try:
        import morph_kgc
    except ImportError as exc:
        raise RuntimeError("instale o extra 'rdf' (uv sync --extra rdf) para materializar com Morph-KGC") from exc
    config = f"[DataSource1]\nmappings: {path}\n"
    g = morph_kgc.materialize(config)
    out = project.docs_dir / "ontology-data.ttl"
    out.write_text(g.serialize(format="turtle"), encoding="utf-8")
    return {"yarrrml": str(path), "materialized": True, "output": str(out), "triples": len(g), "skipped": skipped}


def bump_version(project: Project, part: str) -> str:
    manifest = load_manifest(project)
    major, minor, patch = (int(x) for x in str(manifest.get("version", "0.0.0")).split("."))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        major, minor, patch = (int(x) for x in part.split("."))
    version = f"{major}.{minor}.{patch}"
    manifest["version"] = version
    save_manifest(project, manifest)
    log = read_yaml(project.changelog_path)
    entries = list(log.get("entries") or [])
    entries.append({"release": version, "released_at": now_iso()})
    write_yaml(project.changelog_path, {"entries": entries})
    return version


def publish(project: Project, target: str = "yaml", dry_run: bool = True, release: str | None = None) -> dict[str, Any]:
    if target not in TARGETS:
        raise ValueError(f"target desconhecido: {target}. Opcoes: {', '.join(TARGETS)}")
    if release:
        bump_version(project, release)
    out_dir = project.docs_dir / "publish"
    out_dir.mkdir(parents=True, exist_ok=True)
    if target == "rdf":
        result = render_rdf(project, dry_run)
        result.update({"target": target, "dry_run": dry_run})
        return result
    model = semantic_model(project)
    if target == "yaml":
        path = out_dir / "semantic.yml"
        path.write_text(render_yaml(model), encoding="utf-8")
        return {"target": target, "dry_run": True, "artifact": str(path), "sources": len(model["sources"])}
    statements = render_snowflake(model, project) if target == "snowflake" else render_databricks(model, project)
    path = out_dir / f"{target}.sql"
    path.write_text("\n\n".join(statements) + "\n", encoding="utf-8")
    executed = 0
    if not dry_run:
        if project.adapter_name != target:
            raise RuntimeError(f"publish --no-dry-run em {target} exige adapter {target} no akme.yml (atual: {project.adapter_name})")
        adapter = load_adapter(project.adapter_name, project.adapter_options())
        try:
            for stmt in statements:
                adapter.execute(stmt)
                executed += 1
        finally:
            adapter.close()
    return {"target": target, "dry_run": dry_run, "artifact": str(path), "statements": len(statements), "executed": executed}
