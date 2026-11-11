# Revisão da etapa 1 no formato v6: plano de implementação

> **Para agentes:** sub-skill obrigatória: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** trocar a revisão da etapa 1 da aba Revisão por três telas enxutas: caso de uso, perguntas, e lacunas e divergências. A última termina num único "Conferir e salvar", que grava e aplica com o nome de quem aprova.

**Arquitetura:** um arquivo novo, `akme/static/etapa1.js`, cuida das três telas, do modelo e do envio. O `review.js` ganha um seletor "Etapa 1 · Outras propostas (n)": a primeira opção monta o `AkmeEtapa1`, e a segunda mantém a caixa de entrada atual para as etapas 2 a 5 e para os pendentes da etapa 1 que as telas não cobrem (glossário e `update_*`/`remove_*` do agente). No backend entram três campos opcionais nas propostas (sinais da IA), e o SKILL passa a pedir esses campos e de 2 a 3 casos de uso.

**Stack:** Python 3.11 + pytest (backend e testes de texto); HTML/CSS/JS puro, sem build; verificação no navegador com Playwright, fora do repositório.

**Spec:** `docs/superpowers/specs/2026-11-10-revisao-etapa1-v6-design.md`. Referência visual: `docs/design/revisao/v6-prototipo.html`.

## Restrições globais

- Sem build e sem dependência nova; editar em `akme/static/` (`docs/` é cópia do `akme export`).
- Tokens QBDS de `akme.css` (`--rad: 0`, Inter/Roboto Mono, acento QB só em foco ou seleção), nos temas claro e escuro.
- Texto ao usuário em pt-BR, sem travessão; código e comentários em português sem acento.
- Toda escrita passa por `/api/review` e `/api/propose`; aplicar só com nome, via `/api/apply`.
- Commits em Conventional Commits, em português, **sem linha Co-Authored-By** (preferência do usuário).
- Nada vem pré-selecionado pela IA; a sugestão dela aparece só como dica.
- Cada tarefa termina com `uv run pytest -q` passando e parada para aprovação do usuário (preferência registrada).

## Foco da revisão

1. **Proposta antiga, sem os campos novos** (`data_check`, `depends_on`, `suggestion`): o card mostra a fonte da primeira evidência no lugar do sinal, sem erro. Teste na Tarefa 5.
2. **Falha no meio do "Conferir e salvar"** (um POST devolve 400): para no primeiro erro, mostra a mensagem no diálogo, não chama `/api/apply` e deixa tentar de novo. Teste na Tarefa 7.
3. **Nome só com espaços:** o diálogo não envia. Teste na Tarefa 7.
4. **Etapa 1 já fechada ou sem pendentes da etapa 1:** a aba abre em "Outras propostas", e a Etapa 1 mostra "Nada a decidir" nas telas vazias. Teste na Tarefa 3.
5. **Pergunta criada para um caso de uso escrito na mesma sessão:** o caso é proposto antes e o id devolvido entra em `use_cases` da pergunta. Teste na Tarefa 7.

---

### Tarefa 1: campos de sinal da IA nas propostas

**Arquivos:**
- Modificar: `akme/tools/ontology_write.py` (`_validate_payload`, ~L105-161)
- Testar: `tests/test_ontology_write.py`

**Interfaces:**
- Produz, em `add_competency_question.payload`:
  - `data_check: str` (opcional, não vazio quando presente);
  - `depends_on: list[str]` (opcional, cada item casa `^D-\d{2,}$`).
- Produz, em `add_divergence.payload`: `suggestion: {"winner": str, "reason": str}` (opcional). `winner` precisa ser o `label` de uma das `sources`, e `reason` não pode ser vazio.
- `priority` em CQ continua opcional e passa a significar "prioridade sugerida".

- [ ] **Passo 1: escrever os testes que falham**

