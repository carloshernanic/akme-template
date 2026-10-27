# akme-template

Template para construir, validar e publicar uma ontologia e uma camada semantica sobre a base de dados de um cliente. Segue LOT + NeOn com humano no loop: um agente de IA le `SKILL.md`, consulta a ontologia pelo servidor MCP (`akme serve`) e propoe edicoes tipadas que so entram depois de aprovadas. Snowflake, Databricks, Postgres e pastas locais sao apenas adapters de entrada e alvos de publicacao; a ontologia vive em `ontology/` como texto versionado. No Claude Code, `.mcp.json` registra o servidor e `.claude/skills/akme` carrega a skill.

## Demo local

```bash
uv sync --extra dev
```

```bash
uv run akme init --demo
```

```bash
uv run akme demo
```

Depois abra `docs/index.html`. Os passos individuais sao `akme connect`, `akme profile`, `akme validate`, `akme eval`, `akme export` e `akme publish --target snowflake` (dry-run por padrao).

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
