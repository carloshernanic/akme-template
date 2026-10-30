# Revisão de requisitos: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a etapa 1 do AKME produzir caso de uso, um lote de CQs com tipo, conceitos e evidência, lacunas e divergências, revisados pelo humano numa página local do projeto, aplicados em lote após "aplica" no chat, e fechar um portão antes de qualquer classe entrar na ontologia.

**Architecture:** Fonte da verdade continua em `ontology/content.yml` e `ontology/pending/`; a decisão do humano é um bloco `review` dentro do pendente. Um módulo novo `akme/tools/requirements.py` calcula ids, portão, referências e espelhamento; `akme/tools/batch.py` aplica lotes numa cópia temporária, valida e só então promove. `akme/review_server.py` (biblioteca padrão) serve `docs/` e uma API JSON; `docs/review.js` desenha a aba Revisão dentro de `docs/index.html`.

**Tech Stack:** Python 3.11, pydantic 2, rdflib, pyyaml, typer, `http.server`; HTML e JS sem build; pytest.

**Spec:** `docs/superpowers/specs/2026-10-30-revisao-de-requisitos-design.md`

## Global Constraints

- Sem dependência nova em `pyproject.toml`; servidor com `http.server`, só `127.0.0.1`.
- Nenhuma escrita em `content.yml` ou `schema.ttl` fora de `apply_edit`, `apply_reviewed` e `apply_batch`; `propose_edit`, `review_edit` e a API só tocam `ontology/pending/`.
- Vocabulários fixos (copiar literalmente): tipos de CQ `classificacao_hierarquia`, `relacao_entre_conceitos`, `atributos`, `quantidade_agregacao`, `tempo_estado`, `regras_restricoes`; status de CQ `proposed`, `approved`, `reserved`, `rejected`, `deprecated`; decisão de lacuna `request_from_client`, `reformulate`, `drop`, `open`; decisão de divergência `precedence`, `distinct_terms`, `ask_expert`, `dismiss`, `open`; evidência `kind` em `source`, `conversation`; prioridade `high`, `medium`, `low`.
- Ids: `CQ-nnn`, `UC-nn`, `L-nn`, `D-nn`, sequenciais, considerando aplicados e pendentes.
- Mensagens e textos de interface em português sem acentos nos identificadores, como o resto do repositório.
- Commits sem linha de co-autoria. Mensagens no padrão do repositório (`feat:`, `test:`, `docs:`).
- `akme demo`, `akme seed` e a fixture `seeded` continuam funcionando ao fim de cada tarefa.

## Review Focus

1. Revisar um pendente que já foi aplicado ou apagado: `review_edit` e `POST /api/review` devolvem erro claro (`EditError` e HTTP 404), nunca criam arquivo novo. Teste em Tarefa 5 e Tarefa 7.
2. Revisor vazio: `review_edit` recusa e `POST /api/review` responde 400; nada é gravado. Teste em Tarefa 5 e Tarefa 7.
3. Duas CQs criadas sem id na mesma rodada (uma pela IA pendente, outra pelo humano na página) não colidem: `next_id` conta pendentes. Teste em Tarefa 2.
4. CQ que deixa de ser `reserved` por `update_competency_question` sai de `questions.yml`, e os `expects` das outras entradas permanecem. Teste em Tarefa 3.
5. Lote com erro pré-existente (mapping quebrado da etapa 3) ainda aplica as CQs; lote que introduz erro novo não grava nada. Teste em Tarefa 5.

---

### Tarefa 1: Esquema, constantes e modelo de revisão

**Files:**
- Modify: `akme/models.py:10-40`
- Modify: `akme/ontology.py:13-21`
- Modify: `ontology/content.yml`
- Test: `tests/test_models_schema.py`

**Interfaces:**
- Produces: `EditType` com membros novos `add_use_case`, `update_competency_question`, `remove_competency_question`, `add_gap`, `add_divergence`, `update_gap`, `update_divergence`; tuplas `CQ_TYPES`, `CQ_STATUSES`, `PRIORITIES`, `GAP_DECISIONS`, `DIVERGENCE_DECISIONS`, `EVIDENCE_KINDS`; `STAGE1_TYPES: frozenset[EditType]` (os sete novos mais `add_competency_question`, `add_requirement`, `add_glossary`); `ONTOLOGY_TYPES: frozenset[EditType]` (`add_class`, `add_relation`, `add_term`, `add_mapping`, `add_constraint`, `add_precedence`); `class Review(BaseModel)` com `decision: Literal["accept", "reject"]`, `reviewer: str`, `reviewed_at: str`, `edits: dict[str, Any] = {}`, `reason: str = ""`; `Edit.review: Review | None = None`; `REQUIRED_FIELDS` com `add_use_case: ["name", "description"]`, `update_competency_question: ["id"]`, `remove_competency_question: ["id", "reason"]`, `add_gap: ["question", "reason", "missing", "evidence"]`, `add_divergence: ["topic", "sources"]`, `update_gap: ["id", "decision"]`, `update_divergence: ["id", "decision"]`; `add_competency_question` **continua** `["id", "question"]` nesta tarefa (muda na Tarefa 3, junto com a demo); `EMPTY_CONTENT["requirements"]` com `use_cases: []`, `no_use_case: ""`, `gaps: []`, `divergences: []`.

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_models_schema.py
from akme.models import (CQ_STATUSES, CQ_TYPES, DIVERGENCE_DECISIONS, GAP_DECISIONS, ONTOLOGY_TYPES,
                         REQUIRED_FIELDS, STAGE1_TYPES, Edit, EditType, Review)
from akme.ontology import load_content

def test_new_edit_types_and_vocabularies():
    assert EditType("add_gap") in STAGE1_TYPES and EditType.add_class in ONTOLOGY_TYPES
    assert REQUIRED_FIELDS[EditType.add_gap] == ["question", "reason", "missing", "evidence"]
    assert "dismiss" in DIVERGENCE_DECISIONS and "request_from_client" in GAP_DECISIONS
    assert CQ_TYPES[0] == "classificacao_hierarquia" and "reserved" in CQ_STATUSES

