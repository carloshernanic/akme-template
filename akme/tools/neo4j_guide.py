"""Tutorial do projeto no Neo4j Browser (`:guide <url>`), gerado a cada `publish --target neo4j`: so navegacao, em
cinco paginas curtas. A primeira ja e um desenho: o mapa das classes e, em grafo pequeno, o grafo inteiro.

O guia e HTML no formato que o Browser 2026.10 aceita: `<article class="guide">` com `<carousel>` e um `<slide>` por
pagina; blocos `<pre mode="cypher" class="code runnable">` rodam com um clique. E puro e deterministico: mesmo plano da
o mesmo texto, byte a byte (sem horario; as unicas contagens sao as do plano). Leva so nomes de label, contagens do
plano e consultas de navegacao; nenhum valor lido da origem.

Junto do guia saem as consultas salvas (CSV do painel Queries) e o estilo (GraSS: uma cor por classe, a camada de
ontologia em cinza e o nome da relacao escrito nas setas RELACAO_ONTOLOGIA).
"""
from __future__ import annotations

import csv
import html
import io
import re
from typing import Any

from .neo4j_plan import RESERVED_LABELS, Plan
from .neo4j_values import ONTOLOGY_TYPE

GUIDE_ROUTE = "/neo4j/guia"
REVIEW_PORT = 8765
GUIDE_FILE = "neo4j_guia.html"
QUERIES_FILE = "neo4j_consultas.csv"
STYLE_FILE = "neo4j_estilo.grass"
USAGE_GUIDE = "reports/docs_exp_neo4j/README.md"
AURA_SECTION = "Perguntas em portugues pelo Aura console"
SMALL_GRAPH = 500  # ate este numero de nos de dado, o guia oferece o grafo inteiro numa consulta (o Browser desenha 1.000)

_META = ", ".join(f"'{m}'" for m in RESERVED_LABELS)
SCHEMA_VIEW_QUERY = ("CALL db.schema.visualization() YIELD nodes, relationships\n"
                     f"RETURN [n IN nodes WHERE NOT n.name IN [{_META}]] AS classes,\n"
                     f"       [r IN relationships WHERE NOT startNode(r).name IN [{_META}]] AS relacoes")


def guide_url(port: int = REVIEW_PORT) -> str:
    return f"http://127.0.0.1:{port}{GUIDE_ROUTE}"


def _literal(text: str) -> str:
    return "'" + str(text).replace("\\", "\\\\").replace("'", "\\'") + "'"


def map_query(project_name: str, apoc: bool) -> str:
    """O mapa da ontologia: todos os Conceito do projeto, as setas RELACAO_ONTOLOGIA e SUBCLASSE_DE. Com APOC, cada
    RELACAO_ONTOLOGIA aparece como seta virtual com o nome da relacao no TTL (apoc.create.vRelationship, nada
    gravado); sem APOC, aparece o tipo RELACAO_ONTOLOGIA e o nome fica na propriedade `nome`."""
    head = (f"MATCH (a:Conceito {{_projeto: {_literal(project_name)}}})\n"
            "OPTIONAL MATCH (a)-[r:RELACAO_ONTOLOGIA|SUBCLASSE_DE]->(b:Conceito)\n")
    if not apoc:
        return head + "RETURN a, r, b"
    return (head + "RETURN a, b, CASE WHEN type(r) = 'RELACAO_ONTOLOGIA'\n"
            "  THEN apoc.create.vRelationship(a, r.nome, {}, b) ELSE r END AS seta")


def whole_graph_query(project_name: str) -> str:
    """Todos os nos de dado do projeto e as arestas entre eles, sem a camada de ontologia. So para grafo pequeno."""
    return (f"MATCH (n) WHERE n._projeto = {_literal(project_name)} AND NOT n:Conceito AND NOT n:Termo\n"
            "OPTIONAL MATCH (n)-[r]->(m)\nRETURN n, r, m")


def without_data_query(project_name: str) -> str:
    return (f"MATCH (c:Conceito {{_projeto: {_literal(project_name)}}}) WHERE NOT c.publicada_nos_dados\n"
            "RETURN c.nome AS conceito, c.tipo AS tipo, c.definicao AS definicao ORDER BY conceito")


