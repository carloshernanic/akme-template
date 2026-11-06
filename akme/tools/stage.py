"""Em que etapa das seis (LOT) o projeto esta, o que falta para fechar a atual e o proximo passo.

E uma leitura heuristica do estado em disco, feita para orientar o humano na pagina e o agente
no chat. Nao substitui o portao de requisitos (`requirements_status`), que continua sendo a regra.
"""
from __future__ import annotations

from typing import Any

from ..models import EDIT_STAGE, EditType
from ..ontology import load_content
from ..project import Project, read_yaml

STAGES = [
    (1, "Especificar", "Caso de uso, perguntas de competência, lacunas e divergências"),
    (2, "Conceitualizar", "Classes, relações e termos a partir das CQs aprovadas"),
    (3, "Codificar", "Mappings para tabela e coluna, restrições e precedências"),
    (4, "Avaliar", "Validate e eval; correções voltam como novas propostas"),
    (5, "Publicar", "Export da página e publish em dry-run no alvo"),
    (6, "Manter", "Mudanças começam por uma CQ nova e passam pela mesma revisão"),
]


def _pending_by_stage(project: Project) -> dict[int, int]:
    from .ontology_write import list_pending
    out = {n: 0 for n, _, _ in STAGES}
    for e in list_pending(project):
        out[EDIT_STAGE.get(e.type, 1)] += 1
    return out


def current_stage(project: Project) -> dict[str, Any]:
    from .requirements import domain_class_count, requirements_status
    from .ontology_write import list_pending

    content = load_content(project)
    status = requirements_status(project)
    pending = list_pending(project)
    by_stage = _pending_by_stage(project)
    classes = domain_class_count(project)
    terms, mappings = len(content["terms"]), len(content["mappings"])
    validation = read_yaml(project.validation_path) if project.validation_path.exists() else {}
    errors = [f for f in validation.get("findings", []) if f.get("level") == "error"]
    validated = bool(validation) and project.validation_path.stat().st_mtime >= project.content_path.stat().st_mtime
    published = (project.docs_dir / "publish").exists() and any((project.docs_dir / "publish").iterdir())
    undecided = [e for e in pending if e.review is None]

    missing: list[str] = []
    if not status["closed"]:
        number = 1
        missing = list(status["missing"])
        next_step = ("Decida os pendentes da etapa 1 e aplique." if undecided
                     else "No chat, peça ao agente o que falta para fechar os requisitos.")
    elif classes == 0 or terms == 0 or by_stage[2]:
        number = 2
        if by_stage[2]:
            missing.append(f"{by_stage[2]} propostas de classe, relação ou termo aguardando decisão ou aplicação")
        if classes == 0:
            missing.append("nenhuma classe de domínio aplicada")
        if terms == 0:
            missing.append("nenhum termo aplicado")
        next_step = ("Decida as propostas e aplique." if by_stage[2]
                     else "No chat, peça ao agente as classes, relações e termos a partir das CQs aprovadas.")
    elif mappings == 0 or by_stage[3]:
        number = 3
        if by_stage[3]:
            missing.append(f"{by_stage[3]} propostas de mapping, restrição ou precedência aguardando decisão ou aplicação")
        if mappings == 0:
            missing.append("nenhum mapping aplicado")
        next_step = ("Decida as propostas e aplique." if by_stage[3]
                     else "No chat, peça ao agente os mappings de cada termo para tabela e coluna.")
    elif not validated or errors:
        number = 4
        if not validated:
            missing.append("validate ainda não rodou sobre a versão atual")
        if errors:
            missing.append(f"{len(errors)} erros no último validate")
        next_step = "No chat, peça ao agente para rodar validate e eval e propor as correções."
    elif not published:
        number = 5
        missing.append("nenhum artefato em docs/publish/")
        next_step = "No chat, peça o publish em dry-run para o alvo do cliente."
    else:
        number = 6
        next_step = "Toda mudança começa por uma CQ nova ou uma alteração proposta na página."

    name = next(n for num, n, _ in STAGES if num == number)
    return {
        "number": number, "name": name, "total": len(STAGES),
        "label": f"Etapa {number} de {len(STAGES)}: {name}",
        "missing": missing, "next_step": next_step,
        "requirements_closed": status["closed"], "gate_active": status["gate_active"],
        "checklist": checklist(project, number),
        "pending_by_stage": by_stage, "undecided": len(undecided),
        "counts": {"classes": classes, "terms": terms, "mappings": mappings, "pending": len(pending)},
        "stages": [{"number": n, "name": name_, "description": d,
                    "status": "completed" if n < number else "active" if n == number else "incomplete"}
                   for n, name_, d in STAGES],
    }


def _step(text: str, done: bool | None, tools: str = "") -> dict[str, Any]:
    """Um passo do checklist. done=None quando so o agente sabe (ele marca na lista de tarefas)."""
    return {"text": text, "done": done, "tools": tools}