def test_edit_carries_optional_review():
    e = Edit(id="x", type=EditType.add_gap, payload={})
    assert e.review is None
    e2 = Edit(id="x", type=EditType.add_gap, payload={}, review=Review(decision="reject", reviewer="ana", reviewed_at="2026-10-30T00:00:00+00:00", reason="duplicada"))
    assert e2.model_dump(mode="json")["review"]["reason"] == "duplicada"

def test_empty_content_has_requirement_sections(project):
    req = load_content(project)["requirements"]
    assert req["use_cases"] == [] and req["gaps"] == [] and req["divergences"] == [] and req["no_use_case"] == ""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_models_schema.py -v`
Expected: FAIL com `ImportError` (`CQ_STATUSES`).

- [ ] **Step 3: Implementar em `akme/models.py` e `akme/ontology.py`; atualizar comentários de exemplo em `ontology/content.yml` com as seções `use_cases`, `gaps`, `divergences` e uma CQ completa (campos da tabela 4.2 da spec)**

- [ ] **Step 4: Rodar tudo**

Run: `uv run pytest -q`
Expected: tudo passa (nada ainda usa os tipos novos).

- [ ] **Step 5: Commit**

```bash
git add akme/models.py akme/ontology.py ontology/content.yml tests/test_models_schema.py
git commit -m "feat: esquema de caso de uso, lacunas, divergencias e bloco de revisao"
```

---

### Tarefa 2: Módulo `requirements`: ids, referências, espelhamento, portão

**Files:**
- Create: `akme/tools/requirements.py`
- Test: `tests/test_requirements.py`

**Interfaces:**
- Consumes: `load_content`, `load_graph`, `classes` de `akme/ontology.py`; `read_yaml`, `write_yaml` de `akme/project.py`; `list_pending` de `akme/tools/ontology_write.py` (import dentro da função, para evitar ciclo).
- Produces:
  - `next_id(project: Project, prefix: str) -> str`: `prefix` em `CQ`, `UC`, `L`, `D`; três dígitos para `CQ`, dois para os demais; maior número entre a lista correspondente em `content.yml` e os payloads pendentes do mesmo tipo, mais um.
  - `domain_class_count(project: Project) -> int`: classes do `schema.ttl` fora de `Entity`, `Relation`, `Rule`, `Metric`.
  - `requirements_status(project: Project) -> dict`: `{"closed": bool, "missing": list[str], "ontology_empty": bool, "gate_active": bool}`; `missing` com uma frase por condição falha da seção 4.9 da spec (cinco condições); `gate_active = ontology_empty and not closed`.
  - `cq_references(project: Project, cq_id: str) -> dict`: `{"changelog": list[str]` (edit_ids com `requirement_id == cq_id`, excluindo a própria `add_competency_question`), `"evidence": list[str]`, `"in_questions": bool}`.
  - `mirror_reserved(project: Project) -> None`: mescla `validation/questions.yml` por id: cria ou atualiza `question` e `answer` das CQs `reserved`, preserva outros campos (`expects`), remove entradas cujo id existe em `content.yml` com status diferente de `reserved`, mantém entradas sem CQ.
  - `data_request(project: Project) -> list[dict]`: lacunas com `decision == "request_from_client"`, campos `id`, `question`, `missing`, `use_cases`.

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_requirements.py
from akme.ontology import load_content, save_content
from akme.project import read_yaml, write_yaml
from akme.tools import ontology_write, requirements as rq

def _cq(id, status, answer=None, **k):
    d = {"id": id, "question": f"q {id}", "type": "atributos", "concepts": ["X"], "status": status,
         "priority": "high", "evidence": [{"kind": "source", "path": "a.md", "locator": "pagina 1", "quote": "x"}]}
    if answer: d["answer"] = answer
    return d | k

def test_next_id_counts_applied_and_pending(project):
    c = load_content(project); c["requirements"]["competency_questions"].append(_cq("CQ-004", "approved")); save_content(project, c)
    assert rq.next_id(project, "CQ") == "CQ-005"
    ontology_write.propose_edit(project, "add_competency_question", _cq("CQ-007", "proposed"))
    assert rq.next_id(project, "CQ") == "CQ-008"
    assert rq.next_id(project, "UC") == "UC-01" and rq.next_id(project, "L") == "L-01"

def test_status_lists_every_missing_condition_on_empty_project(project):
    s = rq.requirements_status(project)
    assert s["closed"] is False and s["ontology_empty"] is True and s["gate_active"] is True
    assert len(s["missing"]) == 3  # caso de uso, nenhuma CQ approved, purpose/scope; pendentes e abertas so entram quando ha itens

def test_status_closes_with_use_case_approved_cq_purpose_scope(project):
    c = load_content(project); r = c["requirements"]
    r["use_cases"].append({"id": "UC-01", "name": "n", "description": "d"}); r["purpose"] = "p"; r["scope"] = "s"
    r["competency_questions"].append(_cq("CQ-001", "approved")); save_content(project, c)
    assert rq.requirements_status(project)["closed"] is True
    r["gaps"].append({"id": "L-01", "question": "q", "reason": "r", "missing": "m", "decision": "open"}); save_content(project, c)
    s = rq.requirements_status(project); assert s["closed"] is False and any("L-01" in m for m in s["missing"])

def test_mirror_reserved_merges_and_preserves_expects(project):
    write_yaml(project.questions_path, {"questions": [{"id": "CQ-002", "question": "old", "expects": ["Cliente type Class"]}, {"id": "ZZ", "question": "orfa"}]})
    c = load_content(project); c["requirements"]["competency_questions"] += [_cq("CQ-002", "reserved", "financeiro"), _cq("CQ-003", "reserved", "categoria"), _cq("CQ-001", "approved")]; save_content(project, c)
    rq.mirror_reserved(project)
    q = {x["id"]: x for x in read_yaml(project.questions_path)["questions"]}
    assert q["CQ-002"]["expects"] == ["Cliente type Class"] and q["CQ-002"]["question"] == "q CQ-002" and q["CQ-002"]["answer"] == "financeiro"
    assert "CQ-003" in q and "ZZ" in q and "CQ-001" not in q

def test_cq_references_and_data_request(seeded, project):
    assert rq.cq_references(seeded, "CQ-001")["changelog"]  # classes e termos do seed apontam para CQ-001
    assert rq.cq_references(project, "CQ-999") == {"changelog": [], "evidence": [], "in_questions": False}
    assert rq.data_request(project) == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_requirements.py -v`
