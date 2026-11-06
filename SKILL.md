---
name: akme
description: Constroi, valida e publica uma ontologia e uma camada semantica sobre a base de dados de um cliente seguindo LOT + NeOn com humano no loop. Use quando o consultor pedir para mapear um dominio, criar termos, mappings ou perguntas de competencia, validar a ontologia ou publicar a camada semantica. As tools do servidor MCP akme sao deterministicas; o raciocinio fica com voce e toda escrita passa por aprovacao humana.
---

# AKME: ontologia e camada semantica com humano no loop

## Objetivo

Levar o consultor do primeiro contato com os dados do cliente ate uma camada semantica publicada, construindo no caminho uma ontologia versionada em texto (`ontology/schema.ttl`, `ontology/content.yml`). O fluxo segue as fases do LOT (especificacao, implementacao, publicacao, manutencao) com as atividades da NeOn que o LOT nao cobre (reuso, alinhamento, reengenharia de recursos nao ontologicos). A base metodologica esta em `docs/research/lot-neon.md`; nao invente etapas que nao estejam la.

## Regras que nunca mudam

1. **Nada entra na ontologia sem aprovacao explicita do humano.** Toda escrita passa por `propose_edit` (grava em `ontology/pending/`) e so vira ontologia com `apply_edit`, que exige o nome de quem aprovou. Nunca chame `apply_edit` sem o humano ter dito "aprovado" para aquela edicao especifica nesta conversa. `apply_reviewed` so pode ser chamado depois de voce mostrar o resumo das decisoes lidas em `list_pending` e o humano responder 'aplica' com o nome de quem aprova. O caminho normal e `decide_pending`: o humano decide cada pendente num formulario do proprio harness e, no ultimo formulario, confirma "Aplicar agora" com o nome de quem aprova. Quando `decide_pending` volta com `status: applied`, isso vale como aprovacao; nao peca "aplica" de novo.
2. **`validate` roda antes de todo `apply_edit`.** Se houver erro, mostre ao humano e proponha correcao em vez de aplicar.
3. **Nunca responda de memoria sobre a ontologia.** Use `list_entities`, `list_relations`, `search_term`, `resolve_acronym`, `get_precedence`, `get_requirements` e `list_competency_questions` para saber o que existe.
4. **Toda proposta carrega proveniencia.** Preencha `requirement_id` (a CQ que motiva) e `evidence` (documento, tabela, coluna ou conversa de origem). O `apply_edit` grava isso em `changelog.yml` e na secao `evidence` do `content.yml`.
5. **`publish`, `apply_edit` e `apply_reviewed` sao acoes com aprovacao por chamada.** `publish` roda em dry-run por padrao; executar no alvo exige o humano confirmar na CLI.
6. **As tools nao chamam LLM.** O que exige julgamento semantico (redigir definicoes, propor classes, interpretar relatorios) e trabalho seu, sempre apresentado como proposta.
7. **Toda hipotese, ambiguidade ou conflito mostrado ao humano diz de onde veio.** Antes de apresentar, chame `find_in_sources` com o termo (siglas com `case_sensitive=true`) e cite cada ocorrencia relevante com o `path` devolvido, a pagina ou slide, ou a aba e a coluna, e um trecho curto entre aspas. Nunca cite de memoria. Se a tool nao encontrar o termo por extenso, diga isso e mostre onde ele aparece abreviado. Separe sempre o que esta escrito na fonte do que e hipotese sua. Toda CQ, lacuna e divergencia proposta carrega `evidence` com `kind: source` citando `path`, `locator` e `quote`; o que vem de conversa leva `kind: conversation`. Ver "Como apresentar ambiguidades".

## Roteiro visivel no harness

O humano acompanha o fluxo pela lista de tarefas do harness, nao pelo texto das suas respostas. Mantenha essa lista sempre igual ao estado real:

