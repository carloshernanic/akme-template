# AKME do zero: ontologia e camada semântica com LOT + NeOn

Este guia explica o que o template faz, por que faz assim, e como usar de ponta a ponta num caso
novo. Ele cobre o estado do template em 2026-10-30, depois da reconstrução da etapa de
requisitos. O que ainda não está pronto está dito na última seção.

## 1. O problema que o template resolve

Um consultor recebe o banco de dados de um cliente (tabelas, dicionário, relatórios, glossário) e
precisa deixar um agente de IA respondendo perguntas de negócio sobre esses dados na plataforma
do cliente (Snowflake, Databricks). Entre o banco e o agente ficam dois artefatos:

- **A ontologia**: o mapa dos conceitos do negócio e de como se relacionam (Cliente, Pedido,
  Faturamento, "Pedido pertence a Cliente"). Vale para qualquer cliente do mesmo ramo.
- **A camada semântica**: onde cada conceito está no banco e como cada métrica se calcula
  (`pedidos.vl_total`, `SUM(... WHERE status = 'FATURADO')`). Só vale neste banco.

O template guia a construção dos dois com uma IA propondo e um humano decidindo, e guarda tudo
como texto versionado em `ontology/`.

## 2. Por que LOT + NeOn

O guia metodológico do grupo adota o fluxo da **LOT** (Linked Open Terms): especificação de
requisitos, implementação, publicação, manutenção, em ciclos curtos. Da **NeOn** vêm as atividades
que a LOT não detalha: reuso de ontologias existentes, alinhamento, re-engenharia de recursos que
não são ontologias (como um banco de dados). As duas insistem em três coisas que moldaram o
template:

1. **Requisitos antes de modelo.** A LOT começa com casos de uso e perguntas de competência (CQs):
   as perguntas que a ontologia precisa permitir responder. Especialistas e usuários validam e
   priorizam cada uma. Só depois se modelam classes.
2. **O humano decide.** A LOT atribui a validação dos requisitos e a avaliação da ontologia a
   especialistas e usuários. A revisão sistemática que embasa o guia (Li, Garijo e Poveda-Villalón,
   2026) mostra que LLMs ajudam a propor, mas não são confiáveis para avaliar sem verificação
   externa e revisão humana.
3. **Rastreabilidade.** Cada requisito tem identificador, prioridade, status e proveniência; cada
   elemento da ontologia aponta para o requisito que o motivou; cada decisão fica registrada.

No template isso virou: nada entra na ontologia sem passar por `propose_edit` (fica pendente),
aprovação humana nominal e `apply_edit`; toda proposta carrega evidência citando arquivo e página;
e, desde a reconstrução de hoje, nenhuma classe pode ser criada antes de os requisitos estarem
fechados.

## 3. O que foi reconstruído em 2026-10-30 e por quê

O diagnóstico (`docs/diagnostico-2026-10-30.md`) mostrou que a etapa de requisitos do template era
só texto: a IA propunha CQs soltas, o humano decidia digitando no chat, não havia caso de uso,
não havia registro do que os dados não respondem nem do que as fontes contradizem, e a ontologia
podia nascer antes de qualquer requisito validado. O teste em grupo com a planilha
`CQs_Capstone_Insper.xlsx` mostrou o que funciona: CQs com tipo, conceitos, trecho da fonte e caso
de uso, acompanhadas de lacunas e divergências.

O que entrou (desenho em `docs/superpowers/specs/2026-10-30-revisao-de-requisitos-design.md`):

| Peça | O que é | Onde vive |
|---|---|---|
| Caso de uso | Nome, descrição, atores e fluxo, como na LOT. Um ou vários por ontologia. Opcional, mas o agente sempre pergunta | `content.yml` → `requirements.use_cases` |
| CQ completa | Pergunta, tipo (seis tipos), conceitos envolvidos, evidência com arquivo e trecho, prioridade, status (`proposed`, `approved`, `reserved`, `rejected`, `deprecated`), resposta esperada quando reservada, quem propôs e quem revisou | `requirements.competency_questions` |
| Lacuna | Pergunta que o caso de uso sugere e os dados não respondem, com motivo e o que faltaria. As marcadas "pedir ao cliente" formam o **data request** | `requirements.gaps` |
| Divergência | Duas fontes que discordam, com citação de cada uma, a hipótese da IA rotulada como hipótese, e a decisão (qual prevalece, são termos distintos, perguntar ao especialista, descartar) | `requirements.divergences` |
| Bloco de revisão | A decisão do humano gravada dentro do próprio pendente: aceitar ou rejeitar, edições, prioridade, motivo, revisor, hora | `ontology/pending/*.yml` → `review` |
| Aplicação em lote | `apply_reviewed` aplica tudo que tem revisão numa cópia temporária, roda `validate`, e só promove se não houver erro novo | `akme/tools/batch.py` |
| Portão da etapa 1 | Enquanto a ontologia não tem classe de domínio, `propose_edit` de classe, relação, termo, mapping, restrição ou precedência é recusado até os requisitos fecharem | `requirements_status` |
| Página de revisão | Aba **Revisão** no `docs/index.html`, com um cartão por item, editável quando servida por `akme review` | `docs/review.js`, `akme/review_server.py` |

