# Teste do n10s

**Registro histórico:** este teste levou à troca do exportador em 05/11/2026. O `cypher.py` citado abaixo foi removido; o estado atual está em [exportacao.md](exportacao.md).

**Objetivo:** decidir com prova, e não só com documentação, se o n10s substitui ou complementa o exportador próprio (`akme/tools/cypher.py`).

**Regra:** os critérios abaixo foram escritos antes de rodar o teste e não mudam depois. O resultado é registrado como sair, inclusive se favorecer o n10s.

## O que é testado

| Item | Escolha | Motivo |
|---|---|---|
| Dados | Demo `examples/local_demo`, 43 linhas | Mesma base do exportador próprio, com gabarito conhecido |
| Neo4j | P1: `2025.06.2`, par indicado no `pom.xml` do n10s `2025.06.1`. P2: `2026.10.1`, a versão que usamos | P1 é o teste justo do n10s; P2 mede se ele funciona na nossa versão |
| n10s | `2025.06.1`, última versão publicada | Versão atual do projeto |
| Ambiente | Contêineres descartáveis, só em `127.0.0.1` e em portas diferentes | Não toca no banco `akme-neo4j` |
| Entrada R1 | RDF gerado hoje pelo alvo `rdf` do template | Mostra o que o caminho entrega sem código novo |
| Entrada R2 | RDF correto, gerado só para o teste, com chaves, relações e tipos | Isola a capacidade do n10s dos defeitos do nosso RDF |

**Defeitos conhecidos em R1, antes do teste:** o `mappings.yarrrml.yml` não tem nenhuma relação entre nós, identifica `ItemPedido` por `qt_itens`, grava datas e valores sem tipo e marca `Pedido` também como a métrica `Faturamento`. Logo, o caminho pelo n10s exige corrigir e manter o gerador de RDF (`to_yarrrml`).

## Critérios

| # | Pergunta | Passa se |
|---|---|---|
| C1 | Instala e inicia? | O servidor sobe com o plugin e `n10s.graphconfig.init` roda |
| C2 | A ontologia entra no grafo? | `n10s.onto.import` cria as classes e o `subClassOf` de `schema.ttl` |
| C3 | Os dados entram completos? | Nós por classe 8/17/10/8 e arestas 10/17/17, como no gabarito |
| C4 | Os valores ficam iguais? | 216 células iguais aos CSVs |
| C5 | Os tipos ficam certos? | Datas como data e valores como número, sem perda |
| C6 | Repetir a importação não duplica? | Mesmas contagens e mesmo conteúdo depois da segunda importação |
| C7 | A semântica é consultável? | Consulta por hierarquia (`Entity`) e por definição funciona |
| C8 | Valida regras? | Uma shape SHACL simples aponta uma violação plantada |
| C9 | A consulta de negócio é natural? | "Produtos do pedido 1001" escrita em Cypher e respondida corretamente |
| C10 | Quanto código fica conosco? | Linhas que teríamos que manter, comparadas às do `cypher.py` |

**Conferência fora do teste:** o n10s não confere a origem nem recusa dados ruins. Isso já é sabido pela documentação e não é critério de aprovação, mas entra na decisão.

## Resultado (05/11/2026)

**Resumo sincero:** com um RDF correto, o n10s carregou a demo tão bem quanto o nosso exportador e ainda levou a ontologia para o grafo, o que o nosso não faz. Ele funcionou também no Neo4j `2026.10.1`, ao contrário do risco que a pesquisa apontava. Ele não elimina código nosso: a parte difícil (chaves, relações, tipos e conferência) só muda de lugar, para o gerador de RDF.

