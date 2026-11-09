# Exportação para o Neo4j

**Situação em 05/11/2026:** a exportação passou a usar o plugin **n10s** (neosemantics). A demo e o `teste_acme` carregam, conferem e repetem sem duplicar pelo caminho novo, no banco `akme-neo4j`. Guia de uso passo a passo: [reports/docs_exp_neo4j/README.md](../../reports/docs_exp_neo4j/README.md).

- Teste e decisão do n10s: [teste-n10s.md](teste-n10s.md)
- Registro do exportador anterior, em Cypher: [historico.md](historico.md)

## Como funciona

```
dados do adapter + ontologia + chave e tipos aprovados na etapa 5 (content.yml)
        ↓
akme gera RDF (N-Triples) e a lista de problemas e avisos   ← dry-run
        ↓
humano lê o resumo e confirma na CLI
        ↓
n10s: unicidade por IRI → configuração → ontologia → dados, em lotes
        ↓
akme conta no banco e compara com a previsão
```

- **O akme gera o RDF** (`akme/tools/n10s.py`). Cada linha vira um recurso com IRI pela chave (`…#Pedido/1001`), cada coluna vira uma propriedade tipada, e cada relação com join vira uma tripla por par ligado. O join é resolvido no Python, a partir dos contratos.
- **O n10s carrega:**
  - a ontologia (`n10s.onto.import.inline`), que vira nós `Class` com `name`, `label`, `comment` e a hierarquia `SCO`;
  - os dados (`n10s.rdf.import.inline`), que viram nós com a classe como label, por exemplo `Pedido`, mais o label `Resource` e a propriedade `uri`.
- **Nomes limpos:** o grafo usa `handleVocabUris: IGNORE`, então as consultas usam nomes do domínio.
- **Dados como parâmetro:** os dados vão como parâmetro da consulta, nunca dentro do texto do Cypher.
- **Métricas:** entram como comentário no arquivo, sem tradução para Cypher.

## Como usar

**Uma vez por máquina:** subir o Neo4j com o plugin.

```bash
mkdir -p .neo4j/plugins
curl -L -o .neo4j/plugins/neosemantics-2025.06.1.jar \
  https://github.com/neo4j-labs/neosemantics/releases/download/2025.06.1/neosemantics-2025.06.1.jar
# sha256 esperado: 4c461087e08405c7cb472ecfefc043e9e8ed93628ed74988e4fda1f1bac54b3e
NEO4J_AUTH="neo4j/<senha do .env>" docker run -d --name akme-neo4j \
  --publish=127.0.0.1:7474:7474 --publish=127.0.0.1:7687:7687 \
  --env NEO4J_AUTH --env NEO4J_dbms_security_procedures_unrestricted='n10s.*' \
  --volume=akme-neo4j-data:/data --volume="$PWD/.neo4j/plugins":/plugins:ro neo4j:2026.10.1
uv sync --inexact --extra dev --extra neo4j
```

**A cada exportação:**

```bash
uv run akme publish --target neo4j               # dry-run: gera docs/publish/neo4j.nt
set -a; . ./.env; set +a                         # AKME_NEO4J_URI, USER e PASSWORD
uv run akme publish --target neo4j --no-dry-run  # resumo, confirmação, carga e conferência
```

No fim da carga, a CLI diz onde ver o grafo:
- o endereço do Neo4j Browser: `http://localhost:7474` no Docker local; no Aura, `https://console.neo4j.io`;
- o usuário;
- consultas prontas com as classes e relações do projeto carregado.

**Chave e tipos de cada tabela**, que a ontologia não traz, são decididos na etapa 5, só quando o alvo é o Neo4j:

1. `suggest_sources` monta um rascunho, sem LLM:
   - a chave vem dos contratos de relação ou de uma chave candidata do profile;
   - os tipos vêm do profile; inteiro com nome de identificador fica texto;
   - tabela sem classe vira exclusão.
