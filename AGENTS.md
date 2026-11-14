# akme-template

Template para construir, validar e publicar uma ontologia e uma camada semântica sobre a base de dados de um cliente, seguindo LOT + NeOn com humano no loop. Um agente lê `SKILL.md`, consulta a ontologia pelo servidor MCP `akme` e propõe edições tipadas que só entram na ontologia depois de aprovadas por uma pessoa.

## Stack
- Python 3.11+, gerenciado com `uv`
- MCP (SDK `mcp`, FastMCP) para as tools do agente; Typer + Rich para a CLI
- rdflib (OWL/Turtle), PyYAML, Pydantic
- Página local em HTML/CSS/JS puro, sem build
- Extras opcionais por adapter ou formato: `postgres`, `snowflake`, `databricks`, `rdf`, `neo4j`, `pdf`, `office`

## Estrutura
- `SKILL.md` — a skill do agente: regras e as seis etapas do fluxo (`.claude/skills/akme/SKILL.md` e `.agents/skills/akme/SKILL.md` só apontam para ela)
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
- `uv run akme serve` — sobe o servidor MCP (stdio); registrado em `.mcp.json` (Claude Code), `.codex/config.toml` (Codex) e `.cursor/mcp.json` (Cursor); no Antigravity, com `agy mcp add` (ver README)
- `claude --dangerously-load-development-channels server:akme` — modo canal (experimental, só Claude Code): a conversa com o agente acontece no painel "Conversa" da página local (`akme/channel.py`, log em `ontology/pending/chat.jsonl`)
- `uv run akme connect | profile | validate | eval | export | stage | publish` — passos individuais

## Convenções
- Toda escrita na ontologia passa por `propose_edit` (vai para `ontology/pending/`) e só é aplicada com o nome de quem aprovou; o `changelog.yml` registra proveniência
- No modo humano (`human`), antes de rodar o `profile` no Databricks ou bases multi-catálogo, o agente deve obrigatoriamente alinhar com o usuário se é necessário perfilar todas as tabelas de todos os catálogos/schemas ou restringir a um subconjunto de interesse
- As tools não chamam LLM: o julgamento semântico é do agente, sempre como proposta
- Texto voltado ao usuário em português; código e comentários em português sem acento
- Classes em PascalCase, relações em lowerCamelCase
- Commits em Conventional Commits, em português
- Testes usam uma cópia temporária do projeto (fixtures em `tests/conftest.py`), nunca a ontologia da raiz

## Cuidados
- `docs/index.html`, `docs/*.js`, `docs/*.css`, `docs/fonts/` e `docs/brand/` são cópias geradas pelo `akme export`; edite em `akme/static/`
- Nunca commite arquivos de `data/` nem `akme.yml` (configuração local)
- `publish` roda em dry-run por padrão; executar no alvo é irreversível
- Exportação para o Neo4j: o akme grava em Cypher puro, sem plugin (dry-run em `docs/publish/neo4j.cypher`), e cada carga sincroniza o banco com a origem; chave e tipos de cada tabela são decididos na etapa 5 (`add_source`) e a carga é só pelo humano: no botão da aba "Exportar" da página local (`akme/tools/neo4j_page.py`, `akme/static/exportar.js`) ou na CLI; o agente não tem tool nem rota para ela. Passo a passo em `reports/docs_exp_neo4j/README.md`. Cada `publish --target neo4j` gera também o tutorial do projeto no Neo4j Browser (`docs/publish/neo4j_guia.html`, servido pelo `akme review` em `/neo4j/guia`), só de navegação (ontologia, dados, explorar, como navegar e o caminho para perguntas em português no console da Aura). As arestas de dado têm o nome exato do TTL; as setas entre `Conceito` são `RELACAO_ONTOLOGIA` com o nome em `nome`
- Depois de mudar tools MCP, reinicie o servidor `akme` no harness para elas aparecerem
