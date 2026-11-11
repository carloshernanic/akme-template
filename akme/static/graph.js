/* Vista Ontologia: grafo (D3 so para o layout), arvore de classes, painel de detalhe e resumo do validate.
   window.AkmeGraph.init(data) na carga; update(data) quando a API atualiza; show() ao voltar para a aba. */
(function () {
"use strict";
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ROOTS = ["Entity", "Relation", "Rule", "Metric"];
const ICONS = {
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l10 18H2L12 3zM12 10v4M12 17h.01"/></svg>',
};
let DATA = null, selected = null, graph = null, focus = null, showAll = false;
const expanded = new Set(), openTree = new Set();
const POS = new Map();
let lastT = null, spawnFrom = null;
const LAYOUTS = [["force", "Força"], ["radial", "Radial"], ["pyramid", "Pirâmide"], ["tree", "Árvore"]];
let layout = "force";
try { const saved = localStorage.getItem("akme-layout"); if (LAYOUTS.some(([k]) => k === saved)) layout = saved; } catch (e) {}
const MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 480;



function termsOf(cls) { return DATA.terms.filter((t) => t.class === cls); }
function mappingsOf(term) { return DATA.mappings.filter((m) => m.term === term); }
function relationsOf(cls) { return DATA.relations.filter((r) => r.domain.includes(cls) || r.range.includes(cls)); }

function renderStats() {
  const v = DATA.validation;
  const cov = v && v.coverage && v.coverage.available ? v.coverage : null;
  const pit = v ? v.pitfalls.length : null;
  const cards = [
    { label: "classes", value: DATA.classes.length },
    { label: "relações", value: DATA.relations.length },
    { label: "termos", value: DATA.terms.length },
    { label: "mapeamentos", value: DATA.mappings.length },
    { label: "cobertura de colunas", value: cov ? Math.round(cov.ratio * 100) + "%" : "—" },
    { label: "armadilhas", value: pit === null ? "—" : pit },
  ];
  $("#stats").innerHTML = cards.map((c) => `<div class="stat"><div class="value">${esc(c.value)}</div><div class="label">${esc(c.label)}</div></div>`).join("");
}

const CARET = '<svg viewBox="0 0 12 12" fill="currentColor"><path d="M4 2l5 4-5 4z"/></svg>';
function cls(name) { return DATA.classes.find((c) => c.name === name); }
function parentsOf(name) { return ((cls(name) || {}).subclass_of || []).filter((p) => cls(p)); }
function childrenOf(name) { return DATA.classes.filter((c) => c.subclass_of.includes(name)).map((c) => c.name); }
function relEdges() {
  const out = [], seen = new Set();
  DATA.relations.forEach((r) => {
    if (seen.has(r.name)) return;
    r.inverse_of.forEach((i) => seen.add(i));
    r.domain.forEach((d) => r.range.forEach((g) => cls(d) && cls(g) && out.push({ source: d, target: g, label: r.name })));
  });
  return out;
}
function neighborsOf(name) {
  const n = new Set([...parentsOf(name), ...childrenOf(name)]);
  relEdges().forEach((e) => { if (e.source === name) n.add(e.target); if (e.target === name) n.add(e.source); });
  n.delete(name);
  if (!ROOTS.includes(name)) ROOTS.forEach((r) => n.delete(r));
  return n;
}
function lineage(name) {
  const path = [], seen = new Set();
  let cur = name;
  while (cur && !seen.has(cur) && cls(cur)) { seen.add(cur); path.unshift(cur); cur = parentsOf(cur)[0]; }
  return path;
}
function defaultFocus() {
  if (selected) return selected;
  const candidates = DATA.classes.filter((c) => !ROOTS.includes(c.name));
  const pool = candidates.length ? candidates : DATA.classes;
  if (!pool.length) return null;
  return pool.reduce((best, c) => (neighborsOf(c.name).size > neighborsOf(best.name).size ? c : best)).name;
}

function renderNav(filter = "") {
  const q = filter.trim().toLowerCase();
  const matchClass = (c) => !q || [c.name, c.label, c.comment, ...termsOf(c.name).map((t) => t.name)].some((x) => String(x).toLowerCase().includes(q));
  const children = (parent) => DATA.classes.filter((c) => c.subclass_of.includes(parent));
  const visible = (c) => matchClass(c) || children(c.name).some(visible);
  const item = (c, depth) => {
    const kids = children(c.name).filter(visible);
    const open = !!q || openTree.has(c.name);
    return `<li><div class="tree-row" style="padding-left:${depth * 14}px">
      <button type="button" class="caret${kids.length ? "" : " leaf"}" data-toggle="${esc(c.name)}" aria-expanded="${open}" aria-label="${open ? "Recolher" : "Expandir"} ${esc(c.label || c.name)}" ${kids.length ? "" : 'tabindex="-1"'}>${CARET}</button>
      <button type="button" class="nav-item" data-class="${esc(c.name)}" aria-pressed="${selected === c.name}" title="${esc(c.label || c.name)}">
      <span>${esc(c.label || c.name)}</span><span class="count">${termsOf(c.name).length || ""}</span></button></div>
      ${kids.length && open ? `<ul>${kids.map((k) => item(k, depth + 1)).join("")}</ul>` : ""}</li>`;
  };
  const roots = DATA.classes.filter((c) => ROOTS.includes(c.name) || !c.subclass_of.length);
  const gl = DATA.glossary.filter((g) => !q || [g.acronym, g.meaning].some((x) => String(x).toLowerCase().includes(q)));
  $("#nav").innerHTML = `<div class="group-label">Classes</div><ul>${roots.filter(visible).map((c) => item(c, 0)).join("")}</ul>
    ${gl.length ? `<div class="group-label" style="margin-top:12px">Glossário</div><ul>${gl.map((g) => `<li class="nav-item" style="cursor:default"><span class="mono">${esc(g.acronym)}</span><span class="secondary label">${esc(g.meaning)}</span></li>`).join("")}</ul>` : ""}`;
  $("#nav").querySelectorAll("button[data-class]").forEach((b) => b.addEventListener("click", () => select(b.dataset.class)));
  $("#nav").querySelectorAll("button[data-toggle]").forEach((b) => b.addEventListener("click", () => {
    const n = b.dataset.toggle;
    openTree.has(n) ? openTree.delete(n) : openTree.add(n);
    renderNav($("#search").value);
  }));
}
$("#search").addEventListener("input", (e) => renderNav(e.target.value));

function renderPanel() {
  const el = $("#panel");
  if (!selected) {
    el.innerHTML = `<div class="panel-head"><div class="rv-empty"><b>Nenhuma classe escolhida</b><span>Escolha uma classe no grafo ou na lista para ver termos, mapeamentos, restrições e glossário ligados a ela.</span></div></div>`;
    return;
  }
  const c = DATA.classes.find((x) => x.name === selected);
  const terms = termsOf(c.name);
  const rels = relationsOf(c.name);
  const cons = DATA.constraints.filter((k) => terms.some((t) => t.name === k.term));
  const text = (terms.map((t) => t.name + " " + t.definition).join(" ") + " " + c.comment).toUpperCase();
  const gl = DATA.glossary.filter((g) => text.includes(String(g.acronym).toUpperCase()));
  const prec = DATA.precedence.filter((p) => terms.some((t) => String(p.topic).toLowerCase().includes(t.name.replace("_", " ")) || String(p.topic).toLowerCase().includes(t.name)));
  el.innerHTML = `
    <div class="panel-head">
      <span class="kind">${esc(c.subclass_of.length ? "subclasse de " + c.subclass_of.join(", ") : "classe raiz")}</span>
      <h2 class="h3" style="font-weight:600">${esc(c.label || c.name)}</h2>
      <p class="p secondary">${esc(c.comment || "sem descrição")}</p>
      <code class="label tertiary">${esc(c.iri)}</code>
    </div>
    <div class="panel-section"><h3>Termos e mapeamentos</h3>
      ${terms.length ? terms.map((t) => `<div><div class="row"><span style="font-weight:600">${esc(t.name)}</span>${t.synonyms && t.synonyms.length ? `<span class="label tertiary">${esc(t.synonyms.join(", "))}</span>` : ""}</div>
        <div class="p secondary">${esc(t.definition)}</div>
        <div class="badges" style="margin-top:4px">${mappingsOf(t.name).map((m) => `<span class="badge ${m.role === "metric" ? "" : "badge-alt"} mono" title="${esc(m.note || m.expression || "")}">${esc(m.source)}.${esc(m.column)}</span>`).join("") || '<span class="badge badge-outline">sem mapeamento</span>'}${t.unit ? `<span class="badge badge-outline">${esc(t.unit)}</span><span class="badge badge-outline">grão: ${esc(t.grain || "")}</span><span class="badge badge-outline">${esc(t.additivity || "")}</span>` : ""}</div></div>`).join("") : '<p class="p secondary">Nenhum termo ligado a esta classe.</p>'}
    </div>
    <div class="panel-section"><h3>Hierarquia</h3>
      <div class="row"><span class="k">superclasse</span><span>${parentsOf(c.name).map(classLink).join(", ") || '<span class="tertiary">nenhuma</span>'}</span></div>
      <div class="row"><span class="k">subclasses</span><span>${childrenOf(c.name).map(classLink).join(", ") || '<span class="tertiary">nenhuma</span>'}</span></div>
    </div>
    <div class="panel-section"><h3>Relações</h3>
      ${rels.length ? rels.map((r) => `<div class="rel-item"><span class="mono">${esc(r.name)}</span><span class="secondary">${r.domain.map(classLink).join(", ")} para ${r.range.map(classLink).join(", ")}</span>${relContract(r)}</div>`).join("") : '<p class="p secondary">Nenhuma relação.</p>'}
    </div>
    ${cons.length ? `<div class="panel-section"><h3>Restrições</h3>${cons.map((k) => `<div class="row"><span class="badge ${k.severity === "error" ? "badge-error" : "badge-warning"}">${esc(k.id || k.severity || "regra")}</span><span>${esc(k.rule)}</span></div>`).join("")}</div>` : ""}
    ${gl.length ? `<div class="panel-section"><h3>Glossário</h3>${gl.map((g) => `<div class="row"><span class="k mono">${esc(g.acronym)}</span><span>${esc(g.meaning)}${g.convention ? ` <span class="tertiary">(${esc(g.convention)})</span>` : ""}</span></div>`).join("")}</div>` : ""}
    ${prec.length ? `<div class="panel-section"><h3>Precedência</h3>${prec.map((p) => `<div class="p"><b>${esc(p.topic)}</b>: ${esc(p.winner)} prevalece sobre ${esc(p.over)}.<span class="secondary"> ${esc(p.reason || "")}</span></div>`).join("")}</div>` : ""}`;
}

function relContract(r) {
  const c = r.contract;
  if (!c) return '<span class="badge badge-outline">sem contrato</span>';
  const join = c.join ? `${c.join.from.source}.${c.join.from.column} = ${c.join.to.source}.${c.join.to.column}` : (c.no_join_reason || "");
  const inv = c.inverse_of_contract ? `<span class="badge badge-outline">inversa de ${esc(c.inverse_of_contract)}</span>` : "";
  const fan = c.observed && c.observed.fanout ? '<span class="badge badge-warning">fanout</span>' : "";
  const orph = c.observed && c.observed.orphans ? `<span class="badge badge-warning">${c.observed.orphans} orfaos</span>` : "";
  return `<span class="badges"><span class="badge badge-alt mono">${esc(c.multiplicity)}</span><span class="badge badge-outline mono">${esc(join)}</span>${inv}${fan}${orph}</span>`;
}

function classLink(name) {
  const c = cls(name);
  if (!c) return esc(name);
  return `<button type="button" class="link-btn" data-goto="${esc(name)}">${esc(c.label || name)}</button>`;
}
$("#panel").addEventListener("click", (e) => { const b = e.target.closest("[data-goto]"); if (b) select(b.dataset.goto); });

// status da pergunta por extenso, com a cor do ponto
const CQ_STATUS = { approved: ["aprovada", "success"], reserved: ["guardada para o teste", "information"], proposed: ["proposta", "warning"], rejected: ["rejeitada", "error"] };
function cqList() {
  const cqs = DATA.requirements.competency_questions || [];
  if (!cqs.length) return '<div class="rv-empty"><b>Nenhuma pergunta ainda</b><span>As perguntas aparecem aqui depois da etapa 1.</span></div>';
  return `<div class="onto-cqs">${cqs.map((q) => {
    const [txt, dot] = CQ_STATUS[q.status] || [q.status || "", "information"];
    return `<div class="onto-cq"><span class="q">${esc(q.question)}</span><span class="meta"><span class="mono">${esc(q.id)}</span> · <span class="status-dot ${dot}"></span>${esc(txt)}</span></div>`;
  }).join("")}</div>`;
}

function select(name) {
  if (!cls(name)) return;
  selected = name;
  spawnFrom = name;
  focus = name;
  expanded.clear();
  lineage(name).slice(0, -1).forEach((n) => openTree.add(n));
  renderNav($("#search").value);
  renderPanel();
  renderGraph();
}
// Um clique: so mostra as informacoes no painel, sem mexer no grafo.
function inspect(name) {
  if (!cls(name)) return;
  selected = name;
  lineage(name).slice(0, -1).forEach((n) => openTree.add(n));
  renderNav($("#search").value);
  renderPanel();
  if (graph) graph.highlight(selected);
}
$("#graph-all").addEventListener("click", () => { showAll = !showAll; $("#graph-all").setAttribute("aria-pressed", String(showAll)); renderGraph(); });
function renderLayouts() {
  $("#layouts").innerHTML = LAYOUTS.map(([k, label]) => `<button type="button" data-layout="${k}" aria-pressed="${layout === k}">${label}</button>`).join("");
  $("#layouts").querySelectorAll("[data-layout]").forEach((b) => b.addEventListener("click", () => {
    layout = b.dataset.layout;
    try { localStorage.setItem("akme-layout", layout); } catch (e) {}
    renderLayouts();
    renderGraph();
  }));
}
renderLayouts();
$("#graph-reset").addEventListener("click", () => { expanded.clear(); showAll = false; $("#graph-all").setAttribute("aria-pressed", "false"); renderGraph(); });

function renderCrumbs() {
  const path = focus ? lineage(focus) : [];
  $("#crumbs").innerHTML = path.map((n, i) => `${i ? '<span class="sep">/</span>' : ""}<button type="button" data-goto="${esc(n)}" aria-current="${n === focus}">${esc((cls(n) || {}).label || n)}</button>`).join("");
  $("#crumbs").querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => select(b.dataset.goto)));
}