```python
def test_cq_accepts_optional_ai_signals(project):
    base = {"question": "q", "type": "atributos", "concepts": ["X"],
            "evidence": [{"kind": "source", "path": "a.csv", "locator": "col", "quote": "x"}]}
    e = ontology_write.propose_edit(project, "add_competency_question",
                                    base | {"data_check": "sim, a.csv tem col", "depends_on": ["D-01"], "priority": "high"},
                                    proposed_by="agent")
    assert e.payload["data_check"].startswith("sim") and e.payload["depends_on"] == ["D-01"]
    with pytest.raises(EditError, match="depends_on"):
        ontology_write.propose_edit(project, "add_competency_question", base | {"depends_on": ["CQ-1"]}, proposed_by="agent")
    with pytest.raises(EditError, match="data_check"):
        ontology_write.propose_edit(project, "add_competency_question", base | {"data_check": "  "}, proposed_by="agent")

def test_divergence_suggestion_must_name_a_source(project):
    src = [{"label": "financeiro", "path": "g.md", "locator": "l17", "quote": "a"},
           {"label": "ERP", "path": "c.csv", "locator": "fl_ativo", "quote": "b"}]
    base = {"topic": "cliente ativo", "sources": src}
    e = ontology_write.propose_edit(project, "add_divergence", base | {"suggestion": {"winner": "financeiro", "reason": "glossário oficial"}})
    assert e.payload["suggestion"]["winner"] == "financeiro"
    with pytest.raises(EditError, match="suggestion"):
        ontology_write.propose_edit(project, "add_divergence", base | {"suggestion": {"winner": "CRM", "reason": "x"}})
```

- [ ] **Passo 2:** `uv run pytest tests/test_ontology_write.py -k "signals or suggestion" -q`. Esperado: FAIL, porque as propostas inválidas não levantam erro.
- [ ] **Passo 3:** em `_validate_payload`, nos ramos `add_competency_question` e `add_divergence`, validar os campos acima quando presentes. As mensagens de `EditError` precisam citar o nome do campo (`data_check`, `depends_on`, `suggestion`).
- [ ] **Passo 4:** `uv run pytest -q`. Esperado: tudo PASS.
- [ ] **Passo 5:** commit `feat(requisitos): sinais opcionais da IA em CQ e divergencia`.

---

### Tarefa 2: SKILL e manifesto pedem os sinais e 2 a 3 casos de uso

**Arquivos:**
- Modificar: `SKILL.md` (etapa 1, passos 1, 4, 5 e "Pare e pergunte"), `ontology/manifest.yml` se ele descrever a CQ
- Testar: `tests/test_skill_text.py`

**Interfaces:** consome os nomes de campo da Tarefa 1.

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_skill_asks_for_ai_signals_and_several_use_cases():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for needle in ("data_check", "depends_on", "suggestion", "dois a tres casos de uso"):
        assert needle in skill, needle
    assert "quais CQs sao usadas na construcao e quais ficam guardadas para o teste" not in skill
