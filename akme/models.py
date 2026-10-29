from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EditType(str, Enum):
    add_term = "add_term"
    add_mapping = "add_mapping"
    add_constraint = "add_constraint"
    add_glossary = "add_glossary"
    add_precedence = "add_precedence"
    add_class = "add_class"
    add_relation = "add_relation"
    add_competency_question = "add_competency_question"
    add_requirement = "add_requirement"


CONTENT_SECTION = {
    EditType.add_term: "terms",
    EditType.add_mapping: "mappings",
    EditType.add_constraint: "constraints",
    EditType.add_glossary: "glossary",
    EditType.add_precedence: "precedence",
}

REQUIRED_FIELDS: dict[EditType, list[str]] = {
    EditType.add_term: ["name", "class", "definition"],
    EditType.add_mapping: ["term", "source", "column"],
    EditType.add_constraint: ["term", "rule"],
    EditType.add_glossary: ["acronym", "meaning"],
    EditType.add_precedence: ["topic", "winner", "over"],
    EditType.add_class: ["name", "label", "comment"],
    EditType.add_relation: ["name", "domain", "range", "label"],
    EditType.add_competency_question: ["id", "question"],
    EditType.add_requirement: ["field", "value"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Edit(BaseModel):
    id: str
    type: EditType
    payload: dict[str, Any]
    rationale: str = ""
    proposed_by: str = "agent"
    requirement_id: str | None = None
    evidence: str = ""
    created_at: str = Field(default_factory=now_iso)
    status: str = "pending"


class ColumnProfile(BaseModel):
    name: str
    type: str
    nulls: int
    null_ratio: float
    distinct: int
    cardinality: str
    candidate_key: bool
    samples: list[Any] = []
    conventions: list[str] = []


class SourceProfile(BaseModel):
    name: str
    origin: str = ""
    rows_sampled: int
    columns: list[ColumnProfile]
    candidate_keys: list[str]


class Profile(BaseModel):
    adapter: str
    generated_at: str = Field(default_factory=now_iso)
    sources: list[SourceProfile]
    docs: list[dict[str, Any]] = []
    conventions: dict[str, Any] = {}


class Finding(BaseModel):
    level: str
    check: str
    message: str
    subject: str = ""


class ValidationReport(BaseModel):
    generated_at: str = Field(default_factory=now_iso)
    ok: bool
    findings: list[Finding]
    coverage: dict[str, Any]
    pitfalls: list[dict[str, Any]]
    oops: dict[str, Any] | None = None

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]