1. **Ao comecar** (e ao retomar uma conversa), chame `stage`. Crie a lista de tarefas do harness com as seis etapas (`Etapa 1 de 6: Especificar` ... `Etapa 6 de 6: Manter`), marque as anteriores a atual como concluidas e, logo abaixo da etapa atual, um item por passo do `checklist` que `stage` devolve. No Claude Code use a ferramenta de lista de tarefas (TodoWrite ou a lista do app); num harness sem lista, escreva o mesmo checklist em markdown (`- [x]` / `- [ ]`) no inicio da resposta.
2. **Cada passo do `checklist`** tem `text`, `tools` e `done`: `true` ou `false` vem do estado em disco e nao se discute; `null` e um passo que so voce sabe se fez (ex: consultar a LOV), marque quando fizer. Nao pule passo: se um `false` ficar para tras, volte nele ou diga ao humano por que ele nao se aplica.
3. **Ao terminar cada passo**, marque na lista antes de comecar o proximo. Ao mudar de etapa, chame `stage` de novo e troque os passos pelos da etapa nova.
4. Comece cada resposta com uma linha curta de onde voce esta: `Etapa X de 6 · passo: <texto do passo>`.

## Decisoes no chat e a pagina so de visualizacao

As decisoes do humano acontecem no proprio chat, em formularios que o harness desenha (MCP elicitation). A pagina web servida por `akme review` (127.0.0.1:8765) e so a visualizacao da ontologia: grafo, termos, cobertura e pitfalls; ela nao tem mais fila de decisao. Regras para voce:

- **Em toda parada "Pare e pergunte" das etapas 1, 2 e 3**, depois de gravar as propostas:
  1. Mostre no chat so a lista curta (titulo e tipo de cada proposta) e diga em uma linha que os formularios vao abrir.
  2. Chame `decide_pending` com o `stage` da etapa (`requirements` na etapa 1, `ontology` nas etapas 2 e 3). A tool pede o nome do revisor, pergunta se ele quer decidir uma a uma ou aceitar todas como propostas, abre um formulario por pendente (com a evidencia, o que o dado mostra e os campos editaveis) e, no fim, pergunta se aplica agora e quem aprova.
  3. Com `applied`: resuma em poucas linhas o que entrou (`applied`, `rejected`, `applied_types`, `approved_by`; se `held_by_gate`, `pending` ou `skipped` tiverem itens, diga quantos ficaram de fora e por que), atualize a lista de tarefas com o `checklist` devolvido e siga direto para o proximo passo.
  4. Com `decided` (decidiu mas escolheu aplicar depois), `postponed` (escolheu "Agora nao") ou `cancelled`: diga em uma linha o que ficou pendente e pergunte quando quer retomar; ao retomar, chame `decide_pending` de novo (ele so traz o que falta e oferece aplicar o que ja foi decidido).
  5. Com `apply_failed`: mostre os `new_errors` do validate, proponha a correcao com `propose_edit` e chame `decide_pending` de novo.
  6. Com `no_elicitation`: este harness nao desenha formularios. Mostre cada item de `items` (o campo `text` ja vem pronto), pergunte a decisao (use a ferramenta de perguntas do harness, se houver; senao, "aprovado" ou "rejeitado com motivo" item a item), grave cada resposta com `review_edit`, mostre o resumo, peca "aplica" com o nome de quem aprova e so entao chame `apply_reviewed`.
- **Ao retomar uma conversa**, leia `list_pending`: se ha pendentes sem decisao ou decididos sem aplicar, chame `decide_pending`.
- **Para o humano ver a ontologia**, chame `open_ontology` e diga a URL em uma linha. Ela se atualiza sozinha quando algo e aplicado. Faca isso no fim das etapas 2 e 3 e na etapa 5.
- **No fim de cada etapa**, chame `stage`, atualize a lista de tarefas e termine a resposta com: "Etapa X de 6 concluida. Proximo passo: ...".
- Nunca aponte o humano para o arquivo `docs/index.html`: aponte sempre para a URL local.

## Preparacao

```
akme init                                            (local_folder lendo a pasta data/)
akme init --adapter local_folder --path <pasta>      (outra pasta; ou postgres, snowflake, databricks)
akme connect
```

Se `connect` falhar por falta de extra, instrua: `uv sync --extra <adapter>`. Para a demo: `akme init --demo` e `akme demo`.

Por padrao os dados do cliente ficam em `data/`, cujo conteudo o git ignora; nunca sugira commitar arquivos dessa pasta. O adapter `local_folder` percorre subpastas e aceita uma lista de pastas em `path`. Planilhas `.csv` e `.xlsx` viram fontes; cada aba de um `.xlsx` com mais de uma aba vira uma fonte separada. O nome da fonte junta pastas, arquivo e aba com `__` (ex: `vendas__2026__pedidos__janeiro`) e o campo `origin` do profile guarda o caminho real. Documentos `.md`, `.txt`, `.pdf`, `.docx` e `.pptx` sao lidos por pagina ou slide. `.xlsx`, `.docx` e `.pptx` exigem `uv sync --extra office`; `.pdf` exige `--extra pdf`. Formatos antigos (`.xls`, `.doc`, `.ppt`) nao sao lidos: peca ao consultor para salvar no formato novo.

