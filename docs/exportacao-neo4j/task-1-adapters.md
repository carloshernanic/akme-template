# Task 1: leitura em blocos nos adapters e BOM

## O que mudou

Todos os adapters de tabela ganharam o método `iter_rows`, que lê uma fonte em blocos em vez de trazer tudo para a memória. O adapter de pasta local também passou a ler CSV com BOM sem sujar o nome da primeira coluna.

## Por que

O exportador novo precisa ler tabelas de centenas de milhares de linhas sem teto. Hoje só existe `read_sample`, que devolve uma lista inteira. Sem leitura em blocos, o plano e a carga das próximas tarefas teriam de guardar tudo em memória.

## A interface

```python
Adapter.iter_rows(self, source: str, batch: int = 5000) -> Iterator[list[dict[str, Any]]]
```

- Cada bloco tem até `batch` dicts, no mesmo formato de `read_sample` (célula vazia vira `None`, nomes de coluna iguais).
- Uma fonte vazia não gera nenhum bloco.
- O padrão da classe base levanta `AdapterError` ("o adapter X nao le em blocos").
- `SqlAdapter._iter_query(sql, batch, cursor=None)` executa a consulta, chama `fetchmany(batch)` até esvaziar e fecha o cursor no fim, mesmo se o consumidor parar cedo.

## Comportamento por adapter

| Adapter | Como lê |
|---------|---------|
| Pasta local (CSV) | `csv.reader` linha a linha, agrupando em blocos com `itertools.islice` |
| Pasta local (xlsx) | `openpyxl` em modo `read_only`, o mesmo laço de antes, sem o corte por `n` |
| Postgres | cursor nomeado (`conn.cursor(name="akme_iter")`), do lado do servidor, porque o cursor comum do psycopg traz tudo para a memória |
| Snowflake e Databricks | cursor comum com `fetchmany` |

O SQL é o mesmo do `read_sample`, sem `LIMIT`. Na pasta local, `read_sample` e `read_schema` agora usam o mesmo gerador interno (`_rows`), então os dois caminhos não divergem.

## A correção do BOM

O CSV do Olist começa com o byte order mark, e a primeira coluna aparecia como `﻿product_category_name`. O mapeamento por nome de coluna falhava sem aviso. O encoding padrão do `LocalFolderAdapter` passou de `utf-8` para `utf-8-sig`, que descarta o BOM quando existe e se comporta como `utf-8` quando não existe. Os dados da demo não têm BOM, então nada muda para eles.

## Como foi testado

Arquivo: `tests/test_adapters_iter_rows.py`.

| Teste | O que prova |
|-------|-------------|
| `test_local_csv_in_blocks_matches_read_sample` | blocos de 5 dão `[5, 5, 5, 2]` e, juntos, igualam o `read_sample` |
| `test_csv_with_bom_has_clean_first_column` | a primeira coluna vem como `id`, tanto em `read_sample` quanto em `iter_rows` |
| `test_empty_source_yields_no_block` | CSV só com cabeçalho não gera bloco |
| `test_base_adapter_iter_rows_raises` | o padrão da base levanta `AdapterError` |
| `test_xlsx_in_blocks` | xlsx com 3 linhas e `batch=2` dá `[2, 1]` (pula se faltar `openpyxl`) |
| `test_sql_iter_uses_fetchmany_until_empty` | `fetchmany` até esvaziar, formato dos dicts e cursor fechado |
| `test_postgres_uses_named_cursor` | cursor nomeado `akme_iter` e SQL sem `LIMIT` |
| `test_snowflake_and_databricks_iter_without_limit` | SQL sem `LIMIT` nos dois |
| `test_postgres_real_iter_rows` | com Postgres real, 12 linhas e `batch=5` dão `[5, 5, 2]` (só com `AKME_PG_TEST_DSN`) |

Evidência RED/GREEN: rodando os testes contra o código do `HEAD` (sem a implementação), 8 falham com `AttributeError: ... iter_rows` e o de Postgres real é pulado. Com a implementação, 8 passam e 1 é pulado.

Na suíte completa, a falha de `test_optional_adapters_fail_clearly` já existia antes desta tarefa (também falha numa cópia limpa do `HEAD`) e não tem relação com ela.

## Limites

- O cursor nomeado do Postgres exige transação aberta; quem consome deve ler o gerador até o fim ou descartá-lo para o cursor fechar.
- Os testes de Snowflake, Databricks e Postgres usam cursores falsos, sem banco real, exceto o teste opcional de Postgres.
- Um CSV lido com outro `encoding` explícito na configuração não passa pelo `utf-8-sig`.

## Revisão

A revisão independente aprovou a tarefa, sem pontos críticos nem importantes.

Pontos menores adiados para a revisão final da branch:

1. O nome fixo do cursor `akme_iter` no Postgres impede duas leituras ao mesmo tempo na mesma conexão e deixa a transação aberta depois da leitura.
2. Não há guarda para `batch <= 0`.
3. O BOM no teste está como caractere invisível em vez de escape.
4. Não há teste de que o cursor fecha quando o consumidor para cedo.
5. `read_sample` e `read_schema` deixam o arquivo aberto até a coleta do gerador.
