# Histórico da exportação para o Neo4j

Registro cronológico, com as saídas completas de cada prova. Trechos antigos podem estar superados: o estado atual está em [exportacao.md](exportacao.md).

## 12/11/2026: tutorial do projeto no Neo4j Browser (Task 11)

Esta entrada é a mais recente. As seções depois dela são registros antigos, mantidos como estavam.

**O que mudou:** todo `publish --target neo4j`, dry-run ou carga, gera `docs/publish/neo4j_guia.html`, um guia do Neo4j Browser sobre o projeto, com seis páginas só de navegação: o que tem aqui (classes com contagem), a ontologia (mapa com os nomes do TTL; setas virtuais com APOC), os dados (`db.schema.visualization` sem a camada de ontologia), explorar (um registro de cada classe e o que está ligado a ele), como navegar e perguntas em português pelo console da Aura, e `docs/publish/neo4j_consultas.csv`, as mesmas consultas para importar no Browser. O `akme review` serve o guia em `/neo4j/guia`, com CORS só para as origens do Neo4j Browser; no Browser, `:guide http://127.0.0.1:8765/neo4j/guia`. As arestas de dado mantêm o nome exato do TTL. A camada `Conceito` virou espelho do `schema.ttl`: toda relação, inversas incluídas, como seta `RELACAO_ONTOLOGIA` com o nome em `nome`. Todo nó ganhou a legenda `name`.

**Decisão de Mateus (12/11, cerca de 18:35):** a primeira versão da Task 11 gravava as arestas de dado em UPPER_SNAKE (`PERTENCE_A`). Depois de ver o mapa, Mateus pediu o nome exato do TTL nos dados e um tipo único entre os `Conceito`. Os tipos continuam diferentes, então o mapa nativo continua sem setas falsas.

**Por quê:** a crítica do João (o Browser mostra bolinhas soltas e exige Cypher) e a [pesquisa de visualização](../exportacao-neo4j/pesquisa-visualizacao.md): sem `name`, a legenda era `_carga`; com o mesmo tipo em `Conceito` e nos dados, o mapa nativo desenhava 18 setas falsas no Olist. Pedido de Mateus: "sempre que alguém rode, gere esse tutorial, sobre o projeto que for, mas cubra todas as perguntas de competência".

**Atenção na primeira carga depois da mudança:** quem carregou com a versão UPPER_SNAKE tem arestas `PERTENCE_A` no banco. A carga grava as de nome do TTL e a sincronização apaga as antigas. A prévia mostra, por tipo de aresta, banco, origem e "pelo menos N serão removidas", e avisa que o tipo antigo não é mais gravado. Consultas escritas com o nome antigo param de achar arestas.

**Onde está o detalhe:** [task-11-tutorial.md](../exportacao-neo4j/task-11-tutorial.md).

## 12/11/2026: camada semântica legível no grafo (Task 10)

Registro mantido como foi escrito.

**O que mudou:** cada nó e aresta de dado ganhou `_descricao` (a definição da classe ou da relação, ou o rótulo da relação enquanto ela não tiver definição). A carga passou a gravar um esquema descritivo para o LLM em `docs/publish/neo4j_schema.md` e na propriedade `esquema` da marca `_AkmeProjeto`. Os termos do `content.yml` entraram como nós `Termo`, ligados por `TEM_TERMO`. A regra "não somar após juntar com" passou a citar labels. Antes do "confirmar?", a CLI mostra quantos nós a sincronização vai apagar, pelo menos.

**Por quê:** a pesquisa de 12/11/2026 ([pesquisa-camada-semantica.md](../exportacao-neo4j/pesquisa-camada-semantica.md)) mostrou que as ferramentas de LLM não leem descrição nenhuma do grafo e que quem clica num nó no Browser não vê a definição. Decisão de Mateus: descrição em cada nó, para navegação, e o esquema gravado também no banco.

**Correção do registro da entrada abaixo:** dos quatro motivos da troca do n10s, a pesquisa confirmou o do Aura. O teto de 100 mil linhas era do nosso código (`MAX_ROWS` no `n10s.py`), não do n10s. Relação virar nó era um problema do `onto.import`, que tinha meio-termo (n10s só para os dados). O pedido do colega não exigia sair do n10s. O que a troca perdeu de fato foi o único gerador de RDF fiel.

**Onde está o detalhe:** [task-10-semantica.md](../exportacao-neo4j/task-10-semantica.md).

## 11/11/2026 a 12/11/2026: de volta ao Cypher, sem n10s

Registro mantido como foi escrito. Veja a correção dos motivos na entrada acima.

**O que mudou:** o exportador com RDF e o plugin n10s (`akme/tools/n10s.py`, de 05/11/2026) foi apagado. A exportação passou a gravar dados e ontologia em Cypher puro, pelo driver, sem plugin (`akme/tools/neo4j_values.py`, `neo4j_plan.py`, `neo4j_onto.py` e `neo4j_load.py`). O artefato do dry-run passou de `docs/publish/neo4j.nt` para `docs/publish/neo4j.cypher`. A ontologia entra como nós `Conceito`, com as relações como setas, e cada carga sincroniza o banco com a origem.

**Por quê:**

- **Relações viravam nós.** O `n10s.onto.import` grava cada relação como um nó `Relationship`, ligado às classes por `DOMAIN` e `RANGE`. Quem abria o grafo via relações como entidades.
- **Teto de 100 mil linhas.** O exportador lia cada tabela inteira em memória e recusava tabelas maiores. O `olist_order_items_dataset`, com 112.650 linhas, não carregava.
- **O n10s não existe no Aura.** Depender do plugin limitava onde o grafo pode rodar.
- **Pedido do colega:** ver no Neo4j Browser a camada semântica do jeito que se lê, com conceitos como nós e relações como setas.

**Decisão:** de Mateus, em 11/11/2026, depois de ver o teste descartável com a demo e o Olist em Cypher ("pode ser"). Bancos carregados pelo n10s são reconhecidos e recusados, sem migração; o guia traz o comando de limpeza.