// Arvore geradora a partir de uma raiz (busca em largura sobre as arestas visiveis). Subclasses primeiro, depois relacoes.
// subOnly: so arestas de subclasse (hierarquia pura). Nos nao alcancados viram arvores proprias.
function spanningTree(rootId, nodes, links, subOnly = false) {
  const adj = new Map(nodes.map((n) => [n.id, []]));
  links.filter((l) => !subOnly || l.kind === "sub").forEach((l) => {
    const a = l.source.id || l.source, b = l.target.id || l.target, w = l.kind === "sub" ? 0 : 1;
    adj.get(a).push([b, w]); adj.get(b).push([a, w]);
  });
  adj.forEach((v) => v.sort((x, y) => x[1] - y[1]));
  const parent = new Map();
  const walk = (start) => {
    parent.set(start, null);
    const queue = [start];
    while (queue.length) {
      const cur = queue.shift();
      adj.get(cur).forEach(([nb]) => { if (!parent.has(nb)) { parent.set(nb, cur); queue.push(nb); } });
    }
  };
  walk(rootId);
  const extra = [];
  const isTop = (id) => !parentsOf(id).some((p) => adj.has(p));
  [...nodes.map((n) => n.id).filter(isTop), ...nodes.map((n) => n.id)].forEach((id) => { if (!parent.has(id)) { walk(id); extra.push(id); } });
  const build = (id) => ({ id, children: [...parent].filter(([, p]) => p === id).map(([c]) => build(c)) });
  const others = extra.map(build);
  const flat = (t) => [t.id, ...t.children.flatMap(flat)];
  return { tree: build(rootId), others, orphans: others.flatMap(flat) };
}

