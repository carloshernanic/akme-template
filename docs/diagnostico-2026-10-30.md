# Diagnóstico do akme-template frente ao guia LOT + NeOn

Data: 2026-10-30. Escrito para quem trabalha no template e conhece o repositório.
Referência metodológica: o guia em `github.com/capstone-insper/202602_MCKINSEY_DiagnosticEngineDataRequest_Docs`
(páginas `criacao-da-ontologia/01-metodologia-lot-neon.mdx`, `workflow-e-ferramentas/02-o-fluxo-completo.mdx`,
`publicacao/01-plataforma-do-cliente.mdx`) e `docs/research/lot-neon.md` deste repositório.

## 1. Veredito

O template tem uma espinha dorsal boa: edições tipadas, fila de pendências, aprovação nominal,
proveniência e leitura de fontes com citação. Isso é o "humano no loop" que o artigo primário e o
LOT pedem, e está implementado de verdade.

O problema é que a skill promete seis etapas e as tools só sustentam três. Da etapa 4 em diante
o template entrega a sensação de ter avaliado, publicado e mantido, sem fazer nenhuma das três
coisas como o guia define. O risco prático é um consultor chegar ao fim do fluxo com `validate ok`,
`eval 3/3 pass` e um `snowflake.sql` gerado, acreditando que a camada semântica está pronta,
quando o artefato não responde nem a CQ de maior prioridade da própria demo.

| Etapa da skill | Etapas do guia | O que a skill promete | O que as tools sustentam | Estado |
|---|---|---|---|---|
| 1. Especificar | 1, 2 | ORSD: propósito, escopo, usuários, CQs priorizadas, glossário | Leitura de fontes forte; ORSD parcial (sem resposta esperada, sem dúvidas pendentes, sem responsáveis) | Aceitável |
| 2. Conceitualizar | 3 | Classes, relações, termos, reuso via LOV | Classes e object properties sim; atributos, cardinalidade e disjunção não; reuso sem definição nem registro | Parcial |
| 3. Codificar | 6 | Mappings, constraints, precedência, `validate` antes de aplicar | Mappings sim; `validate` não é forçado; termo e mapping entram sem checagem no `propose` | Parcial |
| 4. Avaliar | 4, 6b, 7 | Verificação formal e teste pelo resultado | Parse + 6 pitfalls + existência de classes; nenhum reasoner, nenhuma cobertura de CQ, nenhum teste contra dados | Não atende |
| 5. Publicar | 5, 8 | Semantic view, metric view, YAML completo | SQL sem chaves e sem relationships; Databricks só comentários; YAML sem joins, sinônimos e SQL verificado | Não atende |
| 6. Manter | 9, 10 | Issue, classificação, impacto, correção | Só existem edições `add_*`; não há como alterar, depreciar ou remover nada | Inexecutável |

## 2. Como este diagnóstico foi feito

- Leitura integral de `SKILL.md`, `ontology/manifest.yml`, todos os módulos em `akme/` e `tests/`, e
  `docs/research/lot-neon.md`.
- Leitura das páginas do guia com `status: ready`. As páginas de validação, quick start, conexão e
  exploração ainda são `placeholder`; onde o guia não define algo, isto está dito.
- Execução, numa cópia fora do repositório: `akme demo`, `akme validate`, `akme eval`,
  `akme publish --target yaml|snowflake|databricks` (dry-run). As saídas estão no anexo.
- `uv run pytest -q`: 27 testes, todos passam. A suíte é útil para o que cobre, mas não cobre
  nenhum dos problemas abaixo (não há teste de relationships no SQL, de cobertura de CQ, de
  `validate` antes de `apply_edit`, nem de separação entre CQ de exemplo e CQ de gabarito).

Correção de uma afirmação anterior minha: eu disse que a Snowflake rejeita a semantic view sem
chave primária. No DDL `CREATE SEMANTIC VIEW` a chave é opcional; ela se torna obrigatória quando
há `RELATIONSHIPS`. O ponto que importa continua: sem chaves não há relationships, e sem
relationships o Cortex Analyst não cruza tabelas.

## 3. O que está bem

Nada aqui é cortesia. São partes que eu manteria como estão.

