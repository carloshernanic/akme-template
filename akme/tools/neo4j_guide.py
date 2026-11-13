"""Tutorial do projeto no Neo4j Browser (`:guide <url>`), gerado a cada `publish --target neo4j`: so navegacao, em ate
seis paginas curtas.

O guia e HTML no formato que o Browser 2026.10 aceita: `<article class="guide">` com `<carousel>` e um `<slide>` por
pagina; blocos `<pre mode="cypher" class="code runnable">` rodam com um clique. E puro e deterministico: mesmo plano da
o mesmo texto, byte a byte (sem horario; as unicas contagens sao as do plano). Leva so nomes de label, contagens do
plano e consultas de navegacao; nenhum valor lido da origem.
"""
from __future__ import annotations

import csv
import html
import io
import re
from typing import Any

from .neo4j_plan import RESERVED_LABELS, Plan

GUIDE_ROUTE = "/neo4j/guia"
REVIEW_PORT = 8765
GUIDE_FILE = "neo4j_guia.html"
QUERIES_FILE = "neo4j_consultas.csv"
USAGE_GUIDE = "reports/docs_exp_neo4j/README.md"
AURA_SECTION = "Perguntas em portugues pelo Aura console"

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


def _cy(identifier: str) -> str:
    """Identificador no Cypher do guia: crases so quando o nome precisa."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        return identifier
    return "`" + identifier.replace("`", "``") + "`"


def one_record_query(label: str) -> str:
    return f"MATCH (n:{_cy(label)}) WITH n LIMIT 1\nMATCH p = (n)--(m)\nWHERE NOT m:Conceito\nRETURN p LIMIT 25"


def _e(text: Any) -> str:
    return html.escape(" ".join(str(text or "").split()), quote=False)


def _pre(query: str) -> str:
    return f'<pre mode="cypher" class="code runnable">{html.escape(query.strip(), quote=False)}</pre>'


def _count(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _labels(plan: Plan) -> list[str]:
    return sorted(s.label for s in plan.sources)


def _slides(plan: Plan, apoc: bool | None) -> list[str]:
    slides = []
    # a. o que tem aqui
    parts = ["<h3>O que tem aqui</h3>",
             f"<p>O grafo do projeto <b>{_e(plan.project)}</b>: cada bolinha e um registro do cliente, e a cor diz a "
             "classe.</p>"]
    if plan.problems:
        parts.append("<p><b>Atencao:</b> o plano tem problemas e a carga seria recusada.</p>")
    parts.append("<ul>" + "".join(f"<li><code>{_e(label)}</code>: {_count(n)}</li>" for label, n in plan.nodes.items())
                 + "</ul>")
    slides.append("\n".join(parts))

    # b. a ontologia
    parts = ["<h3>A ontologia</h3>",
             "<p>As classes e relacoes do projeto, com os nomes do schema.ttl. Nada aqui e dado do cliente.</p>"]
    if apoc is not False:
        parts.append(("<p>Com o APOC:</p>" if apoc is None else "") + _pre(map_query(plan.project, apoc=True)))
    if apoc is not True:
        parts.append("<p>Sem o APOC, clique em <code>RELACAO_ONTOLOGIA</code> na legenda e escolha <code>nome</code>:</p>"
                     + _pre(map_query(plan.project, apoc=False)))
    slides.append("\n".join(parts))

    # c. os dados
    slides.append("\n".join([
        "<h3>Os dados</h3>",
        "<p>Uma bolinha por classe e uma seta por tipo de ligacao que existe nos dados, calculadas pelo Neo4j.</p>",
        _pre(SCHEMA_VIEW_QUERY)]))

    # d. explorar
    parts = ["<h3>Explorar</h3>", "<p>Um registro de cada classe e tudo o que esta ligado a ele.</p>"]
    parts += [f"<p><code>{_e(label)}</code></p>" + _pre(one_record_query(label)) for label in _labels(plan)]
    slides.append("\n".join(parts))

    # e. como navegar
    slides.append("\n".join([
        "<h3>Como navegar</h3>",
        "<ul>",
        "<li>Na lateral (icone de banco), clique num tipo de relacao: vem setas com as duas pontas.</li>",
        "<li>Dois cliques numa bolinha trazem os vizinhos dela.</li>",
        ("<li>Um clique mostra as colunas no painel da direita; <code>_descricao</code> traz a definicao da classe.</li>"
         if plan.descricao else
         "<li>Um clique mostra as colunas no painel da direita. A definicao de cada classe esta no slide A ontologia "
         "(no <code>Conceito</code>, em <code>definicao</code>).</li>"),
        "<li>Seta <code>RELACAO_ONTOLOGIA</code> = relacao da ontologia; o nome do TTL esta em <code>nome</code>. Para "
        "ver o nome na seta: no painel Results overview, clique no chip <code>RELACAO_ONTOLOGIA</code> e escolha "
        "<code>nome</code> como legenda (o Browser guarda a escolha). O slide A ontologia ja desenha com os nomes.</li>",
        "</ul>"]))

    # f. perguntas em portugues
    slides.append("\n".join([
        "<h3>Perguntas em portugues</h3>",
        "<p>No console da Aura (console.neo4j.io), o Query tem um gerador de Cypher a partir de texto, ligado a este "
        "banco local; ele precisa do APOC. A conexao do console a um banco local funcionou num teste; o gerador de "
        "Cypher nao foi testado, nem o AuraDB (o banco na nuvem): o akme so foi testado com o Neo4j local em Docker.</p>",
        f"<p>Passo a passo e cuidados com dado de cliente: secao \"{AURA_SECTION}\" de <code>{USAGE_GUIDE}</code>.</p>"]))
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
    """(nome, consulta) das consultas de navegacao do guia, na ordem dos slides."""
    out = [("1. A ontologia", map_query(plan.project, apoc=apoc is not False)), ("2. Os dados", SCHEMA_VIEW_QUERY)]
    return out + [(f"Explorar: {label}", one_record_query(label)) for label in _labels(plan)]


def saved_queries_csv(plan: Plan, apoc: bool | None = None) -> str:
    """CSV do painel Queries do Browser 2026.10 (Upload): uma pasta do projeto com as consultas do guia."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["name", "description", "query", "id", "parentId", "isFolder", "isProtected"])
    writer.writerow([f"akme {plan.project}", "", "", 0, "", "true", "false"])
    for i, (title, query) in enumerate(saved_queries(plan, apoc), 1):
        writer.writerow([title, "", query, i, 0, "false", "false"])
    return buf.getvalue()


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
    ] + _stale_lines(port)


def _stale_lines(port: int) -> list[str]:
    from ..review_server import stale_message  # import tardio: review_server importa este modulo

    stale = stale_message(port)
    return [f"  atencao: {stale}"] if stale else []
