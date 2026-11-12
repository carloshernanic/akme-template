# Task 8: documentação, guia e verificador da demo

Esta tarefa põe os documentos de uso e os registros em dia com o exportador em Cypher (Tasks 1 a 7). O único código alterado é o verificador da demo, `examples/local_demo/verificar_neo4j.py`. Nenhum código do produto mudou.

## Para que serve cada documento e o que mudou

| Arquivo | Para que serve | Antes | Agora |
|---|---|---|---|
| `reports/docs_exp_neo4j/README.md` | Guia de uso, do primeiro uso até ver o grafo | Passo de baixar e conferir o plugin n10s; `docker run` com volume de plugins e variável que liberava as rotinas do plugin; conferência pela contagem de rotinas do plugin; glossário com RDF e n10s; dry-run gerava `neo4j.nt`; linhas apagadas continuavam no grafo; teto de 100 mil linhas | Sem plugin: Parte 1 com 4 passos (1.1 a 1.4); `docker run` só com porta, senha e volume de dados; conferência pela versão do Neo4j; glossário com Cypher, Conceito e sincronização; dry-run gera `neo4j.cypher`; nova seção 3.3 sobre sincronização; saída real da CLI antes de confirmar; consultas com `Conceito`; recusa do banco antigo com o comando de limpeza; limites novos |
| `docs/neo4j/exportacao.md` | Estado atual da exportação, com fluxo, modelo, casos e motivos | Situação de 05/11/2026 com n10s; fluxo RDF → plugin; provas do n10s | Situação de 12/11/2026 em Cypher; fluxo plano → confirmação → carga → sincronização → conferência; modelo no grafo, nomes do esquema `akme_*`, tabela de casos nova; nota curta "Antes (n10s)" apontando para o histórico; seção "Provas" com "a preencher na Task 9" |
| `docs/neo4j/historico.md` | Registro cronológico | Terminava no caminho com n10s | Entrada nova de 11/11/2026 a 12/11/2026, no topo, com o que mudou, o motivo (relações como nós no `onto.import`, teto de 100 mil linhas, n10s ausente no Aura, pedido do colega), a decisão e os links para estas páginas (o desenho original não é linkado, por decisão de Mateus). As entradas antigas não mudaram |
| `SKILL.md` (etapa 5, item 2) | Instrução do agente para o alvo `neo4j` | RDF em `neo4j.nt`, carregado pelo n10s; executar exigia o plugin | Cypher puro em `docs/publish/neo4j.cypher`, sem plugin; ontologia como `Conceito`; cada carga sincroniza; carga continua só pelo humano, na CLI |
| `CLAUDE.md` e `AGENTS.md` (Cuidados) | Instrução do projeto para agentes | "o akme gera RDF e o plugin n10s carrega" | "o akme grava em Cypher puro, sem plugin (dry-run em `docs/publish/neo4j.cypher`), e cada carga sincroniza"; o resto do item e o link para o guia ficaram iguais |
| `.gitignore` | Arquivos fora do Git | `.neo4j/`, comentado como pasta do plugin n10s | `.neo4j/` mantido, com o comentário "pasta do plugin da exportação antiga; não é mais usada" (motivo abaixo) |
| `examples/local_demo/verificar_neo4j.py` | Conferência só de leitura da demo contra os CSVs e o gabarito | Checava `Resource`, `Class`, `SCO`, `n10s_unique_uri` e nomes de aresta em maiúsculas; consulta vazia dava `IndexError` | Checa o modelo novo (seção seguinte); consulta sem resultado vira linha `FALHA` |
| `docs/exportacao-neo4j/index.md` e `mkdocs.yml` | Estas páginas | Task 8 "a fazer" | Task 8 "em revisão"; esta página no menu |

**Por que o `.neo4j/` continua no `.gitignore`:** nenhum código usa a pasta, mas ela ainda existe em máquinas que seguiram o guia antigo, com o jar do plugin (12,8 MB). Tirar a linha faria esse jar aparecer como arquivo novo no `git status`, com risco de ir num commit. O guia, em "Recomeçar do zero", diz que a pasta pode ser apagada.