function structuredLayout(nodes, links, byId, anchor) {
  const sep = (a, b) => (a.data.id === "__v" || b.data.id === "__v" ? 0 : 1);
  let rootId = focus && byId[focus] ? focus : nodes[0].id;
  if (layout !== "radial") {
    const up = lineage(rootId).filter((n) => byId[n]);
    if (up.length) rootId = up[0];
  }
  const { tree, others, orphans } = spanningTree(rootId, nodes, links, showAll && layout !== "radial");
  const pos = new Map();
  if (layout === "radial") {
    const h = d3.hierarchy({ id: "__v", children: [tree, ...orphans.map((id) => ({ id, orphan: true, children: [] }))] });
    d3.tree().size([2 * Math.PI, 1]).separation((a, b) => (a.parent === b.parent ? 1 : 2) / Math.max(a.depth, 1))(h);
    const ring = (d) => (d.data.orphan ? maxDepth + 1 : d.depth - 1);
    const maxDepth = d3.max(h.descendants().filter((d) => !d.data.orphan && d.data.id !== "__v"), (d) => d.depth - 1) || 0;
    const rings = [];
    h.descendants().forEach((d) => { if (d.data.id === "__v") return; const r = ring(d); (rings[r] = rings[r] || []).push(d); });
    const radius = [0];
    for (let r = 1; r < rings.length; r++) {
      const need = d3.sum(rings[r] || [], (d) => byId[d.data.id].w + 28) / (2 * Math.PI);
      radius[r] = Math.max(radius[r - 1] + 150, need);
    }
    rings.forEach((list, r) => {
      if (!list) return;
      if (r === 0) { list.forEach((d) => pos.set(d.data.id, { x: 0, y: 0 })); return; }
      list.forEach((d) => {
        const a = d.x;
        pos.set(d.data.id, { x: Math.cos(a - Math.PI / 2) * radius[r], y: Math.sin(a - Math.PI / 2) * radius[r] });
      });
    });
  } else if (layout === "pyramid") {
    // Piramide: filhos sem descendentes viram fileiras (4 no topo, 2 abaixo), como um organograma, para a arvore nao ficar larga e achatada.
    const GX = 24, GY = 110, RH = 62;
    const measure = (t, depth = 0) => {
      const kids = t.children || [];
      kids.forEach((k) => measure(k, depth + 1));
      const ROW = depth <= 1 ? 4 : 2;
      const leaves = kids.filter((k) => !k.children.length);
      const inner = kids.filter((k) => k.children.length);
      const pack = leaves.length > ROW;
      const rows = [];
      if (pack) for (let i = 0; i < leaves.length; i += ROW) rows.push(leaves.slice(i, i + ROW));
      const rowW = (r) => d3.sum(r, (k) => byId[k.id].w) + GX * (r.length - 1);
      const block = pack ? { block: true, rows, width: d3.max(rows, rowW), rowW } : null;
      const subs = pack ? inner : kids;
      const half = Math.ceil(subs.length / 2);
      t.parts = block ? [...subs.slice(0, half), block, ...subs.slice(half)] : subs;
      t.cw = t.parts.length ? d3.sum(t.parts, (q) => q.width) + GX * (t.parts.length - 1) : 0;
      t.width = Math.max(t.id === "__v" ? 0 : byId[t.id].w, t.cw);
    };
    const place = (t, cx, y) => {
      if (t.id !== "__v") pos.set(t.id, { x: cx, y });
      let x = cx - t.cw / 2;
      t.parts.forEach((q) => {
        if (q.block) {
          q.rows.forEach((r, i) => {
            let rx = x + (q.width - q.rowW(r)) / 2;
            r.forEach((k) => { const w = byId[k.id].w; pos.set(k.id, { x: rx + w / 2, y: y + GY + i * RH }); rx += w + GX; });
          });
        } else place(q, x + q.width / 2, y + GY);
        x += q.width + GX;
      });
    };
    const top = { id: "__v", children: [tree, ...others] };
    measure(top);
    place(top, 0, -GY);
  } else {
    const vertical = false;
    const h = d3.hierarchy({ id: "__v", children: [tree, ...others] });
    const size = (d) => (d.data.id === "__v" ? 0 : vertical ? byId[d.data.id].w : byId[d.data.id].h);
    d3.tree().nodeSize([1, 1]).separation((a, b) => (size(a) + size(b)) / 2 + (vertical ? 28 : 16))(h);
    const maxW = d3.max(nodes, (n) => n.w);
    h.descendants().forEach((d) => {
      if (d.data.id === "__v") return;
      const depth = d.depth - 1;
      pos.set(d.data.id, vertical ? { x: d.x, y: depth * 110 } : { x: depth * (maxW + 70), y: d.x });
    });
  }
  const f = pos.get(rootId) || { x: 0, y: 0 };
  const keep = layout === "radial" ? f : (pos.get(focus) || f);
  const at = byId[focus] ? anchor : { x: 0, y: 0 };
  nodes.forEach((n) => {
    const p = pos.get(n.id) || { x: 0, y: 0 };
    n.x = p.x - keep.x + at.x; n.y = p.y - keep.y + at.y;
  });
}

