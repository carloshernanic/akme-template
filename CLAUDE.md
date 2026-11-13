@AGENTS.md

## Só no Claude Code
- Claude Code é a harness recomendada; `AGENTS.md` acima vale para todas (Codex, Cursor, Antigravity)
- Modo canal: `claude --dangerously-load-development-channels server:akme` leva a conversa para o painel "Conversa" da página local
- Subagentes de pesquisa em `.claude/agents/` (`observador-oeg`, `pesquisador-lot-neon`)
- Para recarregar tools MCP depois de mudar o servidor, rode `/mcp` e reinicie o `akme`
