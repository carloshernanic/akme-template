# AKME do zero: ontologia e camada semântica com LOT + NeOn

Este guia explica o que o template faz, por que faz assim, e como usar de ponta a ponta num caso
novo. Ele cobre o estado do template em 2026-11-03, depois da reconstrução da etapa de
requisitos (30/10) e da página de revisão como caixa de entrada de decisões (03/11). O que ainda não está pronto está dito na última seção.

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
| Caso de uso | Nome, descrição, atores e fluxo, como na LOT. Um ou vários por ontologia. O agente propõe de 2 a 3 tirados das fontes e você escolhe ou escreve o seu na página | `content.yml` → `requirements.use_cases` |
| CQ completa | Pergunta, tipo (seis tipos), conceitos envolvidos, evidência com arquivo e trecho, prioridade, status (`proposed`, `approved`, `reserved`, `rejected`, `deprecated`), resposta esperada quando reservada, quem propôs e quem revisou | `requirements.competency_questions` |
| Lacuna | Pergunta que o caso de uso sugere e os dados não respondem, com motivo e o que faltaria. As marcadas "pedir ao cliente" formam o **data request** | `requirements.gaps` |
| Divergência | Duas fontes que discordam, com citação de cada uma, a hipótese da IA rotulada como hipótese, e a decisão (qual prevalece, são termos distintos, perguntar ao especialista, descartar) | `requirements.divergences` |
| Bloco de revisão | A decisão do humano gravada dentro do próprio pendente: aceitar ou rejeitar, edições, prioridade, motivo, revisor, hora | `ontology/pending/*.yml` → `review` |
| Aplicação em lote | `apply_reviewed` aplica tudo que tem revisão numa cópia temporária, roda `validate`, e só promove se não houver erro novo | `akme/tools/batch.py` |
| Portão da etapa 1 | Enquanto a ontologia não tem classe de domínio, `propose_edit` de classe, relação, termo, mapping, restrição ou precedência é recusado até os requisitos fecharem | `requirements_status` |
| Página de revisão | Caixa de entrada de decisões em qualquer etapa: uma proposta por vez, aceitar ou rejeitar, aplicar com nome. Servida por `akme review`; atualiza sozinha | `akme/static/`, `akme/review_server.py`, `akme/tools/review_view.py` |

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
`SKILL.md`, que é o roteiro que o agente segue. Codex, Cursor e Antigravity também funcionam: veja
"Outras harnesses" no `README.md`.

### 4.2 Quem decide: você ou a IA

Logo depois do pedido para criar a ontologia, o agente abre um formulário (`choose_decision_mode`)
com duas opções e o seu nome:

- **Eu decido cada proposta** (modo humano): o fluxo descrito abaixo, com a página de revisão.
- **A IA decide tudo e eu reviso no fim** (modo automático): o agente aceita, ajusta ou rejeita
  cada proposta e aplica em seu nome, sem parar. Cada decisão vai para o `changelog.yml` assinada
  como "IA (modo automático, autorizado por SEU NOME)". A IA não inventa dado que falta (lacuna vira
  pedido ao cliente), faz no máximo dois ciclos de correção na avaliação e só gera o `publish` em
  dry-run. No fim, entrega um relatório do que decidiu e abre a página para você conferir.

A escolha fica em `ontology/decision_mode.yml`, com o histórico de trocas. Para mudar, peça ao
agente ("quero decidir eu"). Fora do modo automático, o servidor recusa revisão ou aplicação em nome
da IA: o agente não consegue se autoaprovar.

### 4.3 Etapa 1: especificar (LOT: especificação de requisitos)

No chat: "mapeie o domínio do cliente". O agente:

O caso de uso vem antes de tudo e é escolhido na página, em duas rodadas de revisão.

1. **Lê as fontes.** `profile` (colunas, tipos, chaves, siglas), `read_document` página a página,
   `find_in_sources` para localizar termos. Com Databricks, pergunta antes quais catálogos ou
   schemas perfilar.
2. **Propõe de 2 a 3 casos de uso** tirados das fontes (nome, para que serve, quem usa), cada um
   com a evidência, e **abre a página na hora** (`open_review`). Na tela "Caso de uso" você marca
   os que valem, escreve o seu ou diz "Não temos caso de uso", e clica em **Conferir e salvar**,
   que grava e aplica com o seu nome. O agente estava esperando e segue sozinho.