"Requisitos fechados" significa: há caso de uso (ou o motivo de não haver), nenhuma CQ ainda em
`proposed`, nenhum pendente da etapa 1 sem decisão, ao menos uma CQ aprovada, nenhuma lacuna ou
divergência em aberto, propósito e escopo preenchidos. CQ reservada com gabarito **não** é
exigida: nem todo projeto tem; sem ela o `eval` avisa que não testou pelo resultado.

## 4. Como usar, do zero

### 4.1 Preparar

```bash
git clone <repo do template> meu-cliente && cd meu-cliente
uv sync --extra dev --extra office --extra pdf
```

Coloque os arquivos do cliente em `data/` (planilhas `.csv` e `.xlsx`, documentos `.md`, `.txt`,
`.pdf`, `.docx`, `.pptx`; subpastas são lidas). O git ignora essa pasta. Depois:

```bash
uv run akme init          # cria akme.yml apontando para data/
uv run akme connect       # confere que as fontes são lidas
```

Para Snowflake, Databricks ou Postgres: `uv run akme init --adapter snowflake` e as variáveis de
ambiente listadas em `.env.example`.

Abra o Claude Code na pasta. O `.mcp.json` registra o servidor `akme` e a skill `akme` carrega o
`SKILL.md`, que é o roteiro que o agente segue.

### 4.2 Etapa 1: especificar (LOT: especificação de requisitos)

No chat: "mapeie o domínio do cliente". O agente:

1. **Pergunta o caso de uso.** Nome, uma descrição, atores e fluxo. Pode responder "não tem"; ele
   registra o motivo e segue, avisando que as CQs sairão mais genéricas.
2. **Lê as fontes.** `profile` (colunas, tipos, chaves, siglas), `read_document` página a página,
   `find_in_sources` para localizar termos.
3. **Propõe propósito, escopo e usuários**, e em seguida **dez CQs**, duas por tipo quando o
   domínio permite (classificação e hierarquia, relação entre conceitos, atributos, quantidade e
   agregação, tempo e estado, regras e restrições), cada uma com conceitos e evidência citada.
   Propõe também as **lacunas** e as **divergências** que encontrou. Tudo vira pendente; no chat
   aparece só a lista curta.
4. **Pede que você rode** `uv run akme review`. Isso roda o `export`, sobe um servidor local em
   `http://localhost:8765` e abre a página.

Na página, aba **Revisão**:

- Coloque seu nome em **Revisor** (sem ele, nada salva).
- Em cada CQ: edite o texto se quiser, escolha **Aceitar** ou **Rejeitar** (com motivo), dê
  **Prioridade**, marque **Ajuste** (vira exemplo para o agente) ou **Reservada** (vira gabarito do
  teste; pede a resposta esperada). Crie CQs suas em **Nova CQ**.
- Em cada lacuna: pedir o dado ao cliente, reformular, descartar ou deixar aberta.
- Em cada divergência: qual fonte prevalece, são termos distintos, perguntar ao especialista,
  descartar ou deixar aberta. "Prevalece" vira candidata a regra de precedência na etapa 3.
- **Salvar decisões.** Grava em `ontology/pending/*.yml`. Nada foi aplicado ainda.