```

- [ ] **Passo 2:** `uv run pytest tests/test_skill_text.py -q`. Esperado: FAIL no teste novo.
- [ ] **Passo 3:** editar o SKILL:
  - Passo 1.1: proponha **dois a tres casos de uso** tirados das fontes (`add_use_case`), sem perguntar um. O humano escolhe na página ou escreve o dele, e "não temos caso de uso" vira `no_use_case`.
  - Passo 1.4: cada CQ leva também `priority` (sugerida), `data_check` (comece com "sim" quando os dados respondem; senão diga o que falta) e `depends_on` (ids das divergências cujo termo a pergunta usa).
  - Divergências levam `suggestion {winner, reason}` quando houver base.
  - "Pare e pergunte": troque a escolha construção/teste por "a página não pede essa escolha; toda CQ aceita lá vira approved. Para reservar uma CQ como teste, proponha com `status: reserved` e `answer`". Mantenha o aviso "o eval não testará pelo resultado".
  - Passo 5: "Conferir e salvar" grava e aplica a etapa 1 de uma vez; `wait_for_review` volta com `applied`.
- [ ] **Passo 4:** `uv run pytest -q`. Esperado: PASS, incluindo os testes antigos do SKILL ("dez CQs", "kind: source", "no_use_case").
- [ ] **Passo 5:** commit `docs(skill): agente propoe casos de uso e sinais da IA`.

---

### Tarefa 3: casca da Etapa 1 e seletor de modo

**Arquivos:**
- Criar: `akme/static/etapa1.js`
- Modificar:
  - `akme/static/index.html` (adicionar `<script src="etapa1.js"></script>` antes de `review.js`);
  - `akme/tools/export.py` (`PAGE_FILES` ganha `"etapa1.js"`);
  - `akme/static/review.js` (`S.mode`, seletor, montagem);
  - `akme/static/akme.css` (classes `.e1-*`).
- Testar: `tests/test_docs_page.py`

**Interfaces:**
- Produz `window.AkmeEtapa1 = { mount(el, ctx), pendingCount(data) }`:
  - `ctx = { data, api, reviewer: string, onDone(result), toast(html) }`;
  - `pendingCount(data) -> number` conta os pendentes da etapa 1 que as três telas cobrem: `add_use_case`, `add_requirement` com field purpose/scope/users/no_use_case, `add_competency_question`, `add_gap` e `add_divergence`.
- Interno, usado nas Tarefas 4 a 7: `buildModel(data) -> M`, em que `M = { step: 0|1|2, ucs[], reqs[], cqs[], gaps[], divs[], applied: {ucs, cqs, gaps, divs}, own: {ucs[], cqs[]} }`; mais `missing(M, step) -> string[]` e `render()`.
- No `review.js`:
  - `S.mode: "etapa1" | "outras"`;
  - no `init`, o modo é `"outras"` se `data.requirements.status.closed` ou se `pendingCount(data) === 0`, e `"etapa1"` nos outros casos;
  - um botão `data-act="mode"` com `data-value` alterna o modo;
  - "Outras propostas" filtra `S.order` para tirar os kinds que a Etapa 1 cobre.
- Stepper da Etapa 1: 3 passos ("Caso de uso", "Perguntas", "Lacunas e divergências"), com `aria-current="step"` no passo atual. Rodapé fixo com `#e1-msg` (`aria-live="polite"`), "← Voltar" e o botão de avançar.

- [ ] **Passo 1:** atualizar `tests/test_docs_page.py`:
  - `index.html` contém `src="etapa1.js"`, antes de `src="review.js"`;
  - `etapa1.js` contém `window.AkmeEtapa1`, `/api/apply` e `"requirements"`;
  - `review.js` contém `data-act="mode"`;
  - `test_export_copies_the_page_into_docs` inclui `etapa1.js`;
  - trocar a asserção `"Usar na construção"`/`"Guardar para o teste"` por `"Nada a decidir"` em `etapa1.js`.
- [ ] **Passo 2:** `uv run pytest tests/test_docs_page.py -q`. Esperado: FAIL.
- [ ] **Passo 3:** implementar a casca: as três telas vazias com título e "Nada a decidir", o stepper, o rodapé e a navegação livre pelo stepper, mais o seletor de modo. Ainda sem cards.
- [ ] **Passo 4:** `uv run pytest -q`. Esperado: PASS. Verificar no navegador:
  - rodar `uv run akme init --demo` numa cópia temporária do projeto e então `uv run akme review --port 8770 --no-open`;
  - com pendentes da etapa 1, a aba Revisão abre na Etapa 1;
  - o seletor alterna para "Outras propostas", que mostra a caixa de entrada atual sem os kinds cobertos;
  - com a etapa 1 fechada (demo aplicada), a aba abre em "Outras propostas".
- [ ] **Passo 5:** commit `feat(revisao): casca da etapa 1 em tres telas`.

---

### Tarefa 4: Tela 1 (caso de uso, propósito, escopo e usuários)

**Arquivos:** modificar `akme/static/etapa1.js` e `akme/static/akme.css`.

