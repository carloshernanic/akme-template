# Task 10: camada semântica legível no grafo

> **Atualização (rodada final, 12/11/2026):** a `_descricao` nos dados passou a ser opcional e vem **desligada**; liga-se com `neo4j: {descricao_nos_dados: true}` no `akme.yml`. O motivo é o custo medido abaixo (+43% regravando por cima; +14% numa base nova, na [Task 9](task-9-aceitacao.md)). O esquema para o LLM, os `Termo` e o resto desta página continuam valendo.

A [pesquisa de 12/11/2026](pesquisa-camada-semantica.md) mostrou duas lacunas. Quem clica num nó no Neo4j Browser não vê a definição da classe. E as ferramentas de LLM (o MCP oficial da Neo4j, o `neo4j-graphrag`) só leem nomes e tipos, então a definição, os termos e as regras de métrica nunca chegam ao modelo. Mateus decidiu: descrição em cada nó, para navegação (opção A), e o esquema descritivo gravado também dentro do Neo4j (opção E), para o LLM conseguir lê-lo. A seta do dado para o `Conceito` (opção C) ficou de fora.

## O que muda

| Item | Antes | Depois |
|---|---|---|
| Nó de dado | Colunas, `_id`, `_projeto`, `_carga` | Também `_descricao`, a definição da classe (igual a `Conceito.definicao`) |
| Aresta de dado | Só `_carga` | Também `_descricao`: a definição da relação ou, sem ela, o rótulo |
| Esquema para o LLM | Não existia | `docs/publish/neo4j_schema.md` e a propriedade `esquema` da marca `_AkmeProjeto` |
| Termos do `content.yml` | Fora do grafo | Nós `Termo`, ligados por `(:Conceito)-[:TEM_TERMO]->(:Termo)` |
| "Não somar após juntar com" | Nomes de tabela (`olist_order_items_dataset`) | Labels do grafo (`ItemPedido`); fonte sem nó vira `fonte <nome> (nao publicada)` |
| Prévia antes do "confirmar?" | `banco N -> origem M` por label | Mais `pelo menos K serao removidos` e o total |
| Endereço do Browser no fim da carga | Sempre a porta 7474 | `AKME_NEO4J_BROWSER_URL`, se definida |
| Nomes reservados | Labels `Conceito`, `_AkmeProjeto`; propriedades `_id`, `_projeto`, `_carga` | Também o label `Termo` e a propriedade `_descricao` |

## Por quê

- **`_descricao`:** é o único jeito de a definição aparecer ao clicar no nó, sem uma consulta a mais. O nome tem sublinhado para não colidir com uma coluna `descricao` do cliente, e por isso é reservado como `_id`.
- **Esquema no banco:** quem só tem acesso ao Neo4j (por exemplo, um agente pelo MCP somente leitura) não tem o arquivo. Com o texto na marca do projeto, uma consulta basta: `MATCH (p:_AkmeProjeto {projeto: $projeto}) RETURN p.esquema`. A marca já existia e o guarda do destino já a conhece, então não foi preciso criar label.
- **`Termo`:** o significado de cada coluna (`review_score`, `fl_ativo`) estava só no `content.yml`. Agora pode ser consultado no grafo.
- **Labels na regra:** o grafo não dizia em lugar nenhum que `olist_order_items_dataset` virou `ItemPedido`. O LLM tinha de adivinhar.
- **Prévia de remoção:** a sincronização apaga o que não veio da origem. O número antes do "confirmar?" deixa a pessoa ver o tamanho disso.

## O que isto muda para um LLM, sem exagero

Resposta curta: **o esquema escrito (item E) pode ajudar um LLM. O `_descricao` em cada nó (item A) quase não ajuda, e custa caro.** Nenhuma das duas coisas foi medida num LLM de verdade. O que segue é o que a evidência permite dizer.

**Por que a mudança foi feita.** Antes, a definição de cada classe estava só nos nós `Conceito`, e o significado das colunas, as regras e o glossário não entravam no grafo. As ferramentas que um LLM usa para ler o Neo4j (o MCP oficial e o `neo4j-graphrag`) montam o esquema pelo APOC e entregam só nomes e tipos (seção 2.1 da pesquisa). O LLM via `review_score: INTEGER` e mais nada. Também não havia como saber, pelo grafo, que a tabela `olist_order_items_dataset` virou o label `ItemPedido`.