def _cy(identifier: str) -> str:
    """Identificador no Cypher do guia: crases so quando o nome precisa."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        return identifier
    return "`" + identifier.replace("`", "``") + "`"


def one_record_query(label: str, linked: bool = True) -> str:
    """O registro mais ligado da classe e os vizinhos dele (um registro qualquer pode nao ter ligacao nenhuma e a
    consulta viria vazia). Classe sem relacao nos dados (`linked` falso): os registros dela, sem setas."""
    if not linked:
        return f"MATCH (n:{_cy(label)})\nRETURN n LIMIT 25"
    return (f"MATCH (n:{_cy(label)}) WITH n ORDER BY COUNT {{ (n)--() }} DESC LIMIT 1\n"
            "MATCH p = (n)--(m)\nWHERE NOT m:Conceito\nRETURN p LIMIT 25")


def _e(text: Any) -> str:
    return html.escape(" ".join(str(text or "").split()), quote=False)


def _pre(query: str) -> str:
    return f'<pre mode="cypher" class="code runnable">{html.escape(query.strip(), quote=False)}</pre>'


def _count(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _labels(plan: Plan) -> list[str]:
    return sorted(s.label for s in plan.sources)


def linked_labels(plan: Plan) -> set[str]:
    """Classes com alguma aresta de dado nesta carga (as outras sao tabelas de referencia soltas)."""
    return ({e.domain for e in plan.edges if plan.relationships.get(e.relation)}
            | {e.range for e in plan.edges if plan.relationships.get(e.relation)})


def is_small(plan: Plan) -> bool:
    return 0 < sum(plan.nodes.values()) <= SMALL_GRAPH


def _slides(plan: Plan, apoc: bool | None) -> list[str]:
    slides = []
    linked = linked_labels(plan)
    # a. o que tem aqui: primeiro o desenho, depois as contagens
    parts = ["<h3>O que tem aqui</h3>",
             f"<p>O grafo do projeto <b>{_e(plan.project)}</b>. Comece pelo mapa: uma bolinha por classe e uma seta "
             "por ligação que existe nos dados.</p>"]
    if plan.problems:
        parts.append("<p><b>Atenção:</b> o plano tem problemas e a carga seria recusada.</p>")
    parts.append(_pre(SCHEMA_VIEW_QUERY))
    if is_small(plan):
        parts.append(f"<p>O grafo é pequeno ({_count(sum(plan.nodes.values()))} registros): dá para ver tudo de uma "
                     "vez. Cada bolinha é um registro, e a cor diz a classe.</p>" + _pre(whole_graph_query(plan.project)))
    parts.append("<p>Registros por classe:</p><ul>" + "".join(
        f"<li><code>{_e(label)}</code>: {_count(n)}" + ("" if label in linked else " (sem ligações)") + "</li>"
        for label, n in plan.nodes.items()) + "</ul>")
    slides.append("\n".join(parts))

    # b. a ontologia
    parts = ["<h3>A ontologia</h3>",
             "<p>As classes e relações do projeto, com os nomes do schema.ttl. Nada aqui é dado do cliente.</p>"]
    if apoc is not False:
        parts.append(("<p>Se o banco tiver o plugin APOC (opcional):</p>" if apoc is None else "")
                     + _pre(map_query(plan.project, apoc=True)))
    if apoc is not True:
        parts.append("<p>Para o nome de cada relação aparecer escrito na seta, importe as cores (página Como "
                     "navegar). Sem as cores, toda seta mostra <code>RELACAO_ONTOLOGIA</code> e o nome fica dentro "
                     "dela, em <code>nome</code>.</p>" + _pre(map_query(plan.project, apoc=False)))
    if plan.concepts_without_data:
        parts.append(f"<p>{_count(len(plan.concepts_without_data))} conceito(s) estão na ontologia e ainda não têm "
                     "registros no grafo:</p>" + _pre(without_data_query(plan.project)))
    slides.append("\n".join(parts))

    # c. explorar
    parts = ["<h3>Explorar</h3>", "<p>O registro mais ligado de cada classe e tudo o que está ligado a ele.</p>"]
    parts += [f"<p><code>{_e(label)}</code>" + ("" if label in linked else " (sem ligações: só os registros)") + "</p>"
              + _pre(one_record_query(label, label in linked)) for label in _labels(plan)]
    slides.append("\n".join(parts))

    # d. como navegar
    slides.append("\n".join([
        "<h3>Como navegar</h3>",
        "<ul>",
        "<li>Dois cliques numa bolinha trazem os vizinhos dela.</li>",
        ("<li>Um clique mostra as colunas no painel da direita; <code>_descricao</code> traz a definição da classe.</li>"
         if plan.descricao else
         "<li>Um clique mostra as colunas no painel da direita. A definição de cada classe está na página A ontologia "
         "(no <code>Conceito</code>, em <code>definicao</code>).</li>"),
        "<li>Na lateral (ícone de banco), clique num tipo de relação: vêm setas com as duas pontas. Clicar numa classe "
        "traz só bolinhas soltas.</li>",
        f"<li>Cores fixas por classe e o nome nas setas da ontologia: rode <code>:style</code>, Upload, e escolha "
        f"<code>docs/publish/{STYLE_FILE}</code> (uma vez por navegador).</li>",
        "<li>Seta <code>RELACAO_ONTOLOGIA</code> = relação da ontologia; o nome do TTL está em <code>nome</code>.</li>",
        "</ul>"]))

    # e. perguntas em portugues
    slides.append("\n".join([
        "<h3>Perguntas em português</h3>",
        "<p>No console da Aura (console.neo4j.io), o Query tem um gerador de Cypher a partir de texto, ligado a este "
        "banco local; ele precisa do APOC. A conexão do console a um banco local funcionou num teste; o gerador de "
        "Cypher não foi testado, nem o AuraDB (o banco na nuvem): o akme só foi testado com o Neo4j local em Docker.</p>",
        f"<p>Passo a passo e cuidados com dado de cliente: seção \"{AURA_SECTION}\" de <code>{USAGE_GUIDE}</code>.</p>"]))
    return slides


def guide_html(plan: Plan, apoc: bool | None = None) -> str:
    """HTML do guia do Neo4j Browser. `apoc`: o banco tem APOC (depois da carga) ou None (dry-run, sem banco: o mapa
    vem nas duas formas)."""
    body = "".join(f'<slide class="row-fluid"><div class="col-sm-12">\n{s}\n</div></slide>\n' for s in _slides(plan, apoc))
    return ('<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8">'
            f"<title>Grafo {_e(plan.project)}</title></head><body>\n"
            '<article class="guide"><carousel class="deck container-fluid">\n'
            f"{body}</carousel></article>\n</body></html>\n")


def saved_queries(plan: Plan, apoc: bool | None = None) -> list[tuple[str, str]]:
    """(nome, consulta) das consultas de navegacao do guia, na ordem das paginas."""
    linked = linked_labels(plan)
    out = [("1. O mapa das classes", SCHEMA_VIEW_QUERY)]
    if is_small(plan):
        out.append(("2. O grafo inteiro", whole_graph_query(plan.project)))
    out.append(("3. A ontologia", map_query(plan.project, apoc=apoc is not False)))
    if plan.concepts_without_data:
        out.append(("4. Conceitos sem dados", without_data_query(plan.project)))
    return out + [(f"Explorar: {label}", one_record_query(label, label in linked)) for label in _labels(plan)]


def saved_queries_csv(plan: Plan, apoc: bool | None = None) -> str:
    """CSV do painel Queries do Browser 2026.10 (Upload): uma pasta do projeto com as consultas do guia."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["name", "description", "query", "id", "parentId", "isFolder", "isProtected"])
    writer.writerow([f"akme {plan.project}", "", "", 0, "", "true", "false"])
    for i, (title, query) in enumerate(saved_queries(plan, apoc), 1):
        writer.writerow([title, "", query, i, 0, "false", "false"])
    return buf.getvalue()