**Onde está o detalhe:**

- Motivo e plano: [visão geral nas páginas MkDocs](../exportacao-neo4j/index.md) (`uv run --extra docs mkdocs serve`)
- O que mudou em cada uma das 9 tarefas, com testes e revisão: as páginas `task-N` em [docs/exportacao-neo4j/](../exportacao-neo4j/index.md), por exemplo [task-6-carga.md](../exportacao-neo4j/task-6-carga.md) e [task-7-troca.md](../exportacao-neo4j/task-7-troca.md)
- Estado atual: [exportacao.md](exportacao.md); guia de uso: [reports/docs_exp_neo4j/README.md](../../reports/docs_exp_neo4j/README.md)

**Atenção:** tudo o que vem abaixo vale para o exportador anterior, que gerava Cypher (`akme/tools/cypher.py`). Em 05/11/2026 ele foi substituído pelo caminho com n10s.

Registro de como o grafo da demo chega ao Neo4j: o que foi feito, por que escolhemos cada caminho, de onde veio a informação e qual é a prova de que funcionou.

**Meta atual:** ter o grafo da demo (`examples/local_demo`) funcionando no Neo4j. Melhorias ficam para depois.

Cada afirmação usa um destes rótulos:

- **Provado:** observado neste ambiente, com a saída registrada aqui.
- **Fonte:** lido na referência citada.
- **Pesquisa:** vem do relatório `reports/Exportar ontologia para Neo4j.md`, sem nova conferência nesta etapa.
- **Decisão:** escolha nossa, com o motivo ao lado.

## Andamento

| # | Task | Estado |
|---|---|---|
| 1 | Subir o Neo4j em Docker, acessível só nesta máquina | Concluída em 05/11/2026 |
| 2 | Instalar o driver e configurar a conexão | Concluída em 05/11/2026 |
| 3 | Gerar o script em dry-run e ler o resultado | Concluída em 05/11/2026 |
| 4 | Carregar a demo no Neo4j | Concluída em 05/11/2026 |
| 5 | Comparar o banco com o gabarito | Concluída em 05/11/2026 |
| 6 | Ver o grafo no Browser e rodar duas consultas | Concluída em 05/11/2026: o usuário viu o grafo no Browser; as consultas de negócio são a prova V8 e V9. Observação do usuário: o grafo completo, a olho nu, não é fácil de entender. Registrar no guia que os insights vêm de perguntas específicas, e não de olhar o grafo inteiro |
| 7 | Rodar a carga uma segunda vez | Concluída em 05/11/2026 |

**Meta alcançada em 05/11/2026 para a demo em CSV:** o grafo está no Neo4j, conferido contra a origem, e repetir a carga com os mesmos dados não o altera. A funcionalidade ainda não está pronta para os demais casos (ver "O que podemos garantir").

## Como isto vira um caminho guiado no template

As tasks abaixo são manuais porque estamos aprendendo e provando cada passo. Quem usar o template não deve repeti-las: elas servem de base para automatizar o processo e escrever o guia final. **Esta seção é um plano; nada dela foi implementado.**

| Task de hoje | Quem usa o template, no futuro | Estado |
|---|---|---|
| 1. Subir o Neo4j | Um comando sobe a versão fixada e gera a senha no `.env`. Quem já tem Neo4j ou Aura só informa a conexão | A fazer |
| 2. Driver e conexão | `uv sync --extra neo4j`, uma única vez; o projeto carrega o `.env` e testa a conexão sozinho | Extra pronto; carregar o `.env` e testar a conexão, a fazer |
| 3. Dry-run | `akme publish --target neo4j` | Existe no rascunho |
| 4. Carga | `akme publish --target neo4j --no-dry-run`, com confirmação | Existe no rascunho, ainda sem carga real |
| 5 e 7. Conferência | O próprio `publish` confere o banco depois da carga e informa o resultado | A fazer |
| 6. Ver o grafo | O final do comando mostra a URL do Browser e o que conferir | A fazer |

O agente conduz esse caminho pela skill (`SKILL.md`, etapa 5, e `akme stage`), explicando cada passo e pedindo aprovação antes da carga. O guia final deve entrar em `docs/guia-do-fluxo.md`.

Ao concluir cada task, registre aqui: o que o usuário final ainda precisa fazer, o que o template pode fazer por ele e quais erros ele pode encontrar, como o de senha no Browser.

## O que podemos garantir

Nenhum teste garante que a exportação funciona para todos os dados possíveis. A garantia proposta tem três camadas; **nenhuma está pronta**:

1. **Contrato:** o template declara o que suporta e recusa o resto com uma mensagem clara, em vez de exportar errado.
2. **Conferência em cada carga:** o banco é comparado com a origem. Essa é a prova de que aquela carga, com aqueles dados, deu certo.
3. **Casos de teste:** um conjunto de dados feito para cobrir os casos difíceis, mais o domínio de seguros em `examples/teste_acme` e, quando houver, dados reais.

Comportamento atual do rascunho nos casos difíceis:

| Caso | Hoje | Base | Deveria |
|---|---|---|---|
| Chave duplicada | Recusa | Teste automatizado | Manter |
| Chave nula | Recusa a carga (A3) | Teste automatizado | Manter |
| Tabela sem chave no lado "one" | Recusa até declarar a chave (A4) | Teste automatizado | Manter |
| Chave composta | Declarada em `neo4j.keys` (A4) | Teste automatizado e carga real | Manter |
| Fonte sem classe associada | Recusa a carga, salvo exclusão explícita (A3) | Teste automatizado | Manter |
| Fonte com mais de uma classe | Recusa a carga (A3) | Teste automatizado | Manter |
| Duas fontes com a mesma classe | Recusa a carga (A3) | Teste automatizado | Manter |
| Relação sem join | Não publica e informa o nome | Leitura do código | Informar também o motivo |
| Mais de 100 mil linhas | Recusa a carga (A3), sem opção de aprovar | Teste automatizado | Permitir carregar tudo em volumes maiores |
| Linha apagada na origem | Continua no grafo | Leitura do código | Sincronizar com travas |
| Tipos mistos numa coluna | Tipo declarado por coluna; valor inválido recusa a carga (A4) | Teste automatizado e carga real | Manter |

