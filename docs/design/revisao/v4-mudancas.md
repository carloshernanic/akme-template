# Protótipo v4: o que mudou em relação ao v3

Arquivo: `v4-prototipo.html` (10/11/2026).

## Saiu o campo "Uso" (Construção/Teste)

O usuário achou o campo confuso e decidiu que a tela de revisão não precisa dele. Com isso:

- toda pergunta aceita, seja sugerida pela IA ou escrita pela pessoa, serve para construir a ontologia;
- aceitar pede só a prioridade, e sai também o campo "Resposta esperada";
- o resumo final mostra só quantas perguntas foram aceitas;
- as perguntas já aplicadas mostram só a prioridade.

## Impacto a levar para a implementação

No código, o status `reserved` em `content.yml` é o que separa uma pergunta de teste. Hoje é ele que alimenta `validation/` e o `akme eval`, e o `validate` exige resposta para essas perguntas. Tirar o campo da página não remove essa função. Falta decidir de onde viriam as perguntas de teste do eval: escritas direto em `validation/`, marcadas pelo agente na CLI ou não usadas.

## Verificação

O fluxo inteiro foi rodado no Chrome (Playwright), sem erros no console.
