"""Esquema descritivo do grafo para o LLM, em Markdown: o que cada label, propriedade e aresta significa.

As ferramentas da Neo4j (MCP oficial, neo4j-graphrag) montam o esquema so com nomes e tipos. Este texto leva junto a
definicao das classes, os termos de cada coluna, as metricas e as regras. E puro e deterministico: mesma ontologia e
mesmo plano dao o mesmo texto, byte a byte (sem horario; as unicas contagens sao as do plano). A carga grava o texto
em docs/publish/neo4j_schema.md e na propriedade `esquema` da marca _AkmeProjeto.
"""
from __future__ import annotations

from typing import Any

from ..ontology import classes, is_metric_class, load_content, load_graph, relations
from ..project import Project
from .contracts import fanout_sources
from .neo4j_onto import join_labels
from .neo4j_plan import Plan

SCHEMA_QUERY = "MATCH (p:_AkmeProjeto {projeto: $projeto}) RETURN p.esquema"


# como o `_id` e montado, igual nos dois modos de `_descricao`
ID_TEXT = ("valores da chave unidos por `/`, cada um com percent-encoding: `Sao Paulo` vira `Sao%20Paulo`; para "
           "filtrar, use a coluna original, nao `_id`")

def _one_line(text: Any) -> str:
    return " ".join(str(text or "").split())


def _metric_lines(content: dict[str, Any], contracts: list[dict[str, Any]], source: str, g: Any,
                  definitions: dict[str, str], labels: dict[str, str]) -> list[str]:
    """Metricas cujo mapping (papel metric) le esta fonte, na ordem do content.yml."""
    terms = {t["name"]: t for t in content["terms"]}
    out = []
    for m in content["mappings"]:
        term = terms.get(m.get("term"))
        if m.get("source") != source or m.get("role") != "metric" or term is None:
            continue
        cls = term.get("class") or ""
        head = f"metrica `{cls}` (termo `{term['name']}`)" if cls and is_metric_class(g, cls) else f"metrica do termo `{term['name']}`"
        parts = [_one_line(definitions.get(cls) or term.get("definition"))]
        if m.get("expression"):
            parts.append(f"expressao (SQL da origem, sobre as colunas deste label): `{_one_line(m['expression'])}`")
        parts += [f"{label} {_one_line(term[key])}" for key, label in (("unit", "unidade"), ("grain", "grao"), ("additivity", "aditividade"))
                  if term.get(key)]
        if term.get("non_additive_over"):
            parts.append("nao somar sobre: " + ", ".join(term["non_additive_over"]))
        fan = fanout_sources(contracts, source)
        if fan:
            parts.append("nao somar apos juntar com: " + ", ".join(join_labels(fan, labels)))
        out.append(f"  - {head}: " + "; ".join(p for p in parts if p))
    return out


def column_terms(content: dict[str, Any], source: str) -> dict[str, list[str]]:
    """Coluna -> textos "termo `x`: definicao; sinonimos: ..." dos mappings da fonte (igual no esquema e no guia)."""
    terms = {t["name"]: t for t in content["terms"]}
    mapped: dict[str, list[str]] = {}
    for m in content["mappings"]:
        term = terms.get(m.get("term"))
        if m.get("source") == source and m.get("column") and term is not None:
            text = f"termo `{term['name']}`: {_one_line(term.get('definition'))}"
            if term.get("synonyms"):
                text += "; sinonimos: " + ", ".join(term["synonyms"])
            mapped.setdefault(m["column"], []).append(text)
    return mapped