Nada desta tabela foi executado em um Neo4j. As correções ficam para depois da primeira carga real.

## Independência do formato de entrada

O exportador não lê CSV: ele pede as linhas ao adapter (`read_sample`) e usa a ontologia, os contratos e o profile. Os CSVs só aparecem porque são os dados da demo.

| Entrada | Situação em 05/11/2026 | Base |
|---|---|---|
| CSV (pasta local) | Carregado no Neo4j e conferido | Tasks 4 e 5 |
| Excel `.xlsx` | Só dry-run, em cópia temporária: mesmas contagens, sem omissões, e as linhas de pedido e cliente inspecionadas iguais às do CSV; não carregado no Neo4j | Provado (X1) |
| Postgres, Snowflake, Databricks | Adapter existe; nunca testado com o exportador | Leitura do código |
| PDF, Word, PowerPoint, Markdown, texto | São lidos como documentos, mas não viram nós | Leitura do código |
| JSON, API e outros formatos | Sem adapter | Leitura do código |

**X1:** a demo convertida para `.xlsx`, com números e datas tipados, gerou 11 instruções, nós 8/17/10/8 e arestas 17/10/17 (`contem`, `pertenceA`, `referencia`).

Plano para qualquer entrada, **ainda não implementado**:

```
adapter → linhas normalizadas → ontologia e contratos → plano → carga → conferência
```

- **Adapter novo:** um formato novo só precisa implementar o contrato do adapter (ver `README.md`), sem mexer no exportador.
- **Leitura completa:** `read_sample` é para amostras, e o Postgres o implementa com `SELECT * ... LIMIT n`, sem `ORDER BY`. A exportação precisa de um método próprio, com leitura completa e ordem definida.
- **Tipos declarados:** cada fonte entrega tipos diferentes, então o tipo final deve vir do plano, não do formato de entrada.
- **Conferência por adapter:** o gabarito da demo lê CSV e só serve para a demo. A conferência geral precisa funcionar para qualquer fonte, e seu grau de independência quando a leitura passa pelo mesmo adapter ainda está em aberto.

## Task 1: Neo4j local em Docker

### O que foi feito

Subimos o contêiner `akme-neo4j` com a imagem `neo4j:2026.10.1`, com as portas publicadas só em `127.0.0.1` e os dados no volume `akme-neo4j-data`. O banco está vazio.

```bash
NEO4J_AUTH="neo4j/<senha>" docker run -d --name akme-neo4j \
  --publish=127.0.0.1:7474:7474 --publish=127.0.0.1:7687:7687 \
  --env NEO4J_AUTH --volume=akme-neo4j-data:/data neo4j:2026.10.1
```

- **Browser:** http://localhost:7474, usuário `neo4j`, senha em `AKME_NEO4J_PASSWORD` no arquivo `.env`.
- **Conexão do driver:** `bolt://127.0.0.1:7687`.

### Por que este caminho

| Escolha | Alternativa descartada | Motivo | Base |
|---|---|---|---|
| Docker | Instalar no sistema; Aura | Local e fácil de remover; os dados não saem da máquina | Decisão |
| `2026.10.1` | `5.26.32` LTS | A documentação indica essa imagem a quem não tem preferência; o capstone é curto e usa versão fixada | Fonte [1]; decisão D1 |
| Tag exata | `neo4j:latest` ou `neo4j:5` | Tags móveis mudam com o tempo, e queremos repetir o mesmo resultado | Pesquisa; decisão |
| Community | Enterprise | Não exige contrato; a imagem usada é a padrão, sem o sufixo `-enterprise` | Pesquisa; edição provada em P2 |
| Só em `127.0.0.1` | `--publish=7474:7474`, como no exemplo oficial | Sem o endereço, a porta fica aberta para a rede | Decisão; provado em P6 e P7 |
| Senha aleatória em `.env` | Senha padrão | O `.env` é ignorado pelo Git e só o dono do arquivo consegue ler | Provado em P9 |
| Volume nomeado | Pasta local, como no exemplo oficial | Mantém os dados ao recriar o contêiner, sem criar pasta no projeto | Fonte [1] para persistir em `/data`; decisão pelo volume nomeado |
| Sem `--restart always` | Reinício automático, como no exemplo oficial | Em ambiente de estudo, o banco só roda quando pedimos | Decisão |

### Provas

Saídas de 05/11/2026, com `cypher-shell` executado dentro do contêiner.

| # | O que prova | Resultado |
|---|---|---|
| P1 | O banco responde consultas | `RETURN 1` devolve `1` |
| P2 | Versão e edição são as escolhidas | `"Neo4j Kernel", ["2026.10.1"], "community"` |
| P3 | O banco começa vazio | `count(n)` devolve `0` |
| P4 | O Browser está no ar | `http://127.0.0.1:7474/` devolve HTTP 200 |
| P5 | A autenticação está ativa | Senha errada: `Access denied` |
| P6 | As portas só estão publicadas localmente | `7474/tcp -> 127.0.0.1:7474` e `7687/tcp -> 127.0.0.1:7687` |
| P7 | A porta não responde pelo IP da rede | `curl` em `<IP da máquina>:7474`: conexão recusada (código 7) |
| P8 | A imagem é rastreável | `neo4j@sha256:7dbd307cc8f35d6a061cf71659d3d8f783c3db9e8c2f5bb9d54f77921931952a` |
| P9 | A senha está fora do Git | `git check-ignore` confirma `.gitignore:8:.env`; permissões `-rw-------` |

### Limites conhecidos