1. **Gate humano real.** `propose_edit` grava em `ontology/pending/` e não toca a ontologia
   (`akme/tools/ontology_write.py:21-38`). `apply_edit` recusa `approved_by` vazio e grava quem
   aprovou, quando, com que evidência e por qual requisito (`ontology_write.py:69-113`).
   `reject_edit` registra o motivo. Isso cobre a regra transversal 1 de `lot-neon.md` e a lacuna
   de validação humana que o artigo primário aponta (6 de 49 estudos).
2. **Proveniência em dois lugares.** `changelog.yml` e a seção `evidence` do `content.yml`. É
   mais do que o LOT exige para requisitos e serve de base para manutenção quando ela existir.
3. **Citação de fonte.** `find_in_sources` devolve caminho, página ou slide, coluna e trecho, e a
   skill obriga a usar antes de apresentar hipótese. É a parte da etapa 1 que mais evita o LLM
   inventar.
4. **Adapters e profile.** `local_folder` lê subpastas, xlsx por aba, docx, pptx e pdf por página;
   `profile` dá tipos, nulos, cardinalidade, chaves candidatas e siglas. Isso atende bem a
   "data exchange identification" do LOT.
5. **Pitfalls nativos e OOPS! opcional.** Seis códigos calculados localmente e o serviço remoto
   quando há rede, com checagem de status do OEG antes. Boa decisão de não bloquear por
   indisponibilidade.
6. **Dry-run por padrão e confirmação na CLI.** `publish` sem `--no-dry-run` nunca toca o alvo;
   com ele, exige confirmação interativa e adapter igual ao alvo.
7. **Documentação mínima existe.** `export` gera JSON, Mermaid e `docs/index.html`, o que cumpre
   a documentação que o LOT considera obrigatória mesmo sem publicação online.
8. **Base metodológica honesta.** `lot-neon.md` marca `needs_validation` onde não leu a fonte e
   diz claramente que "LOT + NeOn" é um arcabouço do artigo de revisão, não uma metodologia nova.

## 4. O que está ruim, por etapa

Cada item diz o que a metodologia pede, o que o template faz, onde está no código e qual o impacto.

### 4.1 Especificar

**ORSD incompleto.** O LOT pede CQ com resposta esperada, status controlado (Proposed, Accepted,
Rejected, Pending, Deprecated, Superseded) e proveniência; o guia pede ainda critérios de
aceitação, responsáveis e dúvidas pendentes. A CQ em `content.yml` tem id, texto, prioridade,
`source` e um `status` em texto livre (`ontology_write.py:78-83`). A resposta esperada vive em
`validation/questions.yml`, sem vínculo além do id. Impacto: não há como saber, lendo o ORSD, se
uma CQ foi respondida ou o que conta como resposta certa.

**Sem distinção entre CQ de ajuste e CQ reservada.** O guia é explícito: "uma pergunta nunca é
exemplo e gabarito ao mesmo tempo". A skill diz que `approved` vira exemplo e "as reservadas ficam
só no eval", mas não existe campo nem status para "reservada". Na demo, CQ-001 e CQ-002 estão
`approved` (entram como `examples` em `docs/publish/semantic.yml`) e também em `questions.yml`
(entram como gabarito do `eval`). O `validate` ainda emite aviso quando uma pergunta do eval
**não** está registrada como CQ (`validate.py:81-86`), empurrando para a sobreposição.

**`requirement_id` não é validado.** `propose_edit` aceita qualquer string ou nenhuma
(`ontology_write.py:21-38`). A rastreabilidade requisito → elemento, que é o motivo de o LOT pedir
identificadores, depende de disciplina do agente, não da tool.

### 4.2 Conceitualizar

**Modelo expressivo demais no texto e pobre demais no código.** A skill fala em "classes,
hierarquias, relações, atributos e restrições". As tools escrevem `owl:Class` com `subClassOf`,
`rdfs:label` e `rdfs:comment`, e `owl:ObjectProperty` com domain, range e inversa
(`akme/ontology.py:87-116`). Não há datatype property, cardinalidade, `owl:disjointWith` nem
enumeração. O `eval` sabe testar `disjointWith` (`eval.py:48-50`), mas nenhuma edição consegue
escrevê-lo. O exemplo do próprio guia, "Cliente é PF ou PJ", não é modelável.

