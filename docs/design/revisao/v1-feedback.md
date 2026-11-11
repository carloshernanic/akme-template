# Revisão de design: protótipo v1

Protótipo: `v1-prototipo.html` (10/11/2026). Ele tem três etapas:

1. Caso de uso: escolher entre as propostas da IA ou escrever o próprio.
2. Perguntas de competência: layout de 30/out, com cards e a coluna de decisão.
3. Lacunas e divergências.

Método: três usuários simulados, cada um rodando o protótipo no Chrome (Playwright) em 1280 px e 390 px.

| Persona | Perfil | Clareza | Facilidade/Eficiência | Confiança |
|---|---|---|---|---|
| Rafael (leigo) | estagiário apressado, nunca ouviu falar de ontologia | 2 | 3 ("é fácil terminar, e esse é o problema") | 1 |
| Juliana (média) | consultora, conhece o negócio, assina a aprovação | 3 | 3 | 2 |
| Marcos (especialista) | engenheiro de ontologias, LOT/NeOn, exigente com UX | 3 | 2 (rigor do método: 2) | 1 |

## O que funcionou

- O layout de card com coluna de decisão é legível e lembra um PR review (Marcos).
- A evidência com caminho e trecho foi elogiada e chegou a ajudar uma decisão: a Juliana rejeitou a CQ-002 porque o glossário falava em 180 dias e não em 90.
- "Falta: ..." no card e no rodapé deixa claro o que é obrigatório.

## Defeitos, por gravidade

O número entre parênteses diz quantas personas encontraram o defeito.

### Alta

1. **Salvar ignora as etapas anteriores (3/3).** Pelo stepper dá para pular direto para a etapa 3, e o "Salvar decisões" fica liberado com perguntas sem decisão e até sem nenhum caso de uso. A etapa 3 ainda aparece com ✓. Causa: `next.disabled` só olha a etapa atual.
2. **"+ Nova pergunta" não deixa escrever (3/3).** O card criado não tem campo de texto, tipo, conceitos nem caso de uso. Ele aparece como "proposta pela IA" e mesmo assim pode ser aceito. O Rafael criou um sem querer, achando que era o botão de seguir, e aceitou para destravar.
3. **Proveniência e aprovador (2/3).** A página não pede nem mostra o nome de quem aprova e não exibe um resumo do que vai ser registrado. A pergunta escrita pelo revisor sai rotulada como da IA, e as aplicadas não mostram quem aprovou nem o motivo.
4. **Decisões pré-preenchidas pela IA (3/3).** O UC-01 vem marcado, e com isso o rodapé já diz "✓ Tudo preenchido". A CQ-001 vem com prioridade Alta. Nos dois casos, a pessoa aprova sem ter escolhido.
5. **Caso de uso sem efeito nas perguntas (2/3).** Todas as perguntas ficam ligadas ao UC-01. Desmarcar o UC-01 não muda nada, e um caso escrito pela pessoa nunca aparece nas perguntas. O vínculo aparece só como o código "UC-01", sem o nome.
6. **Perguntas e divergências sem ligação (3/3).** A CQ-002 ("clientes ativos") depende da divergência D-01 ("cliente ativo"), mas a página não mostra isso. Quem decide a pergunta faz isso antes de ver a divergência.
7. **Etapa 3 incompleta em relação ao método (1/3, Marcos).** "Em aberto" sem motivo conta como decidida e vira a saída mais fácil (o Rafael usou nas duas). Faltam ainda:
   - "Consultar especialista" e a precedência sugerida por fonte, na divergência;
   - "Distintos" não pede os dois nomes;
   - "Reformular" não deixa escrever a nova pergunta;
   - a lacuna não aponta para a pergunta de onde veio.
8. **Teclado e leitor de tela (1/3, Marcos).**
   - Os cards de caso de uso e o "+ Nova pergunta" são `div`s fora da ordem do Tab.
   - O foco volta para o topo a cada clique, porque cada clique recria o HTML.
   - Faltam `aria-pressed`, `<label>` e `aria-live`.

### Média

9. **Termos sem explicação (3/3).** "competência", "Construção/Teste", "Distintos", "Reformular", "lacuna", "divergência" e os tipos de pergunta. O Rafael marcou tudo como Construção só para fugir do campo "resposta esperada".
10. **"Resposta esperada" vaga (2/3).** Não diz o formato e não tem fonte. A Juliana não tinha o dado e escreveu um número qualquer.
11. **Estado e contadores errados (2/3).**
    - "Falta: motivo" continua no card enquanto a pessoa digita.
    - O stepper conta o caso próprio vazio como escolhido.
    - Ao trocar a decisão, a resposta e o motivo antigos continuam guardados.
12. **Layout da etapa 3 em desktop (2/3).** "Em aberto" estoura o controle segmentado, e "Pedir ao cliente" quebra em três linhas.
13. **Celular, 390 px (3/3).** O rodapé fixo ocupa 22% da tela e cobre campos. "Falta" quebra palavra por palavra, e o stepper ocupa 104 px.
14. **Escala (1/3, Marcos).** Com 11 perguntas, o contador "Pendentes" não diminui conforme se decide. Não há filtro, ordenação, ação em lote nem "próxima pendente". Os ids saem como "CQ-0010".
15. **Contraste das bordas dos controles (1/3).** Ficam em 1,84:1, abaixo dos 3:1 que o WCAG 1.4.11 pede.
16. **CQ só tem aceitar ou rejeitar (1/3).** Não dá para editar o texto ou o tipo.

### Baixa

17. **Botão de avançar desabilitado sem retorno.** Clicar nele não diz por que está desabilitado.
18. **Botões e links mortos.** "Propor alteração", "Fontes lidas" e os links de evidência não fazem nada.
19. **Vocabulário inconsistente.** "Guardar para o teste" nas aplicadas e "Teste" no seletor.

## Decisões erradas que o design induziu (Rafael)

- Aprovou o UC-01 sem olhar os outros casos.
- Aceitou a CQ-002 com "cliente ativo" ainda em disputa.
- Mandou tudo para Construção para não ter que escrever a resposta esperada.
- Aceitou uma pergunta vazia que criou sem querer.
- Salvou com lacuna e divergência "Em aberto" sem motivo.

## O que faltou para decidir com segurança (Juliana)

- Nome de quem aprova e um resumo final antes de salvar.
- Abrir a fonte por trás da evidência.
- Uma linha explicando Construção/Teste e cada opção da etapa 3.
- Saber o que acontece depois de "Pedir ao cliente" ou de "Em aberto".
- Ver quais perguntas dependem de qual divergência.

## Ressalva

Parte dos defeitos é do protótipo e não do design. Os botões mortos, os ids "CQ-0010" e a falta de "consultar especialista" (que o código real em `akme/static/review.js` já tem) são exemplos. Mesmo assim, ficam listados para não voltarem no v2.