**Interfaces:**
- Itens do modelo:
  - `M.ucs[i] = { edit_id, name, description, actors, src, sel: false }`;
  - `M.applied.ucs` (já aprovados: contam para "ao menos um" e aparecem marcados como "já aprovado", sem toggle);
  - `M.own.ucs[] = { tmpId: "novo-1", name, description }`;
  - `M.noUseCase: string | null`;
  - `M.reqs[i] = { edit_id, field, value, edited: string|null, ok: bool }`.
- `missing(M, 0)` inclui:
  - "escolher pelo menos um caso de uso", quando não há marcado, aplicado, próprio completo nem `noUseCase`;
  - "completar o caso de uso escrito por você";
  - "aceitar <propósito|escopo|usuários>" para cada `reqs` não aceito.

- [ ] **Passo 1:** implementar a tela conforme o v6:
  - cards de caso de uso como `<button aria-pressed>`, sem nenhum marcado;
  - "+ Escrever o meu caso de uso" com nome e uma frase;
  - link "Não temos caso de uso", que pede uma frase;
  - propósito, escopo e usuários como cards enxutos com "✓ Aceitar" e "ajustar" (textarea com o valor; o valor ajustado vai em `edits.value`).
- [ ] **Passo 2:** verificar no navegador com a demo e com uma cópia de `examples/teste_acme`:
  - avançar fica bloqueado até escolher um caso;
  - o caso próprio pela metade não conta como escolhido;
  - "Não temos caso de uso" libera;
  - o foco volta ao controle clicado.
- [ ] **Passo 3:** `uv run pytest -q`. Esperado: PASS.
- [ ] **Passo 4:** commit `feat(revisao): tela de caso de uso da etapa 1`.

---

### Tarefa 5: Tela 2 (perguntas de competência)

**Arquivos:** modificar `akme/static/etapa1.js` e `akme/static/akme.css`.

**Interfaces:**
- `M.cqs[i]`:
  - `edit_id, id, question, type, concepts, use_cases[], evidence[]`;
  - `aiPrio` (vindo de `payload.priority`), `dataCheck`, `dependsOn[]`;
  - `dec: null|"ok"|"rej"`, `prio`, `why`, `reason`, `open`, `det`.
- `M.own.cqs[] = { tmpId, question, uc, type, concepts, prio, open }`. Valores de `uc`: o id de um caso aplicado ou pendente, ou o `tmpId` de um caso próprio.
- Constantes:
  - `WHY = [["clara","Pouco clara"],["escopo","Fora do caso de uso"],["dados","Os dados não respondem"],["repetida","Repetida"],["outro","Outro motivo"]]`;
  - `PRIO = [["high","Alta"],["medium","Média"],["low","Baixa"]]`.
- Escopo:
  - uma CQ pertence a um caso se algum id de `use_cases` está entre os casos marcados ou aplicados;
  - sem `use_cases`, ela vai para o grupo "Sem caso de uso";
  - fora disso, vai para "Fora dos casos escolhidos", que não pede decisão.
- `missing(M, 1)` só olha CQs no escopo e as próprias.

- [ ] **Passo 1:** implementar conforme o v6:
  - caixa "Criar pergunta" (Enter adiciona; campo vazio avisa);
  - card enxuto com a linha de sinal;
  - "ver detalhes" com id, tipo, conceitos, evidência e o aviso de `dependsOn`, que linka para a divergência na Tela 3;
  - ✓ Aceitar e ✕ Rejeitar;
  - prioridade com "A IA sugere X";
  - motivos em chips;
  - recolher em linha com "rever";
  - contador "N sugestões da IA para avaliar";
  - "Já aplicadas" em linhas com prioridade, `reviewed_by` e `reviewed_at`, mais a marca "teste" quando `status === "reserved"`. Ali, "ver detalhes" oferece "Propor alteração" e "Propor exclusão", que reaproveitam a lógica atual de `a-cq`.

  Linha de sinal:
  - `dependsOn[0]` → "● depende de “<tópico>” · ver D-xx";
  - `dataCheck` começando com "sim" → "● os dados respondem" (verde);
  - outro `dataCheck` → "● <dataCheck>" (amarelo);
  - sem os dois → "<path> · <locator>" da primeira evidência (Foco da revisão 1).
