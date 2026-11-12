# Pesquisa: como ver o grafo

Pergunta: como apresentar a ontologia e os dados do cliente no Neo4j para que uma pessoa de negócio, que não sabe Cypher, abra o banco e entenda o que vê?

Pesquisa feita em 12/11/2026. O que foi testado rodou no Neo4j 2026.10.1 Community, em Docker, com o Olist completo (projeto `olist`, contêiner descartável `akme-neo4j-t6`). O Browser servido por essa versão se identifica como `query@neo4j-browser-2026.10.21`. Quando algo não foi testado por nós, o texto diz. Quando é opinião, aparece marcado como **(julgamento)**.

> **Decisão posterior (12/11/2026, cerca de 18:35):** esta pesquisa recomendou arestas de dado em UPPER_SNAKE (D3) e `tipo_no_grafo` nas setas de `Conceito`. Depois de ver o mapa, Mateus decidiu o contrário: as arestas de dado mantêm o nome exato do TTL, e as setas entre `Conceito` passam a ter o tipo único `RELACAO_ONTOLOGIA`, com o nome em `nome`. O argumento do mapa nativo continua valendo, porque os tipos seguem diferentes. Estado atual em [Task 11](task-11-tutorial.md).

## Resumo

- **O Neo4j Browser é ferramenta de desenvolvedor.** Sem ajuda, a pessoa cai numa tela de consulta vazia. Clicar num label mostra 25 nós soltos, porque a opção que liga os resultados vem desligada. A legenda do nó cai na primeira propriedade em ordem alfabética, que no nosso grafo era `_carga`.
- **Dá para tornar o Browser utilizável sem Cypher, só com o que o akme gera.** Testamos quatro peças: (1) uma propriedade `name` legível em cada nó; (2) um guia do akme que abre sozinho ao conectar, com blocos que rodam com um clique; (3) consultas salvas, importadas com um clique; (4) tipos de aresta da ontologia diferentes dos tipos de aresta dos dados. Com a quarta, o mapa nativo do Neo4j (`db.schema.visualization`) passa a desenhar o modelo dos dados sem erro. É o pedido do João, de graça.
- **Para exploração visual de verdade, a ferramenta é o Bloom (Explore).** Ele não roda num Community próprio. O caminho gratuito é o console da Aura apontando para o banco local. Mateus testou em 12/11/2026 e funcionou com `neo4j://127.0.0.1:27687`.
- **Ver e responder são usos diferentes.** Bloom e Browser servem para ver ligações. Para perguntas com resposta (contagens, rankings), a pessoa precisa de uma tabela: as consultas salvas, um painel (Dashboards) ou um LLM que devolva o texto e o Cypher usado. Pedir "quantas cidades?" no Bloom devolve mil nós, não um número.
- **Recomendação:** no Community local, o Browser com as quatro peças acima, que o akme gera de forma determinística por projeto. Como complemento opcional, o console da Aura (Bloom, Query com assistente, Dashboards), com os cuidados de dados da seção 1.4. Quando o alvo for o Aura, as mesmas peças, mais um painel importável.

## 1. Ferramentas e para quem

### 1.1 O que existe em 2026

| Ferramenta | Para quem | Community local | Aura | Custo e licença |
|---|---|---|---|---|
| **Neo4j Browser** (no 2026.10 é o Query do console, empacotado) | Desenvolvedor | Sim, em `:7474` | Como "Query" | Grátis |
| **Bloom / Explore** | Negócio e analista: busca, perspectivas, legendas, estilo por regra | Não como plugin; só pelo console da Aura (1.3) | Sim | Plugin de servidor exige chave de licença; no Desktop, só para banco local Enterprise |
| **Console da Aura**: Query, Bloom, Dashboards, Import | Os dois públicos | Sim, ligando o banco ao console (1.3) | Nativo | Grátis para Community ligado ao console, segundo a Neo4j |
| **Dashboards** (Aura e Desktop 2) | Negócio: tabelas e gráficos prontos | Pelo console ou pelo Desktop | Sim | Importa JSON do NeoDash |
| **NeoDash (Labs)** | Painéis | Rodaria | Não se aplica | O README diz "This project is no longer maintained, use at your own risk". Última imagem `neo4jlabs/neodash:2.4.11`, de 29/09/2025 |
| **Neo4j Desktop 2.3** | Desenvolvedor | Banco do próprio Desktop (licença Developer, Enterprise) | Conecta | O Bloom do Desktop não pode ser usado com banco remoto sem contrato |

