"""Confere o grafo da demo no Neo4j contra os CSVs e o gabarito. Somente leitura.

Vale so para a demo, carregada pelo `akme publish --target neo4j --no-dry-run` (Cypher, sem plugin).
Confere os nos de dado por label, as arestas com o nome exato das relacoes, a camada Conceito da ontologia (espelho
do schema.ttl: setas RELACAO_ONTOLOGIA com o nome em `nome`), o mapa db.schema.visualization sem setas falsas, os termos
(Termo), a legenda name de cada no, a _descricao de nos e arestas, o esquema para o LLM na marca do projeto,
as restricoes e indices akme_*, os valores e tipos gravados e a marca da carga (sincronizacao).

Uso, com as variaveis AKME_NEO4J_* no ambiente:
    uv run --extra neo4j python examples/local_demo/verificar_neo4j.py
Sai com codigo 1 se alguma verificacao falhar.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import neo4j

HERE = Path(__file__).resolve().parent
PROJETO = "local_demo"
# relacao da ontologia -> (dominio, alcance, tipo da aresta de dado no Neo4j, que e tambem o nome no gabarito)
EDGES = {
    "contem": ("Pedido", "ItemPedido", "CONTEM"),
    "pertenceA": ("Pedido", "Cliente", "PERTENCE_A"),
    "referencia": ("ItemPedido", "Produto", "REFERENCIA"),
}
# coluna-alvo de cada join, que precisa de indice para resolver as arestas
JOIN_TARGETS = [("Cliente", "id_cliente"), ("ItemPedido", "id_pedido"), ("Produto", "sku")]
SOURCES = {
    "Cliente": ("clientes", ["id_cliente"]),
    "ItemPedido": ("itens_pedido", ["id_pedido", "sku"]),
    "Pedido": ("pedidos", ["id_pedido"]),
    "Produto": ("produtos", ["sku"]),
}
STORED_TYPES = {
    ("Cliente", "cnpj"): "STRING", ("Cliente", "dt_cadastro"): "DATE", ("Cliente", "fl_ativo"): "STRING", ("Cliente", "id_cliente"): "STRING",
    ("ItemPedido", "id_pedido"): "STRING", ("ItemPedido", "qt_itens"): "INTEGER", ("ItemPedido", "sku"): "STRING", ("ItemPedido", "vl_item"): "FLOAT",
    ("Pedido", "dt_pedido"): "DATE", ("Pedido", "id_cliente"): "STRING", ("Pedido", "id_pedido"): "STRING", ("Pedido", "nf"): "STRING", ("Pedido", "status"): "STRING", ("Pedido", "vl_total"): "FLOAT",
    ("Produto", "categoria"): "STRING", ("Produto", "sku"): "STRING", ("Produto", "vl_unitario"): "FLOAT",
}
# akme_projeto_uniq: uma marca _AkmeProjeto por projeto (duas primeiras cargas simultaneas nao criam duas)
CONSTRAINTS = sorted(["akme_conceito_uniq_projeto_nome", "akme_projeto_uniq", "akme_termo_uniq_projeto_nome"]
                     + [f"akme_uniq_{label}" for label in SOURCES])
RESERVED = {"_id", "_projeto", "_carga", "_descricao", "name"}  # name: legenda gravada pelo akme
# classes do schema.ttl da demo: as 4 do template mais as 5 das edicoes da demo
CONCEITOS = ["Cliente", "Entity", "Faturamento", "ItemPedido", "Metric", "Pedido", "Produto", "Relation", "Rule"]
SUBCLASSES = ["Cliente->Entity", "Faturamento->Metric", "ItemPedido->Entity", "Pedido->Entity", "Produto->Entity"]
DATA = "n._projeto = $p AND NOT n:Conceito AND NOT n:Termo"
# termos do content.yml da demo, cada um ligado ao conceito da sua classe
TERMOS = {"categoria": "Produto", "cliente": "Cliente", "cliente_ativo": "Cliente", "data_pedido": "Pedido",
          "faturamento": "Faturamento", "pedido": "Pedido", "produto": "Produto", "quantidade": "ItemPedido",
          "status_pedido": "Pedido", "uf": "Cliente"}
# _descricao das arestas: as relacoes da demo nao tem definicao, entao vale o rotulo
EDGE_TEXT = {"contem": "contem", "pertenceA": "pertence a", "referencia": "referencia"}
# setas RELACAO_ONTOLOGIA: toda owl:ObjectProperty do schema.ttl da demo, inversas incluidas
# (dominio, nome, alcance, publicada nos dados)
ONTOLOGY_ARROWS = [("Cliente", "possuiPedido", "Pedido", False), ("ItemPedido", "pertenceAoPedido", "Pedido", False),
                   ("ItemPedido", "referencia", "Produto", True), ("Pedido", "contem", "ItemPedido", True),
                   ("Pedido", "pertenceA", "Cliente", True)]


class SemResultado(Exception):
    """Consulta que deveria devolver linhas e nao devolveu."""


def read_csv(name: str) -> list[dict[str, str]]:
    with (HERE / f"{name}.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def same_value(stored, raw: str) -> bool:
    """Numeros sao comparados pelo valor, portanto esta funcao nao avalia o tipo gravado."""
    if raw == "":
        return stored is None
    if hasattr(stored, "iso_format"):
        return stored.iso_format() == raw
    if isinstance(stored, (int, float)) and not isinstance(stored, bool):
        return Decimal(str(stored)) == Decimal(raw)
    return stored == raw


def fingerprint(query) -> dict[str, str]:
    """Resume o conteudo do grafo (sem _carga, que muda a cada carga) e as identidades internas."""
    def digest(rows) -> str:
        return hashlib.sha256(json.dumps(sorted(rows), ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]

    def plain(props: dict) -> dict:
        return {k: v for k, v in props.items() if k != "_carga"}

    nodes = query("MATCH (n) RETURN labels(n) AS l, properties(n) AS p, elementId(n) AS e")
    edges = query("MATCH (a)-[r]->(b) RETURN type(r) AS t, properties(r) AS r, properties(a) AS a, properties(b) AS b, elementId(r) AS e")
    return {
        "conteudo_nos": digest(json.dumps([r["l"], plain(r["p"])], sort_keys=True, ensure_ascii=False, default=str) for r in nodes),
        "conteudo_arestas": digest(json.dumps([r["t"], plain(r["r"]), plain(r["a"]), plain(r["b"])], sort_keys=True, ensure_ascii=False, default=str)
                                   for r in edges),
        "identidades_nos": digest(r["e"] for r in nodes),
        "identidades_arestas": digest(r["e"] for r in edges),
    }


def main() -> int:
    """Erros de conexao viram uma mensagem curta, sem credenciais nem o texto do driver."""
    try:
        return _main()
    except neo4j.exceptions.AuthError:
        print("falha no Neo4j: usuario ou senha recusados (confira AKME_NEO4J_USER e AKME_NEO4J_PASSWORD)")
    except neo4j.exceptions.ServiceUnavailable:
        print("falha no Neo4j: servidor indisponivel (confira se ele esta rodando e o AKME_NEO4J_URI)")
    return 1


def _main() -> int:
    missing = [v for v in ("AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD") if not os.environ.get(v)]
    if missing:
        print(f"defina no ambiente: {', '.join(missing)}")
        return 2
    gabarito = json.loads((HERE / "gabarito.json").read_text(encoding="utf-8"))
    driver = neo4j.GraphDatabase.driver(os.environ["AKME_NEO4J_URI"], auth=(os.environ["AKME_NEO4J_USER"], os.environ["AKME_NEO4J_PASSWORD"]))
    try:
        driver.verify_connectivity()  # falha rapido, sem as novas tentativas do execute_query
    except Exception:
        driver.close()
        raise
    failures: list[str] = []

    def query(cypher: str, **params) -> list[dict]:
        return [r.data() for r in driver.execute_query(cypher, params, routing_="r",
                                                       database_=os.environ.get("AKME_NEO4J_DATABASE") or None).records]

    def scalar(cypher: str, **params):
        rows = query(cypher, **params)
        if not rows:
            raise SemResultado(cypher)
        return next(iter(rows[0].values()))

    def check(name: str, got, expected) -> None:
        """got e uma funcao: uma consulta sem resultado vira FALHA, nunca excecao."""
        try:
            value = got()
        except SemResultado as exc:
            print("FALHA", name)
            print(f"   consulta sem resultado: {exc}")
            failures.append(name)
            return
        ok = value == expected
        print("OK   " if ok else "FALHA", name)
        if not ok:
            print(f"   obtido:   {value}\n   esperado: {expected}")
            failures.append(name)

    def money(cypher: str) -> str:
        value = scalar(cypher)
        if value is None:
            raise SemResultado(cypher)
        return f"{value:.2f}"

    p = PROJETO
    try:
        # modelo do grafo
        check("marca do projeto", lambda: [r["p"] for r in query("MATCH (m:_AkmeProjeto) RETURN m.projeto AS p")], [p])
        check("nos por label", lambda: {r["l"]: r["c"] for r in query(f"MATCH (n) WHERE {DATA} UNWIND labels(n) AS l RETURN l, count(*) AS c", p=p)},
              gabarito["nodes"])
        check("cada no de dado com um label so", lambda: scalar(f"MATCH (n) WHERE {DATA} AND size(labels(n)) <> 1 RETURN count(n) AS c", p=p), 0)
        check("nenhum no fora do projeto", lambda: scalar("MATCH (n) WHERE NOT n:_AkmeProjeto AND coalesce(n._projeto, '') <> $p RETURN count(n) AS c", p=p), 0)
        check("arestas de dado por tipo (nome da relacao)",
              lambda: {r["t"]: r["c"] for r in query(f"MATCH (n)-[r]->() WHERE {DATA} RETURN type(r) AS t, count(*) AS c", p=p)},
              {relation: gabarito["relationships"][g] for relation, (_, _, g) in EDGES.items()})
        for relation, (domain, range_, g) in EDGES.items():
            check(f"arestas (:{domain})-[:{relation}]->(:{range_})",
                  lambda d=domain, t=relation, a=range_: scalar(f"MATCH (:`{d}`)-[x:`{t}`]->(:`{a}`) WHERE NOT x._carga IS NULL RETURN count(x) AS c"),
                  gabarito["relationships"][g])
        check("mapa db.schema.visualization: setas de dado so entre os pares dos contratos",
              lambda: sorted((r["a"], r["t"], r["b"]) for r in query(
                  "CALL db.schema.visualization() YIELD relationships UNWIND relationships AS r "
                  "WITH startNode(r).name AS a, type(r) AS t, endNode(r).name AS b "
                  "WHERE NOT a IN ['Conceito', 'Termo', '_AkmeProjeto'] RETURN a, t, b")),
              sorted((d, relation, r) for relation, (d, r, _) in EDGES.items()))
        check("legenda name em todo no de dado, distinta e comecando pelo label",
              lambda: scalar(f"MATCH (n) WHERE {DATA} WITH n, labels(n)[0] AS l "
                             "WITH count(n) AS total, count(DISTINCT n.name) AS distintos, "
                             "count(CASE WHEN n.name STARTS WITH l + ' ' THEN 1 END) AS certos "
                             "RETURN total = distintos AND total = certos AS c", p=p), True)
        check("nenhuma aresta entre dados e Conceito",
              lambda: scalar("MATCH (a)-[r]-(b:Conceito) WHERE NOT a:Conceito AND NOT a:Termo RETURN count(r) AS c"), 0)

        # sincronizacao: tudo do projeto gravado pela mesma carga
        check("uma so _carga nos nos do projeto", lambda: scalar("MATCH (n) WHERE n._projeto = $p RETURN count(DISTINCT n._carga) AS c", p=p), 1)
        check("arestas com a mesma _carga dos nos",
              lambda: scalar("MATCH (n)-[r]->() WHERE n._projeto = $p WITH collect(DISTINCT r._carga) AS rc "
                             "MATCH (m) WHERE m._projeto = $p WITH rc, collect(DISTINCT m._carga) AS nc RETURN rc = nc AS c", p=p), True)

        # camada da ontologia
        check("conceitos (um por classe do schema.ttl)",
              lambda: sorted(r["n"] for r in query("MATCH (c:Conceito {_projeto: $p}) RETURN c.nome AS n", p=p)), CONCEITOS)
        check("SUBCLASSE_DE da ontologia",
              lambda: sorted(f"{r['a']}->{r['b']}" for r in query("MATCH (a:Conceito)-[:SUBCLASSE_DE]->(b:Conceito) RETURN a.nome AS a, b.nome AS b")),
              SUBCLASSES)
        check("setas da ontologia: RELACAO_ONTOLOGIA por relacao do schema.ttl, com nome e publicada_nos_dados",
              lambda: sorted((r["a"], r["n"], r["b"], r["pub"]) for r in query(
                  "MATCH (a:Conceito)-[r]->(b:Conceito) WHERE type(r) <> 'SUBCLASSE_DE' "
                  "RETURN a.nome AS a, type(r) + ':' + r.nome AS n, b.nome AS b, r.publicada_nos_dados AS pub")),
              sorted((d, f"RELACAO_ONTOLOGIA:{n}", r, pub) for d, n, r, pub in ONTOLOGY_ARROWS))
        check("legenda name de Conceito e Termo igual ao nome",
              lambda: scalar("MATCH (n) WHERE (n:Conceito OR n:Termo) AND n._projeto = $p AND n.name <> n.nome RETURN count(n) AS c", p=p), 0)
        check("legenda name da marca", lambda: scalar("MATCH (m:_AkmeProjeto {projeto: $p}) RETURN m.name AS c", p=p), f"Projeto {p}")
        check("definicao de Pedido no grafo", lambda: bool(scalar("MATCH (c:Conceito {nome: 'Pedido'}) RETURN c.definicao AS c")), True)
        check("termos ligados ao conceito da classe",
              lambda: {r["t"]: r["c"] for r in query("MATCH (c:Conceito {_projeto: $p})-[:TEM_TERMO]->(t:Termo {_projeto: $p}) "
                                                     "RETURN t.nome AS t, c.nome AS c", p=p)}, TERMOS)
        check("nenhum Termo solto", lambda: scalar("MATCH (t:Termo) WHERE NOT (:Conceito)-[:TEM_TERMO]->(t) RETURN count(t) AS c"), 0)

        # camada semantica nos dados: _descricao e esquema para o LLM
        check("todo no de dado com _descricao igual a Conceito.definicao do seu label",
              lambda: scalar(f"MATCH (n) WHERE {DATA} OPTIONAL MATCH (c:Conceito {{_projeto: $p}}) WHERE c.nome IN labels(n) "
                             "WITH n, c WHERE c IS NULL OR coalesce(n._descricao, '') <> coalesce(c.definicao, '') "
                             "RETURN count(n) AS c", p=p), 0)
        check("_descricao das arestas de dado",
              lambda: {r["t"]: r["d"] for r in query(f"MATCH (n)-[r]->() WHERE {DATA} RETURN DISTINCT type(r) AS t, r._descricao AS d", p=p)},
              EDGE_TEXT)
        check("esquema para o LLM na marca do projeto",
              lambda: (lambda e: bool(e) and e.startswith("# Esquema do grafo") and "### Pedido" in e and "NOT n:Conceito" in e)(
                  scalar("MATCH (m:_AkmeProjeto {projeto: $p}) RETURN m.esquema AS e", p=p)), True)

        # esquema: restricoes e indices do akme
        check("restricoes akme_*",
              lambda: sorted(r["name"] for r in query("SHOW CONSTRAINTS YIELD name WHERE name STARTS WITH 'akme_' RETURN name")), CONSTRAINTS)
        check("nenhuma restricao da exportacao antiga",
              lambda: scalar("SHOW CONSTRAINTS YIELD name WHERE NOT name STARTS WITH 'akme_' RETURN count(*) AS c"), 0)
        check("indice ONLINE em cada coluna-alvo de join",
              lambda: sorted((r["l"], r["c"]) for r in query(
                  "SHOW INDEXES YIELD name, labelsOrTypes, properties, state WHERE name STARTS WITH 'akme_idx_' AND state = 'ONLINE' "
                  "RETURN labelsOrTypes[0] AS l, properties[0] AS c")),
              JOIN_TARGETS)

        # valores, celula a celula
        cells = 0
        for label, (source, key) in SOURCES.items():
            rows = read_csv(source)
            stored = [r["n"] for r in query(f"MATCH (n:`{label}`) WHERE n._projeto = $p RETURN properties(n) AS n", p=p)]
            by_key = {tuple(str(n.get(k)) for k in key): n for n in stored}
            wrong, extra = [], set()
            for row in rows:
                node = by_key.get(tuple(row[k] for k in key))
                if node is None:
                    wrong.append(("sem no", row))
                    continue
                for column, value in row.items():
                    cells += 1
                    if not same_value(node.get(column), value):
                        wrong.append((column, value, node.get(column)))
                extra |= set(node) - set(row) - RESERVED
            check(f"valores de {label} ({len(rows)} linhas)", lambda w=wrong: w, [])
            check(f"sem propriedade extra em {label}", lambda e=extra: sorted(e), [])
            check(f"chave unica em {label}", lambda b=by_key: len(b), len(rows))
            check(f"_id unico em {label}", lambda lb=label: scalar(f"MATCH (n:`{lb}`) RETURN count(DISTINCT n._id) AS c"), len(rows))
        print(f"     celulas comparadas: {cells}")

        # pares de cada relacao
        pedidos, itens = read_csv("pedidos"), read_csv("itens_pedido")
        check("pares de pertenceA", lambda: sorted((r["a"], r["b"]) for r in query("MATCH (a:Pedido)-[:pertenceA]->(b:Cliente) RETURN a.id_pedido AS a, b.id_cliente AS b")),
              sorted((x["id_pedido"], x["id_cliente"]) for x in pedidos))
        check("pares de contem", lambda: sorted((r["a"], r["b"], r["c"]) for r in query("MATCH (a:Pedido)-[:contem]->(b:ItemPedido) RETURN a.id_pedido AS a, b.id_pedido AS b, b.sku AS c")),
              sorted((i["id_pedido"], i["id_pedido"], i["sku"]) for i in itens))
        check("pares de referencia", lambda: sorted((r["a"], r["b"], r["c"]) for r in query("MATCH (a:ItemPedido)-[:referencia]->(b:Produto) RETURN a.id_pedido AS a, a.sku AS b, b.sku AS c")),
              sorted((i["id_pedido"], i["sku"], i["sku"]) for i in itens))
        check("cada pedido com 1 cliente", lambda: scalar("MATCH (p:Pedido) OPTIONAL MATCH (p)-[r:pertenceA]->() WITH p, count(r) AS c WHERE c <> 1 RETURN count(p) AS c"), 0)
        check("clientes sem pedido", lambda: sorted(r["c"] for r in query("MATCH (c:Cliente) WHERE NOT (c)<-[:pertenceA]-() RETURN c.id_cliente AS c")),
              gabarito["direct_answers"]["clientes_sem_pedido"])

        # medidas e consultas de negocio
        measures = gabarito["measures"]
        check("soma de qt_itens", lambda: scalar("MATCH (i:ItemPedido) RETURN sum(i.qt_itens) AS s"), measures["qt_itens"])
        check("faturamento", lambda: money("MATCH (p:Pedido {status: 'FATURADO'}) RETURN sum(p.vl_total) AS s"), measures["faturamento"])
        check("vl_total sem filtro", lambda: money("MATCH (p:Pedido) RETURN sum(p.vl_total) AS s"), measures["vl_total_sem_filtro"])
        check("erro de fan-out reproduzido", lambda: money("MATCH (p:Pedido {status: 'FATURADO'})-[:contem]->() RETURN sum(p.vl_total) AS s"),
              gabarito["traps"]["fanout_faturamento_apos_itens"])
        check("produtos do pedido 1001",
              lambda: {r["s"]: r["q"] for r in query("MATCH (:Pedido {id_pedido: '1001'})-[:contem]->(i)-[:referencia]->(s:Produto) RETURN s.sku AS s, i.qt_itens AS q")},
              gabarito["direct_answers"]["produtos_do_pedido_1001"])

        def stored_types():
            found_types = {}
            for (label, column) in STORED_TYPES:
                found = query(f"MATCH (n:`{label}`) WHERE n.`{column}` IS NOT NULL RETURN DISTINCT valueType(n.`{column}`) AS t")
                found_types[(label, column)] = " | ".join(sorted(r["t"].replace(" NOT NULL", "") for r in found))
            return found_types
        check("tipos gravados", stored_types, STORED_TYPES)

        print("IMPRESSAO DIGITAL", json.dumps(fingerprint(query), sort_keys=True))
    finally:
        driver.close()

    print("RESULTADO:", "todas as verificacoes passaram" if not failures else f"{len(failures)} falhas: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
