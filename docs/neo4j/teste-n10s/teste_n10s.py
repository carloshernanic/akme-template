"""Teste do n10s contra a demo. Codigo de teste, nao faz parte do template.

Uso: python teste_n10s.py <bolt_uri> <arquivo_senha> <R1|R2> <schema.ttl> <pasta_csv> <saida.json>
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import neo4j
from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

AKME = Namespace("https://akme.example/ontology#")
SOURCES = {"Cliente": ("clientes", ["id_cliente"]), "ItemPedido": ("itens_pedido", ["id_pedido", "sku"]),
           "Pedido": ("pedidos", ["id_pedido"]), "Produto": ("produtos", ["sku"])}
TYPES = {"dt_cadastro": XSD.date, "dt_pedido": XSD.date, "vl_total": XSD.decimal, "vl_item": XSD.decimal,
         "vl_unitario": XSD.decimal, "qt_itens": XSD.integer}
EXPECTED_NODES = {"Cliente": 8, "ItemPedido": 17, "Pedido": 10, "Produto": 8}
EXPECTED_EDGES = {"pertenceA": 10, "contem": 17, "referencia": 17}


def read(folder: Path, name: str) -> list[dict[str, str]]:
    with (folder / f"{name}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def iri(label: str, row: dict[str, str]) -> URIRef:
    return AKME[f"{label}/" + "/".join(row[k] for k in SOURCES[label][1])]


def build_r2(folder: Path) -> str:
    """RDF correto: IRI pela chave, toda coluna como propriedade tipada, relacoes como object properties."""
    g = Graph()
    rows = {label: read(folder, src) for label, (src, _) in SOURCES.items()}
    for label, items in rows.items():
        for r in items:
            s = iri(label, r)
            g.add((s, RDF.type, AKME[label]))
            for col, value in r.items():
                if value != "":
                    g.add((s, AKME[col], Literal(value, datatype=TYPES.get(col, XSD.string))))
    for p in rows["Pedido"]:
        g.add((iri("Pedido", p), AKME.pertenceA, AKME[f"Cliente/{p['id_cliente']}"]))
    for i in rows["ItemPedido"]:
        g.add((AKME[f"Pedido/{i['id_pedido']}"], AKME.contem, iri("ItemPedido", i)))
        g.add((iri("ItemPedido", i), AKME.referencia, AKME[f"Produto/{i['sku']}"]))
    return g.serialize(format="turtle")


SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix akme: <https://akme.example/ontology#> .
akme:ClienteShape a sh:NodeShape ; sh:targetClass akme:Cliente ;
  sh:property [ sh:path akme:uf ; sh:minCount 1 ] .
"""