**Reuso é cosmético.** A skill manda "comparar definição com definição, não nome com nome".
`search_registry` devolve IRI, tipo, prefixo do vocabulário e score (`akme/tools/ontology_read.py:69-85`);
nenhuma tool lê a definição do termo externo (a tabela 6.1 de `lot-neon.md` pedia `ontology_read`
aceitando IRI remota). E não existe edição para registrar o resultado: nem `owl:equivalentClass`,
nem `rdfs:seeAlso`, nem um campo "reuso avaliado e rejeitado porque". O passo 3 do guia pede
exatamente esse registro. Hoje o reuso acontece na conversa e evapora.

**Rótulos só em português.** `add_class` e `add_relation` fixam `lang="pt"`. Detalhe, mas fecha a
porta ao cenário 9 da NeOn (localização) sem motivo.

### 4.3 Codificar

**`validate` antes de `apply_edit` é regra de texto, não de código.** A regra 2 da skill e o
`runs_before: [validate]` do manifest não têm contraparte em `apply_edit` (`ontology_write.py:69`).
`add_term` com classe inexistente e `add_mapping` com coluna inexistente passam no `propose`
(a checagem de referências só cobre `add_class` e `add_relation`, `ontology_write.py:41-46`) e
podem ser aplicados; o erro só aparece se alguém rodar `validate` depois. A ontologia pode entrar
em estado inválido por um comando legítimo.

**Etapa 3 antes da etapa 4 inverte o guia.** No guia a ontologia é verificada (etapa 4) e
registrada (5) antes de se gerar a camada semântica (6). Na skill, o mapeamento para colunas é a
etapa 3 e a avaliação é a 4. Na prática, mapeia-se uma ontologia que ainda não passou por pitfalls
nem cobertura. Não é só ordem: é o que permite que a verificação 6b (do `.yml`) e a 4 (da ontologia)
tenham virado uma coisa só no `validate`.

### 4.4 Avaliar

Esta é a etapa mais grave, porque é ela que daria sentido ao resto.

**Nenhum raciocinador.** O guia define HermiT como portão (classe insatisfazível reprova). O
`validate` parseia o Turtle e para (`validate.py:21-28`). Como a ontologia só tem subclasses e
object properties simples, hoje nada poderia ficar inconsistente; mas isso é consequência da
pobreza do modelo, não de um check.

**Cobertura errada.** O guia pede "script de cobertura de requisitos": quais CQs a ontologia
cobre. O `validate` mede colunas do profile cobertas por mappings (`validate.py:38-67`). São
medidas diferentes com nomes parecidos. Não existe relatório de CQ sem classe, termo ou mapping,
embora o `changelog.yml` tenha os dados para calcular.

**`eval` não testa pelo resultado.** O guia descreve a etapa 7 como rodar as perguntas reservadas
contra os dados, com gabarito SQL revisado, e usar o erro para decidir se volta para a etapa 3
(conceito) ou 6 (mapping). O `eval` confere se nomes existem no `schema.ttl` (`eval.py:34-58`). O
`answer` é uma substring (`vl_total`, `financeiro`, `categoria`) comparada com a resposta de um
callable que o usuário precisa fornecer. Nada roda SQL, nada toca o adapter. O resultado
`structural 3/3 pass` da demo não diz nada sobre a camada semântica.

**Verificação 6b não existe.** O guia lista cinco checagens do `.yml`: formato, tabelas e colunas
existem, SQL de cada métrica roda, todo conceito está ligado a um dado ou marcado "sem dado",
joins fazem sentido. O template faz a segunda. Termo sem mapping não é sinalizado; expressão de
métrica nunca é executada; join não existe para ser checado.

**Pitfall P04 é inalcançável.** `add_class` sempre grava `subClassOf`, e o P04 só dispara para
classe sem `subClassOf` nem relação (`validate.py:95-97`). É código morto enquanto a única forma
de criar classe for essa tool.

### 4.5 Publicar

Saídas reais no anexo.

