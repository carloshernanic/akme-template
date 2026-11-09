"""O oraculo da demo precisa ser independente do exportador e bater com um segundo metodo."""
import ast
import csv
import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "local_demo"


def _oracle():
    spec = importlib.util.spec_from_file_location("demo_oracle", DEMO / "oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    for table in ("clientes", "pedidos", "itens_pedido", "produtos"):
        with (DEMO / f"{table}.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        cols = list(rows[0])
        db.execute(f"CREATE TABLE {table} ({', '.join(cols)})")
        db.executemany(f"INSERT INTO {table} VALUES ({', '.join('?' for _ in cols)})", [[r[c] for c in cols] for r in rows])
    return db


def _money(db, sql) -> str:
    """Soma em centavos inteiros, para o segundo metodo nao depender de float nem de Decimal."""
    return f"{db.execute(sql).fetchone()[0] / 100:.2f}"


CENTS = "CAST(ROUND({} * 100) AS INTEGER)"


def test_oracle_does_not_use_the_exporter():
    tree = ast.parse((DEMO / "oracle.py").read_text(encoding="utf-8"))
    imported = {n.split(".")[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                for n in ([a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""])}
    assert imported <= {"__future__", "argparse", "collections", "csv", "decimal", "json", "pathlib"}


def test_counts_match_sql():
    g, db = _oracle().compute(DEMO), _db()
    one = lambda sql: db.execute(sql).fetchone()[0]
    assert g["nodes"] == {t: one(f"SELECT COUNT(*) FROM {s}") for t, s in
                          {"Cliente": "clientes", "ItemPedido": "itens_pedido", "Pedido": "pedidos", "Produto": "produtos"}.items()}
    assert g["relationships"]["PERTENCE_A"] == one("SELECT COUNT(*) FROM pedidos p JOIN clientes c USING (id_cliente)")
    assert g["relationships"]["CONTEM"] == one("SELECT COUNT(*) FROM pedidos p JOIN itens_pedido i USING (id_pedido)")
    assert g["relationships"]["REFERENCIA"] == one("SELECT COUNT(*) FROM itens_pedido i JOIN produtos p USING (sku)")
    assert g["keys_unique"]["ItemPedido(id_pedido, sku)"] == (one("SELECT COUNT(DISTINCT id_pedido || '|' || sku) FROM itens_pedido") == g["nodes"]["ItemPedido"])


def test_money_matches_sql_in_cents():
    g, db = _oracle().compute(DEMO), _db()
    total = CENTS.format("p.vl_total")
    m = g["measures"]
    assert m["faturamento"] == _money(db, f"SELECT SUM({total}) FROM pedidos p WHERE status = 'FATURADO'")
    assert m["vl_total_sem_filtro"] == _money(db, f"SELECT SUM({total}) FROM pedidos p")
    assert g["traps"]["fanout_faturamento_apos_itens"] == _money(db, f"SELECT SUM({total}) FROM pedidos p JOIN itens_pedido i USING (id_pedido) WHERE status = 'FATURADO'")
    assert m["qt_itens"] == db.execute("SELECT SUM(CAST(qt_itens AS INTEGER)) FROM itens_pedido").fetchone()[0]


def test_gabarito_on_disk_is_what_the_oracle_computes():
    oracle = _oracle()
    stored = json.loads((DEMO / "gabarito.json").read_text(encoding="utf-8"))
    assert stored == json.loads(json.dumps(oracle.compute(DEMO)))
