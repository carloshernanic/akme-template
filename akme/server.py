from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .project import Project
from .tools import connect as connect_tool
from .tools import eval as eval_tool
from .tools import export as export_tool
from .tools import ontology_read as read_tool
from .tools import ontology_write as write_tool
from .tools import profile as profile_tool
from .tools import publish as publish_tool
from .tools import requirements as requirements_tool
from .tools import validate as validate_tool

mcp = FastMCP("akme")


def project() -> Project:
    return Project(os.environ.get("AKME_ROOT", "."))


@mcp.tool()
def connect() -> dict[str, Any]:
    """Escolhe o adapter definido em akme.yml e testa a conexao, listando fontes e documentos."""
    return connect_tool.connect(project())


@mcp.tool()
def read_document(name: str, page: int | None = None) -> dict[str, Any]:
    """Le um documento do cliente (md, txt, pdf, docx, pptx). Sem page devolve o indice de paginas ou slides;
    com page (comeca em 1) devolve o texto daquela pagina. Use o nome exato listado por connect ou profile."""
    return connect_tool.read_document(project(), name, page)


@mcp.tool()
def find_in_sources(query: str, whole_word: bool = True, case_sensitive: bool = False,
                    max_hits: int = 50) -> dict[str, Any]:
    """Procura um termo em todos os documentos e planilhas do cliente. Devolve cada ocorrencia com caminho,
    pagina ou slide e trecho; nas tabelas, fonte, aba, coluna, linhas de dados e valores. Use antes de afirmar
    de onde vem uma informacao ou que algo nao aparece. Para siglas, use case_sensitive=true."""
    return connect_tool.find_in_sources(project(), query, whole_word, case_sensitive, max_hits)


@mcp.tool()
def profile(sample_size: int = 500) -> dict[str, Any]:
    """Perfila as fontes: colunas, tipos, nulos, cardinalidade, chaves candidatas e convencoes. Grava docs/profile.json."""
    return profile_tool.profile(project(), sample_size).model_dump()


@mcp.tool()
def list_entities() -> list[dict[str, Any]]:
    """Lista as classes do schema.ttl com os termos ligados a cada uma."""
    return read_tool.list_entities(project())


@mcp.tool()
def list_relations() -> list[dict[str, Any]]:
    """Lista as relacoes (object properties) com domain, range e inversa."""
    return read_tool.list_relations(project())


@mcp.tool()
def search_term(query: str) -> dict[str, Any]:
    """Busca um texto em termos, glossario, mappings, classes e relacoes."""
    return read_tool.search_term(project(), query)


@mcp.tool()
def resolve_acronym(acronym: str) -> dict[str, Any] | None:
    """Devolve o significado de uma sigla registrada no glossario, ou null."""
    return read_tool.resolve_acronym(project(), acronym)


@mcp.tool()
def get_precedence(topic: str | None = None) -> list[dict[str, Any]]:
    """Lista as regras de precedencia entre fontes, opcionalmente filtradas por topico."""
    return read_tool.get_precedence(project(), topic)


@mcp.tool()
def list_competency_questions(status: str | None = None) -> list[dict[str, Any]]:
    """Lista as competency questions; filtra por status (proposed, approved, reserved...) se informado."""
    return read_tool.list_competency_questions(project(), status)


@mcp.tool()
def get_requirements() -> dict[str, Any]:
    """Devolve os requisitos: ORSD, pedido de dados e status do portao."""
    return read_tool.get_requirements(project())


@mcp.tool()
def search_registry(query: str, limit: int = 10) -> dict[str, Any]:
    """Busca termos reutilizaveis na LOV (Linked Open Vocabularies). Precisa de rede; degrada com available=false."""
    return read_tool.search_registry(query, limit)


@mcp.tool()
def propose_edit(type: str, payload: dict[str, Any], rationale: str = "", proposed_by: str = "agent",
                 requirement_id: str | None = None, evidence: str = "") -> dict[str, Any]:
    """Grava uma edicao tipada em ontology/pending/ sem alterar a ontologia. Tipos da etapa 1 (requisitos):
    add_use_case, add_competency_question, update_competency_question, remove_competency_question, add_gap,
    update_gap, add_divergence, update_divergence, add_requirement, add_glossary. Tipos da etapa 2 (ontologia,
    bloqueados ate os requisitos fecharem): add_class, add_relation, add_term, add_mapping, add_constraint, add_precedence."""
    return write_tool.propose_edit(project(), type, payload, rationale, proposed_by, requirement_id, evidence).model_dump(mode="json")


@mcp.tool()
def list_pending() -> list[dict[str, Any]]:
    """Lista as edicoes pendentes de aprovacao humana."""
    return [e.model_dump(mode="json") for e in write_tool.list_pending(project())]


@mcp.tool()
def review_edit(edit_id: str, decision: str, reviewer: str, edits: dict[str, Any] | None = None,
                reason: str = "") -> dict[str, Any]:
    """Grava a revisao humana (accept ou reject) no pendente, sem aplicar. reject exige reason; edits muda campos do payload."""
    return write_tool.review_edit(project(), edit_id, decision, reviewer, edits, reason).model_dump(mode="json")


@mcp.tool()
def apply_edit(edit_id: str = "", approved_by: str = "", edit_ids: list[str] | None = None) -> dict[str, Any]:
    """Aplica uma edicao pendente (edit_id) ou um lote transacional (edit_ids, com validate). Exige o nome de quem
    aprovou; chame somente apos aprovacao explicita do humano."""
    return write_tool.apply_edit(project(), edit_id or None, approved_by, edit_ids)


@mcp.tool()
def apply_reviewed(approved_by: str) -> dict[str, Any]:
    """Aplica em lote todos os pendentes revisados e devolve o resumo. Mostre o resumo e espere o "aplica" do humano antes."""
    return write_tool.apply_reviewed(project(), approved_by)


@mcp.tool()
def requirements_status() -> dict[str, Any]:
    """Diz se os requisitos da etapa 1 estao fechados, o que falta e se o portao da ontologia esta ativo."""
    return requirements_tool.requirements_status(project())


@mcp.tool()
def reject_edit(edit_id: str, rejected_by: str, reason: str = "") -> dict[str, Any]:
    """Descarta uma edicao pendente e registra o motivo no changelog."""
    return write_tool.reject_edit(project(), edit_id, rejected_by, reason)


@mcp.tool()
def validate(oops: bool = False) -> dict[str, Any]:
    """Valida TTL, classes referenciadas, mappings contra o profile, precedencia, cobertura e pitfalls. oops=true chama o OOPS! remoto."""
    return validate_tool.validate(project(), oops).model_dump()


@mcp.tool()
def publish(target: str = "yaml", dry_run: bool = True, release: str | None = None) -> dict[str, Any]:
    """Gera a camada semantica para yaml, snowflake, databricks ou rdf. dry_run=false executa no alvo e exige aprovacao humana."""
    return publish_tool.publish(project(), target, dry_run, release)


@mcp.tool()
def evaluate() -> dict[str, Any]:
    """Roda os testes estruturais de validation/questions.yml contra a ontologia. A comparacao com e sem ontologia usa a CLI com --callable."""
    return eval_tool.evaluate(project())


@mcp.tool()
def export() -> dict[str, Any]:
    """Gera docs/ontology.json, docs/ontology.js, docs/ontology.mmd e ontology/mappings.yarrrml.yml."""
    return export_tool.export(project())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