Fontes na seção 7. A linha do Browser vem do próprio pacote servido em `:7474`, lido por nós. O código registra `id: query@neo4j-browser-2026.10.21`, e o manifesto liga só a ferramenta `query`.

### 1.2 O que uma pessoa sem Cypher usa de fato (julgamento)

- **Para ver ligações** ("o que está ligado a este pedido?"): o Bloom/Explore, que foi feito para isso (busca por texto, expandir com clique, legenda e cor por categoria). Sem ele, o Browser com um guia que entregue as consultas prontas.
- **Para obter respostas** ("qual vendedor tem a pior nota?"): uma tabela vinda de uma consulta que alguém escreveu e conferiu. Pode ser uma consulta salva, um painel ou um LLM que mostre o Cypher que usou. Nenhuma visualização de grafo responde a uma pergunta agregada.
- **O Browser sozinho não serve para quem não sabe Cypher.** A tela inicial é um editor e a barra lateral mistura labels de dado e de meta. As visões prontas (clicar num label ou num tipo) mostram amostras soltas.

### 1.3 O console da Aura ligado ao banco local

A própria tela inicial do Browser 2026.10 oferece o caminho: "Do more with Community Edition. Connect in Aura for free access to: Rich graph exploration and dashboards, Cloud storage for your queries, Data import tooling, AI copilots". O blog da Neo4j de 26/03/2026 diz o mesmo: um Community "deployed anywhere" pode ser ligado ao console "for free" e ganha o Bloom (Explore). Um funcionário da Neo4j confirmou em 16/04/2026 que o Explore não está disponível para o Community, "however there is an exception": registrar a instância no console.

O que Mateus observou em 12/11/2026 no console (`console.neo4j.io`):

- **Conexão rápida sem TLS funciona.** Em Studio → Bloom, a conexão com `neo4j://127.0.0.1:27687` abriu. A perspectiva padrão e as legendas (`name`) apareceram.
- **"Add deployment" exige TLS.** Salvar a instância como implantação (Unmonitored) só aceita endereço cifrado: "Use https, neo4j+s or bolt+s". O banco local, sem TLS, não pode ser salvo assim.
- **Menu do console:** Studio (Import, Query, Bloom, Dashboards, Document Intelligence) e Data services (Instances, Graph Analytics, GraphQL Data APIs, Agents).
- **Busca em linguagem natural no Bloom não responde perguntas.** "Tem cliente de quantas cidades diferentes?" trouxe 1.000 nós `Cliente` (limite atingido), sem número. O Bloom traduz a frase numa busca de padrão de grafo, não numa agregação.

Por que a conexão sem TLS funciona **(julgamento, não medido)**: o console roda no navegador e abre o WebSocket do Bolt direto do navegador para `127.0.0.1`. Os navegadores tratam `localhost` e `127.0.0.1` como origem confiável e deixam uma página `https` falar com eles sem TLS. Com um servidor remoto sem TLS, a mesma conexão seria bloqueada como conteúdo misto. Pela mesma razão, os resultados das consultas devem ir do banco direto para o navegador, sem passar pelos servidores da Aura, porque eles não alcançam o `127.0.0.1` da máquina. Não verificamos isso no tráfego.

**Para salvar a instância local no console (TLS):** seria preciso ligar TLS no Bolt (`dbms.ssl.policy.bolt.enabled=true`, `server.bolt.tls_level=REQUIRED`, chave e certificado em `certificates/bolt/`) com um certificado em que o navegador confie. Um certificado autoassinado não basta, porque o navegador recusa o WebSocket sem aviso. Seria preciso uma CA local instalada no sistema (por exemplo, `mkcert`) ou um certificado de domínio real. Não testado. Para o uso local, a conexão rápida basta.

### 1.4 O que fica na nuvem da Aura (cuidado com dado de cliente)

O que se sabe:

