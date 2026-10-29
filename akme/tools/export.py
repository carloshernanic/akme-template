from __future__ import annotations

import json
from typing import Any

from ..adapters import AdapterError, load_adapter
from ..ontology import classes, load_content, load_graph, load_manifest, relations
from ..project import Project, read_yaml, write_yaml


def build_export(project: Project) -> dict[str, Any]:
    g = load_graph(project.schema_path)
    content = load_content(project)
    manifest = load_manifest(project)
    validation = read_yaml(project.validation_path) if project.validation_path.exists() else None
    summary = None
    if validation:
        summary = {
            "generated_at": validation.get("generated_at"),
            "ok": validation.get("ok"),
            "errors": sum(1 for f in validation.get("findings", []) if f.get("level") == "error"),
            "warnings": sum(1 for f in validation.get("findings", []) if f.get("level") == "warning"),
            "coverage": validation.get("coverage"),
            "pitfalls": validation.get("pitfalls", []),
            "findings": validation.get("findings", []),
        }
    return {
        "project": project.name,
        "version": manifest.get("version", "0.0.0"),
        "base_iri": manifest.get("base_iri"),
        "classes": classes(g),
        "relations": relations(g),
        "terms": content["terms"],
        "mappings": content["mappings"],
        "constraints": content["constraints"],
        "glossary": content["glossary"],
        "precedence": content["precedence"],
        "requirements": content["requirements"],
        "validation": summary,
    }


def to_mermaid(data: dict[str, Any]) -> str:
    lines = ["classDiagram"]
    for c in data["classes"]:
        lines.append(f"    class {c['name']}")
        for parent in c["subclass_of"]:
            lines.append(f"    {parent} <|-- {c['name']}")
    for r in data["relations"]:
        for d in r["domain"]:
            for rg in r["range"]:
                lines.append(f"    {d} --> {rg} : {r['name']}")
    return "\n".join(lines) + "\n"


def _csv_files(project: Project) -> dict[str, str] | None:
    if project.adapter_name != "local_folder":
        return None
    try:
        adapter = load_adapter(project.adapter_name, project.adapter_options())
        locations = {s: adapter.source_location(s) for s in adapter.list_sources()}
    except AdapterError:
        return None
    return {s: loc["file"].as_posix() for s, loc in locations.items() if loc["file"].suffix.lower() == ".csv"}


def to_yarrrml(project: Project, data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    base = data.get("base_iri") or "https://akme.example/ontology#"
    files = _csv_files(project)
    source_dir = project.adapter_options().get("path", ".")
    term_class = {t["name"]: t.get("class") for t in data["terms"]}
    mappings: dict[str, Any] = {}
    skipped: list[str] = []
    for m in data["mappings"]:
        source = m["source"]
        if files is not None and source not in files:
            if source not in skipped:
                skipped.append(source)
            continue
        access = files[source] if files is not None else f"{source_dir}/{source}.csv"
        entry = mappings.setdefault(source, {
            "sources": [{"access": access, "referenceFormulation": "csv"}],
            "s": f"{base}{source}/$({m['column']})",
            "po": [],
        })
        cls = term_class.get(m["term"])
        if cls and ["a", f"akme:{cls}"] not in entry["po"]:
            entry["po"].append(["a", f"akme:{cls}"])
        entry["po"].append([f"akme:{m['term']}", f"$({m['column']})"])
    return {"prefixes": {"akme": base}, "mappings": mappings}, skipped


def export(project: Project) -> dict[str, Any]:
    data = build_export(project)
    project.docs_dir.mkdir(parents=True, exist_ok=True)
    json_path = project.docs_dir / "ontology.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    js_path = project.docs_dir / "ontology.js"
    js_path.write_text("window.AKME_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    mmd_path = project.docs_dir / "ontology.mmd"
    mmd_path.write_text(to_mermaid(data), encoding="utf-8")
    yarrrml_path = project.ontology_dir / "mappings.yarrrml.yml"
    yarrrml, skipped = to_yarrrml(project, data)
    write_yaml(yarrrml_path, yarrrml)
    return {"json": str(json_path), "mermaid": str(mmd_path), "yarrrml": str(yarrrml_path), "yarrrml_skipped": skipped,
            "classes": len(data["classes"]), "relations": len(data["relations"]), "terms": len(data["terms"])}
