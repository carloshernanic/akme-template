# Correções de 13/11/2026: primeira impressão no Browser e aba Exportar

Depois do teste de ponta a ponta com os dados do capstone, Mateus abriu o Neo4j Browser e viu "um monte de entidade solta". Esta página registra a auditoria daquele grafo, o que foi corrigido em 13/11/2026 e o que ficou aberto. As anotações de trabalho estão em `anotacoes_mateus/correcoes-exportacao.md`.

## O que a auditoria achou

O grafo do capstone tinha 392 nós e 492 arestas; 332 nós eram de dado. As contagens e os valores batiam com a origem (zero divergência), mas a primeira impressão era ruim por três motivos:

1. **O grafo é de fato desconectado.** Os 332 nós de dado formam 49 pedaços: quem faz o Capstone (210 nós), como se avalia (65), calendário (21, em 11 pedaços) e 36 nós sem aresta nenhuma. Nada no dry-run avisava.
2. **A visão boa era opcional e não abriu.** O tutorial dependia do `akme review` ligado, de um comando digitado e de uma linha no `.env` que ninguém sabia que faltava. Sem ele, os atalhos do Browser mostram amostras de 25 pares soltos.
3. **As bolinhas eram ilegíveis.** A legenda pegava a primeira coluna mapeada (por exemplo, `Projeto.tipo`, preenchida em 1 de 31 linhas) e não havia cor fixa por classe.

Das 18 perguntas de competência do capstone, o grafo responde 9 por inteiro, 2 em parte, 4 só pelo texto das regras e 3 não responde (faltam fatos por estudante).

## O que foi corrigido

### Nomes reservados recusados cedo

Uma classe chamada `Conceito` só era recusada na carga, depois de toda a ontologia pronta. Agora o `propose_edit` recusa na hora, com a sugestão de nome, e o `validate` avisa em ontologias antigas:

| Tipo | Nomes reservados |
|---|---|
| Classe | `Conceito`, `Termo`, `_AkmeProjeto` |
| Relação | `RELACAO_ONTOLOGIA`, `SUBCLASSE_DE`, `TEM_TERMO` |
| Coluna | `_id`, `_projeto`, `_carga`, `_descricao` |

A lista vive em um lugar só, `akme/tools/neo4j_values.py` (`reserved_problem`).

### Legenda dos nós decidida na etapa 5

O `add_source` ganhou o campo opcional `caption`: a coluna cujo valor aparece na bolinha. Sem decisão, a regra automática é:

1. coluna de texto com cara de nome (`nome`, `titulo`, `descricao`...), que não seja identificador nem coluna de junção, preenchida em 90% das linhas ou mais: a legenda é só o valor;
2. senão, a primeira coluna mapeada preenchida em 50% ou mais completa "Classe chave";
3. senão, "Classe chave".

A página de revisão mostra a legenda escolhida, um exemplo real e alerta quando a coluna está preenchida em menos da metade das linhas. No capstone, `Projeto` passou de "Projeto P01" para o título do projeto e `Estudante` para o nome completo.

### Camada `Conceito` sem as classes de base

`Entity`, `Metric`, `Relation` e `Rule` são classes internas do akme e deixaram de virar `Conceito` (no capstone, de 28 para 24). Cada `Conceito` ganhou `tipo` (entidade, métrica, relação ou regra) e `publicada_nos_dados` passou a valer também para métricas. A conferência depois da carga conta os mesmos conceitos que a carga grava.

### Esquema para o LLM

`docs/publish/neo4j_schema.md` passou a dizer qual coluna é a legenda de cada label, a marcar colunas de junção ("repete o que a aresta já diz; siga a aresta"), a listar os conceitos sem dado no grafo e a identificar cada regra pelo termo.

### Tutorial do Browser abre pelo desenho

O tutorial passou de seis para cinco páginas:

1. **O que tem aqui:** primeiro o mapa das classes; em grafo pequeno (até 500 registros), o grafo inteiro numa consulta; depois as contagens, com "(sem ligações)" nas classes soltas.
2. **A ontologia:** o mapa dos conceitos e a consulta dos conceitos sem dado.
3. **Explorar:** o registro mais ligado de cada classe (antes era um registro qualquer, que podia vir vazio).
4. **Como navegar.**
5. **Perguntas em português.**

O publish também gera `docs/publish/neo4j_estilo.grass`: uma cor fixa por classe, a camada de ontologia em cinza, o nome na bolinha e o nome da relação nas setas `RELACAO_ONTOLOGIA`. O Browser 2026.10 só importa cor, tamanho, legenda e espessura da seta, e o arquivo usa só isso. Importa-se por `:style`, **Upload GraSS styles**, **Import**. Tudo foi conferido num Browser de verdade, por automação, contra um Neo4j descartável com os dados do capstone.