**`_descricao` no nó (item A): serve à pessoa no Browser, não ao LLM.**

- As ferramentas padrão não leem valores de propriedade. No modo "enhanced", leem uma amostra cortada em 50 caracteres por propriedade, e é só isso que chegaria ao modelo.
- Um LLM só leria `_descricao` se escrevesse uma consulta para isso. Nesse caso, ler `Conceito.definicao` ou o esquema daria o mesmo texto, uma vez só, e não repetido 99 mil vezes.
- Nas arestas, a `_descricao` hoje é o rótulo da relação (`pertence a`), que quase repete o nome do tipo (`pertenceA`). Informação nova para o LLM: praticamente nenhuma, até a ontologia ter definição nas relações.
- O custo é real: +123 MB (+43%) no Olist, na mesma base.
- Há um risco pequeno: `_descricao` aparece em `properties(n)` e no esquema APOC como mais uma propriedade `STRING`, e um LLM pode tentar filtrar por ela. O esquema escrito avisa que ela é do akme.
- Foi uma decisão para a navegação humana, tomada sabendo disso. Não é uma melhoria para o LLM.

**Esquema escrito (item E): é o que tem chance de ajudar, com ressalvas.**

- **O que ele leva que o APOC não leva:** a definição de cada label, o termo de cada coluna (por exemplo, o que `fl_ativo` quer dizer e que o financeiro define "ativo" de outro jeito), as métricas com grão e aditividade, "não somar após juntar com" já em labels, o glossário, as regras e as precedências. E avisa da armadilha mais concreta deste grafo: as relações têm o mesmo nome entre `Conceito` e entre os dados, então um `MATCH ()-[:contemItem]->()` sem label conta também a aresta da ontologia.
- **O que a literatura apoia:** descrição de coluna ajuda de forma modesta. No BIRD (texto para SQL), o GPT-4o foi de 30,1% para 33,3% com descrições de referência, e o ganho é maior em colunas de nome pouco claro, como as do Olist. Conhecimento específico por pergunta rende mais (+15 a +20 pontos), e o esquema não é isso. Não há estudo de texto para Cypher que isole o efeito de descrições.
- **O que pode atrapalhar:** a Neo4j mediu que prompts mais longos pioram o acerto e que um esquema podado acerta mais. O nosso esquema do Olist tem 11.311 caracteres, cerca de 3,4 vezes o esquema padrão do APOC (3.359). Não podamos por pergunta. Pode ser que, para perguntas simples, ele piore o resultado em vez de melhorar.
- **Ele não chega sozinho:** nenhuma ferramenta oficial lê a propriedade `esquema`. Quem monta o agente precisa pôr a instrução no prompt ("antes de responder, rode `MATCH (p:_AkmeProjeto) RETURN p.esquema`") ou passar o arquivo ao `neo4j-graphrag`. Sem isso, o LLM vê o mesmo que antes.
- **Por que gravar no banco, e não só no arquivo:** um agente que só tem o MCP somente leitura não vê o repositório. Com o texto no banco, uma consulta basta. O custo é um texto de 11 mil caracteres num nó só.

**Termos como nós (`Termo`):** úteis para quem consulta o grafo de propósito: dá para perguntar "que coluna guarda a nota da avaliação?" com uma consulta. Pelo mesmo motivo do item A, as ferramentas padrão não os leem. O esquema escrito já traz os mesmos termos, então para o LLM os nós `Termo` são redundantes se ele ler o esquema.

**O que falta para afirmar que ajuda:** rodar as perguntas de competência do Olist num LLM em três configurações (só o esquema do APOC; APOC mais o esquema do akme; esquema do akme podado por pergunta) e comparar o acerto. Enquanto isso não for feito, "melhor para o LLM" é uma hipótese apoiada por evidência indireta, não um resultado.

## Como

