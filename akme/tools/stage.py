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
    elif not published or by_stage[5]:
        number = 5
        if by_stage[5]:
            missing.append(f"{by_stage[5]} decisões de exportação Neo4j (chave e tipos por tabela) aguardando decisão ou aplicação")
        if not published:
            missing.append("nenhum artefato em docs/publish/")
        next_step = ("Decida as tabelas na página e aplique." if by_stage[5]
                     else "No chat, peça o publish em dry-run para o alvo do cliente.")
    else:
        number = 6
        next_step = "Toda mudança começa por uma CQ nova ou uma alteração proposta na página."

    name = next(n for num, n, _ in STAGES if num == number)
    return {
        "number": number, "name": name, "total": len(STAGES),
        "label": f"Etapa {number} de {len(STAGES)}: {name}",
        "missing": missing, "next_step": next_step,
        "requirements_closed": status["closed"], "gate_active": status["gate_active"],
        "pending_by_stage": by_stage, "undecided": len(undecided),
        "counts": {"classes": classes, "terms": terms, "mappings": mappings, "pending": len(pending)},
        "stages": [{"number": n, "name": name_, "description": d,
                    "status": "completed" if n < number else "active" if n == number else "incomplete"}
                   for n, name_, d in STAGES],
    }


def stage_for(edit_type: EditType) -> int:
    return EDIT_STAGE.get(edit_type, 1)