`tests/test_skill_text.py` e `tests/test_docs_page.py` não citam n10s nem o texto alterado; não precisaram de ajuste. `docs/neo4j/teste-n10s.md` e `docs/neo4j/teste-n10s/` são registros históricos e não mudaram.

## Como o guia manteve a estrutura didática

O autor tinha acabado de deixar o guia pensado para quem nunca usou Neo4j (commit `afcef25`). Mudou só o conteúdo; a forma ficou:

- **"Antes de começar"** e a tabela de termos continuam. Saíram RDF e n10s; entraram Cypher, Conceito (camada da ontologia) e sincronização. Dry-run continua.
- **O diagrama do fluxo** continua, com "carga: você confirma, o akme grava em Cypher e confere o banco".
- **A lista de conferência da Parte 1** foi renumerada: 1.1 ferramentas, 1.2 driver, 1.3 `.env`, 1.4 subir o Neo4j e conferir. As referências a "passo 1.5" viraram "passo 1.4".
- **Cada comando com a saída esperada:** a conferência do Neo4j passou a ser a versão do servidor (`"2026.10.1"`), testada no banco descartável. A limpeza diz que não mostra nada quando dá certo e como conferir (`count(n)` igual a `0`).
- **A Parte 3** ganhou a saída real da CLI antes de confirmar, com "como ler" cada linha, e a seção 3.3 sobre sincronização: o que é apagado e as três regras de segurança (só este projeto; só depois de tudo gravado; só se a origem não mudou no meio). "Banco com outro projeto" virou 3.4.
- **"Problemas comuns"** ganhou a recusa do banco antigo, com a mensagem exata da CLI, e uma subseção "Banco da exportação antiga" com o comando de limpeza do brief. Também entraram as mensagens de lote que falhou, origem que mudou e divergência. Saiu a linha do plugin ausente.
- **"Limites conhecidos":** sem teto de linhas; memória do driver com texto acentuado; duas cargas no mesmo segundo dividem a `_carga`; a sincronização percorre todos os nós (sem índice em `_projeto`); dinheiro como `FLOAT`. Saiu "linhas apagadas continuam no grafo", que a sincronização resolve.

## O verificador da demo

`examples/local_demo/verificar_neo4j.py` continua com o mesmo uso (variáveis `AKME_NEO4J_*` no ambiente, código de saída 1 se algo falhar) e só lê o banco. Sem as variáveis, diz quais faltam e sai com 2. As checagens:

- **Modelo:** a marca `local_demo`; nós por label iguais ao gabarito; cada nó de dado com um label só; nenhum nó fora do projeto; arestas de dado por tipo, com o nome das relações (`contem`, `pertenceA`, `referencia`); cada relação contada pelo padrão `(:Dominio)-[:relacao]->(:Alcance)`; nenhuma aresta entre dados e `Conceito`.
- **Sincronização:** uma só `_carga` nos nós do projeto, e as arestas com a mesma.
- **Ontologia:** os 9 `Conceito` (um por classe do `schema.ttl` da demo), os 5 `SUBCLASSE_DE`, as 3 setas com o nome das relações e a definição de `Pedido`.
- **Esquema:** as restrições `akme_uniq_<Label>` e `akme_conceito_uniq_projeto_nome`; nenhuma restrição fora do `akme_*` (a do n10s, por exemplo); um índice `akme_idx_*` ONLINE em cada coluna-alvo de join.
- **Valores:** as 216 células dos CSVs, sem propriedade a mais além de `_id`, `_projeto` e `_carga`; chave e `_id` únicos por label; pares de cada relação; medidas, armadilha de fan-out e consultas de negócio do gabarito; tipos gravados (`DATE`, `INTEGER`, `FLOAT`, `STRING`).
- **Impressão digital:** do conteúdo sem `_carga`, que muda a cada carga, e das identidades internas.

Erros de conexão (`AuthError`, `ServiceUnavailable`) viram uma linha curta em português, sem credenciais, com saída 1; o verificador confere a conexão antes (`verify_connectivity`), para não esperar as novas tentativas do driver. Cada checagem recebe uma função; se uma consulta que precisa de linha não devolve nenhuma, a função levanta `SemResultado` e a checagem vira `FALHA` com a consulta, em vez de `IndexError`.