## Fluxo em seis etapas

Cada etapa diz quais tools chamar, o que voce produz e onde parar para o humano decidir. A classificacao vem da tabela da secao 5 de `docs/research/lot-neon.md`.

### 1. Especificar (LOT: especificacao de requisitos)

Tools: `connect`, `profile`, `read_document`, `find_in_sources`, `get_requirements`, `list_competency_questions`, `propose_edit` com `add_use_case`, `add_requirement`, `add_competency_question`, `add_gap`, `add_divergence`, `add_glossary`; `decide_pending`, `open_ontology`, `list_pending`, `requirements_status`, `apply_reviewed`, `stage`.

1. Pergunte o caso de uso (ou constate que `get_requirements` ja traz um em `use_cases`; nesse caso nao pergunte de novo): nome, descricao, atores e fluxo. Proponha `add_use_case`. Se o humano disser que nao tem, registre o motivo com `add_requirement` no campo `no_use_case`, avise que as CQs sairao mais genericas e siga.
2. Rode `profile`. Leia fontes, colunas, tipos, nulos, chaves candidatas e convencoes detectadas. O profile traz so um excerto de cada documento: para o conteudo completo, chame `read_document` sem `page` para ver o indice e depois pagina a pagina. Use `find_in_sources` nos termos que aparecerem. Cite arquivo e pagina na `evidence` (ex: `contratos/glossario.docx, pagina 3` ou `kickoff.pptx, slide 2`).
3. Proponha proposito, escopo e usuarios (`add_requirement` com `field` purpose, scope ou users). Diferencie o que esta explicito nos documentos do que e hipotese sua.
4. Proponha exatamente dez CQs (`add_competency_question`), distribuidas entre os seis tipos: `classificacao_hierarquia`, `relacao_entre_conceitos`, `atributos`, `quantidade_agregacao`, `tempo_estado`, `regras_restricoes`. O ideal e duas por tipo; se o dominio nao sustenta um tipo, diga qual e por que. Cada CQ leva `question`, `type`, `concepts` e `evidence` com ao menos um `{kind: source, path, locator, quote}`; `use_cases` e opcional. O `id` e o `status: proposed` o servidor preenche. Siga a regra do LOT: pergunta quando ha interrogacao de negocio, frase quando e fato, tabela quando e lista de atributos. Em seguida proponha as lacunas (`add_gap`: perguntas que o caso de uso sugere e os dados nao respondem) e as divergencias (`add_divergence`: fontes que discordam), cada uma com evidencia.
5. Mostre no chat so a lista curta (id, pergunta, tipo) e diga que os formularios de decisao vao abrir.
6. Chame `decide_pending` com `stage: requirements` (ver "Decisoes no chat e a pagina so de visualizacao"). Com `applied`, resuma as decisoes (quantas CQs aceitas e rejeitadas; lacunas e divergencias decididas) e siga para o passo 7.
7. Proponha o glossario (`add_glossary`) para siglas vistas em `profile.conventions.acronyms_found` e nos documentos. As entradas ficam pendentes e o humano decide com `decide_pending`; a etapa so fecha depois que elas forem aplicadas. Se menos de cinco CQs foram aceitas, ofereca uma segunda rodada de ate dez, sem repetir as rejeitadas.

**Pare e pergunte:** o humano decide nos formularios de `decide_pending` (claro, completo, sem ambiguidade, prioridade, quais CQs sao usadas na construcao e quais ficam guardadas para o teste). Nao transforme hipotese em regra. Mesmo depois do "aplica", a etapa so termina quando `requirements_status` diz `closed`.

Saida: `use_cases`, CQs com status, `gaps`, `divergences`, `requirements` e `glossary` no `content.yml`; CQs reservadas espelhadas em `validation/questions.yml`. Se nao ha nenhuma reservada, diga ao humano: o eval nao testara pelo resultado; a etapa 4 fica so com verificacao formal.

### 2. Conceitualizar (LOT: implementacao, conceitualizacao e reuso)

