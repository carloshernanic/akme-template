# Protótipo v6: o que mudou em relação ao v5

Arquivo: `v6-prototipo.html` (10/11/2026).

**Por quê:** o usuário achou que a tela de lacunas e divergências tinha muito texto e pediu o mesmo card enxuto das perguntas.

## Lacuna

- O card mostra só três coisas:
  - a pergunta que os dados não respondem;
  - um sinal com o motivo, por exemplo "● os dados não têm data de entrega";
  - quatro botões: Pedir o dado ao cliente, Reformular a pergunta, Descartar e Deixar em aberto.
- O link "ver detalhes" abre o id, o caso de uso de origem e a evidência, por exemplo o cabeçalho de `pedidos.csv`.
- Um texto só é pedido quando a escolha precisa dele:
  - "Reformular" pede a nova pergunta;
  - "Descartar" e "Deixar em aberto" pedem o motivo;
  - "Pedir ao cliente" decide direto, sem texto.
- Quando há texto, o card fecha pelo botão "Concluir". Sem texto, ele vira linha na hora: ✓, a pergunta, a escolha e "rever".

## Divergência

- O título vira uma pergunta: "Qual definição de 'cliente ativo' vale?".
- As duas fontes aparecem como dois botões grandes, cada um com a fonte e a definição. Clicar escolhe e fecha o card.
- Abaixo do título fica uma linha com a sugestão da IA ("IA sugere A (financeiro)"), quais perguntas a divergência afeta (link para a CQ-002) e "ver detalhes", que mostra os arquivos e a justificativa da IA.
- O link "nenhuma das duas? outras opções" revela São coisas diferentes, Perguntar ao especialista e Deixar em aberto.
- "São coisas diferentes" pede o que diferencia os dois sentidos, e "Deixar em aberto" pede o motivo.

## Mudança de regra

O motivo deixou de ser obrigatório em toda decisão, como era no v2. Agora ele só é pedido nas saídas de escape (Descartar, Deixar em aberto) e quando é preciso escrever algo novo (a nova pergunta, ou o que diferencia os termos). Escolher A ou B, pedir o dado ao cliente ou perguntar ao especialista decide com um clique.

No código atual, o motivo é obrigatório nas lacunas e divergências que não ficam em aberto. Isso precisa ser alinhado na implementação.

## Verificação

O fluxo inteiro foi rodado no Chrome (Playwright) em 1280 px e 390 px, sem erros no console. Foram conferidos estes casos:

- "Reformular" sem texto não fecha e avisa o que falta.
- "Reformular" com o texto preenchido fecha.
- Escolher A fecha a divergência.
- "Deixar em aberto" pede o motivo.
- O resumo final mostra a nova pergunta da lacuna.
