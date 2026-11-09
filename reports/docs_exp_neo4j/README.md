# Exportar a ontologia e os dados para o Neo4j

Guia de uso, do primeiro uso até ver o grafo. O motivo de cada escolha e as provas estão em `docs/neo4j/exportacao.md`.

**O que você vai ter no fim:** os dados do cliente como um grafo no Neo4j, com a ontologia junto: classes, definições e hierarquia. Quem carrega no banco é o plugin n10s, e o akme gera o RDF que ele recebe.

```
ontologia aprovada (etapas 1 a 4)
   → etapa 5: chave e tipos de cada tabela, aprovados na página de revisão
   → dry-run: o akme gera o RDF e mostra o que vai gravar
   → carga: você confirma, o n10s grava, o akme confere o banco
   → Neo4j Browser: você vê e consulta o grafo
```

## Parte 1. Primeiro uso, uma vez por máquina

### 1.1 Ferramentas

| Ferramenta | Para quê | Como conferir |
|---|---|---|
| Docker Desktop, aberto | Roda o Neo4j local | `docker ps` responde sem erro |
| uv | Roda o akme | `uv --version` |
| curl e shasum | Baixam e conferem o plugin | já vêm no macOS |

### 1.2 Instalar o extra do Neo4j no akme

```bash
uv sync --inexact --extra dev --extra neo4j
```

O extra `neo4j` instala o driver Python. Sem ele, a carga para com "Instale com: uv sync --extra neo4j".

### 1.3 Baixar o plugin n10s

```bash
mkdir -p .neo4j/plugins
curl -L -o .neo4j/plugins/neosemantics-2025.06.1.jar \
  https://github.com/neo4j-labs/neosemantics/releases/download/2025.06.1/neosemantics-2025.06.1.jar
shasum -a 256 .neo4j/plugins/neosemantics-2025.06.1.jar
```

O resultado do `shasum` tem que ser:

```
4c461087e08405c7cb472ecfefc043e9e8ed93628ed74988e4fda1f1bac54b3e
```

Se for diferente, apague o arquivo e baixe de novo. Cuidado com o arquivo que termina em `-javadoc.jar`: ele não é o plugin. A pasta `.neo4j/` é ignorada pelo Git.

### 1.4 Preencher o `.env`

Copie o modelo e preencha só as três linhas do Neo4j:

```bash
cp .env.example .env      # só se ainda não existir um .env
```

```
AKME_NEO4J_URI=bolt://127.0.0.1:7687
AKME_NEO4J_USER=neo4j
AKME_NEO4J_PASSWORD=<escolha uma senha com pelo menos 8 caracteres>
```

- **A senha é sua.** Ela vira a senha do Neo4j no passo seguinte.
- **Não compartilhe.** Não cole a senha em chat nem em documento, e não faça commit do `.env`, que já é ignorado pelo Git.
- **O akme não lê o `.env` sozinho.** Antes de cada carga, carregue o arquivo no terminal com o comando do passo 3.3.

### 1.5 Subir o Neo4j com o plugin

```bash
set -a; . ./.env; set +a
NEO4J_AUTH="neo4j/$AKME_NEO4J_PASSWORD" docker run -d --name akme-neo4j \
  --publish=127.0.0.1:7474:7474 --publish=127.0.0.1:7687:7687 \
  --env NEO4J_AUTH --env NEO4J_dbms_security_procedures_unrestricted='n10s.*' \
  --volume=akme-neo4j-data:/data --volume="$PWD/.neo4j/plugins":/plugins:ro \
  neo4j:2026.10.1
```

O que cada parte faz:

| Parte | Por quê |
|---|---|
| `127.0.0.1:` nas portas | Só a sua máquina acessa o banco |
| `NEO4J_AUTH` | Define a senha na primeira vez em que o volume é criado |
| `procedures_unrestricted='n10s.*'` | Libera as rotinas do n10s |
| `--volume=...:/data` | Os dados sobrevivem quando o contêiner é recriado |
| `--volume=...plugins:/plugins:ro` | Entrega o plugin ao Neo4j, só para leitura |

Espere uns 30 segundos e confira:

```bash
docker exec -e NEO4J_USERNAME=$AKME_NEO4J_USER -e NEO4J_PASSWORD=$AKME_NEO4J_PASSWORD akme-neo4j \
  cypher-shell "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'n10s' RETURN count(name)"
```

O resultado deve ser um número acima de 50, que é a quantidade de rotinas `n10s`. Se der erro de autenticação, veja "Problemas comuns".

**Nas próximas vezes**, o contêiner já existe. Basta `docker start akme-neo4j`.

## Parte 2. Decidir chave e tipos, a etapa 5

Faça esta parte depois que a ontologia estiver aprovada nas etapas 1 a 4, e de novo sempre que tabelas ou colunas mudarem.

A ontologia diz o que cada tabela significa, mas não diz duas coisas que o Neo4j precisa:
- **a chave:** qual coluna identifica cada linha, para a mesma linha não virar dois nós;
- **os tipos:** quais colunas são data, inteiro ou decimal. Sem tipo, a coluna vira texto, e não dá para somar nem comparar datas.

1. **No chat, peça ao agente:** "prepare a exportação para o Neo4j". Ele chama `suggest_sources`, ajusta o que exige julgamento e registra uma proposta por tabela. Exemplos de ajuste: chave composta, dinheiro como decimal. Cada proposta é conferida contra os dados na hora.
2. **Abra a página de revisão** no endereço que o agente indicar, normalmente http://127.0.0.1:8765/.
3. **Em "Por tipo", clique em "Exportação Neo4j".** Cada cartão é uma tabela, com:
   - a chave;
   - os tipos;
   - o que o dado mostra, por exemplo "2 de 2 valores convertem para data".

   Tabelas que não aparecem na ontologia vêm marcadas para ficar de fora.
