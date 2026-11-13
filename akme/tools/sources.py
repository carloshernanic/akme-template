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
from .neo4j_plan import BATCH, Scan, contract_keys, join_columns, labels_for, ragged_problem, scan_source
from .neo4j_values import shown
from .profile import profile_source

# nomes que indicam identificador: um inteiro com esse nome fica texto (zero a esquerda, nao se soma)
_IDENTIFIER = {"id", "identifier", "ident", "number", "numero", "num", "nr", "no", "code", "codigo", "cod", "cd",
               "cnpj", "cpf", "cep", "nf", "sku", "key", "chave"}


SAMPLE_ROWS = 100_000  # so o rascunho do suggest_sources usa amostra


class SourceError(ValueError):
    pass


def _tokens(name: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return [t for t in re.split(r"[^a-zA-Z0-9]+", spaced.lower()) if t]


def looks_like_identifier(name: str) -> bool:
    return any(t in _IDENTIFIER for t in _tokens(name))


def _join_columns(project: Project, source: str) -> set[str]:
    contracts = load_content(project)["relation_contracts"]
    return {column for src, column in join_columns(contracts) if src == source}


def _sample(project: Project, source: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Amostra para o rascunho do suggest_sources. A conferencia do check_source le a fonte inteira."""
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        if source not in adapter.list_sources():
            raise SourceError(f"fonte inexistente: {shown([source])}")
        rows = adapter.read_sample(source, SAMPLE_ROWS)
    finally:
        adapter.close()
    return (list(rows[0]) if rows else []), rows


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


def _read_whole(project: Project, source: str, key: list[str], types: dict[str, str], *, check: bool = True) -> Scan:
    """Confere que a fonte existe e, com check, le a fonte inteira pelo leitor unico do plano (scan_source)."""
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        if source not in adapter.list_sources():
            raise SourceError(f"fonte inexistente: {shown([source])}")
        if not check:
            return Scan(columns=[], key=[], absent=[])
        return scan_source(adapter, source, key, types, batch=BATCH)
    finally:
        adapter.close()


def check_source(project: Project, payload: dict[str, Any]) -> dict[str, Any]:
    """Confere chave e tipos contra a fonte inteira, lida em blocos. Devolve o payload normalizado com o bloco `checked`."""
    source = payload["source"]
    exclude = str(payload.get("exclude") or "").strip()
    raw_key = payload.get("key")
    key = [raw_key] if isinstance(raw_key, str) else [str(k).strip() for k in (raw_key or []) if str(k).strip()]
    types = parse_types(payload.get("types"))
    # o que o payload sozinho ja recusa vem antes de ler a fonte inteira
    if exclude and (key or types):
        raise SourceError("fonte excluida nao pode ter key nem types")
    if not exclude and not key:
        raise SourceError("add_source exige key ou exclude")
    unknown = {c: k for c, k in types.items() if k not in SOURCE_TYPES}
    if unknown:
        raise SourceError(f"tipo desconhecido em {source}: {unknown}; use {', '.join(SOURCE_TYPES)}")
    protected = set(key) | _join_columns(project, source)
    wrong = [c for c, k in types.items() if c in protected and k != "string"]
    if wrong:
        raise SourceError(f"{source}.{', '.join(wrong)} e chave ou join e precisa ficar string")
    scan = _read_whole(project, source, key, types, check=not exclude)
    if exclude:
        return {"source": source, "exclude": exclude}
    if scan.ragged:  # mesma recusa do plano: a carga nao aceitaria esta fonte
        raise SourceError(ragged_problem(source, scan.ragged))
    if not scan.rows:
        raise SourceError(f"fonte {source} sem linhas: nao ha como conferir a chave")
    absent = [c for c in key + list(types) if c not in scan.columns]
    if absent:
        raise SourceError(f"coluna inexistente em {source}: {shown(absent)}")
    empty = scan.rows - scan.complete
    if empty:
        raise SourceError(f"{source}: {empty} linha(s) com a chave {'+'.join(key)} vazia")
    if scan.repeated_ids:
        raise SourceError(f"{source}.{'+'.join(key)} repete {len(scan.repeated_ids)} valor(es), ex.: {scan.repeated[:3]}: duas linhas virariam o mesmo no")
    checked: dict[str, Any] = {"rows": scan.rows, "types": {}}
    for col, kind in types.items():
        if scan.invalid[col]:
            raise SourceError(f"{scan.invalid[col]} de {scan.filled[col]} valores de {source}.{col} nao convertem para {kind}, ex.: {scan.examples[col]}")
        checked["types"][col] = {"kind": kind, "converted": scan.filled[col], "filled": scan.filled[col],
                                 "example": str(scan.first[col]) if col in scan.first else ""}
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

    data = build_export(project)
    contracts = data["relation_contracts"]
    contract_key = contract_keys(contracts)
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
    labels, _ = labels_for(data, project, sources, [])
    out = []
    for source in sources:
        if source not in labels:
            reason = "nao aparece em nenhuma relacao nem mapping da ontologia"
            out.append({"source": source, "class": None, "key": [], "key_from": "", "types": {}, "notes": [reason],
                        "payload": {"source": source, "exclude": reason}})
            continue
        columns, rows = _sample(project, source)
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
