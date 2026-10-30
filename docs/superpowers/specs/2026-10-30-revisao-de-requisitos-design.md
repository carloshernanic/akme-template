# Revisão de requisitos: caso de uso, lote de CQs, lacunas e divergências

Data: 2026-10-30. Status: aguardando aprovação do grupo. Escopo: etapa 1 (Especificar) do
`SKILL.md`. Decisão já tomada pelo grupo: CQs aplicadas também são editáveis na página (4.6).

## 1. Intenção e porquê

Hoje a etapa 1 pede ao agente que proponha CQs e pare para o humano validar, mas não diz como o
lote é gerado, não dá ao humano contexto para julgar cada CQ, não registra o que os dados não
respondem nem o que as fontes contradizem, e obriga o humano a decidir tudo digitando no chat.
O teste em grupo (planilha `CQs_Capstone_Insper.xlsx`, não documentada) mostrou o que funciona:
uma tabela de CQs com tipo, conceitos envolvidos, trecho da fonte e caso de uso, acompanhada de
três visões auxiliares, análise do domínio, lacunas e divergências. Com isso o humano entende de
onde cada pergunta veio e consegue validar.

Este desenho leva essa informação para dentro do template: a IA propõe, o humano revisa e decide
numa tela do próprio projeto, a decisão volta para o repositório com autor, e a aprovação final
continua sendo uma palavra no chat. Base metodológica: LOT 3.1.1 (caso de uso, opcional),
3.1.4 (proposta de requisitos), 3.1.5 (validação e priorização pelo humano), e o Passo 2 do guia
do grupo (cada CQ com identificador, trecho que a sustenta e dúvidas pendentes).

## 2. Objetivos, não objetivos, anti-objetivos

Objetivos

- O agente pede o caso de uso no início de todo projeto, uma vez, e aceita "não tem".
- O agente gera um lote de dez CQs, mais as lacunas e divergências que encontrou ao ler as
  fontes, tudo como edições pendentes com evidência citada.
- O humano revisa numa página servida localmente a partir do repositório: edita o texto de cada
  CQ, dá prioridade, marca ajuste ou reservada, aceita ou rejeita com motivo, cria CQs novas,
  decide cada lacuna e cada divergência.
- As decisões ficam gravadas nos arquivos de `ontology/pending/` com nome do revisor e hora.
- A aplicação continua passando pelo gate: o agente resume as decisões no chat, o humano diz
  "aplica", o agente aplica em lote.
- A IA lê tudo isso pelas tools existentes (`get_requirements`, `list_competency_questions`,
  `list_pending`), sem formato paralelo.

Não objetivos

- Não muda as etapas 2 a 6, exceto pelo portão de entrada da etapa 2 (4.9). A aba de revisão
  mostra só o que a etapa 1 produz. Classes, relações e mappings pendentes continuam sendo
  aprovados pelo fluxo atual.
- Não resolve os outros itens do diagnóstico (`docs/diagnostico-2026-10-30.md`): reasoner,
  cobertura de CQ no `validate`, `publish`, operações de modificação em classes e termos.
- Não exporta para Excel. Se o cliente precisar, é um comando futuro a partir do mesmo YAML.
- Não é uma aplicação web multiusuário. É uma página local, um revisor por vez.

Anti-objetivos (o que tornaria isto um fracasso mesmo funcionando)

- Decisão aplicada sem que alguém tenha dito "aplica" no chat com nome.
- CQ reservada entrando como exemplo no `publish`, ou CQ de ajuste entrando como gabarito no
  `eval`.
- Hipótese da IA gravada como se fosse fonte. Toda evidência cita arquivo e página ou coluna;
  o que é suposição fica rotulado como suposição.
- Um segundo formato de dados que a IA não lê. A fonte da verdade é `content.yml` e
  `ontology/pending/`.

## 3. Restrições

- Python 3, dependências atuais (`rdflib`, `pydantic`, `typer`, `rich`, `pyyaml`, `mcp`). O
  servidor local usa a biblioteca padrão (`http.server`); sem framework web novo.
- A página de revisão é uma aba do `docs/index.html` existente, no mesmo tema (tokens em
  `docs/design-tokens.md`), sem build step e sem dependência externa.