- A senha aparece em `docker inspect akme-neo4j`, porque foi passada como variável de ambiente. Isso é aceitável para um banco local com dados da demo, mas não para um cliente.
- O P7 testou a porta 7474 pelo IP de uma interface de rede. A porta 7687 não foi testada dessa forma; a evidência para ela é o P6.
- Esta configuração serve para a demo e não foi avaliada para produção.
- Ainda não carregamos nenhum dado.

### Erro de autenticação no Browser

Em 05/11/2026 o Browser mostrou "The client is unauthorized due to authentication failure", enquanto a senha do `.env` funcionava no `cypher-shell` e no driver, pela porta 7687 publicada. A senha do `.env` tem 32 caracteres, e o campo do Browser mostrava cerca de 21 (contagem visual na captura de tela). Colar a senha do `.env` no campo resolveu, o que confirma que a causa era a senha preenchida. Quem a preencheu, possivelmente o gerenciador do Chrome, não foi confirmado.

Para copiar a senha sem exibi-la no terminal:

```bash
grep '^AKME_NEO4J_PASSWORD=' .env | cut -d= -f2- | tr -d '\n' | pbcopy
```

### Como repetir ou desfazer

```bash
docker stop akme-neo4j                 # para o banco
docker start akme-neo4j                # liga de novo, com os mesmos dados
docker rm -f akme-neo4j                # remove o contêiner e mantém o volume
docker volume rm akme-neo4j-data       # apaga os dados de vez
```

## Task 2: driver Python e conexão

### O que foi feito

Instalamos no ambiente do projeto o driver oficial `neo4j` e testamos a conexão pela função que a carga vai usar. Nenhum dado foi gravado.

```bash
uv sync --inexact --extra dev --extra neo4j
```

O projeto não carrega o `.env` sozinho, então as variáveis precisam ser exportadas antes de cada execução real:

```bash
set -a; . ./.env; set +a
```

### Por que este caminho

| Escolha | Alternativa descartada | Motivo | Base |
|---|---|---|---|
| Driver oficial | `cypher-shell` ou `LOAD CSV` | É o caminho que o rascunho já usa; funciona por conexão Bolt, sem o servidor precisar acessar os arquivos | Pesquisa; decisão |
| Versão 6.4.1 | Série 5.x | É a última versão publicada e a que o `uv.lock` já resolve | Fonte [2]; provado em D1 |
| `--inexact` | `uv sync` normal | Não remove pacotes de outros extras já instalados, como o `psycopg` | Decisão; provado em D1 |
| Credenciais por variável de ambiente | Senha no código | A senha fica fora do Git, e a função falha se ela faltar | Provado em D2 e D7 |
| `verify_connectivity()` | Só criar o driver | Criar o driver não abre uma conexão, então isso não testaria nada | Fonte [3] |

### Provas

| # | O que prova | Resultado |
|---|---|---|
| D0 | O driver não estava instalado antes | `driver instalado: False` |
| D1 | O driver foi instalado, sem remover outros pacotes | `neo4j 6.4.1`, Python 3.12.13; `psycopg`, `openpyxl` e `pytest` presentes |
| D2 | O código do projeto lê a configuração | `_connection()` devolve `bolt://127.0.0.1:7687`, `neo4j`, senha definida |
| D3 | O driver conversa com o servidor certo | `Neo4j/2026.10.1`, protocolo `(6, 1)` |
| D4 | Nenhum dado foi gravado | `count(n)` devolve `0` |
| D5 | O driver respeita a autenticação | Senha errada: `AuthError` |
| D6 | O caminho real de execução funciona | `cypher._run(["RETURN 1"])` executa `1` instrução |
| D7 | A falta de configuração gera erro claro | `RuntimeError` citando as três variáveis |
| D8 | Os testes do exportador e do gabarito continuam passando | 15 passaram (`tests/test_publish_neo4j.py`, `tests/test_demo_oracle.py`) |

### Limites conhecidos

- O D6 prova a conexão com uma instrução inofensiva. A carga real só será testada na task 4.
- O piso `neo4j>=5.0` no `pyproject.toml` é mais baixo que o recomendado pela pesquisa. Ele não afeta esta instalação, que usa o `uv.lock`, e o ajuste fica para a P1.
- A instalação também acrescentou pacotes do extra `dev`, como `python-pptx`, e atualizou `pytz` para a versão do `uv.lock`.

## Task 3: script em dry-run

### O que foi feito

Geramos o script sem gravar no banco e o comparamos com o gabarito (`examples/local_demo/gabarito.json`), que é calculado direto dos CSVs por outro código.

```bash
uv run akme publish --target neo4j
```

O resultado é `docs/publish/neo4j.cypher`, com 11 instruções, nesta ordem:

| Ordem | Instruções | O que fazem |
|---|---|---|
| 1 | 4 `CREATE CONSTRAINT` | Impedem duas entidades com a mesma chave |
| 2 | 4 `UNWIND ... MERGE` | Criam os nós: 8 `Cliente`, 17 `ItemPedido`, 10 `Pedido` e 8 `Produto` |
| 3 | 3 `MATCH ... MERGE` | Ligam os nós: `pertenceA`, `contem` e `referencia` |

### Por que este caminho

| Escolha | Motivo | Base |
|---|---|---|
| Ler o script antes de executar | A carga grava no banco; o dry-run mostra o que vai acontecer sem esse risco | Decisão |
| Constraints antes dos dados e nós antes das arestas | A Neo4j recomenda essa ordem na importação | Pesquisa |
| Comparar com o gabarito | O relatório do `publish` é calculado pelo próprio gerador e não serve como prova independente | Pesquisa; decisão |
| Não corrigir nada agora | A meta é ter o grafo funcionando, e nada encontrado aqui parece impedir a carga da demo | Decisão |

### Provas

