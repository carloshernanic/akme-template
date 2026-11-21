# akme-template

Template para construir, validar e publicar uma ontologia e uma camada semantica sobre uma base de dados. Segue LOT + NeOn com humano no loop: um agente de IA (Claude Code, de preferencia, ou Codex, Cursor ou Antigravity) le o `SKILL.md`, consulta a ontologia pelo servidor MCP `akme` e propoe edicoes que so entram na ontologia depois de aprovadas por uma pessoa. A ontologia vive em `ontology/` como texto versionado; Snowflake, Databricks, Postgres e pastas locais sao apenas entradas e alvos de publicacao.

> Vai comecar um projeto de verdade? Siga **Criar uma ontologia do zero**. A secao **Demo** no fim usa dados de exemplo e serve so para conhecer a ferramenta.

## Criar uma ontologia do zero

### 1. Prepare o ambiente

Requisitos: Python 3.11+, [uv](https://docs.astral.sh/uv/) e [Claude Code](https://code.claude.com) (recomendado) ou outra harness com MCP: Codex, Cursor ou Antigravity (ver **Outras harnesses**).

```bash
uv sync
```

Instale tambem o extra de cada formato ou banco que quiser conectar:

| Fonte | Extra |
|---|---|
| `.xlsx`, `.docx`, `.pptx` | `uv sync --extra office` |
| `.pdf` | `uv sync --extra pdf` |
| Postgres, Snowflake, Databricks | `uv sync --extra postgres` (ou `snowflake`, `databricks`) |
| neo4j | `uv sync --extra neo4j`|

Os extras se somam no mesmo comando, ex: `uv sync --extra office --extra pdf`. Cuidado: cada `uv sync` remove os extras que nao estao no comando. Para acrescentar um extra sem perder os outros, use `--inexact` (ex: `uv sync --inexact --extra neo4j`).

### 2. Aponte para os dados

**Arquivos (pasta local).** Coloque planilhas e documentos em `data/` (pode ter subpastas; o git ignora o conteudo dessa pasta) e rode:

```bash
uv run akme init
```

Aceita `.csv` e `.xlsx` (cada aba vira uma fonte) e documentos `.md`, `.txt`, `.pdf`, `.docx` e `.pptx`, lidos por pagina ou slide. Formatos antigos (`.xls`, `.doc`, `.ppt`) precisam ser salvos no formato novo.

**Banco de dados.** Copie `.env.example` para `.env`, preencha as variaveis do banco (`AKME_PG_*`, `AKME_SNOWFLAKE_*` ou `AKME_DATABRICKS_*`) e rode, por exemplo:

```bash
uv run akme init --adapter databricks
```

Nos dois casos, confira se a conexao enxerga as fontes:

```bash
uv run akme connect
```

O `init` cria o `akme.yml` (configuracao local, nao vai para o git). Nunca commite `data/`, `akme.yml` nem `.env`.

### 3. Abra o agente e comece

Na pasta do projeto, abra o Claude Code:

```bash
claude
```

Na primeira vez ele pergunta se pode usar o servidor MCP `akme` deste projeto: aceite. Depois peca, por exemplo: **"vamos criar a ontologia"**. A skill `akme` carrega sozinha e o agente conduz o resto.

Na etapa de Conceitualização o agente abre a pagina de revisao em `http://127.0.0.1:8765`. La cada proposta aparece com a evidencia e com o que o dado mostra, e voce aceita, ajusta ou rejeita. Quando voce aplica, o agente segue sozinho.

> **Modo canal (opcional, só no Claude Code):** para conversar com o agente pela propria pagina, sem voltar ao terminal, abra o Claude Code com `claude --dangerously-load-development-channels server:akme` e a pagina com `uv run akme review`. O painel "Conversa" da pagina passa a falar com a sessao. A flag mostra um aviso de "desenvolvimento local" porque o canal do akme nao esta na lista aprovada da Anthropic.

### Outras harnesses

O Claude Code é o recomendado, mas o fluxo é o mesmo em qualquer agente com MCP: as instruções do projeto estao em `AGENTS.md`, a skill em `.agents/skills/akme/` aponta para o `SKILL.md` e o servidor e sempre `uv run akme serve`.

| Harness | Skill | Servidor MCP `akme` |
|---|---|---|
| Claude Code | `.claude/skills/akme/` | `.mcp.json` (aceite na primeira vez) |
| Codex | `.agents/skills/akme/` | `.codex/config.toml`; o Codex so le esse arquivo depois que voce marca a pasta como confiavel ao abrir `codex` nela |
| Cursor | `.agents/skills/akme/` | `.cursor/mcp.json`; ative o `akme` em Settings > MCP |
| Antigravity (`agy`) | `.agents/skills/akme/` | `.agents/mcp_config.json`; Ative o `akme` pelo comando `\mcp`|

Só o Claude Code tem: o modo canal, os agentes de pesquisa de `.claude/agents/` e o formulario de "quem decide" (nas outras a pergunta vem no chat). Se as tools do `akme` nao aparecerem depois de mudar o servidor, reinicie o MCP na harness (Claude Code: `/mcp`; Codex e `agy`: abra uma sessao nova; Cursor: recarregue em Settings > MCP).

### 4. Primeiro passo: quem decide

Antes de tudo, o agente pergunta quem decide as propostas:

- **Voce (modo humano, padrao):** o agente propõe e voce decide cada proposta na pagina.
- **A IA (modo automatico):** a IA aceita, ajusta ou rejeita cada proposta e aplica em seu nome, com a assinatura "IA (modo automatico, autorizado por NOME)" no changelog. Você revisa no fim. Publicar no alvo continua exigindo a sua confirmação.

A escolha fica em `ontology/decision_mode.yml` e pode ser trocada a qualquer momento, pedindo ao agente.

### 5. As seis etapas

O agente segue as seis etapas do LOT descritas no `SKILL.md`. Em cada parada, ele abre a pagina, diz quantos itens esperam decisao e continua sozinho quando voce aplica.

| Etapa | O que o agente faz | O que voce decide |
|---|---|---|
| **1. Especificar** | Perfila os dados e le os documentos. Depois propoe de 2 a 3 casos de uso tirados das fontes e abre a pagina so com eles (nao pergunta no chat). Com o caso de uso escolhido, define proposito, escopo e usuarios, dez perguntas de competencia (CQs), lacunas, divergencias e o glossário de siglas, sempre citando a fonte. | Primeiro, quais casos de uso valem (ou escrever o seu, ou dizer que não há). Depois, quais CQs valem e com que prioridade, quais ficam reservadas para o teste final, e como tratar lacunas e divergencias. Enquanto os requisitos nao fecham, a ontologia nao e criada. |
| **2. Conceitualizar** | A partir das CQs aprovadas, propõe classes, relações e termos; métricas levam unidade, grao e aditividade. Busca termos reutilizaveis na LOV. | Aceitar, ajustar ou rejeitar cada classe, relacao e termo. |
| **3. Codificar** | Propoe o mapping de cada termo para tabela e coluna, regras implicitas dos documentos (restricoes) e qual fonte prevalece quando elas divergem (precedencia). Roda o `validate`. | Aceitar ou rejeitar mappings, restricoes e precedencias. |
| **4. Avaliar** | Roda `validate` (cobertura e pitfalls) e `eval` (as CQs reservadas como teste) e propoe correcoes. | Voltar para a etapa 2 ou 3, ou seguir para publicar. |
| **5. Publicar** | Gera o artefato do alvo em dry-run em `docs/publish/`: Snowflake (semantic view), Databricks (comments), YAML, RDF ou Neo4j. | Se e quando publicar. Executar no alvo e irreversivel e so acontece com a sua confirmacao: na CLI ou, para o Neo4j, no botao do passo "Neo4j" da pagina. |
| **6. Manter** | Cada mudanca comeca com um registro (issue ou CQ nova), e o agente classifica e lista o impacto. | O escopo da mudanca e quando ela entra em release. |

Nada entra na ontologia ate ser aplicado com o nome de quem aprovou: pela pagina ("Salvar e aplicar" ou "Aplicar decisões", que pedem o seu nome), dizendo "aplicar" no chat ou na CLI (`uv run akme apply --all-reviewed --approved-by NOME`). Para saber em que ponto o projeto esta, rode `uv run akme stage` ou olhe o topo da pagina.

### Exportar para o Neo4j

Instale o extra do Neo4j uma vez (o `--inexact` mantem os outros extras ja instalados):

```bash
uv sync --inexact --extra neo4j
```

Depois, o passo "Neo4j" da pagina (`uv run akme review`) guia a exportacao em quatro passos: conectar à sua instância Neo4j, conferir a previa, carregar e ver o grafo. A publicação é feita pelo usuário, pela página de revisão ou pela comando no terminal; o agente não carrega.

Pela CLI, o caminho e este:

1. Conecte com o Neo4j: 

   Suba a instância (Neo4j Desktop, Aura ou Docker) e atualize as variaveis de ambiente no `.env`.

   ```bash
   AKME_NEO4J_URI=bolt://127.0.0.1:7687
   AKME_NEO4J_USER=neo4j
   AKME_NEO4J_PASSWORD=<senha com pelo menos 8 caracteres>
   ```

   

3. Gere a previa (dry-run, nao toca no banco e apenas prepara a publicação):

   ```bash
   uv run akme publish --target neo4j
   ```

4. Carregue. A CLI mostra o destino, o que vai gravar e o que o banco tem hoje, e pede confirmacao:

   ```bash
   uv run akme publish --target neo4j --no-dry-run
   ```

5. Abra o Neo4j Browser em `http://localhost:7474`. Com o `uv run akme review` ligado, o tutorial do projeto abre com `:guide http://127.0.0.1:8765/neo4j/guia`.

O passo a passo completo, as opcoes do `.env` e a tabela de erros estao em `reports/docs_exp_neo4j/README.md`.

### Onde fica cada coisa

- `ontology/`: a ontologia (`schema.ttl`, `content.yml`, `manifest.yml`), o historico (`changelog.yml`) e as propostas aguardando decisao (`pending/`)
- `validation/questions.yml`: as CQs reservadas que o `eval` usa como teste
- `docs/`: a pagina de revisao e as saidas do `export`; `docs/publish/` guarda os artefatos de publicacao

## Comandos individuais

O agente roda estes passos por voce; use direto quando quiser:

- `uv run akme connect`: testa a conexao e lista fontes e documentos
- `uv run akme profile`: perfila as fontes (colunas, tipos, nulos, chaves candidatas)
- `uv run akme review`: serve a pagina de revisao (`--background` sobe e devolve a URL)
- `uv run akme stage`: etapa atual, o que falta e o proximo passo
- `uv run akme validate` e `uv run akme eval`: verificacao formal e teste pelas CQs
- `uv run akme export`: gera os dados da pagina e os arquivos de exportacao
- `uv run akme publish --target snowflake`: publica (dry-run por padrao; `--no-dry-run` executa)
- `uv run akme publish --target neo4j`: previa da exportacao para o Neo4j; `--no-dry-run` carrega no banco do `.env`, com confirmacao

## Demo (so para conhecer)

A demo usa dados ficticios de `examples/local_demo/` e uma copia propria da ontologia, sem tocar em `ontology/`. Nao use estes comandos num projeto real: o `init --demo` aponta o `akme.yml` para os dados de exemplo.

```bash
uv sync --extra dev
```

```bash
uv run akme init --demo
```

```bash
uv run akme demo
```

```bash
uv run akme review
```

Para voltar a um projeto real depois, rode `uv run akme init` de novo (sem `--demo`).

## Como adicionar um adapter

1. Crie `akme/adapters/<nome>.py` com uma classe que herda de `Adapter` (ou `SqlAdapter`) e implementa `list_sources()`, `read_schema(source)`, `read_sample(source, n)` e, se houver documentos, `read_docs()`.
2. Importe dependencias pesadas dentro de `connect()` usando `require("pacote", "extra")` para que a ausencia do extra gere mensagem clara.
3. Registre em `ADAPTERS` em `akme/adapters/__init__.py` e adicione o extra em `pyproject.toml`.
4. Adicione as opcoes padrao em `akme init` (`akme/cli.py`) e um teste em `tests/`.

## Agentes de pesquisa

Os dois agentes em `.claude/agents/` podem ser rodados de novo no Claude Code:

- `pesquisador-lot-neon`: le `docs/research/sources/neon-lot.pdf` e regenera `docs/research/lot-neon.md`, a base do `SKILL.md`.
- `observador-oeg`: varre `github.com/oeg-upm` com `gh` e gera `docs/research/oeg-upm-AAAA-MM-DD.md` com o que mudou desde a ultima rodada.

Peca ao Claude Code: "rode o agente observador-oeg" ou "rode o agente pesquisador-lot-neon".