2. O agente ajusta o que exige julgamento, como chave composta ou dinheiro como `float`, e propõe um `add_source` por tabela. Cada proposta é conferida contra o dado: chave repetida ou valor que não converte é recusado na hora.
3. O humano decide na página de revisão, grupo "Exportação Neo4j", com "Aceitar tudo". Chave e tipos podem ser editados no cartão, e a edição é conferida de novo.
4. As decisões ficam na seção `sources` do `content.yml`, versionada com a ontologia:

```yaml
sources:
- {source: itens_pedido, key: [id_pedido, sku], types: {qt_itens: integer, vl_item: float}}
- {source: fireclaim, exclude: não aparece em nenhuma relação nem mapping da ontologia}
```

O exportador recusa:
- tabela sem decisão aprovada, e diz quando há proposta pendente;
- o bloco antigo `neo4j` no `akme.yml`.

A tool MCP só roda em dry-run. Quem executa a carga é o humano, na CLI.

**Consulta de exemplo:**

```cypher
MATCH (:Pedido {id_pedido: '1001'})-[:contem]->(i:ItemPedido)-[:referencia]->(p:Produto)
RETURN p.sku, i.qt_itens
```

Para contar só dados, sem os nós da ontologia, filtre `NOT n:Class AND NOT n:Relationship`.

## O que o exportador faz com cada caso

| Caso | Resultado |
|---|---|
| Fonte sem classe, com mais de uma classe ou classe em mais de uma fonte | Recusa |
| Fonte sem chave; chave vazia ou repetida | Recusa |
| Mais de 100 mil linhas | Recusa |
| Valor que não converte sem perda, como `03/07/2026` em `date` | Recusa |
| Tipo, fonte ou coluna inexistente na configuração; chave ou join com tipo diferente de `string` | Recusa |
| Coluna de join ausente, ou relação em que nenhuma linha encontra alvo | Recusa |
| Servidor sem n10s, ou grafo configurado com outro modo de nomes | Recusa, sem gravar |
| Banco com a marca de outro projeto, com dados sem marca ou com nós que não vieram do akme nem do n10s | Recusa antes da confirmação, e de novo antes de gravar |
| n10s carrega menos triplas do que recebeu, ou responde diferente de `OK` | Erro, dizendo quantos lotes já foram gravados |
| Parte das linhas de uma relação sem alvo | Avisa; essas linhas ficam sem aresta |
| Medida sem tipo numérico declarado | Avisa; carrega como texto |
| Coluna com caractere especial, como espaço | Avisa; o nome da propriedade fica codificado, como `Loss%20Ratio` |
| Banco diverge da previsão depois da carga | Erro; os dados continuam gravados |

As recusas de dados acontecem no dry-run, antes de conectar ao banco. As de servidor acontecem antes do primeiro lote.

**Proteção do destino:** a primeira carga num banco vazio grava o nó `(:_AkmeProjeto {projeto})`. Depois disso, o banco só aceita o mesmo projeto. A marca é necessária porque o namespace não distingue projetos: a demo e o `teste_acme` usam o mesmo `https://akme.example/ontology#`. No Neo4j Community há um banco só, então outro projeto exige outro contêiner, ou limpar este.

## Por que este caminho

| Decisão | Motivo | Base |
|---|---|---|
| Neo4j como alvo | Pedido de Gabriel, da McKinsey | Conversa com o usuário |
| n10s para carregar | Leva a ontologia para o grafo; padrão W3C; menos lógica de carga nossa | [teste-n10s.md](teste-n10s.md); decisão do usuário |
| Gerar o RDF no akme, sem Morph-KGC | Funciona com qualquer adapter; o alvo `rdf` atual perde relações e tipos | Teste do n10s, entrada R1 |
| Nomes limpos (`IGNORE`) | Consultas naturais para pessoas e LLM | Decisão do usuário |
| Sem SHACL do n10s | Não funcionou com nomes limpos no teste | Teste do n10s, C8 |
| Manter recusa e conferência do akme | O n10s não confere a origem nem recusa dados ruins | Teste do n10s; decisão do usuário |
| Chave e tipo decididos na etapa 5, com sugestão automática | Identidade estável, tipo que não depende dos dados, nada escrito à mão, decisão versionada | Testes automatizados; demo e `teste_acme` |
| Dinheiro como `xsd:decimal`, gravado como `FLOAT` | O Neo4j não tem tipo decimal; não serve para uso contábil | Teste do n10s, C5; decisão do usuário |
| Docker 2026.10.1 com n10s 2025.06.1 | Funcionou no teste, mas o par não é oficial | Teste do n10s, P2 |