4. **Corrija o que discordar.** Em "Ajustar texto antes de aceitar", mude a chave ou os tipos no formato `coluna: tipo, coluna: tipo`. Os tipos possíveis são `string`, `integer`, `float` e `date`. A página confere a edição contra os dados.
5. **Clique em "Aceitar tudo", depois em "Salvar decisões", e use "Aplicar decididas" com o seu nome.**

"Aceitar tudo" aceita só o que não exige escolha sua. O que precisar de escolha continua na lista, com o motivo. As decisões ficam no `content.yml`, versionadas com a ontologia.

## Parte 3. Exportar

### 3.1 Ver antes de gravar: dry-run

```bash
uv run akme publish --target neo4j
```

O dry-run não conecta ao banco. Ele gera `docs/publish/neo4j.nt` e devolve:

| Campo | O que fazer |
|---|---|
| `nodes`, `relationships` | Confira se as quantidades fazem sentido, por exemplo uma linha por nó |
| `problems` | Se não estiver vazio, a carga será recusada. Cada item diz o que corrigir |
| `warnings` | A carga acontece, mas leia: por exemplo, linhas sem par numa relação ficam sem aresta |

### 3.2 Banco vazio ou do mesmo projeto

O banco aceita um projeto só. Na primeira carga, o akme grava uma marca com o nome do projeto. Depois disso, o banco só aceita esse mesmo projeto. Para carregar outro projeto, use outro banco ou limpe este:

```bash
docker exec -e NEO4J_USERNAME=$AKME_NEO4J_USER -e NEO4J_PASSWORD=$AKME_NEO4J_PASSWORD akme-neo4j \
  cypher-shell "MATCH (n) DETACH DELETE n; DROP CONSTRAINT n10s_unique_uri IF EXISTS;"
```

**Atenção:** esse comando apaga tudo o que está no banco.

### 3.3 Carregar

```bash
set -a; . ./.env; set +a
uv run akme publish --target neo4j --no-dry-run
```

Antes de perguntar, a CLI mostra:
- `destino`: o endereço do banco;
- o resumo de nós, arestas e avisos;
- `banco`: o estado atual, que deve ser `vazio` ou `projeto <nome>, sera atualizado`.

Responda `y` para gravar. No fim, confira `"verification": {"ok": true}`: é o akme contando no banco o que foi previsto.

**Repetir a carga é seguro.** A mesma linha atualiza o mesmo nó, e nada é duplicado.

## Parte 4. Ver o grafo

No fim da carga, a CLI imprime "Para ver o grafo", com consultas prontas do seu projeto. Os passos são:

1. Abra **http://localhost:7474** no navegador. É o Neo4j Browser, que vem com o Neo4j.
2. Entre com o usuário `neo4j` e a senha de `AKME_NEO4J_PASSWORD`.
3. Cole uma das consultas impressas e aperte Enter. Por exemplo:

```cypher
// os dados, sem os nós da ontologia
MATCH (n)-[r]->(m) WHERE NOT n:Class AND NOT n:Relationship RETURN n, r, m LIMIT 300

// a ontologia: classes e hierarquia; clique numa classe para ver a definição
MATCH p = (:Class)-[:SCO]->(:Class) RETURN p
```

Na lateral do Browser, o ícone de banco lista os labels, que são as classes, e os tipos de relação. Clique em um deles para ver os nós.

Cada nó de dado tem:
- o label da classe, por exemplo `Sinistro`;
- o label `Resource`;
- a propriedade `uri`, que é a identidade dele;
- uma propriedade por coluna, com o tipo aprovado.

## Problemas comuns

| Mensagem | Causa | O que fazer |
|---|---|---|
| `publish neo4j --no-dry-run exige AKME_NEO4J_URI...` | O `.env` não foi carregado neste terminal | Rode `set -a; . ./.env; set +a` |
| `falha no Neo4j: ... Connection refused` | O Neo4j não está rodando | Abra o Docker Desktop e rode `docker start akme-neo4j` |
| `falha no Neo4j: ... authentication failure` | A senha do `.env` não é a do banco. O `NEO4J_AUTH` só vale na primeira criação do volume | Use a senha original, ou recrie o volume, o que apaga os dados |
| `o servidor nao tem o plugin n10s` | O plugin não foi montado ou não é o jar certo | Refaça o passo 1.3 e recrie o contêiner do passo 1.5 |
| `o banco ja tem o projeto X` | O banco tem outro projeto | Use outro banco ou limpe este, como no passo 3.2 |
| `o banco tem N no(s) sem a marca` | O banco tem dados que não vieram do akme | Use um banco vazio |
| `fonte X sem chave e tipos aprovados na etapa 5` | Falta a decisão da tabela | Faça a Parte 2 para essa tabela |
| `o bloco neo4j do akme.yml nao e mais lido` | Configuração antiga | Apague o bloco `neo4j` do `akme.yml` e faça a Parte 2 |
| `warning: VIRTUAL_ENV=.venv does not match` | Aviso do uv, sem efeito | Pode ignorar |
| As tools novas não aparecem no chat | O servidor MCP ainda roda o código antigo | No Claude Code, rode `/mcp` e reinicie o `akme` |

## Limites conhecidos

- **Linhas apagadas na origem:** continuam no grafo. Para refletir a origem, limpe o banco e carregue de novo.
- **Dinheiro:** é gravado como `FLOAT`, porque o Neo4j não tem tipo decimal. Não serve para conciliação contábil.
- **Tamanho:** até 100 mil linhas por tabela. Acima disso, a carga é recusada.