Expected: FAIL com `ModuleNotFoundError: akme.tools.requirements`.

- [ ] **Step 3: Implementar `akme/tools/requirements.py` com as seis funções da seção Interfaces**

Frases de `missing`, literalmente: `"sem caso de uso (ou motivo em requirements.no_use_case)"`, `"CQs ainda em proposed: <ids>"`, `"pendentes da etapa 1 sem revisao: <ids>"`, `"nenhuma CQ approved"`, `"lacunas ou divergencias em open: <ids>"`, `"purpose ou scope vazios"`. As condições de pendentes e de abertas só entram quando há itens.

- [ ] **Step 4: Rodar**

Run: `uv run pytest tests/test_requirements.py -v`
Expected: PASS (`propose_edit` de CQ com `id` explícito já funciona com os campos atuais).

- [ ] **Step 5: Commit**

```bash
git add akme/tools/requirements.py tests/test_requirements.py
git commit -m "feat: ids sequenciais, portao de requisitos, referencias e espelhamento de reservadas"
```

---

### Tarefa 3: Novos tipos de edição no `propose_edit` e no `apply_edit`, e demo com CQs completas

**Files:**
- Modify: `akme/models.py` (`REQUIRED_FIELDS[add_competency_question] = ["question", "type", "concepts", "evidence"]`)
- Modify: `akme/tools/ontology_write.py:21-47` (propose) e `:69-113` (apply)
- Modify: `examples/local_demo/seed_edits.yml`, `examples/local_demo/questions.yml`
- Modify: `tests/test_export_eval_publish.py:27-42` (contagens do eval), `tests/test_validate.py` (se propõe CQ só com `id` e `question`)
- Test: `tests/test_ontology_write.py` (acrescentar)

**Interfaces:**
- Consumes: Tarefa 1 e Tarefa 2.
- Demo (`seed_edits.yml`), nesta ordem: `add_use_case` (`id: UC-01`, `name: Carteira e faturamento`, `description`, `actors: [analista comercial]`, `flow`); `add_requirement` purpose, scope, users (já existem); CQs com `type`, `concepts`, `evidence` (`kind: source`, `path` relativo a `examples/local_demo`, `locator`, `quote`), `priority`, `status`: `CQ-001` `approved`, `high`, `quantidade_agregacao`; `CQ-002` `reserved`, `medium`, `tempo_estado`, `answer: financeiro`; `CQ-003` `reserved`, `low`, `quantidade_agregacao`, `answer: categoria`; `add_gap` `L-01` (`question: Quais pedidos foram entregues com atraso?`, `reason: nao ha data de entrega`, `missing: data de entrega por pedido`, `decision: request_from_client`); `add_divergence` `D-01` (`topic: cliente ativo`, fontes `glossario.md` e `clientes.csv` coluna `fl_ativo`, `decision: precedence`, `winner: financeiro`, `reason`); depois as classes, relações, termos, mappings, constraint, glossário e precedência como hoje. `questions.yml` da demo fica só com `CQ-002` e `CQ-003`, mantendo os `expects` atuais.
- Produces: `propose_edit` passa a validar, além de `REQUIRED_FIELDS`: para `add_competency_question`, `type in CQ_TYPES`, `concepts` lista não vazia, `evidence` lista com itens `{kind, ...}` e, quando `proposed_by == "agent"`, ao menos um `kind == "source"`; `status` ausente vira `proposed`; `id` ausente vira `next_id`. Para `add_use_case` e `add_gap`, `id` ausente vira `next_id`; `add_gap.decision` default `open` e validado em `GAP_DECISIONS`. Para `add_divergence`, `sources` com dois ou mais itens, `decision` default `open` em `DIVERGENCE_DECISIONS`. Para `update_*` e `remove_*`, o `id` precisa existir na lista correspondente. `apply_edit` ganha ramos: `add_use_case` → `requirements.use_cases`; `add_competency_question` grava a CQ inteira (campos da tabela 4.2) e chama `mirror_reserved`; `update_competency_question` mescla campos enviados, grava no changelog `before` e `after` por campo, re-espelha; `remove_competency_question` apaga se `cq_references` vazio, senão marca `status: deprecated` e `deprecation_reason`; em ambos re-espelha; `add_gap`, `add_divergence` → listas; `update_gap`, `update_divergence` mesclam e gravam `decided_by = approved_by`, `decided_at = now_iso()`.

- [ ] **Step 1: Escrever os testes**