## Provas

| O que foi provado | Resultado | Base |
|---|---|---|
| O RDF do exportador é o mesmo que passou no n10s | 300 triplas, grafos idênticos ao R2 | Comparação com `rdflib.compare` |
| n10s com esse RDF, no Neo4j 2026.10.1 | Dados completos, 216 células iguais, tipos certos, repetição idêntica, ontologia e hierarquia no grafo | Banco descartável, [teste-n10s.md](teste-n10s.md) |
| Recusas, avisos, lotes, parâmetros, plugin ausente e falha parcial | 88 testes de Neo4j e MCP passam | `tests/test_publish_neo4j.py`, com o servidor simulado |
| Suíte completa | 186 passam, 1 pulado, 1 falha | A falha é o teste de Postgres, fora do Neo4j |
| Erro de conexão | Mensagem curta, sem senha | CLI com porta sem serviço |
| Plugin no banco da demo | 55 procedimentos `n10s` | Contêiner `akme-neo4j` recriado |
| Carga da demo pelo n10s | `"executed": 1`, `verification.ok` verdadeiro | Executada pelo usuário, com `echo y` |
| Grafo igual à origem | 31 de 31 verificações, 216 células, tipos, pares de cada relação, 5 `SCO` e definição de `Pedido` | `verificar_neo4j.py`, banco real |
| Repetição da carga, com `onto.import` de novo | Impressão digital idêntica, 31 de 31 verificações, 58 nós no total | Executada pelo usuário |
| Proteção do destino no banco real | Recusou 58 nós sem marca antes de perguntar; banco limpo foi aceito como `vazio`; a carga gravou a marca `local_demo`; `teste_acme` seria recusado | Executada pelo usuário em 06/11/2026 |
| Grafo com a marca | 32 de 32 verificações; conteúdo dos 58 nós de dados e ontologia igual ao da carga 1 | `verificar_neo4j.py` e impressão digital sem o nó da marca |
| Consulta de negócio | Pedido 1001: `ARE-M3`=5, `ARG-20`=10, `CIM-50`=100 | Banco real |

**Teste com outros dados (`examples/teste_acme`, seguros P&C), em 09/11/2026:**

| O que foi provado | Resultado | Base |
|---|---|---|
| Dry-run com 29 fontes, 14 no escopo e 15 excluídas por configuração | 290 triplas, nenhum problema, nenhum aviso além das exclusões | `akme publish --target neo4j` |
| Carga | 54 nós em 14 classes, 56 arestas em 14 relações, `verification.ok` | Executada pelo usuário |
| Grafo contra os CSVs | 21 de 21 verificações: 344 células, pares de cada relação, tipos (`DATE`, `FLOAT`, `STRING`), classes da ontologia e marca do projeto | Verificador independente, só leitura |
| Repetição da carga | Impressão digital idêntica, 89 nós e 99 arestas no total, 21 de 21 verificações | Executada pelo usuário |
| Decisões da etapa 5 pela página de revisão | 29 aplicadas pelo usuário com "Aceitar tudo", sem nada escrito à mão; dry-run com as mesmas 290 triplas | Changelog do `teste_acme` |
| RDF do fluxo contra o banco já carregado | 54 nós, 180 propriedades e 56 arestas idênticos, sem nenhuma diferença; 21 de 21 verificações lendo chave e tipos do `content.yml` | Comparação só de leitura |
| Consulta de negócio | Sinistralidade de 2019 na apólice 31003000336: 6600 / 20000 = 0,33 | Cypher no banco real |

