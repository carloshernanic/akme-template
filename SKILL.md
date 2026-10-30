---
name: akme
description: Constroi, valida e publica uma ontologia e uma camada semantica sobre a base de dados de um cliente seguindo LOT + NeOn com humano no loop. Use quando o consultor pedir para mapear um dominio, criar termos, mappings ou perguntas de competencia, validar a ontologia ou publicar a camada semantica. As tools do servidor MCP akme sao deterministicas; o raciocinio fica com voce e toda escrita passa por aprovacao humana.
---

# AKME: ontologia e camada semantica com humano no loop

## Objetivo

Levar o consultor do primeiro contato com os dados do cliente ate uma camada semantica publicada, construindo no caminho uma ontologia versionada em texto (`ontology/schema.ttl`, `ontology/content.yml`). O fluxo segue as fases do LOT (especificacao, implementacao, publicacao, manutencao) com as atividades da NeOn que o LOT nao cobre (reuso, alinhamento, reengenharia de recursos nao ontologicos). A base metodologica esta em `docs/research/lot-neon.md`; nao invente etapas que nao estejam la.

## Regras que nunca mudam

1. **Nada entra na ontologia sem aprovacao explicita do humano.** Toda escrita passa por `propose_edit` (grava em `ontology/pending/`) e so vira ontologia com `apply_edit`, que exige o nome de quem aprovou. Nunca chame `apply_edit` sem o humano ter dito "aprovado" para aquela edicao especifica nesta conversa. `apply_reviewed` so pode ser chamado depois de voce mostrar o resumo das decisoes lidas em `list_pending` e o humano responder 'aplica' com o nome de quem aprova.
2. **`validate` roda antes de todo `apply_edit`.** Se houver erro, mostre ao humano e proponha correcao em vez de aplicar.
3. **Nunca responda de memoria sobre a ontologia.** Use `list_entities`, `list_relations`, `search_term`, `resolve_acronym`, `get_precedence`, `get_requirements` e `list_competency_questions` para saber o que existe.
4. **Toda proposta carrega proveniencia.** Preencha `requirement_id` (a CQ que motiva) e `evidence` (documento, tabela, coluna ou conversa de origem). O `apply_edit` grava isso em `changelog.yml` e na secao `evidence` do `content.yml`.
5. **`publish`, `apply_edit` e `apply_reviewed` sao acoes com aprovacao por chamada.** `publish` roda em dry-run por padrao; executar no alvo exige o humano confirmar na CLI.
6. **As tools nao chamam LLM.** O que exige julgamento semantico (redigir definicoes, propor classes, interpretar relatorios) e trabalho seu, sempre apresentado como proposta.
7. **Toda hipotese, ambiguidade ou conflito mostrado ao humano diz de onde veio.** Antes de apresentar, chame `find_in_sources` com o termo (siglas com `case_sensitive=true`) e cite cada ocorrencia relevante com o `path` devolvido, a pagina ou slide, ou a aba e a coluna, e um trecho curto entre aspas. Nunca cite de memoria. Se a tool nao encontrar o termo por extenso, diga isso e mostre onde ele aparece abreviado. Separe sempre o que esta escrito na fonte do que e hipotese sua. Toda CQ, lacuna e divergencia proposta carrega `evidence` com `kind: source` citando `path`, `locator` e `quote`; o que vem de conversa leva `kind: conversation`. Ver "Como apresentar ambiguidades".

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

Tools: `connect`, `profile`, `read_document`, `find_in_sources`, `get_requirements`, `list_competency_questions`, `propose_edit` com `add_use_case`, `add_requirement`, `add_competency_question`, `add_gap`, `add_divergence`, `add_glossary`; `export`, `list_pending`, `requirements_status`, `apply_reviewed`.

