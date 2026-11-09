from __future__ import annotations

from typing import Any

import yaml

from ..adapters import load_adapter
from ..models import now_iso
from ..ontology import is_metric_class, load_graph, load_manifest, save_manifest
from ..project import Project, read_yaml, write_yaml
from .contracts import fanout_sources
from .export import build_export, to_yarrrml

TARGETS = ("yaml", "snowflake", "databricks", "rdf", "neo4j")


def _q(text: str) -> str:
    return (text or "").replace("'", "''")


class PublishError(ValueError):
    pass


def _relationships(contracts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str], list[str]]:
    """Relacoes com join viram (filho -> pai); o lado one vira chave primaria do pai. many_to_many fica de fora."""
    rels, keys, skipped = [], {}, []
    for c in contracts:
        join, mult = c.get("join"), c.get("multiplicity")
        if not join or mult == "many_to_many":
            skipped.append(c["relation"])
            continue
        child, parent = (join["to"], join["from"]) if mult == "one_to_many" else (join["from"], join["to"])
        if keys.setdefault(parent["source"], parent["column"]) != parent["column"]:
            skipped.append(c["relation"])
            continue
        rels.append({"name": c["relation"], "multiplicity": mult, "from_source": child["source"],
                     "from_column": child["column"], "to_source": parent["source"], "to_column": parent["column"]})
    return rels, keys, skipped


def semantic_model(project: Project) -> dict[str, Any]:
    data = build_export(project)
    g = load_graph(project.schema_path)
    terms = {t["name"]: t for t in data["terms"]}
    contracts = data["relation_contracts"]
    by_source: dict[str, dict[str, Any]] = {}

    def source(name: str) -> dict[str, Any]:
        return by_source.setdefault(name, {"name": name, "primary_key": None, "columns": [], "metrics": []})

    no_expression = []
    for m in data["mappings"]:
        t = terms.get(m["term"], {})
        src = source(m["source"])
        col = {"column": m["column"], "term": m["term"], "class": t.get("class"), "definition": t.get("definition", "")}
        if m.get("role") == "metric" or (t.get("class") and is_metric_class(g, t["class"])):
            if not str(m.get("expression") or "").strip():
                no_expression.append(m["term"])
                continue
            col |= {"expression": m["expression"]} | {k: t[k] for k in ("unit", "grain", "additivity", "non_additive_over") if t.get(k)}
            col["do_not_sum_after_join_with"] = fanout_sources(contracts, m["source"])
            src["metrics"].append(col)
        else:
            src["columns"].append(col)
    if no_expression:
        raise PublishError("metricas sem expression no mapping: " + ", ".join(no_expression) + ". Rode akme validate")
    rels, keys, skipped = _relationships(contracts)
    for r in rels:
        source(r["from_source"]), source(r["to_source"])
    for name, column in keys.items():
        source(name)["primary_key"] = column
    return {
        "project": data["project"], "version": data["version"], "sources": list(by_source.values()),
        "relationships": rels, "relationships_not_published": skipped,
        "relations": data["relations"], "glossary": data["glossary"], "precedence": data["precedence"],
        "examples": [c for c in data["requirements"]["competency_questions"] if c.get("status") == "approved"],
    }


def render_yaml(model: dict[str, Any]) -> str:
    return yaml.safe_dump(model, allow_unicode=True, sort_keys=False)


_ADDITIVITY_PT = {"additive": "aditiva", "semi_additive": "semiaditiva", "non_additive": "nao aditiva"}


def _metric_comment(c: dict[str, Any]) -> str:
    parts = [f"unidade {c['unit']}" if c.get("unit") else "", f"grao {c['grain']}" if c.get("grain") else "",
             _ADDITIVITY_PT.get(c.get("additivity", ""), "")]
    if c.get("do_not_sum_after_join_with"):
        parts.append("nao somar apos join com " + ", ".join(c["do_not_sum_after_join_with"]))
    extra = "; ".join(p for p in parts if p)
    return f"{c['definition']} [{extra}]" if extra else c["definition"]


def render_snowflake(model: dict[str, Any], project: Project) -> list[str]:
    opts = project.adapter_options()
    db, schema = opts.get("database", "DB"), opts.get("schema", "PUBLIC")
    name = f"{db}.{schema}.{model['project'].upper()}_SEMANTIC"
    tables, rels, dims, metrics, comments = [], [], [], [], []
    for s in model["sources"]:
        fq = f"{db}.{schema}.{s['name']}"
        pk = f" PRIMARY KEY ({s['primary_key']})" if s.get("primary_key") else ""
        tables.append(f"    {s['name']} AS {fq}{pk}")
        for c in s["columns"]:
            dims.append(f"    {s['name']}.{c['term']} AS {c['column']} COMMENT = '{_q(c['definition'])}'")
            comments.append(f"COMMENT ON COLUMN {fq}.{c['column']} IS '{_q(c['definition'])}';")
        for c in s["metrics"]:
            metrics.append(f"    {s['name']}.{c['term']} AS {c['expression']} COMMENT = '{_q(_metric_comment(c))}'")
    for r in model.get("relationships", []):
        rels.append(f"    {r['name']} AS {r['from_source']} ({r['from_column']}) REFERENCES {r['to_source']} ({r['to_column']})")
    stmt = [f"CREATE OR REPLACE SEMANTIC VIEW {name}", "  TABLES (", ",\n".join(tables), "  )"]
    if rels:
        stmt += ["  RELATIONSHIPS (", ",\n".join(rels), "  )"]
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
    if target != "rdf":
        semantic_model(project)  # falha antes do bump se faltar contrato de metrica
    if release and target != "neo4j":
        bump_version(project, release)
    out_dir = project.docs_dir / "publish"
    out_dir.mkdir(parents=True, exist_ok=True)
    if target == "rdf":
        result = render_rdf(project, dry_run)
        result.update({"target": target, "dry_run": dry_run})
        return result
    model = semantic_model(project)
    if target == "neo4j":
        from .n10s import publish_neo4j
        result = publish_neo4j(project, model, dry_run)
        if release and not result["problems"]:
            bump_version(project, release)
        return result
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
