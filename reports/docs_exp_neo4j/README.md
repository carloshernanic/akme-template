# Exportar a ontologia e os dados para o Neo4j

Guia de uso, do primeiro uso até ver o grafo. O motivo de cada escolha e as provas estão nas páginas de `docs/exportacao-neo4j/` (visão geral em `index.md`, provas em `task-9-aceitacao.md`; `uv run --extra docs mkdocs serve`).

**O que você vai ter no fim:** os dados do cliente como um grafo no Neo4j, com a ontologia junto: conceitos, definições, hierarquia e relações como setas.

**Você não escreve código nem script.** A exportação é sempre o mesmo comando, para qualquer projeto: o akme lê o que foi aprovado nas etapas e monta o grafo sozinho. Não precisa instalar nenhum plugin no Neo4j. O script `examples/local_demo/verificar_neo4j.py` não faz parte da exportação; é uma conferência que vale só para a demo.

```
ontologia aprovada (etapas 1 a 4)
   → etapa 5: chave e tipos de cada tabela, aprovados na página de revisão
   → dry-run: o akme gera o arquivo do grafo e mostra o que vai gravar, sem tocar no banco
   → carga: você confirma, o akme grava em Cypher e confere o banco
   → Neo4j Browser: você vê e consulta o grafo
```

## Antes de começar

- **Rode todos os comandos na pasta raiz do projeto** (a que tem o `akme.yml`).
- **Neo4j 5.23 ou mais novo.** O guia usa o `neo4j:2026.10.1`. Num Neo4j mais antigo, a carga para antes de gravar, com `o Neo4j X e antigo: a carga exige Neo4j 5.23 ou mais novo`.
- **Use a mesma janela do terminal do começo ao fim de cada parte.** Alguns comandos dependem de variáveis carregadas antes, e elas se perdem quando você abre outra janela.
- **A Parte 1 é feita uma vez por máquina** e leva uns 10 minutos, quase tudo esperando o download do Neo4j. Depois, cada exportação é só a Parte 2 e a Parte 3.

Palavras que aparecem no guia:

| Termo | O que é |
|---|---|
| Neo4j | Banco de dados em grafo: guarda nós (ex: um pedido) e arestas (ex: "feito por cliente") |
| Docker, contêiner | O Docker roda o Neo4j isolado na sua máquina, sem instalar nada no sistema. O contêiner é esse Neo4j rodando |
| Volume | Pasta do Docker onde o Neo4j guarda os dados. Sobrevive quando o contêiner é recriado |
| Cypher | A linguagem de consulta do Neo4j. O akme grava o grafo com comandos Cypher, e você usa Cypher para consultar no Browser |
| Conceito (camada da ontologia) | Nó com o label `Conceito`, um por classe da ontologia (ex: `Pedido`), com a definição. As relações da ontologia aparecem como setas `RELACAO_ONTOLOGIA` entre conceitos, com o nome da relação em `nome` |
| Sincronização | No fim de cada carga, o akme apaga do banco o que é deste projeto e não veio da origem nesta carga. Assim as contagens do banco batem com as da origem lida nesta carga |
| Dry-run | Ensaio: gera tudo e mostra o resumo, sem gravar no banco |

## Parte 1. Primeiro uso, uma vez por máquina

Resumo do que você vai fazer:

- [ ] 1.1 Conferir as ferramentas
- [ ] 1.2 Instalar o driver do Neo4j no akme
- [ ] 1.3 Criar o `.env` com a senha do banco
- [ ] 1.4 Subir o Neo4j e conferir

### 1.1 Conferir as ferramentas

| Ferramenta | Para quê |
|---|---|
| Docker Desktop, **aberto** | Roda o Neo4j local. Instale em https://www.docker.com/products/docker-desktop/ |
| uv | Roda o akme. Se você já usa o akme, já tem |

```bash
docker ps > /dev/null && echo "docker ok"; uv --version
```

Deve aparecer `docker ok` e a versão do uv. Se aparecer `Cannot connect to the Docker daemon`, o Docker Desktop está fechado: abra o aplicativo, espere ele iniciar e rode de novo.

### 1.2 Instalar o driver do Neo4j no akme

O driver é a biblioteca Python que o akme usa para falar com o banco.

```bash
uv sync --inexact --extra dev --extra neo4j
```

O `--inexact` mantém os outros extras que você já tenha instalado. O fim da saída mostra `+ neo4j==...`, ou nada, se já estava instalado. O aviso `VIRTUAL_ENV=.venv does not match` é inofensivo e pode ser ignorado.

### 1.3 Criar o `.env` com a senha do banco

O `.env` guarda o endereço, o usuário e a senha do Neo4j fora do código. Se ainda não existe um `.env` na raiz, copie o modelo:

```bash
cp .env.example .env
```

Abra o `.env` no seu editor. O modelo tem linhas de outros bancos (Postgres, Snowflake, Databricks): deixe-as como estão. Preencha só as três do Neo4j, no fim do arquivo:

```
AKME_NEO4J_URI=bolt://127.0.0.1:7687
AKME_NEO4J_USER=neo4j
AKME_NEO4J_PASSWORD=<invente uma senha com pelo menos 8 caracteres>
# opcional: endereço do Neo4j Browser, se não for http://localhost:7474
# AKME_NEO4J_BROWSER_URL=http://localhost:7474
# opcional: nome do banco, num servidor com vários bancos (Enterprise); sem ela, o banco padrão
# AKME_NEO4J_DATABASE=neo4j
```