| # | O que prova | Resultado |
|---|---|---|
| S1 | O dry-run não exige credenciais | Rodou sem as variáveis `AKME_NEO4J_*` |
| S2 | O dry-run não grava no banco | 0 nós antes e depois; `executed: 0` |
| S3 | O script é repetível | Duas gerações com o mesmo hash, `0a4542ee99aea6be4d0769784ddb0855d1ab7526` |
| S4 | O script traz todas as linhas | Linhas contadas no próprio script: 8/17/10/8, total 43, iguais ao gabarito |
| S5 | A previsão de arestas bate com o gabarito | `publish`: `contem` 17, `pertenceA` 10, `referencia` 17; gabarito: `CONTEM` 17, `PERTENCE_A` 10, `REFERENCIA` 17 |
| S6 | Nada foi omitido | `relations_not_published`, `rows_skipped`, `truncated_sources` e `sources_skipped` vazios |
| S7 | O script está fora do Git | `git check-ignore`: `.gitignore:14:docs/publish/` |

### Limites conhecidos

- O script **ainda não foi executado**. Ler o texto não prova que o Cypher é válido nem que as arestas serão criadas; isso fica para as tasks 4 e 5.
- O S5 compara uma previsão com o gabarito. As arestas reais só existem depois da carga.
- O S6 não detecta tudo: uma fonte sem classe associada não é lida nem aparece em `sources_skipped` (leitura de `_labels` e `build` em `akme/tools/cypher.py`). Na demo, as 4 fontes foram exportadas (S4), mas outro projeto poderia perder uma fonte sem aviso.
- Pontos observados no script e deixados para a P1:
  - `ItemPedido` é identificado pela posição da linha (`_akme_row`).
  - `nf` sai como número (`55010`).
  - As datas saem como texto (`"2026-07-03"`).
  - As arestas usam `pertenceA`, e não `PERTENCE_A`, como aprovado em D3; o gabarito usa o nome aprovado.
  - Não há índice em `ItemPedido.id_pedido`.

### Para o guia

- **O usuário final faz:** roda o comando e lê o resumo; não precisa ler o Cypher.
- **O template pode fazer:** apresentar o resumo em linguagem clara e avisar quando algo for omitido.

## Task 4: primeira carga real

### O que foi feito

O próprio usuário executou a carga no terminal, confirmando na CLI como exige a regra 5 do `SKILL.md`. Foi a primeira execução real do rascunho, sem nenhuma alteração no código.

```bash
set -a; . ./.env; set +a
echo y | uv run akme publish --target neo4j --no-dry-run
```

### Por que este caminho

| Escolha | Motivo | Base |
|---|---|---|
| Rodar o rascunho sem alterar | Mostra como ele se comporta de fato, antes de qualquer correção | Pesquisa (roteiro, etapa 3) |
| Confirmação feita pelo humano na CLI | Executar no alvo exige confirmar na conversa e na CLI | `SKILL.md`, regra 5 |
| Banco local e só dados da demo | Um erro nesta etapa não afeta dados de ninguém | Decisão |

### Provas

| # | O que prova | Resultado |
|---|---|---|
| C1 | O banco estava vazio e o destino era local | Antes da carga: 0 nós, 0 constraints, `bolt://127.0.0.1:7687` |
| C2 | Todas as instruções rodaram sem erro | `"dry_run": false`, `"statements": 11`, `"executed": 11` |
| C3 | Os dados foram gravados | Consulta direta ao banco: 43 nós, 44 arestas, 4 constraints |
| C4 | O script executado é o que foi revisado | Mesmo hash da task 3, `0a4542ee99aea6be4d0769784ddb0855d1ab7526` |

Estes resultados confirmam na prática que o Cypher gerado é aceito pelo Neo4j `2026.10.1` Community.

### Limites conhecidos

- Os totais batem, mas os números por label e por tipo de aresta ainda serão comparados com o gabarito na task 5.
- Valores das propriedades e consultas de negócio ainda não foram conferidos (tasks 5 e 6).
- A repetição da carga ainda não foi testada (task 7).
- Uma carga bem-sucedida na demo não prova nada sobre os casos difíceis listados em "O que podemos garantir".

### Para o guia

- **O usuário final faz:** roda um comando e confirma.
- **O template pode fazer:** carregar o `.env` sozinho, para dispensar o `set -a`, e mostrar o resultado em linguagem clara.
- **Erro que ele pode encontrar:** sem as variáveis de conexão, o comando falha citando `AKME_NEO4J_URI`, `AKME_NEO4J_USER` e `AKME_NEO4J_PASSWORD` (provado em D7).

## Task 5: banco comparado com a origem

### O que foi feito

Comparamos o conteúdo do Neo4j com os CSVs e com `examples/local_demo/gabarito.json`, por meio de consultas somente de leitura. Foram 26 verificações, e todas passaram.

### Por que este caminho

| Escolha | Motivo | Base |
|---|---|---|
| Comparar com os CSVs brutos | O relatório do `publish` vem do próprio gerador, então não prova nada sobre o banco | Pesquisa; decisão |
| Comparar cada valor e cada ligação | Contagens podem bater mesmo com dados trocados ou arestas erradas | Decisão |
| Procurar propriedades extras | Exportação correta também não pode inventar dados | Decisão |
| Consultar com `routing_='r'` | A verificação não deve gravar nada | Decisão |

### Provas

| # | O que prova | Resultado |
|---|---|---|
| V1 | Nós por tipo | `Cliente` 8, `ItemPedido` 17, `Pedido` 10, `Produto` 8; cada nó com um só label |
| V2 | Arestas por tipo | `pertenceA` 10, `contem` 17, `referencia` 17, mapeados para os nomes do gabarito |
| V3 | Nenhum valor foi perdido ou alterado | 216 células comparadas, nenhuma diferença |
| V4 | Nenhum dado foi inventado | Nenhuma propriedade fora dos CSVs, exceto `_akme_row` |
| V5 | Cada ligação é a correta | Os pares das 3 relações são idênticos aos dos CSVs |
| V6 | Multiplicidade de `pertenceA` | Todo pedido com exatamente 1 cliente; clientes 3 e 7 sem pedido, como nos CSVs |
| V7 | As regras existem no banco | As 4 constraints previstas |
| V8 | Somas | 2.999 itens; `vl_total` sem filtro 26.797,35; faturamento 23.077,35 |
| V9 | Consulta de negócio | Pedido 1001: `ARE-M3`=5, `ARG-20`=10, `CIM-50`=100 |
| V10 | O erro de fan-out acontece como previsto | Somar depois de `contem` dá 49.819,30, e o banco não acusa erro |

