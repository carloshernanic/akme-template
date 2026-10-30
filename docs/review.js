/* Aba Revisao do docs/index.html. Sem biblioteca, sem build.
   window.AkmeReview.init(data, api): data = window.AKME_DATA (ou ontology.json);
   api = null (modo leitura) ou { get(path), post(path, body) } quando servida por `akme review`. */
(function () {
  "use strict";

  const CQ_TYPES = [
    ["classificacao_hierarquia", "Classificação e hierarquia"],
    ["relacao_entre_conceitos", "Relação entre conceitos"],
    ["atributos", "Atributos"],
    ["quantidade_agregacao", "Quantidade e agregação"],
    ["tempo_estado", "Tempo e estado"],
    ["regras_restricoes", "Regras e restrições"],
  ];
  const PRIORITIES = [["high", "Alta"], ["medium", "Média"], ["low", "Baixa"]];
  const USES = [["approved", "Ajuste"], ["reserved", "Reservada"]];
  const DECISIONS = [["accept", "Aceitar"], ["reject", "Rejeitar"]];
  const GAP_DECISIONS = [
    ["request_from_client", "Pedir dado ao cliente"],
    ["reformulate", "Reformular a CQ"],
    ["drop", "Descartar"],
    ["open", "Deixar aberta"],
  ];
  const DIV_OTHER = [
    ["distinct_terms", "São conceitos distintos"],
    ["ask_expert", "Perguntar ao especialista"],
    ["dismiss", "Descartar"],
    ["open", "Deixar aberta"],
  ];
  const LABELS = {
    type: Object.fromEntries(CQ_TYPES),
    priority: Object.fromEntries(PRIORITIES),
    status: { proposed: "Proposta", approved: "Ajuste", reserved: "Reservada", rejected: "Rejeitada", deprecated: "Deprecated" },
    gap: Object.fromEntries(GAP_DECISIONS),
    div: Object.assign({ precedence: "Precedência" }, Object.fromEntries(DIV_OTHER)),
  };
  const GROUP_OF_TYPE = {
    add_competency_question: "cq", update_competency_question: "cq", remove_competency_question: "cq",
    add_gap: "gap", update_gap: "gap", add_divergence: "div", update_divergence: "div",
    add_use_case: "uc", add_requirement: "uc",
  };
  // tipos da etapa 1 (akme/models.py STAGE1_TYPES); os demais so se aprovam pelo chat
  const STAGE1 = new Set([
    "add_use_case", "update_competency_question", "remove_competency_question", "add_gap", "add_divergence",
    "update_gap", "update_divergence", "add_competency_question", "add_requirement", "add_glossary",
  ]);
  const groupOf = (t) => (STAGE1.has(t) ? GROUP_OF_TYPE[t] || "other" : "ro");
  const TYPE_TITLE = {
    update_competency_question: "proposta de alteração", remove_competency_question: "proposta de exclusão",
    update_gap: "proposta de alteração", update_divergence: "proposta de alteração",
    add_use_case: "novo caso de uso", add_requirement: "novo requisito",
  };

  const S = {
    data: null, api: null, drafts: {}, newKeys: [], newSeq: 0, cards: {}, reviewer: "",
    busy: false, invalid: new Set(), tab: null, wired: false,
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
  const origin = (by) => (!by || by === "agent" ? "proposta pela IA" : "proposta por " + by);

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

  function findApplied(key, id) { return (req()[key] || []).find((x) => x.id === id) || null; }

  // ---------- portao e abas ----------
  function gate() {
    const st = S.data.requirements_status || { closed: true, missing: [] };
    const active = typeof st.gate_active === "boolean" ? st.gate_active : st.closed === false;
    return { st, active };
  }

  function applyGate() {
    const { st, active } = gate();
    const banner = $("#gate-banner");
    $("#tab-ontologia").hidden = active;
    banner.hidden = !active;
    if (active) {
      banner.innerHTML = `<div><div class="rv-banner-t">Requisitos abertos. Falta:</div><ul>${(st.missing || []).map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div>`;
    }
    setTab(active ? "revisao" : S.tab || read("akme-tab") || "ontologia", false);
  }

  function setTab(name, persist = true) {
    if (name !== "revisao") name = "ontologia";
    if (name === "ontologia" && gate().active) name = "revisao";
    const prev = S.tab;
    S.tab = name;
    $("#view-ontologia").hidden = name !== "ontologia";
    $("#view-revisao").hidden = name !== "revisao";
    $("#tab-ontologia").setAttribute("aria-selected", String(name === "ontologia"));
    $("#tab-revisao").setAttribute("aria-selected", String(name === "revisao"));
    const ontNav = [$("#nav"), $(".search")].filter(Boolean);
    ontNav.forEach((el) => { el.hidden = name === "revisao"; });
    const rvNav = $("#rv-nav");
    if (rvNav) rvNav.hidden = name !== "revisao";
    if (persist) store("akme-tab", name);
    // o grafo e desenhado com o tamanho do container; ao voltar para a aba, redesenha
    if (name === "ontologia" && prev && prev !== "ontologia") dispatchEvent(new Event("resize"));
  }

  // ---------- modelo de cartoes ----------
  function buildCards() {
    const cards = {};
    for (const p of pending()) {
      const t = p.type;
      let kind = "p-simple";
      if (t === "add_competency_question") kind = "p-addcq";
      else if (t === "add_gap") kind = "p-addgap";
      else if (t === "add_divergence") kind = "p-adddiv";
      if (!STAGE1.has(t)) kind = "p-readonly";
      cards["p:" + p.id] = { kind, item: p, group: groupOf(t) };
    }
    for (const q of req().competency_questions || []) cards["a:cq:" + q.id] = { kind: "a-cq", item: q, group: "cq" };
    for (const g of req().gaps || []) cards["a:gap:" + g.id] = { kind: "a-gap", item: g, group: "gap" };
    for (const d of req().divergences || []) cards["a:div:" + d.id] = { kind: "a-div", item: d, group: "div" };
    for (const k of S.newKeys) cards[k] = { kind: "n-cq", item: null, group: "cq" };
    S.cards = cards;
    // descarta rascunhos de pendentes que sumiram (aplicados ou rejeitados em outro lugar)
    for (const k of Object.keys(S.drafts)) if (!cards[k]) delete S.drafts[k];
  }

  function cqFields(src) {
    const st = src.status;
    return {
      question: src.question || "", type: src.type || "", concepts: list(src.concepts),
      priority: src.priority || "", use: st === "approved" || st === "reserved" ? st : "", answer: src.answer || "",
    };
  }

  function baseline(key) {
    const c = S.cards[key];
    if (!c) return null;
    const p = c.item;
    const r = p && p.review;
    const e = (r && r.edits) || {};
    const pl = (p && p.payload) || {};
    switch (c.kind) {
      case "p-addcq":
        return Object.assign({ decision: r ? r.decision : null }, cqFields(Object.assign({}, pl, e)), { reason: (r && r.reason) || "" });
      case "p-simple":
        return { decision: r ? r.decision : null, reason: (r && r.reason) || "" };
      case "p-addgap":
        return { choice: r ? e.decision ?? pl.decision ?? "" : "", note: (e.note ?? pl.note) || "" };
      case "p-adddiv":
        return { choice: r ? e.decision ?? pl.decision ?? "" : "", winner: (e.winner ?? pl.winner) || "", reason: (e.reason ?? pl.reason) || "" };
      case "a-cq":
        return Object.assign({ mode: "" }, cqFields(p), { reason: "" });
      case "a-gap":
        return { mode: "", choice: p.decision || "", note: p.note || "" };
      case "a-div":
        return { mode: "", choice: p.decision || "", winner: p.winner || "", reason: p.reason || "" };
      case "n-cq":
        return { question: "", type: "", concepts: [], priority: "", use: "", answer: "", use_cases: [] };
    }
    return null;
  }

  const view = (key) => S.drafts[key] || baseline(key);
  function draft(key) {
    if (!S.drafts[key]) S.drafts[key] = JSON.parse(JSON.stringify(baseline(key)));
    return S.drafts[key];
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
    if (c.kind.startsWith("a-")) return d.mode === "remove" || (d.mode === "alter" && Object.keys(appliedDiff(c, d)).length > 0);
    const decided = c.kind === "p-addgap" || c.kind === "p-adddiv" ? !!d.choice : !!d.decision;
    return decided && JSON.stringify(d) !== JSON.stringify(baseline(key));
  }

  function cardLabel(key) {
    const c = S.cards[key];
    if (!c) return key;
    if (c.kind === "n-cq") return "Nova CQ";
    const it = c.item;
    return (it.payload && it.payload.id) || it.id;
  }

  // ---------- operacoes ----------
  function cqError(d) {
    if (!d.question.trim()) return "pergunta vazia";
    if (!d.type) return "escolha o tipo";
    if (!d.concepts.length) return "informe ao menos um conceito";
    if (!d.priority) return "escolha a prioridade";
    if (!d.use) return "escolha o uso (ajuste ou reservada)";
    if (d.use === "reserved" && !d.answer.trim()) return "resposta esperada obrigatória em reservada";
    return "";
  }

  function buildOp(key) {
    const c = S.cards[key], d = S.drafts[key], p = c.item, reviewer = S.reviewer.trim();
    const fail = (m) => ({ error: `${cardLabel(key)}: ${m}` });
    const review = (rest) => ({ path: "/api/review", body: Object.assign({ edit_id: p.id, reviewer }, rest) });
    const propose = (type, payload) => ({ path: "/api/propose", body: { type, payload, reviewer } });
    const rejectOp = () => (d.reason.trim() ? review({ decision: "reject", reason: d.reason.trim() }) : fail("motivo obrigatório para rejeitar"));
    switch (c.kind) {
      case "p-addcq": {
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
      case "p-simple":
        return d.decision === "reject" ? rejectOp() : review({ decision: "accept" });
      case "p-addgap": {
        if (d.choice !== "open" && !d.note.trim()) return fail("motivo obrigatório (só Deixar aberta dispensa)");
        const edits = { decision: d.choice };
        if (d.note.trim()) edits.note = d.note.trim();
        return review({ decision: "accept", edits });
      }
      case "p-adddiv": {
        if (d.choice === "precedence" && !d.winner) return fail("escolha a fonte que prevalece");
        if (d.choice !== "open" && !d.reason.trim()) return fail("motivo obrigatório (só Deixar aberta dispensa)");
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
          if (!d.reason.trim()) return fail("motivo obrigatório para propor exclusão");
          return propose("remove_competency_question", { id: p.id, reason: d.reason.trim() });
        }
        const diff = appliedDiff(c, d);
        if ("question" in diff && !diff.question) return fail("pergunta vazia");
        if ("concepts" in diff && !diff.concepts.length) return fail("informe ao menos um conceito");
        if (d.use === "reserved" && !d.answer.trim()) return fail("resposta esperada obrigatória em reservada");
        return propose("update_competency_question", Object.assign({ id: p.id }, diff));
      }
      case "a-gap": {
        if (d.choice !== "open" && !d.note.trim()) return fail("motivo obrigatório (só Deixar aberta dispensa)");
        const diff = appliedDiff(c, d);
        return propose("update_gap", Object.assign({ id: p.id, decision: d.choice }, diff));
      }
      case "a-div": {
        if (d.choice === "precedence" && !d.winner) return fail("escolha a fonte que prevalece");
        if (d.choice !== "open" && !d.reason.trim()) return fail("motivo obrigatório (só Deixar aberta dispensa)");
        const diff = appliedDiff(c, d);
        return propose("update_divergence", Object.assign({ id: p.id, decision: d.choice }, diff));
      }
    }
    return fail("cartão desconhecido");
  }

  function orderedKeys() {
    return Array.from(document.querySelectorAll("#rv-body [data-card]")).map((el) => el.dataset.card);
  }

  async function reload() {
    const [pend, requirements] = await Promise.all([S.api.get("/api/pending"), S.api.get("/api/requirements")]);
    const r = Object.assign({}, requirements);
    const status = r.status;
    delete r.status;
    delete r.data_request;
    S.data.pending = pend;
    S.data.requirements = Object.assign({}, S.data.requirements, r);
    if (status) S.data.requirements_status = status;
  }

  async function save() {
    if (!S.api || !S.reviewer.trim() || S.busy) return;
    const keys = orderedKeys().filter(isChanged);
    if (!keys.length) return setMsg("info", "Nada alterado para salvar.");
    const ops = keys.map((k) => Object.assign({ key: k }, buildOp(k)));
    const bad = ops.filter((o) => o.error);
    S.invalid = new Set(bad.map((o) => o.key));
    if (bad.length) {
      render();
      setMsg("error", bad[0].error + (bad.length > 1 ? ` (e mais ${bad.length - 1})` : ""));
      const el = $(`#rv-body [data-card="${sel(bad[0].key)}"]`);
      if (el) { el.scrollIntoView({ block: "center" }); const f = el.querySelector("textarea, input, select, button:not(:disabled)"); if (f) f.focus({ preventScroll: true }); }
      return;
    }
    S.busy = true;
    renderFooter();
    setMsg("info", "Salvando…");
    let ok = 0, err = null;
    for (const o of ops) {
      try {
        await S.api.post(o.path, o.body);
        delete S.drafts[o.key];
        S.newKeys = S.newKeys.filter((k) => k !== o.key);
        ok++;
      } catch (e) {
        err = `${cardLabel(o.key)}: ${e.message}`;
        S.invalid.add(o.key);
        break;
      }
    }
    try { await reload(); } catch (e) { err = err || "falha ao recarregar: " + e.message; }
    S.busy = false;
    applyGate();
    render();
    if (err) setMsg("error", `${ok} de ${ops.length} salvas. Erro em ${err}`);
    else setMsg("success", `${ok} ${ok === 1 ? "decisão salva" : "decisões salvas"} em ontology/pending/. Depois, no chat: "aplica".`);
  }

  function discard() {
    S.drafts = {};
    S.newKeys = [];
    S.invalid = new Set();
    render();
    setMsg("info", "Alterações locais descartadas.");
  }

  // ---------- pecas de HTML ----------
  const dis = () => (S.api ? "" : " disabled");
  const disPropose = () => (S.api && S.reviewer.trim() ? "" : " disabled");

  function seg(key, field, options, isOn, opts = {}) {
    return `<div class="rv-seg${opts.col ? " rv-col" : ""}" role="group" aria-label="${esc(opts.label || field)}">${options.map(([v, l]) =>
      `<button type="button" data-act="set" data-key="${esc(key)}" data-field="${esc(field)}" data-value="${esc(v)}" aria-pressed="${isOn(v)}"${opts.no && v === "reject" ? ' class="rv-no"' : ""}${dis()}>${esc(l)}</button>`).join("")}</div>`;
  }

  function textField(key, field, label, value, opts = {}) {
    const id = fid(key, field);
    const tag = opts.input
      ? `<input id="${id}" class="rv-input" type="text" data-key="${esc(key)}" data-field="${esc(field)}" value="${esc(value)}" placeholder="${esc(opts.placeholder || "")}"${dis()}>`
      : `<textarea id="${id}" class="rv-input rv-text${opts.q ? " rv-q" : ""}" rows="${opts.rows || 2}" data-key="${esc(key)}" data-field="${esc(field)}" placeholder="${esc(opts.placeholder || "")}"${dis()}>${esc(value)}</textarea>`;
    return `<div class="rv-field"><label class="rv-lbl" for="${id}">${esc(label)}</label>${tag}</div>`;
  }

  function typeSelect(key, value) {
    const id = fid(key, "type");
    return `<div class="rv-field"><label class="rv-lbl" for="${id}">Tipo</label><select id="${id}" class="rv-input" data-key="${esc(key)}" data-field="type"${dis()}>
      <option value=""${value ? "" : " selected"}>escolha o tipo</option>${CQ_TYPES.map(([v, l]) => `<option value="${esc(v)}"${v === value ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></div>`;
  }

  const chips = (items, cls = "alt") => items.map((x) => `<span class="chip ${cls}">${esc(x)}</span>`).join("");
  const conceptChips = (cs) => (cs.length ? chips(cs, "outline") : '<span class="label tertiary">sem conceitos</span>');

  function conceptsField(key, concepts) {
    return `${textField(key, "concepts", "Conceitos (separados por vírgula)", concepts.join(", "), { input: true, placeholder: "Pedido, Cliente" })}
      <div class="chips rv-concepts" data-preview="${esc(key)}">${conceptChips(concepts)}</div>`;
  }

  function evidenceHtml(items) {
    items = Array.isArray(items) ? items : [];
    if (!items.length) return "";
    return `<div class="rv-ev"><span class="rv-lbl">Evidência</span>${items.map((ev) => {
      if (ev && ev.kind === "conversation") {
        return `<div><span class="chip alt">conversa</span> ${esc(ev.who)} · ${esc(fmtDate(ev.when))}${ev.note ? " · " + esc(ev.note) : ""}</div>`;
      }
      return `<div>${sourceLine(ev || {})}</div>`;
    }).join("")}</div>`;
  }

  function sourceLine(s) {
    const check = S.api && s.quote
      ? ` <button type="button" class="rv-link" data-act="check" data-q="${esc(s.quote)}">conferir citação</button><span class="rv-checked" aria-live="polite"></span>` : "";
    return `<span class="rv-path">${esc(s.path || "")}${s.locator ? ", " + esc(s.locator) : ""}</span>${s.quote ? ` · “${esc(s.quote)}”` : ""}${check}`;
  }

  function decisionBlock(key, v) {
    return `<span class="rv-lbl">Decisão</span>${seg(key, "decision", DECISIONS, (x) => v.decision === x, { label: "Decisão", no: true })}
      ${v.decision === "reject" ? textField(key, "reason", "Motivo da rejeição", v.reason, { placeholder: "obrigatório" }) : ""}`;
  }

  function savedNote(p) {
    const r = p && p.review;
    return r ? `<p class="label secondary">Decisão salva por ${esc(r.reviewer)} em ${esc(fmtDate(r.reviewed_at))} (${r.decision === "accept" ? "aceitar" : "rejeitar"}). Pode mudar.</p>` : "";
  }

  function cardOpen(key, extra = "", wide = false) {
    const cls = ["rv-card"];
    if (wide) cls.push("rv-wide");
    if (extra) cls.push(extra);
    if (S.invalid.has(key)) cls.push("rv-invalid");
    return `<article class="${cls.join(" ")}" data-card="${esc(key)}">`;
  }

  function diffTable(current, payload) {
    const fields = Object.keys(payload || {}).filter((k) => k !== "id");
    if (!fields.length) return '<p class="p secondary">Sem campos alterados.</p>';
    return `<table class="rv-diff"><thead><tr><th>campo</th><th>antes</th><th>depois</th></tr></thead><tbody>${fields.map((f) =>
      `<tr><td class="mono label">${esc(f)}</td><td class="secondary">${esc(fmtValue(f, current ? current[f] : undefined))}</td><td>${esc(fmtValue(f, payload[f]))}</td></tr>`).join("")}</tbody></table>`;
  }

  function kvList(obj) {
    const entries = Object.entries(obj || {});
    if (!entries.length) return "";
    return `<dl class="rv-kv">${entries.map(([k, v]) => `<dt class="rv-lbl">${esc(k)}</dt><dd>${esc(fmtValue(k, v))}</dd>`).join("")}</dl>`;
  }

  // ---------- cartoes ----------
  function cardHtml(key) {
    const c = S.cards[key];
    if (!c) return "";
    switch (c.kind) {
      case "p-addcq": return pendingCqCard(key, c.item);
      case "p-simple": return simpleCard(key, c.item);
      case "p-readonly": return readonlyCard(key, c.item);
      case "p-addgap": return gapCard(key, c.item.payload || {}, c.item, true);
      case "p-adddiv": return divCard(key, c.item.payload || {}, c.item, true);
      case "a-cq": return appliedCqCard(key, c.item);
      case "a-gap": return gapCard(key, c.item, null, false);
      case "a-div": return divCard(key, c.item, null, false);
      case "n-cq": return newCqCard(key);
    }
    return "";
  }

  function cqEditColumns(key, v) {
    return `${textField(key, "question", "Pergunta", v.question, { q: true, rows: 2 })}
      <div class="rv-row2">${typeSelect(key, v.type)}<div>${conceptsField(key, v.concepts)}</div></div>`;
  }

  function cqDecisionFields(key, v) {
    return `<span class="rv-lbl">Prioridade</span>${seg(key, "priority", PRIORITIES, (x) => v.priority === x, { label: "Prioridade" })}
      <span class="rv-lbl">Uso</span>${seg(key, "use", USES, (x) => v.use === x, { label: "Uso" })}
      ${v.use === "reserved" ? textField(key, "answer", "Resposta esperada (reservada)", v.answer, { placeholder: "trecho que a resposta precisa conter" }) : ""}`;
  }

  function pendingCqCard(key, p) {
    const v = view(key), pl = p.payload || {};
    const edited = v.question.trim() !== (pl.question || "") || (v.type && v.type !== pl.type) || !sameList(v.concepts, pl.concepts);
    return `${cardOpen(key, v.decision === "reject" ? "rv-dim" : "")}
      <div class="rv-main">
        <div class="rv-id"><span>${esc(pl.id || p.id)}</span><span>· ${esc(origin(p.proposed_by))}</span>${edited ? '<span class="rv-edited">· editada pelo revisor</span>' : ""}</div>
        ${cqEditColumns(key, v)}
        ${evidenceHtml(pl.evidence)}
        ${list(pl.use_cases).length ? `<div class="chips rv-meta"><span class="rv-lbl">Casos de uso</span>${chips(list(pl.use_cases), "outline mono")}</div>` : ""}
        ${p.rationale ? `<p class="p secondary">Justificativa: ${esc(p.rationale)}</p>` : ""}
      </div>
      <div class="rv-dec">
        ${decisionBlock(key, v)}
        ${v.decision === "reject" ? "" : cqDecisionFields(key, v)}
        ${savedNote(p)}
      </div></article>`;
  }

  function simpleCard(key, p) {
    const v = view(key), pl = p.payload || {}, t = p.type;
    let body = "";
    if (t === "update_competency_question" || t === "update_gap" || t === "update_divergence") {
      const listKey = t === "update_competency_question" ? "competency_questions" : t === "update_gap" ? "gaps" : "divergences";
      const current = p.current || findApplied(listKey, pl.id);
      const title = current ? current.question || current.topic || "" : "";
      body = `${title ? `<p class="rv-q">${esc(title)}</p>` : ""}${diffTable(current, pl)}`;
    } else if (t === "remove_competency_question") {
      const current = p.current || findApplied("competency_questions", pl.id);
      const refs = p.references;
      let refsHtml;
      if (!refs) refsHtml = '<p class="label secondary">Referências disponíveis só com akme review.</p>';
      else {
        const any = refs.changelog.length || refs.evidence.length || refs.in_questions;
        const items = [];
        if (refs.changelog.length) items.push(`<li>changelog: <span class="mono label">${esc(refs.changelog.join(", "))}</span></li>`);
        if (refs.evidence.length) items.push(`<li>evidências: <span class="mono label">${esc(refs.evidence.join(", "))}</span></li>`);
        if (refs.in_questions) items.push("<li>espelhada em validation/questions.yml</li>");
        refsHtml = any
          ? `<div class="callout warn"><div><div class="t">Há referências: a exclusão vai virar deprecated</div><ul class="rv-ul b">${items.join("")}</ul></div></div>`
          : '<div class="callout info"><div><div class="t">Sem referências</div><div class="b">A CQ será removida de content.yml.</div></div></div>';
      }
      body = `${current ? `<p class="rv-q">${esc(current.question)}</p>` : ""}<p class="p"><b>Motivo:</b> ${esc(pl.reason)}</p>${refsHtml}`;
    } else {
      body = kvList(pl);
    }
    const label = pl.id ? `${pl.id} · ${TYPE_TITLE[t] || t}` : TYPE_TITLE[t] || t;
    return `${cardOpen(key, v.decision === "reject" ? "rv-dim" : "")}
      <div class="rv-main">
        <div class="rv-id"><span>${esc(label)}</span><span>· ${esc(origin(p.proposed_by))}</span></div>
        ${body}
        ${p.rationale ? `<p class="p secondary">Justificativa: ${esc(p.rationale)}</p>` : ""}
      </div>
      <div class="rv-dec">${decisionBlock(key, v)}${savedNote(p)}</div></article>`;
  }

  function readonlyCard(key, p) {
    const pl = p.payload || {};
    return `${cardOpen(key, "", true)}
      <div class="rv-main">
        <div class="rv-id"><span>${esc(p.type)}</span><span>· ${esc(origin(p.proposed_by))}</span></div>
        ${kvList(pl)}
        ${p.rationale ? `<p class="p secondary">Justificativa: ${esc(p.rationale)}</p>` : ""}
      </div></article>`;
  }

  function appliedCqCard(key, q) {
    const v = view(key);
    const mode = S.drafts[key] ? S.drafts[key].mode : "";
    const dim = q.status === "rejected" || q.status === "deprecated";
    const statusChip = `<span class="chip ${q.status === "approved" ? "high" : q.status === "reserved" ? "alt" : "outline"}">${esc(LABELS.status[q.status] || q.status || "sem status")}</span>`;
    const hasPending = pending().some((p) => GROUP_OF_TYPE[p.type] === "cq" && p.type !== "add_competency_question" && (p.payload || {}).id === q.id);
    let main, dec;
    if (mode === "alter") {
      main = `<div class="rv-id"><span>${esc(q.id)}</span>${statusChip}<span>· propor alteração</span></div>${cqEditColumns(key, v)}${evidenceHtml(q.evidence)}`;
      dec = `${cqDecisionFields(key, v)}<button type="button" class="rv-btn rv-ghost rv-small" data-act="cancel" data-key="${esc(key)}">Cancelar</button>`;
    } else {
      main = `<div class="rv-id"><span>${esc(q.id)}</span>${statusChip}<span>· ${esc(origin(q.proposed_by))}</span></div>
        <p class="rv-q">${esc(q.question)}</p>
        <div class="chips rv-meta">${q.type ? `<span class="chip alt">${esc(LABELS.type[q.type] || q.type)}</span>` : ""}${conceptChips(list(q.concepts))}${list(q.use_cases).length ? chips(list(q.use_cases), "outline mono") : ""}</div>
        ${evidenceHtml(q.evidence)}
        ${q.status === "reserved" && q.answer ? `<p class="p"><b>Resposta esperada:</b> ${esc(q.answer)}</p>` : ""}
        ${q.status === "rejected" ? `<p class="p"><b>Motivo:</b> ${esc(q.rejection_reason || "")}</p>` : ""}
        ${q.status === "deprecated" ? `<p class="p"><b>Motivo:</b> ${esc(q.deprecation_reason || "")}</p>` : ""}
        ${q.reviewed_by ? `<p class="label secondary">Revisada por ${esc(q.reviewed_by)} em ${esc(fmtDate(q.reviewed_at))}</p>` : ""}`;
      if (mode === "remove") {
        dec = `${textField(key, "reason", "Motivo da exclusão", v.reason, { placeholder: "obrigatório" })}
          <p class="label secondary">Se algo referencia a CQ, a exclusão vira deprecated.</p>
          <button type="button" class="rv-btn rv-ghost rv-small" data-act="cancel" data-key="${esc(key)}">Cancelar</button>`;
      } else {
        dec = `<span class="rv-lbl">Prioridade</span><span class="p">${esc(fmtValue("priority", q.priority))}</span>
          <span class="rv-lbl">Uso</span><span class="p">${esc(LABELS.status[q.status] || q.status || "—")}</span>
          ${hasPending ? '<p class="label secondary">Já há pendente para esta CQ.</p>' : ""}
          <div class="rv-actions">
            <button type="button" class="rv-btn rv-ghost rv-small" data-act="alter" data-key="${esc(key)}"${disPropose()}>Propor alteração</button>
            <button type="button" class="rv-btn rv-ghost rv-small" data-act="remove" data-key="${esc(key)}"${disPropose()}>Propor exclusão</button>
          </div>`;
      }
    }
    return `${cardOpen(key, dim && !mode ? "rv-dim" : "")}<div class="rv-main">${main}</div><div class="rv-dec">${dec}</div></article>`;
  }

  function newCqCard(key) {
    const v = view(key);
    const ucs = req().use_cases || [];
    const ucField = ucs.length
      ? `<fieldset class="rv-fieldset"><legend class="rv-lbl">Casos de uso</legend>${ucs.map((u) =>
        `<label class="rv-checkbox"><input type="checkbox" data-key="${esc(key)}" data-field="use_cases" value="${esc(u.id)}"${v.use_cases.includes(u.id) ? " checked" : ""}${dis()}> <span class="mono label">${esc(u.id)}</span> ${esc(u.name || "")}</label>`).join("")}</fieldset>` : "";
    return `${cardOpen(key)}
      <div class="rv-main">
        <div class="rv-id"><span>Nova CQ</span><span>· por ${esc(S.reviewer.trim() || "revisor")}</span><span>· evidência: conversa com o revisor</span></div>
        ${cqEditColumns(key, v)}
        ${ucField}
      </div>
      <div class="rv-dec">${cqDecisionFields(key, v)}
        <button type="button" class="rv-btn rv-ghost rv-small" data-act="drop-new" data-key="${esc(key)}">Remover rascunho</button></div></article>`;
  }

  function gapCard(key, g, p, isPending) {
    const v = view(key);
    const mode = isPending ? "edit" : S.drafts[key] ? S.drafts[key].mode : "";
    const editing = mode === "edit" || mode === "alter";
    const head = isPending
      ? `<span>${esc(g.id || p.id)}</span><span>· ${p.proposed_by && p.proposed_by !== "agent" ? "identificada por " + esc(p.proposed_by) : "identificada pela IA"}</span>`
      : `<span>${esc(g.id)}</span><span class="chip ${g.decision === "open" ? "warning" : "alt"}">${esc(LABELS.gap[g.decision] || g.decision || "—")}</span>${mode === "alter" ? "<span>· propor alteração</span>" : ""}`;
    let dec;
    if (editing) {
      dec = `<span class="rv-lbl">Decisão</span>${seg(key, "choice", GAP_DECISIONS, (x) => v.choice === x, { col: true, label: "Decisão da lacuna" })}
        <span class="rv-lbl">Entra no data request</span><span class="p">${v.choice === "request_from_client" ? "Sim" : "Não"}</span>
        ${textField(key, "note", "Motivo da decisão", v.note, { placeholder: v.choice === "open" ? "opcional" : "obrigatório" })}
        ${isPending ? savedNote(p) : `<button type="button" class="rv-btn rv-ghost rv-small" data-act="cancel" data-key="${esc(key)}">Cancelar</button>`}`;
    } else {
      dec = `<span class="rv-lbl">Decisão</span><span class="p">${esc(LABELS.gap[g.decision] || g.decision || "—")}</span>
        <span class="rv-lbl">Entra no data request</span><span class="p">${g.decision === "request_from_client" ? "Sim" : "Não"}</span>
        ${g.note ? `<span class="rv-lbl">Motivo</span><span class="p">${esc(g.note)}</span>` : ""}
        ${g.decided_by ? `<p class="label secondary">Decidida por ${esc(g.decided_by)} em ${esc(fmtDate(g.decided_at))}</p>` : ""}
        <div class="rv-actions"><button type="button" class="rv-btn rv-ghost rv-small" data-act="alter" data-key="${esc(key)}"${disPropose()}>Propor alteração</button></div>`;
    }
    return `${cardOpen(key, !editing && (g.decision === "drop") ? "rv-dim" : "")}
      <div class="rv-main">
        <div class="rv-id">${head}</div>
        <p class="rv-q rv-qbox rv-gap">${esc(g.question)}</p>
        <p class="p"><b>Motivo:</b> ${esc(g.reason || "—")}</p>
        <p class="p"><b>O que faltaria:</b> ${esc(g.missing || "—")}</p>
        ${evidenceHtml(g.evidence)}
        ${isPending && p.rationale ? `<p class="p secondary">Justificativa: ${esc(p.rationale)}</p>` : ""}
      </div>
      <div class="rv-dec">${dec}</div></article>`;
  }

  function divCard(key, dv, p, isPending) {
    const v = view(key);
    const mode = isPending ? "edit" : S.drafts[key] ? S.drafts[key].mode : "";
    const editing = mode === "edit" || mode === "alter";
    const sources = Array.isArray(dv.sources) ? dv.sources : [];
    const labels = sources.map((s, i) => s.label || "Fonte " + String.fromCharCode(65 + i));
    const decLabel = (d, w) => (d === "precedence" ? (w ? w + " prevalece" : "Precedência") : LABELS.div[d] || d || "—");
    const head = isPending
      ? `<span>${esc(dv.id || p.id)}</span><span>· ${p.proposed_by && p.proposed_by !== "agent" ? "identificada por " + esc(p.proposed_by) : "identificada pela IA"}</span>`
      : `<span>${esc(dv.id)}</span><span class="chip ${dv.decision === "open" ? "warning" : "alt"}">${esc(decLabel(dv.decision, dv.winner))}</span>${mode === "alter" ? "<span>· propor alteração</span>" : ""}`;
    let dec;
    if (editing) {
      const opts = labels.map((l) => ["precedence|" + l, l + " prevalece"]).concat(DIV_OTHER.map(([d, l]) => [d + "|", l]));
      const on = (val) => { const [d, w] = splitChoice(val); return v.choice === d && (d !== "precedence" || v.winner === w); };
      dec = `<span class="rv-lbl">Decisão</span>${seg(key, "divchoice", opts, on, { col: true, label: "Decisão da divergência" })}
        ${v.choice === "precedence" && v.winner && !labels.includes(v.winner) ? `<p class="label secondary">Vencedor registrado: ${esc(v.winner)}</p>` : ""}
        ${textField(key, "reason", "Motivo", v.reason, { placeholder: v.choice === "open" ? "opcional" : "obrigatório" })}
        ${isPending ? savedNote(p) : `<button type="button" class="rv-btn rv-ghost rv-small" data-act="cancel" data-key="${esc(key)}">Cancelar</button>`}`;
    } else {
      dec = `<span class="rv-lbl">Decisão</span><span class="p">${esc(decLabel(dv.decision, dv.winner))}</span>
        ${dv.reason ? `<span class="rv-lbl">Motivo</span><span class="p">${esc(dv.reason)}</span>` : ""}
        ${dv.decided_by ? `<p class="label secondary">Decidida por ${esc(dv.decided_by)} em ${esc(fmtDate(dv.decided_at))}</p>` : ""}
        <div class="rv-actions"><button type="button" class="rv-btn rv-ghost rv-small" data-act="alter" data-key="${esc(key)}"${disPropose()}>Propor alteração</button></div>`;
    }
    return `${cardOpen(key, !editing && dv.decision === "dismiss" ? "rv-dim" : "")}
      <div class="rv-main">
        <div class="rv-id">${head}</div>
        <p class="rv-q rv-qbox rv-div">${esc(dv.topic)}</p>
        ${sources.map((s, i) => `<div class="rv-ev${i % 2 ? " b" : ""}"><div><b>Fonte ${String.fromCharCode(65 + i)}</b>${s.label ? " · " + esc(s.label) : ""} · ${sourceLine(s)}</div></div>`).join("")}
        ${dv.hypothesis ? `<p class="p secondary"><b>Hipótese da IA</b> (não é fonte): ${esc(dv.hypothesis)}</p>` : ""}
        ${isPending && p.rationale ? `<p class="p secondary">Justificativa: ${esc(p.rationale)}</p>` : ""}
      </div>
      <div class="rv-dec">${dec}</div></article>`;
  }

  function useCaseCards() {
    const r = req();
    const out = [];
    if (r.purpose || r.scope) {
      out.push(`<article class="rv-card rv-wide rv-ctx"><div class="rv-id">Propósito e escopo</div>
        <p class="p"><b>Propósito:</b> ${esc(r.purpose || "—")}</p><p class="p"><b>Escopo:</b> ${esc(r.scope || "—")}</p>
        ${list(r.users).length ? `<div class="chips">${chips(list(r.users), "outline")}</div>` : ""}</article>`);
    }
    for (const u of r.use_cases || []) {
      out.push(`<article class="rv-card rv-wide rv-ctx"><div class="rv-id">${esc(u.id)}${u.source ? " · " + esc(u.source) : ""}</div>
        <p class="p"><b>Nome:</b> ${esc(u.name)}</p>
        <p class="p"><b>Descrição:</b> ${esc(u.description || "—")}</p>
        ${list(u.actors).length ? `<p class="p"><b>Atores:</b> ${esc(list(u.actors).join(", "))}</p>` : ""}
        ${u.flow ? `<p class="p"><b>Fluxo:</b> ${esc(u.flow)}</p>` : ""}</article>`);
    }
    if (!(r.use_cases || []).length) {
      out.push(`<article class="rv-card rv-wide rv-ctx"><p class="p">${r.no_use_case ? `<b>Sem caso de uso:</b> ${esc(r.no_use_case)}` : "Nenhum caso de uso registrado. Peça ao agente para registrar um ou o motivo de não haver."}</p></article>`);
    }
    return out.join("");
  }

  function sourcesRead() {
    const counts = new Map();
    const add = (path) => { if (path) counts.set(path, (counts.get(path) || 0) + 1); };
    const r = req();
    const fromItem = (it) => {
      (Array.isArray(it.evidence) ? it.evidence : []).forEach((e) => e && e.kind !== "conversation" && add(e.path));
      (Array.isArray(it.sources) ? it.sources : []).forEach((s) => s && add(s.path));
    };
    [].concat(r.competency_questions || [], r.gaps || [], r.divergences || []).forEach(fromItem);
    pending().forEach((p) => fromItem(p.payload || {}));
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }

  // ---------- render ----------
  function groups() {
    const by = { cq: [], gap: [], div: [], uc: [], other: [], ro: [] };
    pending().forEach((p) => by[groupOf(p.type)].push("p:" + p.id));
    return by;
  }

  function render() {
    buildCards();
    const g = groups();
    const r = req();
    const { st, active } = gate();
    const body = $("#rv-body");
    const parts = [];
    if (!S.api) {
      parts.push(`<div class="callout info"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg><div><div class="t">Modo leitura</div><div class="b">abra com akme review para editar</div></div></div>`);
    }
    if (!active && st.closed === false) {
      parts.push(`<div class="callout warn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l10 18H2L12 3zM12 10v4M12 17h.01"/></svg><div><div class="t">Requisitos abertos. Falta:</div><ul class="rv-ul b">${(st.missing || []).map((m) => `<li>${esc(m)}</li>`).join("")}</ul></div></div>`);
    }

    parts.push(`<section class="rv-section" id="rv-sec-uc"><h3 class="rv-grp">Contexto · caso de uso</h3>${useCaseCards()}${g.uc.map(cardHtml).join("")}</section>`);

    const appliedCq = (r.competency_questions || []).map((q) => "a:cq:" + q.id);
    parts.push(`<section class="rv-section" id="rv-sec-cqs"><h3 class="rv-grp">CQs pendentes · ${g.cq.length}</h3>
      ${!g.cq.length ? '<article class="rv-card rv-wide"><p class="p">Nada pendente. Peça ao agente para propor CQs.</p></article>' : g.cq.map(cardHtml).join("")}
      ${S.newKeys.map(cardHtml).join("")}
      <button type="button" class="rv-new" data-act="new-cq"${disPropose()}>+ Nova CQ escrita pelo revisor <span class="secondary">(id gerado, autor = revisor, evidência = conversa)</span></button>
      ${appliedCq.length ? `<h3 class="rv-grp">CQs aplicadas · ${appliedCq.length}</h3>${appliedCq.map(cardHtml).join("")}` : ""}</section>`);

    const appliedGaps = (r.gaps || []).map((x) => "a:gap:" + x.id);
    parts.push(`<section class="rv-section" id="rv-sec-gaps"><h3 class="rv-grp">Lacunas · perguntas que os dados não respondem</h3>
      ${g.gap.length ? `<h4 class="rv-sub">Pendentes · ${g.gap.length}</h4>${g.gap.map(cardHtml).join("")}` : ""}
      ${appliedGaps.length ? `<h4 class="rv-sub">Registradas · ${appliedGaps.length}</h4>${appliedGaps.map(cardHtml).join("")}` : ""}
      ${!g.gap.length && !appliedGaps.length ? '<p class="p secondary">Nenhuma lacuna registrada.</p>' : ""}</section>`);

    const appliedDivs = (r.divergences || []).map((x) => "a:div:" + x.id);
    parts.push(`<section class="rv-section" id="rv-sec-divs"><h3 class="rv-grp">Divergências · fontes que discordam</h3>
      ${g.div.length ? `<h4 class="rv-sub">Pendentes · ${g.div.length}</h4>${g.div.map(cardHtml).join("")}` : ""}
      ${appliedDivs.length ? `<h4 class="rv-sub">Registradas · ${appliedDivs.length}</h4>${appliedDivs.map(cardHtml).join("")}` : ""}
      ${!g.div.length && !appliedDivs.length ? '<p class="p secondary">Nenhuma divergência registrada.</p>' : ""}</section>`);

    if (g.other.length) {
      parts.push(`<section class="rv-section" id="rv-sec-other"><h3 class="rv-grp">Outros pendentes · ${g.other.length}</h3>${g.other.map(cardHtml).join("")}</section>`);
    }
    if (g.ro.length) {
      parts.push(`<section class="rv-section" id="rv-sec-ro"><h3 class="rv-grp">Outros (aprovar pelo chat) · ${g.ro.length}</h3>
        <p class="p secondary">Edições da etapa 2 não são decididas aqui: peça ao agente e aprove no chat.</p>${g.ro.map(cardHtml).join("")}</section>`);
    }

    const srcs = sourcesRead();
    parts.push(`<section class="rv-section" id="rv-sec-src"><h3 class="rv-grp">Contexto · fontes lidas · ${srcs.length}</h3>
      <article class="rv-card rv-wide rv-ctx">${srcs.length ? `<table><thead><tr><th>arquivo</th><th>citações</th></tr></thead><tbody>${srcs.map(([p, n]) => `<tr><td class="rv-path">${esc(p)}</td><td>${n}</td></tr>`).join("")}</tbody></table>` : '<p class="p secondary">Nenhuma fonte citada ainda.</p>'}</article></section>`);

    body.innerHTML = parts.join("");
    renderNav(g, srcs.length);
    renderFooter();
    const unreviewed = pending().filter((p) => STAGE1.has(p.type) && !p.review).length;
    $("#tab-revisao-count").textContent = unreviewed ? String(unreviewed) : "";
  }

  function renderNav(g, nSources) {
    const nav = $("#rv-nav");
    if (!nav) return;
    const item = (target, label, n) => `<li><button type="button" class="nav-item" data-act="goto" data-target="${target}">${esc(label)}<span class="count">${n}</span></button></li>`;
    nav.innerHTML = `<div class="group-label">Pendentes</div><ul>
      ${item("rv-sec-cqs", "CQs", g.cq.length)}${item("rv-sec-gaps", "Lacunas", g.gap.length)}${item("rv-sec-divs", "Divergências", g.div.length)}
      ${g.other.length ? item("rv-sec-other", "Outros", g.other.length) : ""}
      ${g.ro.length ? item("rv-sec-ro", "Outros (aprovar pelo chat)", g.ro.length) : ""}</ul>
      <div class="group-label" style="margin-top:12px">Contexto</div><ul>
      ${item("rv-sec-uc", "Caso de uso", (req().use_cases || []).length + g.uc.length)}${item("rv-sec-src", "Fontes lidas", nSources)}</ul>`;
  }

  function renderFooter() {
    const keys = Object.keys(S.cards);
    const n = { cq: 0, gap: 0, div: 0, other: 0, prop: 0 };
    let undecided = 0;
    for (const k of keys) {
      const c = S.cards[k];
      const changed = isChanged(k);
      if (c.kind === "p-readonly") continue;
      if (c.kind.startsWith("p-")) {
        if (changed) n[c.group === "cq" || c.group === "gap" || c.group === "div" ? c.group : "other"]++;
        else if (!c.item.review) undecided++;
      } else if (changed) n.prop++;
    }
    const total = n.cq + n.gap + n.div + n.other + n.prop;
    const bits = [`${n.cq} CQs decididas`, `${n.gap} lacunas`, `${n.div} divergências`];
    if (n.other) bits.push(`${n.other} outros`);
    if (n.prop) bits.push(`${n.prop} propostas`);
    bits.push(`${undecided} pendentes sem decisão`);
    $("#rv-counts").textContent = bits.join(" · ");
    $("#rv-save").disabled = !S.api || !S.reviewer.trim() || S.busy || !total;
    $("#rv-discard").disabled = S.busy || !Object.keys(S.drafts).length;
    $("#rv-save").title = !S.api ? "abra com akme review para editar" : !S.reviewer.trim() ? "preencha o revisor" : "";
  }

  function setMsg(kind, text) {
    const el = $("#rv-msg");
    el.className = "rv-msg " + kind;
    el.textContent = text;
  }

  function rerenderCard(key, focus) {
    const el = $(`#rv-body [data-card="${sel(key)}"]`);
    if (!el) return render();
    el.outerHTML = cardHtml(key);
    renderFooter();
    if (focus) {
      const card = $(`#rv-body [data-card="${sel(key)}"]`);
      const target = card && (card.querySelector(focus) || card.querySelector("textarea, input, select"));
      if (target) target.focus();
    }
  }

  // ---------- eventos ----------
  function onClick(e) {
    const b = e.target.closest("[data-act]");
    if (!b || b.disabled) return;
    const act = b.dataset.act, key = b.dataset.key;
    if (act === "goto") {
      const sec = document.getElementById(b.dataset.target);
      if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (act === "set") {
      const d = draft(key), f = b.dataset.field, val = b.dataset.value;
      if (f === "divchoice") { const [ch, w] = splitChoice(val); d.choice = ch; d.winner = ch === "precedence" ? w : ""; }
      else d[f] = val;
      S.invalid.delete(key);
      rerenderCard(key, `[data-act="set"][data-field="${sel(f)}"][data-value="${sel(val)}"]`);
      return;
    }
    if (act === "alter" || act === "remove") {
      draft(key).mode = act;
      rerenderCard(key, null);
      return;
    }
    if (act === "cancel") {
      delete S.drafts[key];
      S.invalid.delete(key);
      rerenderCard(key, `[data-act="alter"]`);
      return;
    }
    if (act === "new-cq") {
      const k = "n:" + ++S.newSeq;
      S.newKeys.push(k);
      S.cards[k] = { kind: "n-cq", item: null, group: "cq" };
      S.drafts[k] = baseline(k);
      render();
      const t = $(`#${fid(k, "question")}`);
      if (t) t.focus();
      return;
    }
    if (act === "drop-new") {
      delete S.drafts[key];
      S.newKeys = S.newKeys.filter((k) => k !== key);
      S.invalid.delete(key);
      render();
      return;
    }
    if (act === "check") return checkQuote(b);
    if (act === "save") return save();
    if (act === "discard") return discard();
  }

  function onInput(e) {
    const el = e.target;
    const key = el.dataset && el.dataset.key, f = el.dataset && el.dataset.field;
    if (!key || !f || !S.cards[key]) return;
    const d = draft(key);
    if (f === "concepts") {
      d.concepts = el.value.split(",").map((s) => s.trim()).filter(Boolean);
      const prev = $(`#rv-body [data-preview="${sel(key)}"]`);
      if (prev) prev.innerHTML = conceptChips(d.concepts);
    } else if (f === "use_cases") {
      const card = el.closest("[data-card]");
      d.use_cases = Array.from(card.querySelectorAll('input[data-field="use_cases"]:checked')).map((x) => x.value);
    } else {
      d[f] = el.value;
    }
    renderFooter();
  }

  async function checkQuote(b) {
    const out = b.nextElementSibling;
    const q = b.dataset.q || "";
    out.textContent = " conferindo…";
    try {
      const res = await S.api.get("/api/sources?q=" + encodeURIComponent(q) + "&case_sensitive=false");
      const n = (res.documents || []).length + (res.tables || []).length;
      const where = Array.from(new Set((res.documents || []).map((d) => d.path).concat((res.tables || []).map((t) => t.path)))).slice(0, 3).join(", ");
      out.textContent = res.found ? ` encontrada (${n} ${n === 1 ? "trecho" : "trechos"}${where ? ": " + where : ""})` : " não encontrada nas fontes";
    } catch (e) {
      out.textContent = " erro: " + e.message;
    }
  }

  function renderShell() {
    const view = $("#view-revisao");
    view.innerHTML = `<div class="rv">
      <div class="rv-toolbar">
        <div><span class="kind">etapa 1 · requisitos</span><h2 class="h2">Revisão</h2>
          <p class="p secondary">Decida cada CQ, lacuna e divergência. Nada é aplicado aqui: as decisões vão para ontology/pending/ e o agente aplica depois do "aplica" no chat.</p></div>
        <span class="chip ${S.api ? "success" : "outline"}">${S.api ? "editável" : "modo leitura"}</span>
        <div class="rv-reviewer"><label class="rv-lbl" for="reviewer">Revisor</label>
          <input id="reviewer" class="rv-input" type="text" autocomplete="name" placeholder="seu nome (obrigatório para salvar)"${S.api ? "" : " disabled"}></div>
      </div>
      <div id="rv-body" class="rv-body"></div>
      <div class="rv-foot">
        <button type="button" class="rv-btn" id="rv-save" data-act="save">Salvar decisões</button>
        <button type="button" class="rv-btn rv-ghost" id="rv-discard" data-act="discard">Descartar</button>
        <span id="rv-msg" class="rv-msg" role="status" aria-live="polite"></span>
        <span class="rv-hint"><span id="rv-counts"></span><br>grava em ontology/pending/ com revisor e hora · depois, no chat: "aplica"</span>
      </div></div>`;
    const input = $("#reviewer");
    input.value = S.reviewer;
    input.addEventListener("input", () => {
      const wasEmpty = !S.reviewer.trim();
      S.reviewer = input.value;
      store("akme-reviewer", S.reviewer);
      if (wasEmpty !== !S.reviewer.trim()) render();
      else renderFooter();
    });
  }

  function init(data, api) {
    S.data = data || {};
    S.data.requirements = S.data.requirements || {};
    S.api = api || null;
    S.reviewer = read("akme-reviewer") || "";
    renderShell();
    if (!S.wired) {
      const viewEl = $("#view-revisao");
      viewEl.addEventListener("click", onClick);
      viewEl.addEventListener("input", onInput);
      viewEl.addEventListener("change", onInput);
      const nav = $("#rv-nav");
      if (nav) nav.addEventListener("click", onClick);
      $("#tab-ontologia").addEventListener("click", () => setTab("ontologia"));
      $("#tab-revisao").addEventListener("click", () => setTab("revisao"));
      S.wired = true;
    }
    applyGate();
    render();
    if (S.api) {
      reload().then(() => { applyGate(); render(); }).catch((e) => setMsg("error", "falha ao carregar da API: " + e.message));
    }
  }

  window.AkmeReview = { init };
})();