As perguntas de competência continuam fora do tutorial (decisão de 12/11).

### Aba "Exportar" na página local

O `:guide` não abriu no primeiro teste porque o Browser rodava na porta 17474 e o `.env` não tinha `AKME_NEO4J_BROWSER_URL`; o Browser bloqueia a resposta sem mostrar erro. Em vez de mais um passo de manual, a página local ganhou a aba **Exportar**, com quatro passos:

1. **Banco.** Diz o que falta no `.env`, mostra as linhas para colar e o comando do Docker que cria o banco. **Conferir de novo** relê o `.env` sem reiniciar o servidor. Senha com menos de 8 caracteres é recusada antes de qualquer comando (o Neo4j cria o contêiner e desliga). Quando nada responde no endereço, a página olha o contêiner `akme-neo4j` e diz se ele não existe, está parado, está ligando ou morreu por senha curta, com os comandos de cada caso.
2. **O que vai para o grafo.** O resumo do dry-run: registros, ligações, avisos, problemas que bloqueiam e classes sem ligação. O detalhe por classe fica recolhido.
3. **Carregar.** O botão só libera depois de marcar "Entendi que a carga altera o banco e não tem como desfazer". Remoção de mais de 20% de uma classe pede o número digitado. As recusas são as mesmas da CLI.
4. **Ver o grafo.** O link do Browser, o usuário e a senha para entrar e o comando do tutorial para copiar. Se o Browser não responde no endereço esperado, a página avisa e mostra a linha do `.env`.

**APOC e console da Aura no mesmo caminho.** O comando do Docker que a página mostra já cria o banco com o APOC (`NEO4J_PLUGINS='["apoc"]'`), exigido pelo gerador de Cypher do console da Aura. No passo 4, o item opcional "Perguntas em português, pelo console da Aura" diz se o banco tem o plugin, dá o comando que recria o contêiner com ele sem perder o grafo e mostra endereço, usuário e senha para a conexão rápida do console. Conferido num Neo4j descartável: o contêiner sobe com a linha e `apoc.meta.schema` responde. O gerador em si continua não testado pelo akme.

**Regra que mudou, com aval de Mateus:** a carga continua só do humano, mas agora pelo botão da página ou pela CLI. O agente não tem tool para ela, e o `SKILL.md` o proíbe de chamar a rota. A rota `POST /api/neo4j/carga` recusa pedido que não venha da própria página (sem `Origin` ou de outra origem) e só aceita uma carga por vez. A senha nunca passa pela página: da senha, o servidor só diz se está preenchida e se tem tamanho suficiente.

**Sem Docker: Neo4j Desktop.** O passo 1 abre com a escolha entre **Docker** e **Neo4j Desktop** (lembrada no navegador); com o Desktop, as instruções são criar a instância em **Instances** › **Create**, esperar **RUNNING** e colar as mesmas linhas no `.env`, e os erros falam da instância em vez do contêiner. O passo 4 tem um roteiro por caminho, com a mesma escolha (trocável ali, em **Ver pelo**): Browser com login e `:guide`; Desktop com **Query**, `CALL db.schema.visualization()` e uma consulta de registros, e o tutorial do Browser recolhido como opcional. Testado por Mateus em 13/11/2026 com o Desktop (instância 2026.10.2): conexão, carga e consulta, sem mudar o servidor.

Código: `akme/tools/neo4j_page.py` (estado e carga), rotas `GET /api/neo4j` e `POST /api/neo4j/carga` em `akme/review_server.py`, tela em `akme/static/exportar.js`.

## Verificação

- Suíte sem banco: 524 testes passam, 30 pulados.
- Integração com Neo4j descartável: 27 passam, 1 pulado, rodada depois das mudanças do tutorial; não foi repetida depois da aba Exportar.
- Aba Exportar no navegador: caminho completo (sem `.env`, pronto, carga pelo botão, depois da carga) contra um Neo4j descartável; os estados do passo Banco e o desenho final, com respostas simuladas do servidor.
- O teste de primeira vez feito por Mateus pegou a senha curta e a ordem errada das hipóteses; as duas coisas foram corrigidas.

## Revisão de código antes do commit

Uma revisão automática do diff apontou nove pontos no código, todos corrigidos e com teste:

