from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

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
    add_use_case = "add_use_case"
    update_competency_question = "update_competency_question"
    remove_competency_question = "remove_competency_question"
    add_gap = "add_gap"
    add_divergence = "add_divergence"
    update_gap = "update_gap"
    update_divergence = "update_divergence"
    add_source = "add_source"
    update_mapping = "update_mapping"
    remove_mapping = "remove_mapping"
    rename_class = "rename_class"


# Vocabularios da revisao de requisitos
CQ_TYPES = ("classificacao_hierarquia", "relacao_entre_conceitos", "atributos", "quantidade_agregacao", "tempo_estado", "regras_restricoes")
CQ_STATUSES = ("proposed", "approved", "reserved", "rejected", "deprecated")
PRIORITIES = ("high", "medium", "low")
GAP_DECISIONS = ("request_from_client", "reformulate", "drop", "open")
DIVERGENCE_DECISIONS = ("precedence", "distinct_terms", "ask_expert", "dismiss", "open")
EVIDENCE_KINDS = ("source", "conversation")

# Contratos de relacao e metrica. Multiplicidade lida de domain para range.
MULTIPLICITIES = ("many_to_one", "one_to_many", "one_to_one", "many_to_many")
ADDITIVITY = ("additive", "semi_additive", "non_additive")
METRIC_FIELDS = ("unit", "grain", "additivity")

# Tipos da etapa 1 (requisitos) e da etapa 2 (ontologia)
STAGE1_TYPES = frozenset({
    EditType.add_use_case, EditType.update_competency_question, EditType.remove_competency_question,
    EditType.add_gap, EditType.add_divergence, EditType.update_gap, EditType.update_divergence,
    EditType.add_competency_question, EditType.add_requirement, EditType.add_glossary,
})
ONTOLOGY_TYPES = frozenset({
    EditType.add_class, EditType.add_relation, EditType.add_term,
    EditType.add_mapping, EditType.add_constraint, EditType.add_precedence,
    EditType.update_mapping, EditType.remove_mapping, EditType.rename_class,
})
# Correcoes do que ja foi aplicado: mudam ou apagam um item em vez de acrescentar
MAPPING_FIELDS = ("term", "source", "column", "role", "expression", "note")

# Etapa 5 (publicar): chave e tipos de cada fonte, decididos so quando o alvo e o Neo4j
EXPORT_TYPES = frozenset({EditType.add_source})
SOURCE_TYPES = ("string", "integer", "float", "date")

# Etapa do fluxo (LOT) em que cada tipo e decidido: 1 especificar, 2 conceitualizar, 3 codificar, 5 publicar
EDIT_STAGE: dict[EditType, int] = {t: 1 for t in STAGE1_TYPES} | {
    EditType.add_class: 2, EditType.add_relation: 2, EditType.add_term: 2,
    EditType.add_mapping: 3, EditType.add_constraint: 3, EditType.add_precedence: 3,
    EditType.add_source: 5,
    EditType.rename_class: 2, EditType.update_mapping: 3, EditType.remove_mapping: 3,
}
APPLY_STAGES = ("requirements", "ontology", "export", "all")


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
    EditType.add_relation: ["name", "domain", "range", "label", "multiplicity"],
    EditType.add_competency_question: ["question", "type", "concepts", "evidence"],
    EditType.add_requirement: ["field", "value"],
    EditType.add_use_case: ["name", "description"],
    EditType.update_competency_question: ["id"],
    EditType.remove_competency_question: ["id", "reason"],
    EditType.add_gap: ["question", "reason", "missing", "evidence"],
    EditType.add_divergence: ["topic", "sources"],
    EditType.update_gap: ["id", "decision"],
    EditType.update_divergence: ["id", "decision"],
    EditType.add_source: ["source"],
    EditType.update_mapping: ["term", "source", "column", "set"],
    EditType.remove_mapping: ["term", "source", "column", "reason"],
    EditType.rename_class: ["name", "new_name"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Review(BaseModel):
    decision: Literal["accept", "reject"]
    reviewer: str
    reviewed_at: str
    edits: dict[str, Any] = {}
    reason: str = ""


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
    review: Review | None = None


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