3. **Propõe propósito, escopo e usuários**, e em seguida **dez CQs** ligadas aos casos escolhidos,
   duas por tipo quando o domínio permite (classificação e hierarquia, relação entre conceitos,
   atributos, quantidade e agregação, tempo e estado, regras e restrições), cada uma com conceitos
   e evidência citada. Propõe também as **lacunas** e as **divergências** que encontrou. Tudo vira
   pendente; no chat aparece só a lista curta.
4. **Abre a página de novo**, nas telas "Perguntas" e "Lacunas e divergências", e diz a URL em
   uma linha. Se preferir, você mesmo roda `uv run akme review`.

Na página (vista **Revisão**, a inicial):

- A barra lateral mostra o **fluxo LOT** com a etapa atual. O cabeçalho diz "Etapa X de 6" e,
  enquanto os requisitos estão abertos, uma faixa no topo diz o que falta.
- Um seletor no topo separa **Etapa 1** (telas Caso de uso, Perguntas, Lacunas e divergências e
  Glossário; só aparecem as que têm algo a decidir) de **Outras propostas** (classes, relações,
  termos, mapeamentos, restrições, precedências, fontes e alterações do que já foi aplicado). O
  número ao lado de cada um cai conforme você decide.
- Cada proposta é um cartão enxuto: título, fonte citada, **ver detalhes** (evidência com
  "conferir", justificativa da IA e, nas relações, o que o dado mostra) e os botões **✓ Aceitar**
  e **✕ Rejeitar**. Rejeitar pede o motivo em botões. O que já foi decidido vira uma linha com
  **rever**. Textos ajustáveis (rótulo, comentário, definição, sinônimos) ficam em "ajustar
  texto". Em CQs, aceitar pede a **Prioridade**. **Aceitar tudo** aceita o que ainda está sem
  decisão.
- Em cada lacuna: pedir o dado ao cliente, reformular, descartar ou deixar em aberto. Em cada
  divergência: qual fonte vale, são coisas diferentes, perguntar ao especialista, descartar ou
  deixar em aberto. "Vale a fonte X" vira candidata a regra de precedência na etapa 3. Deixar em
  aberto mantém a etapa 1 aberta até alguém decidir.
- Criar algo (caso de uso, pergunta) ou alterar o que já foi aplicado (em **Já aplicadas**, dentro
  de Outras propostas) abre uma janela no centro da tela.
- **Conferir e salvar.** Mostra o resumo e pede o nome de quem aprova. **Salvar e aplicar** grava
  as decisões e roda o lote numa cópia com `validate`; só promove se não surgir erro novo.
  Equivale a dizer "aplica" no chat ou a `uv run akme apply --all-reviewed --approved-by SEU_NOME`
  na CLI.

A página atualiza sozinha: quando o agente propõe algo novo, o item aparece; quando o agente
aplica pelo chat, o item sai. O que você decidiu e ainda não salvou continua lá enquanto a página
estiver aberta.

Enquanto a página está aberta, o agente fica esperando no chat (`wait_for_review`) e a página
mostra "O agente está esperando você aplicar". Depois de **Salvar e aplicar**, a página diz para
voltar ao chat: o agente já recebeu o resumo ("8 aceitas, 2 rejeitadas, aplicadas por você") e
seguiu para o próximo passo, sem você escrever nada. Se preferir decidir no chat, escreva lá: o
agente para de esperar, lê os pendentes, resume e pede **"aplica"** com seu nome.
`apply_reviewed` grava em `content.yml` e `schema.ttl`, espelha as reservadas em
`validation/questions.yml` e registra tudo em `changelog.yml`. Se menos de cinco CQs foram aceitas,
ele oferece uma segunda rodada. Termine de salvar na página antes de dizer "aplica".

Enquanto os requisitos não fecham, a faixa da etapa 1 diz o que falta e o agente é barrado:
qualquer tentativa de criar classe devolve "requisitos nao fechados: ..." com a lista.

### 4.4 Etapas 2 a 6 (sem mudança hoje além do portão)

- **2. Conceitualizar.** O agente chama `requirements_status`; se fechado, lê o modelo atual e
  propõe classes, relações e termos a partir das CQs aprovadas, cada proposta ligada à CQ que a
  motiva. Consulta a LOV (`search_registry`) para reuso. Você decide na mesma página: cada
  relação mostra a junção declarada e o que o dado mostra; classes e relações pendentes aparecem
  tracejadas no grafo da vista Ontologia.