- Tudo que o humano decide tem de caber em YAML legível e diffável no git.
- `SKILL.md` só pode descrever etapas que existam em `docs/research/lot-neon.md`; o lote de dez
  CQs, o caso de uso e as três visões auxiliares cabem nas seções 2.2 e 4.1 desse documento.
- Pastas: dados do cliente em `data/` (ignorada pelo git); ontologia em `ontology/`; páginas em
  `docs/`.

## 4. O que foi decidido

### 4.1 Caso de uso

- Vive em `content.yml`, em `requirements.use_cases`, lista no nível da ontologia, como no LOT.
  Campos: `id` (UC-nn), `name`, `description`, `actors` (lista), `flow`, `source`.
- Entra por `propose_edit` com tipo novo `add_use_case` e passa pelo gate como tudo.
- O agente pede no primeiro contato do projeto. Se `use_cases` já tem item, não pede de novo.
  Se o humano não tem, o agente registra isso na conversa, avisa que as CQs sairão mais
  genéricas, e segue com profile e documentos.
- Ligação CQ para caso de uso: campo `use_cases` opcional na CQ, lista de ids. Não é exigido.

### 4.2 Competency question

Campos da CQ em `content.yml`:

| Campo | Obrigatório | Quem preenche | Valores |
|---|---|---|---|
| `id` | sim | tool (CQ-nnn sequencial) | |
| `question` | sim | IA propõe, humano edita | texto |
| `type` | sim | IA propõe, humano edita | `classificacao_hierarquia`, `relacao_entre_conceitos`, `atributos`, `quantidade_agregacao`, `tempo_estado`, `regras_restricoes` |
| `concepts` | sim | IA propõe | lista de nomes em linguagem natural (ainda não são classes) |
| `evidence` | sim, ao menos uma | IA via `find_in_sources`; humano via página | lista de itens com `kind`: `source` (`{kind, path, locator, quote}`, `locator` é página, slide, ou aba e coluna) ou `conversation` (`{kind, who, when, note}`). CQ proposta pela IA exige ao menos um item `source`; CQ criada pelo humano recebe um item `conversation` com revisor e hora, preenchido pela página |
| `use_cases` | não | IA ou humano | lista de UC-nn |
| `priority` | sim quando aceita | humano | `high`, `medium`, `low` |
| `status` | sim | tool | `proposed`, `approved` (ajuste), `reserved`, `rejected`, `deprecated` |
| `answer` | sim quando `reserved` | humano (IA pode sugerir) | trecho que a resposta precisa conter |
| `proposed_by` | sim | tool | nome do revisor ou `agent` |
| `reviewed_by`, `reviewed_at` | sim quando decidida | tool | |
| `rejection_reason` | sim quando `rejected` | humano | texto |

Regras

- `approved` entra como exemplo no `publish`; `reserved` nunca entra no `publish` e é espelhada
  em `validation/questions.yml` no `apply` (id, question, answer), para o `eval` não depender de
  arquivo mantido à mão.
- CQ rejeitada **fica** em `content.yml` com `status: rejected` e motivo. O LOT guarda requisitos
  rejeitados; a IA precisa vê-los para não propor de novo. Em termos de tool: rejeitar uma CQ na
  revisão **não** é `reject_edit`; é aplicar a CQ com `status: rejected`, `rejection_reason`,
  `reviewed_by` e `reviewed_at`. `list_competency_questions` devolve todas e ganha filtro por
  status; `publish` usa só `approved`; a página mostra rejeitadas esmaecidas. `reject_edit`
  continua existindo para descartar um pendente que nem deve virar registro (ex.: duplicata).
- Reservada espelhada em `validation/questions.yml` por **mesclagem por id**: o `apply` cria ou
  atualiza `id`, `question` e `answer`, preserva `expects` e outros campos escritos à mão, e
  remove a entrada quando a CQ deixa de ser `reserved` (por `update_competency_question`,
  `deprecated` ou remoção). Entradas sem CQ correspondente ficam e continuam gerando aviso.
- Excluir CQ: tipo novo `remove_competency_question`. Se nada em `changelog.yml` ou `content.yml`
  referencia o id, remove de verdade. Se algo referencia, vira `status: deprecated` com motivo e
  o agente lista o que ficaria órfão antes de o humano confirmar. (Decisão minha, marcada em 6.)
