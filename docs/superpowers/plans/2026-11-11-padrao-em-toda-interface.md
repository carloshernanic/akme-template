# Caso de uso primeiro e padrao novo em toda a interface: plano

Data: 11/11/2026. Branch: `design-perguntas-competencia`, com a `main` (conversa na pagina, modo automatico) ja juntada.

## Por que

No teste real (`examples/demo_nova`), o agente perguntou o caso de uso no chat, aplicou e so depois abriu a pagina. O revisor nunca viu a escolha nem a criacao de caso de uso, e a pagina abriu na caixa antiga, so com o glossario. O usuario pediu:

- a escolha e a criacao do caso de uso vem antes de tudo, na pagina, que abre na hora;
- o padrao das telas novas vale para a interface inteira.

## Regras que valem para todas as tarefas

- Pagina em HTML/CSS/JS puro em `akme/static/`; `docs/` e copia do `akme export`.
- API do servidor (`/api/review`, `/api/propose`, `/api/apply`) nao muda. O SKILL muda so na tarefa 2.
- Texto ao usuario em portugues com acento; codigo e comentarios sem acento.
- Padrao: card enxuto (titulo, linha de fonte, "ver detalhes", botoes grandes), item decidido vira linha com "rever", etiqueta "obrigatorio" e "Falta: ...", criar algo sempre em janela central com fundo desfocado, um botao cheio por area, nome pedido so ao salvar.
- Cada tarefa termina com: testes da pagina, teste no navegador (claro, escuro, celular), revisao do diff, resumo ao usuario e parada para aprovacao. Commit so com aval.

## Tarefas

1. **Tela 1 salva sozinha.** A etapa 1 mostra so as telas que tem algo a decidir. Quando so ha casos de uso pendentes (a primeira rodada), a tela 1 ja tem "Conferir e salvar". A aba abre na Etapa 1 enquanto a etapa 1 nao fecha. O contador do seletor diminui conforme o revisor decide. No modo automatico a etapa 1 so mostra, sem botoes de decisao.
2. **SKILL em duas rodadas.** Passo 1.1: o agente le as fontes, propoe de 2 a 3 casos de uso (`add_use_case`, com evidencia) e chama `open_review` na hora; o humano escolhe ou escreve o dele na tela 1. Depois do `applied`, o agente propoe proposito, escopo, usuarios, CQs (com `use_cases` dos casos escolhidos), lacunas e divergencias e abre a pagina de novo (telas 2 e 3). `tests/test_skill_text.py` continua passando.
3. **Glossario no padrao novo.** As siglas pendentes viram uma tela da etapa 1 ("Glossario"), com linhas de sigla e significado, aceitar, ajustar ou rejeitar.
4. **Base comum.** Textos com acento e em portugues (graph.js, review.js), aviso de requisitos sem ids crus, um estilo de titulo de secao, um formato de tela vazia, regra de botoes, painel da conversa no mesmo padrao.
5. **Aba Ontologia.** Numeros numa linha, controles do grafo com a mesma altura, painel de detalhes e lista de perguntas no padrao.
6. **Outras propostas (etapas 2 a 5).** Classes, relacoes, termos, mappings, restricoes, precedencias e fontes no card enxuto, decidido vira linha, nome so ao salvar, sem a fila lateral antiga.
7. **Revisao final.** Revisor independente sobre o diff inteiro, suite completa, teste de ponta a ponta com um projeto novo pelo fluxo do agente.