- **A carga pelo botão vale só para a prévia que a pessoa viu.** O estado devolve uma marca (destino, contagens da origem e do banco); a carga recusa se a origem, o banco ou o `.env` mudaram depois, e pede para conferir de novo.
- **Erro depois que a gravação começou não diz mais "a carga não foi feita".** A tela avisa que o banco pode ter mudado e manda conferir.
- **A conferência não desfaz o tutorial da carga.** Com o banco carregado, o tutorial volta à forma que aquele banco aceita (com ou sem APOC).
- **A conferência é só da própria página** (pedido vindo de outro site é recusado), roda uma por vez e espera a carga terminar.
- **Senha com caractere especial** (`$`, espaço, aspas, `#`, `&`, `!`) é recusada: o comando do Docker lê a senha pelo terminal, que a interpretaria de outro jeito, e o banco nasceria com outra senha.
- **Legenda automática precisa distinguir os registros.** Coluna com cara de nome que repete demais (cidade do cliente, categoria do produto) não vira legenda sozinha; a leitura mede os valores distintos com memória limitada (2.000 por coluna).
- **Legenda só com espaços** cai em "Classe chave" em vez de bolinha em branco.
- **Classe de base usada por uma relação** continua virando `Conceito`, para a seta não sumir.
- **Exemplo de legenda na revisão** não mistura mais valores de linhas diferentes.

## Corrigir o que já foi aplicado

No Olist (11/11), um termo foi mapeado para a tabela errada e a tabela de produtos virou duas classes; o agente não tinha como corrigir. No capstone (13/11), trocar o nome da classe `Conceito` exigiu editar arquivos à mão. Três tipos de edição resolvem isso, pela mesma revisão e aprovação humana de qualquer outra proposta, com registro no `changelog.yml` do antes e do depois:

| Tipo | O que faz | Campos |
|---|---|---|
| `update_mapping` | Troca um mapping aplicado | `term`, `source` e `column` de hoje, mais `set` com o que muda (`term`, `source`, `column`, `role`, `expression`, `note`) |
| `remove_mapping` | Apaga um mapping aplicado | `term`, `source`, `column` e `reason` |
| `rename_class` | Troca o nome de uma classe | `name`, `new_name` e, se quiser, `label` |

- **A correção vale para o mapping que a pessoa viu.** A proposta guarda o mapping de antes; se ele mudar até a aprovação, a aplicação recusa e pede uma proposta nova.
- **As recusas do `add_mapping` continuam valendo** no resultado: coluna com nome reservado, métrica sem expressão SQL, mapping repetido, termo que não existe.
- **`rename_class` troca o nome em tudo que cita a classe:** `schema.ttl` (inclusive subclasses, domínio e alcance de relações), termos, contratos de relação, conceitos das perguntas de competência e propostas pendentes. As classes de base do akme e os nomes reservados do Neo4j são recusados.
- **O `validate` avisa antes da etapa 5** (`source_classes`) quando uma tabela recebe termos de mais de uma classe, dizendo quais termos puxam cada classe. Antes, isso só aparecia como problema do plano de carga.
- **No Neo4j, a correção chega na carga seguinte:** ela sincroniza o banco com a origem, então nós e propriedades do nome antigo saem.

## Definição em cada nó, por padrão

Navegando o grafo do capstone, a definição aparecia ao clicar num `Termo`, mas não ao clicar num registro (`EventoCalendario`, `Projeto`): ela fica no `Conceito` de mesmo nome. A opção `descricao_nos_dados`, que grava `_descricao` em cada nó e aresta de dado, passou a vir **ligada por padrão** (decisão de Mateus, 13/11). Quem tem uma base grande desliga com `neo4j: {descricao_nos_dados: false}` no `akme.yml`: no Olist, a opção ligada custou 14% de disco numa base nova. Vale a partir da próxima carga.

## O que ficou aberto

- **Grafo desconectado sem aviso próprio.** A aba Exportar já lista as classes sem ligação; falta contar pedaços e nós isolados no dry-run e pôr a regra na etapa 3 do `SKILL.md`.
- **Renomear relação** (`rename_relation`) não existe; por enquanto só classe.
- **Perguntas de competência em Cypher** como teste depois da carga, e a decisão de voltar com elas como consultas salvas.
- **Tutorial abrir sozinho.** Depende de o contêiner ter sido criado pelo comando da página (que já inclui a linha).
- **Refazer o teste do Olist** e testar o gerador de Cypher do console da Aura.
- No capstone: `ProfessorOrientador` é subclasse de `Avaliador`, mas os nós `Avaliador` são papéis; `Projeto.slide` é proveniência da transcrição, não dado; o projeto ainda se chama `akme-template`.
