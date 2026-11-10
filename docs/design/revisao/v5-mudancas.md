# Protótipo v5: o que mudou em relação ao v4

Arquivo: `v5-prototipo.html` (10/11/2026).

**Por quê:** o usuário ainda via informação demais na tela. A solução usa revelação progressiva (Nielsen Norman Group): a tela mostra só o necessário para decidir, e o resto aparece quando a pessoa pede. Das opções apresentadas, o usuário escolheu a A, com os cortes.

## Card enxuto

- Cada pergunta da IA mostra três coisas:
  - a pergunta;
  - um sinal da IA: "● os dados respondem" em verde, ou "● depende de 'cliente ativo' · ver D-01" em amarelo;
  - os botões Aceitar e Rejeitar.
- O link "ver detalhes" abre o id, o tipo, os conceitos, a evidência e o aviso de dependência.
- Uma pergunta decidida vira uma linha fina:
  - aceita: ✓ com a prioridade;
  - rejeitada: ✕ com o motivo;
  - a pergunta da própria pessoa leva a marca "sua".
- Clicar na linha ("rever") reabre o card, e "recolher" fecha de novo.
- O card fecha sozinho quando a decisão termina: ao escolher a prioridade ou o motivo da rejeição. Em "Outro motivo", ele fica aberto até a pessoa clicar em "recolher".

## Cortes

- Saiu a barra lateral, que repetia o stepper, e a página ficou centralizada.
- O card não mostra mais o caso de uso, que já é o título do grupo, nem "sugerida pela IA", que é o padrão.
- O id aparece só nos detalhes, e também saiu das listas de fora dos casos e de aplicadas.
- A linha "Para avaliar" com três critérios virou o sinal único da IA.
- Saíram as etiquetas "Para avaliar", "Aceita" e "Rejeitada"; o estado aparece pela cor da borda e pela linha recolhida.
- Os botões Aceitar e Rejeitar perderam o contorno amarelo de pendente.
- O "?" ficou só no título de cada etapa (um texto único para lacunas e divergências), e saiu o aviso de protótipo.
- A pergunta criada pela pessoa já entra no caso de uso escolhido na caixa de criação, então o campo de caso de uso saiu do card.

## Verificação

O fluxo inteiro foi rodado no Chrome (Playwright) em 1280 px e 390 px, sem erros no console. Ao escolher a prioridade, o card de aceitar recolhe. Ao escolher o motivo, o de rejeitar recolhe. A pergunta da pessoa recolhe ao escolher tipo e prioridade. "Rever" reabre o card, e o resumo final está correto.