Tools: `requirements_status`, `list_entities`, `list_relations`, `search_term`, `search_registry`, `propose_edit` com `add_class`, `add_relation`, `add_term`; `decide_pending`, `open_ontology`, `list_pending`, `apply_reviewed`, `stage`.

0. Chame `requirements_status`; se `closed` for falso, volte a etapa 1 e mostre `missing` ao humano. Enquanto estiver aberto e a ontologia nao tiver classe de dominio, `propose_edit` recusa classes, relacoes, termos, mappings, constraints e precedencias.
1. Leia o modelo atual com `list_entities` e `list_relations` antes de propor qualquer coisa.
2. A partir das CQs aprovadas e do `profile`, proponha classes (subclasses de `Entity`, `Metric`, `Rule` ou `Relation`), relacoes com domain, range e inversa, e termos ligados a cada classe. Associe cada proposta ao `requirement_id`.
   - Toda relacao leva o contrato: `multiplicity` lida de domain para range (`many_to_one`, `one_to_many`, `one_to_one` ou `many_to_many`) e `join` com `from` (fonte e coluna do domain) e `to` (fonte e coluna do range), ex: `join: {from: {source: pedidos, column: id_cliente}, to: {source: clientes, column: id_cliente}}`. Relacao sem join fisico (conceitual ou via tabela ponte) leva `no_join_reason`. Nome de coluna igual nao prova join.
   - `propose_edit` le o dado e grava em `observed` nulos, chaves repetidas, orfaos e a multiplicidade observada. Se o lado declarado `one` tiver chave repetida, a proposta e recusada; corrija a multiplicidade. So use `override_reason` quando o humano confirmar que o dado esta errado, nunca para destravar a proposta. Mostre `observed` ao humano junto com a proposta.
   - Termo de classe `Metric` (ou subclasse) leva o contrato da medida: `unit` (BRL, unidades, %), `grain` (o que e uma linha, ex: um pedido) e `additivity` (`additive`, `semi_additive` com `non_additive_over`, ou `non_additive`). Quantidade, razao, media e taxa sao medidas diferentes; razao de totais nao e media de razoes.
3. Quando a conceitualizacao estiver estavel, consulte `search_registry` para termos reutilizaveis na LOV. Compare definicao com definicao, nao nome com nome. Se nao houver rede, registre que o reuso ficou pendente.
4. Sinalize termos ambiguos, sobreposicoes e CQs ainda sem classe que as atenda.

**Pare e pergunte:** chame `decide_pending` com `stage: ontology`; o humano aceita, ajusta ou rejeita cada classe, relacao e termo no formulario (ele mostra o `observed` e os alertas de fanout e orfaos) e aplica. Com `applied`, resuma, chame `open_ontology` para ele ver o grafo e siga para a etapa 3. Nomes de classe em PascalCase, de relacao em lowerCamelCase.

Saida: classes e relacoes em `schema.ttl`, termos em `content.yml`.

### 3. Codificar (LOT: implementacao, codificacao)

Tools: `propose_edit` com `add_mapping`, `add_constraint`, `add_precedence`; `validate`; `decide_pending`, `open_ontology`, `list_pending`, `apply_reviewed`, `apply_edit`, `stage`.

1. Para cada termo, proponha o mapping para `tabela.coluna` do `profile`. Metricas levam `role: metric` e `expression` SQL explicita; nao existe `SUM` implicito. Uma metrica no grao da fonte do lado `one` de uma relacao nao pode ser somada depois de juntar com o lado `many` (fanout): o `publish` registra isso em `do_not_sum_after_join_with`.
2. Proponha `add_constraint` para regras implicitas achadas nos documentos (ex: faturamento so com status FATURADO) e `add_precedence` quando duas fontes divergem sobre o mesmo conceito, dizendo qual prevalece e por que.
3. Rode `validate`. Corrija o que for erro antes de pedir aprovacao.

**Pare e pergunte:** chame `decide_pending` com `stage: ontology`; os mappings, restricoes e precedencias aparecem no formulario com a evidencia de cada um. O humano aceita, rejeita com motivo ou ajusta, e aplica. Com `applied`, resuma e siga para a etapa 4.

Saida: `mappings`, `constraints` e `precedence` aplicados; `changelog.yml` atualizado.

### 4. Avaliar (LOT: implementacao, avaliacao)

Tools: `validate` (com `oops=true` quando houver rede), `eval`, `export`.

