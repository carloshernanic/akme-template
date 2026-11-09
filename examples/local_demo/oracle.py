"""Oraculo da demo: calcula as respostas esperadas direto dos CSVs brutos.

So usa a biblioteca padrao e nao importa nada do akme, para que um erro do exportador
nao possa se repetir aqui. Dinheiro em Decimal, nunca float.

Uso: python examples/local_demo/oracle.py [--write]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _read(data_dir: Path, name: str) -> list[dict[str, str]]:
    with (data_dir / f"{name}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _sum(rows: list[dict[str, str]], column: str) -> Decimal:
    return sum((Decimal(r[column]) for r in rows), Decimal("0"))


def _unique(rows: list[dict[str, str]], *columns: str) -> bool:
    return len({tuple(r[c] for c in columns) for r in rows}) == len(rows)


def compute(data_dir: Path) -> dict:
    clientes = _read(data_dir, "clientes")
    pedidos = _read(data_dir, "pedidos")
    itens = _read(data_dir, "itens_pedido")
    produtos = _read(data_dir, "produtos")

    uf = {c["id_cliente"]: c["uf"] for c in clientes}
    categoria = {p["sku"]: p["categoria"] for p in produtos}
    ids_pedido = {p["id_pedido"] for p in pedidos}
    itens_por_pedido = Counter(i["id_pedido"] for i in itens)
    faturados = [p for p in pedidos if p["status"] == "FATURADO"]
    com_pedido = {p["id_cliente"] for p in pedidos}
    fanout = sum((Decimal(p["vl_total"]) * itens_por_pedido[p["id_pedido"]] for p in faturados), Decimal("0"))

    return {
        "nodes": {"Cliente": len(clientes), "ItemPedido": len(itens), "Pedido": len(pedidos), "Produto": len(produtos)},
        "relationships": {
            "CONTEM": sum(1 for i in itens if i["id_pedido"] in ids_pedido),
            "PERTENCE_A": sum(1 for p in pedidos if p["id_cliente"] in uf),
            "REFERENCIA": sum(1 for i in itens if i["sku"] in categoria),
        },
        "keys_unique": {
            "Cliente(id_cliente)": _unique(clientes, "id_cliente"),
            "ItemPedido(id_pedido, sku)": _unique(itens, "id_pedido", "sku"),
            "Pedido(id_pedido)": _unique(pedidos, "id_pedido"),
            "Produto(sku)": _unique(produtos, "sku"),
        },
        "measures": {
            "faturamento": _money(_sum(faturados, "vl_total")),
            "qt_itens": sum(int(i["qt_itens"]) for i in itens),
            "vl_total_sem_filtro": _money(_sum(pedidos, "vl_total")),
        },
        "direct_answers": {
            "clientes_sem_pedido": sorted(set(uf) - com_pedido),
            "produtos_do_pedido_1001": {i["sku"]: int(i["qt_itens"]) for i in sorted(itens, key=lambda x: x["sku"]) if i["id_pedido"] == "1001"},
            "todo_pedido_tem_um_cliente": all(p["id_cliente"] in uf for p in pedidos),
        },
        "traps": {
            "fanout_faturamento_apos_itens": _money(fanout),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="grava gabarito.json ao lado deste arquivo")
    args = parser.parse_args()
    text = json.dumps(compute(HERE), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.write:
        (HERE / "gabarito.json").write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