function renderGraph(opts = {}) {
  const svg = d3.select("#graph");
  svg.selectAll("*:not(title)").remove();
  const wrap = $(".graph-wrap");
  const W = wrap.clientWidth, H = wrap.clientHeight;
  if (!DATA.classes.length) { $("#graph-empty").hidden = false; $("#graph-empty").textContent = "Ainda não há classes. Elas aparecem quando a etapa 2 for aplicada."; $("#crumbs").innerHTML = ""; return; }
  $("#graph-empty").hidden = true;
  if (!focus || !cls(focus)) focus = defaultFocus();
  renderCrumbs();
  const ids = new Set();
  if (showAll) DATA.classes.forEach((c) => ids.add(c.name));
  else {
    ids.add(focus);
    neighborsOf(focus).forEach((n) => ids.add(n));
    expanded.forEach((e) => { if (ids.has(e)) neighborsOf(e).forEach((n) => ids.add(n)); });
  }
  const nodes = [...ids].map((id) => {
    const c = cls(id), label = c.label || c.name, kind = c.subclass_of[0] || "";
    const w = Math.max(label.length * 7.4, kind.length * 6.2) + 28;
    const hidden = showAll ? 0 : [...neighborsOf(id)].filter((n) => !ids.has(n)).length;
    return { id, label, kind, w, h: kind ? 44 : 36, root: ROOTS.includes(id), metric: c.subclass_of.includes("Metric"), pending: !!c.pending, hidden };
  });
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const links = [];
  DATA.classes.forEach((c) => byId[c.name] && c.subclass_of.forEach((p) => byId[p] && links.push({ source: c.name, target: p, kind: "sub" })));
  relEdges().forEach((e) => byId[e.source] && byId[e.target] && e.source !== e.target && links.push({ ...e, kind: "rel" }));
  links.forEach((l) => { l.source = byId[l.source]; l.target = byId[l.target]; });
  const origin = POS.get(spawnFrom) || POS.get(focus) || { x: W / 2, y: H / 2 };
  nodes.forEach((d, i) => {
    const p = POS.get(d.id);
    d.isNew = !p;
    const a = (i / nodes.length) * Math.PI * 2;
    d.sx = p ? p.x : origin.x; d.sy = p ? p.y : origin.y;
    d.x = p ? p.x : origin.x + Math.cos(a) * 60; d.y = p ? p.y : origin.y + Math.sin(a) * 60;
  });
  const f = byId[focus];
  const anchor = f ? { x: f.x, y: f.y } : { x: W / 2, y: H / 2 };
  if (f && !showAll) { f.fx = anchor.x; f.fy = anchor.y; }
  svg.append("defs").html('<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker>');
  const g = svg.append("g");
  const zoom = d3.zoom().scaleExtent([0.12, 2.5]).on("zoom", (e) => { g.attr("transform", e.transform); lastT = e.transform; });
  svg.call(zoom).on("dblclick.zoom", null);
  if (layout !== "force") structuredLayout(nodes, links, byId, anchor);
  else {
  const sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.id).distance((l) => (l.kind === "sub" ? 130 : 210)).strength(0.6))
    .force("charge", d3.forceManyBody().strength(showAll ? -700 : -900))
    .force("x", d3.forceX(anchor.x).strength(0.05))
    .force("y", d3.forceY(anchor.y).strength(0.08))
    .force("collide", d3.forceCollide((d) => d.w / 2 + 18))
    .stop();
  sim.tick(nodes.some((d) => !d.isNew) ? 250 : 400);
  }
  nodes.forEach((d) => { d.ex = d.x; d.ey = d.y; POS.set(d.id, { x: d.x, y: d.y }); });
  const edge = g.append("g").selectAll("path").data(links).join("path")
    .attr("class", (l) => "edge " + l.kind).attr("marker-end", (l) => (l.kind === "rel" ? "url(#arrow)" : null)).style("color", "var(--text-secondary)");
  const labels = g.append("g").selectAll("text").data(links.filter((l) => l.kind === "rel")).join("text").attr("class", "edge-label").attr("text-anchor", "middle").text((l) => l.label);
  const node = g.append("g").selectAll("g").data(nodes).join("g")
    .attr("class", (d) => "node" + (d.root ? " root" : "") + (d.metric ? " metric" : "") + (d.pending ? " pending" : "") + (d.id === focus && !showAll ? " focus" : ""))
    .attr("tabindex", 0).attr("role", "button").attr("aria-label", (d) => d.label)
    .on("click", (e, d) => inspect(d.id))
    .on("dblclick", (e, d) => { e.preventDefault(); e.stopPropagation(); select(d.id); })
    .on("keydown", (e, d) => {
      if (e.key === "Enter" && e.shiftKey) { e.preventDefault(); select(d.id); }
      else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); inspect(d.id); }
    })
    .call(d3.drag().on("drag", (e, d) => { d.x = e.x; d.y = e.y; POS.set(d.id, { x: d.x, y: d.y }); position(); }));
  node.append("title").text((d) => d.label + (d.hidden ? ` (${d.hidden} vizinhos ocultos)` : "") + "\nClique: ver informacoes. Dois cliques: centralizar o grafo.");
  node.append("rect").attr("class", "box").attr("rx", 8).attr("x", (d) => -d.w / 2).attr("y", (d) => -d.h / 2).attr("width", (d) => d.w).attr("height", (d) => d.h);
  node.append("text").attr("text-anchor", "middle").attr("dy", (d) => (d.kind ? -1 : 4)).text((d) => d.label);
  node.filter((d) => d.kind).append("text").attr("class", "kind").attr("text-anchor", "middle").attr("dy", 13).text((d) => d.kind);
  const more = node.filter((d) => d.hidden > 0 && !expanded.has(d.id) && d.id !== focus).append("g").attr("class", "more")
    .attr("transform", (d) => `translate(${d.w / 2},${-d.h / 2})`).attr("role", "button").attr("tabindex", 0)
    .attr("aria-label", (d) => `Abrir ${d.hidden} vizinhos de ${d.label}`)
    .on("click", (e, d) => { e.stopPropagation(); expanded.add(d.id); spawnFrom = d.id; renderGraph(); })
    .on("keydown", (e, d) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); expanded.add(d.id); spawnFrom = d.id; renderGraph(); } });
  more.append("circle").attr("r", 11);
  more.append("text").attr("text-anchor", "middle").attr("dy", 3.5).text((d) => "+" + d.hidden);
  function clip(from, to) {
    const dx = to.x - from.x, dy = to.y - from.y;
    const s = Math.min(dx ? (from.w / 2 + 3) / Math.abs(dx) : Infinity, dy ? (from.h / 2 + 3) / Math.abs(dy) : Infinity, 1);
    return [from.x + dx * s, from.y + dy * s];
  }
  function path(l) {
    const [sx, sy] = clip(l.source, l.target), [tx, ty] = clip(l.target, l.source);
    const dx = tx - sx, dy = ty - sy;
    const mx = (sx + tx) / 2 - dy * 0.08, my = (sy + ty) / 2 + dx * 0.08;
    return `M${sx},${sy} Q${mx},${my} ${tx},${ty}`;
  }
  function position() {
    edge.attr("d", path);
    labels.attr("x", (l) => (l.source.x + l.target.x) / 2 - (l.target.y - l.source.y) * 0.04).attr("y", (l) => (l.source.y + l.target.y) / 2 + (l.target.x - l.source.x) * 0.04 - 4);
    node.attr("transform", (d) => `translate(${d.x},${d.y})`);
  }
  const x0 = Math.min(...nodes.map((n) => n.ex - n.w / 2)), x1 = Math.max(...nodes.map((n) => n.ex + n.w / 2));
  const y0 = Math.min(...nodes.map((n) => n.ey - n.h / 2)), y1 = Math.max(...nodes.map((n) => n.ey + n.h / 2));
  const k = Math.min(W / (x1 - x0 + 80), H / (y1 - y0 + 80), 1.2);
  const target = d3.zoomIdentity.translate(W / 2 - ((x0 + x1) / 2) * k, H / 2 - ((y0 + y1) / 2) * k).scale(k);
  const fresh = (l) => l.source.isNew || l.target.isNew;
  if (!MOTION || !lastT || opts.instant) {
    nodes.forEach((d) => { d.x = d.ex; d.y = d.ey; });
    position();
    svg.call(zoom.transform, target);
  } else {
    nodes.forEach((d) => { d.x = d.sx; d.y = d.sy; });
    position();
    svg.call(zoom.transform, lastT);
    node.filter((d) => d.isNew).attr("opacity", 0).transition().duration(MOTION).attr("opacity", 1);
    edge.filter(fresh).attr("opacity", 0).transition().delay(MOTION / 2).duration(MOTION / 2).attr("opacity", 1);
    labels.filter(fresh).attr("opacity", 0).transition().delay(MOTION / 2).duration(MOTION / 2).attr("opacity", 1);
    svg.transition("move").duration(MOTION).ease(d3.easeCubicInOut)
      .tween("move", () => (t) => { nodes.forEach((d) => { d.x = d.sx + (d.ex - d.sx) * t; d.y = d.sy + (d.ey - d.sy) * t; }); position(); })
      .call(zoom.transform, target);
  }
  spawnFrom = null;
  graph = { highlight(name) { node.classed("selected", (d) => d.id === name); } };
  graph.highlight(selected);
}