# cores das classes, em ordem fixa: a classe i (por nome) recebe a cor i, em ciclo
_PALETTE = ["#4C8EDA", "#F79767", "#57C7E3", "#F16667", "#8DCC93", "#FFC454", "#C990C0", "#569480", "#DA7194",
            "#D9C8AE", "#ECB5C9", "#6DCE9E"]
_GREY = "#C8CDD3"  # camada de ontologia e marca do projeto
DATA_DIAMETER = 70  # px; cabe um nome curto na bolinha
ONTOLOGY_DIAMETER = 90  # px; poucos nos, nome inteiro da classe


def _grass_node(label: str, color: str, diameter: int) -> str:
    return f"node.{label} {{\n  color: {color};\n  diameter: {diameter}px;\n  caption: \"{{name}}\";\n}}\n"


def style_grass(plan: Plan) -> str:
    """Estilo do Neo4j Browser (GraSS, `:style` > Upload): uma cor fixa por classe de dado, a camada de ontologia e a
    marca em cinza, legenda `name` em todo no e, nas setas RELACAO_ONTOLOGIA, o nome da relacao. Deterministico.
    So as propriedades que o Browser 2026.10 importa: caption, color, diameter e shaft-width (conferido no Browser).
    Classe com nome que nao e identificador simples fica com a cor padrao (o seletor do GraSS nao a alcanca)."""
    simple = [label for label in _labels(plan) if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label)]
    out = [_grass_node(label, _PALETTE[i % len(_PALETTE)], DATA_DIAMETER) for i, label in enumerate(simple)]
    out += [_grass_node(label, _GREY, ONTOLOGY_DIAMETER) for label in RESERVED_LABELS]
    out.append(f"relationship.{ONTOLOGY_TYPE} {{\n  caption: \"{{nome}}\";\n}}\n")
    return "\n".join(out)


def guide_lines(port: int = REVIEW_PORT) -> list[str]:
    """Como abrir o tutorial do projeto no Neo4j Browser (mensagem final da CLI, na carga e no dry-run)."""
    url = guide_url(port)
    return [
        "",
        "Tutorial do projeto no Neo4j Browser (docs/publish/neo4j_guia.html):",
        "  1. ligue o servidor local: uv run akme review (serve o guia em " + url + ")",
        f"  2. no Neo4j Browser, rode :guide {url}",
        "  para abrir sozinho a cada conexao, no docker run do Neo4j:",
        f"     --env NEO4J_browser_post__connect__cmd='guide {url}'",
        f"  consultas salvas: docs/publish/{QUERIES_FILE} (Browser, Queries, Upload)",
        f"  cores por classe e nome nas setas da ontologia: docs/publish/{STYLE_FILE} (Browser, rode :style, Upload)",
    ] + _stale_lines(port)


def _stale_lines(port: int) -> list[str]:
    from ..review_server import stale_message  # import tardio: review_server importa este modulo

    stale = stale_message(port)
    return [f"  atencao: {stale}"] if stale else []