### Limites conhecidos

- **Os tipos não foram avaliados por V3**, que compara números pelo valor. Lido no banco, `nf` é `INTEGER` e `dt_pedido` é `STRING`. Nenhum valor mudou na demo, mas esses tipos são os previstos para correção na P1.
- O gabarito é referência provisória, porque ainda aguarda aprovação formal do usuário.
- Na task 5, o script de verificação ainda não estava salvo. Na task 7, ele foi salvo em `examples/local_demo/verificar_neo4j.py` e repetiu as mesmas 26 verificações.
- Isto prova a exportação da demo. Os casos difíceis de "O que podemos garantir" continuam abertos.

### Para o guia

- **O usuário final faz:** lê o resultado da conferência, sem escrever consultas.
- **O template pode fazer:** rodar esta comparação depois de toda carga, para qualquer projeto. O gabarito da demo não serve para isso, então a conferência geral terá de usar as fontes e os contratos.

## Task 7: repetir a carga

### O que foi feito

Salvamos a verificação em `examples/local_demo/verificar_neo4j.py`, registramos o estado do grafo, e o usuário executou a mesma carga uma segunda vez, confirmando na CLI. Depois, comparamos os dois estados.

```bash
set -a; . ./.env; set +a
uv run python examples/local_demo/verificar_neo4j.py
```

### Por que este caminho

| Escolha | Motivo | Base |
|---|---|---|
| Repetir a carga | Uma exportação usada mais de uma vez não pode duplicar dados | Pesquisa; decisão |
| Comparar conteúdo e identidades internas | As contagens não mostrariam nós recriados nem conteúdo trocado | Decisão |
| Resumo por hash | Permite comparar o grafo inteiro sem expor os dados | Decisão |

### Provas

| # | O que prova | Resultado |
|---|---|---|
| R1 | A segunda carga rodou sem erro | `"executed": 11` |
| R2 | O script executado é o que foi revisado | Mesmo hash, `0a4542ee99aea6be4d0769784ddb0855d1ab7526` |
| R3 | A verificação continua passando | 26 de 26, código de saída 0 |
| R4 | O conteúdo não mudou | Nós `2489afb7e5c05b53` e arestas `12d3d71a0487d6e5`, antes e depois |
| R5 | Nada foi recriado | Identidades de nós `eaab9da7bf8e69f5` e de arestas `42aaaefbafd4439c`, antes e depois |
| R6 | A saída completa da verificação é a mesma | `diff` sem diferenças |

### Limites conhecidos

- **Isto prova só a repetição com os mesmos dados.** Linhas apagadas, alteradas ou reordenadas na origem não foram testadas, e a leitura do código indica problemas nesses casos.
- Foi testada uma única repetição, na demo em CSV.
- A verificação é específica da demo.

### Para o guia

- **O usuário final faz:** pode rodar a exportação de novo com os mesmos dados.
- **O template pode fazer:** informar quantos elementos a carga criou ou alterou.
- **Aviso necessário enquanto a P1 não estiver pronta:** se a origem mudou, recarregar não basta para o grafo refletir a mudança.

## Correções da revisão

### A1: o MCP não carrega no Neo4j

- **Problema:** a tool `publish` do servidor MCP aceitava `dry_run=false` e o código não exigia confirmação, contrariando a regra 5 do `SKILL.md`. O risco foi encontrado na revisão por leitura do código; nenhuma carga desta exportação usou esse caminho.
- **Correção:** com `target="neo4j"` e `dry_run=false`, a tool recusa com `PermissionError` e indica o comando da CLI (`akme/server.py`).
- **Escopo:** só o alvo `neo4j`. `snowflake`, `databricks` e `rdf` continuam como antes, e a tool ainda aceita executar neles. Isso é um problema separado, anterior a este trabalho, e aguarda decisão do usuário.
- **Prova:** `tests/test_server_publish_guard.py`: a recusa em `neo4j`, o dry-run em `neo4j` e os outros 4 alvos sem mudança.
- **Limite:** isso fecha o caminho pela tool. Um agente com acesso ao terminal ainda poderia rodar a CLI, e `typer.confirm` aceita `y` por pipe, como em `echo y |`. Essa parte segue em aberto, assim como o texto das tasks 4 e 7, que trata esse comando como confirmação na CLI.
- **Para o guia:** o agente prepara e mostra o dry-run; quem executa a carga é o usuário.

### A2: resumo antes da confirmação e conferência depois da carga

- **Problema:** os avisos só apareciam depois da carga, e o relatório repetia a previsão do gerador sem consultar o banco. Ele poderia dizer "17 arestas" sem nenhuma ter sido criada.
- **Correção, só no alvo `neo4j`:**
  - Antes de confirmar, a CLI mostra o destino, sem credenciais, as contagens previstas e os avisos (`akme/cli.py`).
  - Depois da carga, conta no banco cada label e cada tipo de aresta previstos. Se houver divergência, o comando termina com erro e código 1 (`_verify` em `akme/tools/cypher.py`).
- **Provas automatizadas:** 8 testes novos em `tests/test_publish_neo4j.py`. Eles cobrem carga conferida, arestas ausentes, nós a mais, dry-run sem acesso ao banco, resumo antes da confirmação, credenciais fora da saída, avisos e código de erro. Usam um banco simulado.
- **Provas no banco real, somente leitura:**
  - `_verify` aceitou as contagens corretas.
  - Com previsões erradas de propósito, apontou `Cliente: esperado 7, encontrado 8`, `contem: esperado 99, encontrado 17` e `NaoExiste: esperado 1, encontrado 0`.
  - Recusar a confirmação terminou com código 1, e a impressão digital do grafo não mudou.
  - Sem as variáveis de conexão, o comando terminou com código 1 e uma mensagem clara.