- **URI:** `bolt` é o protocolo do Neo4j; `127.0.0.1:7687` é a sua própria máquina, na porta padrão.
- **USER:** `neo4j` é o administrador que já vem no Neo4j.
- **PASSWORD:** você inventa agora. Ela vira a senha do banco no passo 1.4. Guarde: trocar depois apaga os dados (ver "Problemas comuns").
- **Não compartilhe.** Não cole a senha em chat nem em documento. O `.env` já é ignorado pelo Git.
- **BROWSER_URL (opcional):** só se o Neo4j Browser abrir em outro endereço, por exemplo um contêiner publicado com `--publish=127.0.0.1:27474:7474`. Sem ela, o akme mostra `http://localhost:7474` no fim da carga (com uma URI do Aura, o console; o Aura não foi testado).
- **DATABASE (opcional):** só num servidor com vários bancos (Neo4j Enterprise). Todas as conexões do akme, da prévia à conferência, usam esse banco. Sem ela, vale o banco padrão do servidor, que é o caso do Docker deste guia (e, pela documentação da Neo4j, do Aura, não testado).

Para conferir sem mostrar a senha:

```bash
grep -c '^AKME_NEO4J_[A-Z]*=.\+' .env
```

O resultado deve ser `3`. Se der menos, alguma das três linhas ficou vazia: o comando abaixo diz qual, sem mostrar valores.

```bash
grep '^AKME_NEO4J' .env | awk -F= '{print $1, ($2=="" ? "VAZIA" : "ok")}'
```

**Quem lê o `.env`:** o akme lê sozinho, toda vez que roda. O Docker não: nos comandos `docker` deste guia, carregue antes o `.env` no terminal com `set -a; . ./.env; set +a`. Isso vale só para aquela janela do terminal.

### 1.4 Subir o Neo4j e conferir

```bash
set -a; . ./.env; set +a
NEO4J_AUTH="neo4j/$AKME_NEO4J_PASSWORD" docker run -d --name akme-neo4j \
  --publish=127.0.0.1:7474:7474 --publish=127.0.0.1:7687:7687 \
  --env NEO4J_AUTH --volume=akme-neo4j-data:/data \
  --env NEO4J_browser_post__connect__cmd='guide http://127.0.0.1:8765/neo4j/guia' \
  neo4j:2026.10.1
```

A linha `NEO4J_browser_post__connect__cmd` é opcional: com ela, o Neo4j Browser abre sozinho o tutorial do projeto a cada conexão (Parte 4). O tutorial só abre com o `akme review` ligado; sem ele, o Browser mostra um erro no painel do guia e segue normal.

Na primeira vez, o Docker baixa a imagem do Neo4j, o que leva alguns minutos. No fim, aparece um código longo: é o identificador do contêiner, sinal de que ele subiu.

O que cada parte faz:

| Parte | Por quê |
|---|---|
| `set -a; . ./.env; set +a` | Carrega a senha do `.env` neste terminal, para o Docker usar |
| `127.0.0.1:` nas portas | Só a sua máquina acessa o banco |
| `7474` e `7687` | 7474 é o Neo4j Browser (a tela no navegador); 7687 é por onde o akme conecta |
| `NEO4J_AUTH` | Define a senha na primeira vez em que o volume é criado |
| `--volume=...:/data` | Os dados sobrevivem quando o contêiner é recriado |
| `NEO4J_browser_post__connect__cmd` (opcional) | Abre o tutorial do projeto no Browser a cada conexão |

Espere uns 30 segundos e confira, **na mesma janela do terminal**:

```bash
docker exec -e NEO4J_USERNAME=$AKME_NEO4J_USER -e NEO4J_PASSWORD=$AKME_NEO4J_PASSWORD akme-neo4j \
  cypher-shell "CALL dbms.components() YIELD name, versions WHERE name = 'Neo4j Kernel' RETURN versions[0] AS versao"
```

O resultado deve ser:

```
versao
"2026.10.1"
```

É a prova de que o Neo4j está no ar e aceita a sua senha. Se der `Connection refused`, o Neo4j ainda está iniciando: espere mais um pouco e repita. Outros erros estão em "Problemas comuns".

**Nas próximas vezes**, o contêiner já existe. Basta abrir o Docker Desktop e rodar `docker start akme-neo4j`.

## Parte 2. Decidir chave e tipos, a etapa 5

Faça esta parte depois que a ontologia estiver aprovada nas etapas 1 a 4, e de novo sempre que tabelas ou colunas mudarem.

A ontologia diz o que cada tabela significa, mas não diz duas coisas que o Neo4j precisa:
- **a chave:** qual coluna identifica cada linha, para a mesma linha não virar dois nós;
- **os tipos:** quais colunas são data, inteiro ou decimal. Sem tipo, a coluna vira texto, e não dá para somar nem comparar datas.

1. **No chat, peça ao agente:** "prepare a exportação para o Neo4j". Ele chama `suggest_sources`, ajusta o que exige julgamento e registra uma proposta por tabela. Exemplos de ajuste: chave composta, dinheiro como decimal. Cada proposta é conferida contra os dados na hora, lendo a tabela inteira.
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