// nivel do validate e das armadilhas, por extenso
const LEVEL = { error: "erro", warning: "aviso", info: "nota", critical: "crítico", important: "importante", minor: "menor" };
const levelOf = (l) => LEVEL[l] || l;
function renderSummary() {
  const v = DATA.validation;
  const left = [];
  if (!v) {
    left.push(`<div class="callout callout-nota">${ICONS.info}<div><div class="t">Ainda sem validação</div><div class="b">A cobertura e as armadilhas aparecem aqui depois do validate da etapa 4.</div></div></div>`);
  } else {
    const cov = v.coverage && v.coverage.available ? v.coverage : null;
    left.push(`<div class="row"><span class="status-dot ${v.ok ? "success" : "error"}"></span><span>${v.ok ? "Validação ok" : "Validação com erros"}</span><span class="label tertiary" style="margin-left:auto">${esc((v.generated_at || "").replace("T", " ").slice(0, 16))}</span></div>`);
    if (cov) {
      left.push(`<div><div class="row"><span>Cobertura</span><span class="secondary" style="margin-left:auto">${cov.mapped} de ${cov.columns} colunas</span></div><div class="bar ${cov.ratio >= 0.8 ? "ok" : ""}"><i style="width:${Math.round(cov.ratio * 100)}%"></i></div></div>`);
      left.push(`<table><thead><tr><th>fonte</th><th>mapeadas</th><th>sem mapeamento</th></tr></thead><tbody>${Object.entries(cov.by_source).map(([s, x]) => `<tr><td class="mono">${esc(s)}</td><td>${x.mapped}/${x.columns}</td><td class="secondary label">${x.unmapped.length ? `<details class="onto-cols"><summary>${x.unmapped.length} ${x.unmapped.length === 1 ? "coluna" : "colunas"}</summary><span class="mono">${esc(x.unmapped.join(", "))}</span></details>` : "todas mapeadas"}</td></tr>`).join("")}</tbody></table>`);
    } else {
      left.push(`<div class="callout callout-atencao">${ICONS.warn}<div><div class="t">Fontes ainda não perfiladas</div><div class="b">A cobertura dos mapeamentos aparece depois do profile das fontes.</div></div></div>`);
    }
    if (v.findings.length) left.push(`<table><thead><tr><th>nível</th><th>verificação</th><th>mensagem</th></tr></thead><tbody>${v.findings.map((f) => `<tr><td><span class="status-dot ${f.level === "error" ? "error" : "warning"}"></span><span class="nowrap">${esc(levelOf(f.level))}</span></td><td class="mono label">${esc(f.check)}</td><td class="secondary">${esc(f.message)}</td></tr>`).join("")}</tbody></table>`);
  }
  const pit = v ? v.pitfalls : [];
  const right = pit.length
    ? `<table><thead><tr><th>código</th><th>nível</th><th>elemento</th><th>descrição</th></tr></thead><tbody>${pit.map((p) => `<tr><td class="mono">${esc(p.code)}</td><td><span class="status-dot ${p.level === "critical" || p.level === "important" ? "error" : "warning"}"></span><span class="nowrap">${esc(levelOf(p.level))}</span></td><td class="mono label">${esc(p.subject)}</td><td class="secondary">${esc(p.message)} <span class="tertiary">(${esc(p.source)})</span></td></tr>`).join("")}</tbody></table>`
    : `<div class="callout callout-nota">${ICONS.info}<div><div class="t">Nenhuma armadilha</div><div class="b">Os checks nativos (P04, P08, P11, P13, P22, P41) não encontraram problemas${v && v.oops && v.oops.available === false ? ". O OOPS! remoto estava indisponível" : ""}.</div></div></div>`;
  const req = DATA.requirements;
  $("#summary").innerHTML = `
    <div class="card wide"><span class="kind">requisitos</span><h2 class="h2">Propósito e perguntas</h2>
      <p class="p-lg">${esc(req.purpose || "Propósito ainda não registrado.")}</p>
      ${req.scope ? `<p class="p secondary">${esc(req.scope)}</p>` : ""}
      ${req.users && req.users.length ? `<div class="badges">${req.users.map((u) => `<span class="badge badge-outline">${esc(u)}</span>`).join("")}</div>` : ""}
      ${cqList()}
    </div>
    <div class="card"><span class="kind">última validação</span><h2 class="h2">Cobertura e achados</h2>${left.join("")}</div>
    <div class="card"><span class="kind">armadilhas</span><h2 class="h2">Armadilhas de modelagem</h2>${right}</div>`;
}