```python
def test_cq_requires_type_concepts_and_source_evidence(project):
    base = {"question": "q", "type": "atributos", "concepts": ["X"]}
    with pytest.raises(EditError, match="exige os campos"):
        ontology_write.propose_edit(project, "add_competency_question", base)
    with pytest.raises(EditError, match="source"):
        ontology_write.propose_edit(project, "add_competency_question", base | {"evidence": [{"kind": "conversation", "who": "ana", "when": "x"}]}, proposed_by="agent")
    e = ontology_write.propose_edit(project, "add_competency_question", base | {"evidence": [{"kind": "conversation", "who": "ana", "when": "x"}]}, proposed_by="ana")
    assert e.payload["id"] == "CQ-001" and e.payload["status"] == "proposed"

def test_update_and_remove_cq(seeded):
    u = ontology_write.propose_edit(seeded, "update_competency_question", {"id": "CQ-002", "status": "approved", "priority": "low"})
    ontology_write.apply_edit(seeded, u.id, "ana")
    cq = next(c for c in load_content(seeded)["requirements"]["competency_questions"] if c["id"] == "CQ-002")
    assert cq["status"] == "approved" and cq["priority"] == "low"
    questions = {q["id"]: q for q in read_yaml(seeded.questions_path)["questions"]}
    assert "CQ-002" not in questions and questions["CQ-003"]["expects"]  # saiu a que deixou de ser reservada; expects da outra ficam
    entry = read_yaml(seeded.changelog_path)["entries"][-1]; assert entry["before"]["status"] == "reserved" and entry["after"]["status"] == "approved"
    r = ontology_write.propose_edit(seeded, "remove_competency_question", {"id": "CQ-002", "reason": "duplicada"})
    ontology_write.apply_edit(seeded, r.id, "ana")
    cq = next(c for c in load_content(seeded)["requirements"]["competency_questions"] if c["id"] == "CQ-002")
    assert cq["status"] == "deprecated"  # CQ-002 e referenciada por classes do seed

def test_remove_orphan_cq_deletes(project):
    e = ontology_write.propose_edit(project, "add_competency_question", {"question": "q", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]}, proposed_by="ana")
    ontology_write.apply_edit(project, e.id, "ana")
    r = ontology_write.propose_edit(project, "remove_competency_question", {"id": "CQ-001", "reason": "erro"})
    ontology_write.apply_edit(project, r.id, "ana")
    assert load_content(project)["requirements"]["competency_questions"] == []

def test_gap_and_divergence_lifecycle(project):
    g = ontology_write.propose_edit(project, "add_gap", {"question": "q", "reason": "r", "missing": "m", "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]})
    ontology_write.apply_edit(project, g.id, "ana")
    with pytest.raises(EditError, match="sources"):
        ontology_write.propose_edit(project, "add_divergence", {"topic": "t", "sources": [{"label": "A", "path": "a", "locator": "1", "quote": "x"}]})
    d = ontology_write.propose_edit(project, "add_divergence", {"topic": "t", "sources": [{"label": "A", "path": "a", "locator": "1", "quote": "x"}, {"label": "B", "path": "b", "locator": "2", "quote": "y"}]})
    ontology_write.apply_edit(project, d.id, "ana")
    u = ontology_write.propose_edit(project, "update_divergence", {"id": "D-01", "decision": "precedence", "winner": "A", "reason": "normativo"})
    ontology_write.apply_edit(project, u.id, "ana")
    req = load_content(project)["requirements"]
    assert req["gaps"][0]["id"] == "L-01" and req["gaps"][0]["decision"] == "open"
    assert req["divergences"][0]["decision"] == "precedence" and req["divergences"][0]["decided_by"] == "ana"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_ontology_write.py -v`
Expected: FAIL nas asserções novas.

- [ ] **Step 3: Implementar os ramos em `propose_edit` e `apply_edit`, mudar `REQUIRED_FIELDS` da CQ e reescrever o seed e o `questions.yml` da demo conforme Interfaces**

Separe a validação por tipo numa função `_validate_payload(project, edit_type, payload, proposed_by) -> dict` que devolve o payload normalizado (ids e defaults preenchidos), chamada por `propose_edit` antes de gravar.

- [ ] **Step 4: Ajustar testes existentes afetados e rodar tudo**

`test_structural_eval`: 2 perguntas, ambas `pass`. `test_eval_with_callable`: recalcule `with_correct` e `without_correct` com a função de resposta do teste sobre `CQ-002` e `CQ-003`. Qualquer teste que proponha CQ só com `id` e `question` passa a enviar `type`, `concepts` e `evidence`.

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add akme/models.py akme/tools/ontology_write.py examples/local_demo tests
git commit -m "feat: edicoes de caso de uso, CQ completa, lacuna e divergencia; demo com requisitos completos"
```

---

### Tarefa 4: Portão da etapa 1

**Files:**
- Modify: `akme/tools/ontology_write.py` (`propose_edit`)
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: `requirements_status` (Tarefa 2), `ONTOLOGY_TYPES` (Tarefa 1), demo da Tarefa 3 (que já fecha os requisitos antes da primeira classe).
- Produces: `propose_edit` levanta `EditError("requisitos nao fechados: " + "; ".join(missing))` quando `edit_type in ONTOLOGY_TYPES` e `requirements_status(project)["gate_active"]`.

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_gate.py
import pytest
from akme.tools import ontology_write, requirements as rq
from akme.tools.ontology_write import EditError

def test_gate_blocks_classes_until_requirements_closed(project):
    with pytest.raises(EditError, match="requisitos nao fechados"):
        ontology_write.propose_edit(project, "add_class", {"name": "Cliente", "label": "Cliente", "comment": "c"})
    for t, p in [("add_use_case", {"name": "n", "description": "d"}),
                 ("add_requirement", {"field": "purpose", "value": "p"}), ("add_requirement", {"field": "scope", "value": "s"}),
                 ("add_competency_question", {"question": "q", "type": "atributos", "concepts": ["X"], "status": "approved", "priority": "high",
                                              "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]})]:
        e = ontology_write.propose_edit(project, t, p, proposed_by="ana"); ontology_write.apply_edit(project, e.id, "ana")
    assert rq.requirements_status(project)["closed"] is True
    ontology_write.propose_edit(project, "add_class", {"name": "Cliente", "label": "Cliente", "comment": "c"})

def test_gate_inactive_once_ontology_has_domain_classes(seeded):
    e = ontology_write.propose_edit(seeded, "add_competency_question", {"question": "nova", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]}, proposed_by="ana")
    assert rq.requirements_status(seeded)["closed"] is False and rq.requirements_status(seeded)["gate_active"] is False
    ontology_write.propose_edit(seeded, "add_class", {"name": "Transportadora", "label": "Transportadora", "comment": "c"})

def test_demo_seed_closes_gate_before_first_class(seeded):
    from akme.project import read_yaml
    entries = read_yaml(seeded.changelog_path)["entries"]
    first_class = next(i for i, e in enumerate(entries) if e["type"] == "add_class")
    types_before = {e["type"] for e in entries[:first_class]}
    assert {"add_use_case", "add_competency_question", "add_gap", "add_divergence"} <= types_before
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_gate.py -v`
Expected: FAIL (`propose_edit` aceita `add_class` com requisitos abertos).

