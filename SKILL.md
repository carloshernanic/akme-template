---
name: akme
description: Constroi, valida e publica uma ontologia e uma camada semantica sobre a base de dados de um cliente seguindo LOT + NeOn com humano no loop. Use quando o consultor pedir para mapear um dominio, criar termos, mappings ou perguntas de competencia, validar a ontologia ou publicar a camada semantica. As tools do servidor MCP akme sao deterministicas; o raciocinio fica com voce e toda escrita passa por aprovacao humana.
---

# AKME: ontologia e camada semantica com humano no loop

## Objetivo

Levar o consultor do primeiro contato com os dados do cliente ate uma camada semantica publicada, construindo no caminho uma ontologia versionada em texto (`ontology/schema.ttl`, `ontology/content.yml`). O fluxo segue as fases do LOT (especificacao, implementacao, publicacao, manutencao) com as atividades da NeOn que o LOT nao cobre (reuso, alinhamento, reengenharia de recursos nao ontologicos). A base metodologica esta em `docs/research/lot-neon.md`; nao invente etapas que nao estejam la.

## Regras que nunca mudam

1. **Nada entra na ontologia sem aprovacao explicita do humano.** Toda escrita passa por `propose_edit` (grava em `ontology/pending/`) e so vira ontologia com `apply_edit`, que exige o nome de quem aprovou. Nunca chame `apply_edit` sem o humano ter dito "aprovado" para aquela edicao especifica nesta conversa.
2. **`validate` roda antes de todo `apply_edit`.** Se houver erro, mostre ao humano e proponha correcao em vez de aplicar.
3. **Nunca responda de memoria sobre a ontologia.** Use `list_entities`, `list_relations`, `search_term`, `resolve_acronym`, `get_precedence`, `get_requirements` e `list_competency_questions` para saber o que existe.
4. **Toda proposta carrega proveniencia.** Preencha `requirement_id` (a CQ que motiva) e `evidence` (documento, tabela, coluna ou conversa de origem). O `apply_edit` grava isso em `changelog.yml` e na secao `evidence` do `content.yml`.
5. **`publish` e `apply_edit` sao acoes com aprovacao por chamada.** `publish` roda em dry-run por padrao; executar no alvo exige o humano confirmar na CLI.
6. **As tools nao chamam LLM.** O que exige julgamento semantico (redigir definicoes, propor classes, interpretar relatorios) e trabalho seu, sempre apresentado como proposta.

## Preparacao

```
akme init --adapter local_folder --path <pasta>      (ou postgres, snowflake, databricks)
akme connect
```

Se `connect` falhar por falta de extra, instrua: `uv sync --extra <adapter>`. Para a demo: `akme init --demo` e `akme demo`.

## Fluxo em seis etapas

Cada etapa diz quais tools chamar, o que voce produz e onde parar para o humano decidir. A classificacao vem da tabela da secao 5 de `docs/research/lot-neon.md`.

### 1. Especificar (LOT: especificacao de requisitos)

Tools: `connect`, `profile`, `get_requirements`, `list_competency_questions`, `propose_edit` com `add_requirement` e `add_competency_question`.

1. Rode `profile`. Leia fontes, colunas, tipos, nulos, chaves candidatas, convencoes detectadas e os excertos dos documentos do cliente.
2. Proponha proposito, escopo e usuarios (`add_requirement` com `field` purpose, scope ou users). Diferencie o que esta explicito nos documentos do que e hipotese sua.
3. Proponha competency questions a partir da pergunta de negocio do cliente, dos documentos e das colunas. Cada CQ tem `id` (CQ-nnn), `priority` e `source`. Siga a regra do LOT: pergunta quando ha interrogacao de negocio, frase quando e fato, tabela quando e lista de atributos.
4. Proponha entradas de glossario (`add_glossary`) para siglas vistas em `profile.conventions.acronyms_found` e nos documentos.

**Pare e pergunte:** o humano valida cada requisito (claro, completo, sem ambiguidade), prioriza, e diz quais CQs sao de ajuste e quais ficam reservadas para o teste. So depois peca aprovacao e chame `apply_edit`. Nao transforme hipotese em regra.

Saida: `requirements` e `glossary` preenchidos no `content.yml`; CQs reservadas registradas em `validation/questions.yml` com `expects` e `answer`.

### 2. Conceitualizar (LOT: implementacao, conceitualizacao e reuso)

Tools: `list_entities`, `list_relations`, `search_term`, `search_registry`, `propose_edit` com `add_class`, `add_relation`, `add_term`.

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

## Como interpretar o validate

| Campo | O que significa | O que fazer |
|---|---|---|
| `findings` nivel `error` | TTL nao parseia, termo aponta para classe inexistente, mapping para coluna inexistente, precedencia contraditoria | Bloqueia `apply_edit` e `publish`. Proponha correcao |
| `findings` nivel `warning` | Profile ausente, pergunta do eval sem CQ registrada | Rode `profile` ou registre a CQ |
| `coverage` | Colunas do profile cobertas por mappings, por fonte, com a lista das nao cobertas | Colunas nao mapeadas sao candidatas a termo ou devem ser marcadas fora de escopo com o humano |
| `pitfalls` | Subconjunto do catalogo OOPS! calculado localmente: P04 elemento desconectado, P08 sem label ou comment, P11 relacao sem domain ou range, P13 relacao sem inversa, P22 nome fora da convencao, P41 sem licenca | `important` corrige antes de publicar; `minor` registra e decide com o humano |
| `oops` | Resultado do servico remoto quando `oops=true`; `available=false` quando o servico esta fora do ar | Nao bloqueie o fluxo por indisponibilidade; repita mais tarde |

## Como interpretar o eval

- `structural`: `pass` quando todos os `expects` da pergunta valem no `schema.ttl`; `fail` lista o que falta (classe, subclasse, relacao ou dominio errado); `n/a` quando a pergunta nao tem `expects`.
- `without_ontology` e `with_ontology` aparecem so na CLI com `--callable`. A funcao recebe `(pergunta, contexto)` e o contexto e `None` na primeira chamada e o resumo da ontologia na segunda. `answer` em `questions.yml` e o trecho que a resposta precisa conter.
- Leia o resumo: `with_correct` maior que `without_correct` indica que a ontologia esta ajudando; igual ou menor indica termos, mappings ou precedencia faltando. Uma pergunta nunca e exemplo e gabarito ao mesmo tempo: CQs com `status: approved` entram como exemplos no `publish`, as reservadas ficam so no eval.

## Ferramentas do OEG citadas, nao integradas

Widoco (documentacao HTML, exige Java), OnToology (publicacao com w3id), Chowlk (diagrama para OWL), Astrea (SHACL a partir de OWL), FOOPS! (checklist FAIR), Themis e OOPS! como servicos remotos, yatter e RMLdoc (RML), OntoRipple (propagacao de mudancas), CORAL e CQ4OE (padroes de CQ). Detalhes e comandos em `docs/research/oeg-upm.md`.
