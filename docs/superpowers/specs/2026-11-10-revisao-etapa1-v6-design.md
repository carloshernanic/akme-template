# Revisão da etapa 1 no formato do protótipo v6: design

Data: 10/11/2026. Branch: `design-perguntas-competencia`.

Referência visual: `docs/design/revisao/v6-prototipo.html`. O histórico das versões está em `docs/design/revisao/` (v1 a v6, com feedback de três usuários simulados no v1).

## Intenção

O revisor da etapa 1 hoje decide uma proposta por vez numa caixa de entrada. Cada cartão tem muitos campos e muito texto. O redesenho troca a parte da etapa 1 da aba Revisão por três telas em sequência:

1. Caso de uso.
2. Perguntas de competência.
3. Lacunas e divergências.

As três seguem a mesma regra: cada item mostra só o necessário para decidir, o resto fica em "ver detalhes", e o item decidido vira uma linha fina com "rever". O revisor também cria as próprias perguntas, com uma caixa clara no topo da tela de perguntas. No fim, ele confere um resumo e salva com o próprio nome.

O porquê, nas palavras do usuário ao longo da conversa: "tem muito texto", "deixar mais simples", "o usuário também cria as CQ", "deixe claro o que deve ser preenchido".

## Objetivos

- Etapa 1 em três telas com stepper no topo: caso de uso, perguntas, lacunas e divergências. Dá para navegar livremente pelo stepper, mas salvar só fica liberado com as três completas.
- O card enxuto (v5/v6) vale para perguntas, lacunas e divergências.
- Criar uma pergunta própria pela caixa "Criar pergunta" (pergunta + caso de uso + Adicionar). A pergunta entra como aceita e pede tipo e prioridade.
- Obrigatórios visíveis: a etiqueta "obrigatório", a borda amarela enquanto o campo está vazio, "Falta: …" no card e no rodapé, e o botão de avançar que explica o que falta quando é clicado.
- Nada pré-selecionado pela IA. A sugestão dela aparece como dica.
- "Conferir e salvar" abre um resumo e pede o nome de quem aprova.

## Não-objetivos

- Não muda as telas e cartões das etapas 2 a 5 (classes, relações, termos, mappings, restrições, precedências, exportação Neo4j). Elas seguem no `genericCard` e na caixa de entrada atual.
- Não muda a aba Ontologia (o grafo).
- Escala para centenas de itens (filtro, atalhos novos) e a revisão completa de acessibilidade ficam fora. Ainda assim, o que o protótipo já tem (botões reais, `aria-pressed`, `label`, `aria-live`, foco) deve vir junto.

## Anti-objetivos (seria fracasso mesmo funcionando)

- Voltar a encher o card de rótulos e metadados.
- Permitir salvar com a etapa 1 incompleta, ou aprovar sem nome.
- Quebrar a revisão das etapas 2 a 5 ou o fluxo do agente (`open_review`, `wait_for_review`, `apply_reviewed`).
- A IA decidir pelo humano por padrão (itens pré-marcados).

## Restrições

- HTML/CSS/JS puro em `akme/static/`, sem build e sem dependência nova. `docs/` é cópia gerada pelo `akme export`.
- Os tokens QBDS já em `akme.css` (cantos retos, Inter/Roboto Mono, acento QB só no foco ou seleção). Tema claro e escuro.
- Texto voltado ao usuário em português; código e comentários em português sem acento.
- Toda escrita continua indo por `/api/review` e `/api/propose` para `ontology/pending/`, e só é aplicada com nome via `/api/apply`. A proveniência no `changelog.yml` não muda.
- As tools não chamam LLM.
- `tests/test_docs_page.py` testa strings e ids. Ele deve ser atualizado junto, sem remover os ids que o resto da página usa.

## Como fica (decidido com o usuário)

### Tela 1: caso de uso

- Os casos de uso propostos pela IA (`add_use_case` pendentes) aparecem como cards selecionáveis. Cada card mostra nome, uma frase, quem usa e a fonte. Nenhum vem marcado.
- "+ Escrever o meu caso de uso" pede só **nome** e **uma frase**.
- É obrigatório escolher ao menos um.
- As perguntas da tela 2 ficam agrupadas pelos casos escolhidos. As de casos não escolhidos vão para "Fora dos casos escolhidos" e não pedem decisão.