- [ ] **Passo 2:** verificar no navegador com `teste_acme`:
  - uma CQ sem `data_check` mostra a evidência no lugar do sinal;
  - aceitar e depois escolher a prioridade recolhe o card;
  - rejeitar e escolher um motivo recolhe o card;
  - "Outro motivo" pede texto;
  - "rever" reabre o card;
  - uma CQ fora dos casos escolhidos não conta em `missing`.
- [ ] **Passo 3:** `uv run pytest -q`. Esperado: PASS.
- [ ] **Passo 4:** commit `feat(revisao): tela de perguntas enxuta com criacao`.

---

### Tarefa 6: Tela 3 (lacunas e divergências)

**Arquivos:** modificar `akme/static/etapa1.js` e `akme/static/akme.css`.

**Interfaces:**
- `M.gaps[i] = { edit_id, id, question, reason, missing, evidence, dec, note, newq, open, det }`, com `dec` ∈ `request_from_client|reformulate|drop|open`.
- `M.divs[i] = { edit_id, id, topic, sources[], suggestion, affects[], dec, winner, reason, open, det, more }`:
  - `affects` = ids das CQs com `dependsOn` contendo este `id`;
  - `dec` ∈ `precedence|distinct_terms|ask_expert|dismiss|open`.
- Precisam de texto (`NEEDS`):
  - lacuna: `reformulate` (newq), `drop` (note), `open` (note);
  - divergência: `distinct_terms` (reason), `dismiss` (reason), `open` (reason).
- Lacunas e divergências aplicadas aparecem como linhas. "ver detalhes" oferece "Propor alteração", com a lógica atual de `a-gap`/`a-div`.

- [ ] **Passo 1:** implementar conforme o v6:
  - quatro botões na lacuna;
  - fontes como botões grandes (`precedence` + `winner` = `label`);
  - sinal "IA sugere <winner>" quando houver `suggestion`;
  - "afeta CQ-xx" com link;
  - "nenhuma das duas? outras opções" com São coisas diferentes, Perguntar ao especialista, Descartar e Deixar em aberto;
  - "Concluir" quando a escolha pede texto, e linha recolhida com "rever".
- [ ] **Passo 2:** verificar no navegador:
  - "Reformular" sem texto não conclui;
  - escolher uma fonte recolhe;
  - os links CQ↔D trocam de tela e destacam o card;
  - uma tela sem itens mostra "Nada a decidir" e conta como completa.
- [ ] **Passo 3:** `uv run pytest -q`. Esperado: PASS.
- [ ] **Passo 4:** commit `feat(revisao): tela de lacunas e divergencias enxuta`.

---

### Tarefa 7: "Conferir e salvar" grava e aplica

**Arquivos:**
- Modificar: `akme/static/etapa1.js` (diálogo, `buildOps`, `commit`) e `akme/static/index.html` (se o diálogo for novo; senão reaproveitar `#rv-dialog`)
- Testar: `tests/test_review_server.py`

**Interfaces:**
- `buildOps(M) -> Op[]`, em que `Op = { url: "/api/review"|"/api/propose", body, label }`. Ordem:
  1. Casos próprios: `/api/propose add_use_case {name, description}`. O id devolvido em `payload.id` substitui o `tmpId` nas CQs próprias.
  2. `noUseCase`: `/api/propose add_requirement {field:"no_use_case", value}`.
  3. Casos pendentes:
     - marcados: `review accept`;
     - não marcados: `review reject reason:"não escolhido pelo revisor"`.
  4. `reqs`: `review accept` (com `edits.value` se ajustado).
  5. CQs da IA no escopo:
     - aceita: `accept`, `edits {status:"approved", priority}`;
     - rejeitada: `reject`, `reason = rótulo do motivo + (": " + texto, se houver)`.
     - CQs fora do escopo: `reject reason:"fora dos casos escolhidos"`.
  6. CQs próprias: `/api/propose add_competency_question {question, type, concepts, priority, status:"approved", use_cases:[uc]}`.
  7. Lacunas: `accept`, `edits {decision, note}`; em `reformulate`, `note` = nova pergunta.
  8. Divergências: `accept`, `edits {decision, winner?, reason?}`.
