"""Contratos de relacao e metrica: o que o join e a medida prometem, conferido no dado."""
from __future__ import annotations

from typing import Any

from ..adapters import load_adapter
from ..project import Project
from .neo4j_values import shown

JOIN_SIDES = ("from", "to")
JOIN_FIELDS = ("source", "column")
SAMPLE = 5000


def check_join_shape(join: Any) -> str | None:
    """Mensagem de erro se o bloco join nao tiver from e to com source e column."""
    if not isinstance(join, dict):
        return "join deve ser um objeto com from e to"
    for side in JOIN_SIDES:
        end = join.get(side)
        if not isinstance(end, dict) or any(not str(end.get(f) or "").strip() for f in JOIN_FIELDS):
            return f"join.{side} exige source e column"
    return None


def _key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _side(rows: list[dict[str, Any]], column: str) -> dict[str, Any]:
    keys = [_key(r.get(column)) for r in rows]
    present = [k for k in keys if k is not None]
    distinct = set(present)
    return {"rows": len(rows), "nulls": len(keys) - len(present), "distinct": len(distinct),
            "duplicated": len(distinct) < len(present), "keys": distinct}


def observe_join(project: Project, join: dict[str, Any], sample: int = SAMPLE) -> dict[str, Any]:
    """Le uma amostra das duas pontas e mede nulos, duplicatas, orfaos e a multiplicidade observada."""
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        sources = set(adapter.list_sources())
        ends = {}
        for side in JOIN_SIDES:
            src, col = join[side]["source"], join[side]["column"]
            if src not in sources:
                return {"available": False, "reason": f"fonte inexistente: {shown([src])}"}
            if col not in [c["name"] for c in adapter.read_schema(src)["columns"]]:
                return {"available": False, "reason": f"coluna inexistente: {src}.{shown([col])}"}
            ends[side] = _side(adapter.read_sample(src, sample), col)
    finally:
        adapter.close()
    left, right = ends["from"], ends["to"]
    orphans = sorted(left["keys"] - right["keys"])
    truncated = left["rows"] >= sample or right["rows"] >= sample
    observed = f"{'many' if left['duplicated'] else 'one'}_to_{'many' if right['duplicated'] else 'one'}"
    return {
        "available": True, "sample": sample, "truncated": truncated,
        "multiplicity": observed,
        "from": {k: v for k, v in left.items() if k != "keys"},
        "to": {k: v for k, v in right.items() if k != "keys"},
        "orphans": len(orphans), "orphan_examples": orphans[:5],
        "coverage": round(1 - len(orphans) / left["distinct"], 3) if left["distinct"] else 0.0,
        # juntar domain com range repete linhas do domain quando a ponta "to" tem chave repetida
        "fanout": right["duplicated"],
    }


def contradictions(declared: str, observed: dict[str, Any]) -> list[str]:
    """Lados declarados como "one" mas com chave repetida no dado. "many" sem repeticao na amostra e compativel."""
    if not observed.get("available"):
        return []
    left, right = declared.split("_to_")
    out = []
    if left == "one" and observed["from"]["duplicated"]:
        out.append("o lado do domain foi declarado 'one' mas a coluna de join tem valores repetidos")
    if right == "one" and observed["to"]["duplicated"]:
        out.append("o lado do range foi declarado 'one' mas a coluna de join tem valores repetidos (fanout)")
    return out


def one_side_sources(contract: dict[str, Any]) -> list[tuple[str, str]]:
    """Pares (fonte do lado one, fonte do lado many) de um contrato com join."""
    join, mult = contract.get("join"), contract.get("multiplicity", "")
    if not join or mult not in ("many_to_one", "one_to_many"):
        return []
    a, b = join["from"]["source"], join["to"]["source"]
    return [(b, a)] if mult == "many_to_one" else [(a, b)]


def fanout_sources(contracts: list[dict[str, Any]], source: str) -> list[str]:
    """Fontes cujo join com `source` repete as linhas de `source` (ela e o lado one)."""
    return sorted({many for c in contracts for one, many in one_side_sources(c) if one == source})