1. Pergunte o caso de uso (ou constate que `get_requirements` ja traz um em `use_cases`; nesse caso nao pergunte de novo): nome, descricao, atores e fluxo. Proponha `add_use_case`. Se o humano disser que nao tem, registre o motivo com `add_requirement` no campo `no_use_case`, avise que as CQs sairao mais genericas e siga.
2. Rode `profile`. Leia fontes, colunas, tipos, nulos, chaves candidatas e convencoes detectadas. O profile traz so um excerto de cada documento: para o conteudo completo, chame `read_document` sem `page` para ver o indice e depois pagina a pagina. Use `find_in_sources` nos termos que aparecerem. Cite arquivo e pagina na `evidence` (ex: `contratos/glossario.docx, pagina 3` ou `kickoff.pptx, slide 2`).
3. Proponha proposito, escopo e usuarios (`add_requirement` com `field` purpose, scope ou users). Diferencie o que esta explicito nos documentos do que e hipotese sua.
4. Proponha exatamente dez CQs (`add_competency_question`), distribuidas entre os seis tipos: `classificacao_hierarquia`, `relacao_entre_conceitos`, `atributos`, `quantidade_agregacao`, `tempo_estado`, `regras_restricoes`. O ideal e duas por tipo; se o dominio nao sustenta um tipo, diga qual e por que. Cada CQ leva `question`, `type`, `concepts` e `evidence` com ao menos um `{kind: source, path, locator, quote}`; `use_cases` e opcional. O `id` e o `status: proposed` o servidor preenche. Siga a regra do LOT: pergunta quando ha interrogacao de negocio, frase quando e fato, tabela quando e lista de atributos. Em seguida proponha as lacunas (`add_gap`: perguntas que o caso de uso sugere e os dados nao respondem) e as divergencias (`add_divergence`: fontes que discordam), cada uma com evidencia.
5. Rode `export` e diga ao humano: "rode `akme review` e abra a aba Revisao". Mostre no chat so a lista curta (id, pergunta, tipo); o detalhe e a decisao ficam na aba.
6. Pare. Quando o humano voltar, leia `list_pending` e resuma as decisoes (quantas CQs aceitas, rejeitadas, editadas e criadas; lacunas e divergencias decididas). Peca "aplica" com o nome de quem aprova. So depois chame `apply_reviewed` com esse nome.
7. Proponha o glossario (`add_glossary`) para siglas vistas em `profile.conventions.acronyms_found` e nos documentos. As entradas ficam pendentes e o humano decide na aba Revisao (ou diz "aprovado" no chat e voce chama `apply_edit`); a etapa so fecha depois que elas forem aplicadas. Se menos de cinco CQs foram aceitas, ofereca uma segunda rodada de ate dez, sem repetir as rejeitadas.

**Pare e pergunte:** o humano decide na aba Revisao (claro, completo, sem ambiguidade, prioridade, quais CQs sao de ajuste e quais ficam reservadas para o teste). Nao transforme hipotese em regra. Mesmo depois do "aplica", a etapa so termina quando `requirements_status` diz `closed`.

Saida: `use_cases`, CQs com status, `gaps`, `divergences`, `requirements` e `glossary` no `content.yml`; CQs reservadas espelhadas em `validation/questions.yml`. Se nao ha nenhuma reservada, diga ao humano: o eval nao testara pelo resultado; a etapa 4 fica so com verificacao formal.

### 2. Conceitualizar (LOT: implementacao, conceitualizacao e reuso)

Tools: `requirements_status`, `list_entities`, `list_relations`, `search_term`, `search_registry`, `propose_edit` com `add_class`, `add_relation`, `add_term`.

0. Chame `requirements_status`; se `closed` for falso, volte a etapa 1 e mostre `missing` ao humano. Enquanto estiver aberto e a ontologia nao tiver classe de dominio, `propose_edit` recusa classes, relacoes, termos, mappings, constraints e precedencias.
1. Leia o modelo atual com `list_entities` e `list_relations` antes de propor qualquer coisa.
2. A partir das CQs aprovadas e do `profile`, proponha classes (subclasses de `Entity`, `Metric`, `Rule` ou `Relation`), relacoes com domain, range e inversa, e termos ligados a cada classe. Associe cada proposta ao `requirement_id`.
3. Quando a conceitualizacao estiver estavel, consulte `search_registry` para termos reutilizaveis na LOV. Compare definicao com definicao, nao nome com nome. Se nao houver rede, registre que o reuso ficou pendente.
4. Sinalize termos ambiguos, sobreposicoes e CQs ainda sem classe que as atenda.

**Pare e pergunte:** o humano aprova o modelo conceitual e as decisoes de reuso. Nomes de classe em PascalCase, de relacao em lowerCamelCase.

Saida: classes e relacoes em `schema.ttl`, termos em `content.yml`.

### 3. Codificar (LOT: implementacao, codificacao)

Tools: `propose_edit` com `add_mapping`, `add_constraint`, `add_precedence`; `validate`; `apply_edit`.

1. Para cada termo, proponha o mapping para `tabela.coluna` do `profile`. Metricas levam `role: metric` e `expression` SQL.
2. Proponha `add_constraint` para regras implicitas achadas nos documentos (ex: faturamento so com status FATURADO) e `add_precedence` quando duas fontes divergem sobre o mesmo conceito, dizendo qual prevalece e por que.
3. Rode `validate`. Corrija o que for erro antes de pedir aprovacao.

**Pare e pergunte:** apresente as edicoes pendentes em lote, com evidencia de cada uma. O humano aprova, rejeita (`reject_edit` com motivo) ou pede ajuste.

Saida: `mappings`, `constraints` e `precedence` aplicados; `changelog.yml` atualizado.

### 4. Avaliar (LOT: implementacao, avaliacao)

Tools: `validate` (com `oops=true` quando houver rede), `eval`, `export`.

1. Rode `validate` e leia findings, cobertura e pitfalls (ver "Como interpretar o validate").
2. Rode `eval`. Os `expects` de cada pergunta sao testes estruturais; `fail` significa que a ontologia nao sustenta a pergunta.
3. Para a comparacao com e sem ontologia, peca ao consultor para rodar `akme eval --callable modulo:funcao` com o agente dele (ver "Como interpretar o eval").
4. Interprete os relatorios e proponha correcoes como novos `propose_edit`. Nunca aplique correcao sem voltar ao passo de aprovacao.