- **Prova de ponta a ponta:** o usuário rodou a carga pelo fluxo novo, com `echo y |`. A saída trouxe o resumo antes da confirmação, `"executed": 11` e `"verification": {"ok": true, "divergences": []}`. O resultado da verificação da demo depois dessa carga está em "Conferência após a A2", logo abaixo.
- **Limites:**
  - A previsão vem do próprio gerador. A conferência detecta o que o banco não recebeu, mas não um erro na leitura da origem.
  - Compara contagens, não valores; a comparação de valores existe só na verificação da demo.
  - Os avisos são mostrados, mas ainda não bloqueiam a carga (A3).
  - Se a verificação falha, os dados já foram gravados: o erro avisa, mas não desfaz a carga.
  - Erros do driver, como senha errada, ainda não recebem mensagem tratada (grupo B).
- **Para o guia:** antes de confirmar, leia o destino e os avisos. Se a conferência falhar, não use o grafo até entender a divergência.

#### Conferência após a A2

Depois da carga de ponta a ponta, `examples/local_demo/verificar_neo4j.py` terminou com código 0 e 26 de 26 verificações. A saída foi idêntica à registrada antes da task 7, incluindo a impressão digital (`conteudo_nos` `2489afb7e5c05b53`, `conteudo_arestas` `12d3d71a0487d6e5`, `identidades_nos` `eaab9da7bf8e69f5`, `identidades_arestas` `42aaaefbafd4439c`). Isso confirma, na demo, que o fluxo novo não alterou o grafo.

### A3: recusar o que perderia dados

- **Problema:** em vários casos, o exportador seguia em frente e perdia dados, às vezes sem avisar.
- **Correção, só no alvo `neo4j`:** o exportador acumula uma lista `problems`. O dry-run mostra todos os problemas de uma vez, e a carga é recusada antes de conectar ao banco, sem pedir confirmação (`akme/tools/cypher.py`, `akme/cli.py`).

| Caso recusado | Mensagem |
|---|---|
| Fonte sem classe | `fonte extra sem classe associada: mapeie a fonte ou inclua em neo4j.exclude_sources` |
| Fonte com mais de uma classe | `fonte pedidos com mais de uma classe: Cliente, Pedido` |
| Duas fontes com a mesma classe | `classe Cliente em mais de uma fonte: clientes, clientes2` |
| Mais linhas que o limite | `fonte X truncada: tem mais de 100000 linhas` |
| Chave vazia | `fonte produtos: 1 linha(s) com chave sku vazia` |
| Chave repetida | `produtos.sku repete ['CIM-50']: o MERGE juntaria linhas diferentes. Rode akme validate` |
| Exclusão de fonte inexistente | `neo4j.exclude_sources cita fonte inexistente: nao_existe` |
| Fonte da ontologia ausente no adapter | `fonte X citada na ontologia, mas nao existe no adapter` |

- **Exclusão explícita:** uma fonte fora do escopo é declarada em `akme.yml`, e o resumo a mostra como aviso:

```yaml
neo4j:
  exclude_sources: [extra]
```

- **Provas automatizadas:** 11 testes falharam antes da correção e passam depois. O último caso da tabela não tem teste próprio. Os testes de recusa garantem que `_run` e `_observed` não são chamados.
- **Prova de uso real:** numa cópia temporária com fonte sem classe, chave vazia e chave repetida, com a URI apontando para uma porta sem serviço, o comando listou os 3 problemas de uma vez, terminou com código 1 e não pediu confirmação nem tentou conectar.
- **Prova de que a demo não mudou:** `problems` vazio e o script com o mesmo hash, `0a4542ee99aea6be4d0769784ddb0855d1ab7526`.
- **Limites:**
  - Testado com CSV em cópia da demo, ainda não com outro domínio nem com fontes SQL.
  - Uma fonte mapeada para classe e superclasse, como `Person` e `Party`, também é recusada como ambígua. Isso pode ser rigoroso demais e precisa ser avaliado com `teste_acme`.
  - Não há como aprovar uma exceção para chave vazia ou para fonte acima do limite; é preciso corrigir os dados.
  - `exclude_sources` não foi pedido na tabela original da A3. Foi acrescentado porque, sem ele, uma única fonte fora do escopo bloquearia toda a carga.
- **Para o guia:** se a carga for recusada, a mensagem indica a fonte e o que fazer. Depois de corrigir, rode o dry-run de novo.

### A4, parte 1: chave composta

- **Problema:** `ItemPedido` era identificado pela posição da linha (`_akme_row`). Reordenar ou apagar uma linha trocaria a identidade dos itens.
- **Correção, só no alvo `neo4j`:** a chave vem de `neo4j.keys`, no `akme.yml`, ou da coluna do lado "one" de uma relação. Sem nenhuma das duas, a carga é recusada. `_akme_row` deixou de existir. `akme init --demo` já grava a chave da demo.

```yaml
neo4j:
  keys:
    itens_pedido: [id_pedido, sku]
```

- **Provas automatizadas:** testes em `tests/test_publish_neo4j.py` para constraint e `MERGE` compostos, independência da ordem das linhas, fonte sem chave, coluna ou fonte inexistente, chave repetida e parte da chave vazia.
- **Limites:**
  - O script mudou de hash para `ff7ed9a025a3608558d5cd96016d263e06966485`, então as provas das tasks 4 a 7 valem para o script anterior. A carga, a comparação e a repetição foram refeitas (ver "Prova no banco real").
  - `akme.yml` é ignorado pelo Git, então a chave de um projeto real não fica versionada. Avaliar levá-la para a ontologia, com aprovação pelo fluxo normal.
  - Reordenar as linhas é provado no script, ainda não no banco. O cenário de linha apagada continua dependendo da sincronização (grupo B).
