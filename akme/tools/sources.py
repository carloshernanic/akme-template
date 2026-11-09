"""Chave e tipos de cada fonte, decididos na etapa 5 antes de exportar para o Neo4j.

`suggest_sources` monta um rascunho a partir dos contratos de relacao e do profile, sem LLM. `check_source`
confere uma proposta contra o dado e recusa o que daria erro na carga. A decisao final e humana, na revisao.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..adapters import load_adapter
from ..models import SOURCE_TYPES
from ..ontology import load_content
from ..project import Project
from .profile import profile_source

# nomes que indicam identificador: um inteiro com esse nome fica texto (zero a esquerda, nao se soma)
_IDENTIFIER = {"id", "identifier", "ident", "number", "numero", "num", "nr", "no", "code", "codigo", "cod", "cd",
               "cnpj", "cpf", "cep", "nf", "sku", "key", "chave"}


class SourceError(ValueError):
    pass


def _tokens(name: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return [t for t in re.split(r"[^a-zA-Z0-9]+", spaced.lower()) if t]


def looks_like_identifier(name: str) -> bool:
    return any(t in _IDENTIFIER for t in _tokens(name))


def _filled(value: Any) -> bool:
    return value not in (None, "")


def _join_columns(project: Project, source: str) -> set[str]:
    contracts = load_content(project)["relation_contracts"]
    return {c["join"][side]["column"] for c in contracts if c.get("join") for side in ("from", "to")
            if c["join"][side]["source"] == source}


def _read(project: Project, source: str) -> tuple[list[str], list[dict[str, Any]], bool]:
    from .n10s import MAX_ROWS

    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        if source not in adapter.list_sources():
            raise SourceError(f"fonte inexistente: {source}")
        rows = adapter.read_sample(source, MAX_ROWS + 1)
    finally:
        adapter.close()
    return (list(rows[0]) if rows else []), rows[:MAX_ROWS], len(rows) > MAX_ROWS


def parse_types(value: Any) -> dict[str, str]:
    """Aceita dict ou o texto que a pagina de revisao envia: 'coluna: tipo, coluna: tipo'."""
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    out: dict[str, str] = {}
    for part in re.split(r"[,\n]", str(value or "")):
        if not part.strip():
            continue
        if ":" not in part:
            raise SourceError(f"types: use 'coluna: tipo', recebi '{part.strip()}'")
        col, kind = (x.strip() for x in part.rsplit(":", 1))
        out[col] = kind
    return out


def check_source(project: Project, payload: dict[str, Any]) -> dict[str, Any]:
    """Confere chave e tipos contra o dado. Devolve o payload normalizado com o bloco `checked`."""
    from .n10s import rdf_literal

    source = payload["source"]
    exclude = str(payload.get("exclude") or "").strip()
    raw_key = payload.get("key")
    key = [raw_key] if isinstance(raw_key, str) else [str(k).strip() for k in (raw_key or []) if str(k).strip()]
    types = parse_types(payload.get("types"))
    columns, rows, truncated = _read(project, source)
    if exclude:
        if key or types:
            raise SourceError("fonte excluida nao pode ter key nem types")
        return {"source": source, "exclude": exclude}
    if not key:
        raise SourceError("add_source exige key ou exclude")
    if not rows:
        raise SourceError(f"fonte {source} sem linhas: nao ha como conferir a chave")
    absent = [c for c in key + list(types) if c not in columns]
    if absent:
        raise SourceError(f"coluna inexistente em {source}: {', '.join(absent)}")
    empty = sum(1 for r in rows if not all(_filled(r.get(c)) for c in key))
    if empty:
        raise SourceError(f"{source}: {empty} linha(s) com a chave {'+'.join(key)} vazia")
    counts = Counter(tuple(str(r[c]) for c in key) for r in rows)
    repeated = [" | ".join(v) for v, n in counts.items() if n > 1]
    if repeated:
        raise SourceError(f"{source}.{'+'.join(key)} repete {len(repeated)} valor(es), ex.: {repeated[:3]}: duas linhas virariam o mesmo no")
    unknown = {c: k for c, k in types.items() if k not in SOURCE_TYPES}
    if unknown:
        raise SourceError(f"tipo desconhecido em {source}: {unknown}; use {', '.join(SOURCE_TYPES)}")
    protected = set(key) | _join_columns(project, source)
    wrong = [c for c, k in types.items() if c in protected and k != "string"]
    if wrong:
        raise SourceError(f"{source}.{', '.join(wrong)} e chave ou join e precisa ficar string")
    checked: dict[str, Any] = {"rows": len(rows), "truncated": truncated, "types": {}}
    for col, kind in types.items():
        values = [r[col] for r in rows if _filled(r.get(col))]
        bad = []
        for v in values:
            try:
                rdf_literal(kind, v)
            except ValueError:
                bad.append(v)
        if bad:
            raise SourceError(f"{len(bad)} de {len(values)} valores de {source}.{col} nao convertem para {kind}, ex.: {bad[0]}")
        checked["types"][col] = {"kind": kind, "converted": len(values), "filled": len(values),
                                 "example": str(values[0]) if values else ""}
    return {"source": source, "key": key, "types": types, "class": _class_of(project, source), "checked": checked}


def _class_of(project: Project, source: str) -> str:
    """Classe que a fonte vira no grafo, so para mostrar na revisao."""
    content = load_content(project)
    for c in content["relation_contracts"]:
        for side, cls in (("from", c.get("domain")), ("to", c.get("range"))):
            if c.get("join") and c["join"][side]["source"] == source:
                return cls or ""
    classes = {t["name"]: t.get("class") for t in content["terms"]}
    return next((classes.get(m["term"]) or "" for m in content["mappings"] if m["source"] == source and m.get("role") != "metric"), "")


def suggest_sources(project: Project) -> list[dict[str, Any]]:
    """Rascunho de chave e tipos para cada fonte. O agente revisa antes de propor; o humano decide."""
    from .export import build_export
    from .n10s import _keys, _labels

    data = build_export(project)
    contracts = data["relation_contracts"]
    contract_key = _keys(contracts)
    key_relation = {}
    for c in contracts:
        join, mult = c.get("join"), c.get("multiplicity")
        if join and mult != "many_to_many":
            side = join["from"] if mult == "one_to_many" else join["to"]
            key_relation.setdefault(side["source"], c["relation"])
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        sources = adapter.list_sources()
    finally:
        adapter.close()
    labels, _ = _labels(data, project, sources, [])
    out = []
    for source in sources:
        if source not in labels:
            reason = "nao aparece em nenhuma relacao nem mapping da ontologia"
            out.append({"source": source, "class": None, "key": [], "key_from": "", "types": {}, "notes": [reason],
                        "payload": {"source": source, "exclude": reason}})
            continue
        columns, rows, _ = _read(project, source)
        prof = profile_source(source, columns, rows)
        joins = _join_columns(project, source)
        notes: list[str] = []
        if source in contract_key:
            key, key_from = [contract_key[source]], f"contrato da relacao {key_relation[source]}"
        else:
            candidates = [c for c in prof.candidate_keys if c in joins or looks_like_identifier(c)]
            key = candidates[:1]
            key_from = "chave candidata do profile" if key else ""
            if not key:
                notes.append("nenhuma coluna unica com nome de identificador: proponha a chave, que pode ser composta")
        types: dict[str, str] = {}
        for col in prof.columns:
            if col.name in joins or col.name in key:
                continue
            if col.type == "date":
                types[col.name] = "date"
            elif col.type == "number":
                types[col.name] = "float"
            elif col.type == "integer" and not looks_like_identifier(col.name):
                types[col.name] = "integer"
            elif col.type == "integer":
                notes.append(f"{col.name} tem numeros, mas o nome indica identificador: fica texto")
            elif col.type == "datetime":
                notes.append(f"{col.name} tem data com horario: fica texto, o Neo4j recebe so data")
        out.append({"source": source, "class": labels[source], "key": key, "key_from": key_from, "types": types,
                    "notes": notes, "payload": {"source": source, "key": key, "types": types} if key else None})
    return out
