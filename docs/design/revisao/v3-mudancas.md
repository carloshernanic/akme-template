# Protótipo v3: o que mudou em relação ao v2

Arquivo: `v3-prototipo.html` (10/11/2026). Ele atende a dois pedidos do usuário:

- a pessoa também cria perguntas de competência, então criar precisa ser uma opção clara;
- a decisão de aceitar ou rejeitar precisa ficar mais visível.

## Criar pergunta

- No topo da tela de perguntas há uma caixa fixa, "Criar pergunta", com o campo da pergunta, a escolha do caso de uso e o botão "+ Adicionar" (Enter também funciona).
- O card criado aparece no grupo do caso de uso, com borda azul e o rótulo "escrita por você · entra como aceita". Ele não passa por aceitar ou rejeitar, porque foi a própria pessoa que escreveu.
- Ainda pede tipo, prioridade e uso (e a resposta esperada, se o uso for Teste). Conceitos é opcional.
- Clicar em adicionar com o campo vazio mostra um aviso e não cria nada.

## Avaliar as perguntas sugeridas pela IA

- Cada card tem embaixo uma faixa de avaliação com dois botões grandes, "✓ Aceitar" em verde e "✕ Rejeitar" em vermelho.
- Antes de decidir, o card mostra "Para avaliar". Depois, a borda esquerda e a etiqueta ficam verdes ("Aceita") ou vermelhas ("Rejeitada").
- A linha "Para avaliar" traz três critérios de leitura: está clara? serve ao caso de uso? os dados respondem? No terceiro aparece a verificação da IA, por exemplo "IA: sim, pedidos.csv tem UF e vl_total".
- Para rejeitar basta escolher um motivo entre "Pouco clara", "Fora do caso de uso", "Os dados não respondem", "Repetida" e "Outro motivo". O detalhe em texto é opcional, exceto em "Outro motivo".
- Ao aceitar, prioridade e uso aparecem lado a lado na mesma faixa.
- Acima da lista, um contador mostra quantas sugestões da IA ainda faltam avaliar.
- O resumo final lista as rejeitadas com o motivo de cada uma.

## Verificação

O fluxo inteiro foi rodado no Chrome (Playwright) em 1280 px e 390 px, sem erros no console.

Dois defeitos achados nesse teste foram corrigidos:

- o campo de criar voltava a mostrar o texto anterior depois de adicionar;
- "IA: sim" aparecia na cor de alerta em vez de verde.