- **Preparação do banco:** o grafo local foi apagado com `DETACH DELETE`, e as 4 constraints antigas foram removidas, porque a identidade dos itens mudou.
- **Para o guia:** toda tabela sem chave óbvia precisa de uma chave declarada. A mensagem de recusa indica onde declarar.

#### Prova no banco real

Com o banco vazio, o usuário executou a carga, com `echo y |`. Resultado:

- Carga: `"executed": 11`, `"problems": []`, `"verification": {"ok": true, "divergences": []}`.
- Verificação da demo: 26 de 26, código de saída 0, 216 células sem diferença.
- Constraint no banco: `akme_ItemPedido_id_pedido_sku`, tipo `NODE_PROPERTY_UNIQUENESS`, em `["id_pedido", "sku"]`.
- Itens com `_akme_row`: 0.
- Impressão digital: `conteudo_nos` `17695392dc6849f8`, `conteudo_arestas` `4f98c2bd6ec1f5ed`, `identidades_nos` `eaab9da7bf8e69f5`, `identidades_arestas` `42aaaefbafd4439c`.

O conteúdo mudou, como esperado, porque os itens perderam `_akme_row`. As identidades internas ficaram iguais às do grafo anterior, ao contrário do que previmos. A explicação provável é o Neo4j reutilizar os identificadores depois do `DETACH DELETE`, mas isso não foi confirmado. Consequência: comparar identidades só mostra recriação entre cargas sem limpeza no meio.

**Repetição:** o usuário rodou a mesma carga outra vez, sem limpar o banco. Resultado: `"executed": 11`, `verification.ok` verdadeiro, 26 de 26 verificações, script com o mesmo hash, e impressão digital igual à da primeira carga nos quatro valores. Nada foi duplicado ou recriado.

### A4, parte 2: tipos por coluna

- **Problema:** o tipo dependia dos dados. `nf` virava número, as datas ficavam como texto, e um único valor diferente mudava o tipo da coluna inteira.
- **Decisões do usuário:** dinheiro fica em `FLOAT`, com arredondamento na saída, e coluna sem tipo declarado vira texto, porque isso não perde informação como zeros à esquerda.
- **Correção, só no alvo `neo4j`:** os tipos vêm de `neo4j.types`, no `akme.yml`, e aceitam `string`, `integer`, `float` e `date`. O exportador deixou de usar o profile para decidir tipos. `akme init --demo` já grava os tipos da demo.

```yaml
neo4j:
  types:
    clientes: {dt_cadastro: date}
    itens_pedido: {qt_itens: integer, vl_item: float}
    pedidos: {dt_pedido: date, vl_total: float}
    produtos: {vl_unitario: float}
```

- **O que recusa a carga:** valor que não converte sem perda (`03/07/2026` em `date`, `4.120,50` em `float`, `007` em `integer`, data com horário), tipo desconhecido, fonte ou coluna inexistente, e chave ou coluna de join declarada com tipo diferente de `string`.
- **Provas automatizadas:** a suíte de Neo4j e MCP passou de 40 para 71 testes, a maioria casos de valores aceitos e recusados. A suíte completa teve 170 aprovados, 1 pulado e a mesma falha de Postgres.
- **Prova de que a nova checagem detecta o problema:** `verificar_neo4j.py` ganhou a verificação "tipos gravados", agora 27 no total. Contra o grafo anterior, as outras 26 passaram e ela falhou, com código de saída 1.
- **Script:** novo hash `963e6f2f2bece1d275e8172ce17503fe000c66f9`, 11 instruções e `problems` vazio.
- **Preparação do banco:** o grafo local foi apagado com `DETACH DELETE`, depois de conferir que só havia os 4 labels da demo. As 4 constraints foram mantidas, porque não mudaram.
- **Limites:**
  - A repetição da carga com este script ainda não foi testada.
  - `FLOAT` pode acumular erro de arredondamento em somas; não serve para uso contábil.
  - Medida sem tipo declarado vira texto e não soma. O erro de declaração não é detectado.
  - Testado com CSV. Uma chave vinda do Excel como número pode virar `"1001.0"` e não casar com `"1001"` de outra fonte. Isso precisa ser testado na rodada com outros dados.
  - Datas com horário são recusadas, porque ainda não há tipo `datetime`.
- **Para o guia:** declare o tipo de toda medida e data. O que ficar sem declaração será texto.

#### Prova no banco real

Com o banco sem nós, o usuário executou a carga, com `echo y |`. Resultado:

- Carga: `"executed": 11`, `"problems": []`, `"verification": {"ok": true, "divergences": []}`.
- Verificação da demo: 27 de 27, código de saída 0, 216 células sem diferença.
- Tipos lidos no banco, no pedido 1001: `nf` `"55010"` é `STRING`, `dt_pedido` `2026-07-03` é `DATE`, `vl_total` `4120.5` é `FLOAT`.
- Impressão digital: `conteudo_nos` `563404a69a988413`, `conteudo_arestas` `46ea529883a477ff`, `identidades_nos` `eaab9da7bf8e69f5`, `identidades_arestas` `42aaaefbafd4439c`.

## Fontes

1. Neo4j Operations Manual, [Docker: Introduction](https://neo4j.com/docs/operations-manual/current/docker/introduction/). Lida em 05/11/2026. Trechos usados: "If you are unsure which base image to use or have no preference, just use the default of neo4j:2026.10.1"; o `--volume` em `/data` para persistir dados; e `NEO4J_AUTH` para definir a senha inicial.
2. PyPI, [neo4j](https://pypi.org/project/neo4j/). Consultado em 05/11/2026: última versão 6.4.1, Python >=3.10, licença Apache-2.0 AND Python-2.0.
3. Neo4j Python Driver Manual, [Connection](https://neo4j.com/docs/python-manual/current/connect/). Lida em 05/11/2026. Trecho usado: "Creating a Driver instance only provides information on how to access the database, but does not actually establish a connection".
