# Teste de usuário: primeiro uso com os dados ACME

- **Data:** 2026-10-30
- **Testador:** Mateus, no papel de consultor que usa o AKME pela primeira vez
- **Pasta:** `akme-teste-acme`, com o código do branch `fix-fluxo` sem commit
- **Dados:** 29 CSVs de seguros P&C (sinistros, apólices, prêmios) e um mapeamento R2RML do data.world, que o AKME não lê

## Passos seguidos

| # | O que o usuário fez | O que aconteceu | Esperado? |
|---|---|---|---|
| 1 | Abriu o Claude Code na pasta e pediu o mapeamento do domínio | O agente perguntou se havia caso de uso definido | Sim |
| 2 | Respondeu que não tem caso de uso | O agente seguiu e propôs as perguntas (CQs) | Sim. Falta conferir se o motivo foi gravado em `no_use_case` |
| 3 | Esperou a tela de revisão | O agente não abriu a tela. Só pediu que o usuário rodasse o comando | Não, como experiência de uso |
| 4 | Revisou, aplicou e seguiu até a conceitualização | A ontologia foi criada com cerca de 25 classes, relações, termos, mappings e glossário. O validate passou | Sim |
| 5 | Pediu para ver o resultado | O agente mandou abrir `docs/index.html`. Aberto direto no navegador, o arquivo não mostra a informação certa | Não |
| 6 | Abriu a página pelo servidor local, porta 8765 | O grafo com todas as classes ficou ilegível: nós e rótulos sobrepostos e nomes cortados | Não |

## Resultado

O usuário considerou que o fluxo deu certo de ponta a ponta. O grafo no estilo Protégé ficou para depois.

## Problemas de uso

1. **A tela de revisão não abre sozinha.** Um usuário novo nem saberia que a tela existe. O agente deveria subir `akme review` em segundo plano e abrir o navegador assim que as propostas ficam prontas, dizendo em uma linha o que fazer lá.

2. **O agente manda abrir o arquivo HTML em vez da página servida.** A instrução vem do passo 4 do `SKILL.md` ("aponte o humano para `docs/index.html`"), do `akme demo` no `cli.py` e do `README.md`. Aberto como arquivo, o navegador bloqueia a leitura dos dados e a página não funciona direito. O caminho certo é sempre `uv run akme review`, com a URL local.
3. **O grafo não escala.** Com o ACME, o grafo de força com todas as classes vira uma bagunça. O usuário pediu um comportamento como o do Protégé: navegar clicando nas entidades, que vão se abrindo.
4. **O painel de detalhe sobrepõe texto.** Na lista de relações, o nome da relação longa (ex.: `hasAgreementParticipation`) fica por cima de "Agreement para AgreementPartyRole".
5. **Rótulos cortados nos nós** ("Pagamento d.", "Valor da ap.", "Localizacao."). Classes sem acento ("Avaliacao", "Ocorrencia") também chamam atenção numa interface em português.

6. **Depois de gerar a ontologia, o usuário não sabe qual é o próximo passo.** O agente não fecha cada etapa dizendo onde o usuário está, entre as seis, e o que vem a seguir. O print também mostra mappings prontos (ex.: `agreement.Agreement_Type_Code`), sinal de que as etapas 2 e 3 podem ter sido feitas juntas, sem a parada de aprovação entre elas. Isso ainda precisa ser conferido.

## Dúvidas do usuário

1. **Para que serve "Uso: ajuste | reservada"?** O rótulo não se explica sozinho na tela.
   - *Resposta dada:* ajuste é uma CQ que o agente usa para construir a ontologia. Reservada é guardada para o teste final (`akme eval`), escondida durante a construção e com uma resposta esperada. O campo é opcional, e o padrão é ajuste.
   - *Melhoria sugerida:* trocar os rótulos por "Usar na construção" e "Guardar para teste (precisa de resposta)", com uma dica ao passar o mouse.

2. **O que faço depois de gerar a ontologia?**
   - *Resposta dada:* seguir pelas etapas 3 (codificar: mappings, regras, precedência), 4 (avaliar: validate e eval), 5 (publicar em dry-run) e 6 (manter).
   - *Melhoria sugerida:* toda resposta do agente ao fim de uma etapa termina com "Etapa X de 6 concluída. Próximo passo: ...", e a página mostra a etapa atual.

## Melhorias propostas (não aplicadas)

- O agente sobe a tela sozinho em segundo plano e avisa a URL.
- Os rótulos de uso ficam autoexplicativos na tela.
- `SKILL.md`, `cli.py` e `README.md` passam a apontar para `uv run akme review` e para a URL local, nunca para o arquivo.
- **Grafo no estilo Protégé:** a árvore de classes à esquerda continua sendo a navegação principal. O grafo mostra só a classe selecionada e seus vizinhos diretos: superclasse, subclasses e classes ligadas por relação. Clicar num vizinho o torna o centro, e um botão "+" expande mais um nível sem recentrar. Há um caminho de navegação (Entidade > Contrato > Apólice) e uma opção "ver tudo" para o grafo completo.
- O painel de relações passa a usar uma linha por relação, com o nome em cima e "de X para Y" embaixo.