- **Contas e organização:** o console exige conta Neo4j. A conexão rápida pede URL, usuário e senha do banco; não verificamos se a senha fica guardada no console.
- **Consultas salvas:** a tela do Browser anuncia "Cloud storage for your queries" para quem liga o banco ao console. O texto das consultas (que pode conter valores de cliente, como um `order_id`) fica na nuvem.
- **Assistente de IA (Query e Bloom copilot):** precisa ser ligado nas configurações da organização. Para criar painéis com IA, a documentação diz que a IA analisa só o esquema (labels e tipos), "It cannot read the actual data". Não achamos texto equivalente para o assistente do Query. Uma página da Aura diz que, para usar o assistente com uma instância do Desktop, é preciso o APOC; o nosso banco não tem APOC. Os termos de recursos da Aura dizem que o Aura Agent usa modelos de terceiros.
- **Perspectivas do Bloom e painéis:** no Bloom com plugin, a perspectiva fica no banco. No console, não achamos documento que diga onde ficam as perspectivas de uma instância ligada **(não verificado)**. Painéis podem ser guardados como JSON no próprio banco; o import do Dashboards lê "a JSON stored in your database".
- **O próprio Browser local envia telemetria:** o pacote tem chave do Segment e DSN do Sentry, e o banco responde `client.allow_telemetry = true` em `dbms.clientConfig()`. Para dado sensível, vale pôr `client.allow_telemetry=false` na configuração do servidor **(não testado)**.

Para dados reais de cliente, isso pede uma conversa com o cliente antes de usar o console **(julgamento)**.

## 2. O que o Browser permite (testado)

Tudo abaixo rodou no Browser servido pelo `akme-neo4j-t6`, em Chromium sem tela (Playwright 1.58.2), com capturas em `.../tmp/vis/shots/` (seção 6). O comportamento foi lido também no código do pacote (`/browser/assets/*.js`).

| Recurso | Resultado | Como |
|---|---|---|
| **Guia próprio** (`:guide URL` ou `:play URL`) | **Funciona.** Abre num painel à esquerda, com páginas, acentos corretos e botões "Execute in Query tab" e "Edit in Cypher editor" em cada bloco | HTML no formato antigo: `<article><carousel><slide>`; bloco rodável é `<pre mode="cypher">` ou `class="runnable"`; link interno com `play-topic`. Também aceita `.adoc`. Remove `script`, `iframe`, `svg`, `form` |
| **Onde o guia pode estar** | URL completa é buscada direto do navegador, sem a lista de hosts permitidos (que só vale para nomes curtos). O servidor do guia precisa mandar `Access-Control-Allow-Origin` | Testado com servidor local com CORS |
| **`browser.post_connect_cmd`** | **Funciona.** Com `guide http://127.0.0.1:8899/olist.html`, o guia abre sozinho a cada conexão | O Browser põe `:` na frente de cada comando; só aceita comandos de cliente, não Cypher |
| **`browser.remote_content_hostname_allowlist`** | **Não existe no 2026.10.1.** O servidor recusou subir: "Unrecognized setting. No declared setting with name: browser.remote_content_hostname_allowlist" (validação estrita). O Browser lê `browser.remote_content_hostname_whitelist` (padrão `guides.neo4j.com,localhost`) | Não é necessário para URL completa |
| **Consultas salvas** | **Funciona.** Painel "Queries" → Upload aceita `.csv` ou `.zip`. CSV com colunas `name,description,query,id,parentId,isFolder,isProtected`; pasta e 13 consultas importadas ("Cypher import completed!") | Ficam no `localStorage` do navegador (`persist:nx.v1.query.savedCypher`), uma vez por máquina |
| **Estilo GraSS** (`:style`) | **Funciona por arquivo.** O quadro `:style` tem "Upload GraSS styles" (`.grass`, `.style`, `.txt`), pede confirmação e converte `diameter` em `size`. Não carrega de URL | Fica no `localStorage` (`nx.v1.nx.graphStyling`). Também há um seletor por label: clicar no chip do label no resultado abre cor, tamanho e legenda |
| **Legenda padrão** | Ordem de escolha: propriedade `name`, depois `title`, depois `label`, depois qualquer uma que termine em `name`, depois em `description`, e por fim a primeira em ordem alfabética. Por isso `_carga` aparecia. `nome` não conta | Lido no código (`bv=[/^name$/i,/^title$/i,/^label$/i,/name$/i,/description$/i,/^.+/]`) e conferido na tela |
| **Legenda some de longe** | Com muitos nós na tela, o texto só aparece ao aproximar (zoom) | Captura 12 contra 14 |
| **"Automatically connect result nodes"** | **Vem desligado** (`autoConnectResultNodes: false`). Por isso clicar no label `Conceito` mostra 18 nós soltos. Ligado em Settings, o mesmo clique mostra as 21 setas | Capturas 32 e 34. A escolha fica no `localStorage` |
| **Clique no chip de label / tipo** | Roda `MATCH (n:Label) RETURN n LIMIT 25` e `MATCH p=()-[:TIPO]->() RETURN p LIMIT 25` | Lido no código. São amostras, não visões |
| **Mapa do esquema por clique** | **Não há.** Nenhum botão roda `db.schema.visualization`. Só pelo guia ou por consulta salva | Lido no código e na tela |
| **Limites de desenho** | `maxVizNodes` 1.000 e `recordLimit` 5.000 por padrão | Lido no código |
| **Barra lateral** | Mostra todos os labels, tipos e chaves de propriedade do banco, inclusive os de meta e chaves antigas que nenhum nó usa mais (`_handleVocabUris`, `cnpj`, `ds_produto`...) | As chaves vêm de `db.propertyKeys()`, e o Neo4j nunca apaga um nome de propriedade. Só um banco novo as remove |