O dry-run não conecta ao banco. Ele lê cada tabela inteira, em blocos, e gera dois arquivos em `docs/publish/`:
- `neo4j.cypher`: o resumo no topo, os comandos Cypher da ontologia e os modelos dos comandos de dados (sem os dados). Se houver problema, o topo do arquivo diz `NAO EXECUTE`;
- `neo4j_schema.md`: o esquema do grafo para um LLM ler (seção "Usar com um LLM").

O dry-run devolve:

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

Não precisa carregar o `.env` antes: o akme lê sozinho. Antes de perguntar, a CLI mostra o destino, o que vai gravar e o que o banco tem hoje. Saída real com a demo, num banco que já tinha a demo carregada:

```
destino: bolt://127.0.0.1:7687
linhas: 43 em 7 lote(s) de dados, mais a ontologia
nos previstos:
  Cliente: 8
  ItemPedido: 17
  Pedido: 10
  Produto: 8
arestas previstas:
  contem: 17
  pertenceA: 10
  referencia: 17
no banco hoje, deste projeto:
  Cliente: banco 8 -> origem 8
  ItemPedido: banco 17 -> origem 17
  Pedido: banco 10 -> origem 10
  Produto: banco 8 -> origem 8
arestas no banco hoje, deste projeto (por tipo):
  contem: banco 17 -> origem 17
  pertenceA: banco 10 -> origem 10
  referencia: banco 17 -> origem 17
avisos:
  a carga apaga deste projeto o que nao vier da origem nesta carga
banco: projeto local_demo, sera atualizado
Executar no alvo neo4j? Esta acao altera a plataforma do cliente. [y/N]:
```

Como ler:
- `destino`: o endereço do banco, sem usuário nem senha;
- `nos previstos` e `arestas previstas`: o que a origem tem hoje;
- `no banco hoje`: por label, quantos nós deste projeto o banco tem (`banco`) e quantos vai ter depois da carga (`origem`). Se `banco` for maior que `origem`, a linha termina com `pelo menos N serao removidos`, e uma linha abaixo soma o total (`a sincronizacao apaga pelo menos N no(s) deste projeto`). É "pelo menos" porque uma linha trocada na origem, com outra chave, também sai, e a contagem não mostra isso (seção 3.3). Um label que saiu da ontologia aparece com `origem 0`. Leia esses números antes de responder `y`;
- `arestas no banco hoje`: o mesmo, por tipo de aresta. Um tipo que esta carga não grava mais (relação renomeada ou excluída) aparece com `origem 0`, e os avisos dizem que consultas com esse nome deixam de achar arestas;
- `banco`: o estado atual. Na primeira carga deve ser `vazio`; nas seguintes, `projeto <nome>, sera atualizado`.

Se o banco já tiver outro projeto, nós que não vieram do akme ou dados da exportação antiga, a CLI para aqui e não grava nada; veja a seção 3.4 e "Problemas comuns".

Responda `y` para gravar. Se a sincronização for apagar mais de 20% dos nós de algum label (por exemplo, uma extração que falhou e deixou a tabela quase vazia), a CLI pede uma segunda confirmação: digite o número total de nós que serão removidos, o mesmo de `a sincronizacao apaga pelo menos N no(s)`. Com qualquer outra resposta, nada é gravado.

No fim, confira o campo `verification`: o `ok` dentro dele deve ser `true`. É o akme contando no banco o que foi previsto: nós por label e arestas por relação. Ele não compara valores. `ok` quer dizer que as contagens do banco batem com as da origem lida nesta carga, não que cada valor foi conferido. Uma comparação de valores, por amostra, existe só para a demo: `examples/local_demo/amostra_valores.py`. O campo `removed` diz quantos nós e arestas a sincronização apagou. Em seguida, a CLI imprime "Para ver o grafo", com consultas prontas do seu projeto, e como abrir o tutorial do projeto no Browser (Parte 4).

**Se você carregou com a versão de 12/11/2026 que gravava as arestas em maiúsculas (`PERTENCE_A`):** as arestas voltaram ao nome exato da ontologia (`pertenceA`). Na próxima carga, a prévia mostra `PERTENCE_A: banco N -> origem 0, pelo menos N serao removidas` e um aviso; a sincronização apaga as de nome antigo e grava as novas, e o campo `removed` mostra esse número. É esperado. Consultas escritas com o nome em maiúsculas param de achar arestas; troque pelo nome da ontologia.

**Repetir a carga é seguro.** A mesma linha atualiza o mesmo nó, e nada é duplicado.

### 3.3 Sincronização: as contagens do banco batem com as da origem

Cada carga recebe uma marca com a data e a hora (`_carga`), gravada em todo nó e toda aresta que ela escreve. No fim, o akme apaga o que é deste projeto e ficou com uma marca antiga.

**O que é apagado:**
- nós de linhas que foram apagadas na origem;
- arestas cuja chave mudou de alvo (ex: o pedido passou para outro cliente);
- nós e arestas de classes ou relações que saíram da ontologia, inclusive os `Conceito`.

Os valores não dependem da sincronização: cada nó é regravado com a linha da origem, então uma célula que ficou vazia some do nó na hora em que ele é gravado.

**A origem é lida de novo na carga.** O resumo que você aprovou vem da leitura feita antes da confirmação. Se alguém editar a origem entre a prévia e a carga sem mudar o número de linhas, o banco recebe a versão nova, mas o resumo aprovado não mostra essa mudança. Só a contagem de linhas é conferida entre as duas leituras (regra 3 abaixo).