- [ ] **Step 3: Implementar o portão em `propose_edit`**

- [ ] **Step 4: Rodar tudo e a demo**

Run: `uv run pytest -q && rm -rf /tmp/akme-demo && mkdir /tmp/akme-demo && cp -r . /tmp/akme-demo/ && cd /tmp/akme-demo && uv run akme init --demo && uv run akme demo | tail -3`
Expected: testes PASS; demo termina em "abra docs/index.html para ver o grafo".

- [ ] **Step 5: Commit**

```bash
git add akme/tools/ontology_write.py tests/test_gate.py
git commit -m "feat: portao da etapa 1 antes da primeira classe"
```

---

### Tarefa 5: Revisão, aplicação em lote transacional e tools MCP

**Files:**
- Create: `akme/tools/batch.py`
- Modify: `akme/tools/ontology_write.py` (`review_edit`, `apply_edit` com `edit_ids`, `apply_reviewed`)
- Modify: `akme/server.py:102-126`
- Test: `tests/test_review.py`

**Interfaces:**
- Consumes: `Review` (Tarefa 1), `validate` de `akme/tools/validate.py`.
- Produces:
  - `review_edit(project: Project, edit_id: str, decision: str, reviewer: str, edits: dict | None = None, reason: str = "") -> Edit`: grava `review` no pendente; `EditError` se pendente não existe, se `reviewer` vazio, se `decision == "reject"` sem `reason`, ou se `edits` tem chave fora do payload permitido do tipo.
  - `apply_edit(project, edit_id: str | None = None, approved_by: str = "", edit_ids: list[str] | None = None) -> dict`: com `edit_id`, comportamento atual acrescido de: se o pendente tem `review`, mescla `review.edits` no payload e, para `add_competency_question` com `decision == "reject"`, grava a CQ com `status: rejected`, `rejection_reason`, `reviewed_by`, `reviewed_at`; para CQ aceita grava `reviewed_by`, `reviewed_at`; para lacuna e divergência aceitas grava `decided_by = reviewer`. Com `edit_ids`, delega a `apply_batch`.
  - `apply_reviewed(project: Project, approved_by: str) -> dict`: ids de todos os pendentes com `review`, em ordem de `created_at`, via `apply_batch`.
  - `akme/tools/batch.py`: `class BatchError(EditError)` com atributo `new_errors: list[dict]`; `stage(project: Project) -> Project` (copia `ontology_dir`, `questions_path` e `profile_path` para um diretório temporário e devolve um `Project` cujo `akme.yml` aponta para essas cópias com caminhos absolutos); `apply_batch(project: Project, edit_ids: list[str], approved_by: str) -> dict` com `{"applied": [entry...], "rejected": [entry...], "preexisting_errors": [finding...], "summary": {"cqs_accepted", "cqs_rejected", "cqs_edited", "cqs_created_by_human", "gaps", "divergences"}}` (`cqs_edited` conta as aceitas cujo `review.edits` altera `question`, `type`, `concepts` ou `answer`; `cqs_created_by_human` as de `proposed_by != "agent"`; `gaps` e `divergences` são dicionários decisão → contagem); erros novos (findings `error` presentes depois e ausentes antes, comparados por `(check, subject, message)`) levantam `BatchError` sem promover; `promote(staging: Project, project: Project) -> None` substitui `ontology_dir` e `questions_path` do projeto pelos da cópia e roda `validate(project)` para atualizar `docs/validation.json`.
  - Tools MCP em `akme/server.py`: `review_edit(edit_id, decision, reviewer, edits: dict | None = None, reason: str = "")`, `apply_reviewed(approved_by: str)`, `requirements_status()`; `apply_edit(edit_id: str = "", approved_by: str = "", edit_ids: list[str] | None = None)`.

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_review.py
import pytest
from akme.ontology import load_content, save_content
from akme.tools import ontology_write
from akme.tools.batch import BatchError
from akme.tools.ontology_write import EditError

CQ = {"question": "q", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]}

def test_review_requires_reviewer_reason_and_existing_pending(project):
    e = ontology_write.propose_edit(project, "add_competency_question", CQ)
    with pytest.raises(EditError, match="reviewer"): ontology_write.review_edit(project, e.id, "accept", "")
    with pytest.raises(EditError, match="reason"): ontology_write.review_edit(project, e.id, "reject", "ana")
    with pytest.raises(EditError, match="nao encontrada"): ontology_write.review_edit(project, "add_gap-deadbeef", "accept", "ana")
    r = ontology_write.review_edit(project, e.id, "accept", "ana", edits={"question": "editada", "priority": "high", "status": "approved"})
    assert r.review.reviewer == "ana" and ontology_write.list_pending(project)[0].review.edits["question"] == "editada"

def test_apply_reviewed_merges_edits_and_records_rejections(project):
    a = ontology_write.propose_edit(project, "add_competency_question", CQ)
    b = ontology_write.propose_edit(project, "add_competency_question", CQ | {"question": "outra"})
    c = ontology_write.propose_edit(project, "add_competency_question", CQ | {"question": "sem revisao"})
    ontology_write.review_edit(project, a.id, "accept", "ana", edits={"priority": "high", "status": "approved", "question": "editada"})
    ontology_write.review_edit(project, b.id, "reject", "ana", reason="fora do caso de uso")
    out = ontology_write.apply_reviewed(project, "ana")
    cqs = {x["id"]: x for x in load_content(project)["requirements"]["competency_questions"]}
    assert cqs[a.payload["id"]]["question"] == "editada" and cqs[a.payload["id"]]["reviewed_by"] == "ana"
    assert cqs[b.payload["id"]]["status"] == "rejected" and cqs[b.payload["id"]]["rejection_reason"] == "fora do caso de uso"
    assert out["summary"]["cqs_accepted"] == 1 and out["summary"]["cqs_rejected"] == 1 and out["summary"]["cqs_edited"] == 1
    assert [e.id for e in ontology_write.list_pending(project)] == [c.id]