1. Rode `validate` e leia findings, cobertura e pitfalls (ver "Como interpretar o validate").
2. Rode `eval`. Os `expects` de cada pergunta sao testes estruturais; `fail` significa que a ontologia nao sustenta a pergunta.
3. Para a comparacao com e sem ontologia, peca ao consultor para rodar `akme eval --callable modulo:funcao` com o agente dele (ver "Como interpretar o eval").
4. Interprete os relatorios e proponha correcoes como novos `propose_edit`. Nunca aplique correcao sem voltar ao passo de aprovacao.

**Pare e pergunte:** o humano decide se volta para a etapa 2 ou 3, ou se segue para publicar. A decisao final de qualidade e humana; o validate e o eval sao verificadores externos, nao juizes.

### 5. Publicar (LOT: publicacao)

Tools: `export`, `open_ontology`, `publish`, `stage`.

1. Chame `open_ontology` e aponte o humano para a URL local (grafo, termos, cobertura e pitfalls).
2. Rode `publish --target <alvo>` em dry-run e mostre o artefato gerado (`docs/publish/`). Alvos: `snowflake` (semantic view com `PRIMARY KEY` e `RELATIONSHIPS` tirados dos contratos de relacao, e comments), `databricks` (comments do Unity Catalog), `yaml` (camada generica), `rdf` (YARRRML e, com o extra `rdf`, materializacao via Morph-KGC).
3. Se o humano quiser versao nova, use `--release patch|minor|major`.
4. Documentacao em HTML (Widoco) e checklist FAIR (FOOPS!) ficam fora do template; cite os comandos de `docs/research/oeg-upm.md` quando o cliente pedir.

**Pare e pergunte:** executar no alvo (`--no-dry-run`) e acao publica e irreversivel. Nunca execute sem o humano confirmar nesta conversa e na CLI.

### 6. Manter (LOT: manutencao)

Tools: `validate`, `eval`, `propose_edit`, `apply_edit`, `publish --release`.

1. Toda mudanca comeca com um registro: uma issue no repositorio do cliente ou uma CQ nova (`add_competency_question`). Sem registro, nao ha edicao.
2. Classifique o pedido: bug (volta para a etapa 3), requisito novo (volta para a etapa 1), mudanca na fonte (rode `profile` de novo e verifique mappings quebrados no `validate`).
3. Liste o impacto: CQs, termos, mappings e publicacoes afetadas.

**Pare e pergunte:** o humano decide o escopo da mudanca e quando ela entra em release.

## Como apresentar ambiguidades

Divergencias entre fontes viram `add_divergence` (`topic`, `sources` com duas ou mais `{label, path, locator, quote}`, `hypothesis`) e o que os dados nao respondem vira `add_gap` (`question`, `reason`, `missing`, `evidence`). Ambos sao decididos pelo humano nos formularios de `decide_pending`; o chat mostra so a lista curta (id, tema ou pergunta, fontes em uma linha). Cada item tem: o termo, o problema em uma frase, as fontes com caminho e trecho, a sua hipotese marcada como hipotese, e uma pergunta fechada para o humano. O caminho e o que o humano usa para abrir o arquivo e conferir. Exemplo:

```
Ambiguidades que encontrei:

1. CC e EX: nao aparecem por extenso em nenhum documento.
   Onde aparecem:
   - data/alunos.xlsx, aba Matriculas, coluna curso: 42 linhas (valores CC, EX)
   Hipotese minha, sem fonte: CC = Ciencia da Computacao, EX = Engenharia Mecatronica.
   Pergunta: esta certo?

2. MG: dois significados no mesmo documento.
   - data/plano_de_ensino.pdf, pagina 4: "...a MG (Media de Grupo) compoe 40% da nota..."
   - data/plano_de_ensino.pdf, pagina 9: "...aprovado com MG, a media geral, igual ou superior a 6..."
   Pergunta: qual significado vale para a ontologia, ou sao dois termos diferentes?

3. Carga horaria: duas fontes divergem.
   - data/regulamento.docx, pagina 2: "...carga horaria total de 360 h..."
   - data/site_curso.md: "...300 horas de atividades..."
   Sugestao: o Regulamento prevalece, e isso vira uma regra de precedencia na etapa 3 (a divergencia fica como `add_divergence` com decisao `precedence`).
   Pergunta: concorda?
```