def llm_schema(project: Project, plan: Plan) -> str:
    """Texto Markdown do esquema, sem acento (gerado pelo codigo). So le ontologia, content.yml e o plano."""
    g = load_graph(project.schema_path)
    content = load_content(project)
    contracts = {c["relation"]: c for c in content["relation_contracts"]}
    definitions = {c["name"]: c["comment"] for c in classes(g)}
    rels = {r["name"]: r for r in relations(g)}
    labels = {s.source: s.label for s in plan.sources}
    example = min(labels.values()) if labels else "Label"

    lines = [f"# Esquema do grafo do projeto {plan.project} no Neo4j", "",
             "Gerado pelo akme a partir da ontologia aprovada e do plano da carga. Leia antes de escrever Cypher.", ""]
    if plan.problems:
        lines += ["ATENCAO: o plano tem problemas e a carga seria recusada; este texto descreve o que seria gravado.", ""]
    lines += [
        "## Como consultar", "",
        "- Labels do akme que NAO sao dados: `Conceito` (um no por classe da ontologia, com `definicao`), "
        "`Termo` (termos do negocio, ligados ao seu Conceito por `TEM_TERMO`) e `_AkmeProjeto` (marca do projeto; "
        "guarda este esquema em `esquema`).",
        "- Arestas de dado tem como tipo o nome exato da relacao na ontologia (`[:feitoPorCliente]`). A camada de "
        "ontologia e um espelho do schema.ttl: as setas entre `Conceito` tem todas o tipo `RELACAO_ONTOLOGIA`, com o "
        "nome da relacao em `nome` (mais `rotulo`, `definicao`, `inversa`, `multiplicidade` e `publicada_nos_dados`; a "
        "inversa de um contrato tem `inversa_de`); `SUBCLASSE_DE` liga subclasse a classe. Para ler a ontologia: "
        "`MATCH (a:Conceito)-[r:RELACAO_ONTOLOGIA]->(b:Conceito) RETURN a.nome, r.nome, b.nome`. Toda contagem de dados "
        f"usa o label do dado, como `(:{example})`, ou filtra `WHERE NOT n:Conceito`.",
        *(["- `_id`, `_projeto`, `_carga` e `_descricao` sao propriedades do akme, nao colunas da origem: `_id` e a "
           f"chave ({ID_TEXT}), `_projeto` o projeto, `_carga` a data da carga e `_descricao` a definicao da classe (no "
           "no) ou a definicao da relacao (na aresta; ou o rotulo, quando a relacao nao tem definicao)."]
          if plan.descricao else
          ["- `_id`, `_projeto` e `_carga` sao propriedades do akme, nao colunas da origem: `_id` e a chave "
           f"({ID_TEXT}), `_projeto` o projeto e `_carga` a data da carga. Nos e arestas de dado nao tem `_descricao`: "
           "a definicao de cada classe e relacao esta neste esquema e na propriedade `definicao` do `Conceito` "
           "(`MATCH (c:Conceito {nome: 'Label'}) RETURN c.definicao`)."]),
        "- `name` e a legenda que o akme grava em todo no para o Neo4j Browser (label, inicio da chave e uma coluna "
        "descritiva), nao uma coluna da origem; nao use em filtros. Quando a fonte tem coluna `name`, vale a da origem.",
        f"- Este esquema fica no banco: `{SCHEMA_QUERY}`.",
        "- Propriedade sem tipo declarado e texto (string), mesmo quando parece numero. Celula vazia na origem nao "
        "vira propriedade.",
        "", "## Labels de dado", ""]

    by_label = sorted(plan.sources, key=lambda s: s.label)
    for src in by_label:
        lines += [f"### {src.label}", ""]
        if definitions.get(src.label):
            lines.append(f"- definicao: {_one_line(definitions[src.label])}")
        lines.append(f"- fonte: `{src.source}`; nos previstos: {plan.nodes.get(src.label, 0)}")
        lines.append("- chave: " + (", ".join(f"`{c}`" for c in src.key) if src.key else "nenhuma"))
        mapped = column_terms(content, src.source)
        lines.append("- propriedades:")
        for column in sorted(src.columns):
            entry = f"  - `{column}` ({src.types.get(column, 'string')})"
            if column in mapped:
                entry += ": " + " | ".join(sorted(mapped[column]))
            lines.append(entry)
        out_edges = sorted((e for e in plan.edges if e.domain == src.label), key=lambda e: e.relation)
        if out_edges:
            lines.append("- relacoes que saem:")
            for e in out_edges:
                info, contract = rels.get(e.relation, {}), contracts.get(e.relation, {})
                parts = [contract.get("multiplicity") or "multiplicidade nao declarada"]
                if info.get("label"):
                    parts.append(f"rotulo \"{_one_line(info['label'])}\"")
                if info.get("comment"):
                    parts.append(f"definicao: {_one_line(info['comment'])}")
                inverse = contract.get("inverse_of") or next(iter(info.get("inverse_of") or []), "")
                if inverse and inverse in plan.relationships:
                    parts.append(f"inversa: {inverse} (tem aresta propria no grafo: `[:{inverse}]`)")
                elif inverse:
                    parts.append(f"inversa: {inverse} (sem aresta propria; e esta aresta lida ao contrario: "
                                 f"`(:{e.range})<-[:{e.relation}]-(:{e.domain})`)")
                parts.append(f"{plan.relationships.get(e.relation, 0)} aresta(s)")
                lines.append(f"  - `(:{e.domain})-[:{e.relation}]->(:{e.range})`: " + "; ".join(parts))
        metrics = _metric_lines(content, list(contracts.values()), src.source, g, definitions, labels)
        if metrics:
            lines += ["- metricas:", *metrics]
        lines.append("")

    if plan.relations_not_published:
        lines += ["Relacoes da ontologia sem aresta no grafo (nao use em consultas de dados): "
                  + ", ".join(sorted(plan.relations_not_published)), ""]

    if content["glossary"]:
        lines += ["## Glossario", ""]
        for item in content["glossary"]:
            entry = f"- {item.get('acronym')}: {_one_line(item.get('meaning'))}"
            if item.get("convention"):
                entry += f" (convencao: {_one_line(item['convention'])})"
            lines.append(entry)
        lines.append("")
    if content["constraints"]:
        lines += ["## Regras", ""]
        for rule in content["constraints"]:
            where = ", ".join(x for x in (f"termo {rule['term']}" if rule.get("term") else "",
                                           f"severidade {rule['severity']}" if rule.get("severity") else "") if x)
            lines.append(f"- {rule.get('id', '')}" + (f" ({where})" if where else "") + f": {_one_line(rule.get('rule'))}")
        lines.append("")
    if content["precedence"]:
        lines += ["## Precedencias", ""]
        for item in content["precedence"]:
            entry = f"- {item.get('topic')}: vale {item.get('winner')} sobre {item.get('over')}"
            if item.get("reason"):
                entry += f" ({_one_line(item['reason'])})"
            lines.append(entry)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
