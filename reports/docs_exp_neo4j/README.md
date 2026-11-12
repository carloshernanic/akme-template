# Exportar a ontologia e os dados para o Neo4j

Guia de uso, do primeiro uso até ver o grafo. O motivo de cada escolha e as provas estão em `docs/neo4j/exportacao.md`.

**O que você vai ter no fim:** os dados do cliente como um grafo no Neo4j, com a ontologia junto: classes, definições e hierarquia.

**Você não escreve código nem script.** A exportação é sempre o mesmo comando, para qualquer projeto: o akme lê o que foi aprovado nas etapas e monta o grafo sozinho. O script `examples/local_demo/verificar_neo4j.py` não faz parte da exportação; é uma conferência que vale só para a demo.

```
ontologia aprovada (etapas 1 a 4)
   → etapa 5: chave e tipos de cada tabela, aprovados na página de revisão
   → dry-run: o akme gera o arquivo do grafo e mostra o que vai gravar, sem tocar no banco
   → carga: você confirma, o n10s grava, o akme confere o banco
   → Neo4j Browser: você vê e consulta o grafo
```

## Antes de começar

- **Rode todos os comandos na pasta raiz do projeto** (a que tem o `akme.yml`).
- **Use a mesma janela do terminal do começo ao fim de cada parte.** Alguns comandos dependem de variáveis carregadas antes, e elas se perdem quando você abre outra janela.
- **A Parte 1 é feita uma vez por máquina** e leva uns 15 minutos, quase tudo esperando downloads. Depois, cada exportação é só a Parte 2 e a Parte 3.

Palavras que aparecem no guia:

| Termo | O que é |
|---|---|
| Neo4j | Banco de dados em grafo: guarda nós (ex: um pedido) e arestas (ex: "feito por cliente") |
| Docker, contêiner | O Docker roda o Neo4j isolado na sua máquina, sem instalar nada no sistema. O contêiner é esse Neo4j rodando |
| Volume | Pasta do Docker onde o Neo4j guarda os dados. Sobrevive quando o contêiner é recriado |
| RDF | Formato de dados em triplas (sujeito, propriedade, valor). O akme gera o grafo nesse formato |
| n10s (neosemantics) | Plugin que ensina o Neo4j a ler RDF. É ele que grava o arquivo do akme no banco |
| Dry-run | Ensaio: gera tudo e mostra o resumo, sem gravar no banco |

## Parte 1. Primeiro uso, uma vez por máquina

Resumo do que você vai fazer:

- [ ] 1.1 Conferir as ferramentas
- [ ] 1.2 Instalar o driver do Neo4j no akme
- [ ] 1.3 Baixar o plugin n10s
- [ ] 1.4 Criar o `.env` com a senha do banco
- [ ] 1.5 Subir o Neo4j com o plugin e conferir

### 1.1 Conferir as ferramentas

| Ferramenta | Para quê |
|---|---|
| Docker Desktop, **aberto** | Roda o Neo4j local. Instale em https://www.docker.com/products/docker-desktop/ |
| uv | Roda o akme. Se você já usa o akme, já tem |
| curl e shasum | Baixam e conferem o plugin. Já vêm no macOS |

```bash
docker ps > /dev/null && echo "docker ok"; uv --version; which curl shasum
```

Deve aparecer `docker ok`, a versão do uv e dois caminhos. Se aparecer `Cannot connect to the Docker daemon`, o Docker Desktop está fechado: abra o aplicativo, espere ele iniciar e rode de novo.

### 1.2 Instalar o driver do Neo4j no akme

O driver é a biblioteca Python que o akme usa para falar com o banco.

```bash
uv sync --inexact --extra dev --extra neo4j
```

O `--inexact` mantém os outros extras que você já tenha instalado. O fim da saída mostra `+ neo4j==...`, ou nada, se já estava instalado. O aviso `VIRTUAL_ENV=.venv does not match` é inofensivo e pode ser ignorado.

### 1.3 Baixar o plugin n10s

