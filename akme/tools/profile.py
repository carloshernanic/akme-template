from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from typing import Any

from ..adapters import load_adapter
from ..models import ColumnProfile, Profile, SourceProfile
from ..project import Project

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")
BOOL_VALUES = {"true", "false", "0", "1", "sim", "nao", "não", "s", "n", "y", "yes", "no"}

NAME_HINTS = [
    (re.compile(r"^(id_|cd_|cod_)|(_id|_cd|_cod)$", re.I), "identifier"),
    (re.compile(r"^(dt_|data_|dat_)|(_dt|_date|_data|_at)$", re.I), "date"),
    (re.compile(r"^(vl_|valor_|vlr_)|(_vl|_valor|_amount|_total)$", re.I), "monetary"),
    (re.compile(r"^(qt_|qtd_|qtde_)|(_qt|_qtd|_qty)$", re.I), "quantity"),
    (re.compile(r"^(fl_|flg_|is_|has_)|(_fl|_flag)$", re.I), "flag"),
    (re.compile(r"^(nm_|nome_|ds_|desc_)|(_nm|_nome|_ds|_desc)$", re.I), "descriptive"),
]
ACRONYM = re.compile(r"\b[A-Z]{2,6}\b")


def _parse(value: Any) -> str:
    if value is None or isinstance(value, (int, float, bool, date, datetime)):
        return {bool: "boolean", int: "integer", float: "number", date: "date", datetime: "datetime"}.get(type(value), "null")
    s = str(value).strip()
    if s.lower() in BOOL_VALUES and s.lower() not in {"0", "1"}:
        return "boolean"
    if re.fullmatch(r"[-+]?\d+", s):
        return "integer"
    if re.fullmatch(r"[-+]?\d*[.,]\d+", s):
        return "number"
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return "date" if "%H" not in fmt else "datetime"
        except ValueError:
            continue
    return "string"


def _infer_type(values: list[Any]) -> str:
    kinds = Counter(_parse(v) for v in values if v is not None)
    if not kinds:
        return "unknown"
    if set(kinds) <= {"integer", "number"}:
        return "number" if "number" in kinds else "integer"
    if set(kinds) == {"date"} or set(kinds) == {"datetime"}:
        return kinds.most_common(1)[0][0]
    if set(kinds) == {"boolean"}:
        return "boolean"
    return "string"


def _naming_style(name: str) -> str:
    if re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", name):
        return "snake_case"
    if re.fullmatch(r"[A-Z0-9]+(_[A-Z0-9]+)*", name):
        return "UPPER_SNAKE"
    if re.fullmatch(r"[a-z]+([A-Z][a-z0-9]*)+", name):
        return "camelCase"
    if re.fullmatch(r"([A-Z][a-z0-9]*)+", name):
        return "PascalCase"
    return "mixed"


def profile_column(name: str, values: list[Any], total: int) -> ColumnProfile:
    non_null = [v for v in values if v is not None]
    distinct = len(set(map(str, non_null)))
    nulls = total - len(non_null)
    if non_null and distinct == len(non_null):
        cardinality = "unique"
    elif distinct <= 10:
        cardinality = "low"
    elif distinct <= max(10, total // 2):
        cardinality = "medium"
    else:
        cardinality = "high"
    conventions = [hint for pattern, hint in NAME_HINTS if pattern.search(name)]
    samples = []
    for v in non_null:
        if v not in samples:
            samples.append(v)
        if len(samples) >= 5:
            break
    kind = _infer_type(values)
    return ColumnProfile(
        name=name, type=kind, nulls=nulls,
        null_ratio=round(nulls / total, 3) if total else 0.0,
        distinct=distinct, cardinality=cardinality,
        candidate_key=cardinality == "unique" and nulls == 0 and total > 1 and kind in ("integer", "string"),
        samples=samples, conventions=conventions,
    )


def profile_source(name: str, columns: list[str], rows: list[dict[str, Any]]) -> SourceProfile:
    total = len(rows)
    cols = [profile_column(c, [r.get(c) for r in rows], total) for c in columns]
    return SourceProfile(
        name=name, rows_sampled=total, columns=cols,
        candidate_keys=[c.name for c in cols if c.candidate_key],
    )


def detect_conventions(sources: list[SourceProfile], docs: list[dict[str, str]]) -> dict[str, Any]:
    names = [c.name for s in sources for c in s.columns]
    styles = Counter(_naming_style(n) for n in names)
    prefixes = Counter(n.split("_")[0] for n in names if "_" in n)
    suffixes = Counter(n.rsplit("_", 1)[-1] for n in names if "_" in n)
    acronyms: Counter[str] = Counter()
    for d in docs:
        acronyms.update(ACRONYM.findall(d.get("text", "")))
    acronyms.update(a for n in names for a in ACRONYM.findall(n.upper()) if len(a) <= 4 and n.isupper())
    return {
        "naming_style": styles.most_common(1)[0][0] if styles else "unknown",
        "naming_styles": dict(styles),
        "common_prefixes": [p for p, c in prefixes.most_common(8) if c > 1],
        "common_suffixes": [s for s, c in suffixes.most_common(8) if c > 1],
        "acronyms_found": [a for a, _ in acronyms.most_common(20)],
    }


def profile(project: Project, sample_size: int = 500) -> Profile:
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    try:
        sources = []
        for name in adapter.list_sources():
            schema = adapter.read_schema(name)
            rows = adapter.read_sample(name, sample_size)
            columns = [c["name"] for c in schema["columns"]]
            sources.append(profile_source(name, columns, rows))
        docs = adapter.read_docs()
    finally:
        adapter.close()
    result = Profile(
        adapter=project.adapter_name, sources=sources,
        docs=[{"name": d["name"], "chars": len(d["text"]), "excerpt": d["text"][:1500]} for d in docs],
        conventions=detect_conventions(sources, docs),
    )
    project.profile_path.parent.mkdir(parents=True, exist_ok=True)
    project.profile_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def load_profile(project: Project) -> Profile | None:
    if not project.profile_path.exists():
        return None
    return Profile.model_validate_json(project.profile_path.read_text(encoding="utf-8"))