def checklist(project: Project, number: int) -> list[dict[str, Any]]:
    """Os passos da etapa `number` como no SKILL.md, marcados pelo que esta em disco."""
    from ..ontology import load_graph, relations
    from .ontology_write import list_pending
    from .requirements import domain_class_count, requirements_status

    content = load_content(project)
    r = content["requirements"]
    pending = list_pending(project)
    of_type = lambda *ts: [e for e in pending if e.type.value in ts]  # noqa: E731
    stage_pending = [e for e in pending if EDIT_STAGE.get(e.type, 1) == number]
    review_done = not stage_pending
    if number == 1:
        cqs = r["competency_questions"]
        return [
            _step("Caso de uso registrado (ou motivo de não ter)",
                  bool(r["use_cases"] or str(r.get("no_use_case") or "").strip() or of_type("add_use_case")),
                  "get_requirements, propose_edit add_use_case"),
            _step("Fontes perfiladas e documentos lidos", project.profile_path.exists(),
                  "profile, read_document, find_in_sources"),
            _step("Propósito, escopo e usuários propostos",
                  bool(str(r.get("purpose") or "").strip() and str(r.get("scope") or "").strip()) or bool(of_type("add_requirement")),
                  "propose_edit add_requirement"),
            _step("Dez CQs propostas, com evidência de fonte", len(cqs) + len(of_type("add_competency_question")) >= 10,
                  "propose_edit add_competency_question"),
            _step("Lacunas e divergências propostas", None, "propose_edit add_gap, add_divergence"),
            _step("Humano revisou e aplicou na página", review_done and bool(cqs), "open_review, wait_for_review"),
            _step("Glossário de siglas aplicado", bool(content["glossary"]) and not of_type("add_glossary"),
                  "propose_edit add_glossary"),
            _step("Requisitos fechados", requirements_status(project)["closed"], "requirements_status, stage"),
        ]
    if number == 2:
        rels = relations(load_graph(project.schema_path))
        return [
            _step("Requisitos fechados", requirements_status(project)["closed"], "requirements_status"),
            _step("Modelo atual lido", None, "list_entities, list_relations"),
            _step("Classes propostas a partir das CQs aprovadas",
                  domain_class_count(project) > 0 or bool(of_type("add_class")), "propose_edit add_class"),
            _step("Relações com multiplicidade e join", bool(rels) or bool(of_type("add_relation")),
                  "propose_edit add_relation"),
            _step("Termos ligados às classes (métricas com unidade, grão e aditividade)",
                  bool(content["terms"]) or bool(of_type("add_term")), "propose_edit add_term"),
            _step("Reuso consultado na LOV", None, "search_registry"),
            _step("Humano revisou e aplicou na página", review_done and domain_class_count(project) > 0, "open_review, wait_for_review"),
        ]
    if number == 3:
        mapped = {m.get("term") for m in content["mappings"]} | {e.payload.get("term") for e in of_type("add_mapping")}
        unmapped = [t.get("name") for t in content["terms"] if t.get("name") not in mapped]
        validation = read_yaml(project.validation_path) if project.validation_path.exists() else {}
        errors = [f for f in validation.get("findings", []) if f.get("level") == "error"]
        return [
            _step("Mapping proposto para cada termo" + (f" (faltam {len(unmapped)})" if unmapped else ""),
                  bool(content["terms"]) and not unmapped, "propose_edit add_mapping"),
            _step("Restrições e precedências achadas nos documentos", None, "propose_edit add_constraint, add_precedence"),
            _step("Validate sem erros", bool(validation) and not errors, "validate"),
            _step("Humano revisou e aplicou na página", review_done and bool(content["mappings"]), "open_review, wait_for_review"),
        ]
    if number == 4:
        validation = read_yaml(project.validation_path) if project.validation_path.exists() else {}
        fresh = bool(validation) and project.validation_path.stat().st_mtime >= project.content_path.stat().st_mtime
        errors = [f for f in validation.get("findings", []) if f.get("level") == "error"]
        return [
            _step("Validate na versão atual, sem erros", fresh and not errors, "validate"),
            _step("Eval estrutural rodado", None, "evaluate"),
            _step("Correções propostas como novas edições", None, "propose_edit"),
            _step("Humano decidiu: voltar à etapa 2 ou 3, ou publicar", None, ""),
        ]
    if number == 5:
        published = (project.docs_dir / "publish").exists() and any((project.docs_dir / "publish").iterdir())
        return [
            _step("Humano viu a aba Ontologia na página", None, "open_review"),
            _step("Publish em dry-run gerado", published, "publish"),
            _step("Versão definida (release)", None, "publish --release"),
            _step("Execução no alvo confirmada pelo humano na CLI", None, ""),
        ]
    return [
        _step("Mudança registrada (issue ou CQ nova)", None, "propose_edit add_competency_question"),
        _step("Pedido classificado: bug, requisito novo ou mudança na fonte", None, ""),
        _step("Impacto listado: CQs, termos, mappings e publicações", None, "validate, evaluate"),
        _step("Humano decidiu escopo e release", None, ""),
    ]


def stage_for(edit_type: EditType) -> int:
    return EDIT_STAGE.get(edit_type, 1)