### Tela 2: perguntas de competência

- No topo, a caixa "Criar pergunta": campo da pergunta, caso de uso e "+ Adicionar" (Enter também adiciona). A pergunta criada entra no grupo com a marca "sua", já como aceita, e pede tipo (obrigatório), conceitos (opcional) e prioridade (obrigatória). Pode ser removida.
- Card da IA:
  - mostra a pergunta e um sinal da IA em uma linha, com "ver detalhes" (id, tipo, conceitos, evidência e aviso de dependência);
  - tem os botões grandes ✓ Aceitar e ✕ Rejeitar;
  - aceitar pede prioridade, com a dica "A IA sugere X" quando houver;
  - rejeitar pede um motivo entre Pouco clara, Fora do caso de uso, Os dados não respondem, Repetida e Outro motivo (este pede texto).
- O card decidido vira uma linha: ✓ ou ✕, a pergunta, a prioridade ou o motivo e "rever". O card recolhe sozinho quando a decisão fica completa. "Outro motivo" fecha por "recolher".
- O campo **Uso (Construção/Teste) sai da tela**, e com ele a resposta esperada. Toda pergunta aceita vira `approved`.
- Contador "N sugestões da IA para avaliar". Listas "Fora dos casos escolhidos" e "Já aplicadas", estas com prioridade, quem aprovou e quando.

### Tela 3: lacunas e divergências

- **Lacuna:**
  - mostra a pergunta e o motivo em uma linha ("● os dados não têm …"), com "ver detalhes";
  - tem quatro botões: Pedir o dado ao cliente, Reformular a pergunta, Descartar e Deixar em aberto;
  - "Reformular" pede a nova pergunta, e "Descartar" e "Deixar em aberto" pedem o motivo;
  - quando a escolha pede texto, o card fecha por "Concluir"; sem texto, fecha na hora.
- **Divergência:**
  - o título é "Qual definição de '<tópico>' vale?";
  - as fontes aparecem como botões grandes com rótulo e trecho, e clicar numa decide;
  - abaixo do título fica uma linha com a sugestão da IA (quando houver), as perguntas afetadas e "ver detalhes";
  - "nenhuma das duas? outras opções" revela São coisas diferentes (pede o que diferencia), Perguntar ao especialista e Deixar em aberto (pede o motivo).
- O motivo deixou de ser exigido em toda decisão. Ele só aparece nas saídas de escape e quando é preciso escrever algo novo (decisão do usuário ao aprovar o v6).

### Salvar

- "Conferir e salvar" na tela 3 só libera com as três telas completas.
- O resumo mostra: casos escolhidos, perguntas aceitas, rejeitadas (com motivo), escritas por você, e a decisão de cada lacuna e divergência.
- Pede o nome (obrigatório). Hoje o nome fica em `localStorage` `akme-reviewer` e deve continuar pré-preenchido.

## O que fica a cargo de quem implementar

- A estrutura interna do JS: substituir as funções só da etapa 1 (`pendingCqCard`, `appliedCqCard`, `newCqCard`, `gapCard`, `divCard`, `cqEditFields`, `cqDecisionFields`, `cqProposalRead`, `contextHtml`, `cqError`) mantendo os helpers e a infraestrutura comuns (`save`, `openApply`, `poll`, `renderStage`, `renderRound`).
- O mapeamento das decisões da página para os payloads atuais de `/api/review` e `/api/propose`:
  - aceitar CQ vira `accept` com `edits.status=approved` e `priority`;
  - rejeitar CQ vira `reject` com `reason` = rótulo do motivo + texto;
  - lacuna vira `accept` com `edits.decision` e `note`;
  - divergência vira `accept` com `decision=precedence` e `winner`, ou com outra decisão e `reason`.
- Usar os ids e o markup que mantêm `tests/test_docs_page.py` e o restante da página funcionando, atualizando o teste onde as strings mudaram ("Usar na construção" e "Guardar para o teste" saem).

## Decisões do usuário depois do builder check (10/11)

