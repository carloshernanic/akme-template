"""Apresentacao legivel de uma edicao pendente para a pagina de revisao.

A pagina nao precisa conhecer os dezesseis tipos de edicao: cada pendente sai de `/api/pending`
com um bloco `view` (titulo, subtitulo, campos com rotulo em portugues, evidencia normalizada,
o que o dado mostra e o que o revisor pode editar). As decisoes continuam em `review_edit`.
"""
from __future__ import annotations

import json
from typing import Any

from ..models import EDIT_STAGE, Edit, EditType

GROUP = {
    EditType.add_competency_question: "cq", EditType.update_competency_question: "cq",
    EditType.remove_competency_question: "cq",
    EditType.add_gap: "gap", EditType.update_gap: "gap",
    EditType.add_divergence: "div", EditType.update_divergence: "div",
    EditType.add_use_case: "uc", EditType.add_requirement: "uc",
    EditType.add_glossary: "glossary",
    EditType.add_class: "class", EditType.add_relation: "relation", EditType.add_term: "term",
    EditType.add_mapping: "mapping", EditType.add_constraint: "constraint", EditType.add_precedence: "precedence",
    EditType.add_source: "source",
    EditType.update_mapping: "mapping", EditType.remove_mapping: "mapping", EditType.rename_class: "class",
}

GROUP_LABEL = {
    "cq": "Perguntas de competência", "gap": "Lacunas", "div": "Divergências", "uc": "Caso de uso e requisitos",
    "glossary": "Glossário", "class": "Classes", "relation": "Relações", "term": "Termos",
    "mapping": "Mappings", "constraint": "Restrições", "precedence": "Precedências", "source": "Exportação Neo4j",
}
TYPE_LABEL = {"string": "texto", "integer": "inteiro", "float": "decimal", "date": "data"}

MULTIPLICITY_LABEL = {
    "many_to_one": "muitos para um", "one_to_many": "um para muitos",
    "one_to_one": "um para um", "many_to_many": "muitos para muitos",
}
ADDITIVITY_LABEL = {"additive": "aditiva", "semi_additive": "semiaditiva", "non_additive": "não aditiva"}
ROLE_LABEL = {"dimension": "dimensão", "metric": "métrica", "key": "chave"}
SEVERITY_LABEL = {"error": "erro", "warning": "aviso"}
REQUIREMENT_FIELD_LABEL = {"purpose": "Propósito", "scope": "Escopo", "users": "Usuários", "no_use_case": "Sem caso de uso"}
CQ_TYPE_LABEL = {
    "classificacao_hierarquia": "Classificação e hierarquia", "relacao_entre_conceitos": "Relação entre conceitos",
    "atributos": "Atributos", "quantidade_agregacao": "Quantidade e agregação",
    "tempo_estado": "Tempo e estado", "regras_restricoes": "Regras e restrições",
}

_MAPPING_LABEL = {"term": "Termo", "source": "Tabela", "column": "Coluna", "role": "Papel",
                  "expression": "Expressão SQL", "note": "Nota"}


def _shown(value: Any) -> str:
    return "(vazio)" if value in (None, "") else str(value)


# campos que o revisor pode ajustar antes de aceitar, por tipo (rotulo e forma do campo)
EDITABLE: dict[EditType, list[dict[str, str]]] = {
    EditType.add_class: [{"key": "label", "label": "Rótulo", "kind": "text"}, {"key": "comment", "label": "Comentário", "kind": "textarea"}],
    EditType.add_relation: [{"key": "label", "label": "Rótulo", "kind": "text"}, {"key": "comment", "label": "Comentário", "kind": "textarea"}],
    EditType.add_term: [{"key": "definition", "label": "Definição", "kind": "textarea"}, {"key": "synonyms", "label": "Sinônimos (separados por vírgula)", "kind": "list"}],
    EditType.add_mapping: [{"key": "note", "label": "Nota", "kind": "textarea"}],
    EditType.add_constraint: [{"key": "rule", "label": "Regra", "kind": "textarea"}],
    EditType.add_precedence: [{"key": "reason", "label": "Motivo", "kind": "textarea"}],
    EditType.add_glossary: [{"key": "meaning", "label": "Significado", "kind": "text"}, {"key": "convention", "label": "Convenção", "kind": "text"}],
    EditType.add_requirement: [{"key": "value", "label": "Valor", "kind": "textarea"}],
    EditType.add_use_case: [{"key": "name", "label": "Nome", "kind": "text"}, {"key": "description", "label": "Descrição", "kind": "textarea"},
                            {"key": "actors", "label": "Atores (separados por vírgula)", "kind": "list"}],
    EditType.remove_mapping: [{"key": "reason", "label": "Motivo", "kind": "textarea"}],
    EditType.add_source: [{"key": "key", "label": "Chave (colunas separadas por vírgula)", "kind": "list"},
                          {"key": "types", "label": "Tipos (coluna: tipo, separados por vírgula)", "kind": "map"},
                          {"key": "caption", "label": "Legenda: coluna cujo valor aparece na bolinha do Neo4j (vazio = automática)", "kind": "text"}],
}