## 3. Convenções de modelagem que afetam a visão

### 3.1 Nomes: ontologia ou convenção do Neo4j

O Cypher Manual (versão 25) recomenda label em PascalCase, tipo de relação em `SCREAMING_SNAKE_CASE` e propriedade em camelCase. Lembra que nomes são sensíveis a maiúsculas. É recomendação, não regra do banco. Em 05/11/2026 o akme aprovou a decisão D3, "UPPER_SNAKE com mapa, sem misturar" (`reports/Exportar ontologia para Neo4j.md`, linha 341). O exportador atual grava o nome da ontologia (`contemItem`), e a D3 ficou sem efeito.

- **Pessoa de negócio:** `CONTEM_ITEM` e `contemItem` se leem igual. A legenda da seta é o tipo nos dois casos **(julgamento)**.
- **LLM (text2cypher):** não achamos estudo que compare a grafia do tipo de relação. A Neo4j lista erro de nome entre os cinco grupos de erro mais comuns dos modelos de text2cypher, sem separar por grafia. A favor da convenção: é a forma dos exemplos da documentação e dos tutoriais, de onde os modelos aprenderam Cypher **(julgamento, sem medição)**. O teste que decide é o já previsto: as CQs num LLM, com e sem a mudança.
- **O argumento que decide aqui não é estilo, é o mapa nativo** (seção 4). Os tipos da camada `Conceito` e os tipos dos dados precisam ser diferentes. Com a D3, isso sai de graça: dados em `CONTEM_ITEM`, setas da ontologia com o nome da ontologia (`contemItem`) e a propriedade `tipo_no_grafo: 'CONTEM_ITEM'` como mapa.
- **Custo:** recarregar o grafo; ajustar o esquema escrito para o LLM, as CQs em Cypher (`cq/*.cypher`), o verificador da demo e os testes. A troca das 568.943 arestas do Olist, feita no protótipo por Cypher, levou cerca de 14 s.

### 3.2 Legenda: `name`

`name` é o primeiro nome que o Browser procura (seção 2) e é a convenção dos exemplos da Neo4j. O akme deve gravar `name` em todo nó.

- **Dado:** um texto legível decidido na etapa 5, por fonte. No protótipo: "Pedido &lt;status&gt; &lt;data da compra&gt;", "Cliente de &lt;cidade&gt;/&lt;UF&gt;", "Nota 5". Sem decisão, o padrão é "&lt;rótulo da classe&gt; &lt;início do _id&gt;".
- **`Conceito` e `Termo`:** o próprio nome.
- **A marca do projeto:** "Projeto &lt;nome&gt;". Sem isso, a legenda dela é o esquema inteiro.
- **Colisão:** se a fonte já tiver coluna `name`, o akme não sobrescreve. O plano avisa e usa a coluna. Gravar `nome` não resolve, porque nenhuma ferramenta o procura.

### 3.3 A camada de meta no mesmo banco

O Community tem um só banco de usuário (`neo4j`, além do `system`), então `Conceito`, `Termo` e `_AkmeProjeto` ficam junto dos dados. É o que o n10s também faz. Não há como esconder labels da barra lateral do Browser. O que o protótipo faz:

- **Tipos distintos:** o mapa dos dados sai correto (seção 4).
- **Consultas e guia filtram a meta:** `WHERE NOT m:Conceito`, e o mapa remove `Conceito`, `Termo` e `_AkmeProjeto`.
- **Meta em cinza no GraSS.**
- **No Bloom:** uma perspectiva que só tenha as categorias de dado esconderia a meta **(não testado)**.

Pôr a meta em outro banco exigiria Enterprise ou outra instância, e o LLM perderia a consulta única ao esquema **(julgamento)**.

## 4. O mapa nativo do esquema

`CALL db.schema.visualization()` devolve um nó virtual por label e uma seta por tipo de relação. A descrição do próprio procedimento avisa: "this may include additional relationships that do not exist in the data due to the information available in the count store". O banco sabe, por tipo, quais labels saem e quais chegam, mas não sabe os pares. Ele combina todos.

Medido no `akme-neo4j-t6`:

| | Setas desenhadas para os 6 tipos de dado | Corretas | Erradas |
|---|---:|---:|---:|
| Antes (mesmo nome em `Conceito` e nos dados) | 24 | 6 | 18 (ex.: `Pedido -contemItem-> Conceito`) |
| Depois (dados em `UPPER_SNAKE`, ontologia com o nome da ontologia) | 6 | 6 | 0 |

Depois da troca, o mapa é exatamente `Pedido -CONTEM_ITEM-> ItemPedido`, `Pedido -FEITO_POR_CLIENTE-> Cliente` e assim por diante. É o "entidades como nós, relações como setas" que o João pediu, sem custo de armazenamento. A camada `Conceito` aparece à parte, com setas de `Conceito` para `Conceito`.

Limites:

- **Vale enquanto cada tipo de dado liga um único par de labels.** Isso hoje é verdade: um contrato por relação, um label por nó. Se o akme passar a pôr dois labels num nó (por exemplo, `Avaliacao` e `AvaliacaoNegativa`), as combinações erradas voltam.
- **Sem botão no Browser.** O caminho sem digitar é o guia do akme (página "O mapa") ou a consulta salva "1. Mapa das classes". Ambos rodam com um clique e já tiram a meta.
- **Mostra estrutura, não significado.** A definição de cada classe está no `Conceito` (página 2 do guia) e na página de cada classe.

## 5. Recomendação

### 5.1 Dois usos, duas respostas

| Uso | Pergunta típica | Onde a pessoa encontra |
|---|---|---|
| **Responder** | "Quantas cidades têm clientes?", "pior vendedor por nota" | Tabela: consulta salva ou guia (CQs prontas); painel (Dashboards); LLM pelo MCP, que devolve texto e o Cypher usado; assistente do Query no console. Nunca o Bloom |
| **Explorar ligações** | "O que está ligado a este pedido?", "como as classes se ligam?" | Guia do Browser (mapa, ontologia, exemplo por classe); Bloom pelo console |

Um exemplo de por que o "responder" precisa de quem confira: "quantas cidades distintas têm clientes?" tem duas respostas certas no Olist, conforme se conte o nome da cidade (`count(DISTINCT c.customer_city)`) ou o par cidade e UF, porque há nomes repetidos entre estados. Um assistente pode devolver qualquer uma sem avisar. A CQ aprovada e o glossário são o que fixa a leitura **(julgamento)**. Não testamos o assistente do Query: ele exige a conta de Mateus.

### 5.2 Ranking: Community local

1. **Browser com o kit do akme (recomendado; testado; grátis; sem nuvem).**
    - `name` em cada nó.
    - Arestas de dado em `UPPER_SNAKE` (D3), setas da ontologia com o nome da ontologia e `tipo_no_grafo`.
    - Guia do projeto aberto por `browser.post_connect_cmd`.
    - Consultas salvas em CSV.
    - Estilo GraSS.
    - Pedir no guia para ligar "Automatically connect result nodes".
2. **Console da Aura ligado ao banco local (complemento opcional; parcialmente testado por Mateus; grátis).**
    - Ganha: Bloom com legendas, Query com assistente, Dashboards (importando o JSON do akme).
    - Exige: conta Neo4j; leitura dos cuidados de dados (1.4); para salvar a instância, TLS confiável; para o assistente, ligar IA na organização e possivelmente o APOC.