- **3. Codificar.** Mappings para `tabela.coluna`, métricas com SQL, restrições e precedências
  (as divergências decididas na etapa 1 viram `add_precedence` aqui). `validate` antes de aplicar.
  Também decididos na página.
- **4. Avaliar.** `validate` (parse, referências, cobertura de colunas, pitfalls, e agora as regras
  de requisitos: reservada sem resposta, aprovada sem prioridade, lacuna em aberto) e `eval`
  (testes estruturais das reservadas; comparação com e sem ontologia via `--callable`).
- **5. Publicar.** `export` para o `docs/index.html`; `publish --target snowflake|databricks|yaml|rdf`
  em dry-run; executar no alvo exige confirmação.
- **6. Manter.** Mudança começa por uma CQ nova ou alteração (`update_competency_question`,
  `remove_competency_question`), passa pela mesma revisão. Depois da primeira classe, CQs novas não
  travam a ontologia.

### 4.5 Onde cada coisa fica gravada

| Arquivo | Conteúdo |
|---|---|
| `ontology/content.yml` | Requisitos (caso de uso, CQs, lacunas, divergências), termos, mappings, restrições, glossário, precedência, evidências |
| `ontology/schema.ttl` | Classes e relações em OWL |
| `ontology/pending/` | Propostas aguardando decisão, com o bloco `review` quando já revisadas |
| `ontology/changelog.yml` | Quem propôs, quem aprovou, quando, com que evidência, e o antes e depois das alterações |
| `validation/questions.yml` | CQs reservadas espelhadas automaticamente, com `expects` e `answer` |
| `akme/static/` | A página (HTML, CSS, JS, fontes e marca); `akme export` copia para `docs/` e gera `docs/ontology.js` |

### 4.6 Ver a página

- **Editável:** `uv run akme review` e abrir `http://127.0.0.1:8765`; `--background` sobe sem
  prender o terminal e imprime a URL (é o que o agente usa via `open_review`). Só aceita conexões da
  própria máquina e só do próprio navegador (checa origem).
- **Só leitura:** `uv run akme export` e abrir `docs/index.html` do disco. Mostra tudo, mas não
  decide nem aplica.
- **Etapa atual:** `uv run akme stage` diz em que etapa das seis o projeto está e o próximo passo.

## 5. Demonstração em dois minutos

```bash
uv run akme init --demo      # distribuidora de materiais de construção, dados em examples/local_demo
uv run akme demo             # connect, profile, seed (caso de uso, CQs, lacuna, divergência, classes), validate, export
uv run akme review           # abre a página: Revisão com o já aplicado e Ontologia com o grafo
```

A Revisão da demo não começa com fila: mostra em "Aplicadas" o caso de uso, as CQs, a lacuna e a
divergência já aplicados pelo seed. Para ver a fila, peça ao agente "proponha dez CQs novas para a
demo": elas aparecem na página sem recarregar.

## 6. O que ainda não foi feito

O diagnóstico listou mais do que a etapa 1. Continuam em aberto, por ordem de prioridade:

1. **Avaliação pelo resultado**: rodar as CQs reservadas contra os dados com gabarito SQL. Hoje o
   `eval` é estrutural.
2. **Cobertura de CQs** no `validate`: quais CQs aprovadas ainda não têm classe, termo ou mapping.
3. **Databricks como metric view**. A publicação Snowflake já sai com chaves primárias e `RELATIONSHIPS`
   a partir dos contratos de relação.
4. **Edição e remoção** de classes, termos e mappings (hoje só CQs, lacunas e divergências têm
   `update`/`remove`; na página, as propostas de classe, relação e termo aceitam ajuste de texto
   antes de aceitar, mas domínio, range, multiplicidade e junção exigem nova proposta).
5. **Reuso com substância**: ler a definição do termo na LOV e registrar alinhamentos.
6. Raciocinador (HermiT) como portão de consistência; atributos e disjunção no modelo.

## 7. Referências

- Guia metodológico do grupo: `github.com/capstone-insper/202602_MCKINSEY_DiagnosticEngineDataRequest_Docs`
- Base metodológica detalhada: `docs/research/lot-neon.md`
- Diagnóstico: `docs/diagnostico-2026-10-30.md`
- Desenho desta etapa: `docs/superpowers/specs/2026-10-30-revisao-de-requisitos-design.md`
- Roteiro do agente: `SKILL.md`