- `commit(M, name) -> Promise<result>`:
  - envia as ops em sequência, com `reviewer = name`, e para no primeiro erro, devolvendo `{error, at: label}`;
  - sem erro, chama `POST /api/apply {approved_by: name, stage: "requirements"}`;
  - em seguida chama `ctx.onDone(result)`, que roda o `reload` atual e mostra o resumo do `apply`.
- O diálogo:
  - lista casos escolhidos, aceitas, rejeitadas com motivo, escritas por você, as rejeições automáticas (casos não escolhidos, perguntas fora do escopo) e cada lacuna e divergência;
  - tem o campo "Seu nome", pré-preenchido do `localStorage` `akme-reviewer` e salvo de volta ali;
  - não envia com nome vazio ou só com espaços.

- [ ] **Passo 1: escrever o teste de servidor que falha.** Ele reproduz a sequência da página e confere que a etapa fecha:

```python
def test_etapa1_page_sequence_closes_requirements(server):
    # server: fixture existente com projeto temporario e demo semeada so com pendentes da etapa 1
    # 1) propose add_use_case proprio -> id; 2) review accept/reject dos pendentes como em buildOps;
    # 3) propose add_competency_question com use_cases=[id do caso proprio]; 4) apply stage=requirements
    out = post(server, "/api/apply", {"approved_by": "Ana", "stage": "requirements"})
    assert out["summary"]["cqs_created_by_human"] == 1
    status = get(server, "/api/requirements")["status"]
    assert status["closed"] is True
```

  Se a fixture `server` não semear os pendentes da etapa 1, crie-os no teste com `ontology_write.propose_edit`, usando `examples/local_demo/seed_edits.yml` como modelo.
- [ ] **Passo 2:** `uv run pytest tests/test_review_server.py -k etapa1 -q`. Esperado: FAIL até a sequência estar escrita corretamente no teste. É um teste de contrato e não depende do JS; ele falha se a ordem ou o payload estiverem errados.
- [ ] **Passo 3:** implementar o diálogo, `buildOps` e `commit` no `etapa1.js`.
- [ ] **Passo 4:** `uv run pytest -q`. Esperado: PASS. Verificar no navegador com a demo:
  - fazer o fluxo completo e salvar; o resumo do apply aparece, a aba vai para "Outras propostas" e o stepper global avança para a etapa 2;
  - nome vazio não envia (Foco 3);
  - um caso próprio com uma pergunta ligada a ele grava os dois (Foco 5);
  - forçar 400 (por exemplo, apagar um pendente em `ontology/pending/` antes de salvar) para no erro e não aplica (Foco 2).
- [ ] **Passo 5:** commit `feat(revisao): conferir e salvar aplica a etapa 1`.

---

### Tarefa 8: fechamento

**Arquivos:**
- Modificar: `docs/guia-do-fluxo.md` (trecho da revisão da etapa 1) e `README.md`, se descreverem a tela antiga
- Rodar: `uv run akme export` numa cópia de teste (não commitar a saída de `docs/` gerada a partir de projeto local)

- [ ] **Passo 1:** atualizar o guia com as três telas, o "Conferir e salvar" que aplica e o seletor "Outras propostas".
- [ ] **Passo 2:** `uv run pytest -q`. Esperado: PASS.
- [ ] **Passo 3:** verificar no navegador, em 1280 px e 390 px, nos temas claro e escuro, com a demo e com `teste_acme`. Usar Tab e Enter em todos os controles, e conferir que não há erro no console.
- [ ] **Passo 4:** commit `docs: guia da revisao da etapa 1 em tres telas`.