- **`akme/tools/neo4j_onto.py`:** `descriptions` lê do `schema.ttl` o texto de cada classe e relação; `term_entries` monta as propriedades de cada `Termo`; `join_labels` troca fonte por label; `ontology_statements` recebe o mapa fonte → label do plano e acrescenta, depois das setas, um `MERGE` por termo e a seta `TEM_TERMO`.
- **`akme/tools/neo4j_schema.py` (novo):** `llm_schema(project, plan)`, função pura. Lê só a ontologia, o `content.yml` e o plano. Não põe horário. As únicas contagens são as do plano (nós e arestas previstos).
- **`akme/tools/neo4j_load.py`:**
    - os comandos de nó e de aresta ganharam `, n._descricao = $descricao` e `, e._descricao = $descricao` no mesmo `SET`, com o texto como parâmetro do lote. Sem definição, o parâmetro é `null`, e o Neo4j não grava a propriedade;
    - restrição nova `akme_termo_uniq_projeto_nome`;
    - depois dos comandos da ontologia e antes da sincronização, `MATCH (m:_AkmeProjeto {projeto: $projeto}) SET m.esquema = $esquema`. Uma falha aqui cai na mesma regra da ontologia: nada é apagado;
    - `publish_neo4j` grava `neo4j_schema.md` ao lado de `neo4j.cypher`, no dry-run e na carga, e devolve o caminho em `schema`;
    - `verify` também conta os `Termo` do projeto;
    - a contagem "no banco hoje" deixa de fora `Conceito` e `Termo`, que não são dados;
    - `browser_url` usa `AKME_NEO4J_BROWSER_URL` quando ela existe.
- **`akme/tools/neo4j_plan.py`:** `Termo` em `RESERVED_LABELS` e `_descricao` em `RESERVED_PROPS`.
- **Escolhas minhas:** com vários mappings, `papel` vem do primeiro na ordem do `content.yml`, e `fontes`/`colunas` são listas paralelas ordenadas pelo par. Uma métrica entra no esquema no label da fonte do seu mapping. O esquema lista também as relações da ontologia sem aresta no grafo, para o LLM não consultá-las.
- **Conferência da demo:** `verificar_neo4j.py` passou de 45 para 50 verificações: termos ligados ao conceito certo, nenhum `Termo` solto, `_descricao` de cada nó igual a `Conceito.definicao` do seu label, `_descricao` das arestas e esquema na marca. `amostra_valores.py` trata `_descricao` como campo do akme.

## Testes

- **Unitários:** `tests/test_neo4j_schema.py` (novo: determinismo, bloco "como consultar", definição, termo, sinônimo, métrica com label, glossário, regras, precedência, fonte não publicada, sem horário). Em `tests/test_neo4j_onto.py`: termos e `TEM_TERMO`, vários mappings, termo fora dos conceitos, regra com labels, textos de `_descricao` com e sem definição. Em `tests/test_neo4j_plan.py`: `_descricao` e `Termo` reservados. Em `tests/test_neo4j_load.py`: `_descricao` como parâmetro em nós e arestas, classe sem definição manda `null`, esquema na marca antes da sincronização, arquivo do esquema, restrição do `Termo`, `verify` com `Termo`, prévia com removidos e banco vazio, `AKME_NEO4J_BROWSER_URL`.
- **Integração (Neo4j real):** `test_real_semantic_layer` (todo nó de dado com `_descricao` igual à definição, arestas com o rótulo, esquema na marca igual ao arquivo, 10 termos ligados, regra com label, segunda carga remove 0 e mantém o esquema) e `test_real_preview_counts_what_sync_removes`. Os 11 testes de integração passaram em 43 s.
- **Demo pela CLI:** `verificar_neo4j.py` com 50 de 50 OK, 216 células; `amostra_valores.py` com 43 linhas, 213 células e 0 divergências.

## Medições no Olist

Cópia de aceitação, `neo4j:2026.10.1` Community no contêiner descartável `akme-neo4j-t6`. Tempo e memória com `/usr/bin/time -l`. Disco com `du -sk /data/databases/neo4j` depois de reiniciar o contêiner, o que força o checkpoint (o Community não tem `db.checkpoint()`).