def main() -> None:
    uri, pw_file, variant, schema, folder, out = sys.argv[1:7]
    vocab = sys.argv[7] if len(sys.argv) > 7 else "IGNORE"
    folder = Path(folder)
    data_ttl = Path(variant).read_text(encoding="utf-8") if variant.endswith(".ttl") else build_r2(folder)
    result: dict = {"vocab": sys.argv[7] if len(sys.argv) > 7 else "IGNORE", "entrada": Path(variant).name if variant.endswith(".ttl") else "R2"}
    driver = neo4j.GraphDatabase.driver(uri, auth=("neo4j", Path(pw_file).read_text()))

    def q(cypher: str, **params):
        return [r.data() for r in driver.execute_query(cypher, params).records]

    def step(name: str, fn):
        try:
            result[name] = fn()
        except Exception as exc:  # o teste registra a falha em vez de parar
            result[name] = {"erro": f"{type(exc).__name__}: {str(exc)[:300]}"}

    try:
        q("MATCH (n) DETACH DELETE n")
        for c in q("SHOW CONSTRAINTS YIELD name RETURN name"):
            q(f"DROP CONSTRAINT `{c['name']}`")
        step("C1_graphconfig", lambda: (q("CALL n10s.graphconfig.drop()") if q("MATCH (n:_GraphConfig) RETURN count(n) AS c")[0]["c"] else None,
                                        q("CREATE CONSTRAINT n10s_unique_uri FOR (r:Resource) REQUIRE r.uri IS UNIQUE"),
                                        q("CALL n10s.graphconfig.init({handleVocabUris: $v})", v=vocab), "ok")[-1])
        step("C2_onto_import", lambda: q("CALL n10s.onto.import.inline($ttl, 'Turtle') YIELD terminationStatus, triplesLoaded, extraInfo "
                                         "RETURN terminationStatus, triplesLoaded, extraInfo", ttl=Path(schema).read_text(encoding="utf-8")))
        step("C2_classes", lambda: sorted(r["n"] for r in q("MATCH (c:Class) RETURN c.name AS n")))
        step("C2_subclasses", lambda: sorted(f"{r['a']}->{r['b']}" for r in q("MATCH (a:Class)-[:SCO]->(b:Class) RETURN a.name AS a, b.name AS b")))
        step("C2_class_props", lambda: q("MATCH (c:Class {name: 'Pedido'}) RETURN keys(c) AS k")[0]["k"])

        def load():
            return q("CALL n10s.rdf.import.inline($ttl, 'Turtle') YIELD terminationStatus, triplesLoaded, triplesParsed, extraInfo "
                     "RETURN terminationStatus, triplesLoaded, triplesParsed, extraInfo", ttl=data_ttl)
        step("import_1", load)

        def counts():
            nodes = {r["l"]: r["c"] for r in q("MATCH (n:Resource) WHERE NOT n:Class AND NOT n:Relationship AND NOT n:Property "
                                                 "UNWIND labels(n) AS l RETURN l, count(*) AS c")}
            edges = {r["t"]: r["c"] for r in q("MATCH (a:Resource)-[r]->(b:Resource) WHERE NOT a:Class AND NOT a:Relationship AND NOT a:Property "
                                                 "RETURN type(r) AS t, count(*) AS c")}
            return {"nos": nodes, "arestas": edges}
        step("C3_contagens", counts)

        def values():
            cells, wrong, types = 0, [], {}
            for label, (src, key) in SOURCES.items():
                stored = [r["p"] for r in q(f"MATCH (n:`{label}`) RETURN properties(n) AS p")]
                by_key = {tuple(str(n.get(k)) for k in key): n for n in stored}
                for row in read(folder, src):
                    node = by_key.get(tuple(row[k] for k in key))
                    for col, raw in row.items():
                        cells += 1
                        got = None if node is None else node.get(col)
                        ok = (got is None) if raw == "" else (
                            got.iso_format() == raw if hasattr(got, "iso_format") else
                            Decimal(str(got)) == Decimal(raw) if isinstance(got, (int, float)) and not isinstance(got, bool) else got == raw)
                        if not ok:
                            wrong.append([label, col, raw, str(got)])
                for col in ("dt_pedido", "vl_total", "id_pedido", "nf", "qt_itens", "dt_cadastro"):
                    found = q(f"MATCH (n:`{label}`) WHERE n.`{col}` IS NOT NULL RETURN DISTINCT valueType(n.`{col}`) AS t")
                    if found:
                        types[f"{label}.{col}"] = sorted(r["t"] for r in found)
            return {"celulas": cells, "diferentes": len(wrong), "exemplos": wrong[:6], "tipos": types}
        step("C4_C5_valores_tipos", values)

        def fingerprint():
            rows = q("MATCH (n) RETURN labels(n) AS l, properties(n) AS p, elementId(n) AS e")
            edges = q("MATCH (a)-[r]->(b) RETURN type(r) AS t, a.uri AS a, b.uri AS b")
            h = lambda xs: hashlib.sha256(json.dumps(sorted(xs), default=str).encode()).hexdigest()[:16]
            return {"nos": len(rows), "arestas": len(edges), "conteudo": h(json.dumps([sorted(r["l"]), r["p"]], default=str, sort_keys=True) for r in rows),
                    "identidades": h(r["e"] for r in rows), "arestas_hash": h(json.dumps([r["t"], r["a"], r["b"]]) for r in edges)}
        step("C6_antes", fingerprint)
        step("import_2", load)
        step("C6_depois", fingerprint)

        step("C7_hierarquia_por_inferencia", lambda: q("CALL n10s.inference.nodesLabelled('Entity', {catLabel: 'Class', catNameProp: 'name', subCatRel: 'SCO'}) "
                                                       "YIELD node RETURN count(node) AS c")[0]["c"])
        step("C7_definicao", lambda: q("MATCH (c:Class {name: 'Pedido'}) RETURN c.comment AS comment, c.label AS label"))

        step("C8_shapes", lambda: q("CALL n10s.validation.shacl.import.inline($s, 'Turtle') YIELD target, propertyOrRelationshipPath, param "
                                    "RETURN target, propertyOrRelationshipPath, param", s=SHAPES))
        step("C8_sem_violacao", lambda: q("CALL n10s.validation.shacl.validate() YIELD focusNode, resultPath RETURN count(*) AS c")[0]["c"])
        q("MATCH (c:Cliente) WITH c ORDER BY c.uri LIMIT 1 REMOVE c.uf" if vocab == "IGNORE" else
          "MATCH (c:Resource) WHERE c.uri STARTS WITH 'https://akme.example/ontology#Cliente/' WITH c ORDER BY c.uri LIMIT 1 "
          "WITH c, [k IN keys(c) WHERE k ENDS WITH '__uf'][0] AS k CALL apoc.create.removeProperties(c, [k]) YIELD node RETURN node"
          if False else "MATCH (c:Resource) WHERE c.uri = 'https://akme.example/ontology#Cliente/1' SET c.ns0__uf = null")
        step("C8_violacao_plantada", lambda: q("CALL n10s.validation.shacl.validate() YIELD focusNode, nodeType, resultPath, severity, resultMessage "
                                               "RETURN nodeType, resultPath, severity, resultMessage"))

        step("C9_produtos_pedido_1001", lambda: {r["sku"]: r["q"] for r in q(
            "MATCH (:Pedido {id_pedido: '1001'})-[:contem]->(i:ItemPedido)-[:referencia]->(p:Produto) RETURN p.sku AS sku, i.qt_itens AS q")})
        step("labels_dos_nos", lambda: sorted({json.dumps(sorted(r["l"])) for r in q("MATCH (n) RETURN labels(n) AS l")}))
        step("exemplo_no_pedido", lambda: q("MATCH (p:Pedido) RETURN properties(p) AS p ORDER BY p.uri LIMIT 1"))
    finally:
        driver.close()
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