def test_batch_aborts_on_new_error_and_tolerates_preexisting(seeded):
    content = load_content(seeded); content["mappings"][0]["column"] = "nao_existe"; save_content(seeded, content)  # erro pre-existente
    from akme.tools.profile import profile; profile(seeded)
    ok = ontology_write.propose_edit(seeded, "add_competency_question", CQ); ontology_write.review_edit(seeded, ok.id, "accept", "ana", edits={"priority": "low", "status": "approved"})
    out = ontology_write.apply_reviewed(seeded, "ana")
    assert out["summary"]["cqs_accepted"] == 1 and any(f["check"] == "mapping_column" for f in out["preexisting_errors"])
    bad = ontology_write.propose_edit(seeded, "add_competency_question", CQ | {"question": "reservada sem resposta"}); ontology_write.review_edit(seeded, bad.id, "accept", "ana", edits={"priority": "low", "status": "reserved"})
    before = seeded.content_path.read_text(encoding="utf-8")
    with pytest.raises(BatchError) as exc: ontology_write.apply_reviewed(seeded, "ana")
    assert exc.value.new_errors and seeded.content_path.read_text(encoding="utf-8") == before
    assert [e.id for e in ontology_write.list_pending(seeded)] == [bad.id]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_review.py -v`
Expected: FAIL com `AttributeError: review_edit`.

- [ ] **Step 3: Implementar `review_edit`, `apply_edit` com `edit_ids`, `apply_reviewed` em `ontology_write.py` e `akme/tools/batch.py`; registrar as tools em `akme/server.py`**

`stage` escreve um `akme.yml` temporário com `project`, `adapter`, as opções do adapter, `ontology_dir`, `questions` e `docs_dir` absolutos; `tempfile.mkdtemp(prefix="akme-batch-")`, removido ao fim de `apply_batch` (sucesso ou erro). O teste de erro novo depende da checagem "reserved sem answer" da Tarefa 6; implemente essa checagem aqui, em `validate.py`, como parte desta tarefa.

- [ ] **Step 4: Rodar tudo**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add akme/tools/batch.py akme/tools/ontology_write.py akme/tools/validate.py akme/server.py tests/test_review.py
git commit -m "feat: bloco de revisao no pendente, aplicacao em lote transacional e tools MCP"
```

---

### Tarefa 6: `validate`, leitura, `export` e `publish` cientes dos requisitos

**Files:**
- Modify: `akme/tools/validate.py:81-86` e `validate()`
- Modify: `akme/tools/ontology_read.py:61-66`
- Modify: `akme/tools/export.py:11-40`
- Modify: `akme/tools/publish.py:36` (sem mudança de lógica; confirmar filtro `approved`)
- Modify: `akme/server.py` (`list_competency_questions(status: str | None = None)`)
- Test: `tests/test_validate.py`, `tests/test_export_eval_publish.py`

**Interfaces:**
- Produces: findings novos em `validate`: `error cq_reserved_without_answer`, `error cq_approved_without_priority`, `error cq_agent_without_source_evidence`, `warning no_reserved_cq` ("nenhuma CQ reserved: eval nao testa pelo resultado"), `warning open_gap_or_divergence` (um por item `open`), `question_without_requirement` passa a disparar também quando o id existe mas o status não é `reserved`. `list_competency_questions(project, status: str | None = None)`. `get_requirements` devolve também `data_request` e `status` (saída de `requirements_status`). `build_export` inclui `pending` (lista de `Edit.model_dump(mode="json")`) e `requirements_status`.

- [ ] **Step 1: Escrever os testes**

```python
def test_validate_requirement_rules(project):
    c = load_content(project); r = c["requirements"]
    r["competency_questions"] += [{"id": "CQ-001", "question": "q", "type": "atributos", "concepts": ["X"], "status": "reserved", "priority": "high", "proposed_by": "agent",
                                   "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]},
                                  {"id": "CQ-002", "question": "q", "type": "atributos", "concepts": ["X"], "status": "approved", "proposed_by": "ana",
                                   "evidence": [{"kind": "conversation", "who": "a", "when": "b"}]}]
    r["gaps"].append({"id": "L-01", "question": "q", "reason": "r", "missing": "m", "decision": "open"}); save_content(project, c)
    checks = {(f.level, f.check) for f in validate(project).findings}
    assert {("error", "cq_reserved_without_answer"), ("error", "cq_approved_without_priority"), ("error", "cq_agent_without_source_evidence"), ("warning", "open_gap_or_divergence")} <= checks

def test_validate_warns_without_reserved(seeded):
    c = load_content(seeded)
    for cq in c["requirements"]["competency_questions"]: cq["status"] = "approved"
    save_content(seeded, c)
    assert any(f.check == "no_reserved_cq" for f in validate(seeded).findings)

def test_read_and_export_expose_requirements(seeded):
    assert {c["status"] for c in ontology_read.list_competency_questions(seeded, status="reserved")} == {"reserved"}
    req = ontology_read.get_requirements(seeded); assert req["status"]["closed"] is True and req["data_request"][0]["id"] == "L-01"
    data = export_tool.build_export(seeded); assert "pending" in data and data["requirements_status"]["closed"] is True
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_validate.py tests/test_export_eval_publish.py -v`
Expected: FAIL nas asserções novas.

- [ ] **Step 3: Implementar**