- Edição de CQ já aplicada: tipo novo `update_competency_question`, mesmo gate. O payload leva
  `id` e só os campos alterados; o `apply` mescla sobre a entrada existente e grava no changelog
  o antes e o depois de cada campo. Mudança de `status` entre `approved` e `reserved` refaz o
  espelhamento em `questions.yml`.
- `update_gap` e `update_divergence`: mesmo padrão, usados para mudar a `decision`.

### 4.3 Lacunas e divergências

`requirements.gaps`: `id` (L-nn), `question`, `reason`, `missing`, `evidence` (mesma forma da
CQ), `use_cases` opcional, `decision` em `request_from_client`, `reformulate`, `drop`, `open`,
`decided_by`, `decided_at`, `note`.

`requirements.divergences`: `id` (D-nn), `topic`, `sources` (lista de `{label, path, locator,
quote}`, duas ou mais), `hypothesis` (texto da IA, sempre rotulado como hipótese),
`decision` em `precedence`, `distinct_terms`, `ask_expert`, `dismiss`, `open`, `winner` (quando
`precedence`), `reason`, `decided_by`, `decided_at`.

Lacunas e divergências não têm "aceitar ou rejeitar": são sempre aplicadas com uma `decision`.
"A IA inventou isso" é `drop` na lacuna e `dismiss` na divergência, com motivo; o registro fica,
para a IA não repetir. `open` é a única decisão que não exige motivo.

Tipos de edição novos: `add_gap`, `add_divergence`. Lacuna com `request_from_client` compõe a
lista do data request (`get_requirements` devolve `data_request` derivado). Divergência com
`precedence` é candidata a `add_precedence` na etapa 3; o agente propõe, não aplica sozinho.

### 4.4 Onde a decisão do humano é guardada antes de aplicar

Dentro do próprio arquivo pendente (`ontology/pending/<id>.yml`), num bloco `review`:

```yaml
review:
  decision: accept | reject
  reviewer: Mateus
  reviewed_at: 2026-10-30T14:02:00+00:00
  edits:            # só o que o humano mudou no payload
    question: "..."
    priority: high
    status: reserved
    answer: "..."
  reason: "..."     # obrigatório em reject
```

Sem novo diretório, sem novo formato. `list_pending` passa a devolver o bloco. Uma CQ criada
pelo humano na página é um pendente novo com `proposed_by` igual ao revisor e `review.decision:
accept` já preenchido.

### 4.5 Aplicação em lote

- `apply_edit` passa a aceitar `edit_ids: list[str]` além de `edit_id`, e `approved_by`
  continua obrigatório. Para cada pendente com `review`, aplica o payload com `edits` mesclado
  e grava no changelog o `review` inteiro. Para CQ com `review.decision: reject`, aplica com
  `status: rejected` (ver 4.2); para lacuna e divergência, aplica com a `decision` escolhida.
- Tool nova `apply_reviewed(approved_by)`: aplica todos os pendentes que têm bloco `review`,
  numa chamada. Pendentes sem `review` ficam. Devolve o resumo (aceitas, rejeitadas, editadas,
  criadas pelo humano, lacunas e divergências por decisão, erros).
- O agente nunca chama `apply_reviewed` sem antes mostrar o resumo no chat e receber "aplica"
  (ou equivalente) com o nome de quem aprova. Regra 1 do `SKILL.md` continua valendo.
- `validate` roda dentro dos caminhos em lote (`apply_reviewed` e `apply_edit` com
  `edit_ids`), de forma transacional: o lote é aplicado numa cópia temporária de
  `ontology_dir` e de `validation/questions.yml`, o `validate` roda sobre a cópia, e o
  resultado é comparado com o `validate` do estado atual. Erros **novos** abortam o lote inteiro
  e nada é gravado; erros pré-existentes (ex.: mapping quebrado da etapa 3) não bloqueiam, mas
  aparecem no resumo. Se não há erro novo, os arquivos da cópia substituem os originais e
  `docs/validation.json` é atualizado. O `apply_edit` de um id só, `akme seed`, `akme demo` e a
  fixture `seeded` dos testes não mudam. (Fecha o item "validate não é forçado" do diagnóstico
  só para o caminho em lote; o caminho unitário fica para outro projeto.)