```bash
mkdir -p .neo4j/plugins
curl -L -o .neo4j/plugins/neosemantics-2025.06.1.jar \
  https://github.com/neo4j-labs/neosemantics/releases/download/2025.06.1/neosemantics-2025.06.1.jar
shasum -a 256 .neo4j/plugins/neosemantics-2025.06.1.jar
```

O `curl` mostra uma barra de progresso até 12,2 MB. O `shasum` calcula a impressão digital do arquivo, que tem que ser exatamente:

```
4c461087e08405c7cb472ecfefc043e9e8ed93628ed74988e4fda1f1bac54b3e
```

Se for diferente, o arquivo veio corrompido: apague (`rm .neo4j/plugins/*.jar`) e baixe de novo. Cuidado com o arquivo que termina em `-javadoc.jar`: ele não é o plugin. A pasta `.neo4j/` é ignorada pelo Git.

### 1.4 Criar o `.env` com a senha do banco

O `.env` guarda o endereço, o usuário e a senha do Neo4j fora do código. Se ainda não existe um `.env` na raiz, copie o modelo:

```bash
cp .env.example .env
```

Abra o `.env` no seu editor. O modelo tem linhas de outros bancos (Postgres, Snowflake, Databricks): deixe-as como estão. Preencha só as três do Neo4j, no fim do arquivo:

```
AKME_NEO4J_URI=bolt://127.0.0.1:7687
AKME_NEO4J_USER=neo4j
AKME_NEO4J_PASSWORD=<invente uma senha com pelo menos 8 caracteres>
```

- **URI:** `bolt` é o protocolo do Neo4j; `127.0.0.1:7687` é a sua própria máquina, na porta padrão.
- **USER:** `neo4j` é o administrador que já vem no Neo4j.
- **PASSWORD:** você inventa agora. Ela vira a senha do banco no passo 1.5. Guarde: trocar depois apaga os dados (ver "Problemas comuns").
- **Não compartilhe.** Não cole a senha em chat nem em documento. O `.env` já é ignorado pelo Git.

Para conferir sem mostrar a senha:

```bash
grep -c '^AKME_NEO4J_[A-Z]*=.\+' .env
```

O resultado deve ser `3`. Se der menos, alguma das três linhas ficou vazia: o comando abaixo diz qual, sem mostrar valores.

```bash
grep '^AKME_NEO4J' .env | awk -F= '{print $1, ($2=="" ? "VAZIA" : "ok")}'
```

**Quem lê o `.env`:** o akme lê sozinho, toda vez que roda. O Docker não: nos comandos `docker` deste guia, carregue antes o `.env` no terminal com `set -a; . ./.env; set +a`. Isso vale só para aquela janela do terminal.

### 1.5 Subir o Neo4j com o plugin

```bash
set -a; . ./.env; set +a
NEO4J_AUTH="neo4j/$AKME_NEO4J_PASSWORD" docker run -d --name akme-neo4j \
  --publish=127.0.0.1:7474:7474 --publish=127.0.0.1:7687:7687 \
  --env NEO4J_AUTH --env NEO4J_dbms_security_procedures_unrestricted='n10s.*' \
  --volume=akme-neo4j-data:/data --volume="$PWD/.neo4j/plugins":/plugins:ro \
  neo4j:2026.10.1
```

Na primeira vez, o Docker baixa a imagem do Neo4j, o que leva alguns minutos. No fim, aparece um código longo: é o identificador do contêiner, sinal de que ele subiu.

O que cada parte faz:

| Parte | Por quê |
|---|---|
| `set -a; . ./.env; set +a` | Carrega a senha do `.env` neste terminal, para o Docker usar |
| `127.0.0.1:` nas portas | Só a sua máquina acessa o banco |
| `7474` e `7687` | 7474 é o Neo4j Browser (a tela no navegador); 7687 é por onde o akme conecta |
| `NEO4J_AUTH` | Define a senha na primeira vez em que o volume é criado |
| `procedures_unrestricted='n10s.*'` | Libera as rotinas do n10s |
| `--volume=...:/data` | Os dados sobrevivem quando o contêiner é recriado |
| `--volume=...plugins:/plugins:ro` | Entrega o plugin ao Neo4j, só para leitura |

Espere uns 30 segundos e confira, **na mesma janela do terminal**:

```bash
docker exec -e NEO4J_USERNAME=$AKME_NEO4J_USER -e NEO4J_PASSWORD=$AKME_NEO4J_PASSWORD akme-neo4j \
  cypher-shell "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'n10s' RETURN count(name)"
```

O resultado deve ser um número acima de 50: é a quantidade de rotinas `n10s`, a prova de que o plugin carregou. Se der `Connection refused`, o Neo4j ainda está iniciando: espere mais um pouco e repita. Outros erros estão em "Problemas comuns".

**Nas próximas vezes**, o contêiner já existe. Basta abrir o Docker Desktop e rodar `docker start akme-neo4j`.

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

Antes de tudo, confira que o Neo4j está rodando: `docker start akme-neo4j` (se já estiver, não faz nada).

### 3.1 Ver antes de gravar: dry-run

```bash
uv run akme publish --target neo4j
```

O dry-run não conecta ao banco. Ele gera `docs/publish/neo4j.nt` e devolve:

| Campo | O que fazer |
|---|---|
| `nodes`, `relationships` | Confira se as quantidades fazem sentido, por exemplo um nó por linha da tabela |
| `problems` | Se não estiver vazio, a carga será recusada. Cada item diz o que corrigir |
| `warnings` | A carga acontece, mas leia: por exemplo, linhas sem par numa relação ficam sem aresta |

Se aparecer um problema que exige mudar a ontologia (por exemplo, "fonte X com mais de uma classe"), volte ao agente no chat e mostre a mensagem.

### 3.2 Carregar

```bash
uv run akme publish --target neo4j --no-dry-run
```

Não precisa carregar o `.env` antes: o akme lê sozinho. Antes de perguntar, a CLI mostra:
- `destino`: o endereço do banco;
- o resumo de nós, arestas e avisos;
- `banco`: o estado atual. Na primeira carga deve ser `vazio`; nas seguintes, `projeto <nome>, sera atualizado`.

Se o banco já tiver outro projeto, a CLI para aqui e não grava nada; veja a seção 3.3.

Responda `y` para gravar. No fim, confira `"verification": {"ok": true}`: é o akme contando no banco o que foi previsto. Em seguida, a CLI imprime "Para ver o grafo", com consultas prontas do seu projeto.

**Repetir a carga é seguro.** A mesma linha atualiza o mesmo nó, e nada é duplicado.

### 3.3 Banco com outro projeto

O banco aceita um projeto só. Na primeira carga, o akme grava uma marca com o nome do projeto, e depois disso só aceita esse mesmo projeto. É uma proteção: projetos diferentes podem usar os mesmos endereços de nó, e um sobrescreveria o outro.

Se a CLI disser `o banco ja tem o projeto X`, você tem duas saídas:
- **Limpar este banco**, se não precisa mais do projeto X no Neo4j. Os arquivos do projeto X no repositório não são afetados, e dá para carregá-lo de novo depois.
- **Usar outro contêiner**, numa porta diferente, trocando o `AKME_NEO4J_URI` do `.env`. Assim os dois projetos ficam carregados ao mesmo tempo.

Para limpar:

```bash
set -a; . ./.env; set +a
docker exec -e NEO4J_USERNAME=$AKME_NEO4J_USER -e NEO4J_PASSWORD=$AKME_NEO4J_PASSWORD akme-neo4j \
  cypher-shell "MATCH (n) DETACH DELETE n; DROP CONSTRAINT n10s_unique_uri IF EXISTS;"
```

**Atenção:** esse comando apaga tudo o que está no banco, sem volta.

## Parte 4. Ver o grafo

1. Abra **http://localhost:7474** no navegador. É o Neo4j Browser, que vem com o Neo4j. Ele só abre com o Neo4j rodando; antes do passo 1.5, mostra "Connection to instance failed".
2. Entre com o usuário `neo4j` e a senha que você pôs em `AKME_NEO4J_PASSWORD`.
3. Cole uma das consultas impressas pela CLI no campo do topo e aperte Enter. Por exemplo:

```cypher
// os dados, sem os nós da ontologia
MATCH (n)-[r]->(m) WHERE NOT n:Class AND NOT n:Relationship RETURN n, r, m LIMIT 300

// a ontologia: classes e hierarquia; clique numa classe para ver a definição
MATCH p = (:Class)-[:SCO]->(:Class) RETURN p
```

Na lateral do Browser, o ícone de banco lista os labels, que são as classes, e os tipos de relação. Clique em um deles para ver os nós.

Cada nó de dado tem:
- o label da classe, por exemplo `Pedido`;
- o label `Resource`;
- a propriedade `uri`, que é a identidade dele, formada pela chave (ex: `.../Pedido/1001`);
- uma propriedade por coluna, com o tipo aprovado.

## Recomeçar do zero

Para apagar tudo da Parte 1 e refazer como se fosse a primeira vez (por exemplo, para testar este guia):

```bash
docker rm -f akme-neo4j                # remove o contêiner
docker volume rm akme-neo4j-data       # apaga os dados e a senha do banco
rm -rf .neo4j                          # apaga o plugin
```

Depois, apague ou edite as três linhas `AKME_NEO4J_*` do `.env` e comece na Parte 1. A ontologia e as decisões da etapa 5 ficam intactas: estão no `content.yml`, não no Neo4j.

## Problemas comuns

| Mensagem | Causa | O que fazer |
|---|---|---|
| `Cannot connect to the Docker daemon` | O Docker Desktop está fechado | Abra o aplicativo, espere iniciar e repita |
| `The container name "/akme-neo4j" is already in use` | O contêiner já existe, de um uso anterior | Rode `docker start akme-neo4j` em vez do `docker run` |
| `publish neo4j --no-dry-run exige AKME_NEO4J_...` | Falta o `.env` na raiz do projeto, ou a linha citada está vazia | Refaça o passo 1.4 |
| `falha no Neo4j: ... Connection refused` | O Neo4j não está rodando, ou ainda está iniciando | Rode `docker start akme-neo4j`, espere 30 segundos e repita |
| `Connection to instance failed`, no Neo4j Browser | O Neo4j não está rodando, ou o contêiner ainda não foi criado. O Browser só funciona depois do passo 1.5 | Faça o passo 1.5 ou rode `docker start akme-neo4j`, espere 30 segundos e recarregue a página |
| `falha no Neo4j: ... authentication failure` | A senha do `.env` não é a do banco. O `NEO4J_AUTH` só vale na primeira criação do volume | Volte a senha original no `.env`, ou recomece do zero, o que apaga os dados |
| `docker exec ...` falha com usuário ou senha vazios | O `.env` não foi carregado nesta janela do terminal | Rode `set -a; . ./.env; set +a` e repita |
| `o servidor nao tem o plugin n10s` | O plugin não foi montado ou não é o jar certo | Refaça o passo 1.3 e recrie o contêiner do passo 1.5 |
| `o banco ja tem o projeto X` | O banco tem outro projeto | Veja a seção 3.3 |
| `o banco tem N no(s) sem a marca` | O banco tem dados que não vieram do akme | Use um banco vazio |
| `fonte X sem chave e tipos aprovados na etapa 5` | Falta a decisão da tabela | Faça a Parte 2 para essa tabela |
| `fonte X com mais de uma classe` | Termos de classes diferentes mapeados para a mesma tabela | Mostre a mensagem ao agente; a correção é na ontologia |
| `o bloco neo4j do akme.yml nao e mais lido` | Configuração antiga | Apague o bloco `neo4j` do `akme.yml` e faça a Parte 2 |
| `warning: VIRTUAL_ENV=.venv does not match` | Aviso do uv, sem efeito | Pode ignorar |
| As tools novas não aparecem no chat | O servidor MCP ainda roda o código antigo | No Claude Code, rode `/mcp` e reinicie o `akme` |

## Limites conhecidos

- **Linhas apagadas na origem:** continuam no grafo. Para refletir a origem, limpe o banco (seção 3.3) e carregue de novo.
- **Dinheiro:** é gravado como `FLOAT`, porque o Neo4j não tem tipo decimal. Não serve para conciliação contábil.
- **Tamanho:** até 100 mil linhas por tabela. Acima disso, a carga é recusada.