function augment(d) {
  // classes e relacoes ainda pendentes entram no grafo tracejadas, para o revisor ver onde a proposta se encaixa
  const data = Object.assign({}, d);
  const names = new Set(d.classes.map((c) => c.name));
  const pendingClasses = (d.pending || []).filter((p) => p.type === "add_class" && !names.has(p.payload.name)).map((p) => ({
    name: p.payload.name, iri: "", label: p.payload.label || p.payload.name, comment: p.payload.comment || "",
    subclass_of: [p.payload.subclass_of || "Entity"], pending: true, pending_id: p.id,
  }));
  data.classes = d.classes.concat(pendingClasses);
  const relNames = new Set(d.relations.map((r) => r.name));
  const pendingRels = (d.pending || []).filter((p) => p.type === "add_relation" && !relNames.has(p.payload.name)).map((p) => ({
    name: p.payload.name, iri: "", label: p.payload.label || p.payload.name, comment: p.payload.comment || "",
    domain: [p.payload.domain], range: [p.payload.range], inverse_of: p.payload.inverse_of ? [p.payload.inverse_of] : [],
    pending: true, pending_id: p.id,
  }));
  data.relations = d.relations.concat(pendingRels);
  return data;
}

let dirty = false, wired = false;
function visible() { return !$("#view-ontologia").hidden; }
function init(d) {
  DATA = augment(d);
  DATA.classes.filter((c) => !c.subclass_of.length).forEach((c) => openTree.add(c.name));
  renderStats(); renderNav(); renderPanel(); renderSummary();
  if (visible()) renderGraph(); else dirty = true;
  if (!wired) {
    wired = true;
    let resizeTimer = null;
    addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (visible()) { renderGraph({ instant: true }); dirty = false; } }, 120); });
  }
}
function update(d) {
  DATA = augment(d);
  if (selected && !cls(selected)) selected = null;
  if (focus && !cls(focus)) focus = null;
  renderStats(); renderNav($("#search").value); renderPanel(); renderSummary();
  if (visible()) { renderGraph({ instant: true }); dirty = false; } else dirty = true;
}
function show() { if (dirty && visible()) { renderGraph({ instant: true }); dirty = false; } }
window.AkmeGraph = { init, update, select, show };

})();