3. **Não recomendados:**
    - **Bloom no Desktop:** a licença não cobre banco remoto nem Community.
    - **Plugin do Bloom no servidor:** exige chave de licença.
    - **NeoDash Labs:** sem manutenção.

### 5.3 Ranking: Aura

1. Bloom e Dashboards nativos.
    - Painel importado do JSON do akme, ou guardado no banco.
    - Perspectiva: só quando houver um modelo exportado (5.4).
2. Query do console com as consultas salvas.
    - **Não testado:** se o Query do console aceita `:guide` de URL externa (no Browser local a função existe e está ligada).
    - Se aceitar, o guia precisa estar num endereço `https` com CORS.

### 5.4 O que o akme deve gerar (por projeto, determinístico)

Tudo a partir da ontologia, do `content.yml`, do plano e das CQs, sem nada fixo do Olist. O protótipo (`gerar.py`) lê do banco o que o akme gravou e prova que dá: nada nele cita uma classe do Olist.

| Artefato | Onde | Testado |
|---|---|---|
| `name` em cada nó (dado, `Conceito`, `Termo`, marca), com a regra de colisão | Carga (`neo4j_load.py`); `legenda` por fonte no `add_source` | Sim (protótipo em Cypher) |
| Tipos de dado em `UPPER_SNAKE` e `tipo_no_grafo` nas setas de `Conceito` | `neo4j_plan.py`, `neo4j_onto.py`, `neo4j_schema.py`, CQs | Sim (troca no banco; 3 CQs traduzidas rodaram) |
| Guia HTML: capa com contagens, mapa, ontologia, uma página por classe (definição, ligações, colunas, exemplo), glossário, CQs, ajustes | `docs/publish/neo4j/<projeto>.html` | Sim |
| Consultas salvas (CSV do Browser) | `docs/publish/neo4j/<projeto>-consultas.csv` | Sim |
| Estilo (`.grass`): cor por classe, meta em cinza, legenda `{name}` | `docs/publish/neo4j/<projeto>.grass` | Sim (importado) |
| Painel no formato NeoDash 2.4 (mapa, contagens, glossário, uma tabela por CQ) | `docs/publish/neo4j/<projeto>-painel.json` | Só gerado; import no Aura não testado |
| Perspectiva do Bloom (categoria por classe com legenda `name`; frases de busca vindas das CQs que devolvem grafo) | Futuro | Não. O formato de exportação não é documentado. Caminho seguro: Mateus exporta uma perspectiva do console, que vira o modelo, e o akme preenche |
| Modelo no formato `graph-schema-json` da Neo4j (para a visão de modelo do Import) | Futuro | Não |

**O que o guia do akme (README) deve dizer:**

- **Docker:** como pôr `--env NEO4J_browser_post__connect__cmd='guide <URL do guia>'` e servir o guia com CORS. Nunca usar `remote_content_hostname_allowlist`: o 2026.10 recusa subir com ela.
- **No Browser:** ligar "Automatically connect result nodes"; importar o CSV em Queries → Upload; importar o `.grass` em `:style` → Upload.
- **Responder ou explorar:** usar a tabela para perguntas e o grafo para ligações.
- **Console da Aura:** o caminho opcional, com os cuidados de dados.
- **Para o LLM:** a troca de nomes muda o esquema que ele lê, que precisa sair junto.

## 6. Protótipo

Em 12/11/2026 montamos à mão, num banco descartável com o Olist, um protótipo do que esta pesquisa recomenda: guia do projeto aberto ao conectar (`browser.post_connect_cmd`), setas de dado em UPPER_SNAKE, legenda `name` e consultas salvas. O protótipo e os arquivos dele eram temporários e não ficam no repositório.

O que virou código está na [Task 11](task-11-tutorial.md), com duas mudanças decididas depois de ver o protótipo: as setas de dado mantêm o nome exato do TTL (a camada de ontologia passou a usar `RELACAO_ONTOLOGIA`, o que também resolve o mapa nativo), e o guia ficou com seis slides de navegação, sem as perguntas de competência.

## 7. Fontes

Consultadas em 12/11/2026.

**Neo4j, produto e documentação**