1. **"Conferir e salvar" grava e aplica num clique só.** Grava as decisões da etapa 1 (`/api/review` e `/api/propose`) com o nome informado no resumo e chama `/api/apply` com `stage: "requirements"` e esse nome como `approved_by`.
   - O agente que espera em `wait_for_review` recebe a resposta na hora.
   - O nome é pedido só no resumo e usado como `reviewer` e `approved_by`. Ele vem pré-preenchido do `localStorage`.
   - As etapas 2 a 5 continuam com Salvar e depois Aplicar.
2. **O "Uso" só sai da tela.** Toda pergunta aceita ou criada na página vira `approved`. O sistema continua aceitando `reserved` (agente e CLI), com validate, `validation/questions.yml` e eval intactos. As reservadas já aplicadas aparecem em "Já aplicadas" com a marca "teste".
   - O SKILL deixa de pedir ao humano que escolha quais perguntas guardar para teste na página.
   - O aviso "sem reservada, o eval não testa pelo resultado" continua.
3. **Os sinais da IA vêm do agente,** como campos novos e opcionais na proposta:
   - `add_competency_question`: `data_check` (texto curto; começa com "sim" quando os dados respondem, ou explica o que falta), `depends_on` (lista de ids de divergência) e `priority` (já existe, opcional), que passa a ser a prioridade sugerida;
   - `add_divergence`: `suggestion` (`winner` sugerido + justificativa curta). As perguntas afetadas vêm do `depends_on` das CQs.
   - Validação em `_validate_payload`, com chaves aceitas onde for preciso. O SKILL manda o agente preencher os campos. Testes cobrem os campos.
   - Sem o campo, o card mostra no lugar do sinal a fonte da primeira evidência (arquivo · coluna). Nada quebra para propostas antigas.
4. **A tela 1 também traz propósito, escopo e usuários, e o agente propõe de 2 a 3 casos de uso.**
   - Os pendentes `add_requirement` (purpose, scope, users) aparecem na tela 1 como cards enxutos. Cada um mostra o texto proposto e "✓ Aceitar", com "ajustar" para editar o texto antes de aceitar.
   - O SKILL, passo 1.1, passa a propor de 2 a 3 casos de uso tirados das fontes, em vez de perguntar um. O humano marca na página ou escreve o dele.
   - O glossário continua na caixa de entrada (passo 1.7, depois da revisão).

## Decisões minhas (o usuário pode revisar)

- **Casos de uso não marcados** são rejeitados ao salvar, com o motivo "não escolhido pelo revisor". **As perguntas pendentes ligadas só a casos não escolhidos** são rejeitadas com "fora dos casos escolhidos". As duas listas aparecem no resumo antes de confirmar. Assim o portão da etapa 1 fecha.
- **Pergunta sem `use_cases`** vai para o grupo "Sem caso de uso" e precisa de decisão.
- **Casos de uso já aplicados** aparecem na tela 1 como "já aprovado", contam para "ao menos um" e não são pré-marcações da IA.
- **"Não temos caso de uso"** fica como opção na tela 1. Ela pede uma frase e vira `add_requirement` `no_use_case`.
- **Divergência:** "Descartar" (`dismiss`) entra nas outras opções e pede o motivo.
- **Itens já aplicados** (perguntas, lacunas e divergências) aparecem como linhas. "ver detalhes" mantém "Propor alteração" e "Propor exclusão", usando o fluxo atual (`update_*`, `remove_competency_question`). As propostas `update_*` e `remove_*` vindas do agente seguem na caixa de entrada atual.
- **Quando as telas aparecem:**
  - com a etapa 1 aberta, a aba Revisão abre nas três telas;
  - com a etapa 1 fechada, ela abre na caixa de entrada das etapas 2 a 5;
  - um seletor no topo ("Etapa 1 · Outras propostas (n)") alterna entre as duas.
- **Tela vazia conta como completa.** Uma tela sem itens (por exemplo, sem lacunas nem divergências) mostra "Nada a decidir".
- **Regra do motivo:** o motivo só é pedido em Descartar, Deixar em aberto, São coisas diferentes e Outro motivo (CQ), e Reformular pede a nova pergunta. O servidor já não exige motivo para lacuna e divergência, então a mudança fica no JS.