Condições do teste:
- A ontologia do `teste_acme` foi escrita direto nos arquivos, sem o fluxo de aprovação, só para exercitar o exportador.
- Na primeira rodada, chaves e tipos foram escritos à mão no `akme.yml`.
- Depois, `suggest_sources` reproduziu sem ajuda as 6 chaves e os tipos de data, e excluiu as 15 tabelas fora da ontologia. Só os dois valores em dinheiro precisaram de ajuste, de `integer` para `float`. Na demo, a sugestão acertou tudo menos a chave composta dos itens, que ela sinalizou.

**Achado de modelagem:** tabelas de subtipo, como `Premium` sobre `Policy_Amount`, viram dois nós ligados por aresta. No RDF, o mais natural seria um recurso com duas classes. Funciona para consulta, mas é uma decisão a tomar.

**Ainda não provado:**
- Excel, SQL e Aura (onde o n10s não roda).

## O que falta

**Antes do teste com `teste_acme`:**

1. Confirmação digitada, adiada pelo usuário.

**Antes do commit:**

2. Refletir mudanças da origem: o n10s também não apaga linhas ou valores que sumiram.
3. Carregar o mesmo plano que foi revisado: hoje a carga lê a origem de novo depois da confirmação.
4. Conferir valores em qualquer projeto, e não só na demo.

**Depois:**

5. `PERTENCE_A` no lugar de `pertenceA` (decisão D3).
6. Ligar cada nó de dado ao seu nó `Class`, se a consulta por ontologia precisar.
7. Leitura completa com ordem definida, e cargas acima de 100 mil linhas.
8. Decidir o destino do alvo `rdf`, cujo YARRRML perde relações e tipos.

**Riscos do n10s, aceitos na decisão:**
- É projeto da Neo4j Labs, declarado não aprovado para produção.
- Não roda no Aura.
- Exige instalar o plugin no servidor do cliente.
- Ainda não há versão oficial para o Neo4j 2026.x.

**Antes de commitar, não incluir:** `.DS_Store`, `.neo4j/` (já ignorado) e as alterações geradas em `docs/ontology.json` e `docs/ontology.mmd`. Conferir também origem e licença de `examples/teste_acme`.

**Fora do Neo4j, só anotado:**
- A tool MCP ainda executa `snowflake`, `databricks` e `rdf` sem confirmação.
- `test_optional_adapters_fail_clearly` falha com o `psycopg` instalado.
- `connect` ignora o `.r2rml` do `teste_acme`.

**Nota sobre a verificação:** na primeira rodada depois da carga, `verificar_neo4j.py` acusou 1 falha. A contagem de arestas incluía as arestas da ontologia (`SCO`, `DOMAIN`, `RANGE`), enquanto as arestas de dados estavam certas (17/10/17). O erro era do roteiro adaptado. A contagem passou a considerar só nós de dados, e as arestas da ontologia ganharam uma verificação própria.

Depois da limpeza e da carga com marca, as identidades internas mudaram, o que é esperado ao recriar os nós. O conteúdo dos nós, sem a marca, continua com a mesma impressão.

Impressão digital depois da primeira carga, igual depois da repetição: `conteudo_nos` `17623bbd9ed2004a`, `conteudo_arestas` `1bd57c930f3e0417`, `identidades_nos` `209927d0714d67f6`, `identidades_arestas` `8a46b4a3e7a25e22`.

## Fontes

1. Neo4j Labs, [neosemantics](https://neo4j.com/labs/neosemantics/), e [releases no GitHub](https://github.com/neo4j-labs/neosemantics/releases), consultados em 05/11/2026.
2. Neo4j Operations Manual, [Docker: Introduction](https://neo4j.com/docs/operations-manual/current/docker/introduction/), lida em 05/11/2026.
3. PyPI, [neo4j](https://pypi.org/project/neo4j/), versão 6.4.1.
4. Pesquisa completa: `reports/Exportar ontologia para Neo4j.md`.