| # | Critério | P1 (2025.06.2) | P2 (2026.10.1) | R1, RDF do template |
|---|---|---|---|---|
| C1 | Instala e inicia | Passa: 55 procedimentos `n10s` | Passa: 55 procedimentos | Não se aplica |
| C2 | Ontologia no grafo | Passa: 9 classes, 5 `SCO`, com `label` e `comment` | Passa, igual | Não se aplica |
| C3 | Dados completos | Passa: 8/17/10/8 e 10/17/17 | Passa, igual | **Falha:** 16 itens e 0 arestas |
| C4 | Valores | Passa: 216 células, 0 diferenças | Passa, igual | **Falha:** colunas não mapeadas somem |
| C5 | Tipos | Passa: `DATE`, `INTEGER`, `FLOAT`, e `nf` como texto | Passa, igual | **Falha:** tudo texto |
| C6 | Repetir a importação | Passa: conteúdo, identidades e arestas iguais | Passa, igual | Passa |
| C7 | Semântica consultável | Passa: `n10s.inference.nodesLabelled('Entity')` devolve os 43 nós; definição de `Pedido` legível | Passa, igual | Não testado |
| C8 | SHACL | **Falha** com nomes limpos (`IGNORE`): "The graph is not namespace aware". **Passa** com `SHORTEN`: aponta a violação plantada | Mesmo resultado | Não testado |
| C9 | Consulta de negócio | Passa com nomes limpos: `ARE-M3`=5, `ARG-20`=10, `CIM-50`=100. Com `SHORTEN`, a mesma consulta não acha nada, porque os nomes viram `ns0__Pedido` | Passa, igual | **Falha:** sem arestas |
| C10 | Código nosso | Gerador de RDF do teste com 20 linhas, mas com chaves e tipos escritos no próprio código | Igual | `to_yarrrml` com 31 linhas e com defeitos |

**O que mais o teste mostrou:**
- Todo nó ganha o label `Resource` e a propriedade `uri`, e o banco ganha os nós `_GraphConfig`, `Class` e `Relationship`. Para consultar só os dados, é preciso filtrar esses nós.
- O R1 prova que o alvo `rdf` do template hoje não serve para o Neo4j: identifica itens pela quantidade, não tem relações e não tipa valores.
- Nenhum critério testou recusa de dados ruins ou conferência com a origem: o n10s não faz isso, e o nosso exportador faz.

**O que o teste não provou:**
- **Produção:** o aviso da Neo4j Labs continua valendo; o projeto não é aprovado para produção, e a compatibilidade com 2026.10.1 foi observada, não declarada.
- **Aura:** o n10s não roda lá, segundo a documentação.
- **Instalação no cliente:** o plugin exige acesso de administrador ao servidor do cliente.
- **Escala:** só 43 linhas.
- **Mudanças na origem:** linha apagada ou célula esvaziada não foram testadas, nem no n10s nem no nosso exportador.

**O que muda na análise anterior:**
- **Estava errado:** a pesquisa inferiu que, sem versão para 2026.x, o n10s provavelmente não rodaria na nossa versão. Ele rodou.
- **Estava exagerado:** com `IGNORE`, o grafo tem nomes do domínio, com exceção de `Resource` e `uri`, e não tem a cara de triplas descrita.
- **Continua valendo:** aviso de produção, ausência no Aura, ausência de conferência, e SHACL que só funciona com nomes prefixados.
- **Novo:** o caminho pelo n10s não dispensa código nosso. Chaves, relações e tipos precisam ser gerados no RDF, e isso exige o mesmo conhecimento que o `cypher.py` usa.

## Decisão

Em 05/11/2026, o usuário decidiu usar o n10s, com nomes limpos (`IGNORE`) e mantendo a camada de recusa e conferência do akme. O SHACL do n10s fica de fora, porque não funcionou com nomes limpos. A implementação está em `akme/tools/n10s.py`, e o RDF que ela gera para a demo é idêntico ao R2 deste teste (300 triplas, comparadas como grafos).

## Como repetir

- **Imagens:** `neo4j:2025.06.2` e `neo4j:2026.10.1`.
- **Plugin:** `neosemantics-2025.06.1.jar`, sha256 `4c461087e08405c7cb472ecfefc043e9e8ed93628ed74988e4fda1f1bac54b3e`, montado em `/plugins`, com `NEO4J_dbms_security_procedures_unrestricted=n10s.*`.
- **Contêineres:** descartáveis (`--rm`), nas portas `127.0.0.1:17474` e `17687`. O banco `akme-neo4j` não foi tocado.
- **Arquivos:** roteiro `teste-n10s/teste_n10s.py` e saídas completas em `teste-n10s/*.json`.