### 4.6 A página de revisão

- `akme review [--port 8765] [--no-open]` sobe um servidor da biblioteca padrão que serve
  `docs/` e expõe `GET /api/pending` (pendentes com `review`), `GET /api/requirements`
  (`content.yml` já aplicado), `POST /api/review` (grava o bloco `review` num pendente),
  `POST /api/propose` (cria pendente novo a partir da página: `add_competency_question` em
  "Nova CQ", `update_competency_question` em "propor alteração", `remove_competency_question`
  em "propor exclusão"; o pendente nasce com `proposed_by` igual ao revisor e `review.decision:
  accept`), `GET /api/sources?q=` (encaminha para `find_in_sources`, para o humano conferir
  uma citação). Só escuta em `127.0.0.1`. Encerra com Ctrl+C.
- CQs já aplicadas aparecem na aba como cartões em leitura, com dois botões: "propor
  alteração" abre os campos editáveis (pergunta, tipo, conceitos, prioridade, uso, resposta
  esperada) e, ao salvar, cria um pendente `update_competency_question` cujo cartão mostra o
  diff campo a campo (antes e depois); "propor exclusão" pede motivo e cria um pendente
  `remove_competency_question`, cujo cartão lista o que referencia a CQ (classes, termos,
  mappings, entradas do changelog) e avisa se a exclusão vai virar `deprecated`. Os dois
  pendentes entram no mesmo `apply_reviewed`, depois do "aplica" no chat. Decisão do grupo em
  2026-10-30: o consultor nunca precisa digitar uma CQ no chat.
- Lacunas e divergências já decididas seguem a mesma regra, com "propor alteração" para mudar
  a `decision` (ex.: reabrir ou fechar). Não há exclusão delas; `drop` e `dismiss` cumprem esse
  papel.
- A aba "Revisão" entra em `docs/index.html` ao lado de Grafo e Termos. Quando a página é
  aberta como arquivo (sem servidor), a aba mostra os pendentes em modo leitura a partir de
  `docs/ontology.js` (o `export` passa a incluir `pending` e `requirements` completos). Quando
  servida por `akme review`, fica editável.
- Layout aprovado no mockup (`.superpowers/brainstorm/24938-1793368327/content/tela-revisao-v2.html`):
  barra lateral com Pendentes (CQs, Lacunas, Divergências) e Contexto (Caso de uso, Fontes
  lidas); cartões um por item; para CQ: id e origem, pergunta editável, chips de tipo e
  conceitos, evidência com `path`, locator e citação, e à direita decisão, prioridade, uso e,
  quando reservada, resposta esperada; CQ rejeitada esmaecida com motivo; cartão "Nova CQ";
  para lacuna: pergunta, motivo, o que faltaria, evidência, decisão em quatro saídas e "entra no
  data request"; para divergência: tópico, fonte A e B com citação, hipótese da IA rotulada,
  decisão em quatro saídas e motivo. Rodapé fixo com contagem, "Salvar decisões", "Descartar" e
  o lembrete "depois, no chat: aplica". Campo "Revisor" no topo, obrigatório para salvar.
- Contraste: texto `text-primary` sobre `surface-primary`, conforme `docs/design-tokens.md`.
  O primeiro mockup falhou nisso e foi corrigido.
- O painel "Análise do domínio" da planilha **não entra nesta versão**. Os conceitos ficam nos
  chips de cada CQ. (Decisão minha, marcada em 6.)

### 4.7 O lote de dez CQs e a etapa 1 no `SKILL.md`

Nova redação da etapa 1, em ordem:

1. Perguntar o caso de uso (ou constatar que já existe). Propor `add_use_case`.
2. `profile`, `read_document` nos documentos, `find_in_sources` nos termos que aparecerem.
3. Propor propósito, escopo e usuários (como hoje).
4. Propor exatamente dez CQs, distribuídas entre os seis tipos (idealmente duas por tipo; se o
   domínio não sustenta um tipo, dizer qual e por quê). Cada CQ com `concepts`, `evidence`
   citada e `type`. Propor em seguida as lacunas (perguntas que o caso de uso sugere e os dados
   não respondem) e as divergências (fontes que discordam), com evidência.