- [ ] **Step 4: Rodar tudo**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add akme/tools/validate.py akme/tools/ontology_read.py akme/tools/export.py akme/server.py tests
git commit -m "feat: validate, leitura e export cientes de CQs, lacunas, divergencias e portao"
```

---

### Tarefa 7: Servidor local `akme review`

**Files:**
- Create: `akme/review_server.py`
- Modify: `akme/cli.py` (comando `review`)
- Test: `tests/test_review_server.py`

**Interfaces:**
- Consumes: `list_pending`, `review_edit`, `propose_edit` (Tarefas 3 e 5); `requirements_status`, `get_requirements`; `find_in_sources` de `akme/tools/connect.py`.
- Produces:
  - `make_handler(project: Project) -> type[http.server.BaseHTTPRequestHandler]`.
  - `start(project: Project, port: int = 8765) -> http.server.ThreadingHTTPServer` (bind `127.0.0.1`; `port=0` escolhe livre; `server.server_address[1]` dá a porta).
  - `serve(project: Project, port: int = 8765, open_browser: bool = True) -> None` (bloqueia; `webbrowser.open` quando `open_browser`).
  - Rotas: `GET /` e arquivos de `docs_dir` (`Content-Type` por extensão; `..` recusado com 403); `GET /api/status` → `requirements_status`; `GET /api/pending` → lista de pendentes (`Edit.model_dump(mode="json")`), e para `update_competency_question` e `remove_competency_question` cada item ganha `references` com `cq_references(project, payload["id"])` e `current` com a CQ atual de `content.yml`; `GET /api/requirements` → `get_requirements`; `GET /api/sources?q=&case_sensitive=` → `find_in_sources`; `POST /api/review` com JSON `{edit_id, decision, reviewer, edits?, reason?}` → 200 com o pendente, 400 em `EditError` cuja mensagem contém `reviewer`, `reason` ou `decision`, 404 em "nao encontrada"; `POST /api/propose` com `{type, payload, reviewer}` → `propose_edit(..., proposed_by=reviewer)` seguido de `review_edit(accept)`, 400 em `EditError`; `type` restrito a `add_competency_question`, `update_competency_question`, `remove_competency_question`, `update_gap`, `update_divergence`, `add_use_case`, `add_requirement`; qualquer outro, 400.
  - CLI: `akme review --port 8765 --no-open` chama `serve`.

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_review_server.py
import json, threading, urllib.request, urllib.error
import pytest
from akme import review_server
from akme.tools import ontology_write

@pytest.fixture
def server(seeded):
    srv = review_server.start(seeded, port=0); t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", seeded
    srv.shutdown()

def _get(url): return json.loads(urllib.request.urlopen(url).read())
def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp: return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")

def test_status_pending_and_static(server):
    base, project = server
    assert _get(base + "/api/status")["closed"] is True
    assert urllib.request.urlopen(base + "/").status == 200
    assert urllib.request.urlopen(base + "/api/pending").status == 200
    with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(base + "/../akme.yml")
    assert e.value.code in (403, 404)

def test_review_and_propose_endpoints(server):
    base, project = server
    e = ontology_write.propose_edit(project, "add_competency_question", {"question": "q", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "source", "path": "a", "locator": "1", "quote": "x"}]})
    assert _post(base + "/api/review", {"edit_id": e.id, "decision": "accept", "reviewer": "", "edits": {}})[0] == 400
    assert _post(base + "/api/review", {"edit_id": "add_gap-deadbeef", "decision": "accept", "reviewer": "ana"})[0] == 404
    assert _post(base + "/api/review", {"edit_id": e.id, "decision": "accept", "reviewer": "ana", "edits": {"priority": "high", "status": "approved"}})[0] == 200
    assert ontology_write.list_pending(project)[0].review.reviewer == "ana"
    assert _post(base + "/api/propose", {"type": "add_class", "payload": {}, "reviewer": "ana"})[0] == 400
    code, _ = _post(base + "/api/propose", {"type": "add_competency_question", "reviewer": "ana", "payload": {"question": "minha", "type": "atributos", "concepts": ["X"], "evidence": [{"kind": "conversation", "who": "ana", "when": "hoje"}], "priority": "low", "status": "approved"}})
    assert code == 200 and any(p.proposed_by == "ana" and p.review and p.review.decision == "accept" for p in ontology_write.list_pending(project))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_review_server.py -v`
Expected: FAIL com `ModuleNotFoundError: akme.review_server`.

- [ ] **Step 3: Implementar `akme/review_server.py` e o comando em `akme/cli.py`**

- [ ] **Step 4: Rodar tudo e subir manualmente**

Run: `uv run pytest -q && (cd /tmp/akme-demo && timeout 5 uv run akme review --no-open --port 8777; true)`
Expected: testes PASS; o servidor sobe e sai pelo timeout sem traceback.

- [ ] **Step 5: Commit**

```bash
git add akme/review_server.py akme/cli.py tests/test_review_server.py
git commit -m "feat: servidor local akme review com API de pendentes e revisao"
```

---

### Tarefa 8: Aba Revisão em `docs/index.html` e `docs/review.js`

**Files:**
- Modify: `docs/index.html:270-330` (cabeçalho e `main`), bloco `<style>`, e `load()`/inicialização
- Create: `docs/review.js`
- Test: `tests/test_docs_page.py` (presença e contrato), verificação manual

**Interfaces:**
- Consumes: `DATA.requirements_status`, `DATA.pending`, `DATA.requirements` do `ontology.js` (Tarefa 6); API da Tarefa 7.
- Produces: em `index.html`, uma barra `<nav class="tabs" id="tabs">` no cabeçalho com `button#tab-ontologia` e `button#tab-revisao`; o conteúdo atual (`#stats`, `.workspace`, `#summary`) envolto em `<div id="view-ontologia">`; `<section id="view-revisao" hidden>`; `<div id="gate-banner" hidden>` acima das views; `<script src="review.js">` antes do script inline. `review.js` define `window.AkmeReview = { init(data, api) }`, onde `api` é `null` (modo leitura, página aberta como arquivo) ou um objeto `{ get(path), post(path, body) }` criado pelo `index.html` quando `fetch("/api/status")` responde 200. Comportamento: se `data.requirements_status.closed === false`, `#tab-ontologia` fica oculto, `#view-revisao` ativo e `#gate-banner` mostra "Requisitos abertos. Falta: " seguido de `missing` em lista; quando `closed`, abre em `#view-ontologia`. Em `#view-revisao`: campo `input#reviewer` (persistido em `localStorage` sob `akme-reviewer`, em try/catch), barra lateral com contagens por grupo (CQs, Lacunas, Divergências, Caso de uso, Fontes), cartões conforme a seção 4.6 da spec e o mockup `tela-revisao-v2.html`; em modo leitura, controles desabilitados e aviso "abra com akme review para editar"; "Salvar decisões" envia um `POST /api/review` por cartão alterado e um `POST /api/propose` por cartão novo, com `reviewer` obrigatório (botão desabilitado sem nome), depois recarrega `/api/pending`; CQs aplicadas (de `data.requirements.competency_questions`) em cartões de leitura com "propor alteração" (abre os campos; ao salvar, `POST /api/propose` com `update_competency_question`, só campos alterados) e "propor exclusão" (pede motivo; `POST /api/propose` com `remove_competency_question`); pendentes de `update_*` mostram diff campo a campo (`current` contra payload, ambos vindos de `/api/pending`); pendentes de `remove_*` mostram `references` e avisam "vai virar deprecated" quando há alguma; lacunas e divergências já aplicadas aparecem em cartões de leitura com "propor alteração" da `decision` (`POST /api/propose` com `update_gap` ou `update_divergence`), sem botão de exclusão. Cores só por tokens já definidos no `<style>` do `index.html`; texto `var(--text-primary)`.

