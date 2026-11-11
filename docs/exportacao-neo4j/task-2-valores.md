# Task 2: conversão de valores e identidade do nó

## O que mudou

Novo módulo `akme/tools/neo4j_values.py` com as funções que transformam o valor de uma célula em valor Python tipado e que calculam a identidade (`_id`) de cada nó. O módulo antigo `akme/tools/n10s.py` não foi alterado; ele só sai na Task 7.

## Por que

O exportador antigo gerava literais N-Triples (`"7"^^xsd:integer`). O novo manda ao Neo4j valores Python tipados, como parâmetros do driver. A conversão segue as mesmas regras de aceitação e recusa do `rdf_literal`: o que antes era recusado continua recusado. Há duas recusas novas, estouro e underflow de `float` (veja abaixo). Assim nenhum dado é perdido ou alterado em silêncio. Só muda o tipo de saída.

## A interface

| Função | O que faz |
|--------|-----------|
| `TYPES` | `("string", "integer", "float", "date")`, os tipos que a etapa 5 pode declarar |
| `filled(value)` | falso só para `None` e `""`; `0`, `False` e `" "` são valores |
| `convert(kind, value)` | devolve `str`, `int`, `float` ou `datetime.date`; levanta `ValueError` quando perderia informação |
| `node_id(values)` | texto de identidade do nó a partir dos valores da chave |
| `name(identifier)` | identificador Cypher entre crases |

## Regras de conversão

| Tipo | Aceita | Recusa |
|------|--------|--------|
| `string` | qualquer valor, via `str(value)` (`12` vira `"12"`) | nada |
| `integer` | `"7"`, `"7.0"` (vira `7`), `100`, `100.0`; intervalo int64 | `"7.5"`, `"007"`, `"abc"`, `2**63`, `True` |
| `float` | `"10.50"` (10.5), `Decimal("1.25")`, `7`, `0.00001` | `"abc"`, `"nan"`, `"inf"`, `"4.120,50"`, `True`, `"1e999"` (estouro, viraria `inf`), `"1e-400"` (underflow, viraria `0.0` sendo diferente de zero) |
| `date` | `"2026-01-02"`, `date`, `datetime` à meia-noite sem fuso | `"2026-01-02T10:00:00"`, `datetime` com horário, valor com fuso, `"02/01/2026"` |
| outro tipo | nada | sempre `ValueError` |

Decimais longos são arredondados para float64 (`"0.1234567890123456789"` vira `0.12345678901234568`), que é o que uma coluna `float` do Neo4j guarda. Quem precisa dos dígitos exatos declara a coluna como `string` no `add_source`.

Booleano em coluna numérica é recusado porque `True` viraria `1` sem ninguém pedir.

## Por que `node_id` codifica cada valor

`node_id` aplica `quote(str(v), safe="")` em cada valor e une com `/`. Sem a codificação, a chave composta `("a/b", "c")` e `("a", "b/c")` gerariam o mesmo texto `a/b/c` e dois nós diferentes colidiriam no `MERGE`. Codificando, a barra do dado vira `%2F` e só a barra de junção separa valores. Chaves simples do dia a dia não mudam: `["1001", "CIM-50"]` vira `1001/CIM-50`.

## Por que `name` dobra a crase

Rótulos e tipos de relação vêm da ontologia e entram no texto Cypher, que não aceita parâmetro para identificador. `name` envolve em crases e dobra qualquer crase interna (`a`b` vira `` `a``b` ``), então um nome estranho não quebra a consulta nem injeta código. Dados de células nunca passam por aqui: vão sempre como parâmetros.

## Como foi testado

Arquivo: `tests/test_neo4j_values.py` (36 casos).

- `test_convert_accepts`: confere valor e tipo exato do resultado (`int` não pode ser `bool`, `float` não pode ser `Decimal`).
- `test_convert_refuses`: todos os casos de recusa do teste antigo do `rdf_literal` mais os da tarefa.
- `test_convert_float_rounds_long_decimals_to_float64`: fixa o arredondamento aceito.
- `test_convert_refuses_unknown_kind_and_aware_date`: tipo desconhecido e data com fuso.
- `test_filled_only_false_for_none_and_empty`, `test_types`.
- `test_node_id_does_not_collide`: a colisão acima, a chave simples e a codificação de espaço e barra.
- `test_name_doubles_backtick`.

## Evidência de TDD

- RED: `uv run pytest tests/test_neo4j_values.py -q` falhou com `ModuleNotFoundError: No module named 'akme.tools.neo4j_values'`.
- GREEN: após implementar, `31 passed`.

## Revisão

A primeira revisão independente encontrou um ponto importante: `float` transformava `"1e999"` em infinito e `"1e-400"` em zero sem avisar. Foi corrigido com duas recusas novas (estouro e underflow) e testes.

Decisões registradas:

- O arredondamento float64 de decimais longos é aceito e documentado; quem precisa dos dígitos exatos usa o tipo `string`.
- `TYPES` passou a reutilizar `SOURCE_TYPES`.

A segunda revisão confirmou as correções, sem quebra nova.