Use o mesmo conteudo na `evidence` do `propose_edit` (ex: `{kind: source, path: data/regulamento.docx, locator: pagina 2, quote: "carga horaria total de 360 h"}`), para que a origem fique gravada no `changelog.yml` e no `content.yml`. Quando houver mais de uma evidencia para a mesma proposta, grave uma lista JSON (`[{...}, {...}]`), nunca objetos concatenados com `;`.

## Como interpretar o validate

| Campo | O que significa | O que fazer |
|---|---|---|
| `findings` nivel `error` | TTL nao parseia, termo aponta para classe inexistente, mapping para coluna inexistente, precedencia contraditoria | Bloqueia `apply_edit` e `publish`. Proponha correcao |
| `findings` nivel `warning` | Profile ausente, pergunta do eval sem CQ registrada | Rode `profile` ou registre a CQ |
| `cq_reserved_without_answer` (error) | CQ `reserved` sem `answer` | Proponha `update_competency_question` com a resposta esperada |
| `cq_approved_without_priority` (error) | CQ `approved` sem `priority` | Proponha `update_competency_question` com `priority` |
| `cq_agent_without_source_evidence` (error) | CQ proposta pelo agente sem item `kind: source` na `evidence` | Proponha a correcao com `path`, `locator` e `quote` da fonte |
| `no_reserved_cq` (warning) | Nenhuma CQ `reserved` | Avise o humano: o eval nao testara pelo resultado |
| `open_gap_or_divergence` (warning) | Lacuna ou divergencia com `decision: open` | Leve ao humano com `decide_pending` |
| `relation_without_contract` (warning) | Relacao sem `multiplicity` nem `join` (criada antes dos contratos) | Proponha a relacao de novo com o contrato |
| `multiplicity_mismatch` (error; warning com `override_reason`) | O dado contradiz a multiplicidade declarada: lado `one` com chave repetida | Corrija a multiplicidade ou leve ao humano; nao publique com fanout escondido |
| `join_broken` (error) | Fonte ou coluna do join sumiu | A fonte mudou; volte a etapa 3 |
| `join_orphans` / `join_nulls` (warning) | Chaves do domain sem par no range, ou chave nula | Mostre os exemplos ao humano; podem ser dado sujo ou filtro de negocio |
| `metric_without_contract` / `metric_without_expression` (error) | Metrica sem `unit`, `grain` ou `additivity`, ou mapping sem `expression` | Proponha o contrato completo; o `publish` recusa metrica sem expression |
| `coverage` | Colunas do profile cobertas por mappings, por fonte, com a lista das nao cobertas | Colunas nao mapeadas sao candidatas a termo ou devem ser marcadas fora de escopo com o humano |
| `pitfalls` | Subconjunto do catalogo OOPS! calculado localmente: P04 elemento desconectado, P08 sem label ou comment, P11 relacao sem domain ou range, P13 relacao sem inversa, P22 nome fora da convencao, P41 sem licenca | `important` corrige antes de publicar; `minor` registra e decide com o humano |
| `oops` | Resultado do servico remoto quando `oops=true`; `available=false` quando o servico esta fora do ar | Nao bloqueie o fluxo por indisponibilidade; repita mais tarde |

## Como interpretar o eval

- `structural`: `pass` quando todos os `expects` da pergunta valem no `schema.ttl`; `fail` lista o que falta (classe, subclasse, relacao ou dominio errado); `n/a` quando a pergunta nao tem `expects`.
- `without_ontology` e `with_ontology` aparecem so na CLI com `--callable`. A funcao recebe `(pergunta, contexto)` e o contexto e `None` na primeira chamada e o resumo da ontologia na segunda. `answer` em `questions.yml` e o trecho que a resposta precisa conter.
- Leia o resumo: `with_correct` maior que `without_correct` indica que a ontologia esta ajudando; igual ou menor indica termos, mappings ou precedencia faltando. Uma pergunta nunca e exemplo e gabarito ao mesmo tempo: CQs com `status: approved` entram como exemplos no `publish`, as reservadas ficam so no eval.

## Ferramentas do OEG citadas, nao integradas

Widoco (documentacao HTML, exige Java), OnToology (publicacao com w3id), Chowlk (diagrama para OWL), Astrea (SHACL a partir de OWL), FOOPS! (checklist FAIR), Themis e OOPS! como servicos remotos, yatter e RMLdoc (RML), OntoRipple (propagacao de mudancas), CORAL e CQ4OE (padroes de CQ). Detalhes e comandos em `docs/research/oeg-upm.md`.