| Carga | Tempo | Memória máxima do akme | Banco |
|---|---:|---:|---:|
| Antes (código do `HEAD`), banco limpo | 31,24 s | 331 MB | 286,1 MB |
| Depois, por cima da carga anterior (regrava tudo com `_descricao`) | 33,04 s | 305 MB | 409,2 MB |
| Depois, banco limpo | 31,64 s | 297 MB | (ver nota) |

- **O que a carga nova grava a mais:** `_descricao` em 446.873 nós (42,2 milhões de caracteres) e em 568.943 arestas (9,0 milhões), 25 `Termo` com 25 `TEM_TERMO`, e o esquema na marca (11.311 caracteres).
- **Disco:** +123,1 MB (+43%) na mesma base. O arquivo de strings foi de 19,4 para 98,3 MB e o de propriedades de 163,8 para 196,6 MB. A pesquisa mediu +81,5 MB para a descrição só nos nós, numa base recém-criada. A diferença vem das arestas e da regravação por cima, que no formato de registros do Community deixa espaço livre nos arquivos.
- **Nota:** os arquivos do Neo4j não encolhem. Depois de apagar tudo e carregar de novo, o banco ocupava 593,3 MB, porque o espaço liberado não é reaproveitado logo. Esse número não mede o custo da tarefa.
- **Tempo:** sem mudança relevante (31,2 s contra 31,6 s em banco limpo). A memória do processo do akme ficou na mesma faixa. A pesquisa e a Task 9 registraram 224 MB, medidos de outro jeito; aqui os dois lados foram medidos igual.

## Limites

- **Relações sem definição:** a ontologia não exige `comment` em `add_relation`, e o validador (P08) não confere relações. Por isso a `_descricao` das arestas costuma ser só o rótulo (`pertence a`). Fica para a próxima branch, porque é uma falha da ontologia, não do exportador.
- **Fora desta tarefa:** a seta do dado para o `Conceito` (opção C), subclasses marcando os dados (`AvaliacaoNegativa` continua sem nós) e o destino RDF.
- **Custo em disco:** a descrição repete o mesmo texto em cada nó e aresta. No Olist, +43% na mesma base.
- **O LLM ainda precisa ser avisado:** as ferramentas oficiais não leem o esquema sozinhas. O guia traz a instrução pronta para o prompt. Não medimos o efeito num LLM de verdade.
- **Perguntas de competência** não entram no esquema nem no grafo.
- **Uma base só:** medido no Olist, numa máquina (Apple M5, 24 GB), Neo4j Community.

## Revisão

A revisão independente não encontrou problemas críticos. Ela conferiu:

- que a sincronização e o guarda do destino continuam valendo: `Termo` tem `_projeto` e `_carga` e sai junto com a ontologia, e `Conceito` e `Termo` ficam fora da contagem "no banco hoje";
- que `_descricao` fica ausente quando a classe ou a relação não tem definição;
- que o esquema é determinístico e coerente com a carga: o texto gravado na marca é o mesmo do arquivo;
- que a prévia é somente leitura.

Corrigido nesta rodada:

- **Visão geral:** a frase que introduz os motivos da troca do n10s contradizia a lista. Agora segue a pesquisa: o teto de 100 mil era o nosso `MAX_ROWS`, relação virar nó vinha do `onto.import` e tinha meio-termo, só o motivo do Aura se sustenta por inteiro, e o que se perdeu foi o RDF fiel.
- **Inversa no esquema:** "sem aresta própria; percorra no sentido contrário" só aparece quando a inversa não tem aresta publicada no plano. Teste com os dois sentidos publicados.
- **Exemplo do bloco "como consultar":** usa o primeiro label do plano, em ordem, e não mais um `(:Pedido)` fixo. Teste com um projeto sem `Pedido`.
- **Texto de `_descricao` na aresta:** o esquema diz "a definição da relação (ou o rótulo, quando a relação não tem definição)".
- **Página de uso:** a nota agora diz que o limite 4 foi resolvido, e os limites 1 e 3 em parte (o 1 continua sem aresta até o `Conceito`; o 3 sem as perguntas de competência).
- **Guia:** os limites de memória e tempo trazem a medição da Task 10, com o método.
- **Verificador da demo:** uma classe sem definição não falha mais (`coalesce` dos dois lados).