**As três regras de segurança:**
1. **Só o que é deste projeto.** O akme só apaga nós com o nome deste projeto. Nada de outro projeto, e nunca a marca do projeto. Um banco com outro projeto ou com nós que não vieram do akme é recusado antes de gravar.
2. **Só depois que tudo foi gravado.** Se um lote, a ontologia ou a leitura da origem falhar, nenhum nó ou aresta é apagado. A mensagem diz quantos lotes já foram gravados, e repetir a carga completa é seguro.
3. **Só se a origem não mudou no meio.** O akme conta de novo as linhas durante a carga. Se o número for diferente do plano mostrado antes da confirmação, ele para sem apagar nada (`a origem mudou durante a carga: ...`). Rode a carga de novo.
4. **Só se nenhuma outra carga começou depois.** Logo depois de conferir o banco, a carga grava a sua marca na marca do projeto (`carga_atual`). Cada bloco de nós e de arestas, cada comando da ontologia e do esquema e cada comando que apaga só funcionam enquanto essa marca for a dela. Se outra carga do mesmo projeto começou depois (outro terminal, outro consultor no mesmo banco), a mais antiga para no primeiro bloco seguinte, sem gravar nem apagar mais nada, com `outra carga deste projeto comecou depois desta; nada foi apagado`. A mais nova grava tudo de novo e, na sua sincronização, apaga o que a antiga tinha gravado antes e ela não regravou.

Além disso, o plano recusa uma tabela com chave aprovada e nenhuma linha (`fonte X sem linhas`): carregá-la apagaria o label inteiro. Se a tabela deve mesmo sair do grafo, exclua-a na etapa 5.

### 3.4 Banco com outro projeto

O banco aceita um projeto só. Na primeira carga, o akme grava uma marca com o nome do projeto, e depois disso só aceita esse mesmo projeto. É uma proteção: a sincronização de um projeto não pode apagar os dados de outro.

**O nome do projeto é a identidade do grafo.** É o `project` do `akme.yml` (ou, sem ele, o nome da pasta). Dois clones com o mesmo nome apontando para o mesmo banco são, para o akme, o mesmo projeto: a carga de um apaga o que o outro gravou e não veio da sua origem. Dê um `project` diferente a cada cópia que use o mesmo banco.

Se a CLI disser `o banco ja tem o projeto X`, você tem duas saídas:
- **Limpar este banco**, se não precisa mais do projeto X no Neo4j. Os arquivos do projeto X no repositório não são afetados, e dá para carregá-lo de novo depois.
- **Usar outro contêiner**, numa porta diferente, trocando o `AKME_NEO4J_URI` do `.env`. Assim os dois projetos ficam carregados ao mesmo tempo.

Para limpar:

```bash
set -a; . ./.env; set +a
docker exec -e NEO4J_USERNAME=$AKME_NEO4J_USER -e NEO4J_PASSWORD=$AKME_NEO4J_PASSWORD akme-neo4j \
  cypher-shell "MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS;"
```

O comando não mostra nada quando dá certo. Para conferir, rode o mesmo `docker exec` com `cypher-shell "MATCH (n) RETURN count(n) AS nos"`: o resultado deve ser `0`.

**Atenção:** esse comando apaga tudo o que está no banco, sem volta.

## Parte 4. Ver o grafo

1. Abra **http://localhost:7474** no navegador. É o Neo4j Browser, que vem com o Neo4j. Ele só abre com o Neo4j rodando; antes do passo 1.4, mostra "Connection to instance failed".
2. Entre com o usuário `neo4j` e a senha que você pôs em `AKME_NEO4J_PASSWORD`.
3. Cole uma das consultas impressas pela CLI no campo do topo e aperte Enter. Por exemplo:

```cypher
// os dados, sem os nós da ontologia
MATCH (n)-[r]->(m) WHERE NOT n:Conceito RETURN n, r, m LIMIT 300

// a ontologia: conceitos e relações; clique num conceito para ver a definição
MATCH p = (:Conceito)-[:RELACAO_ONTOLOGIA]->(:Conceito) RETURN p
```

Na lateral do Browser, o ícone de banco lista os labels, que são as classes, e os tipos de relação. Clicar num tipo de relação traz setas com as duas pontas. Clicar num label traz só bolinhas, sem as setas. Dois cliques numa bolinha trazem os vizinhos dela. A opção *Automatically connect result nodes* (Settings) só liga as bolinhas que já estão na tela.

### 4.1 Abrir o tutorial do projeto

Todo `publish --target neo4j`, dry-run ou carga, gera um tutorial curto do projeto para o Neo4j Browser: `docs/publish/neo4j_guia.html`. São seis páginas de navegação, com consultas que rodam com um clique:

1. **O que tem aqui:** cada classe com o número de registros;
2. **A ontologia:** classes e relações com os nomes do `schema.ttl`;
3. **Os dados:** o mapa calculado pelo Neo4j, uma bolinha por classe;
4. **Explorar:** um registro de cada classe e tudo o que está ligado a ele;
5. **Como navegar:** o que cada clique do Browser faz;
6. **Perguntas em português:** o caminho para o console da Aura (seção 4.2; o gerador de Cypher e o AuraDB não foram testados).

Para abrir:

1. Num terminal, na pasta do projeto, ligue o servidor local: `uv run akme review`. Ele serve o tutorial em `http://127.0.0.1:8765/neo4j/guia`. Deixe-o aberto. Se aparecer `o servidor da pagina local esta desatualizado: pare e rode uv run akme review de novo`, já há um `akme review` antigo na porta 8765 (por exemplo, aberto antes de atualizar o akme): pare-o com Ctrl+C no terminal dele (ou feche esse terminal) e rode de novo. O akme não encerra o processo sozinho.
2. No campo do topo do Browser, rode `:guide http://127.0.0.1:8765/neo4j/guia`. O guia abre num painel à esquerda; avance com *Next*.
3. Em cada bloco de consulta, passe o mouse e clique no botão de rodar.

O servidor só entrega o guia ao Neo4j Browser: `http://localhost:7474`, `http://127.0.0.1:7474`, a porta de `AKME_NEO4J_BROWSER_URL` (Docker com outra porta) e `https://console.neo4j.io`. Outro site aberto no navegador não consegue lê-lo.

**Seta `RELACAO_ONTOLOGIA`** = relação da ontologia; o nome do TTL está em `nome`. Para ver o nome na seta: no painel *Results overview*, clique no chip `RELACAO_ONTOLOGIA` e escolha `nome` como legenda (o Browser guarda a escolha). A página "A ontologia" do tutorial já desenha com os nomes quando o banco tem o plugin APOC (setas virtuais, nada gravado).

Para abrir sozinho a cada conexão, use a linha opcional `NEO4J_browser_post__connect__cmd` do `docker run` (passo 1.4). Para um contêiner que já existe, recrie-o com a linha nova (o volume guarda os dados).

As consultas do tutorial também estão em `docs/publish/neo4j_consultas.csv`. No Browser, ícone **Queries**, **Upload**, escolha o arquivo: aparece a pasta `akme <projeto>`. As consultas importadas ficam só naquele navegador.

### 4.2 Perguntas em portugues pelo Aura console

O console da Neo4j na nuvem (`console.neo4j.io`) pode ser ligado ao banco local de graça. O **Query** dele tem um gerador de Cypher: você escreve a pergunta em português e ele propõe a consulta. Também traz Bloom (exploração visual) e Dashboards. O que foi testado, em 12/11/2026, foi só a conexão do console a um banco local em Docker, por Mateus; o gerador de Cypher não foi testado, e o AuraDB (o banco na nuvem) também não. Os passos da conexão:

1. Entre em `console.neo4j.io` com a conta Neo4j.
2. No menu da esquerda, em **Studio**, abra **Query** (ou Bloom, ou Dashboards).
3. Na janela "Connect to Neo4j", aba **Self-managed** (conexão rápida): Connection URL `neo4j://127.0.0.1:7687` (a porta Bolt do seu contêiner), usuário `neo4j`, a senha do `.env`.
4. Clique em **Connect**.

O que precisa saber:

- **Conexão rápida, sem TLS, a cada sessão.** "Add deployment" (Instances) só aceita `https`, `neo4j+s` ou `bolt+s`; o banco local, sem TLS, não pode ser salvo ali.
- **O gerador de Cypher precisa do plugin APOC** no banco: no Docker, acrescente `--env NEO4J_PLUGINS='["apoc"]'` ao `docker run` do passo 1.4 (não testado com o gerador). Confira a consulta proposta antes de usar a resposta: ninguém a revisou.
- **O Bloom não responde perguntas de número.** "Quantas cidades?" devolve nós, não um número. Para números, use o Query.

Cuidados com dado real de cliente, antes de usar o console:

- consultas salvas no console ficam na nuvem da Neo4j e podem conter valores do cliente;
- o gerador usa modelos de terceiros, e não está claro o que ele lê além do esquema;
- o Browser local envia telemetria por padrão (`client.allow_telemetry=false` na configuração do servidor desliga; não testado);
- combine com o cliente antes.

Detalhes e fontes: `docs/exportacao-neo4j/pesquisa-visualizacao.md`, seções 1.3 e 1.4.

Cada nó de dado tem:
- o label da classe, por exemplo `Pedido`;
- uma propriedade por coluna preenchida, com o nome da coluna e o tipo aprovado;
- `_id`, que é a identidade dele, formada pela chave (ex: `1001`, ou `1001/CIM-50` numa chave composta);
- `_projeto` e `_carga`, usadas pela proteção do destino e pela sincronização;
- só se você ligar a opção (abaixo), `_descricao`, a definição da classe, igual à do `Conceito`. Sem a opção, que é o padrão, a definição fica no `Conceito` de mesmo nome: `MATCH (c:Conceito {nome: 'Pedido'}) RETURN c.definicao`;
- `name`, a legenda que o Browser mostra na bolinha: o label, o início da chave e o valor de uma coluna descritiva (por exemplo, `ItemPedido 1001/CIM-50 100`). Se a tabela tiver uma coluna `name`, vale a dela.

**`_descricao` nos dados (opcional, desligada por padrão).** Para gravar a definição em cada nó e aresta de dado, e vê-la ao clicar no nó do Browser, acrescente ao `akme.yml`:

```yaml
neo4j:
  descricao_nos_dados: true
```

e carregue de novo. Custa disco: no Olist, o banco ficou 14% maior numa base nova e 43% maior regravando por cima de uma carga anterior. Para voltar, apague o bloco e carregue de novo: a carga apaga a propriedade. O bloco `neo4j` só aceita essa opção.