**Snowflake.** `render_snowflake` (`akme/tools/publish.py:44-63`) emite `TABLES` sem
`PRIMARY KEY`, nenhum bloco `RELATIONSHIPS`, e descarta as cinco relações da ontologia. A
CQ-001 da demo ("faturamento por UF") precisa de pedidos → clientes; o artefato publicado não tem
como responder. O guia pede ainda `verified_queries`, `synonyms` e teste com `verify_only` antes
de criar; nada disso existe.

**Databricks.** `render_databricks` (`publish.py:66-75`) gera `COMMENT ON TABLE` e
`ALTER COLUMN ... COMMENT`. O guia define o alvo como metric view (`CREATE VIEW ... WITH METRICS
LANGUAGE YAML`) mais configuração do Genie (exemplos, instruções, joins). O que o template chama
de "publicar no Databricks" é enriquecer comentários de coluna.

**YAML genérico.** O guia lista cinco tipos de informação. O `semantic.yml` gerado tem mapeamento
e métricas; as relações saem sem condição de join (são a lista crua do TTL); os sinônimos dos
termos são descartados em `semantic_model` (`publish.py:27`); os exemplos saem sem SQL; não há
`dono` nem `canonica`, então duas definições de receita (o caso central da página "Camada
semântica") não têm representação. A `precedence` existe, mas em texto, sem ligar a duas métricas.

**Versão desincronizada.** `bump_version` atualiza `manifest.yml` e `changelog.yml`
(`publish.py:98-116`); o `owl:versionInfo` em `schema.ttl` fica em 0.1.0. O LOT pede semver em
todos os artefatos; aqui o artefato principal é o único que não acompanha.

**Teste do agente publicado (8b) não é citado.** Nem na skill nem no manifest. Como o guia também
não o detalha além do nome, é uma lacuna compartilhada, mas a skill deveria ao menos dizer que
ele existe e que fica fora do template.

### 4.6 Manter

**Inexecutável com as tools.** `EditType` tem nove valores, todos `add_*` (`akme/models.py:10-20`).
Não há `update_*`, `remove_*`, `deprecate_*`. A skill descreve "bug volta para a etapa 3" e
"mudança na fonte: verifique mappings quebrados", mas um mapping quebrado não pode ser corrigido
nem removido por `propose_edit`. A única saída é editar YAML e Turtle à mão, fora do gate humano e
sem changelog, exatamente o que o template existe para evitar.

**Sem registro de issue.** O LOT condiciona toda mudança a uma issue; a skill repete isso, e
`lot-neon.md` (6.2) já apontava a tool como ausente. Nada foi feito.

**A demo é o único caminho ponta a ponta, e ela pula o gate.** `akme demo` aplica o seed com
`approved_by="demo"` sem ninguém olhar (`akme/cli.py:183-187`). É aceitável para demo, mas é
também o único fluxo que um novo integrante vai rodar, e ele ensina o caminho errado.

## 5. Onde a aplicação está se perdendo

Os itens acima são sintomas. As causas são cinco.

1. **A skill foi escrita antes das tools e nunca foi reconciliada com elas.** O texto descreve o
   fluxo ideal de `lot-neon.md` (6.3); o código implementa o subconjunto que coube. `lot-neon.md`
   6.2 listou cinco tools que a metodologia exige e não estavam previstas (requisitos, busca em
   registro, issue, release, diagrama). Duas entraram pela metade (`search_registry`, `--release`),
   três não entraram. A skill fala como se todas existissem.
2. **Ontologia e camada semântica viraram um arquivo só.** `content.yml` guarda termos, mappings,
   constraints e precedência; o `semantic.yml` é uma projeção gerada no `publish`. O guia separa os
   dois artefatos de propósito: a ontologia é verificada e versionada antes, a camada é gerada,
   verificada (6b) e testada (7) depois. Ao fundir, o template perdeu as duas verificações
   intermediárias e a possibilidade de a camada ter coisas que a ontologia não tem (join SQL,
   dono, canônica, perguntas verificadas).
3. **A avaliação é um placebo.** `validate ok` e `eval pass` são obtidos com checagens que a
   própria ontologia nunca poderia reprovar. Sem reasoner, sem cobertura de CQ e sem execução
   contra dados, o "pare e pergunte" da etapa 4 pede ao humano para decidir com base em nada.
4. **O `publish` foi feito para existir, não para funcionar.** Os renderers produzem texto que
   se parece com o alvo e o teste confere substrings (`tests/test_export_eval_publish.py:44-55`).
   Nenhum dos três alvos foi comparado com a especificação da plataforma. O guia já registrava em
   16/10 que "o conversor ainda não existe"; o template deveria dizer o mesmo em vez de oferecer
   `--target snowflake`.
5. **Só há adição, nunca correção.** Um fluxo iterativo (LOT) e evolutivo (NeOn) sem operação de
   modificação não itera. Tudo que entra errado fica.

## 6. Ordem de ataque

Critério: o que, resolvido, muda a resposta do humano no "pare e pergunte".

1. **Etapa 4 primeiro.** (a) Cobertura de CQ: para cada CQ, classes, termos e mappings ligados via
   `requirement_id`, e lista das descobertas. (b) Status `reserved` na CQ, com `publish` excluindo
   e `eval` exigindo. (c) `validate` chamado dentro de `apply_edit`, recusando com erro. (d)
   Checagem de referências em `propose_edit` para `add_term` e `add_mapping`. (e) `eval` com campo
   `sql` por pergunta, executado no adapter, comparado ao gabarito. Pronto quando a demo reprovar
   em algo real.
2. **Snowflake de verdade.** Chave primária por fonte (do `profile.candidate_keys` ou declarada no
   mapping), `RELATIONSHIPS` derivadas das relações da ontologia mais a condição de join, sinônimos
   e `verified_queries` das CQs aprovadas, `verify_only` antes de criar. O guia prioriza Snowflake;
   Databricks como comentários pode ficar, mas rotulado como "enriquecimento de catálogo", não
   "publicação".
3. **Operações de mudança.** `update_term`, `remove_mapping`, `deprecate_class` (com
   `owl:deprecated`), todas pelo mesmo gate. Sem isso a etapa 6 continua sendo texto.
4. **Camada semântica como artefato próprio.** `add_join` (relação → SQL), `dono` e `canonica` na
   métrica, sinônimos preservados, verificação 6b separada da 4.
5. **Reuso com substância.** `search_registry` devolvendo a definição do termo (LOV entrega
   `rdfs:comment`), e `add_alignment` gravando `owl:equivalentClass` ou a decisão de não reusar.
6. **Por último:** HermiT ou `owlready2` como portão, `owl:versionInfo` no bump, rótulo com idioma
   configurável, `add_attribute` para datatype properties.

## Anexo: saídas reais da demo (2026-10-30)

`akme validate`:

```
pitfall minor  P13 (native)  referencia: relacao sem inversa declarada
cobertura: 10/21 colunas mapeadas (48%)
ok
```

`akme eval`: CQ-001, CQ-002, CQ-003 com `structural: pass`; resumo
`{'questions': 3, 'structural_pass': 3, 'structural_fail': 0}`.

`akme publish --target snowflake` (trecho):

```sql
CREATE OR REPLACE SEMANTIC VIEW DB.PUBLIC.LOCAL_DEMO_SEMANTIC
  TABLES (
    clientes AS DB.PUBLIC.clientes,
    pedidos AS DB.PUBLIC.pedidos,
    produtos AS DB.PUBLIC.produtos,
    itens_pedido AS DB.PUBLIC.itens_pedido
  )
  DIMENSIONS ( ... 9 dimensões ... )
  METRICS (
    pedidos.faturamento AS SUM(CASE WHEN status = 'FATURADO' THEN vl_total END) COMMENT '...'
  )
  COMMENT = 'AKME local_demo v0.1.0';
```

Sem `PRIMARY KEY`, sem `RELATIONSHIPS`. As cinco relações do TTL (`pertenceA`, `possuiPedido`,
`contem`, `pertenceAoPedido`, `referencia`) não aparecem.

`akme publish --target databricks` (trecho):

```sql
COMMENT ON TABLE main.default.clientes IS 'AKME local_demo v0.1.0';
ALTER TABLE main.default.clientes ALTER COLUMN id_cliente COMMENT 'cliente: Pessoa juridica cadastrada na distribuidora.';
```

`akme publish --target yaml`: `relations` sem join, `examples` com CQ-001 e CQ-002 (as mesmas de
`questions.yml`), nenhum campo `synonyms`, `dono` ou `canonica`.
