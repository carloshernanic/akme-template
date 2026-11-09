/* Vista Revisão: a caixa de entrada de decisões do consultor. Sem biblioteca, sem build.
   window.AkmeReview.init(data, api, hooks): data = /api/data (ou window.AKME_DATA no modo leitura);
   api = null (modo leitura) ou { get(path), post(path, body) } quando servida por `akme review`;
   hooks.onData(data) avisa a outra vista quando os dados mudam.

   Cada pendente chega com um bloco `view` montado pelo servidor (akme/tools/review_view.py):
   título, subtítulo, campos com rótulo, evidência, o que o dado mostra e o que pode ser editado.
   As decisões vão para /api/review (gravadas no próprio pendente); a aplicação vai para /api/apply
   com o nome de quem aprova. Nada entra na ontologia sem passar por isso. */
(function () {
  "use strict";

  // ---------- vocabulário ----------
  const CQ_TYPES = [
    ["classificacao_hierarquia", "Classificação e hierarquia"],
    ["relacao_entre_conceitos", "Relação entre conceitos"],
    ["atributos", "Atributos"],
    ["quantidade_agregacao", "Quantidade e agregação"],
    ["tempo_estado", "Tempo e estado"],
    ["regras_restricoes", "Regras e restrições"],
  ];
  const PRIORITIES = [["high", "Alta"], ["medium", "Média"], ["low", "Baixa"]];
  const USES = [["approved", "Usar na construção"], ["reserved", "Guardar para o teste"]];
  const USE_HELP = {
    approved: "Vira exemplo para o agente construir a ontologia e a camada semântica.",
    reserved: "Fica fora da construção e serve de gabarito no eval. Exige a resposta esperada.",
  };
  const GAP_DECISIONS = [
    ["request_from_client", "Pedir o dado ao cliente"],
    ["reformulate", "Reformular a pergunta"],
    ["drop", "Descartar"],
    ["open", "Deixar em aberto"],
  ];
  const DIV_OTHER = [
    ["distinct_terms", "São conceitos distintos"],
    ["ask_expert", "Perguntar ao especialista"],
    ["dismiss", "Descartar"],
    ["open", "Deixar em aberto"],
  ];
  const LABELS = {
    type: Object.fromEntries(CQ_TYPES),
    priority: Object.fromEntries(PRIORITIES),
    status: { proposed: "Proposta", approved: "Usar na construção", reserved: "Guardar para o teste", rejected: "Rejeitada", deprecated: "Descontinuada" },
    gap: Object.fromEntries(GAP_DECISIONS),
    div: Object.assign({ precedence: "Precedência" }, Object.fromEntries(DIV_OTHER)),
  };
  const GROUP_ORDER = ["uc", "cq", "gap", "div", "glossary", "class", "relation", "term", "mapping", "constraint", "precedence", "source", "other"];
  const GROUP_LABEL = {
    uc: "Caso de uso e requisitos", cq: "Perguntas de competência", gap: "Lacunas", div: "Divergências", glossary: "Glossário",
    class: "Classes", relation: "Relações", term: "Termos", mapping: "Mappings", constraint: "Restrições", precedence: "Precedências", source: "Exportação Neo4j", other: "Outros",
  };
  const I = {
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    dot: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="5"/></svg>',
    pencil: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3z"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
    warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l10 18H2L12 3zM12 10v4M12 17h.01"/></svg>',
    ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>',
    cls: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="5" width="16" height="14"/><path d="M4 10h16"/></svg>',
    rel: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="12" r="3"/><circle cx="18" cy="12" r="3"/><path d="M9 12h6"/></svg>',
    term: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 6h14M5 12h10M5 18h7"/></svg>',
    map: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16v12H4zM4 11h16M10 6v12"/></svg>',
    q: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17h.01"/></svg>',
    gap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12h5M15 12h5M12 4v5M12 15v5"/></svg>',
    div: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 4v16M18 4v16M6 12h12"/></svg>',
    rule: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/></svg>',
    book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 5h7a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4zM20 5h-7a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2h7z"/></svg>',
  };
  const GROUP_ICON = { uc: I.book, cq: I.q, gap: I.gap, div: I.div, glossary: I.book, class: I.cls, relation: I.rel, term: I.term, mapping: I.map, constraint: I.rule, precedence: I.rule, source: I.map, other: I.dot };

  const S = {
    data: null, api: null, hooks: {}, drafts: {}, newKeys: [], newSeq: 0, cards: {}, order: [], reviewer: "",
    busy: false, invalid: new Set(), editing: new Set(), selected: null, scope: "pending", group: null,
    tab: null, wired: false, token: null, polling: false,
  };

  // ---------- utilidades ----------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (sel, el = document) => el.querySelector(sel);
  const list = (v) => (Array.isArray(v) ? v.map(String) : v ? [String(v)] : []);
  const sameList = (a, b) => JSON.stringify(list(a)) === JSON.stringify(list(b));
  const fmtDate = (s) => String(s || "").replace("T", " ").slice(0, 16);
  const fid = (key, field) => "rv-f-" + String(key).replace(/[^A-Za-z0-9_-]/g, "_") + "-" + field;
  const sel = (s) => (window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/["\\]/g, "\\$&"));
  const splitChoice = (val) => { const i = val.indexOf("|"); return [val.slice(0, i), val.slice(i + 1)]; };
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function read(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  const req = () => S.data.requirements || {};
  const pending = () => S.data.pending || [];
  const stage = () => S.data.stage || null;
  const origin = (by) => (!by || by === "agent" || by === "IA" ? "Proposta pela IA" : "Proposta por " + by);
  const originLow = (by) => (!by || by === "agent" || by === "IA" ? "proposta pela IA" : "proposta por " + by);
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

  function fmtValue(field, v) {
    if (v === undefined || v === null || v === "") return "—";
    if (Array.isArray(v)) return v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(", ") || "—";
    if (typeof v === "object") return JSON.stringify(v);
    if (field === "type") return LABELS.type[v] || v;
    if (field === "priority") return LABELS.priority[v] || v;
    if (field === "status") return LABELS.status[v] || v;
    if (field === "decision") return LABELS.gap[v] || LABELS.div[v] || v;
    return String(v);
  }

  // view de reserva para dados exportados por versoes antigas (sem bloco view)
  function viewOf(p) {
    if (p.view) return p.view;
    const pl = p.payload || {};
    return { title: pl.name || pl.question || pl.topic || pl.id || p.id, subtitle: p.type, group: "other", group_label: "Outros", stage: 1,
      fields: Object.entries(pl).map(([k, v]) => ({ label: k, value: fmtValue(k, v), mono: false })), evidence: [], observed: null, alerts: [],
      editable: [], rejectable: true, origin: p.proposed_by === "agent" ? "IA" : p.proposed_by, requirement_id: p.requirement_id || "", rationale: p.rationale || "" };
  }

  // ---------- abas e etapa ----------
  function setTab(name, persist = true) {
    if (name !== "ontologia") name = "revisao";
    S.tab = name;
    $("#view-ontologia").hidden = name !== "ontologia";
    $("#view-revisao").hidden = name !== "revisao";
    $("#tab-ontologia").setAttribute("aria-selected", String(name === "ontologia"));
    $("#tab-revisao").setAttribute("aria-selected", String(name === "revisao"));
    $("#ont-nav").hidden = name !== "ontologia";
    $("#rv-nav").hidden = name !== "revisao";
    $("#sidebar-mode").textContent = name === "ontologia" ? "ontologia" : "revisão";
    const bar = $("#rv-bar");
    if (bar) bar.hidden = name !== "revisao";
    if (persist) store("akme-tab", name);
    if (name === "ontologia" && window.AkmeGraph) { window.AkmeGraph.show(); dispatchEvent(new Event("resize")); }
  }

  function renderStage() {
    const st = stage();
    const stepper = $("#stepper"), chip = $("#stage-chip"), banner = $("#gate-banner");
    if (!st) { stepper.innerHTML = ""; chip.textContent = ""; banner.hidden = true; return; }
    stepper.innerHTML = (st.stages || []).map((s) => `<li class="step" data-status="${esc(s.status)}" ${s.status === "active" ? 'aria-current="step"' : ""} title="${esc(s.description)}">
      <div class="step-rail"><span class="step-marker">${s.status === "completed" ? I.check : s.number}</span><span class="step-sep"></span></div>
      <div class="step-body"><span class="step-title">${esc(s.name)}</span></div></li>`).join("");
    chip.innerHTML = `<span class="status-dot ${st.gate_active ? "warning" : "information"}"></span>${esc(st.label)}`;
    chip.title = st.next_step || "";
    // a faixa so aparece quando os requisitos estao abertos: e o unico caso em que o humano precisa ler o que falta
    const missing = st.missing || [];
    banner.className = "callout callout-atencao";
    banner.innerHTML = `${I.warn}<div><div class="t">Requisitos abertos</div><div class="b">${missing.length ? `<ul>${missing.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : esc(st.next_step || "")}</div></div>`;
    banner.hidden = !st.gate_active;
  }

  // ---------- modelo de cartões ----------
  function buildCards() {
    const cards = {}, order = [];
    const byGroup = {};
    for (const p of pending()) {
      const v = viewOf(p);
      let kind = "generic";
      if (p.type === "add_competency_question") kind = "cq";
      else if (p.type === "add_gap") kind = "gap";
      else if (p.type === "add_divergence") kind = "div";
      const key = "p:" + p.id;
      cards[key] = { kind, item: p, view: v, group: v.group || "other", applied: false };
      (byGroup[cards[key].group] = byGroup[cards[key].group] || []).push(key);
    }
    for (const k of S.newKeys) { cards[k] = { kind: "n-cq", item: null, view: null, group: "cq", applied: false }; (byGroup.cq = byGroup.cq || []).push(k); }
    for (const g of GROUP_ORDER) (byGroup[g] || []).forEach((k) => order.push(k));
    for (const q of req().competency_questions || []) { const k = "a:cq:" + q.id; cards[k] = { kind: "a-cq", item: q, view: null, group: "cq", applied: true }; order.push(k); }
    for (const g of req().gaps || []) { const k = "a:gap:" + g.id; cards[k] = { kind: "a-gap", item: g, view: null, group: "gap", applied: true }; order.push(k); }
    for (const d of req().divergences || []) { const k = "a:div:" + d.id; cards[k] = { kind: "a-div", item: d, view: null, group: "div", applied: true }; order.push(k); }
    S.cards = cards; S.order = order;
    for (const k of Object.keys(S.drafts)) if (!cards[k]) delete S.drafts[k];
    for (const k of [...S.editing]) if (!cards[k]) S.editing.delete(k);
  }

  function cqFields(src) {
    const st = src.status;
    return { question: src.question || "", type: src.type || "", concepts: list(src.concepts),
      priority: src.priority || "", use: st === "approved" || st === "reserved" ? st : "", answer: src.answer || "" };
  }

  function baseline(key) {
    const c = S.cards[key];
    if (!c) return null;
    const p = c.item, r = p && p.review, e = (r && r.edits) || {}, pl = (p && p.payload) || {};
    switch (c.kind) {
      case "cq": return Object.assign({ decision: r ? r.decision : null }, cqFields(Object.assign({}, pl, e)), { reason: (r && r.reason) || "" });
      case "generic": {
        const edits = {};
        (c.view.editable || []).forEach((f) => { edits[f.key] = f.kind === "list" ? list(e[f.key] ?? pl[f.key]) : f.kind === "map" ? mapText(e[f.key] ?? pl[f.key]) : String(e[f.key] ?? pl[f.key] ?? ""); });
        return { decision: r ? r.decision : null, reason: (r && r.reason) || "", edits };
      }
      case "gap": return { choice: r ? e.decision ?? pl.decision ?? "" : "", note: (e.note ?? pl.note) || "" };
      case "div": return { choice: r ? e.decision ?? pl.decision ?? "" : "", winner: (e.winner ?? pl.winner) || "", reason: (e.reason ?? pl.reason) || "" };
      case "a-cq": return Object.assign({ mode: "" }, cqFields(p), { reason: "" });
      case "a-gap": return { mode: "", choice: p.decision || "", note: p.note || "" };
      case "a-div": return { mode: "", choice: p.decision || "", winner: p.winner || "", reason: p.reason || "" };
      case "n-cq": return { question: "", type: "", concepts: [], priority: "", use: "", answer: "", use_cases: [] };
    }
    return null;
  }
  const view = (key) => S.drafts[key] || baseline(key);
  function draft(key) {
    if (!S.drafts[key]) S.drafts[key] = JSON.parse(JSON.stringify(baseline(key)));
    return S.drafts[key];
  }

  // tipos por coluna ({coluna: tipo}) viram texto editavel "coluna: tipo, coluna: tipo"; o servidor confere de novo
  function mapText(v) {
    if (v && typeof v === "object" && !Array.isArray(v)) return Object.entries(v).map(([k, t]) => `${k}: ${t}`).join(", ");
    return String(v ?? "").trim();
  }
  function genericDiff(c, d) {
    const pl = c.item.payload || {}, out = {};
    (c.view.editable || []).forEach((f) => {
      const cur = d.edits[f.key];
      if (f.kind === "list") { if (!sameList(cur, pl[f.key])) out[f.key] = list(cur); }
      else if (f.kind === "map") { if (String(cur ?? "").trim() !== mapText(pl[f.key])) out[f.key] = String(cur ?? "").trim(); }
      else if (String(cur ?? "").trim() !== String(pl[f.key] ?? "")) out[f.key] = String(cur ?? "").trim();
    });
    return out;
  }
  function appliedDiff(c, d) {
    const it = c.item, out = {};
    if (c.kind === "a-cq") {
      if (d.question.trim() !== (it.question || "")) out.question = d.question.trim();
      if (d.type && d.type !== it.type) out.type = d.type;
      if (!sameList(d.concepts, it.concepts)) out.concepts = d.concepts;
      if (d.priority && d.priority !== it.priority) out.priority = d.priority;
      if (d.use && d.use !== it.status) out.status = d.use;
      if (d.use === "reserved" && d.answer.trim() !== (it.answer || "")) out.answer = d.answer.trim();
    } else if (c.kind === "a-gap") {
      if (d.choice !== it.decision) out.decision = d.choice;
      if (d.note.trim() !== (it.note || "")) out.note = d.note.trim();
    } else if (c.kind === "a-div") {
      if (d.choice !== it.decision) out.decision = d.choice;
      if (d.choice === "precedence" && d.winner !== (it.winner || "")) out.winner = d.winner;
      if (d.reason.trim() !== (it.reason || "")) out.reason = d.reason.trim();
    }
    return out;
  }
  function isChanged(key) {
    const d = S.drafts[key], c = S.cards[key];
    if (!d || !c) return false;
    if (c.kind === "n-cq") return true;
    if (c.applied) return d.mode === "remove" || (d.mode === "alter" && Object.keys(appliedDiff(c, d)).length > 0);
    const decided = c.kind === "gap" || c.kind === "div" ? !!d.choice : !!d.decision;
    return decided && JSON.stringify(d) !== JSON.stringify(baseline(key));
  }
  // estado do item: todo (sem decisão), draft (decidido aqui, não salvo), accept, reject (salvos), applied
  function stateOf(key) {
    const c = S.cards[key];
    if (c.applied) return "applied";
    if (c.kind === "n-cq") return "draft";
    if (isChanged(key)) return "draft";
    const r = c.item.review;
    if (!r) return "todo";
    if (c.kind === "gap" || c.kind === "div") return "accept";
    return r.decision === "reject" ? "reject" : "accept";
  }
  function cardLabel(key) {
    const c = S.cards[key];
    if (!c) return key;
    if (c.kind === "n-cq") return "Nova pergunta";
    if (c.view) return c.view.title;
    return c.item.id;
  }

  // ---------- operações ----------
  function cqError(d) {
    if (!d.question.trim()) return "a pergunta está vazia";
    if (!d.type) return "escolha o tipo da pergunta";
    if (!d.concepts.length) return "informe ao menos um conceito";
    if (!d.priority) return "escolha a prioridade";
    if (!d.use) return "escolha o uso: construção ou teste";
    if (d.use === "reserved" && !d.answer.trim()) return "guardar para o teste exige a resposta esperada";
    return "";
  }
  function buildOp(key) {
    const c = S.cards[key], d = S.drafts[key], p = c.item, reviewer = S.reviewer.trim();
    const fail = (m) => ({ error: `${cardLabel(key)}: ${m}` });
    const review = (rest) => ({ path: "/api/review", body: Object.assign({ edit_id: p.id, reviewer }, rest) });
    const propose = (type, payload) => ({ path: "/api/propose", body: { type, payload, reviewer } });
    const rejectOp = () => (d.reason.trim() ? review({ decision: "reject", reason: d.reason.trim() }) : fail("rejeitar exige um motivo"));
    switch (c.kind) {
      case "cq": {
        if (d.decision === "reject") return rejectOp();
        const err = cqError(d);
        if (err) return fail(err);
        const pl = p.payload || {};
        const edits = { status: d.use, priority: d.priority };
        if (d.use === "reserved") edits.answer = d.answer.trim();
        if (d.question.trim() !== (pl.question || "")) edits.question = d.question.trim();
        if (d.type !== pl.type) edits.type = d.type;
        if (!sameList(d.concepts, pl.concepts)) edits.concepts = d.concepts;
        return review({ decision: "accept", edits });
      }
      case "generic": {
        if (d.decision === "reject") return rejectOp();
        const edits = genericDiff(c, d);
        for (const f of c.view.editable || []) {
          if (f.key in edits && f.kind !== "list" && !edits[f.key]) return fail(`${f.label.toLowerCase()} não pode ficar vazio`);
        }
        return review(Object.keys(edits).length ? { decision: "accept", edits } : { decision: "accept" });
      }
      case "gap": {
        if (d.choice !== "open" && !d.note.trim()) return fail("explique a decisão (só Deixar em aberto dispensa)");
        const edits = { decision: d.choice };
        if (d.note.trim()) edits.note = d.note.trim();
        return review({ decision: "accept", edits });
      }
      case "div": {
        if (d.choice === "precedence" && !d.winner) return fail("escolha a fonte que prevalece");
        if (d.choice !== "open" && !d.reason.trim()) return fail("explique a decisão (só Deixar em aberto dispensa)");
        const edits = { decision: d.choice };
        if (d.choice === "precedence") edits.winner = d.winner;
        if (d.reason.trim()) edits.reason = d.reason.trim();
        return review({ decision: "accept", edits });
      }
      case "n-cq": {
        const err = cqError(d);
        if (err) return fail(err);
        const payload = { question: d.question.trim(), type: d.type, concepts: d.concepts, priority: d.priority, status: d.use };
        if (d.use === "reserved") payload.answer = d.answer.trim();
        if (d.use_cases.length) payload.use_cases = d.use_cases;
        return propose("add_competency_question", payload);
      }
      case "a-cq": {
        if (d.mode === "remove") {
          if (!d.reason.trim()) return fail("propor exclusão exige um motivo");
          return propose("remove_competency_question", { id: p.id, reason: d.reason.trim() });
        }
        const diff = appliedDiff(c, d);
        if ("question" in diff && !diff.question) return fail("a pergunta está vazia");
        if ("concepts" in diff && !diff.concepts.length) return fail("informe ao menos um conceito");
        if (d.use === "reserved" && !d.answer.trim()) return fail("guardar para o teste exige a resposta esperada");
        return propose("update_competency_question", Object.assign({ id: p.id }, diff));
      }
      case "a-gap": {
        if (d.choice !== "open" && !d.note.trim()) return fail("explique a decisão (só Deixar em aberto dispensa)");
        return propose("update_gap", Object.assign({ id: p.id, decision: d.choice }, appliedDiff(c, d)));
      }
      case "a-div": {
        if (d.choice === "precedence" && !d.winner) return fail("escolha a fonte que prevalece");
        if (d.choice !== "open" && !d.reason.trim()) return fail("explique a decisão (só Deixar em aberto dispensa)");
        return propose("update_divergence", Object.assign({ id: p.id, decision: d.choice }, appliedDiff(c, d)));
      }
    }
    return fail("cartão desconhecido");
  }

  async function reload(opts = {}) {
    if (!S.api) return;
    const before = new Set(pending().map((p) => p.id));
    const data = await S.api.get("/api/data");
    S.data = data;
    S.token = data.token || S.token;
    if (S.hooks.onData) S.hooks.onData(data);
    const fresh = pending().filter((p) => !before.has(p.id));
    if (opts.announce && fresh.length) toast(`${plural(fresh.length, "proposta nova", "propostas novas")} do agente na fila.`, { label: "Ver", onClick: () => { S.scope = "pending"; S.group = null; S.selected = "p:" + fresh[0].id; render(); } });
    return fresh.length;
  }

  async function save() {
    if (!S.api || !S.reviewer.trim() || S.busy) return;
    const keys = S.order.filter(isChanged);
    if (!keys.length) return setMsg("info", "Nada para salvar.");
    const ops = keys.map((k) => Object.assign({ key: k }, buildOp(k)));
    const bad = ops.filter((o) => o.error);
    S.invalid = new Set(bad.map((o) => o.key));
    if (bad.length) {
      S.selected = bad[0].key;
      const hidden = !visibleKeys().includes(bad[0].key);
      if (hidden) { S.group = null; S.scope = "pending"; } // o cartao com erro precisa aparecer para ser corrigido
      render();
      setMsg("error", bad[0].error + (bad.length > 1 ? ` (e mais ${bad.length - 1})` : "") + (hidden ? ". O filtro foi limpo para mostrar o cartão." : ""));
      const f = $("#rv-detail textarea, #rv-detail input:not([type=checkbox]), #rv-detail select");
      if (f) f.focus({ preventScroll: true });
      return;
    }
    S.busy = true; renderBar(); setMsg("info", "Salvando…");
    let ok = 0, err = null;
    for (const o of ops) {
      try {
        await S.api.post(o.path, o.body);
        delete S.drafts[o.key];
        S.editing.delete(o.key);
        S.newKeys = S.newKeys.filter((k) => k !== o.key);
        ok++;
      } catch (e) { err = `${cardLabel(o.key)}: ${e.message}`; S.invalid.add(o.key); break; }
    }
    try { await reload(); } catch (e) { err = err || "falha ao recarregar: " + e.message; }
    S.busy = false;
    render();
    if (err) setMsg("error", `${ok} de ${ops.length} salvas. Erro em ${err}`);
    else setMsg("success", `${plural(ok, "decisão salva", "decisões salvas")}. Falta aplicar.`);
  }

  // aceita a proposta como veio em todos os cartões ainda a decidir da fila visível (respeita o filtro por tipo).
  // Só marca rascunhos: o revisor ainda salva e aplica. Lacunas e divergências sem decisão proposta ficam de fora.
  function bulkTargets() {
    return visibleKeys().filter((k) => {
      const c = S.cards[k];
      return !c.applied && c.kind !== "n-cq" && stateOf(k) === "todo";
    });
  }
  // Aceita como proposto o que pode ser aceito sem escolha do revisor. O que exige escolha (pergunta sem
  // prioridade, lacuna ou divergencia sem decisao proposta) nao e aceito em silencio: a lista passa a mostrar
  // so os itens ainda a decidir, com o primeiro aberto e o motivo de cada um.
  function acceptAll() {
    if (!S.api) return;
    let ok = 0;
    const pendingKeys = [], why = {};
    for (const k of bulkTargets()) {
      const c = S.cards[k], pl = (c.item && c.item.payload) || {};
      const hold = (reason) => { pendingKeys.push(k); why[reason] = (why[reason] || 0) + 1; };
      if (c.kind === "generic") { draft(k).decision = "accept"; ok++; }
      else if (c.kind === "cq" && !pl.priority) hold("pergunta sem prioridade");
      else if (c.kind === "cq") {
        const d = draft(k);
        d.decision = "accept";
        d.priority = d.priority || pl.priority;
        if (!d.use) d.use = pl.status === "reserved" && pl.answer ? "reserved" : "approved";
        ok++;
      } else if (c.kind === "gap" && pl.decision) {
        const d = draft(k); d.choice = pl.decision; ok++;
      } else if (c.kind === "div" && pl.decision) {
        const d = draft(k); d.choice = pl.decision; d.winner = pl.winner || ""; ok++;
      } else hold(c.kind === "gap" ? "lacuna sem decisão" : c.kind === "div" ? "divergência sem decisão" : "item sem decisão");
      S.invalid.delete(k);
    }
    S.editing = new Set();
    if (pendingKeys.length) { S.scope = "todo"; S.selected = pendingKeys[0]; }
    render();
    const reasons = Object.entries(why).map(([r, n]) => `${n} ${r}`).join(", ");
    const accepted = ok ? `${plural(ok, "proposta aceita", "propostas aceitas")}, falta salvar. ` : "";
    if (pendingKeys.length) return setMsg(ok ? "info" : "error", `${accepted}${plural(pendingKeys.length, "item continua", "itens continuam")} a decidir e ${pendingKeys.length > 1 ? "estão" : "está"} na lista ao lado: ${reasons}.`);
    setMsg(ok ? "success" : "info", ok ? accepted.trim() : "Nada a aceitar.");
  }

  function discard() {
    S.drafts = {}; S.newKeys = []; S.invalid = new Set(); S.editing = new Set();
    render();
    setMsg("info", "Alterações locais descartadas.");
  }

  // ---------- peças de HTML ----------
  const dis = () => (S.api ? "" : " disabled");
  const disPropose = () => (S.api && S.reviewer.trim() ? "" : " disabled");
  const badge = (text, cls = "badge-alt") => `<span class="badge ${cls}">${esc(text)}</span>`;

  function seg(key, field, options, isOn, opts = {}) {
    return `<div class="seg${opts.col ? " col" : ""}" role="group" aria-label="${esc(opts.label || field)}">${options.map(([v, l]) =>
      `<button type="button" data-act="set" data-key="${esc(key)}" data-field="${esc(field)}" data-value="${esc(v)}" aria-pressed="${isOn(v)}"${opts.no && v === "reject" ? ' class="no"' : ""}${dis()}>${esc(l)}</button>`).join("")}</div>`;
  }
  function textField(key, field, label, value, opts = {}) {
    const id = fid(key, field);
    const tag = opts.input
      ? `<input id="${id}" class="input" type="text" data-key="${esc(key)}" data-field="${esc(field)}" value="${esc(value)}" placeholder="${esc(opts.placeholder || "")}"${dis()}>`
      : `<textarea id="${id}" class="textarea${opts.lg ? " lg" : ""}" rows="${opts.rows || 2}" data-key="${esc(key)}" data-field="${esc(field)}" placeholder="${esc(opts.placeholder || "")}"${dis()}>${esc(value)}</textarea>`;
    return `<div class="field${opts.full ? " full" : ""}"><label class="field-label" for="${id}">${esc(label)}</label>${tag}${opts.help ? `<span class="field-help">${esc(opts.help)}</span>` : ""}</div>`;
  }
  function typeSelect(key, value) {
    const id = fid(key, "type");
    return `<div class="field"><label class="field-label" for="${id}">Tipo</label><select id="${id}" class="select" data-key="${esc(key)}" data-field="type"${dis()}>
      <option value=""${value ? "" : " selected"}>escolha o tipo</option>${CQ_TYPES.map(([v, l]) => `<option value="${esc(v)}"${v === value ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></div>`;
  }
  const conceptBadges = (cs) => (cs.length ? cs.map((x) => badge(x, "badge-outline")).join("") : '<span class="label tertiary">sem conceitos</span>');
  function conceptsField(key, concepts) {
    return `<div class="field"><label class="field-label" for="${fid(key, "concepts")}">Conceitos (separados por vírgula)</label>
      <input id="${fid(key, "concepts")}" class="input" type="text" data-key="${esc(key)}" data-field="concepts" value="${esc(concepts.join(", "))}" placeholder="Pedido, Cliente"${dis()}>
      <div class="badges" data-preview="${esc(key)}">${conceptBadges(concepts)}</div></div>`;
  }

  function sourceLine(s) {
    const check = S.api && s.quote
      ? ` <button type="button" class="check" data-act="check" data-q="${esc(s.quote)}">conferir</button><span class="checked" aria-live="polite"></span>` : "";
    return `<span class="path">${esc(s.path || "")}${s.locator ? " · " + esc(s.locator) : ""}</span>${s.quote ? `<span class="quote">“${esc(s.quote)}”${check}</span>` : check}`;
  }
  function evidenceBlock(items, title = "Evidência") {
    items = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!items.length) return "";
    return `<section class="rv-section"><h3>${esc(title)}</h3>${items.map((ev) => {
      if (ev.kind === "conversation") return `<div class="ev">${badge("conversa")} ${esc(ev.who)} · ${esc(fmtDate(ev.when))}${ev.note ? " · " + esc(ev.note) : ""}</div>`;
      if (ev.kind === "note" || (!ev.path && ev.note)) return `<div class="ev">${esc(ev.note)}</div>`;
      return `<div class="ev">${sourceLine(ev)}</div>`;
    }).join("")}</section>`;
  }
  function observedBlock(v) {
    const o = v.observed;
    if (!o) return "";
    const lines = o.available ? o.lines : [`Não foi possível ler o dado: ${o.reason}`];
    return `<section class="rv-section"><h3>O que o dado mostra</h3><ul class="obs">${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>
      ${(v.alerts || []).map((a) => `<div class="callout callout-atencao">${I.warn}<div><div class="t">Conferir antes de aceitar</div><div class="b">${esc(a)}</div></div></div>`).join("")}</section>`;
  }
  function savedNote(p) {
    const r = p && p.review;
    return r ? `<p class="rv-saved">${I.ok}Salva por ${esc(r.reviewer)}, ${esc(fmtDate(r.reviewed_at))}</p>` : "";
  }
  function diffTable(current, payload) {
    const fields = Object.keys(payload || {}).filter((k) => k !== "id");
    if (!fields.length) return '<p class="p secondary">Sem campos alterados.</p>';
    return `<table class="diff"><thead><tr><th>campo</th><th>antes</th><th>depois</th></tr></thead><tbody>${fields.map((f) =>
      `<tr><td class="mono label">${esc(f)}</td><td class="secondary">${esc(fmtValue(f, current ? current[f] : undefined))}</td><td>${esc(fmtValue(f, payload[f]))}</td></tr>`).join("")}</tbody></table>`;
  }
  const PROSE_LABELS = new Set(["Comentário", "Definição", "Regra", "Motivo", "Significado", "Descrição", "Valor", "Nota", "Hipótese da IA"]);
  const MULT_SHORT = { "muitos para um": ["n", "1"], "um para muitos": ["1", "n"], "um para um": ["1", "1"], "muitos para muitos": ["n", "n"] };
  function eyebrow(parts) {
    return `<p class="eyebrow">${parts.filter(Boolean).map((x) => esc(x)).join(" · ")}</p>`;
  }
  function headBadges(c) {
    const v = c.view, p = c.item;
    const parts = [v.group_label || GROUP_LABEL[c.group] || "Proposta", originLow(p.proposed_by)];
    if (p.requirement_id) parts.push("motivada por " + p.requirement_id);
    if ((v.alerts || []).length) parts.push("conferir o dado");
    return eyebrow(parts);
  }
  // titulo em linguagem humana (rotulo, definicao curta) com o identificador tecnico ao lado
  function cardTitle(c) {
    const v = c.view, pl = c.item.payload || {}, t = c.item.type;
    const human = pl.label || "";
    if ((t === "add_relation" || t === "add_class") && human) {
      return `<h2 class="title">${esc(human)} <span class="ident mono">${esc(pl.name)}</span></h2>`;
    }
    if (t === "add_term") return `<h2 class="title"><span class="mono">${esc(pl.name)}</span> <span class="ident">termo de ${esc(pl.class)}</span></h2>`;
    if (t === "add_mapping") return `<h2 class="title"><span class="mono">${esc(pl.term)}</span> <span class="ident">→ ${esc(pl.source)}.${esc(pl.column)}</span></h2>`;
    if (t === "add_glossary") return `<h2 class="title"><span class="mono">${esc(pl.acronym)}</span> <span class="ident">${esc(pl.meaning || "")}</span></h2>`;
    return `<h2 class="title">${esc(v.title)}</h2>${v.subtitle && t !== "add_relation" ? `<p class="subtitle">${esc(v.subtitle)}</p>` : ""}`;
  }
  // relacao desenhada: dominio, seta com nome e multiplicidade, alcance
  function relationDiagram(c, fieldsByLabel) {
    const pl = c.item.payload || {};
    if (c.item.type !== "add_relation") return "";
    const mult = fieldsByLabel["Multiplicidade"] || "";
    const [a, b] = MULT_SHORT[mult] || ["", ""];
    return `<div class="rel-diagram" aria-label="${esc(pl.domain)} ${esc(pl.label || pl.name)} ${esc(pl.range)}">
      <span class="node">${esc(pl.domain)}</span>
      <span class="arrow"><span class="lbl">${esc(pl.label || pl.name)}</span><span class="line"><i class="m">${esc(a)}</i><i class="shaft"></i><i class="m">${esc(b)}</i></span><span class="mult">${esc(mult)}</span></span>
      <span class="node">${esc(pl.range)}</span></div>`;
  }
  function cardOpen(key) {
    return `<article class="rv-card${S.invalid.has(key) ? " invalid" : ""}" data-card="${esc(key)}">`;
  }
  function decisionSeg(key, v, rejectable = true) {
    const opts = rejectable ? [["accept", "Aceitar"], ["reject", "Rejeitar"]] : [["accept", "Aceitar"]];
    return seg(key, "decision", opts, (x) => v.decision === x, { label: "Decisão", no: true });
  }

  // ---------- cartões ----------
  function cardHtml(key) {
    const c = S.cards[key];
    if (!c) return "";
    switch (c.kind) {
      case "cq": return pendingCqCard(key, c);
      case "generic": return genericCard(key, c);
      case "gap": return gapCard(key, c.item.payload || {}, c.item, true);
      case "div": return divCard(key, c.item.payload || {}, c.item, true);
      case "a-cq": return appliedCqCard(key, c.item);
      case "a-gap": return gapCard(key, c.item, null, false);
      case "a-div": return divCard(key, c.item, null, false);
      case "n-cq": return newCqCard(key);
    }
    return "";
  }

  function genericCard(key, c) {
    const v = c.view, p = c.item, d = view(key), editing = S.editing.has(key);
    const editable = v.editable || [];
    const labelOf = {}; editable.forEach((f) => { labelOf[f.key] = f.label; });
    const diff = S.drafts[key] ? genericDiff(c, d) : {};
    const fields = (v.fields || []).map((f) => {
      const k = editable.find((e) => e.label === f.label || labelOf[e.key] === f.label);
      return k && k.key in diff ? Object.assign({}, f, { value: Array.isArray(diff[k.key]) ? diff[k.key].join(", ") : diff[k.key] }) : f;
    });
    const byLabel = {}; fields.forEach((f) => { byLabel[f.label] = f.value; });
    let proposal;
    if (editing) {
      const inputs = editable.map((f) => f.kind === "list"
        ? textField(key, "edit:" + f.key, f.label, list(d.edits[f.key]).join(", "), { input: true, full: true })
        : f.kind === "map" ? textField(key, "edit:" + f.key, f.label, d.edits[f.key] || "", { rows: 2, full: true })
        : textField(key, "edit:" + f.key, f.label, d.edits[f.key] || "", { rows: f.kind === "textarea" ? 3 : 1, full: f.kind === "textarea" })).join("");
      const rest = fields.filter((f) => !editable.some((e) => e.label === f.label || labelOf[e.key] === f.label));
      proposal = `<div class="rv-edit-grid">${inputs}</div>${metaList(rest)}`;
    } else {
      const prose = fields.filter((f) => PROSE_LABELS.has(f.label) && f.label !== "Rótulo");
      const skip = new Set(["Rótulo", "Multiplicidade"]);
      const meta = fields.filter((f) => !PROSE_LABELS.has(f.label) && !(p.type === "add_relation" && skip.has(f.label)));
      proposal = `${relationDiagram(c, byLabel)}${prose.map((f) => `<p class="rv-prose">${esc(f.value)}</p>`).join("")}${metaList(meta)}`;
      if (!proposal.trim()) proposal = '<p class="p secondary">Sem detalhes além do título.</p>';
    }
    let extra = "";
    const t = p.type, pl = p.payload || {};
    if (t === "update_competency_question" || t === "update_gap" || t === "update_divergence") {
      extra = `<section class="rv-section"><h3>Antes e depois</h3>${diffTable(p.current, pl)}</section>`;
    } else if (t === "remove_competency_question") {
      const refs = p.references;
      let refsHtml = '<p class="label secondary">Referências disponíveis só com akme review.</p>';
      if (refs) {
        const items = [];
        if (refs.changelog.length) items.push(`<li>changelog: <span class="mono label">${esc(refs.changelog.join(", "))}</span></li>`);
        if (refs.evidence.length) items.push(`<li>evidências: <span class="mono label">${esc(refs.evidence.join(", "))}</span></li>`);
        if (refs.in_questions) items.push("<li>espelhada em validation/questions.yml</li>");
        refsHtml = items.length
          ? `<div class="callout callout-atencao">${I.warn}<div><div class="t">Há referências: a exclusão vira "descontinuada"</div><div class="b"><ul>${items.join("")}</ul></div></div></div>`
          : `<div class="callout callout-nota">${I.info}<div><div class="t">Sem referências</div><div class="b">A pergunta será removida de content.yml.</div></div></div>`;
      }
      extra = `<section class="rv-section"><h3>Impacto</h3>${refsHtml}</section>`;
    }
    const canEdit = editable.length && d.decision !== "reject";
    const editBtn = canEdit ? `<button type="button" class="btn btn-outline btn-sm" data-act="${editing ? "edit-off" : "edit-on"}" data-key="${esc(key)}"${dis()}>${editing ? "Manter texto original" : I.pencil + "<span>Ajustar texto antes de aceitar</span>"}</button>` : "";
    return `${cardOpen(key)}
      <div class="rv-card-head">${headBadges(c)}${cardTitle(c)}</div>
      <section class="rv-section rv-body">${proposal}</section>
      ${extra}
      ${evidenceBlock(v.evidence)}
      ${observedBlock(v)}
      ${v.rationale ? `<section class="rv-section"><h3>Justificativa do agente</h3><p class="p">${esc(v.rationale)}</p></section>` : ""}
      <section class="rv-section rv-decide"><h3>Decisão</h3>
        <div class="row">${decisionSeg(key, d, v.rejectable !== false)}${editBtn}</div>
        ${d.decision === "reject" ? textField(key, "reason", "Motivo da rejeição", d.reason, { placeholder: "obrigatório" }) : ""}
        ${savedNote(p)}
      </section></article>`;
  }
  function metaList(fields) {
    if (!fields || !fields.length) return "";
    return `<dl class="meta">${fields.map((f) => `<div><dt>${esc(f.label)}</dt><dd${f.mono ? ' class="mono"' : ""}>${esc(f.value)}</dd></div>`).join("")}</dl>`;
  }
  function cqProposalRead(v, pl) {
    return `<div class="badges">${pl.type ? badge(LABELS.type[pl.type] || pl.type) : ""}${conceptBadges(list(pl.concepts))}${list(pl.use_cases).map((u) => badge(u, "badge-outline mono")).join("")}</div>`;
  }
  function cqEditFields(key, v) {
    return `<div class="rv-edit-grid">${textField(key, "question", "Pergunta", v.question, { lg: true, rows: 2, full: true })}${typeSelect(key, v.type)}${conceptsField(key, v.concepts)}</div>`;
  }
  function cqDecisionFields(key, v) {
    return `<div class="choice"><span class="field-label">Prioridade</span>${seg(key, "priority", PRIORITIES, (x) => v.priority === x, { label: "Prioridade" })}</div>
      <div class="choice"><span class="field-label">Uso da pergunta</span>${seg(key, "use", USES, (x) => v.use === x, { label: "Uso" })}
        ${v.use ? `<span class="choice-help">${esc(USE_HELP[v.use])}</span>` : ""}</div>
      ${v.use === "reserved" ? textField(key, "answer", "Resposta esperada", v.answer, { placeholder: "trecho que a resposta precisa conter" }) : ""}`;
  }
  function pendingCqCard(key, c) {
    const p = c.item, v = view(key), pl = p.payload || {}, editing = S.editing.has(key);
    const edited = v.question.trim() !== (pl.question || "") || (v.type && v.type !== pl.type) || !sameList(v.concepts, pl.concepts);
    const head = eyebrow(["Pergunta de competência", originLow(p.proposed_by), pl.id, edited ? "editada por você" : ""]);
    const editBtn = v.decision !== "reject" ? `<button type="button" class="btn btn-outline btn-sm" data-act="${editing ? "edit-off" : "edit-on"}" data-key="${esc(key)}"${dis()}>${editing ? "Manter texto original" : I.pencil + "<span>Editar a pergunta</span>"}</button>` : "";
    return `${cardOpen(key)}
      <div class="rv-card-head">${head}${editing ? "" : `<h2 class="title">${esc(v.question)}</h2>`}</div>
      <section class="rv-section"><h3>Proposta</h3>${editing ? cqEditFields(key, v) : cqProposalRead(v, Object.assign({}, pl, { type: v.type, concepts: v.concepts }))}</section>
      ${evidenceBlock(pl.evidence)}
      ${p.rationale ? `<section class="rv-section"><h3>Justificativa do agente</h3><p class="p">${esc(p.rationale)}</p></section>` : ""}
      <section class="rv-section rv-decide"><h3>Decisão</h3>
        <div class="row">${decisionSeg(key, v)}${editBtn}</div>
        ${v.decision === "reject" ? textField(key, "reason", "Motivo da rejeição", v.reason, { placeholder: "obrigatório" }) : v.decision === "accept" ? cqDecisionFields(key, v) : ""}
        ${savedNote(p)}
      </section></article>`;
  }

  function appliedCqCard(key, q) {
    const v = view(key), mode = S.drafts[key] ? S.drafts[key].mode : "";
    const hasPending = pending().some((p) => (p.view ? p.view.group === "cq" : false) && p.type !== "add_competency_question" && (p.payload || {}).id === q.id);
    const head = eyebrow(["Pergunta aplicada", q.id, LABELS.status[q.status] || q.status || "sem status", originLow(q.proposed_by)]);
    let body, decide;
    if (mode === "alter") {
      body = `<section class="rv-section"><h3>Alteração proposta</h3>${cqEditFields(key, v)}</section>${evidenceBlock(q.evidence)}`;
      decide = `<section class="rv-section rv-decide"><h3>Prioridade e uso</h3>${cqDecisionFields(key, v)}<div class="row"><button type="button" class="btn btn-ghost btn-sm" data-act="cancel" data-key="${esc(key)}">Cancelar</button></div></section>`;
    } else {
      body = `<section class="rv-section"><h3>Pergunta</h3>${cqProposalRead(v, q)}
          ${q.status === "reserved" && q.answer ? `<p class="p"><b>Resposta esperada:</b> ${esc(q.answer)}</p>` : ""}
          ${q.status === "rejected" ? `<p class="p"><b>Motivo:</b> ${esc(q.rejection_reason || "")}</p>` : ""}
          ${q.status === "deprecated" ? `<p class="p"><b>Motivo:</b> ${esc(q.deprecation_reason || "")}</p>` : ""}
          <dl class="kv"><dt>Prioridade</dt><dd>${esc(fmtValue("priority", q.priority))}</dd></dl>
          ${q.reviewed_by ? `<p class="label secondary">Revisada por ${esc(q.reviewed_by)} em ${esc(fmtDate(q.reviewed_at))}</p>` : ""}</section>${evidenceBlock(q.evidence)}`;
      decide = mode === "remove"
        ? `<section class="rv-section rv-decide"><h3>Propor exclusão</h3>${textField(key, "reason", "Motivo da exclusão", v.reason, { placeholder: "obrigatório", help: "Se algo referencia a pergunta, ela vira descontinuada em vez de sumir." })}<div class="row"><button type="button" class="btn btn-ghost btn-sm" data-act="cancel" data-key="${esc(key)}">Cancelar</button></div></section>`
        : `<section class="rv-section rv-decide"><h3>Ações</h3>${hasPending ? '<p class="label secondary">Já há uma proposta pendente para esta pergunta.</p>' : ""}
            <div class="row"><button type="button" class="btn btn-outline btn-sm" data-act="alter" data-key="${esc(key)}"${disPropose()}>Propor alteração</button><button type="button" class="btn btn-outline btn-sm" data-act="remove" data-key="${esc(key)}"${disPropose()}>Propor exclusão</button></div></section>`;
    }
    return `${cardOpen(key)}<div class="rv-card-head">${head}<h2 class="title">${esc(q.question)}</h2></div>${body}${decide}</article>`;
  }

  function newCqCard(key) {
    const v = view(key), ucs = req().use_cases || [];
    const ucField = ucs.length
      ? `<fieldset class="field full" style="border:0;padding:0;margin:0"><legend class="field-label">Casos de uso</legend><div class="badges">${ucs.map((u) =>
        `<label class="checkbox"><input type="checkbox" data-key="${esc(key)}" data-field="use_cases" value="${esc(u.id)}"${v.use_cases.includes(u.id) ? " checked" : ""}${dis()}> <span class="mono label">${esc(u.id)}</span> ${esc(u.name || "")}</label>`).join("")}</div></fieldset>` : "";
    return `${cardOpen(key)}
      <div class="rv-card-head"><div class="badges">${badge("Nova pergunta")}${badge("por " + (S.reviewer.trim() || "revisor"), "badge-alt")}${badge("evidência: conversa com o revisor", "badge-outline")}</div><h2 class="title">Nova pergunta de competência</h2></div>
      <section class="rv-section"><h3>Pergunta</h3>${cqEditFields(key, v)}${ucField}</section>
      <section class="rv-section rv-decide"><h3>Prioridade e uso</h3>${cqDecisionFields(key, v)}
        <div class="row"><button type="button" class="btn btn-ghost btn-sm" data-act="drop-new" data-key="${esc(key)}">Remover rascunho</button></div></section></article>`;
  }

  function gapCard(key, g, p, isPending) {
    const v = view(key), mode = isPending ? "edit" : S.drafts[key] ? S.drafts[key].mode : "";
    const editing = mode === "edit" || mode === "alter";
    const who = isPending ? (p.proposed_by && p.proposed_by !== "agent" ? "Identificada por " + p.proposed_by : "Identificada pela IA") : "Registrada";
    const head = eyebrow(["Lacuna", who.charAt(0).toLowerCase() + who.slice(1), g.id, !isPending ? (LABELS.gap[g.decision] || g.decision || "") : ""]);
    let decide;
    if (editing) {
      decide = `<section class="rv-section rv-decide"><h3>Decisão</h3>
        <div class="choice"><span class="field-label">O que fazer com esta lacuna</span>${seg(key, "choice", GAP_DECISIONS, (x) => v.choice === x, { col: true, label: "Decisão da lacuna" })}
          ${v.choice === "request_from_client" ? '<span class="choice-help">Entra no pedido de dados ao cliente.</span>' : ""}</div>
        ${textField(key, "note", "Motivo da decisão", v.note, { placeholder: v.choice === "open" ? "opcional" : "obrigatório" })}
        ${isPending ? savedNote(p) : `<div class="row"><button type="button" class="btn btn-ghost btn-sm" data-act="cancel" data-key="${esc(key)}">Cancelar</button></div>`}</section>`;
    } else {
      decide = `<section class="rv-section rv-decide"><h3>Decisão registrada</h3><dl class="kv"><dt>Decisão</dt><dd>${esc(LABELS.gap[g.decision] || g.decision || "—")}</dd>
        <dt>Pedido de dados</dt><dd>${g.decision === "request_from_client" ? "Sim" : "Não"}</dd>${g.note ? `<dt>Motivo</dt><dd>${esc(g.note)}</dd>` : ""}</dl>
        ${g.decided_by ? `<p class="label secondary">Decidida por ${esc(g.decided_by)} em ${esc(fmtDate(g.decided_at))}</p>` : ""}
        <div class="row"><button type="button" class="btn btn-outline btn-sm" data-act="alter" data-key="${esc(key)}"${disPropose()}>Propor alteração</button></div></section>`;
    }
    return `${cardOpen(key)}
      <div class="rv-card-head">${head}<h2 class="title">${esc(g.question)}</h2></div>
      <section class="rv-section"><h3>Por quê</h3><dl class="kv"><dt>Motivo</dt><dd>${esc(g.reason || "—")}</dd><dt>O que faltaria</dt><dd>${esc(g.missing || "—")}</dd></dl></section>
      ${evidenceBlock(g.evidence)}
      ${isPending && p.rationale ? `<section class="rv-section"><h3>Justificativa do agente</h3><p class="p">${esc(p.rationale)}</p></section>` : ""}
      ${decide}</article>`;
  }

  function divCard(key, dv, p, isPending) {
    const v = view(key), mode = isPending ? "edit" : S.drafts[key] ? S.drafts[key].mode : "";
    const editing = mode === "edit" || mode === "alter";
    const sources = Array.isArray(dv.sources) ? dv.sources : [];
    const labels = sources.map((s, i) => s.label || "Fonte " + String.fromCharCode(65 + i));
    const decLabel = (d, w) => (d === "precedence" ? (w ? w + " prevalece" : "Precedência") : LABELS.div[d] || d || "—");
    const who = isPending ? (p.proposed_by && p.proposed_by !== "agent" ? "Identificada por " + p.proposed_by : "Identificada pela IA") : "Registrada";
    const head = eyebrow(["Divergência", who.charAt(0).toLowerCase() + who.slice(1), dv.id, !isPending ? decLabel(dv.decision, dv.winner) : ""]);
    let decide;
    if (editing) {
      const opts = labels.map((l) => ["precedence|" + l, l + " prevalece"]).concat(DIV_OTHER.map(([d, l]) => [d + "|", l]));
      const on = (val) => { const [d, w] = splitChoice(val); return v.choice === d && (d !== "precedence" || v.winner === w); };
      decide = `<section class="rv-section rv-decide"><h3>Decisão</h3>
        <div class="choice"><span class="field-label">Qual fonte vale, ou o que fazer</span>${seg(key, "divchoice", opts, on, { col: true, label: "Decisão da divergência" })}
          ${v.choice === "precedence" ? '<span class="choice-help">Vira candidata a regra de precedência na etapa 3.</span>' : ""}</div>
        ${v.choice === "precedence" && v.winner && !labels.includes(v.winner) ? `<p class="label secondary">Vencedor registrado: ${esc(v.winner)}</p>` : ""}
        ${textField(key, "reason", "Motivo", v.reason, { placeholder: v.choice === "open" ? "opcional" : "obrigatório" })}
        ${isPending ? savedNote(p) : `<div class="row"><button type="button" class="btn btn-ghost btn-sm" data-act="cancel" data-key="${esc(key)}">Cancelar</button></div>`}</section>`;
    } else {
      decide = `<section class="rv-section rv-decide"><h3>Decisão registrada</h3><dl class="kv"><dt>Decisão</dt><dd>${esc(decLabel(dv.decision, dv.winner))}</dd>${dv.reason ? `<dt>Motivo</dt><dd>${esc(dv.reason)}</dd>` : ""}</dl>
        ${dv.decided_by ? `<p class="label secondary">Decidida por ${esc(dv.decided_by)} em ${esc(fmtDate(dv.decided_at))}</p>` : ""}
        <div class="row"><button type="button" class="btn btn-outline btn-sm" data-act="alter" data-key="${esc(key)}"${disPropose()}>Propor alteração</button></div></section>`;
    }
    return `${cardOpen(key)}
      <div class="rv-card-head">${head}<h2 class="title">${esc(dv.topic)}</h2></div>
      <section class="rv-section"><h3>Fontes</h3>${sources.map((s, i) => `<div class="ev${i % 2 ? " b" : ""}"><b>${esc(labels[i])}</b> ${sourceLine(s)}</div>`).join("")}
        ${dv.hypothesis ? `<p class="p secondary"><b>Hipótese da IA</b> (não é fonte): ${esc(dv.hypothesis)}</p>` : ""}</section>
      ${isPending && p.rationale ? `<section class="rv-section"><h3>Justificativa do agente</h3><p class="p">${esc(p.rationale)}</p></section>` : ""}
      ${decide}</article>`;
  }

  // ---------- contexto (só leitura) ----------
  function sourcesRead() {
    const counts = new Map();
    const add = (path) => { if (path) counts.set(path, (counts.get(path) || 0) + 1); };
    const r = req();
    const fromItem = (it) => {
      (Array.isArray(it.evidence) ? it.evidence : []).forEach((e) => e && e.kind !== "conversation" && add(e.path));
      (Array.isArray(it.sources) ? it.sources : []).forEach((s) => s && add(s.path));
    };
    [].concat(r.competency_questions || [], r.gaps || [], r.divergences || []).forEach(fromItem);
    pending().forEach((p) => { fromItem(p.payload || {}); (viewOf(p).evidence || []).forEach((e) => e.kind === "source" && add(e.path)); });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }
  function contextHtml() {
    const r = req(), srcs = sourcesRead();
    const uc = (r.use_cases || []).map((u) => `<article class="rv-card"><div class="rv-card-head"><div class="badges">${badge("Caso de uso")}${badge(u.id, "badge-outline mono")}</div><h2 class="title">${esc(u.name)}</h2></div>
      <section class="rv-section"><dl class="kv"><dt>Descrição</dt><dd>${esc(u.description || "—")}</dd>${list(u.actors).length ? `<dt>Atores</dt><dd>${esc(list(u.actors).join(", "))}</dd>` : ""}${u.flow ? `<dt>Fluxo</dt><dd>${esc(list(u.flow).join(" → "))}</dd>` : ""}</dl></section></article>`).join("");
    return `<article class="rv-card"><div class="rv-card-head"><div class="badges">${badge("Requisitos")}</div><h2 class="title">Propósito e escopo</h2></div>
        <section class="rv-section"><dl class="kv"><dt>Propósito</dt><dd>${esc(r.purpose || "ainda não registrado")}</dd><dt>Escopo</dt><dd>${esc(r.scope || "ainda não registrado")}</dd>${list(r.users).length ? `<dt>Usuários</dt><dd>${esc(list(r.users).join(", "))}</dd>` : ""}</dl></section></article>
      ${uc || `<article class="rv-card"><section class="rv-section"><p class="p">${r.no_use_case ? `<b>Sem caso de uso:</b> ${esc(r.no_use_case)}` : "Nenhum caso de uso registrado. Peça ao agente para registrar um, ou o motivo de não haver."}</p></section></article>`}
      <article class="rv-card"><div class="rv-card-head"><div class="badges">${badge("Fontes lidas")}</div><h2 class="title">${plural(srcs.length, "arquivo citado", "arquivos citados")}</h2></div>
        <section class="rv-section">${srcs.length ? `<table><thead><tr><th>arquivo</th><th>citações</th></tr></thead><tbody>${srcs.map(([p, n]) => `<tr><td class="mono label">${esc(p)}</td><td>${n}</td></tr>`).join("")}</tbody></table>` : '<p class="p secondary">Nenhuma fonte citada ainda.</p>'}</section></article>`;
  }

  // ---------- fila e render ----------
  function visibleKeys() {
    return S.order.filter((k) => {
      const c = S.cards[k], st = stateOf(k);
      if (S.group && c.group !== S.group) return false;
      if (S.scope === "pending") return !c.applied;
      if (S.scope === "todo") return st === "todo";
      if (S.scope === "decided") return st === "draft" || st === "accept" || st === "reject";
      if (S.scope === "applied") return c.applied;
      return true;
    });
  }
  function counts() {
    const n = { todo: 0, decided: 0, unsaved: 0, applied: 0, pending: 0, byGroup: {} };
    for (const k of S.order) {
      const c = S.cards[k], st = stateOf(k);
      if (c.applied) { n.applied++; continue; }
      n.pending++;
      if (st === "todo") { n.todo++; n.byGroup[c.group] = (n.byGroup[c.group] || 0) + 1; }
      else { n.decided++; if (st === "draft") n.unsaved++; }
    }
    return n;
  }

  function position() {
    const keys = visibleKeys();
    const i = keys.indexOf(S.selected);
    return { keys, i };
  }
  function renderProgress() {
    const n = counts();
    const el = $("#rv-progress");
    if (S.scope === "context") { el.innerHTML = ""; el.hidden = true; return; }
    el.hidden = false;
    const { keys, i } = position();
    let pct = 0, text = "";
    if (S.scope === "todo") {
      pct = n.pending ? Math.round((n.decided / n.pending) * 100) : 0;
      text = n.pending ? `${n.decided} de ${n.pending} decididas` : "nada a decidir";
    } else {
      pct = keys.length ? Math.round(((i + 1) / keys.length) * 100) : 0;
      text = keys.length ? `${Math.max(i, 0) + 1} de ${keys.length}` : "nada aqui";
    }
    const where = S.group ? GROUP_LABEL[S.group] : { todo: "A decidir", decided: "Decididas", applied: "Aplicadas" }[S.scope] || "";
    el.innerHTML = `<div class="line" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>
      <div class="row"><span class="where">${esc(where)}</span><span class="pos">${esc(text)}</span><span class="spacer"></span>
        ${S.group ? '<button type="button" class="btn btn-ghost btn-sm" data-act="clear-group">todos os tipos</button>' : ""}
        ${S.api && bulkTargets().length ? `<button type="button" class="btn btn-outline btn-sm" data-act="accept-all" title="Aceita como proposto o que não exige escolha${S.group ? " neste tipo" : ", em todas as etapas"}. O que exige escolha, como a prioridade de uma pergunta, continua na lista. Depois é só salvar.">${I.check}<span>Aceitar tudo (${bulkTargets().length})</span></button>` : ""}
        ${S.scope !== "applied" && S.api ? `<button type="button" class="btn btn-ghost btn-sm" data-act="new-cq"${disPropose()}>${I.plus}<span>Nova pergunta</span></button>` : ""}</div>`;
  }
  function renderCardNav() {
    const el = $("#rv-cardnav");
    if (S.scope === "context" || !S.selected) { el.innerHTML = ""; el.hidden = true; return; }
    const { keys, i } = position();
    const decidedNow = S.selected && i === -1 && S.scope === "todo";
    const hasNext = decidedNow ? keys.length > 0 : i < keys.length - 1;
    const hasPrev = i > 0;
    const nextLabel = decidedNow ? "Próxima proposta" : S.scope === "todo" ? "Pular" : "Próxima";
    el.hidden = false;
    el.innerHTML = `<button type="button" class="btn btn-outline" data-act="prev"${hasPrev ? "" : " disabled"}>Anterior</button>
      <span class="spacer"></span>
      <span class="hint">${decidedNow ? "Rascunho guardado" : ""}</span>
      <button type="button" class="btn${decidedNow ? "" : " btn-outline"}" data-act="next"${hasNext ? "" : " disabled"}>${esc(nextLabel)}</button>`;
  }
  function go(step) {
    const { keys, i } = position();
    let target = null;
    if (step > 0) target = i === -1 ? keys[0] : keys[i + 1];
    else target = i > 0 ? keys[i - 1] : keys[0];
    if (!target) return;
    S.selected = target;
    renderDetail(); renderProgress(); renderCardNav();
    const top = $("#view-revisao");
    if (top) window.scrollTo({ top: Math.max(0, top.getBoundingClientRect().top + window.scrollY - 72), behavior: "smooth" });
  }
  function renderDetail() {
    const el = $("#rv-detail");
    if (S.scope === "context") { el.innerHTML = contextHtml(); return; }
    const keys = visibleKeys();
    if (!keys.includes(S.selected)) S.selected = keys[0] || null;
    if (!S.selected) {
      const n = counts();
      const done = S.scope === "todo" && n.pending && !n.todo;
      el.innerHTML = `<div class="callout ${done ? "callout-ok" : "callout-nota"}">${done ? I.ok : I.info}<div><div class="t">${esc(done ? "Tudo decidido" : S.scope === "applied" ? "Nada aplicado ainda" : S.scope === "decided" ? "Nenhuma decisão ainda" : (stage() || {}).label || "Nada a decidir")}</div><div class="b">${esc(done ? (n.unsaved ? "Salve as decisões e depois aplique, na barra de baixo." : "Aplique as decisões na barra de baixo.") : (stage() || {}).next_step || "")}</div></div></div>`;
      return;
    }
    el.innerHTML = cardHtml(S.selected);
  }
  function renderNav() {
    const n = counts();
    const nav = $("#rv-nav");
    const item = (scope, label, count, hot) => `<button type="button" class="nav-item" data-act="scope" data-scope="${scope}" aria-current="${S.scope === scope && !S.group}">${esc(label)}<span class="count${hot && count ? " hot" : ""}">${count}</span></button>`;
    const groups = GROUP_ORDER.filter((g) => S.order.some((k) => S.cards[k].group === g && !S.cards[k].applied));
    nav.innerHTML = `<div class="group-label">Fila</div>
      ${item("todo", "A decidir", n.todo, true)}${item("decided", "Decididas", n.decided, false)}${item("applied", "Aplicadas", n.applied, false)}
      ${groups.length ? `<div class="group-label" style="margin-top:12px">Por tipo</div>${groups.map((g) => `<button type="button" class="nav-item nav-sub" data-act="group" data-group="${g}" aria-current="${S.group === g}">${GROUP_ICON[g] || ""}${esc(GROUP_LABEL[g])}<span class="count">${n.byGroup[g] || 0}</span></button>`).join("")}` : ""}
      <div class="group-label" style="margin-top:12px">Contexto</div>${item("context", "Caso de uso e fontes", (req().use_cases || []).length, false)}`;
    const badgeEl = $("#tab-revisao-count");
    badgeEl.textContent = n.todo ? String(n.todo) : "";
    badgeEl.hidden = !n.todo;
  }
  function renderBar() {
    const n = counts();
    const bar = $("#rv-bar");
    const parts = [`<b>${n.todo}</b> a decidir`, `<b>${n.decided}</b> decididas` + (n.unsaved ? ` (${n.unsaved} não salvas)` : "")];
    $("#rv-counts").innerHTML = parts.join(" · ");
    const save = $("#rv-save"), apply = $("#rv-apply"), discardBtn = $("#rv-discard");
    save.disabled = !S.api || !S.reviewer.trim() || S.busy || !n.unsaved;
    save.className = "btn" + (n.unsaved ? "" : " btn-outline");
    const savedDecisions = n.decided - n.unsaved;
    apply.disabled = !S.api || S.busy || !savedDecisions || n.unsaved > 0;
    apply.className = "btn" + (savedDecisions && !n.unsaved ? "" : " btn-outline");
    apply.title = !S.api ? "abra com akme review" : n.unsaved ? "salve as decisões antes de aplicar" : !savedDecisions ? "nenhuma decisão salva para aplicar" : "";
    save.title = !S.api ? "abra com akme review para editar" : !S.reviewer.trim() ? "preencha o revisor" : "Atalhos: ← → navegam, a aceita, r rejeita, e edita";
    discardBtn.disabled = S.busy || !Object.keys(S.drafts).length;
    bar.hidden = S.tab !== "revisao";
  }
  function render() {
    buildCards();
    renderStage();
    renderNav();
    renderDetail();
    renderProgress();
    renderCardNav();
    renderBar();
  }
  function rerenderCard(key, focus) {
    if (S.selected !== key) return render();
    const el = $(`#rv-detail [data-card="${sel(key)}"]`);
    if (!el) return render();
    el.outerHTML = cardHtml(key);
    renderNav(); renderProgress(); renderCardNav(); renderBar();
    if (focus) {
      const card = $(`#rv-detail [data-card="${sel(key)}"]`);
      const target = card && (card.querySelector(focus) || card.querySelector("textarea, input, select"));
      if (target) target.focus({ preventScroll: true });
    }
  }
  function setMsg(kind, text) {
    const el = $("#rv-msg");
    el.className = "msg " + kind;
    el.textContent = text;
  }
  let toastTimer = null;
  function toast(text, action) {
    let el = $("#rv-toast");
    if (!el) { el = document.createElement("div"); el.id = "rv-toast"; el.className = "toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.innerHTML = `<span>${esc(text)}</span>${action ? `<button type="button" class="btn btn-sm" data-act="toast-action">${esc(action.label)}</button>` : ""}<button type="button" class="btn btn-ghost btn-icon btn-sm" aria-label="Fechar" data-act="toast-close" style="color:inherit">${I.x}</button>`;
    el.hidden = false;
    el.onclick = (e) => {
      const b = e.target.closest("[data-act]");
      if (!b) return;
      if (b.dataset.act === "toast-action" && action) action.onClick();
      el.hidden = true;
    };
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 12000);
  }

  // ---------- aplicar ----------
  function openApply() {
    const n = counts();
    const dlg = $("#rv-dialog");
    const saved = S.order.filter((k) => !S.cards[k].applied && (stateOf(k) === "accept" || stateOf(k) === "reject"));
    const acc = saved.filter((k) => stateOf(k) === "accept").length, rej = saved.length - acc;
    const st = stage();
    $("#rv-dialog-body").innerHTML = `<h2 class="h3-semibold">Aplicar decisões na ontologia</h2>
      <p class="p">${plural(acc, "aceita", "aceitas")} e ${plural(rej, "rejeitada", "rejeitadas")}. O validate roda antes; se houver erro novo, nada muda.</p>
      ${st && st.gate_active ? `<div class="callout callout-atencao">${I.warn}<div><div class="t">Requisitos ainda abertos</div><div class="b">Classes, relações e termos ficam de fora até a etapa 1 fechar.</div></div></div>` : ""}
      <div class="field"><label class="field-label" for="rv-approver">Quem aprova</label><input id="rv-approver" class="input" type="text" autocomplete="name" value="${esc(S.reviewer)}" placeholder="seu nome"></div>
      <div class="dlg-actions"><button type="button" class="btn btn-outline" data-act="dlg-close">Cancelar</button><button type="button" class="btn" data-act="dlg-apply">Aplicar ${saved.length}</button></div>`;
    dlg.showModal();
    const inp = $("#rv-approver"); if (inp) inp.focus();
    void n;
  }
  async function doApply() {
    const approver = ($("#rv-approver") || {}).value || "";
    if (!approver.trim()) { $("#rv-approver").focus(); return; }
    const body = $("#rv-dialog-body");
    const btn = body.querySelector('[data-act="dlg-apply"]');
    if (btn) { btn.disabled = true; btn.textContent = "Aplicando…"; }
    S.busy = true; renderBar();
    let out = null, err = null;
    try { out = await S.api.post("/api/apply", { approved_by: approver.trim(), stage: "all" }); }
    catch (e) { err = e; }
    S.busy = false;
    if (err) {
      const errs = (err.body && err.body.new_errors) || [];
      body.innerHTML = `<h2 class="h3-semibold">Nada foi aplicado</h2>
        <div class="callout callout-erro">${I.warn}<div><div class="t">${esc(err.message)}</div>${errs.length ? `<div class="b"><ul>${errs.map((f) => `<li><span class="mono label">${esc(f.check)}</span> ${esc(f.subject || "")}: ${esc(f.message)}</li>`).join("")}</ul></div>` : ""}</div></div>
        <p class="p secondary">Corrija as propostas (ou peça ao agente) e tente de novo. A ontologia continua como estava.</p>
        <div class="dlg-actions"><button type="button" class="btn" data-act="dlg-close">Fechar</button></div>`;
      try { await reload(); } catch (e) {}
      render();
      return;
    }
    const s = out.summary || {}, after = out.stage_after || {};
    const types = Object.entries(s.applied_types || {}).map(([t, n]) => `${n} ${t.replace("add_", "").replace("_", " ")}`).join(", ");
    body.innerHTML = `<h2 class="h3-semibold">Aplicado</h2>
      <div class="callout callout-ok">${I.ok}<div><div class="t">${plural((out.applied || []).length, "proposta entrou", "propostas entraram")} na ontologia; ${plural((out.rejected || []).length, "rejeitada registrada", "rejeitadas registradas")} no changelog.</div>
        <div class="b">${types ? `<p>${esc(types)}.</p>` : ""}${(out.held_by_gate || []).length ? `<p>${out.held_by_gate.length} propostas da ontologia ficaram esperando os requisitos fecharem.</p>` : ""}${(out.preexisting_errors || []).length ? `<p>O validate já tinha ${out.preexisting_errors.length} erros antes; eles continuam lá.</p>` : ""}</div></div></div>
      ${after.label ? `<div class="callout callout-nota">${I.info}<div><div class="t">${esc(after.label)}</div><div class="b">${esc(after.next_step || "")}</div></div></div>` : ""}
      <div class="dlg-actions"><button type="button" class="btn" data-act="dlg-close">Fechar</button></div>`;
    try { await reload(); } catch (e) {}
    render();
    setMsg("success", "Decisões aplicadas. " + (after.next_step || ""));
  }

  // ---------- eventos ----------
  function onClick(e) {
    const b = e.target.closest("[data-act]");
    if (!b || b.disabled) return;
    const act = b.dataset.act, key = b.dataset.key;
    switch (act) {
      case "scope": S.scope = b.dataset.scope; S.group = null; S.selected = null; render(); return;
      case "group": S.group = b.dataset.group; if (S.scope === "applied" || S.scope === "context") S.scope = "todo"; S.selected = null; render(); return;
      case "clear-group": S.group = null; render(); return;
      case "select": S.selected = key; renderDetail(); renderProgress(); renderCardNav(); return;
      case "next": go(1); return;
      case "prev": go(-1); return;
      case "set": {
        const d = draft(key), f = b.dataset.field, val = b.dataset.value;
        if (f === "divchoice") { const [ch, w] = splitChoice(val); d.choice = ch; d.winner = ch === "precedence" ? w : ""; }
        else d[f] = val;
        if (f === "decision" && val === "reject") S.editing.delete(key);
        S.invalid.delete(key);
        rerenderCard(key, f === "decision" && val === "reject" ? "textarea" : `[data-act="set"][data-field="${sel(f)}"][data-value="${sel(val)}"]`);
        return;
      }
      case "edit-on": { const d = draft(key); if (!d.decision && (S.cards[key].kind === "cq" || S.cards[key].kind === "generic")) d.decision = "accept"; S.editing.add(key); rerenderCard(key, "textarea, input"); return; }
      case "edit-off": {
        S.editing.delete(key);
        const c = S.cards[key], d = draft(key), base = baseline(key);
        if (c.kind === "generic") d.edits = base.edits;
        else if (c.kind === "cq") Object.assign(d, { question: base.question, type: base.type, concepts: base.concepts });
        rerenderCard(key, null);
        return;
      }
      case "alter": case "remove": draft(key).mode = act; rerenderCard(key, null); return;
      case "cancel": delete S.drafts[key]; S.invalid.delete(key); rerenderCard(key, null); return;
      case "new-cq": {
        const k = "n:" + ++S.newSeq;
        S.newKeys.push(k);
        S.scope = "todo"; S.group = null; S.selected = k;
        render();
        const t = $(`#${fid(k, "question")}`); if (t) t.focus();
        return;
      }
      case "drop-new": delete S.drafts[key]; S.newKeys = S.newKeys.filter((k) => k !== key); S.invalid.delete(key); S.selected = null; render(); return;
      case "check": return checkQuote(b);
      case "accept-all": return acceptAll();
      case "save": return save();
      case "discard": return discard();
      case "apply": return openApply();
      case "dlg-close": $("#rv-dialog").close(); return;
      case "dlg-apply": return doApply();
    }
  }
  function onInput(e) {
    const el = e.target;
    const key = el.dataset && el.dataset.key, f = el.dataset && el.dataset.field;
    if (!key || !f || !S.cards[key]) return;
    const d = draft(key);
    if (f.startsWith("edit:")) {
      const k = f.slice(5), def = (S.cards[key].view.editable || []).find((x) => x.key === k);
      d.edits[k] = def && def.kind === "list" ? el.value.split(",").map((s) => s.trim()).filter(Boolean) : el.value;
      if (!d.decision) d.decision = "accept";
    } else if (f === "concepts") {
      d.concepts = el.value.split(",").map((s) => s.trim()).filter(Boolean);
      const prev = $(`#rv-detail [data-preview="${sel(key)}"]`);
      if (prev) prev.innerHTML = conceptBadges(d.concepts);
    } else if (f === "use_cases") {
      const card = el.closest("[data-card]");
      d.use_cases = Array.from(card.querySelectorAll('input[data-field="use_cases"]:checked')).map((x) => x.value);
    } else {
      d[f] = el.value;
    }
    renderNav(); renderProgress(); renderBar();
  }
  function onKey(e) {
    if (S.tab !== "revisao" || $("#rv-dialog").open) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (["input", "textarea", "select"].includes(tag) || e.target.isContentEditable || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === "j" || e.key === "n") { e.preventDefault(); go(1); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp" || e.key === "k" || e.key === "p") { e.preventDefault(); go(-1); }
    else if ((e.key === "a" || e.key === "r") && S.selected && S.api) {
      const c = S.cards[S.selected];
      if (!c || c.applied || c.kind === "n-cq" || c.kind === "gap" || c.kind === "div") return;
      if (e.key === "r" && c.view && c.view.rejectable === false) return;
      e.preventDefault();
      draft(S.selected).decision = e.key === "a" ? "accept" : "reject";
      if (e.key === "r") S.editing.delete(S.selected);
      rerenderCard(S.selected, e.key === "r" ? "textarea" : null);
    } else if (e.key === "e" && S.selected && S.api) {
      const c = S.cards[S.selected];
      if (c && !c.applied && (c.kind === "cq" || (c.kind === "generic" && (c.view.editable || []).length))) { e.preventDefault(); const d = draft(S.selected); if (!d.decision) d.decision = "accept"; S.editing.add(S.selected); rerenderCard(S.selected, "textarea, input"); }
    }
  }
  async function checkQuote(b) {
    const out = b.nextElementSibling, q = b.dataset.q || "";
    out.textContent = " conferindo…";
    try {
      const res = await S.api.get("/api/sources?q=" + encodeURIComponent(q) + "&case_sensitive=false");
      const n = (res.documents || []).length + (res.tables || []).length;
      const where = Array.from(new Set((res.documents || []).map((d) => d.path).concat((res.tables || []).map((t) => t.path)))).slice(0, 3).join(", ");
      out.textContent = res.found ? ` encontrada (${n} ${n === 1 ? "trecho" : "trechos"}${where ? ": " + where : ""})` : " não encontrada nas fontes";
    } catch (e) { out.textContent = " erro: " + e.message; }
  }

  async function poll() {
    if (S.polling || !S.api) return;
    S.polling = true;
    let failures = 0;
    while (S.api) {
      try {
        const r = await S.api.get(`/api/events?since=${encodeURIComponent(S.token || "")}&timeout=25`);
        failures = 0;
        if (!S.token) { S.token = r.token; continue; }
        if (r.changed && !S.busy) {
          S.token = r.token;
          const fresh = await reload({ announce: true });
          render();
          if (!fresh) setMsg("info", "Dados atualizados.");
        } else S.token = r.token;
      } catch (e) {
        failures++;
        await new Promise((res) => setTimeout(res, Math.min(5000 * failures, 30000)));
      }
    }
  }

  function renderShell() {
    const viewEl = $("#view-revisao");
    viewEl.innerHTML = `<div class="rv">
      ${S.api ? "" : `<div class="callout callout-nota">${I.info}<div><div class="t">Modo leitura</div><div class="b">Rode <code>uv run akme review</code> para decidir e aplicar.</div></div></div>`}
      <div class="rv-one"><div class="rv-progress" id="rv-progress"></div><div class="rv-detail" id="rv-detail"></div><div class="rv-cardnav" id="rv-cardnav"></div></div>
    </div>
    <dialog class="dlg" id="rv-dialog"><div class="dlg-body" id="rv-dialog-body"></div></dialog>`;
    let bar = $("#rv-bar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "rv-bar"; bar.className = "rv-bar";
      bar.innerHTML = `<label class="rv-reviewer"><span class="field-label">Revisor</span><input id="reviewer" class="input" type="text" autocomplete="name" placeholder="seu nome"${S.api ? "" : " disabled"}></label>
        <span class="counts" id="rv-counts"></span><span id="rv-msg" class="msg" role="status" aria-live="polite"></span>
        <div class="actions"><button type="button" class="btn btn-ghost" id="rv-discard" data-act="discard">Descartar</button>
        <button type="button" class="btn btn-outline" id="rv-save" data-act="save" title="Atalhos: ← → navegam, a aceita, r rejeita, e edita">Salvar decisões</button>
        <button type="button" class="btn btn-outline" id="rv-apply" data-act="apply">Aplicar decididas</button></div>`;
      document.body.appendChild(bar);
      bar.addEventListener("click", onClick);
    }
    const input = $("#reviewer");
    input.value = S.reviewer;
    input.disabled = !S.api;
    if (input.dataset.wired) return;
    input.dataset.wired = "1";
    input.addEventListener("input", () => {
      const wasEmpty = !S.reviewer.trim();
      S.reviewer = input.value;
      store("akme-reviewer", S.reviewer);
      if (wasEmpty !== !S.reviewer.trim()) render(); else renderBar();
    });
  }

  function init(data, api, hooks) {
    S.data = data || {};
    S.data.requirements = S.data.requirements || {};
    S.api = api || null;
    S.hooks = hooks || {};
    S.token = (data && data.token) || null;
    S.reviewer = read("akme-reviewer") || "";
    renderShell();
    if (!S.wired) {
      const viewEl = $("#view-revisao");
      viewEl.addEventListener("click", onClick);
      viewEl.addEventListener("input", onInput);
      viewEl.addEventListener("change", onInput);
      $("#rv-nav").addEventListener("click", onClick);
      $("#tab-ontologia").addEventListener("click", () => setTab("ontologia"));
      $("#tab-revisao").addEventListener("click", () => setTab("revisao"));
      document.addEventListener("keydown", onKey);
      S.wired = true;
    }
    const n = counts();
    const saved = read("akme-tab");
    buildCards();
    const c0 = counts();
    S.scope = c0.todo ? "todo" : c0.pending ? "decided" : "todo";
    setTab(c0.todo ? "revisao" : saved || "revisao", false);
    render();
    void n;
    if (S.api) poll();
  }

  window.AkmeReview = { init, setTab };
})();
