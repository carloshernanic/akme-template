"""Confere o grafo da demo no Neo4j contra os CSVs e o gabarito. Somente leitura.

Vale so para a demo, carregada pelo n10s com nomes limpos. Os nomes das arestas sao os gravados hoje.

Uso, com as variaveis AKME_NEO4J_* no ambiente:
    uv run python examples/local_demo/verificar_neo4j.py
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
EDGE_NAMES = {"pertenceA": "PERTENCE_A", "contem": "CONTEM", "referencia": "REFERENCIA"}
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
CONSTRAINTS = ["n10s_unique_uri"]
DATA = "n:Resource AND NOT n:Class AND NOT n:Relationship"
SUBCLASSES = ["Cliente->Entity", "Faturamento->Metric", "ItemPedido->Entity", "Pedido->Entity", "Produto->Entity"]


def read_csv(name: str) -> list[dict[str, str]]:
    with (HERE / f"{name}.csv").open(encoding="utf-8", newline="") as f:
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
    """Resume o conteudo do grafo e as identidades internas, para comparar duas cargas."""
    def digest(rows) -> str:
        return hashlib.sha256(json.dumps(sorted(rows), ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]

    nodes = query("MATCH (n) RETURN labels(n) AS l, properties(n) AS p, elementId(n) AS e")
    edges = query("MATCH (a)-[r]->(b) RETURN type(r) AS t, properties(a) AS a, properties(b) AS b, elementId(r) AS e")
    return {
        "conteudo_nos": digest(json.dumps([r["l"], r["p"]], sort_keys=True, ensure_ascii=False, default=str) for r in nodes),
        "conteudo_arestas": digest(json.dumps([r["t"], r["a"], r["b"]], sort_keys=True, ensure_ascii=False, default=str) for r in edges),
        "identidades_nos": digest(r["e"] for r in nodes),
        "identidades_arestas": digest(r["e"] for r in edges),
    }


def main() -> int:
    gabarito = json.loads((HERE / "gabarito.json").read_text(encoding="utf-8"))
    driver = neo4j.GraphDatabase.driver(os.environ["AKME_NEO4J_URI"], auth=(os.environ["AKME_NEO4J_USER"], os.environ["AKME_NEO4J_PASSWORD"]))
    failures: list[str] = []

    def query(cypher: str) -> list[dict]:
        return [r.data() for r in driver.execute_query(cypher, routing_="r").records]

    def check(name: str, got, expected) -> None:
        ok = got == expected
        print("OK   " if ok else "FALHA", name)
        if not ok:
            print(f"   obtido:   {got}\n   esperado: {expected}")
            failures.append(name)

    def money(cypher: str) -> str:
        return f"{query(cypher)[0]['s']:.2f}"

    try:
        check("nos por label", {r["l"]: r["c"] for r in query(f"MATCH (n) WHERE {DATA} UNWIND labels(n) AS l WITH l WHERE l <> 'Resource' RETURN l, count(*) AS c")}, gabarito["nodes"])
        check("arestas por tipo", {EDGE_NAMES.get(r["t"], r["t"]): r["c"] for r in query("MATCH (n)-[r]->() WHERE " + DATA + " RETURN type(r) AS t, count(*) AS c")}, gabarito["relationships"])
        check("cada no de dado com uma classe e Resource", query(f"MATCH (n) WHERE {DATA} AND size(labels(n)) <> 2 RETURN count(n) AS c")[0]["c"], 0)
        check("nenhum no fora do modelo", query("MATCH (n) WHERE NOT n:Resource AND NOT n:_GraphConfig AND NOT n:_AkmeProjeto RETURN count(n) AS c")[0]["c"], 0)
        check("marca do projeto", [r["p"] for r in query("MATCH (m:_AkmeProjeto) RETURN m.projeto AS p")], ["local_demo"])
        check("arestas da ontologia", {r["t"]: r["c"] for r in query("MATCH (n:Class)-[r]->() RETURN type(r) AS t, count(*) AS c")}, {"SCO": 5})
        check("subclasses da ontologia no grafo", sorted(f"{r['a']}->{r['b']}" for r in query("MATCH (a:Class)-[:SCO]->(b:Class) RETURN a.name AS a, b.name AS b")), SUBCLASSES)
        check("definicao de Pedido no grafo", bool(query("MATCH (c:Class {name: 'Pedido'}) RETURN c.comment AS c")[0]["c"]), True)

        cells = 0
        for label, (source, key) in SOURCES.items():
            rows = read_csv(source)
            stored = [r["n"] for r in query(f"MATCH (n:`{label}`) WHERE NOT n:Class RETURN properties(n) AS n")]
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
                extra |= set(node) - set(row) - {"uri"}
            check(f"valores de {label} ({len(rows)} linhas)", wrong, [])
            check(f"sem propriedade extra em {label}", sorted(extra), [])
            check(f"chave unica em {label}", len(by_key), len(rows))
        print(f"     celulas comparadas: {cells}")

        pedidos, itens = read_csv("pedidos"), read_csv("itens_pedido")
        check("pares de pertenceA", sorted((r["a"], r["b"]) for r in query("MATCH (a:Pedido)-[:pertenceA]->(b:Cliente) RETURN a.id_pedido AS a, b.id_cliente AS b")),
              sorted((p["id_pedido"], p["id_cliente"]) for p in pedidos))
        check("pares de contem", sorted((r["a"], r["b"], r["c"]) for r in query("MATCH (a:Pedido)-[:contem]->(b:ItemPedido) RETURN a.id_pedido AS a, b.id_pedido AS b, b.sku AS c")),
              sorted((i["id_pedido"], i["id_pedido"], i["sku"]) for i in itens))
        check("pares de referencia", sorted((r["a"], r["b"], r["c"]) for r in query("MATCH (a:ItemPedido)-[:referencia]->(b:Produto) RETURN a.id_pedido AS a, a.sku AS b, b.sku AS c")),
              sorted((i["id_pedido"], i["sku"], i["sku"]) for i in itens))
        check("cada pedido com 1 cliente", query("MATCH (p:Pedido) OPTIONAL MATCH (p)-[r:pertenceA]->() WITH p, count(r) AS c WHERE c <> 1 RETURN count(p) AS c")[0]["c"], 0)
        check("clientes sem pedido", sorted(r["c"] for r in query("MATCH (c:Cliente) WHERE NOT (c)<-[:pertenceA]-() RETURN c.id_cliente AS c")), gabarito["direct_answers"]["clientes_sem_pedido"])
        check("constraints", sorted(r["name"] for r in query("SHOW CONSTRAINTS YIELD name RETURN name")), CONSTRAINTS)

        measures = gabarito["measures"]
        check("soma de qt_itens", query("MATCH (i:ItemPedido) RETURN sum(i.qt_itens) AS s")[0]["s"], measures["qt_itens"])
        check("faturamento", money("MATCH (p:Pedido {status: 'FATURADO'}) RETURN sum(p.vl_total) AS s"), measures["faturamento"])
        check("vl_total sem filtro", money("MATCH (p:Pedido) RETURN sum(p.vl_total) AS s"), measures["vl_total_sem_filtro"])
        check("erro de fan-out reproduzido", money("MATCH (p:Pedido {status: 'FATURADO'})-[:contem]->() RETURN sum(p.vl_total) AS s"), gabarito["traps"]["fanout_faturamento_apos_itens"])
        check("produtos do pedido 1001", {r["s"]: r["q"] for r in query("MATCH (:Pedido {id_pedido: '1001'})-[:contem]->(i)-[:referencia]->(s:Produto) RETURN s.sku AS s, i.qt_itens AS q")},
              gabarito["direct_answers"]["produtos_do_pedido_1001"])

        stored_types = {}
        for (label, column) in STORED_TYPES:
            found = query(f"MATCH (n:`{label}`) WHERE n.`{column}` IS NOT NULL RETURN DISTINCT valueType(n.`{column}`) AS t")
            stored_types[(label, column)] = " | ".join(sorted(r["t"].replace(" NOT NULL", "") for r in found))
        check("tipos gravados", stored_types, STORED_TYPES)

        print("IMPRESSAO DIGITAL", json.dumps(fingerprint(query), sort_keys=True))
    finally:
        driver.close()

    print("RESULTADO:", "todas as verificacoes passaram" if not failures else f"{len(failures)} falhas: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