# tipos em que "rejeitar" nao existe: a decisao e sempre um aceite com escolha
NOT_REJECTABLE = {EditType.add_gap, EditType.add_divergence}


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(_s(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _field(label: str, value: Any, mono: bool = False) -> dict[str, Any] | None:
    text = _s(value)
    if not text.strip():
        return None
    return {"label": label, "value": text, "mono": mono}


def _fields(*items: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [i for i in items if i]


def _parse_evidence_text(raw: str) -> list[Any]:
    """O campo evidence do pendente e texto livre: pode ser uma nota, um objeto JSON, uma lista JSON
    ou varios objetos em sequencia separados por ';' ou ',' (como o agente costuma gravar).
    Objetos viram itens tipados; o que sobrar vira nota."""
    raw = raw.strip()
    if not raw:
        return []
    decoder = json.JSONDecoder()
    out: list[Any] = []
    pos, text = 0, ""
    while pos < len(raw):
        ch = raw[pos]
        if ch in "{[":
            try:
                obj, end = decoder.raw_decode(raw, pos)
            except ValueError:
                text += ch
                pos += 1
                continue
            out.extend(obj if isinstance(obj, list) else [obj])
            pos = end
            continue
        text += ch
        pos += 1
    note = text.strip(" ;,\n\t")
    if note:
        out.append({"kind": "note", "note": note})
    return out


def normalize_evidence(edit: Edit) -> list[dict[str, Any]]:
    """Evidencia do payload (lista tipada) ou do campo evidence do pendente (texto ou JSON de um item)."""
    items: list[Any] = []
    payload_ev = edit.payload.get("evidence")
    if isinstance(payload_ev, list):
        items.extend(payload_ev)
    items.extend(_parse_evidence_text(edit.evidence or ""))
    out = []
    for i in items:
        if not isinstance(i, dict):
            out.append({"kind": "note", "note": _s(i)})
            continue
        kind = i.get("kind") or ("source" if i.get("path") else "note")
        out.append({"kind": kind, "path": _s(i.get("path")), "locator": _s(i.get("locator")),
                    "quote": _s(i.get("quote")), "who": _s(i.get("who")), "when": _s(i.get("when")),
                    "note": _s(i.get("note"))})
    return out


def _join_text(p: dict[str, Any]) -> str:
    join = p.get("join")
    if isinstance(join, dict) and isinstance(join.get("from"), dict) and isinstance(join.get("to"), dict):
        f, t = join["from"], join["to"]
        return f"{f.get('source')}.{f.get('column')} → {t.get('source')}.{t.get('column')}"
    return ""


def _observed(p: dict[str, Any]) -> dict[str, Any] | None:
    o = p.get("observed")
    if not isinstance(o, dict):
        return None
    if not o.get("available"):
        return {"available": False, "reason": _s(o.get("reason")), "lines": [], "alerts": []}
    lines, alerts = [], []
    f, t = o.get("from") or {}, o.get("to") or {}
    lines.append(f"Multiplicidade observada: {MULTIPLICITY_LABEL.get(o.get('multiplicity'), o.get('multiplicity'))}")
    lines.append(f"Lado de origem: {f.get('rows', 0)} linhas, {f.get('distinct', 0)} chaves distintas, {f.get('nulls', 0)} nulos")
    lines.append(f"Lado de destino: {t.get('rows', 0)} linhas, {t.get('distinct', 0)} chaves distintas, {t.get('nulls', 0)} nulos")
    orphans = int(o.get("orphans") or 0)
    if orphans:
        ex = ", ".join(_s(x) for x in (o.get("orphan_examples") or [])[:5])
        lines.append(f"Órfãos: {orphans} chaves de origem sem par no destino" + (f" (ex.: {ex})" if ex else ""))
        alerts.append("há chaves de origem sem correspondência no destino")
    if o.get("fanout"):
        alerts.append("a junção repete linhas da origem (fanout): métricas da origem não podem ser somadas depois de juntar")
    declared = p.get("multiplicity")
    if declared and o.get("multiplicity") and declared != o.get("multiplicity"):
        alerts.append(f"declarada {MULTIPLICITY_LABEL.get(declared, declared)}, observada {MULTIPLICITY_LABEL.get(o['multiplicity'], o['multiplicity'])}")
    if o.get("truncated"):
        lines.append(f"Amostra de {o.get('sample')} linhas por lado; o dado pode ser maior")
    return {"available": True, "lines": lines, "alerts": alerts}


def _source_checked(p: dict[str, Any]) -> dict[str, Any] | None:
    c = p.get("checked")
    if p.get("exclude") or not isinstance(c, dict):
        return None
    lines = [f"{c.get('rows', 0)} linhas, chave sem vazios nem repetição"]
    for col, t in (c.get("types") or {}).items():
        lines.append(f"{col}: {t.get('converted')} de {t.get('filled')} valores convertem para {TYPE_LABEL.get(t.get('kind'), t.get('kind'))}"
                     + (f", ex. {t.get('example')}" if t.get("example") else ""))
    alerts = []
    cap = c.get("caption")
    if isinstance(cap, dict):
        if cap.get("column") and cap.get("alone"):
            origin = "decidida" if cap.get("decided") else "automática"
            lines.append(f"legenda ({origin}): coluna {cap['column']}, preenchida em {cap.get('filled')} de {cap.get('rows')} linhas; "
                         f"a bolinha mostra, por exemplo, \"{cap.get('example')}\"")
            if cap.get("rows") and cap.get("filled", 0) < 0.5 * cap["rows"]:
                alerts.append(f"a legenda {cap['column']} está vazia em {cap['rows'] - cap.get('filled', 0)} de {cap['rows']} linhas: "
                              "nessas, a bolinha mostra a classe e a chave")
        else:
            lines.append(f"legenda (automática): nenhuma coluna com cara de nome; a bolinha mostra a classe e a chave, por exemplo, "
                         f"\"{cap.get('example')}\". Para escolher uma coluna, use \"Ajustar\"")
    return {"available": True, "lines": lines, "alerts": alerts}


def present(edit: Edit, current: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bloco `view` de um pendente. `current` e o item aplicado que um update ou remove altera."""
    t, p = edit.type, dict(edit.payload)
    if edit.review and edit.review.edits:
        p |= edit.review.edits
    title, subtitle, fields = "", "", []
    if t == EditType.add_class:
        title, subtitle = f"Classe {p.get('name')}", f"subclasse de {p.get('subclass_of') or 'Entity'}"
        fields = _fields(_field("Rótulo", p.get("label")), _field("Comentário", p.get("comment")))
    elif t == EditType.add_relation:
        title, subtitle = f"Relação {p.get('name')}", f"{p.get('domain')} → {p.get('range')}"
        join = _join_text(p)
        fields = _fields(
            _field("Rótulo", p.get("label")), _field("Comentário", p.get("comment")),
            _field("Multiplicidade", MULTIPLICITY_LABEL.get(p.get("multiplicity"), p.get("multiplicity"))),
            _field("Inversa", p.get("inverse_of"), mono=True),
            _field("Junção", join, mono=True) if join else _field("Sem junção física", p.get("no_join_reason")),
            _field("Multiplicidade mantida apesar do dado", p.get("override_reason")),
        )
    elif t == EditType.add_term:
        title, subtitle = f"Termo {p.get('name')}", f"da classe {p.get('class')}"
        fields = _fields(
            _field("Definição", p.get("definition")), _field("Sinônimos", p.get("synonyms")),
            _field("Unidade", p.get("unit")), _field("Grão", p.get("grain")),
            _field("Aditividade", ADDITIVITY_LABEL.get(p.get("additivity"), p.get("additivity"))),
            _field("Não soma sobre", p.get("non_additive_over")),
        )
    elif t == EditType.add_mapping:
        title, subtitle = f"Mapping de {p.get('term')}", f"{p.get('source')}.{p.get('column')}"
        fields = _fields(
            _field("Papel", ROLE_LABEL.get(p.get("role"), p.get("role"))),
            _field("Expressão SQL", p.get("expression"), mono=True), _field("Nota", p.get("note")),
        )
    elif t == EditType.update_mapping:
        before, after = p.get("before") or p, p.get("after") or {}
        title, subtitle = f"Corrigir o mapping de {p.get('term')}", f"hoje em {p.get('source')}.{p.get('column')}"
        fields = _fields(*[_field(_MAPPING_LABEL[k], f"{_shown(before.get(k))} → {_shown(after.get(k))}", mono=k != "note")
                           for k in _MAPPING_LABEL if before.get(k) != after.get(k)])
    elif t == EditType.remove_mapping:
        title, subtitle = f"Remover o mapping de {p.get('term')}", f"{p.get('source')}.{p.get('column')}"
        fields = _fields(_field("Motivo", p.get("reason")))
    elif t == EditType.rename_class:
        title, subtitle = f"Renomear a classe {p.get('name')}", f"passa a se chamar {p.get('new_name')}"
        fields = _fields(_field("Rótulo novo", p.get("label")),
                         _field("O que muda", "o nome no schema.ttl e em tudo que cita a classe: termos, relações, perguntas e propostas pendentes"))
    elif t == EditType.add_constraint:
        title, subtitle = f"Restrição sobre {p.get('term')}", _s(p.get("id"))
        fields = _fields(_field("Regra", p.get("rule")), _field("Severidade", SEVERITY_LABEL.get(p.get("severity"), p.get("severity"))))
    elif t == EditType.add_precedence:
        title, subtitle = f"Precedência: {p.get('topic')}", f"{p.get('winner')} prevalece sobre {p.get('over')}"
        fields = _fields(_field("Motivo", p.get("reason")))
    elif t == EditType.add_glossary:
        title, subtitle = f"Sigla {p.get('acronym')}", _s(p.get("meaning"))
        fields = _fields(_field("Significado", p.get("meaning")), _field("Convenção", p.get("convention")))
    elif t == EditType.add_requirement:
        title, subtitle = f"Requisito: {REQUIREMENT_FIELD_LABEL.get(p.get('field'), p.get('field'))}", ""
        fields = _fields(_field("Valor", p.get("value")))
    elif t == EditType.add_use_case:
        title, subtitle = f"Caso de uso {p.get('id') or ''}".strip(), _s(p.get("name"))
        fields = _fields(_field("Descrição", p.get("description")), _field("Atores", p.get("actors")), _field("Fluxo", p.get("flow")))
    elif t == EditType.add_competency_question:
        title, subtitle = _s(p.get("question")), f"{p.get('id') or ''} · {CQ_TYPE_LABEL.get(p.get('type'), p.get('type') or '')}".strip(" ·")
        fields = _fields(_field("Conceitos", p.get("concepts")), _field("Casos de uso", p.get("use_cases")))
    elif t == EditType.update_competency_question:
        title, subtitle = _s((current or {}).get("question") or p.get("question") or p.get("id")), f"{p.get('id')} · alteração proposta"
        fields = [f for k, v in p.items() if k != "id" for f in [_field(k, v)] if f]
    elif t == EditType.remove_competency_question:
        title, subtitle = _s((current or {}).get("question") or p.get("id")), f"{p.get('id')} · exclusão proposta"
        fields = _fields(_field("Motivo", p.get("reason")))
    elif t in (EditType.add_gap, EditType.update_gap):
        title, subtitle = _s(p.get("question") or (current or {}).get("question") or p.get("id")), f"{p.get('id') or ''} · lacuna".strip(" ·")
        fields = _fields(_field("Motivo", p.get("reason")), _field("O que faltaria", p.get("missing")))
    elif t in (EditType.add_divergence, EditType.update_divergence):
        title, subtitle = _s(p.get("topic") or (current or {}).get("topic") or p.get("id")), f"{p.get('id') or ''} · divergência".strip(" ·")
        fields = _fields(_field("Hipótese da IA", p.get("hypothesis")))
    elif t == EditType.add_source:
        title = f"Tabela {p.get('source')}"
        if p.get("exclude"):
            subtitle = "fica fora do Neo4j"
            fields = _fields(_field("Motivo", p.get("exclude")))
        else:
            subtitle = f"vira nós {p.get('class')}" if p.get("class") else "vira nós no Neo4j"
            types = p.get("types") or {}
            fields = _fields(_field("Chave", p.get("key"), mono=True),
                             _field("Tipos", ", ".join(f"{c}: {k}" for c, k in types.items()) or "todas as colunas ficam texto", mono=True),
                             _field("Legenda", p.get("caption") or "automática", mono=bool(p.get("caption"))))
    observed = _observed(p) if t == EditType.add_relation else _source_checked(p) if t == EditType.add_source else None
    alerts = list(observed["alerts"]) if observed else []
    return {
        "title": title or edit.id, "subtitle": subtitle, "group": GROUP.get(t, "other"),
        "group_label": GROUP_LABEL.get(GROUP.get(t, "other"), "Outros"), "stage": EDIT_STAGE.get(t, 1),
        "fields": fields, "evidence": normalize_evidence(edit), "observed": observed, "alerts": alerts,
        "editable": EDITABLE.get(t, []), "rejectable": t not in NOT_REJECTABLE,
        "origin": "IA" if edit.proposed_by == "agent" else edit.proposed_by,
        "requirement_id": edit.requirement_id or "", "rationale": edit.rationale or "",
    }