### Execução real, em 12/11/2026

Neo4j 2026.10.1 descartável, sem plugins, na porta 27687. Projeto temporário em `/tmp`, montado como os testes montam (ontologia do template no `git HEAD`, cópia de `examples/local_demo`), com `akme init --demo` e `akme demo`, que aplica as decisões `add_source` do `seed_edits.yml`. O banco foi limpo antes (nós, restrições e índices).

Carga, com `echo y |` (saída aparada: o JSON do resultado sai em várias linhas e aqui ficaram só os campos principais):

```text
destino: bolt://127.0.0.1:27687
linhas: 43 em 7 lote(s) de dados, mais a ontologia
nos previstos:
  Cliente: 8
  ItemPedido: 17
  Pedido: 10
  Produto: 8
arestas previstas:
  contem: 17
  pertenceA: 10
  referencia: 17
no banco hoje, deste projeto:
  Cliente: banco 0 -> origem 8
  ItemPedido: banco 0 -> origem 17
  Pedido: banco 0 -> origem 10
  Produto: banco 0 -> origem 8
avisos:
  a carga apaga deste projeto o que nao vier da origem nesta carga
banco: vazio
Executar no alvo neo4j? Esta acao altera a plataforma do cliente. [y/N]: {
  "executed": 7,
  "carga": "2026-11-12T15:30:13+00:00",
  "removed": {"nodes": 0, "relationships": 0},
  "verification": {"ok": true, "divergences": []}
  ...
}
```

Verificador, depois da carga:

```text
OK    marca do projeto
OK    nos por label
OK    cada no de dado com um label so
OK    nenhum no fora do projeto
OK    arestas de dado por tipo (nome da relacao)
OK    arestas (:Pedido)-[:contem]->(:ItemPedido)
OK    arestas (:Pedido)-[:pertenceA]->(:Cliente)
OK    arestas (:ItemPedido)-[:referencia]->(:Produto)
OK    nenhuma aresta entre dados e Conceito
OK    uma so _carga nos nos do projeto
OK    arestas com a mesma _carga dos nos
OK    conceitos (um por classe do schema.ttl)
OK    SUBCLASSE_DE da ontologia
OK    setas da ontologia com o nome das relacoes
OK    definicao de Pedido no grafo
OK    restricoes akme_*
OK    nenhuma restricao da exportacao antiga
OK    indice ONLINE em cada coluna-alvo de join
OK    valores de Cliente (8 linhas)
OK    sem propriedade extra em Cliente
OK    chave unica em Cliente
OK    _id unico em Cliente
OK    valores de ItemPedido (17 linhas)
OK    sem propriedade extra em ItemPedido
OK    chave unica em ItemPedido
OK    _id unico em ItemPedido
OK    valores de Pedido (10 linhas)
OK    sem propriedade extra em Pedido
OK    chave unica em Pedido
OK    _id unico em Pedido
OK    valores de Produto (8 linhas)
OK    sem propriedade extra em Produto
OK    chave unica em Produto
OK    _id unico em Produto
     celulas comparadas: 216
OK    pares de pertenceA
OK    pares de contem
OK    pares de referencia
OK    cada pedido com 1 cliente
OK    clientes sem pedido
OK    soma de qt_itens
OK    faturamento
OK    vl_total sem filtro
OK    erro de fan-out reproduzido
OK    produtos do pedido 1001
OK    tipos gravados
IMPRESSAO DIGITAL {"conteudo_arestas": "501e677bc15ba148", "conteudo_nos": "9cec529c012257fd", "identidades_arestas": "13cbf45f0832abfd", "identidades_nos": "dcd9563575d8a635"}
RESULTADO: todas as verificacoes passaram
```

45 de 45, código de saída 0.

Outras rodadas no mesmo banco:

| Rodada | Resultado |
|---|---|
| Segunda carga, sem mudar nada | CLI mostrou `banco 8 -> origem 8` (e assim por diante) e `banco: projeto local_demo, sera atualizado`; `removed` 0 e 0; `verification.ok`; verificador 45 de 45 com a **mesma impressão digital, inclusive as identidades** (o `MERGE` atualizou os mesmos nós) |
| Banco esvaziado (só os nós), verificador rodado | 34 `FALHA`, nenhuma exceção, código de saída 1; por exemplo `FALHA definicao de Pedido no grafo` / `consulta sem resultado: MATCH (c:Conceito {nome: 'Pedido'}) RETURN c.definicao AS c` |
| Banco legado simulado (restrição `n10s_unique_uri`, um nó `Resource` e um `_GraphConfig`) | CLI: `banco: banco da exportacao antiga (n10s)` e `erro: banco carregado pela exportacao antiga (n10s); limpe-o com o comando do guia. Nada foi gravado`; saída 1; os 2 nós continuaram no banco |
| Comando de limpeza do guia (`docker exec ... cypher-shell`), depois carga e verificador | Limpeza sem saída; carga com `verification.ok`; verificador 45 de 45. Conteúdo com a mesma impressão; identidades novas, como esperado ao recriar os nós |

Nenhuma saída mostrou a senha.

## Busca final

`git grep -n -i "n10s\|neosemantics\|neo4j\.nt"` só encontra:

- registros históricos: `docs/neo4j/historico.md`, `docs/neo4j/teste-n10s.md`, `docs/neo4j/teste-n10s/*`;
- a detecção de banco legado: `akme/tools/neo4j_load.py` e os testes em `tests/`;
- estas páginas (`docs/exportacao-neo4j/*`) e o título da Task 7 no `mkdocs.yml`;
- o guia: a linha da recusa em "Problemas comuns" e o comando de limpeza da subseção "Banco da exportação antiga";
- a nota "Antes (n10s)" do `docs/neo4j/exportacao.md`.

## Testes

- `uv run pytest -q`: 321 passaram, 10 foram pulados e 1 falhou, a já conhecida `test_optional_adapters_fail_clearly` (5 min 21 s).
- `uv run --extra docs mkdocs build --strict`: sem avisos.

## Revisão

Revisão aprovada, sem críticos nem importantes. O revisor conferiu comandos, variáveis, nomes de restrições e índices e mensagens do guia contra o código (`neo4j_load.py`, `cli.py`).

Corrigido nesta rodada:

- **Links ao desenho original:** trocados pelas páginas do MkDocs em `docs/neo4j/exportacao.md`, `docs/neo4j/historico.md` e `index.md`, por decisão de Mateus (o desenho e o plano ficam fora do repositório).
- **Sincronização no guia:** célula esvaziada saiu da lista do que a sincronização apaga (some na gravação do nó, pelo `SET n = r.p`); a regra 2 diz "nenhum nó ou aresta é apagado".
- **Pasta `.neo4j/`:** quem apagar a pasta recria o contêiner (`docker rm -f akme-neo4j` e o passo 1.4); o volume de dados continua.
- **`verification`:** o guia diz que o `ok` dentro de `verification` deve ser `true` (a CLI imprime o JSON em várias linhas); o bloco da execução real aqui está marcado como aparado.
- **Edição do Neo4j:** `exportacao.md` diz "testado no Neo4j 2026.10.1 Community; sem plugin, não depende da edição (Aura e Enterprise não testados)".
- **Escopo da remoção de arestas:** "arestas com `_carga` antiga que saem de nós do projeto".
- **Problemas comuns:** linhas novas para `sincronizacao falhou: ...`, `ontologia: comando N de M falhou: ...` e `o banco tem mais de um projeto do akme: ...`, com o texto do código.
- **Verificador:** erro de conexão ou de senha vira mensagem curta, sem credenciais. Rodado de novo no banco descartável: 45 de 45, saída 0; com senha errada e com porta sem serviço, uma linha e saída 1.

Não verificado pelo revisor: o `cypher-shell` com dois comandos na mesma chamada e a imagem `neo4j:2026.10.1` sem plugin. Os dois foram rodados só na execução desta tarefa (seção acima).