**Pare e pergunte:** o humano decide se volta para a etapa 2 ou 3, ou se segue para publicar. A decisao final de qualidade e humana; o validate e o eval sao verificadores externos, nao juizes.

### 5. Publicar (LOT: publicacao)

Tools: `export`, `publish`.

1. Rode `export` e aponte o humano para `docs/index.html` (grafo, termos, cobertura e pitfalls).
2. Rode `publish --target <alvo>` em dry-run e mostre o artefato gerado (`docs/publish/`). Alvos: `snowflake` (semantic view e comments), `databricks` (comments do Unity Catalog), `yaml` (camada generica), `rdf` (YARRRML e, com o extra `rdf`, materializacao via Morph-KGC).
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

Divergencias entre fontes viram `add_divergence` (`topic`, `sources` com duas ou mais `{label, path, locator, quote}`, `hypothesis`) e o que os dados nao respondem vira `add_gap` (`question`, `reason`, `missing`, `evidence`). Ambos sao apresentados na aba Revisao, onde o humano decide; o chat mostra so a lista curta (id, tema ou pergunta, fontes em uma linha). Cada item tem: o termo, o problema em uma frase, as fontes com caminho e trecho, a sua hipotese marcada como hipotese, e uma pergunta fechada para o humano. O caminho e o que o humano usa para abrir o arquivo e conferir. Exemplo:

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

Use o mesmo conteudo na `evidence` do `propose_edit` (ex: `{kind: source, path: data/regulamento.docx, locator: pagina 2, quote: "carga horaria total de 360 h"}`), para que a origem fique gravada no `changelog.yml` e no `content.yml`.

## Como interpretar o validate

| Campo | O que significa | O que fazer |
|---|---|---|
| `findings` nivel `error` | TTL nao parseia, termo aponta para classe inexistente, mapping para coluna inexistente, precedencia contraditoria | Bloqueia `apply_edit` e `publish`. Proponha correcao |
| `findings` nivel `warning` | Profile ausente, pergunta do eval sem CQ registrada | Rode `profile` ou registre a CQ |
| `cq_reserved_without_answer` (error) | CQ `reserved` sem `answer` | Proponha `update_competency_question` com a resposta esperada |
| `cq_approved_without_priority` (error) | CQ `approved` sem `priority` | Proponha `update_competency_question` com `priority` |
| `cq_agent_without_source_evidence` (error) | CQ proposta pelo agente sem item `kind: source` na `evidence` | Proponha a correcao com `path`, `locator` e `quote` da fonte |
| `no_reserved_cq` (warning) | Nenhuma CQ `reserved` | Avise o humano: o eval nao testara pelo resultado |
| `open_gap_or_divergence` (warning) | Lacuna ou divergencia com `decision: open` | Leve ao humano na aba Revisao |
| `coverage` | Colunas do profile cobertas por mappings, por fonte, com a lista das nao cobertas | Colunas nao mapeadas sao candidatas a termo ou devem ser marcadas fora de escopo com o humano |
| `pitfalls` | Subconjunto do catalogo OOPS! calculado localmente: P04 elemento desconectado, P08 sem label ou comment, P11 relacao sem domain ou range, P13 relacao sem inversa, P22 nome fora da convencao, P41 sem licenca | `important` corrige antes de publicar; `minor` registra e decide com o humano |
| `oops` | Resultado do servico remoto quando `oops=true`; `available=false` quando o servico esta fora do ar | Nao bloqueie o fluxo por indisponibilidade; repita mais tarde |

## Como interpretar o eval

- `structural`: `pass` quando todos os `expects` da pergunta valem no `schema.ttl`; `fail` lista o que falta (classe, subclasse, relacao ou dominio errado); `n/a` quando a pergunta nao tem `expects`.
- `without_ontology` e `with_ontology` aparecem so na CLI com `--callable`. A funcao recebe `(pergunta, contexto)` e o contexto e `None` na primeira chamada e o resumo da ontologia na segunda. `answer` em `questions.yml` e o trecho que a resposta precisa conter.
- Leia o resumo: `with_correct` maior que `without_correct` indica que a ontologia esta ajudando; igual ou menor indica termos, mappings ou precedencia faltando. Uma pergunta nunca e exemplo e gabarito ao mesmo tempo: CQs com `status: approved` entram como exemplos no `publish`, as reservadas ficam so no eval.

## Ferramentas do OEG citadas, nao integradas

Widoco (documentacao HTML, exige Java), OnToology (publicacao com w3id), Chowlk (diagrama para OWL), Astrea (SHACL a partir de OWL), FOOPS! (checklist FAIR), Themis e OOPS! como servicos remotos, yatter e RMLdoc (RML), OntoRipple (propagacao de mudancas), CORAL e CQ4OE (padroes de CQ). Detalhes e comandos em `docs/research/oeg-upm.md`.