As arestas de dados têm o nome exato da relação na ontologia, por exemplo `(:Pedido)-[:pertenceA]->(:Cliente)`; com a opção ligada, também uma `_descricao`: a definição da relação ou, enquanto a ontologia não tiver uma, o rótulo (por exemplo, `pertence a`). Uma relação inversa sem aresta própria (`possuiPedido`) é a mesma aresta lida ao contrário: `MATCH (c:Cliente)<-[:pertenceA]-(p:Pedido)`. Na camada da ontologia, cada relação do `schema.ttl`, inversas incluídas, aparece como seta `RELACAO_ONTOLOGIA` entre os conceitos, com o nome em `nome`: `(:Conceito {nome: 'Pedido'})-[:RELACAO_ONTOLOGIA {nome: 'pertenceA'}]->(:Conceito {nome: 'Cliente'})`, mais `publicada_nos_dados`, que diz se ela tem aresta nos dados; a hierarquia aparece como `SUBCLASSE_DE`. Por os tipos serem diferentes, o mapa do próprio Neo4j (`CALL db.schema.visualization()`, página "Os dados" do tutorial) desenha só as ligações que existem nos dados. Os termos do negócio ficam em nós `Termo`, ligados ao seu conceito: `MATCH p = (:Conceito)-[:TEM_TERMO]->(:Termo) RETURN p`. Os dados não se ligam à ontologia por arestas, só pelo label.

## Usar com um LLM