- [ ] **Step 1: Escrever o teste de contrato**

```python
# tests/test_docs_page.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_index_has_tabs_and_loads_review_js():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    for needle in ('id="tab-ontologia"', 'id="tab-revisao"', 'id="view-revisao"', 'id="gate-banner"', 'src="review.js"'):
        assert needle in html, needle
    js = (ROOT / "docs" / "review.js").read_text(encoding="utf-8")
    assert "window.AkmeReview" in js and "/api/review" in js and "/api/propose" in js and "akme-reviewer" in js
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_docs_page.py -v`
Expected: FAIL (`review.js` não existe).

- [ ] **Step 3: Implementar `docs/review.js` e as mudanças em `docs/index.html`**

- [ ] **Step 4: Verificar manualmente nos dois modos**

Run: `cd /tmp/akme-demo && uv run akme export && open docs/index.html` e depois `uv run akme review --port 8777`.
Expected: como arquivo, página abre na aba Ontologia (demo tem requisitos fechados), aba Revisão em modo leitura com aviso; pelo servidor, aba Revisão editável; propor uma CQ nova com revisor "teste" cria arquivo em `examples/local_demo/ontology/pending/` com `review.decision: accept`; "propor alteração" em CQ-001 cria pendente `update_competency_question` com diff visível; com o `pending/` contendo uma CQ `proposed` sem revisão, `/api/status` segue `closed: true` (ontologia já tem classes, portão inativo) e o banner não aparece. Para ver o banner: `uv run akme init` num diretório vazio, `uv run akme export`, abrir `docs/index.html`: só a aba Revisão, banner com a lista do que falta. Anote o resultado no commit.

- [ ] **Step 5: Commit**

```bash
git add docs/index.html docs/review.js tests/test_docs_page.py
git commit -m "feat: aba Revisao com cartoes de CQ, lacuna e divergencia e portao visual"
```

---

### Tarefa 9: `SKILL.md`, `manifest.yml`, template e README

**Files:**
- Modify: `SKILL.md` (seção "Fluxo em seis etapas", etapas 1 e 2; "Regras que nunca mudam", regra 7; "Como apresentar ambiguidades")
- Modify: `ontology/manifest.yml` (tools `ontology_read`, `ontology_write`, nova `requirements`, nova `review`)
- Modify: `README.md` (comando `akme review`, resumo do fluxo da etapa 1)
- Test: `tests/test_skill_text.py`

**Interfaces:**
- Produces: etapa 1 reescrita com os sete passos da seção 4.7 da spec; etapa 2 começa com "chame `requirements_status`; se `closed` for falso, volte à etapa 1 e mostre `missing`"; regra nova: "Toda CQ, lacuna e divergência proposta carrega `evidence` com `kind: source` citando `path`, `locator` e `quote`; o que vem de conversa leva `kind: conversation`"; seção "Como apresentar ambiguidades" passa a dizer que divergências viram `add_divergence` e lacunas `add_gap`, apresentadas na aba Revisão, e que o chat mostra só a lista curta; a instrução de encerramento da etapa 1: "resuma as decisões lidas em `list_pending` e peça 'aplica' com o nome; só então `apply_reviewed`"; a distribuição das dez CQs pelos seis tipos; o texto para quando não há reservada ("o eval não testará pelo resultado; a etapa 4 fica só com verificação formal"). `manifest.yml`: entradas para `requirements` (`requirements_status`, `data_request`) e `review` (`review_edit`, `apply_reviewed`, `akme review`), com `requires_approval: true` para `apply_reviewed`.

- [ ] **Step 1: Escrever o teste**

```python
# tests/test_skill_text.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_skill_and_manifest_describe_review_flow():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for needle in ("requirements_status", "apply_reviewed", "akme review", "add_gap", "add_divergence", "add_use_case", "dez CQs", "kind: source"):
        assert needle in skill, needle
    manifest = (ROOT / "ontology" / "manifest.yml").read_text(encoding="utf-8")
    assert "apply_reviewed" in manifest and "requirements_status" in manifest
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_skill_text.py -v`
Expected: FAIL.

- [ ] **Step 3: Reescrever os trechos de `SKILL.md`, `manifest.yml` e `README.md`**

Mantenha o restante do `SKILL.md` intacto. Não acrescente etapas além das seis.

- [ ] **Step 4: Rodar tudo**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md ontology/manifest.yml README.md tests/test_skill_text.py
git commit -m "docs: etapa 1 com caso de uso, lote de CQs, revisao local e portao"
```

---

## Verificação final

- [ ] `uv run pytest -q` passa.
- [ ] Em diretório limpo: `uv run akme init --demo && uv run akme demo && uv run akme validate && uv run akme eval && uv run akme export`; `validate` sem erro; `eval` com duas perguntas `pass`.
- [ ] `uv run akme review --no-open` sobe; `curl -s localhost:8765/api/status` devolve `closed: true` na demo.
- [ ] Em projeto vazio (`akme init`), `propose_edit add_class` pelo MCP devolve "requisitos nao fechados" com a lista.
- [ ] `git log --oneline` mostra um commit por tarefa, sem linha de co-autoria.