De volta ao chat: "revisei". O agente lê os pendentes e resume ("8 aceitas, 2 rejeitadas, 3
editadas, 1 criada por você, 2 lacunas para o data request, 1 divergência com precedência").
Você diz **"aplica"** com seu nome. Só então `apply_reviewed` grava em `content.yml`, espelha as
reservadas em `validation/questions.yml` e registra tudo em `changelog.yml`. Se menos de cinco CQs
foram aceitas, ele oferece uma segunda rodada. Pendentes criados enquanto o `apply_reviewed` está
rodando se perdem: termine de salvar na página antes de dizer "aplica". Edições da etapa 2
(classes, relações, termos) aparecem na página só para leitura, em "Outros (aprovar pelo chat)",
e o `apply_reviewed` não as aplica.

Sem o Claude Code, o mesmo caminho existe na CLI: `uv run akme pending` lista,
`uv run akme apply --all-reviewed --approved-by SEU_NOME` aplica.

Enquanto os requisitos não fecham, a página abre direto na Revisão, com uma faixa dizendo o que
falta, e a aba Ontologia fica escondida. O agente também é barrado: qualquer tentativa de criar
classe devolve "requisitos nao fechados: ..." com a lista.

### 4.3 Etapas 2 a 6 (sem mudança hoje além do portão)

- **2. Conceitualizar.** O agente chama `requirements_status`; se fechado, lê o modelo atual e
  propõe classes, relações e termos a partir das CQs aprovadas, cada proposta ligada à CQ que a
  motiva. Consulta a LOV (`search_registry`) para reuso. Você aprova no chat.
- **3. Codificar.** Mappings para `tabela.coluna`, métricas com SQL, restrições e precedências
  (as divergências decididas na etapa 1 viram `add_precedence` aqui). `validate` antes de aplicar.
- **4. Avaliar.** `validate` (parse, referências, cobertura de colunas, pitfalls, e agora as regras
  de requisitos: reservada sem resposta, aprovada sem prioridade, lacuna em aberto) e `eval`
  (testes estruturais das reservadas; comparação com e sem ontologia via `--callable`).
- **5. Publicar.** `export` para o `docs/index.html`; `publish --target snowflake|databricks|yaml|rdf`
  em dry-run; executar no alvo exige confirmação.
- **6. Manter.** Mudança começa por uma CQ nova ou alteração (`update_competency_question`,
  `remove_competency_question`), passa pela mesma revisão. Depois da primeira classe, CQs novas não
  travam a ontologia.

### 4.4 Onde cada coisa fica gravada

| Arquivo | Conteúdo |
|---|---|
| `ontology/content.yml` | Requisitos (caso de uso, CQs, lacunas, divergências), termos, mappings, restrições, glossário, precedência, evidências |
| `ontology/schema.ttl` | Classes e relações em OWL |
| `ontology/pending/` | Propostas aguardando decisão, com o bloco `review` quando já revisadas |
| `ontology/changelog.yml` | Quem propôs, quem aprovou, quando, com que evidência, e o antes e depois das alterações |
| `validation/questions.yml` | CQs reservadas espelhadas automaticamente, com `expects` e `answer` |
| `docs/index.html` + `docs/ontology.js` | A página; `akme export` ou `akme review` atualizam os dados |

### 4.5 Ver a página

- **Editável:** `uv run akme review` e abrir `http://localhost:8765`. Só aceita conexões da própria
  máquina e só do próprio navegador (checa origem).
- **Só leitura:** `uv run akme export` e abrir `docs/index.html` do disco. Ou servir a pasta com
  `python3 -m http.server` dentro de `docs/`.

## 5. Demonstração em dois minutos

```bash
uv run akme init --demo      # distribuidora de materiais de construção, dados em examples/local_demo
uv run akme demo             # connect, profile, seed (caso de uso, CQs, lacuna, divergência, classes), validate, export
uv run akme review           # abre a página: aba Ontologia com o grafo e aba Revisão com o já aplicado
```

A aba Revisão da demo não começa vazia: mostra o caso de uso, as CQs, a lacuna e a divergência já
aplicados pelo seed, sem pendentes. Para ver pendentes, peça ao agente "proponha dez CQs novas para
a demo" e abra a aba Revisão de novo.

## 6. O que ainda não foi feito

O diagnóstico listou mais do que a etapa 1. Continuam em aberto, por ordem de prioridade:

1. **Avaliação pelo resultado**: rodar as CQs reservadas contra os dados com gabarito SQL. Hoje o
   `eval` é estrutural.
2. **Cobertura de CQs** no `validate`: quais CQs aprovadas ainda não têm classe, termo ou mapping.
3. **Publicação Snowflake** com chaves primárias e `RELATIONSHIPS`; Databricks como metric view.
4. **Edição e remoção** de classes, termos e mappings (hoje só CQs, lacunas e divergências têm
   `update`/`remove`).
5. **Reuso com substância**: ler a definição do termo na LOV e registrar alinhamentos.
6. Raciocinador (HermiT) como portão de consistência; atributos e disjunção no modelo.

## 7. Referências

- Guia metodológico do grupo: `github.com/capstone-insper/202602_MCKINSEY_DiagnosticEngineDataRequest_Docs`
- Base metodológica detalhada: `docs/research/lot-neon.md`
- Diagnóstico: `docs/diagnostico-2026-10-30.md`
- Desenho desta etapa: `docs/superpowers/specs/2026-10-30-revisao-de-requisitos-design.md`
- Roteiro do agente: `SKILL.md`
