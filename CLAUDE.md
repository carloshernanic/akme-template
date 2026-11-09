# akme-template

Template para construir, validar e publicar uma ontologia e uma camada semântica sobre a base de dados de um cliente, seguindo LOT + NeOn com humano no loop. Um agente lê `SKILL.md`, consulta a ontologia pelo servidor MCP `akme` e propõe edições tipadas que só entram na ontologia depois de aprovadas por uma pessoa.

## Stack
- Python 3.11+, gerenciado com `uv`
- MCP (SDK `mcp`, FastMCP) para as tools do agente; Typer + Rich para a CLI
- rdflib (OWL/Turtle), PyYAML, Pydantic
- Página local em HTML/CSS/JS puro, sem build
- Extras opcionais por adapter ou formato: `postgres`, `snowflake`, `databricks`, `rdf`, `pdf`, `office`

## Estrutura
- `SKILL.md` — a skill do agente: regras e as seis etapas do fluxo (`.claude/skills/akme/SKILL.md` só aponta para ela)
- `akme/` — pacote Python: CLI (`cli.py`), servidor MCP (`server.py`), servidor da página local (`review_server.py`), modelos
- `akme/tools/` — lógica determinística de cada tool (ler, propor, aplicar, validar, exportar, publicar)
- `akme/adapters/` — conectores de entrada (pasta local, Postgres, Snowflake, Databricks)
- `akme/static/` — fonte da página web (HTML, CSS, JS, fontes, marca)
- `ontology/` — a ontologia versionada em texto: `schema.ttl`, `content.yml`, `manifest.yml`, `changelog.yml`, `pending/`
- `validation/` — perguntas usadas pelo eval
- `examples/local_demo/` — dados e edições da demo
- `docs/` — guia do fluxo, pesquisa metodológica e saídas geradas pelo `export`
- `data/` — arquivos do cliente (o conteúdo é ignorado pelo git)
- `tests/` — pytest

## Comandos
- `uv sync --extra dev` — instala com dependências de teste
- `uv run pytest -q` — roda os testes (a suíte inteira leva alguns minutos)
- `uv run akme init --demo` e `uv run akme demo` — prepara e roda a demo
- `uv run akme review` — serve a página local em `http://127.0.0.1:8765`
- `uv run akme serve` — sobe o servidor MCP (stdio); registrado em `.mcp.json`
- `uv run akme connect | profile | validate | eval | export | stage | publish` — passos individuais

## Convenções
- Toda escrita na ontologia passa por `propose_edit` (vai para `ontology/pending/`) e só é aplicada com o nome de quem aprovou; o `changelog.yml` registra proveniência
- As tools não chamam LLM: o julgamento semântico é do agente, sempre como proposta
- Texto voltado ao usuário em português; código e comentários em português sem acento
- Classes em PascalCase, relações em lowerCamelCase
- Commits em Conventional Commits, em português
- Testes usam uma cópia temporária do projeto (fixtures em `tests/conftest.py`), nunca a ontologia da raiz

## Cuidados
- `docs/index.html`, `docs/*.js`, `docs/*.css`, `docs/fonts/` e `docs/brand/` são cópias geradas pelo `akme export`; edite em `akme/static/`
- Nunca commite arquivos de `data/` nem `akme.yml` (configuração local)
- `publish` roda em dry-run por padrão; executar no alvo é irreversível
- Depois de mudar tools MCP, reinicie o servidor `akme` no harness para elas aparecerem
