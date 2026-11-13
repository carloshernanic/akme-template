"""Confere uma amostra de linhas da origem contra os nos gravados no Neo4j: valor e tipo, celula a celula. Somente leitura.

Vale para qualquer projeto carregado pelo `akme publish --target neo4j --no-dry-run`. Para cada fonte do plano:
  - sorteia ate N linhas com a chave completa (amostragem de reservatorio, semente fixa), lidas pelo adapter do projeto;
  - converte cada celula preenchida com `convert` do tipo aprovado na etapa 5 (texto se nao declarado);
  - busca o no por label e `_id`;
  - compara campo a campo: mesmo valor e mesmo tipo, nenhuma propriedade a mais ou a menos alem das do akme:
    `_id`, `_projeto`, `_carga` e, so com `neo4j.descricao_nos_dados: true` no akme.yml, `_descricao` (desligada, o
    padrao, uma `_descricao` no no conta como propriedade a mais). A legenda `name` tambem e conferida: o valor esperado e o da regra do
    akme (neo4j_values.caption), ou a coluna `name` da origem quando a fonte tem uma (preenchida na linha).
Datas voltam do driver como neo4j.time.Date e sao normalizadas com to_native() para datetime.date antes da comparacao.
A saida nao mostra valores das linhas, so contagens e o nome da coluna divergente.

Uso, com as variaveis AKME_NEO4J_* no ambiente:
    uv run --extra neo4j python examples/local_demo/amostra_valores.py <akme.yml> --n 200 --seed 42
Sai com codigo 1 se houver divergencia.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import neo4j

from akme.adapters import load_adapter
from akme.project import Project
from akme.tools.neo4j_plan import BATCH, build_plan
from akme.tools.neo4j_values import caption, convert, filled, node_id

RESERVED = {"_id", "_projeto", "_carga"}  # campos do akme, nao da origem; _descricao entra so com a opcao ligada


def sample(adapter: Any, source: str, key: list[str], n: int, rng: random.Random) -> tuple[list[dict[str, Any]], int]:
    """Amostra de reservatorio (algoritmo R) sobre a fonte inteira, lida em blocos. Devolve a amostra e o total visto."""
    chosen: list[dict[str, Any]] = []
    seen = 0
    for block in adapter.iter_rows(source, BATCH):
        for row in block:
            if not all(filled(row.get(c)) for c in key):
                continue
            seen += 1
            if len(chosen) < n:
                chosen.append(row)
            else:
                j = rng.randrange(seen)
                if j < n:
                    chosen[j] = row
    return chosen, seen


def native(value: Any) -> Any:
    """Tipos do driver para Python: neo4j.time.Date -> datetime.date. Os demais (str, int, float) ja sao nativos."""
    return value.to_native() if hasattr(value, "to_native") else value


def compare(expected: dict[str, Any], stored: dict[str, Any] | None, descricao: bool = False) -> list[str]:
    """Divergencias de um no, so com o nome da coluna e o tipo (nunca o valor da linha)."""
    if stored is None:
        return ["sem no"]
    reserved = RESERVED | ({"_descricao"} if descricao else set())
    got = {k: native(v) for k, v in stored.items() if k not in reserved}
    out = [f"faltando:{c}" for c in sorted(set(expected) - set(got))]
    out += [f"a mais:{c}" for c in sorted(set(got) - set(expected))]
    for column in sorted(set(expected) & set(got)):
        a, b = expected[column], got[column]
        if type(a) is not type(b):
            out.append(f"tipo:{column} ({type(a).__name__} != {type(b).__name__})")
        elif a != b:
            out.append(f"valor:{column}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", help="caminho do akme.yml do projeto carregado")
    parser.add_argument("--n", type=int, default=200, help="linhas sorteadas por fonte")
    parser.add_argument("--seed", type=int, default=42, help="semente do sorteio")
    args = parser.parse_args()
    missing = [v for v in ("AKME_NEO4J_URI", "AKME_NEO4J_USER", "AKME_NEO4J_PASSWORD") if not os.environ.get(v)]
    if missing:
        print(f"defina no ambiente: {', '.join(missing)}")
        return 2
    project = Project(Path(args.config).resolve().parent)
    plan = build_plan(project)
    if plan.problems:
        print("o plano tem problemas; a carga seria recusada:", *plan.problems, sep="\n  ")
        return 2
    driver = neo4j.GraphDatabase.driver(os.environ["AKME_NEO4J_URI"],
                                        auth=(os.environ["AKME_NEO4J_USER"], os.environ["AKME_NEO4J_PASSWORD"]))
    adapter = load_adapter(project.adapter_name, project.adapter_options())
    rng = random.Random(args.seed)
    total_rows = total_cells = total_div = skipped = 0
    try:
        driver.verify_connectivity()
        for src in sorted(plan.sources, key=lambda s: s.source):
            if not src.key:
                # lacuna de cobertura visivel: fonte do plano sem chave nao vira no e nao e conferida
                print(f"{src.source} (:{src.label}): PULADA, sem chave no plano; nenhuma linha conferida")
                skipped += 1
                continue
            rows, seen = sample(adapter, src.source, src.key, args.n, rng)
            expected: dict[str, dict[str, Any]] = {}
            kinds: Counter[str] = Counter()
            for r in rows:
                identity = node_id([r[c] for c in src.key])
                if identity in expected:
                    # duas linhas sorteadas com o mesmo _id virariam um no so: divergencia, nunca juntar em silencio
                    kinds["_id repetido na amostra"] += 1
                    continue
                expected[identity] = {c: convert(src.types.get(c, "string"), v) for c, v in r.items() if filled(v)}
                if not src.own_name or not filled(r.get("name")):  # legenda gravada pelo akme
                    expected[identity]["name"] = caption(src.label, [r[c] for c in src.key],
                                                         r.get(src.caption) if src.caption else None,
                                                         src.caption_alone)
            records = driver.execute_query(
                f"UNWIND $ids AS id MATCH (n:`{src.label.replace('`', '``')}` {{_id: id}}) WHERE n._projeto = $p "
                "RETURN id, collect(properties(n)) AS ns", {"ids": list(expected), "p": project.name}, routing_="r",
                database_=os.environ.get("AKME_NEO4J_DATABASE") or None).records
            found = {r["id"]: r["ns"] for r in records}
            for identity, props in expected.items():
                nodes = found.get(identity, [])
                problems = ["no repetido"] if len(nodes) > 1 else compare(props, nodes[0] if nodes else None, plan.descricao)
                kinds.update(p.split(" (")[0] for p in problems)
                total_cells += len(props)
            divergent = sum(kinds.values())
            total_rows += len(rows)
            total_div += divergent
            print(f"{src.source} (:{src.label}): {len(expected)} de {seen} linha(s) conferidas, "
                  f"{sum(len(p) for p in expected.values())} celula(s), {divergent} divergencia(s)"
                  + (f": {dict(kinds)}" if kinds else ""))
    finally:
        adapter.close()
        driver.close()
    print(f"TOTAL: {total_rows} linha(s), {total_cells} celula(s) conferidas, {total_div} divergencia(s) "
          f"(n={args.n}, seed={args.seed})" + (f"; {skipped} fonte(s) pulada(s) sem chave" if skipped else ""))
    return 1 if total_div else 0


if __name__ == "__main__":
    sys.exit(main())