5. Rodar `export`, dizer ao humano: "rode `akme review` e abra a aba Revisão". Mostrar no chat
   só a lista curta: id, pergunta, tipo.
6. Quando o humano voltar, ler `list_pending`, resumir decisões (n aceitas, n rejeitadas, n
   editadas, n criadas, lacunas e divergências decididas) e pedir "aplica" com nome.
7. `apply_reviewed`. Propor glossário (como hoje). Se menos de cinco CQs foram aceitas, oferecer
   uma segunda rodada de até dez, sem repetir rejeitadas.

Saída da etapa: `use_cases`, CQs com status, `gaps`, `divergences` e `glossary` em
`content.yml`; reservadas espelhadas em `validation/questions.yml`; data request derivável.

### 4.8 Validate, publish, eval e export

- `validate`: erro se CQ `reserved` sem `answer`; aviso se não há nenhuma `reserved` (sem
  gabarito o `eval` não testa pelo resultado); erro se `approved` sem `priority`; erro se CQ
  proposta pela IA (`proposed_by: agent`) sem evidência `source`; aviso para toda `gap` ou
  `divergence` com `decision: open` (sem noção de rodada; o aviso some quando alguém decide); a
  checagem `question_without_requirement` passa a aceitar só CQs `reserved`.
- `publish`: `examples` só com `status: approved`.
- `eval`: lê `validation/questions.yml` como hoje; o espelhamento garante que só reservadas
  estejam lá.
- `export`: inclui `pending` (com `review`) e `requirements` completos em `ontology.json` e
  `ontology.js`.
- Demo (`examples/local_demo/seed_edits.yml`): ganha um caso de uso, as CQs com `type`,
  `concepts` e `evidence` estruturada, uma CQ `reserved` com `answer` e `expects` (a demo
  mostra o caminho completo, mesmo que projetos reais possam não ter reservada), uma
  lacuna e uma divergência. `questions.yml` da demo passa a conter só as reservadas, com seus
  `expects` preservados pela mesclagem.

### 4.9 Portão da etapa 1: nada de ontologia antes de requisitos fechados

Decisão do grupo em 2026-10-30: a primeira tela do projeto é a Revisão, e a ontologia não é
mostrada nem criada até os requisitos estarem validados.

Definição de "requisitos fechados" (`requirements_closed`, calculada pelas tools a partir de
`content.yml` e de `ontology/pending/`):

1. Existe ao menos um caso de uso, ou o campo `requirements.no_use_case` tem o motivo
   registrado pelo humano ("o cliente não tem caso de uso definido").
2. Não há CQ com `status: proposed` e não há pendente dos tipos da etapa 1 sem `review`
   aplicado (`add_use_case`, `add_competency_question`, `update_competency_question`,
   `remove_competency_question`, `add_gap`, `add_divergence`, `update_gap`, `update_divergence`,
   `add_requirement`, `add_glossary`).
3. Há ao menos uma CQ `approved`. Reservadas **não** são exigidas: nem todo projeto tem gabarito
   (decisão do grupo em 2026-10-30). Quando não há nenhuma `reserved`, o `validate` emite aviso
   e o `eval` informa que o teste pelo resultado não pôde rodar; a etapa 4 segue só com a
   verificação formal e diz isso ao humano.
4. Nenhuma lacuna e nenhuma divergência com `decision: open`. `ask_expert` conta como decidida:
   alguém assumiu a pergunta; a resposta do especialista entra depois por `update_divergence`.
   (Decisão minha, marcada em 6.)
5. `requirements.purpose` e `requirements.scope` preenchidos.

Efeitos:

- `propose_edit` recusa `add_class`, `add_relation`, `add_term`, `add_mapping`,
  `add_constraint` e `add_precedence` enquanto `requirements_closed` for falso **e** a ontologia
  ainda não tiver nenhuma classe de domínio (só as quatro raízes). A mensagem de erro diz o que
  falta. Depois que a ontologia existe, novas CQs não travam a ontologia: manutenção (etapa 6)
  convive com CQs novas, como no LOT.
