# Protótipo v2: o que mudou em relação ao v1

Arquivo: `v2-prototipo.html` (10/11/2026). Ele responde aos defeitos levantados em `v1-feedback.md`; os números entre parênteses apontam para os itens de lá.

| # | Defeito no v1 | Como ficou no v2 |
|---|---|---|
| 1 | Salvar ignorava as etapas anteriores | "Conferir e salvar" só libera quando as três etapas estão completas. Se alguém clicar antes, um aviso diz o que falta e a página leva para a etapa pendente. |
| 2 | "+ Nova pergunta" não deixava escrever | Agora é "+ Escrever uma pergunta". O card traz pergunta, tipo, caso de uso e conceitos (só conceitos é opcional), recebe o rótulo "escrita por você", pode ser removido e já abre com o cursor no texto. |
| 3 | Não registrava o aprovador | Ao salvar, abre "Conferir e salvar" com o resumo do que vai ser registrado (casos, aceitas para construção ou teste, rejeitadas, lacuna, divergência) e pede o nome, que é obrigatório. As aplicadas mostram quem aprovou e quando. |
| 4 | Escolhas pré-feitas pela IA | Nada vem marcado. A sugestão da IA aparece como dica ("A IA sugere Alta"), sem selecionar nada. |
| 5 | Caso de uso não afetava as perguntas | As perguntas aparecem agrupadas pelos casos escolhidos. As de casos não marcados vão para "Fora dos casos escolhidos" e não precisam de decisão. O caso escrito pela pessoa pode receber perguntas. |
| 6 | Pergunta e divergência sem ligação | O card da CQ-002 mostra "Depende de como 'cliente ativo' for definido · Ver a divergência D-01", e a divergência mostra "afeta CQ-002". Os dois são links que levam ao outro card. |
| 7 | "Em aberto" era a saída fácil | O motivo passou a ser obrigatório em todas as opções, e cada opção diz o que acontece depois. A divergência ganhou "Perguntar ao especialista", "São coisas diferentes" e a sugestão da IA. |
| 9, 10 | Termos sem explicação e resposta esperada vaga | Há um "?" com uma linha de explicação em pergunta de competência, uso, lacuna e divergência. Construção e Teste têm uma frase embaixo. A resposta esperada traz um exemplo e diz que não precisa do número. |
| 11 | Estado e contadores errados | "Falta" atualiza no card enquanto a pessoa digita. Um caso escrito pela metade não conta como escolhido. Trocar a decisão limpa os campos da decisão anterior. |
| 12 | Botões da etapa 3 estourando | As opções da etapa 3 ficam numa grade de duas colunas. |
| 17 | Botão desabilitado sem retorno | O botão continua clicável e mostra o que falta. |
| 18 | Botões mortos | Saíram "Propor alteração" e "Fontes lidas". |
| 19 | Vocabulário inconsistente | As aplicadas usam "Teste", como o seletor. |

## Feito de passagem

- Os cards de caso de uso, o stepper e a barra lateral viraram botões e entram na ordem do Tab.
- Os botões de escolha ganharam `aria-pressed`, os campos ganharam `label` e o rodapé ganhou `aria-live`.
- O foco volta ao controle clicado.
- As bordas dos controles ficaram mais fortes (`--ln2` de 20% para 42%), para melhorar o contraste.
- No celular, o stepper mostra só os números (o nome aparece apenas na etapa atual) e o rodapé tem uma linha.
- Os ids seguem a sequência (CQ-005).

## Ficou para a implementação real

Escala para dezenas de perguntas (filtro, "próxima pendente", atalhos de teclado), a revisão completa de acessibilidade e abrir a fonte por trás da evidência.

## Mudança de regra a confirmar

No código atual (`akme/static/review.js`), lacuna e divergência "em aberto" deixam o motivo opcional. O v2 passa a exigir o motivo em todas as opções.

## Verificação

O fluxo inteiro foi rodado no Chrome (Playwright), em 1280 px e 390 px, sem erros no console. Pular para a etapa 3 e tentar salvar fica bloqueado e leva de volta à etapa 1. A pergunta nova recebe o foco e pode ser preenchida. O link da divergência leva à etapa 3. Salvar sem nome não fecha o resumo, e com o nome mostra "Decisões salvas por Juliana".