As ferramentas oficiais para um LLM consultar o Neo4j, o [MCP da Neo4j](https://github.com/neo4j/mcp) e o `neo4j-graphrag`, precisam do plugin APOC Core. No Aura, pela documentação da Neo4j, ele já vem (não testado). No Docker, ligue-o ao criar o contêiner, acrescentando `--env NEO4J_PLUGINS='["apoc"]'` ao `docker run` do passo 1.4.

Essas ferramentas montam o esquema só com os nomes e os tipos: não leem `_descricao`, nem `Conceito`, nem `Termo`. Por isso o akme escreve, a cada carga, um esquema descritivo com as definições, os termos de cada coluna, as métricas (com "não somar após juntar com"), o glossário, as regras e as precedências. Ele fica em dois lugares:
- no arquivo `docs/publish/neo4j_schema.md`, para colar no prompt ou passar ao `neo4j-graphrag` (parâmetro `neo4j_schema` do `Text2CypherRetriever`);
- no próprio banco, na propriedade `esquema` da marca do projeto, para quem só tem acesso ao Neo4j.

Texto pronto para as instruções do LLM:

```
Antes de responder, rode MATCH (p:_AkmeProjeto) RETURN p.esquema e siga o esquema.
```

O esquema avisa o que mais confunde um LLM neste grafo: as arestas de dado têm o nome da relação (`pertenceA`), e entre os `Conceito` a mesma relação é uma seta `RELACAO_ONTOLOGIA` com `nome: 'pertenceA'`; toda contagem de dados usa o label do dado (por exemplo `(:Pedido)`) ou filtra `NOT n:Conceito`.

## Recomeçar do zero

Para apagar tudo da Parte 1 e refazer como se fosse a primeira vez (por exemplo, para testar este guia):

```bash
docker rm -f akme-neo4j                # remove o contêiner
docker volume rm akme-neo4j-data       # apaga os dados e a senha do banco
```

Depois, apague ou edite as três linhas `AKME_NEO4J_*` do `.env` e comece na Parte 1. A ontologia e as decisões da etapa 5 ficam intactas: estão no `content.yml`, não no Neo4j.

Se você seguiu uma versão antiga deste guia, pode apagar também a pasta `.neo4j/` da raiz (`rm -rf .neo4j`). Ela guardava o plugin da exportação antiga e não é mais usada. Se apagar, recrie o contêiner antigo, que apontava para essa pasta: rode `docker rm -f akme-neo4j` e depois o comando do passo 1.4. O volume `akme-neo4j-data` não é apagado, então os dados e a senha continuam.

## Problemas comuns

| Mensagem | Causa | O que fazer |
|---|---|---|
| `Cannot connect to the Docker daemon` | O Docker Desktop está fechado | Abra o aplicativo, espere iniciar e repita |
| `The container name "/akme-neo4j" is already in use` | O contêiner já existe, de um uso anterior | Rode `docker start akme-neo4j` em vez do `docker run` |
| `publish neo4j --no-dry-run exige AKME_NEO4J_...` | Falta o `.env` na raiz do projeto, ou a linha citada está vazia | Refaça o passo 1.3 |
| `falha no Neo4j: ... Connection refused` | O Neo4j não está rodando, ou ainda está iniciando | Rode `docker start akme-neo4j`, espere 30 segundos e repita |
| `:guide` mostra erro 404, ou `o servidor da pagina local esta desatualizado` | Um `akme review` aberto antes de atualizar o akme ainda ocupa a porta 8765, sem a rota do guia | Pare esse `akme review` (Ctrl+C no terminal dele) e rode `uv run akme review` de novo. O akme não encerra o processo sozinho |
| `Connection to instance failed`, no Neo4j Browser | O Neo4j não está rodando, ou o contêiner ainda não foi criado. O Browser só funciona depois do passo 1.4 | Faça o passo 1.4 ou rode `docker start akme-neo4j`, espere 30 segundos e recarregue a página |
| `falha no Neo4j: ... authentication failure` | A senha do `.env` não é a do banco. O `NEO4J_AUTH` só vale na primeira criação do volume | Volte a senha original no `.env`, ou recomece do zero, o que apaga os dados |
| `docker exec ...` falha com usuário ou senha vazios | O `.env` não foi carregado nesta janela do terminal | Rode `set -a; . ./.env; set +a` e repita |
| `erro: banco carregado pela exportacao antiga (n10s); limpe-o com o comando do guia. Nada foi gravado` | O banco foi carregado pela versão anterior do akme, que usava um plugin. Não há migração | Limpe o banco com o comando logo abaixo da tabela e carregue de novo |
| `o banco ja tem o projeto X` | O banco tem outro projeto | Veja a seção 3.4 |
| `o banco tem mais de um projeto do akme: X, Y` | O banco tem marcas de dois ou mais projetos, o que o akme nunca grava sozinho | Limpe o banco (seção 3.4) ou use outro contêiner |
| `o banco tem N no(s) sem a marca` ou `N no(s) que nao vieram do akme` | O banco tem dados que não vieram do akme | Use um banco vazio |
| `lote X de Y falhou: ... nada foi apagado` | Um lote não foi gravado (por exemplo, a conexão caiu) | Corrija a causa e repita a carga completa: é seguro |
| `ontologia: comando N de M falhou: ... nada foi apagado; repetir a carga completa e seguro` | Um comando da camada da ontologia não foi gravado; os lotes de dados já foram | Corrija a causa (por exemplo, a conexão) e repita a carga completa |
| `sincronizacao falhou: ... A carga nova ja esta gravada; parte do que era antigo pode nao ter sido apagado; repetir a carga completa e seguro` | A carga gravou tudo, mas a limpeza do que era antigo parou no meio | Repita a carga completa: ela termina a limpeza |
| `a origem mudou durante a carga: ...` | Alguém alterou a tabela entre a confirmação e a gravação | Rode a carga de novo |
| `outra carga deste projeto comecou depois desta; nada foi apagado. Rode a carga de novo` | Duas cargas do mesmo projeto rodaram ao mesmo tempo; a mais nova fica com a limpeza | Espere a outra terminar e rode a carga de novo |
| `o Neo4j X e antigo: a carga exige Neo4j 5.23 ou mais novo` | O servidor é anterior ao 5.23 | Atualize o Neo4j (o guia usa `neo4j:2026.10.1`) |
| `N linha(s) de X com colunas a mais ou a menos; primeira: linha L` | Linha do CSV ou da planilha com mais ou menos colunas que o cabeçalho (vírgula sem aspas, por exemplo) | Corrija o arquivo na origem: com aspas no campo que tem vírgula. Nada foi gravado |
| `fonte X sem linhas: a carga apagaria do banco todos os nos de ...` | A tabela veio vazia (extração que falhou?) | Confira a extração; se a tabela deve sair do grafo, exclua-a na etapa 5 |
| `identificador recusado: ...` | Nome de classe, relação ou coluna de join com barra invertida seguida de `u` ou com caractere de controle | Renomeie na ontologia ou na origem |
| `erro: UnicodeDecodeError: ...` (ou outro nome de erro) | Erro inesperado ao ler a origem ou falar com o banco, por exemplo um CSV que não está em UTF-8 | Corrija a causa citada; nada foi gravado se o erro veio antes da confirmação |
| `carga executada, mas o banco diverge do previsto: ...` | O banco não ficou com as contagens do plano | Mostre a mensagem ao agente; os dados continuam gravados |
| `fonte X sem chave e tipos aprovados na etapa 5` | Falta a decisão da tabela | Faça a Parte 2 para essa tabela |
| `fonte X com mais de uma classe` | Termos de classes diferentes mapeados para a mesma tabela | Mostre a mensagem ao agente; a correção é na ontologia |
| `o bloco neo4j do akme.yml nao le mais keys` (ou `types`, `sources`) | Configuração antiga, de antes da etapa 5 | Apague essas chaves do bloco `neo4j` do `akme.yml` (ele só aceita `descricao_nos_dados`) e faça a Parte 2 |
| `neo4j.descricao_nos_dados no akme.yml deve ser true ou false` | Valor como `sim` ou `"true"` entre aspas | Escreva `true` ou `false`, sem aspas |
| `... nao existe nos dados: X.<U+FEFF>coluna; o nome tem caractere invisivel: ...` (ou `coluna inexistente em X: <U+FEFF>...`) | O nome na ontologia ou na proposta tem um caractere que não aparece na tela (BOM do início de um CSV, espaço de largura zero, espaço não separável), marcado como `<U+...>` | Mostre a mensagem ao agente: a correção é reescrever o nome sem o caractere, por proposta na página de revisão |
| `warning: VIRTUAL_ENV=.venv does not match` | Aviso do uv, sem efeito | Pode ignorar |
| As tools novas não aparecem no chat | O servidor MCP ainda roda o código antigo | No Claude Code, rode `/mcp` e reinicie o `akme` |

### Banco da exportação antiga

A versão anterior do akme carregava o grafo por um plugin, que deixava no banco nós e uma restrição próprios. O akme reconhece esse banco e recusa antes de gravar qualquer coisa. Para limpar, **na mesma janela do terminal**:

```bash
set -a; . ./.env; set +a
docker exec -e NEO4J_USERNAME=$AKME_NEO4J_USER -e NEO4J_PASSWORD=$AKME_NEO4J_PASSWORD akme-neo4j \
  cypher-shell "MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS; DROP CONSTRAINT n10s_unique_uri IF EXISTS;"
```

O comando não mostra nada quando dá certo. Depois, rode a carga de novo (seção 3.2): a CLI deve mostrar `banco: vazio`. **Atenção:** apaga tudo o que está no banco, sem volta. Se o contêiner antigo tem o plugin montado, não precisa recriá-lo: o akme não usa o plugin. Só recrie se apagar a pasta `.neo4j/` (veja "Recomeçar do zero").

## Limites conhecidos

- **Tamanho:** não há teto de linhas. Cada tabela é lida em blocos de 5.000 linhas, e o akme guarda em memória só as chaves e os valores de join.
- **Memória e tempo:** no Olist inteiro (cerca de 446 mil linhas, com os comentários acentuados das avaliações), o dry-run levou 2,24 s com 144 MB, e a carga num banco vazio levou 34,1 s, com 356 MB de memória residente máxima no processo do akme; na demo, 0,39 s e 3,18 s. Medidos com `/usr/bin/time -l` sobre o `akme publish`, uma vez, numa máquina (Apple M5, 24 GB), na rodada final. O Olist é um registro de execução (dados e ontologia fora do repositório, numa cópia com três correções); detalhes em `docs/exportacao-neo4j/task-9-aceitacao.md`. O driver do Neo4j guarda parte da memória do texto acentuado em memória nativa, que o Python não libera. Em máquinas com pouca memória, feche outros programas antes de carregar.
- **Memória do plano proporcional ao número de chaves:** o plano não guarda as linhas, mas guarda um `_id` por linha da tabela que está lendo e uma contagem por valor de cada coluna de join. A ordem de grandeza: no Olist (446 mil linhas), o dry-run usou cerca de 144 MB; extrapolando, para 10 milhões de linhas, de 1,5 a 2 GB só de chaves, e cerca de 13 minutos de carga; 100 milhões não cabem numa máquina comum.
- **Carga sempre completa, sem incremental:** cada carga lê a origem inteira e regrava todos os nós e arestas, mesmo que só uma linha tenha mudado.
- **Duas cargas ao mesmo tempo:** a marca `_carga` tem precisão de milissegundos, e a trava da seção 3.3 (regra 4) faz a carga mais antiga parar sem gravar nem apagar mais nada. Sobra uma janela de milissegundos: um bloco da carga antiga que já estava em andamento quando a nova gravou a marca ainda pode terminar; a sincronização da nova apaga o que ele gravou e a nova não regravou. Se a carga nova começar entre os dois comandos da sincronização, a antiga para com `outra carga deste projeto comecou durante a sincronizacao`: rode a carga de novo.
- **A sincronização varre todos os nós:** para achar o que é deste projeto, a sincronização e as consultas de estado da prévia e da carga olham todos os nós, porque `_projeto` não tem índice (um índice exigiria um label comum a todos os nós). Num banco grande, essas etapas podem ser as mais demoradas.
- **Sem tipo `datetime` (a lacuna que mais pesa no uso):** os tipos da etapa 5 são `string`, `integer`, `float` e `date`. Uma data com hora, como `2017-10-02 10:56:33`, fica como texto; para comparar prazos, a consulta precisa cortar a hora (`date(left(p.order_delivered_customer_date, 10))`). No Olist, todas as datas ficaram assim. Número com vírgula decimal (`1,5`) é recusado para `float`: converta na origem ou deixe como texto.
- **CSV e XLSX aparam diferente:** na planilha, o akme tira os espaços das pontas de cada célula e trata célula só com espaços como vazia; no CSV, o valor fica como está. A mesma tabela nos dois formatos pode gerar `_id` diferentes quando há espaço nas pontas da chave.
- **Linha com colunas a mais ou a menos:** no CSV, linha com colunas a mais ou a menos é recusada pelo plano, com o número da linha onde começa a primeira (`N linha(s) de X com colunas a mais ou a menos`). Na planilha, só valor além do cabeçalho é detectado: célula vazia no fim da linha não se distingue de coluna faltando. Corrija o arquivo antes de carregar. Linha totalmente em branco no CSV é pulada e não conta, exceto num CSV de uma coluna só: lá ela é um registro com valor vazio, recusado como chave vazia. A etapa 5 (`add_source`) recusa a linha malformada como o plano.
- **Dinheiro:** é gravado como `FLOAT`, porque o Neo4j não tem tipo decimal. Não serve para conciliação contábil.
- **`_descricao` ligada ocupa espaço:** com a opção ligada, o texto da definição é repetido em cada nó e aresta de dado. No Olist, o banco foi de 443 para 507 MiB numa base nova (+14%), e a Task 10 mediu +43% regravando por cima. Por isso a opção vem desligada.
- **Relações sem definição:** a ontologia ainda não exige definição nas relações, então, com a opção ligada, a `_descricao` das arestas costuma ser só o rótulo.
- **Aura não testado:** tudo neste guia foi testado com o Neo4j local em Docker. O AuraDB e o Enterprise não foram testados; a conexão do console da Aura ao banco local foi testada uma vez (seção 4.2).
- **Tutorial só nesta máquina:** o `akme review` serve o tutorial em `127.0.0.1`. Para um time, o arquivo `docs/publish/neo4j_guia.html` precisa de um endereço com CORS que todos alcancem. Não testamos o `:guide` no Query do console da Aura.
- **Legenda automática:** a legenda `name` usa a primeira coluna mapeada da tabela que não é chave nem join, sem julgamento. Para outra legenda, ponha uma coluna `name` na origem.