- Tool nova `requirements_status()` devolve `closed: bool` e a lista do que falta. O agente a
  chama antes de iniciar a etapa 2 e mostra a lista ao humano quando falso.
- `SKILL.md`: a etapa 2 começa com "chame `requirements_status`; se não estiver fechado, volte
  à etapa 1". A etapa 1 termina com o portão fechado, não com a aplicação do lote.
- Página: enquanto o portão está aberto, `docs/index.html` abre direto na aba Revisão e as abas
  Grafo e Termos ficam ocultas, com uma faixa no topo listando o que falta para fechar. Quando
  fecha, as abas aparecem e a página passa a abrir no Grafo, com a Revisão ainda acessível. O
  estado vem de `requirements_status` via `/api/status` quando servida por `akme review`, e de
  `ontology.js` (o `export` grava o resultado) quando aberta como arquivo.
- `akme demo` e `examples/local_demo/seed_edits.yml`: o seed passa a fechar a etapa 1 antes de
  propor classes (CQ-003 deixa de ser `proposed`; entra lacuna e divergência decididas; entra
  caso de uso). O teste da demo verifica que o portão estava fechado quando a primeira classe
  entrou.

### 4.10 Testes

- `propose_edit` dos tipos novos e dos campos obrigatórios da CQ.
- `review` gravado no pendente; `apply_reviewed` aplica aceitas com `edits` mesclados e rejeita
  as demais com motivo; pendentes sem `review` permanecem.
- `remove_competency_question`: remove quando órfã, deprecia quando referenciada.
- Reservada espelhada em `questions.yml`; `publish` exclui reservada; `validate` reprova
  reservada sem `answer`.
- Servidor: `GET /api/pending`, `POST /api/review`, `POST /api/propose` para os três tipos de
  CQ e para `update_gap` e `update_divergence`, recusa em host externo.
- `update_competency_question` mescla só os campos enviados e registra antes e depois;
  mudança de status refaz o espelhamento.
- `export` com `pending` e `requirements`.
- Portão: `propose_edit(add_class)` recusa com ontologia vazia e requisitos abertos, e aceita
  quando fechados; aceita também com requisitos abertos quando já há classe de domínio;
  `requirements_status` lista exatamente o que falta em cada condição.

## 5. O que fica para quem constrói

- Nomes exatos de endpoints, ids de elementos da página, estrutura interna do JS.
- Como gerar ids sequenciais com segurança (CQ-nnn) quando há pendentes e aplicados.
- Formato do resumo que `apply_reviewed` devolve.
- Como a aba Revisão se comporta com zero pendentes (estado vazio com instrução).
- Ordem de implementação; sugestão: esquema e tipos de edição, depois `review` e
  `apply_reviewed`, depois servidor e página, depois `SKILL.md` e demo.

## 6. Decisões minhas que o grupo pode trocar

1. CQ rejeitada fica em `content.yml` com status `rejected`, em vez de só no changelog.
2. Excluir CQ referenciada vira `deprecated` com motivo; só CQ órfã é apagada.
3. O painel "Análise do domínio" fica fora desta versão.
4. Servidor em biblioteca padrão, só em `127.0.0.1`, sem autenticação.
5. Reservadas espelhadas em `validation/questions.yml` em vez de o `eval` ler `content.yml`,
   por mesclagem que preserva `expects`.
6. Dez CQs fixas por rodada, segunda rodada só se menos de cinco forem aceitas.
7. Rejeitar CQ na revisão grava a CQ com `status: rejected` em `content.yml`, não `reject_edit`.
   Lacunas e divergências nunca são rejeitadas; recebem `drop` ou `dismiss` com motivo.
8. Evidência tem `kind` (`source` ou `conversation`); CQ da IA exige ao menos uma `source`; CQ
   do humano nasce com uma `conversation`.
9. `validate` transacional só nos caminhos em lote; erro novo aborta, erro pré-existente avisa.
10. Aviso de lacuna ou divergência `open` é permanente até alguém decidir; não há "rodada".
11. No portão da etapa 1, `ask_expert` conta como decidida; só `open` trava. E o portão vale
    apenas enquanto a ontologia está vazia: depois da primeira classe, CQs novas não travam.