- Pacote do Browser servido pelo Neo4j 2026.10.1 Community (`http://127.0.0.1:27474/browser/assets/*.js`), lido por nós: `query@neo4j-browser-2026.10.21`; formato do guia, `post_connect_cmd`, legenda padrão, `autoConnectResultNodes`, CSV das consultas salvas, upload de GraSS.
- [Cypher Manual 25, Naming rules and recommendations](https://neo4j.com/docs/cypher-manual/current/syntax/naming/)
- [Blog da Neo4j, Community Edition advances (26/03/2026)](https://neo4j.com/blog/graph-database/community-edition/)
- [Aura feedback, Explore e Community (resposta de 16/04/2026)](https://aura.feedback.neo4j.com/desktop-v2/p/my-understanding-is-that-explore-is-available-for-all-the-version-i-have-communi)
- [Aura, Add a deployment (Fleet Manager)](https://neo4j.com/docs/aura/fleet-management/setup/) e [Self-managed instances](https://www.neo4j.com/docs/aura/managing-instances/self-managed/)
- [Aura, Dashboards: import and export](https://neo4j.com/docs/aura/dashboards/import/) e [Creating a dashboard with AI](https://neo4j.com/docs/aura/dashboards/ai-dashboards)
- [Aura, Explore: perspectives](https://neo4j.com/docs/aura/explore/explore-perspectives/perspectives/)
- [Bloom, deployment modes](https://neo4j.com/docs/bloom-user-guide/current/bloom-installation/bloom-deployment-modes/)
- [Neo4j Desktop 2.3, documentação](https://neo4j.com/docs/desktop/current/) e [Dashboards no Desktop](https://neo4j.com/docs/desktop/current/dashboards/)
- [Neo4j Desktop License](https://neo4j.com/legal-terms/desktop-license/) ("Customer may not use Neo4j Bloom with remote database(s)")
- [Aura Feature-Specific Terms](https://neo4j.com/legal-terms/aura-feature-specific-terms/) e [Visual tour of the console](https://neo4j.com/docs/aura/visual-tour/)
- [Fórum: Neo4j Desktop 2, "Neo4j Bloom requires Neo4j Enterprise Edition"](https://community.neo4j.com/t/neo4j-desktop-2-neo4j-bloom-requires-neo4j-enterprise-edition/75163)
- [NeoDash, README](https://github.com/neo4j-labs/neodash) e [Docker Hub `neo4jlabs/neodash`](https://hub.docker.com/r/neo4jlabs/neodash) (tag 2.4.11, 29/09/2025)
- [Text2Cypher: model struggles (Neo4j)](https://neo4j.com/blog/developer/text2cypher-model-struggles-dataset-improvements/)
- [Formato graph-schema-json](https://github.com/neo4j/graph-schema-json-js-utils) (não testado)

**Repositório**

- `reports/Exportar ontologia para Neo4j.md` (D3, linhas 85 e 341); `research_notes/Exportar ontologia para Neo4j/modelagem_idempotencia.md`
- `akme/tools/neo4j_load.py`, `neo4j_onto.py`, `neo4j_plan.py`; [Task 10](task-10-semantica.md); [Pesquisa: camada semântica](pesquisa-camada-semantica.md); [Uso real do grafo](uso-do-grafo.md)

**Observação de uso:** Mateus no console da Aura, 12/11/2026 (seção 1.3).

## 8. Limites

- **Console da Aura não testado por nós:** o que está na seção 1.3 é a observação de Mateus. Não testamos o assistente do Query, o import de painel nem a perspectiva. O que fica na nuvem (1.4) vem de documentação incompleta.
- **Sem medição com LLM:** a troca para `UPPER_SNAKE` é defendida pelo mapa nativo e pela D3, não por um ganho medido em text2cypher.
- **Sem pessoas reais:** "entende sem Cypher" é julgamento nosso; não houve teste com usuário de negócio.
- **Legendas do protótipo escolhidas à mão:** as do Olist mostram o que a etapa 5 decidiria. A regra automática do akme ainda não existe.
- **Guia local:** servido em `127.0.0.1:8899`, só funciona nesta máquina. Para um time, o guia precisa de um endereço com CORS acessível a todos.
- **Estado por navegador:** consultas salvas, estilo e o ajuste de ligar resultados ficam no `localStorage`. Cada pessoa e cada navegador repetem os passos 7 a 9.
- **Chaves antigas na barra lateral:** só somem com um banco novo.
- **Indisponibilidade causada por esta pesquisa:** o `t6` ficou fora do ar por cerca de 3 minutos, por causa da configuração `allowlist` recusada.
