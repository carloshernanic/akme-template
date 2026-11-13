// Revisao da etapa 1 em tres telas: caso de uso, perguntas, lacunas e divergencias.
// So muda a pagina: as decisoes viram as mesmas chamadas de /api/review e /api/propose de sempre.
// O review.js monta este modulo quando o seletor esta em "Etapa 1"; o resto da aba segue na caixa de entrada.
(function () {
  "use strict";

  // add_requirement destes campos e decidido na tela 1; os demais ficam na caixa de entrada
  const REQ_FIELDS = ["purpose", "scope", "users"];
  const REQ_LABEL = { purpose: "Propósito", scope: "Escopo", users: "Usuários" };
  // tipos que ja tem tela pronta; o resto continua em "Outras propostas" para nada sumir
  const READY = new Set(["add_use_case", "add_requirement", "add_competency_question", "add_gap", "add_divergence", "add_glossary"]);
  // motivos de rejeicao de uma sigla; "outro" pede texto
  const GL_WHY = [["errada", "Significado errado"], ["nao_usada", "Não é usada"], ["repetida", "Repetida"], ["outro", "Outro motivo"]];
  const GL_WHY_L = Object.fromEntries(GL_WHY);
  // escolhas da tela 3; o terceiro valor diz que texto a escolha pede ("" = nenhum)
  const GAP_OPTS = [["request_from_client", "Pedir o dado ao cliente", ""], ["reformulate", "Reformular a pergunta", "new"],
    ["drop", "Descartar", "why"], ["open", "Deixar em aberto", "why"]];
  const DIV_OTHER = [["distinct_terms", "São coisas diferentes", "diff"], ["ask_expert", "Perguntar ao especialista", ""],
    ["dismiss", "Descartar", "why"], ["open", "Deixar em aberto", "why"]];
  const NEED_LABEL = { new: "Como fica a pergunta?", why: "Por quê?", diff: "O que diferencia?" };
  const GAP_L = Object.fromEntries(GAP_OPTS.map(([v, l]) => [v, l]));
  const DIV_L = Object.fromEntries(DIV_OTHER.map(([v, l]) => [v, l]));
  // motivos gravados quando o revisor nao escolhe algo da IA
  const R_UC = "não escolhido pelo revisor", R_OUT = "fora dos casos escolhidos", R_NOUC = "o revisor escolheu caso de uso";
  const CQ_TYPES = [
    ["classificacao_hierarquia", "Classificação e hierarquia"], ["relacao_entre_conceitos", "Relação entre conceitos"],
    ["atributos", "Atributos"], ["quantidade_agregacao", "Quantidade e agregação"], ["tempo_estado", "Tempo e estado"],
    ["regras_restricoes", "Regras e restrições"],
  ];
  const TYPE_L = Object.fromEntries(CQ_TYPES);
  const PRIO = [["high", "Alta"], ["medium", "Média"], ["low", "Baixa"]];
  const PRIO_L = Object.fromEntries(PRIO);
  // motivos de rejeicao: o rotulo vira o reason enviado; "outro" pede texto livre
  const WHY = [["clara", "Pouco clara"], ["escopo", "Fora do caso de uso"], ["dados", "Os dados não respondem"], ["repetida", "Repetida"], ["outro", "Outro motivo"]];
  const WHY_L = Object.fromEntries(WHY);
  const STEPS = [
    { id: "uc", title: "Caso de uso", lead: "Marque os que valem para o projeto." },
    { id: "cq", title: "Perguntas", lead: "Aceite, rejeite ou escreva a sua." },
    { id: "gd", title: "Lacunas e divergências", lead: "Decida o que fazer com cada uma." },
    { id: "gl", title: "Glossário", lead: "Confira cada sigla." },
  ];

  const E = { el: null, ctx: null, M: null, wired: null };

  // ---------- utilidades ----------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (sel, el = document) => el.querySelector(sel);
  const list = (v) => (Array.isArray(v) ? v.map(String) : v ? [String(v)] : []);
  // etiqueta de obrigatorio: fica no html e some quando o campo e preenchido
  const req = (filled, txt) => `<span class="req"${filled ? " hidden" : ""}>${esc(txt || "obrigatório")}</span>`;

  function covers(p) {
    if (!READY.has(p.type)) return false;
    if (p.type === "add_requirement") return REQ_FIELDS.includes((p.payload || {}).field) || (p.payload || {}).field === "no_use_case";
    return true;
  }
  function pendingCount(data) {
    return ((data && data.pending) || []).filter(covers).length;
  }
  // fonte citada pela IA: a evidencia gravada junto da proposta, ou a justificativa
  function sourceOf(p) {
    const ev = (p.view && p.view.evidence) || [];
    const first = ev.find((e) => e.path || e.note);
    if (first) return first.path ? first.path + (first.locator ? " · " + first.locator : "") : first.note;
    return p.evidence || "";
  }

  // ---------- modelo ----------
  // prev guarda o que o revisor ja decidiu nesta sessao; um reload do servidor nao apaga as escolhas
  // decisoes feitas e ainda nao salvas ficam num rascunho deste navegador: recarregar a pagina nao as apaga
  const DRAFT_SKIP = new Set(["payload", "src", "rationale", "saved", "mine", "kind", "proposed", "field", "open", "det", "more", "editing"]);
  const draftKey = (project) => "akme-draft-etapa1:" + (project || "");
  function readDraft(project) {
    try { return JSON.parse(localStorage.getItem(draftKey(project)) || "null") || {}; } catch (e) { return {}; }
  }
  function clearDraft(project) { try { localStorage.removeItem(draftKey(project)); } catch (e) { /* sem armazenamento */ } }
  function writeDraft(M) {
    if (!M || isAuto()) return;
    const items = {};
    Object.values(M.byId).forEach((it) => {
      if (it.saved) return;
      const o = {};
      Object.keys(it).forEach((k) => { if (!DRAFT_SKIP.has(k)) o[k] = it[k]; });
      items[it.edit_id] = o;
    });
    const touched = Object.values(M.byId).some((it) => !it.saved && decided(it)) || M.owns.length || M.ownCqs.length || M.noUc;
    try {
      if (touched) localStorage.setItem(draftKey(M.project), JSON.stringify({ items, owns: M.owns, ownCqs: M.ownCqs, seq: M.seq, noUc: M.noUc }));
      else clearDraft(M.project);
    } catch (e) { /* sem armazenamento: o rascunho fica so na memoria */ }
  }
  function buildModel(data, prev) {
    const old = (prev && prev.byId) || {};
    const project = (data && data.project) || "";
    // primeira montagem (pagina recem-aberta): recupera o rascunho; depois, o modelo anterior manda
    const D0 = prev ? {} : readDraft(project), dItems = D0.items || {};
    const dr = (id, rv) => (!rv && dItems[id] ? Object.assign({}, dItems[id], { edit_id: id }) : null);
    // owns: casos escritos pelo revisor; o rascunho vive na janela (dialogo), fora do modelo
    const arr = (v) => (Array.isArray(v) ? v : []);
    const M = { step: prev ? prev.step : 0, ucs: [], reqs: [], owns: prev ? prev.owns : arr(D0.owns),
      seq: prev ? prev.seq : D0.seq || 0, noUc: prev ? prev.noUc : D0.noUc || null, noUcSeen: prev ? prev.noUcSeen : {}, noUcIds: [], gds: [], gls: [], tmpMap: prev ? prev.tmpMap : {}, cqs: [], ownCqs: prev ? prev.ownCqs : arr(D0.ownCqs),
      applied: { ucs: [] }, byId: {}, reqEditing: prev ? prev.reqEditing : false, project };
    const r = (data && data.requirements) || {};
    M.applied.ucs = r.use_cases || [];
    M.applied.cqs = r.competency_questions || [];
    M.applied.gaps = r.gaps || [];
    M.applied.divs = r.divergences || [];
    M.appliedReq = { purpose: r.purpose || "", scope: r.scope || "", users: list(r.users).join(", "), no_use_case: r.no_use_case || "" };
    for (const p of (data && data.pending) || []) {
      if (!covers(p)) continue;
      const pl = p.payload || {}, rv = p.review, was = old[p.id];
      if (p.type === "add_use_case") {
        const it = was || dr(p.id, rv) || { edit_id: p.id, sel: rv ? rv.decision === "accept" : false };
        Object.assign(it, { kind: "uc", payload: pl, src: sourceOf(p), saved: !!rv, mine: !!p.proposed_by && p.proposed_by !== "agent" });
        M.ucs.push(it); M.byId[p.id] = it;
      } else if (p.type === "add_competency_question") {
        const e = (rv && rv.edits) || {};
        const it = was || dr(p.id, rv) || { edit_id: p.id, dec: rv ? (rv.decision === "accept" ? "ok" : "rej") : null,
          prio: rv && rv.decision === "accept" ? e.priority || pl.priority || "" : "", reason: rv && rv.decision === "reject" ? rv.reason || "" : "",
          why: "", open: false, det: false, editing: false,
          q: String(e.question ?? pl.question ?? ""), type: e.type ?? pl.type ?? "", concepts: list(e.concepts ?? pl.concepts) };
        if (!was && it.reason) { const k = WHY.find(([, l]) => l === it.reason); it.why = k ? k[0] : "outro"; }
        Object.assign(it, { kind: "cq", payload: pl, rationale: p.rationale || "", saved: !!rv });
        M.cqs.push(it); M.byId[p.id] = it;
      } else if (p.type === "add_gap" || p.type === "add_divergence") {
        const e = (rv && rv.edits) || {};
        // a nota da reformulacao e gravada com o prefixo "Nova pergunta: "; na tela, so o texto
        const t0 = String(e.note || (e.decision !== "precedence" && e.reason) || "");
        const it = was || dr(p.id, rv) || { edit_id: p.id, choice: e.decision || "", winner: e.winner || "", text: e.decision === "reformulate" ? t0.replace(/^Nova pergunta: /, "") : t0,
          open: false, det: false, more: false };
        Object.assign(it, { kind: p.type === "add_gap" ? "gap" : "div", payload: pl, rationale: p.rationale || "", saved: !!rv });
        M.gds.push(it); M.byId[p.id] = it;
      } else if (p.type === "add_glossary") {
        const e = (rv && rv.edits) || {};
        const it = was || dr(p.id, rv) || { edit_id: p.id, dec: rv ? (rv.decision === "accept" ? "ok" : "rej") : null, why: "", reason: rv && rv.decision === "reject" ? rv.reason || "" : "",
          editing: false, meaning: String(e.meaning ?? pl.meaning ?? ""), convention: String(e.convention ?? pl.convention ?? "") };
        if (!was && it.reason) { const k = GL_WHY.find(([, l]) => l === it.reason); it.why = k ? k[0] : "outro"; }
        Object.assign(it, { kind: "gl", payload: pl, src: sourceOf(p), saved: !!rv });
        M.gls.push(it); M.byId[p.id] = it;
      } else if (pl.field === "no_use_case") {
        M.noUcIds.push(p.id);
        // registro de "sem caso de uso" ja proposto: aparece como a opcao marcada
        // so na primeira vez: se o revisor desfez, um reload nao traz de volta
        if (!M.noUcSeen[p.id]) { M.noUcSeen[p.id] = true; if (!M.noUc) M.noUc = { text: String(pl.value || ""), edit_id: p.id, ok: true }; }
      } else {
        const it = was || dr(p.id, rv) || { edit_id: p.id, ok: rv ? rv.decision === "accept" : false, editing: false, value: String((rv && rv.edits && rv.edits.value) ?? pl.value ?? "") };
        Object.assign(it, { kind: "req", field: pl.field, proposed: String(pl.value ?? ""), src: sourceOf(p), saved: !!rv });
        M.reqs.push(it); M.byId[p.id] = it;
      }
    }
    M.gds.sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "gap" ? -1 : 1));
    M.reqs.sort((a, b) => REQ_FIELDS.indexOf(a.field) - REQ_FIELDS.indexOf(b.field));
    return M;
  }

  const noUcOk = (M) => !!(M.noUc && M.noUc.ok);
  // casos que valem: marcados agora, ja aprovados antes e os escritos pelo revisor
  function chosenUcs(M) {
    const out = M.applied.ucs.map((u) => ({ id: u.id, name: u.name }));
    M.ucs.filter((u) => u.sel).forEach((u) => out.push({ id: u.payload.id, name: u.payload.name }));
    M.owns.forEach((o) => out.push({ id: o.tmp, name: o.name }));
    return out;
  }

  // o que falta para a tela estar completa; tela sem itens conta como completa
  function missing(M, step) {
    const m = [];
    if (step === 0) {
      if (M.noUc && !noUcOk(M)) m.push("confirmar por que não há caso de uso");
      else if (!chosenUcs(M).length && !noUcOk(M)) m.push("escolher um caso de uso");
      if (M.reqs.length && !reqsOk(M)) m.push("aceitar Sobre o projeto");
      M.reqs.filter((x) => x.ok && !x.value.trim()).forEach((x) => m.push(REQ_LABEL[x.field].toLowerCase() + " está vazio"));
    } else if (step === 1) {
      const { groups } = cqGroups(M), ai = groups.flatMap((g) => g.ai);
      const n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
      const und = ai.filter((c) => !c.dec).length, np = ai.filter((c) => c.dec === "ok" && !c.prio).length;
      const nr = ai.filter((c) => c.dec === "rej" && !reasonOf(c)).length;
      if (und) m.push("decidir " + n(und, "pergunta", "perguntas"));
      if (np) m.push("prioridade de " + n(np, "pergunta", "perguntas"));
      if (nr) m.push("motivo de " + n(nr, "rejeição", "rejeições"));
      const lost = M.ownCqs.filter((o) => !noUcOk(M) && !chosenUcs(M).some((u) => u.id === o.uc)).length;
      if (lost) m.push("caso de uso de " + n(lost, "pergunta sua", "perguntas suas"));
      const anyOk = ai.some((c) => c.dec === "ok") || M.ownCqs.length || M.applied.cqs.some((q) => q.status === "approved");
      if (!anyOk) m.push("aceitar ou escrever pelo menos uma pergunta");
    } else if (step === 2) {
      const und = M.gds.filter((c) => !c.choice || (c.choice === "precedence" && !c.winner)).length;
      const nt = M.gds.filter((c) => c.choice && needOf(c) && !c.text.trim()).length;
      if (und) m.push(`decidir ${und} ${und === 1 ? "item" : "itens"}`);
      if (nt) m.push(`escrever o que falta em ${nt} ${nt === 1 ? "item" : "itens"}`);
    } else if (step === 3) {
      const und = M.gls.filter((g) => !g.dec).length, nr = M.gls.filter((g) => g.dec === "rej" && !glReason(g)).length;
      const ne = M.gls.filter((g) => g.dec === "ok" && !g.meaning.trim()).length;
      if (und) m.push(`decidir ${und} ${und === 1 ? "sigla" : "siglas"}`);
      if (nr) m.push(`motivo de ${nr} ${nr === 1 ? "sigla rejeitada" : "siglas rejeitadas"}`);
      if (ne) m.push(`significado de ${ne} ${ne === 1 ? "sigla" : "siglas"}`);
    }
    return m;
  }

  // ---------- tela 2: perguntas ----------
  const reasonOf = (c) => (c.why && c.why !== "outro" ? WHY_L[c.why] : c.reason.trim());
  const cqDone = (c) => (c.dec === "ok" && !!c.prio) || (c.dec === "rej" && !!reasonOf(c));
  // agrupa pelas escolhas da tela 1; sem caso de uso escolhido ("nao temos"), tudo fica num grupo so
  function cqGroups(M) {
    const all = noUcOk(M), chosen = all ? [] : chosenUcs(M);
    const groups = chosen.map((u) => ({ id: u.id, name: u.name, ai: [], own: [] }));
    const byUc = Object.fromEntries(groups.map((g) => [g.id, g]));
    const none = { id: "", name: all ? "Perguntas" : "Sem caso de uso", ai: [], own: [] };
    const out = [];
    for (const c of M.cqs) {
      const ucs = list(c.payload.use_cases);
      if (all || !ucs.length) { none.ai.push(c); continue; }
      const g = ucs.map((x) => byUc[x]).find(Boolean);
      if (g) g.ai.push(c); else out.push(c);
    }
    M.ownCqs.forEach((o, i) => (byUc[o.uc] || none).own.push({ o, i }));
    return { groups: groups.concat(none).filter((g) => g.ai.length || g.own.length), out };
  }
  function firstSource(evs) {
    const ev = (Array.isArray(evs) ? evs : []).find((x) => x && x.path);
    return ev ? ev.path + (ev.locator ? " · " + ev.locator : "") : "";
  }
  function cqLine(c) {
    const ok = c.dec === "ok";
    return `<div class="e1-line ${ok ? "ok" : "rej"}" data-cq="${esc(c.edit_id)}"><span class="i" aria-hidden="true">${ok ? "✓" : "✕"}</span>
      <span class="q">${esc(c.q)}</span><span class="m">${esc(ok ? PRIO_L[c.prio] : reasonOf(c))}</span>
      <button type="button" class="lnk" data-e1="cq-open" data-id="${esc(c.edit_id)}" aria-label="Rever: ${esc(c.q)}">rever</button></div>`;
  }
  function cqDetails(c) {
    const pl = c.payload, id = esc(c.edit_id);
    const evs = (pl.evidence || []).map((ev) => ev.path
      ? `<div class="ev"><span class="path">${esc(ev.path)}${ev.locator ? " · " + esc(ev.locator) : ""}</span>${ev.quote ? `<span class="quote">“${esc(ev.quote)}”</span>` : ""}</div>`
      : ev.note ? `<div class="ev">${esc(ev.note)}</div>` : "").join("");
    const edit = c.editing
      ? `<div class="e1-cq-edit">
          <div class="field"><label class="field-label" for="e1-cq-q-${id}">Pergunta</label><textarea id="e1-cq-q-${id}" class="textarea" rows="2" data-e1f="cq-q" data-id="${id}">${esc(c.q)}</textarea></div>
          <div class="field"><label class="field-label" for="e1-cq-t-${id}">Tipo</label><select id="e1-cq-t-${id}" class="select" data-e1f="cq-type" data-id="${id}">${CQ_TYPES.map(([v, l]) => `<option value="${v}"${v === c.type ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></div>
          <div class="field"><label class="field-label" for="e1-cq-c-${id}">Conceitos</label><input id="e1-cq-c-${id}" class="input" type="text" data-e1f="cq-concepts" data-id="${id}" value="${esc(c.concepts.join(", "))}"></div></div>`
      : `<div class="badges">${c.type ? `<span class="badge badge-alt">${esc(TYPE_L[c.type] || c.type)}</span>` : ""}${c.concepts.map((x) => `<span class="badge badge-outline">${esc(x)}</span>`).join("")}</div>`;
    return `<div class="cq-det" id="e1-det-${id}">
      <p class="eyebrow">${esc([pl.id, "proposta pela IA"].filter(Boolean).join(" · "))}</p>
      ${edit}${evs}
      ${c.rationale ? `<p class="p secondary"><b>Justificativa da IA:</b> ${esc(c.rationale)}</p>` : ""}
      <div><button type="button" class="lnk" data-e1="cq-edit" data-id="${id}">${c.editing ? "pronto" : "editar texto"}</button></div></div>`;
  }
  function cqCard(c) {
    if (cqDone(c) && !c.open) return cqLine(c);
    const id = esc(c.edit_id), src = firstSource(c.payload.evidence);
    const edited = c.q !== String(c.payload.question || "") || c.type !== (c.payload.type || "") || c.concepts.join("|") !== list(c.payload.concepts).join("|");
    const big = (v, label, cls) => `<button type="button" class="${cls}" data-e1="cq-dec" data-id="${id}" data-v="${v}" aria-pressed="${c.dec === v}">${label}</button>`;
    let after = "";
    if (c.dec === "ok") {
      const sug = c.payload.priority && PRIO_L[c.payload.priority];
      after = `<div class="choice"><span class="field-label">Prioridade ${req(c.prio)}</span>
        <div class="seg" role="group" aria-label="Prioridade">${PRIO.map(([v, l]) => `<button type="button" data-e1="cq-prio" data-id="${id}" data-v="${v}" aria-pressed="${c.prio === v}">${l}</button>`).join("")}</div>
        ${sug ? `<span class="choice-help">A IA sugere ${esc(sug)}.</span>` : ""}</div>`;
    } else if (c.dec === "rej") {
      after = `<div class="choice"><span class="field-label">Por que rejeitar? ${req(c.why)}</span>
        <div class="why" role="group" aria-label="Motivo da rejeição">${WHY.map(([k, l]) => `<button type="button" data-e1="cq-why" data-id="${id}" data-v="${k}" aria-pressed="${c.why === k}">${esc(l)}</button>`).join("")}</div></div>
        ${c.why === "outro" ? `<div class="field"><label class="field-label" for="e1-cq-r-${id}">Qual o motivo? ${req(c.reason.trim())}</label><textarea id="e1-cq-r-${id}" class="textarea" rows="2" data-e1f="cq-reason" data-id="${id}">${esc(c.reason)}</textarea></div>` : ""}`;
    }
    const close = cqDone(c) ? `<div><button type="button" class="btn btn-outline btn-sm" data-e1="cq-close" data-id="${id}">recolher</button></div>` : "";
    return `<article class="rv-card cq-lean${c.dec === "ok" ? " st-ok" : c.dec === "rej" ? " st-rej" : ""}" data-cq="${id}">
      <div class="cq-body">
        <h3 class="cq-q">${esc(c.q)}</h3>
        <div class="cq-sig">${src ? `<span class="mono">${esc(src)}</span>` : '<span class="warn">sem evidência de fonte</span>'}
          <button type="button" class="lnk" data-e1="cq-det" data-id="${id}" aria-expanded="${c.det}" aria-controls="e1-det-${id}">${c.det ? "esconder detalhes" : "ver detalhes"}</button>
          ${edited ? '<span class="mark">editada por você</span>' : ""}</div>
        ${c.det ? cqDetails(c) : ""}
      </div>
      <div class="cq-decide"><div class="big">${big("ok", "✓ Aceitar", "bok")}${big("rej", "✕ Rejeitar", "brej")}</div>${after}${close}</div></article>`;
  }
  function ownCqLine(o, i) {
    return `<div class="e1-line ok own"><span class="i" aria-hidden="true">✓</span><span class="q">${esc(o.q)} <span class="e1-seu">sua</span></span>
      <span class="m">${esc(PRIO_L[o.prio])}</span>
      <button type="button" class="lnk" data-e1="ocq-edit" data-i="${i}">editar</button><button type="button" class="lnk" data-e1="ocq-del" data-i="${i}">remover</button></div>`;
  }
  function screenCq(M) {
    const { groups, out } = cqGroups(M);
    const todo = groups.flatMap((g) => g.ai).filter((c) => !cqDone(c)).length;
    const bar = `<div class="e1-cqbar"><span class="e1-count">${todo ? `<b>${todo}</b> ${todo === 1 ? "sugestão da IA para avaliar" : "sugestões da IA para avaliar"}` : "Nada pendente da IA"}</span>
      <span class="e1-cqbar-a">${todo ? `<button type="button" class="btn btn-outline" data-e1="cq-all" title="Aceita as ${todo} sugestões ainda sem decisão, com a prioridade sugerida pela IA (ou Média). Dá para rever cada uma depois.">✓ Aceitar tudo (${todo})</button>` : ""}
      <button type="button" class="btn btn-outline" data-e1="cq-new">+ Criar pergunta</button></span></div>`;
    const body = groups.map((g) => `<h3 class="e1-sub">${esc(g.name)}</h3><div class="e1-cqs">${g.ai.map(cqCard).join("")}${g.own.map(({ o, i }) => ownCqLine(o, i)).join("")}</div>`).join("");
    const fora = out.length ? `<details class="e1-more"><summary>Fora dos casos escolhidos (${out.length})</summary>${out.map((c) => `<div class="e1-line mute"><span class="q">${esc(c.q)}</span></div>`).join("")}<p class="p secondary">Não pedem decisão: ficam de fora junto com o caso de uso.</p></details>` : "";
    const ap = M.applied.cqs;
    const aplicadas = ap.length ? `<details class="e1-more"><summary>Já aplicadas (${ap.length})</summary>${ap.map((q) => `<div class="e1-line mute"><span class="q">${esc(q.question)}${q.status === "reserved" ? ' <span class="e1-seu">teste</span>' : ""}</span><span class="m">${esc(PRIO_L[q.priority] || q.status || "")}${q.reviewed_by ? " · " + esc(q.reviewed_by) : ""}</span></div>`).join("")}
      <p class="p secondary">Para alterar ou excluir, use <button type="button" class="lnk" data-e1="outras">Outras propostas</button>.</p></details>` : "";
    const nada = !groups.length ? `<div class="e1-empty"><b>Nada a decidir</b><span>Escreva uma pergunta se quiser.</span></div>` : "";
    return `${bar}${nada}${body}${fora}${aplicadas}`;
  }
  // depois de decidir um card, o foco vai para o proximo que ainda espera decisao
  function focusAfter(id) {
    const next = cqGroups(E.M).groups.flatMap((g) => g.ai).find((c) => !cqDone(c) && c.edit_id !== id);
    const sel = cqDone(E.M.byId[id]) && !E.M.byId[id].open
      ? next ? `[data-e1="cq-dec"][data-id="${next.edit_id}"][data-v="ok"]` : `[data-e1="cq-open"][data-id="${id}"]`
      : null;
    return sel;
  }

  // ---------- quais telas aparecem ----------
  // so as telas com algo a decidir; a primeira rodada (so casos de uso) fica so com a tela 1
  function visibleSteps(M) {
    const v = [];
    if (M.ucs.length || M.reqs.length || M.noUcIds.length || M.owns.length || M.noUc || (!M.applied.ucs.length && !M.appliedReq.no_use_case)) v.push(0);
    if (M.cqs.length || M.ownCqs.length) v.push(1);
    if (M.gds.length) v.push(2);
    if (M.gls.length) v.push(3);
    return v.length ? v : [0];
  }
  // quanto falta decidir: alimenta o numero do seletor "Etapa 1"
  function remainingOf(M) {
    const vis = visibleSteps(M);
    let n = 0;
    if (vis.includes(0)) {
      if (M.ucs.length && !M.ucs.some((u) => u.sel) && !M.owns.length && !noUcOk(M)) n += 1;
      if (M.reqs.some((r) => !r.ok)) n += 1; // "Sobre o projeto" e um card so
    }
    // antes de escolher o caso de uso, todas as perguntas contam; depois, so as dos casos escolhidos
    const choice = chosenUcs(M).length || noUcOk(M);
    if (vis.includes(1)) n += (choice ? cqGroups(M).groups.flatMap((g) => g.ai) : M.cqs).filter((c) => !cqDone(c)).length;
    if (vis.includes(2)) n += M.gds.filter((c) => !gdDone(c)).length;
    if (vis.includes(3)) n += M.gls.filter((g) => !glDone(g)).length;
    return n;
  }
  // decidida aqui mas ainda nao gravada no servidor
  function decided(it) {
    if (it.kind === "uc") return !!it.sel;
    if (it.kind === "req") return !!it.ok;
    if (it.kind === "cq") return cqDone(it);
    if (it.kind === "gap" || it.kind === "div") return gdDone(it);
    if (it.kind === "gl") return glDone(it);
    return false;
  }
  const unsavedOf = (M) => Object.values(M.byId).filter((it) => !it.saved && decided(it)).length + M.owns.length + M.ownCqs.length;
  // o numero da aba so cai depois de salvar: decidir sem salvar nao muda nada na ontologia
  function remaining(data) {
    return E.M ? remainingOf(E.M) + unsavedOf(E.M) : pendingCount(data);
  }
  // modo automatico (a main marca o body): a IA decide e aplica; aqui so se acompanha
  const isAuto = () => document.body.dataset.decisionMode === "auto";
  const VIEW_ACTS = new Set(["go", "back", "next", "outras", "cq-det", "gd-det", "gd-more", "gd-ask"]);

  // ---------- tela 3: lacunas e divergencias ----------
  function needOf(c) {
    if (!c.choice || c.choice === "precedence") return "";
    const o = (c.kind === "gap" ? GAP_OPTS : DIV_OTHER).find(([v]) => v === c.choice);
    return o ? o[2] : "";
  }
  const gdDone = (c) => !!c.choice && (c.choice !== "precedence" || !!c.winner) && (!needOf(c) || !!c.text.trim());
  const gdLabel = (c) => (c.kind === "gap" ? GAP_L[c.choice] : c.choice === "precedence" ? `Vale ${c.winner}` : DIV_L[c.choice]) || "";
  const divTitle = (pl) => `Qual definição de “${pl.topic || "?"}” vale?`;
  function gdLine(c) {
    const t = c.kind === "gap" ? c.payload.question : divTitle(c.payload);
    return `<div class="e1-line ok" data-gd="${esc(c.edit_id)}"><span class="i" aria-hidden="true">✓</span><span class="q">${esc(t)}</span>
      <span class="m">${esc(gdLabel(c))}${c.text.trim() ? ": " + esc(c.text.trim()) : ""}</span>
      <button type="button" class="lnk" data-e1="gd-open" data-id="${esc(c.edit_id)}" aria-label="Rever: ${esc(t)}">rever</button></div>`;
  }
  function evList(evs) {
    return (Array.isArray(evs) ? evs : []).map((ev) => ev.path
      ? `<div class="ev"><span class="path">${esc(ev.path)}${ev.locator ? " · " + esc(ev.locator) : ""}</span>${ev.quote ? `<span class="quote">“${esc(ev.quote)}”</span>` : ""}</div>`
      : ev.note ? `<div class="ev">${esc(ev.note)}</div>` : "").join("");
  }
  function needField(c) {
    const need = needOf(c), id = esc(c.edit_id);
    if (!need) return "";
    return `<div class="field"><label class="field-label" for="e1-gd-${id}">${NEED_LABEL[need]} ${req(c.text.trim())}</label>
      <textarea id="e1-gd-${id}" class="textarea" rows="2" data-e1f="gd-text" data-id="${id}">${esc(c.text)}</textarea></div>`;
  }
  // em aberto, a etapa 1 nao fecha (requirements.py conta como pendencia)
  const openNote = (c) => (c.choice === "open" ? '<span class="choice-help">Em aberto, a etapa 1 não fecha: as próximas etapas esperam esta decisão.</span>' : "");
  function gdClose(c) {
    return gdDone(c) && needOf(c) ? `<div><button type="button" class="btn btn-outline btn-sm" data-e1="gd-close" data-id="${esc(c.edit_id)}">concluir</button></div>` : "";
  }
  // abre a Conversa com o item citado ([L-03]), para a resposta do agente ficar ligada a ele
  function askBtn(c) {
    const ch = window.AkmeChannel;
    return ch && ch.available() && !isAuto() ? `<button type="button" class="lnk" data-e1="gd-ask" data-id="${esc(c.edit_id)}">Comentar com a IA</button>` : "";
  }
  function gapCard(c) {
    if (gdDone(c) && !c.open) return gdLine(c);
    const pl = c.payload, id = esc(c.edit_id);
    const sug = pl.decision && pl.decision !== "open" && GAP_L[pl.decision];
    const det = c.det ? `<div class="cq-det" id="e1-det-${id}"><p class="eyebrow">${esc([pl.id, "proposta pela IA"].filter(Boolean).join(" · "))}</p>
      ${pl.missing ? `<p class="p"><b>Faltaria:</b> ${esc(pl.missing)}</p>` : ""}${evList(pl.evidence)}
      ${c.rationale ? `<p class="p secondary"><b>Justificativa da IA:</b> ${esc(c.rationale)}</p>` : ""}</div>` : "";
    return `<article class="rv-card cq-lean${gdDone(c) ? " st-ok" : ""}" data-gd="${id}">
      <div class="cq-body"><h3 class="cq-q">${esc(pl.question)}</h3>
        <div class="cq-sig"><span class="e1-why">● ${esc(pl.reason || "os dados não respondem")}</span>
          <button type="button" class="lnk" data-e1="gd-det" data-id="${id}" aria-expanded="${c.det}" aria-controls="e1-det-${id}">${c.det ? "esconder detalhes" : "ver detalhes"}</button>${askBtn(c)}</div>${det}</div>
      <div class="cq-decide"><div class="e1-opts" role="group" aria-label="O que fazer com esta lacuna">${GAP_OPTS.map(([v, l]) => `<button type="button" data-e1="gd-set" data-id="${id}" data-v="${v}" aria-pressed="${c.choice === v}">${esc(l)}</button>`).join("")}</div>
        ${sug ? `<span class="choice-help">A IA sugere ${esc(sug)}.</span>` : ""}${openNote(c)}${needField(c)}${gdClose(c)}</div></article>`;
  }
  function divCard(c) {
    if (gdDone(c) && !c.open) return gdLine(c);
    const pl = c.payload, id = esc(c.edit_id), srcs = Array.isArray(pl.sources) ? pl.sources : [];
    const lab = (x, i) => x.label || "Fonte " + String.fromCharCode(65 + i);
    const sug = pl.decision === "precedence" && pl.winner;
    const other = c.choice && c.choice !== "precedence";
    const more = c.more || other;
    const det = c.det ? `<div class="cq-det" id="e1-det-${id}"><p class="eyebrow">${esc([pl.id, "proposta pela IA"].filter(Boolean).join(" · "))}</p>
      ${pl.reason ? `<p class="p"><b>Por que a IA sugere:</b> ${esc(pl.reason)}</p>` : ""}
      ${pl.hypothesis ? `<p class="p"><b>Hipótese da IA:</b> ${esc(pl.hypothesis)}</p>` : ""}
      ${c.rationale ? `<p class="p secondary"><b>Justificativa da IA:</b> ${esc(c.rationale)}</p>` : ""}</div>` : "";
    return `<article class="rv-card cq-lean${gdDone(c) ? " st-ok" : ""}" data-gd="${id}">
      <div class="cq-body"><h3 class="cq-q">${esc(divTitle(pl))}</h3>
        <div class="cq-sig">${sug ? `<span>A IA sugere <b>${esc(pl.winner)}</b></span>` : ""}
          <button type="button" class="lnk" data-e1="gd-det" data-id="${id}" aria-expanded="${c.det}" aria-controls="e1-det-${id}">${c.det ? "esconder detalhes" : "ver detalhes"}</button>${askBtn(c)}</div>${det}</div>
      <div class="cq-decide"><div class="e1-srcs">${srcs.map((x, i) => `<button type="button" class="e1-src" data-e1="dv-win" data-id="${id}" data-i="${i}" aria-pressed="${c.choice === "precedence" && c.winner === lab(x, i)}">
          <span class="l">${esc(lab(x, i))}</span>${x.quote ? `<span class="qt">“${esc(x.quote)}”</span>` : ""}${x.path ? `<span class="pa">${esc(x.path)}${x.locator ? " · " + esc(x.locator) : ""}</span>` : ""}</button>`).join("")}</div>
        ${other ? "" : `<div><button type="button" class="lnk" data-e1="gd-more" data-id="${id}" aria-expanded="${more}">${more ? "esconder outras opções" : "nenhuma das duas? outras opções"}</button></div>`}
        ${more ? `<div class="why e1-other" role="group" aria-label="Outras opções">${DIV_OTHER.map(([v, l]) => `<button type="button" data-e1="gd-set" data-id="${id}" data-v="${v}" aria-pressed="${c.choice === v}">${esc(l)}</button>`).join("")}</div>` : ""}
        ${openNote(c)}${needField(c)}${gdClose(c)}</div></article>`;
  }
  function screenGd(M) {
    const gaps = M.gds.filter((c) => c.kind === "gap"), divs = M.gds.filter((c) => c.kind === "div");
    const ap = M.applied.gaps.map((g) => [g.question, GAP_L[g.decision] || g.decision])
      .concat(M.applied.divs.map((d) => [divTitle(d), d.decision === "precedence" ? `Vale ${d.winner}` : DIV_L[d.decision] || d.decision]));
    const aplicadas = ap.length ? `<details class="e1-more"><summary>Já aplicadas (${ap.length})</summary>${ap.map(([q, d]) => `<div class="e1-line mute"><span class="q">${esc(q)}</span><span class="m">${esc(d || "")}</span></div>`).join("")}
      <p class="p secondary">Para alterar, use <button type="button" class="lnk" data-e1="outras">Outras propostas</button>.</p></details>` : "";
    if (!M.gds.length) return `<div class="e1-empty"><b>Nada a decidir</b><span>Nenhuma lacuna ou divergência pendente.</span></div>${aplicadas}`;
    return `${gaps.length ? `<h3 class="e1-sub">Lacunas</h3><div class="e1-cqs">${gaps.map(gapCard).join("")}</div>` : ""}
      ${divs.length ? `<h3 class="e1-sub">Divergências</h3><div class="e1-cqs">${divs.map(divCard).join("")}</div>` : ""}${aplicadas}`;
  }
  function focusAfterGd(id) {
    const c = E.M.byId[id];
    if (!gdDone(c) || c.open) return null;
    const next = E.M.gds.find((x) => !gdDone(x) && x.edit_id !== id);
    if (!next) return `[data-e1="gd-open"][data-id="${id}"]`;
    return next.kind === "gap" ? `[data-e1="gd-set"][data-id="${next.edit_id}"]` : `[data-e1="dv-win"][data-id="${next.edit_id}"]`;
  }

  // ---------- tela 4: glossario ----------
  const glReason = (g) => (g.why && g.why !== "outro" ? GL_WHY_L[g.why] : g.reason.trim());
  const glDone = (g) => (g.dec === "ok" && !!g.meaning.trim()) || (g.dec === "rej" && !!glReason(g));
  function glRow(g) {
    const id = esc(g.edit_id), pl = g.payload;
    const changed = g.meaning !== String(pl.meaning || "") || g.convention !== String(pl.convention || "");
    const body = g.editing
      ? `<div class="e1-gl-edit"><div class="field"><label class="field-label" for="e1-gl-m-${id}">Significado ${req(g.meaning.trim())}</label>
          <input id="e1-gl-m-${id}" class="input" type="text" data-e1f="gl-meaning" data-id="${id}" value="${esc(g.meaning)}"></div>
        <div class="field"><label class="field-label" for="e1-gl-c-${id}">Convenção <span class="opt">opcional</span></label>
          <input id="e1-gl-c-${id}" class="input" type="text" data-e1f="gl-convention" data-id="${id}" value="${esc(g.convention)}"></div></div>`
      : `<span class="mean">${esc(g.meaning)}${changed ? ' <span class="e1-mark">ajustado por você</span>' : ""}</span>
        ${g.convention ? `<span class="conv">${esc(g.convention)}</span>` : ""}${g.src ? `<span class="src">${esc(g.src)}</span>` : ""}`;
    const why = g.dec === "rej"
      ? `<div class="e1-gl-why"><div class="why" role="group" aria-label="Por que rejeitar ${esc(pl.acronym)}">${GL_WHY.map(([k, l]) => `<button type="button" data-e1="gl-why" data-id="${id}" data-v="${k}" aria-pressed="${g.why === k}">${esc(l)}</button>`).join("")}</div>
        ${g.why === "outro" ? `<label class="sr-only" for="e1-gl-r-${id}">Qual o motivo?</label><input id="e1-gl-r-${id}" class="input" type="text" data-e1f="gl-reason" data-id="${id}" value="${esc(g.reason)}" placeholder="Qual o motivo?">` : ""}</div>` : "";
    return `<div class="e1-gl-row${g.dec === "ok" ? " ok" : g.dec === "rej" ? " rej" : ""}" data-gl="${id}">
      <span class="ac">${esc(pl.acronym)}</span>
      <div class="body">${body}${why}</div>
      <div class="acts">
        <button type="button" class="e1-gl-b ok" data-e1="gl-dec" data-id="${id}" data-v="ok" aria-pressed="${g.dec === "ok"}" aria-label="Aceitar ${esc(pl.acronym)}">✓</button>
        <button type="button" class="e1-gl-b rej" data-e1="gl-dec" data-id="${id}" data-v="rej" aria-pressed="${g.dec === "rej"}" aria-label="Rejeitar ${esc(pl.acronym)}">✕</button>
        <button type="button" class="lnk" data-e1="gl-edit" data-id="${id}">${g.editing ? "pronto" : "ajustar"}</button></div></div>`;
  }
  function screenGl(M) {
    const left = M.gls.filter((g) => !g.dec).length;
    return `<div class="e1-cqbar"><span class="e1-count">${left ? `<b>${left}</b> ${left === 1 ? "sigla para conferir" : "siglas para conferir"}` : "Todas conferidas"}</span>
      ${left ? `<button type="button" class="btn btn-outline" data-e1="gl-all">✓ Aceitar tudo (${left})</button>` : ""}</div>
      <div class="e1-gl">${M.gls.map(glRow).join("")}</div>`;
  }

  // ---------- tela 1: caso de uso ----------
  function ucCard(u) {
    const pl = u.payload;
    return `<button type="button" class="e1-uc" data-e1="uc" data-id="${esc(u.edit_id)}" aria-pressed="${u.sel}">
      <span class="ck" aria-hidden="true">${u.sel ? "✓" : ""}</span>
      <span class="t">${esc(pl.name)}${u.mine ? ' <span class="e1-seu">seu</span>' : ""}</span>
      <span class="d">${esc(pl.description || "")}</span>
      ${list(pl.actors).length ? `<span class="who">${list(pl.actors).map(esc).join(", ")}</span>` : ""}</button>`;
  }
  function appliedUcCard(u) {
    return `<div class="e1-uc done" aria-label="${esc(u.name)}, já aprovado">
      <span class="ck" aria-hidden="true">✓</span>
      <span class="t">${esc(u.name)}</span>
      <span class="d">${esc(u.description || "")}</span>
      <span class="src">já aprovado</span></div>`;
  }
  // caso escrito pelo revisor: ja conta como escolhido; da para editar ou remover
  function ownCard(o, i) {
    return `<div class="e1-uc own" role="group" aria-label="${esc(o.name)}, escrito por você">
      <span class="ck" aria-hidden="true">✓</span>
      <span class="t">${esc(o.name)} <span class="e1-seu">seu</span></span>
      <span class="d">${esc(o.desc)}</span>
      ${o.who ? `<span class="who">${esc(o.who)}</span>` : ""}
      <span class="e1-uc-a"><button type="button" class="lnk" data-e1="own-edit" data-i="${i}">editar</button><button type="button" class="lnk" data-e1="own-del" data-i="${i}">remover</button></span></div>`;
  }
  const addTile = () => `<button type="button" class="e1-uc e1-add" data-e1="draft-on"><span class="t">+ Escrever o meu</span></button>`;

  function noUcBlock(M) {
    const n = M.noUc;
    if (!n) return `<button type="button" class="lnk e1-nouc" data-e1="nouc-on">Não temos caso de uso</button>`;
    if (n.ok) return `<p class="e1-nouc-ok"><b>Sem caso de uso:</b> ${esc(n.text)} <button type="button" class="lnk" data-e1="nouc-off">desfazer</button></p>`;
    return `<div class="e1-nouc-f"><label class="field-label" for="e1-nouc">Por que não há caso de uso? ${req(n.text.trim())}</label>
      <div class="row"><input id="e1-nouc" class="input${n.tried && !n.text.trim() ? " miss" : ""}" type="text" data-e1f="nouc" value="${esc(n.text)}" placeholder="Ex.: o cliente ainda não definiu quem vai usar">
      <button type="button" class="btn btn-sm" data-e1="nouc-ok">Confirmar</button><button type="button" class="btn btn-ghost btn-sm" data-e1="nouc-off">Cancelar</button></div></div>`;
  }
  // proposito, escopo e usuarios descrevem o mesmo projeto: um card, um aceite (no servidor seguem tres aceites)
  const reqsOk = (M) => M.reqs.length > 0 && M.reqs.every((x) => x.ok);
  function reqCard(M) {
    const ok = reqsOk(M), editing = !!M.reqEditing;
    const rows = M.reqs.map((x) => {
      const label = REQ_LABEL[x.field], id = "e1-req-" + x.field;
      const val = editing
        ? `<textarea id="${id}" class="textarea${x.value.trim() ? "" : " miss"}" rows="${x.field === "users" ? 1 : 2}" data-e1f="req" data-id="${esc(x.edit_id)}">${esc(x.value)}</textarea>`
        : `<span class="v">${esc(x.value || "—")}</span>${x.value !== x.proposed ? ' <span class="e1-mark">ajustado por você</span>' : ""}`;
      return `<div class="e1-req-row"><dt>${editing ? `<label for="${id}">${esc(label)}</label>` : esc(label)}</dt><dd>${val}</dd></div>`;
    }).join("");
    return `<article class="e1-req${ok ? " ok" : ""}">
      <dl class="e1-req-list">${rows}</dl>
      <div class="e1-req-a">
        <button type="button" class="e1-ok" data-e1="req-ok" aria-pressed="${ok}">✓ ${ok ? "Aceito" : "Aceitar"}</button>
        <button type="button" class="lnk" data-e1="req-edit">${editing ? "pronto" : "ajustar"}</button>
      </div></article>`;
  }
  // sobre o projeto ja aplicado: proposito em destaque, escopo em dentro/fora, usuarios em etiquetas
  function aboutCard(R) {
    const sc = String(R.scope || ""), m = sc.match(/^\s*dentro:\s*([\s\S]*?)\s*fora:\s*([\s\S]*)$/i);
    const scope = !sc ? "" : m
      ? `<div class="e1-about-scope"><div><span class="e1-about-k in">Dentro</span><p>${esc(m[1].replace(/[.;]\s*$/, ""))}</p></div><div><span class="e1-about-k out">Fora</span><p>${esc(m[2].replace(/[.;]\s*$/, ""))}</p></div></div>`
      : `<p>${esc(sc)}</p>`;
    const users = String(R.users || "").split(",").map((u) => u.trim()).filter(Boolean);
    return `<article class="e1-about">
      <div class="e1-about-head"><span class="e1-about-ok" aria-hidden="true">✓</span>aplicado</div>
      ${R.purpose ? `<section><h4>${REQ_LABEL.purpose}</h4><p class="e1-about-lead">${esc(R.purpose)}</p></section>` : ""}
      ${scope ? `<section><h4>${REQ_LABEL.scope}</h4>${scope}</section>` : ""}
      ${users.length ? `<section><h4>${REQ_LABEL.users}</h4><div class="e1-about-users">${users.map((u) => `<span>${esc(u)}</span>`).join("")}</div></section>` : ""}
    </article>`;
  }
  function screenUc(M) {
    const cards = M.ucs.map(ucCard).join("") + M.applied.ucs.map(appliedUcCard).join("") + M.owns.map(ownCard).join("") + addTile();
    const reqs = M.reqs.length
      ? `<h3 class="e1-sub">Sobre o projeto</h3>${reqCard(M)}`
      : M.appliedReq.purpose || M.appliedReq.scope
        ? `<h3 class="e1-sub">Sobre o projeto</h3>${aboutCard(M.appliedReq)}`
        : "";
    const nada = !M.ucs.length && !M.reqs.length && (chosenUcs(M).length || M.appliedReq.no_use_case)
      ? `<div class="e1-empty"><b>Nada a decidir</b><span>Caso de uso já aprovado.</span></div>` : "";
    return `${nada}<div class="e1-ucgrid">${cards}</div>
      ${noUcBlock(M)}
      ${reqs}`;
  }

  // ---------- render ----------
  function stepperHtml(M) {
    const vis = visibleSteps(M);
    return vis.map((i, k) => {
      const s = STEPS[i], cur = i === M.step, done = !cur && !missing(M, i).length;
      return `<button type="button" class="${cur ? "cur" : done ? "done" : ""}" data-e1="go" data-step="${i}"${cur ? ' aria-current="step"' : ""}>
        <span class="n">${done ? "✓" : k + 1}</span><span class="lbl">${esc(s.title)}</span></button>`;
    }).join("");
  }
  const nextStep = (M) => { const v = visibleSteps(M); return v[v.indexOf(M.step) + 1]; };
  const prevStep = (M) => { const v = visibleSteps(M); return v[v.indexOf(M.step) - 1]; };
  function screenHtml(M) {
    const s = STEPS[M.step];
    const body = M.step === 0 ? screenUc(M) : M.step === 1 ? screenCq(M) : M.step === 2 ? screenGd(M) : screenGl(M);
    const ns = isAuto() || !E.ctx.api ? 0 : unsavedOf(M);
    const aviso = ns ? `<div class="unsaved" role="status"><span><b>${ns === 1 ? "1 decisão ainda não salva" : ns + " decisões ainda não salvas"}.</b> Só entram na ontologia depois de conferir e salvar.</span>
      <button type="button" class="btn" data-e1="save">Conferir e salvar</button></div>` : "";
    return `<p class="e1-lead">${esc(s.lead)}</p>${aviso}${body}`;
  }
  function footHtml(M) {
    const nx = nextStep(M);
    const next = nx === undefined ? "Conferir e salvar" : `Próximo: ${STEPS[nx].title} →`;
    return `<span class="e1-msg" id="e1-msg" role="status" aria-live="polite"></span>
      ${prevStep(M) !== undefined ? '<button type="button" class="btn btn-outline" data-e1="back">← Voltar</button>' : ""}
      <button type="button" class="btn" data-e1="next">${esc(next)}</button>`;
  }
  function render(focusSel) {
    if (!E.el) return;
    const M = E.M;
    if (!visibleSteps(M).includes(M.step)) M.step = visibleSteps(M)[0];
    const auto = isAuto();
    E.el.innerHTML = `<div class="e1${auto ? " is-auto" : ""}">${auto ? '<p class="e1-auto">Modo automático: a IA decide e aplica. Aqui você acompanha.</p>' : ""}<nav class="e1-steps" aria-label="Etapa 1">${stepperHtml(M)}</nav>
      <section class="e1-screen" data-screen="${STEPS[M.step].id}">${screenHtml(M)}</section>
      <div class="e1-foot">${footHtml(M)}</div></div>`;
    if (focusSel) { const t = $(focusSel, E.el); if (t) t.focus({ preventScroll: true }); }
    writeDraft(M);
    if (E.ctx.onCount) E.ctx.onCount(remainingOf(M) + unsavedOf(M));
  }
  // depois de digitar: atualiza so o stepper e as marcas de obrigatorio, sem perder o foco
  function refresh(input) {
    const nav = $(".e1-steps", E.el);
    if (nav) nav.innerHTML = stepperHtml(E.M);
    if (input) input.classList.toggle("miss", !input.value.trim());
    const label = input && input.id ? $(`label[for="${input.id}"] .req`, E.el) : null;
    if (label) label.hidden = !!input.value.trim();
    msg("");
    writeDraft(E.M);
    if (E.ctx.onCount) E.ctx.onCount(remainingOf(E.M) + unsavedOf(E.M));
  }
  function msg(text, kind) {
    const el = $("#e1-msg", E.el);
    if (!el) return;
    el.className = "e1-msg" + (kind ? " " + kind : "");
    el.innerHTML = text;
  }

  // ---------- eventos ----------
  function goStep(i) {
    const vis = visibleSteps(E.M);
    if (i === undefined || !vis.includes(i)) return;
    E.M.step = i;
    render();
    const top = $(".e1", E.el);
    if (top) window.scrollTo({ top: Math.max(0, top.getBoundingClientRect().top + window.scrollY - 72), behavior: "smooth" });
  }
  function onNext() {
    const falta = missing(E.M, E.M.step);
    if (falta.length) { msg(`<b>Falta:</b> ${falta.map(esc).join("; ")}`, "warn"); return; }
    const nx = nextStep(E.M);
    if (nx !== undefined) { goStep(nx); return; }
    trySave();
  }
  function trySave() {
    if (isAuto()) { msg("No modo automático, quem salva é a IA.", ""); return; }
    // salvar so com as telas visiveis completas; leva para a primeira que falta
    const bad = visibleSteps(E.M).find((i) => missing(E.M, i).length);
    if (bad !== undefined) { goStep(bad); msg(`<b>Falta em ${esc(STEPS[bad].title)}:</b> ${missing(E.M, bad).map(esc).join("; ")}`, "warn"); return; }
    openSave();
  }
  function onClick(e) {
    const b = e.target.closest("[data-e1]");
    if (!b || !E.el.contains(b)) return;
    const M = E.M, act = b.dataset.e1, it = b.dataset.id ? M.byId[b.dataset.id] : null;
    if (isAuto() && !VIEW_ACTS.has(act)) return;
    switch (act) {
      case "go": return goStep(Number(b.dataset.step));
      case "back": return goStep(prevStep(M));
      case "next": return onNext();
      case "save": return trySave();
      case "gd-ask": return it && window.AkmeChannel && window.AkmeChannel.ask(`[${(it.payload || {}).id || it.edit_id}] `);
      case "outras": if (E.ctx.onOutras) E.ctx.onOutras(); return;
      case "uc": it.sel = !it.sel; if (it.sel && M.noUc) M.noUc = null; return render(`[data-e1="uc"][data-id="${b.dataset.id}"]`);
      case "draft-on": return openDraft(null, b);
      case "own-edit": return openDraft(Number(b.dataset.i), b);
      case "own-del": M.owns.splice(Number(b.dataset.i), 1); return render('[data-e1="draft-on"]');
      case "nouc-on": M.noUc = { text: "", ok: false }; return render("#e1-nouc");
      case "nouc-off": M.noUc = null; return render('[data-e1="nouc-on"]');
      case "nouc-ok": return confirmNoUc();
      case "req-ok": { const ok = !reqsOk(M); M.reqs.forEach((x) => { x.ok = ok; }); if (ok) M.reqEditing = false; return render('[data-e1="req-ok"]'); }
      case "cq-det": it.det = !it.det; return render(`[data-e1="cq-det"][data-id="${b.dataset.id}"]`);
      case "cq-edit": it.editing = !it.editing; return render(it.editing ? `[data-e1f="cq-q"][data-id="${b.dataset.id}"]` : `[data-e1="cq-edit"][data-id="${b.dataset.id}"]`);
      case "cq-dec": it.dec = b.dataset.v; it.open = true; return render(it.dec === "rej" ? `[data-e1="cq-why"][data-id="${b.dataset.id}"]` : `[data-e1="cq-prio"][data-id="${b.dataset.id}"]`);
      case "cq-prio": it.prio = b.dataset.v; it.open = false; return render(focusAfter(it.edit_id));
      case "cq-why": {
        it.why = b.dataset.v;
        if (it.why === "outro") { if (WHY.some(([, l]) => l === it.reason)) it.reason = ""; return render(`#e1-cq-r-${b.dataset.id}`); }
        it.reason = WHY_L[it.why]; it.open = false; return render(focusAfter(it.edit_id));
      }
      case "cq-close": if (!cqDone(it)) return; it.open = false; return render(focusAfter(it.edit_id));
      case "cq-open": it.open = true; return render(`[data-e1="cq-dec"][data-id="${b.dataset.id}"][data-v="${it.dec}"]`);
      case "cq-all": {
        // so as que ainda nao tem decisao completa; as ja decididas ficam como estao
        cqGroups(M).groups.flatMap((g) => g.ai).filter((c) => !cqDone(c)).forEach((c) => {
          c.dec = "ok"; c.open = false;
          if (!c.prio) c.prio = PRIO_L[c.payload.priority] ? c.payload.priority : "medium";
        });
        return render('[data-e1="next"]');
      }
      case "gd-det": it.det = !it.det; return render(`[data-e1="gd-det"][data-id="${b.dataset.id}"]`);
      case "gd-more": it.more = !it.more; return render(`[data-e1="gd-more"][data-id="${b.dataset.id}"]`);
      case "gd-set": {
        it.choice = b.dataset.v; it.winner = ""; it.open = true;
        if (!needOf(it)) { it.open = false; return render(focusAfterGd(it.edit_id)); }
        return render(`#e1-gd-${b.dataset.id}`);
      }
      case "dv-win": {
        const x = (it.payload.sources || [])[Number(b.dataset.i)] || {};
        it.choice = "precedence"; it.winner = x.label || "Fonte " + String.fromCharCode(65 + Number(b.dataset.i)); it.more = false; it.open = false;
        return render(focusAfterGd(it.edit_id));
      }
      case "gd-close": if (!gdDone(it)) return; it.open = false; return render(focusAfterGd(it.edit_id));
      case "gd-open": it.open = true; return render(`[data-e1="gd-det"][data-id="${b.dataset.id}"]`);
      case "gl-dec": it.dec = it.dec === b.dataset.v ? null : b.dataset.v; if (it.dec === "rej") it.editing = false;
        return render(it.dec === "rej" ? `[data-e1="gl-why"][data-id="${b.dataset.id}"]` : `[data-e1="gl-dec"][data-id="${b.dataset.id}"][data-v="${b.dataset.v}"]`);
      case "gl-why": it.why = b.dataset.v; if (it.why !== "outro") it.reason = ""; return render(it.why === "outro" ? `#e1-gl-r-${b.dataset.id}` : `[data-e1="gl-why"][data-id="${b.dataset.id}"][data-v="${it.why}"]`);
      case "gl-edit": it.editing = !it.editing; if (it.editing && it.dec === "rej") it.dec = null; return render(it.editing ? `#e1-gl-m-${b.dataset.id}` : `[data-e1="gl-edit"][data-id="${b.dataset.id}"]`);
      case "gl-all": M.gls.forEach((g) => { if (!g.dec) g.dec = "ok"; }); return render('[data-e1="next"]');
      case "cq-new": return openCq(null);
      case "ocq-edit": return openCq(Number(b.dataset.i));
      case "ocq-del": M.ownCqs.splice(Number(b.dataset.i), 1); return render('[data-e1="cq-new"]');
      case "req-edit": M.reqEditing = !M.reqEditing; return render(M.reqEditing ? '[data-e1f="req"]' : '[data-e1="req-edit"]');
    }
  }
  // ---------- janela de criar caso de uso: centro da tela, fundo desfocado, fecha so ao adicionar ou cancelar ----------
  const D = { i: null, from: null };
  function dlg() {
    let d = document.getElementById("e1-dlg");
    if (d) return d;
    d = document.createElement("dialog");
    d.id = "e1-dlg"; d.className = "dlg e1-dlg"; d.setAttribute("aria-labelledby", "e1-dlg-t");
    d.innerHTML = `<form method="dialog" class="dlg-body" novalidate>
      <h2 class="h3-semibold" id="e1-dlg-t">Novo caso de uso</h2>
      <div class="field"><label class="field-label" for="e1-d-name">Nome <span class="req">obrigatório</span></label>
        <input id="e1-d-name" class="input" type="text" autocomplete="off" placeholder="Ex.: Giro de estoque"></div>
      <div class="field"><label class="field-label" for="e1-d-desc">Para quê <span class="req">obrigatório</span></label>
        <textarea id="e1-d-desc" class="textarea" rows="3" placeholder="Ex.: ver quais produtos ficam parados há mais de 60 dias"></textarea></div>
      <div class="field"><label class="field-label" for="e1-d-who">Quem usa <span class="opt">opcional</span></label>
        <input id="e1-d-who" class="input" type="text" autocomplete="off" placeholder="Ex.: comprador"></div>
      <p class="e1-dlg-msg" id="e1-dlg-msg" role="status" aria-live="polite"></p>
      <div class="dlg-actions"><button type="button" class="btn btn-outline" data-d="cancel">Cancelar</button><button type="submit" class="btn" data-d="ok">Adicionar</button></div></form>`;
    document.body.appendChild(d);
    const form = d.querySelector("form");
    form.addEventListener("submit", (e) => { e.preventDefault(); addDraft(); });
    d.querySelector('[data-d="cancel"]').addEventListener("click", () => closeDraft());
    // Esc fecha como cancelar; clicar fora nao fecha
    d.addEventListener("cancel", (e) => { e.preventDefault(); closeDraft(); });
    d.addEventListener("input", (e) => { const el = e.target; if (el.classList.contains("miss") && el.value.trim()) el.classList.remove("miss"); syncReq(el); });
    return d;
  }
  function syncReq(el) {
    const tag = d0(`label[for="${el.id}"] .req`);
    if (tag) tag.hidden = !!el.value.trim();
  }
  const d0 = (sel) => document.querySelector("#e1-dlg " + sel);
  function openDraft(i, from) {
    const d = dlg(), o = i === null ? { name: "", desc: "", who: "" } : E.M.owns[i];
    D.i = i; D.from = from ? (i === null ? '[data-e1="draft-on"]' : `[data-e1="own-edit"][data-i="${i}"]`) : null;
    d0("#e1-dlg-t").textContent = i === null ? "Novo caso de uso" : "Editar caso de uso";
    d0('[data-d="ok"]').textContent = i === null ? "Adicionar" : "Salvar";
    [["name", o.name], ["desc", o.desc], ["who", o.who]].forEach(([k, v]) => { const el = d0("#e1-d-" + k); el.value = v || ""; el.classList.remove("miss"); syncReq(el); });
    d0("#e1-dlg-msg").textContent = "";
    d.showModal();
    d0("#e1-d-name").focus();
  }
  function closeDraft(focusSel) {
    const d = document.getElementById("e1-dlg");
    if (d && d.open) d.close();
    const t = $(focusSel || D.from || '[data-e1="draft-on"]', E.el);
    if (t) t.focus({ preventScroll: true });
  }
  function addDraft() {
    const M = E.M, v = (k) => d0("#e1-d-" + k).value.trim();
    const falta = [["name", "o nome"], ["desc", "para quê serve"]].filter(([k]) => !v(k));
    falta.forEach(([k]) => d0("#e1-d-" + k).classList.add("miss"));
    if (falta.length) { d0("#e1-dlg-msg").innerHTML = "<b>Falta:</b> " + falta.map(([, l]) => l).join(" e "); d0("#e1-d-" + falta[0][0]).focus(); return; }
    const o = { name: v("name"), desc: v("desc"), who: v("who") };
    let i = D.i;
    if (i === null) { o.tmp = "seu-" + ++M.seq; M.owns.push(o); i = M.owns.length - 1; } else Object.assign(M.owns[i], o);
    M.noUc = null;
    render();
    closeDraft(`[data-e1="own-edit"][data-i="${i}"]`);
  }
  // ---------- janela de criar pergunta: mesmo padrao da de caso de uso ----------
  const Q = { i: null, prio: "" };
  const q0 = (sel) => document.querySelector("#e1-cq-dlg " + sel);
  function cqDlg() {
    let d = document.getElementById("e1-cq-dlg");
    if (d) return d;
    d = document.createElement("dialog");
    d.id = "e1-cq-dlg"; d.className = "dlg e1-dlg"; d.setAttribute("aria-labelledby", "e1-cq-dlg-t");
    d.innerHTML = `<form method="dialog" class="dlg-body" novalidate>
      <h2 class="h3-semibold" id="e1-cq-dlg-t">Nova pergunta</h2>
      <div class="field"><label class="field-label" for="e1-n-q">Pergunta <span class="req">obrigatório</span></label>
        <textarea id="e1-n-q" class="textarea" rows="2" placeholder="Ex.: Quais produtos ficaram mais de 60 dias sem venda?"></textarea></div>
      <div class="field" id="e1-n-uc-f"><label class="field-label" for="e1-n-uc">Caso de uso <span class="req">obrigatório</span></label><select id="e1-n-uc" class="select"></select></div>
      <div class="e1-dlg-2">
        <div class="field"><label class="field-label" for="e1-n-type">Tipo <span class="req">obrigatório</span></label>
          <select id="e1-n-type" class="select"><option value="">escolha</option>${CQ_TYPES.map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join("")}</select></div>
        <div class="field"><label class="field-label" for="e1-n-c">Conceitos <span class="req">obrigatório</span></label>
          <input id="e1-n-c" class="input" type="text" autocomplete="off" placeholder="Ex.: Produto, Pedido"></div></div>
      <div class="field"><span class="field-label" id="e1-n-p-l">Prioridade <span class="req">obrigatório</span></span>
        <div class="seg" role="group" aria-labelledby="e1-n-p-l" id="e1-n-p">${PRIO.map(([v, l]) => `<button type="button" data-p="${v}" aria-pressed="false">${l}</button>`).join("")}</div></div>
      <p class="e1-dlg-msg" id="e1-cq-dlg-msg" role="status" aria-live="polite"></p>
      <div class="dlg-actions"><button type="button" class="btn btn-outline" data-d="cancel">Cancelar</button><button type="submit" class="btn" data-d="ok">Adicionar</button></div></form>`;
    document.body.appendChild(d);
    d.querySelector("form").addEventListener("submit", (e) => { e.preventDefault(); addCq(); });
    d.querySelector('[data-d="cancel"]').addEventListener("click", () => closeCq());
    d.addEventListener("cancel", (e) => { e.preventDefault(); closeCq(); });
    d.addEventListener("click", (e) => {
      const b = e.target.closest("[data-p]");
      if (!b) return;
      Q.prio = b.dataset.p;
      d.querySelectorAll("[data-p]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.p === Q.prio)));
      q0("#e1-n-p").classList.remove("miss"); syncCqReq();
    });
    d.addEventListener("input", (e) => { if (e.target.value && e.target.value.trim()) e.target.classList.remove("miss"); syncCqReq(); });
    return d;
  }
  function syncCqReq() {
    const filled = { "e1-n-q": q0("#e1-n-q").value.trim(), "e1-n-uc": q0("#e1-n-uc").value, "e1-n-type": q0("#e1-n-type").value, "e1-n-c": q0("#e1-n-c").value.trim() };
    Object.entries(filled).forEach(([id, v]) => { const t = q0(`label[for="${id}"] .req`); if (t) t.hidden = !!v; });
    q0("#e1-n-p-l .req").hidden = !!Q.prio;
  }
  function openCq(i) {
    const d = cqDlg(), M = E.M, o = i === null ? { q: "", uc: "", type: "", concepts: [], prio: "" } : M.ownCqs[i];
    const ucs = noUcOk(M) ? [] : chosenUcs(M);
    Q.i = i; Q.prio = o.prio;
    q0("#e1-cq-dlg-t").textContent = i === null ? "Nova pergunta" : "Editar pergunta";
    q0('[data-d="ok"]').textContent = i === null ? "Adicionar" : "Salvar";
    q0("#e1-n-uc-f").hidden = !ucs.length;
    const ucSel = o.uc || (ucs.length === 1 ? ucs[0].id : "");
    q0("#e1-n-uc").innerHTML = `<option value="">escolha</option>${ucs.map((u) => `<option value="${esc(u.id)}"${u.id === ucSel ? " selected" : ""}>${esc(u.name)}</option>`).join("")}`;
    q0("#e1-n-q").value = o.q; q0("#e1-n-type").value = o.type; q0("#e1-n-c").value = o.concepts.join(", ");
    d.querySelectorAll("[data-p]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.p === Q.prio)));
    d.querySelectorAll(".miss").forEach((x) => x.classList.remove("miss"));
    q0("#e1-cq-dlg-msg").textContent = "";
    syncCqReq();
    d.showModal();
    q0("#e1-n-q").focus();
  }
  function closeCq(focusSel) {
    const d = document.getElementById("e1-cq-dlg");
    if (d && d.open) d.close();
    const t = $(focusSel || (Q.i === null ? '[data-e1="cq-new"]' : `[data-e1="ocq-edit"][data-i="${Q.i}"]`), E.el);
    if (t) t.focus({ preventScroll: true });
  }
  function addCq() {
    const M = E.M, needUc = !q0("#e1-n-uc-f").hidden;
    const o = { q: q0("#e1-n-q").value.trim(), uc: needUc ? q0("#e1-n-uc").value : "", type: q0("#e1-n-type").value,
      concepts: q0("#e1-n-c").value.split(",").map((x) => x.trim()).filter(Boolean), prio: Q.prio };
    const falta = [["#e1-n-q", !o.q, "a pergunta"], ["#e1-n-uc", needUc && !o.uc, "o caso de uso"], ["#e1-n-type", !o.type, "o tipo"],
      ["#e1-n-c", !o.concepts.length, "os conceitos"], ["#e1-n-p", !o.prio, "a prioridade"]].filter((x) => x[1]);
    falta.forEach(([sel]) => q0(sel).classList.add("miss"));
    if (falta.length) {
      q0("#e1-cq-dlg-msg").innerHTML = "<b>Falta:</b> " + falta.map((x) => x[2]).join(", ");
      const first = q0(falta[0][0]); (first.matches(".seg") ? first.querySelector("button") : first).focus();
      return;
    }
    let i = Q.i;
    if (i === null) { M.ownCqs.push(o); i = M.ownCqs.length - 1; } else Object.assign(M.ownCqs[i], o);
    render();
    closeCq(`[data-e1="ocq-edit"][data-i="${i}"]`);
  }
  // ---------- conferir e salvar ----------
  // traduz as escolhas para as mesmas chamadas de sempre: /api/review, /api/propose e, no fim, /api/apply
  function planOps(M) {
    const ops = [], noUc = noUcOk(M);
    const rv = (c, decision, extra, label) => ops.push({ label, path: "/api/review", body: Object.assign({ edit_id: c.edit_id, decision }, extra) });
    // casos escritos pelo revisor primeiro: as perguntas dele usam o id que o servidor devolve
    if (!noUc) M.owns.forEach((o) => ops.push({ label: `caso de uso “${o.name}”`, path: "/api/propose", own: o,
      body: { type: "add_use_case", payload: Object.assign({ name: o.name, description: o.desc }, o.who ? { actors: [o.who] } : {}) } }));
    M.ucs.forEach((u) => rv(u, !noUc && u.sel ? "accept" : "reject", !noUc && u.sel ? {} : { reason: R_UC }, `caso de uso “${u.payload.name}”`));
    const noUcPend = M.noUcIds.map((id) => ({ edit_id: id }));
    if (noUc && noUcPend.length) {
      rv(noUcPend[0], "accept", { edits: { value: M.noUc.text } }, "sem caso de uso");
      noUcPend.slice(1).forEach((x) => rv(x, "reject", { reason: "repetido" }, "sem caso de uso"));
    } else {
      if (noUc) ops.push({ label: "sem caso de uso", path: "/api/propose", body: { type: "add_requirement", payload: { field: "no_use_case", value: M.noUc.text } } });
      noUcPend.forEach((x) => rv(x, "reject", { reason: R_NOUC }, "sem caso de uso"));
    }
    M.reqs.forEach((r) => rv(r, "accept", r.value.trim() !== r.proposed ? { edits: { value: r.value.trim() } } : {}, REQ_LABEL[r.field] || r.field));
    const { groups, out } = cqGroups(M);
    groups.flatMap((g) => g.ai).forEach((c) => {
      if (c.dec === "rej") return rv(c, "reject", { reason: reasonOf(c) }, `pergunta “${c.q}”`);
      const pl = c.payload, edits = { status: "approved", priority: c.prio };
      if (c.q.trim() !== String(pl.question || "")) edits.question = c.q.trim();
      if (c.type !== (pl.type || "")) edits.type = c.type;
      if (c.concepts.join("|") !== list(pl.concepts).join("|")) edits.concepts = c.concepts;
      rv(c, "accept", { edits }, `pergunta “${c.q}”`);
    });
    out.forEach((c) => rv(c, "reject", { reason: R_OUT }, `pergunta “${c.q}”`));
    M.ownCqs.forEach((o) => ops.push({ label: `pergunta “${o.q}”`, path: "/api/propose", ownCq: o,
      body: { type: "add_competency_question", payload: { question: o.q, type: o.type, concepts: o.concepts, priority: o.prio, status: "approved" } } }));
    M.gds.forEach((c) => {
      const edits = { decision: c.choice };
      if (c.kind === "gap") { if (c.text.trim()) edits.note = c.choice === "reformulate" ? "Nova pergunta: " + c.text.trim() : c.text.trim(); }
      else { if (c.choice === "precedence") edits.winner = c.winner; else if (c.text.trim()) edits.reason = c.text.trim(); }
      rv(c, "accept", { edits }, c.kind === "gap" ? `lacuna “${c.payload.question}”` : `divergência “${c.payload.topic}”`);
    });
    M.gls.forEach((g) => {
      const pl = g.payload, label = `sigla ${pl.acronym}`;
      if (g.dec === "rej") return rv(g, "reject", { reason: glReason(g) }, label);
      const edits = {};
      if (g.meaning.trim() !== String(pl.meaning || "")) edits.meaning = g.meaning.trim();
      if (g.convention.trim() !== String(pl.convention || "")) edits.convention = g.convention.trim();
      rv(g, "accept", Object.keys(edits).length ? { edits } : {}, label);
    });
    return ops;
  }
  function summaryHtml(M) {
    const sec = (title, rows) => (rows.length ? `<h3 class="e1-sub">${esc(title)}</h3><ul class="e1-sum">${rows.join("")}</ul>` : "");
    const li = (t, m, cls) => `<li class="${cls || ""}"><span class="q">${esc(t)}</span>${m ? `<span class="m">${esc(m)}</span>` : ""}</li>`;
    const noUc = noUcOk(M), { groups, out } = cqGroups(M), ai = groups.flatMap((g) => g.ai);
    const ucRows = noUc ? [li("Sem caso de uso", M.noUc.text)]
      : chosenUcs(M).map((u) => li(u.name, M.owns.some((o) => o.tmp === u.id) ? "seu" : M.applied.ucs.some((a) => a.id === u.id) ? "já aprovado" : "escolhido"));
    const notChosen = M.ucs.filter((u) => noUc || !u.sel).map((u) => li(u.payload.name, "fica de fora", "off"));
    const reqRows = M.reqs.map((r) => li(REQ_LABEL[r.field] || r.field, r.value.trim() !== r.proposed ? "aceito com ajuste" : "aceito"));
    const cqRows = ai.filter((c) => c.dec === "ok").map((c) => li(c.q, PRIO_L[c.prio]))
      .concat(M.ownCqs.map((o) => li(o.q, `${PRIO_L[o.prio]} · sua`)))
      .concat(ai.filter((c) => c.dec === "rej").map((c) => li(c.q, "rejeitada: " + reasonOf(c), "off")))
      .concat(out.map((c) => li(c.q, "fora dos casos escolhidos", "off")));
    const gdRows = M.gds.map((c) => li(c.kind === "gap" ? c.payload.question : divTitle(c.payload), gdLabel(c) + (c.text.trim() ? ": " + c.text.trim() : "")));
    return sec("Caso de uso", ucRows.concat(notChosen)) + sec("Sobre o projeto", reqRows) + sec("Perguntas", cqRows) + sec("Lacunas e divergências", gdRows)
      + sec("Glossário", M.gls.map((g) => (g.dec === "rej" ? li(g.payload.acronym, "rejeitada: " + glReason(g), "off") : li(`${g.payload.acronym} · ${g.meaning}`, ""))));
  }
  function readName() {
    try { return localStorage.getItem("akme-reviewer") || ""; } catch (e) { return ""; }
  }
  function openSave() {
    let d = document.getElementById("e1-save");
    if (!d) {
      d = document.createElement("dialog");
      d.id = "e1-save"; d.className = "dlg e1-dlg e1-save"; d.setAttribute("aria-labelledby", "e1-save-t");
      document.body.appendChild(d);
      d.addEventListener("cancel", (e) => { e.preventDefault(); if (!E.saving) closeSave(); });
      d.addEventListener("click", (e) => {
        const b = e.target.closest("[data-s]");
        if (!b || b.disabled) return;
        if (b.dataset.s === "cancel") closeSave();
        else if (b.dataset.s === "done") { closeSave(); E.M = null; if (E.ctx.onDone) E.ctx.onDone(); }
      });
      d.addEventListener("submit", (e) => { e.preventDefault(); doSave(); });
    }
    const name = (E.ctx.reviewer || readName() || "").trim();
    d.innerHTML = `<form method="dialog" class="dlg-body" novalidate>
      <h2 class="h3-semibold" id="e1-save-t">Conferir e salvar</h2>
      <div class="e1-sum-wrap">${summaryHtml(E.M)}</div>
      <div class="field"><label class="field-label" for="e1-save-name">Seu nome <span class="req"${name ? " hidden" : ""}>obrigatório</span></label>
        <input id="e1-save-name" class="input" type="text" autocomplete="name" value="${esc(name)}" placeholder="quem aprova"></div>
      <p class="e1-dlg-msg" id="e1-save-msg" role="status" aria-live="polite">Salvar grava as decisões e aplica a etapa 1 na ontologia.</p>
      <div class="dlg-actions"><button type="button" class="btn btn-outline" data-s="cancel">Voltar</button><button type="submit" class="btn" data-s="ok">Salvar e aplicar</button></div></form>`;
    d.querySelector("#e1-save-name").addEventListener("input", (e) => { d.querySelector('label[for="e1-save-name"] .req').hidden = !!e.target.value.trim(); e.target.classList.remove("miss"); });
    d.showModal();
    const inp = d.querySelector("#e1-save-name");
    (name ? d.querySelector('[data-s="ok"]') : inp).focus();
  }
  function closeSave() {
    const d = document.getElementById("e1-save");
    if (d && d.open) d.close();
    const t = $('[data-e1="next"]', E.el); if (t) t.focus({ preventScroll: true });
  }
  async function doSave() {
    const d = document.getElementById("e1-save"), M = E.M, api = E.ctx.api;
    const say = (h) => { d.querySelector("#e1-save-msg").innerHTML = h; };
    const inp = d.querySelector("#e1-save-name"), name = inp.value.trim();
    if (!name) { inp.classList.add("miss"); inp.focus(); say("<b>Falta:</b> seu nome"); return; }
    if (!api) { say("Esta página está só para leitura: abra com <code>akme review</code> para salvar."); return; }
    try { localStorage.setItem("akme-reviewer", name); } catch (e) { /* sem armazenamento: segue */ }
    const btns = d.querySelectorAll("button"), ok = d.querySelector('[data-s="ok"]');
    btns.forEach((b) => { b.disabled = true; }); E.saving = true;
    const ops = planOps(M);
    let i = 0, applying = false;
    try {
      for (const o of ops) {
        i++;
        ok.textContent = `Salvando ${i} de ${ops.length}…`;
        const body = Object.assign({ reviewer: name }, o.body);
        if (o.ownCq) {
          const uc = o.ownCq.uc ? M.tmpMap[o.ownCq.uc] || o.ownCq.uc : "";
          if (uc) body.payload = Object.assign({}, body.payload, { use_cases: [uc] });
        }
        const res = await api.post(o.path, body);
        // proposta feita sai da lista local; um novo clique nao duplica
        if (o.own) {
          const nid = (res && res.payload && res.payload.id) || "";
          M.tmpMap[o.own.tmp] = nid;
          // se algo falhar depois, as perguntas suas ja apontam para o caso de uso gravado
          if (nid) M.ownCqs.forEach((q) => { if (q.uc === o.own.tmp) q.uc = nid; });
          M.owns.splice(M.owns.indexOf(o.own), 1);
        }
        if (o.ownCq) M.ownCqs.splice(M.ownCqs.indexOf(o.ownCq), 1);
      }
      ok.textContent = "Aplicando…"; applying = true;
      const out = await api.post("/api/apply", { approved_by: name, stage: "requirements" });
      const after = (out && out.stage_after) || {};
      E.saving = false;
      clearDraft(E.M.project);
      d.querySelector("form").innerHTML = `<h2 class="h3-semibold" id="e1-save-t">Etapa 1 salva e aplicada</h2>
        <div class="e1-empty"><b>${(out.applied || []).length} ${(out.applied || []).length === 1 ? "decisão entrou" : "decisões entraram"} na ontologia</b>
          <span>${window.AkmeChannel ? window.AkmeChannel.after() : "Volte para o chat: o agente segue para o próximo passo."}${after.label ? " Agora: " + esc(after.label) + "." : ""}</span></div>
        <div class="dlg-actions"><button type="button" class="btn" data-s="done">Fechar</button></div>`;
      d.querySelector('[data-s="done"]').focus();
    } catch (e) {
      E.saving = false;
      btns.forEach((b) => { b.disabled = false; }); ok.textContent = "Tentar de novo";
      const errs = (e.body && e.body.new_errors) || [];
      const where = applying ? "ao aplicar" : i ? `em ${esc(ops[i - 1].label)}` : "";
      say(`<b>Parou ${where}:</b> ${esc(e.message || String(e))}${errs.length ? `<ul>${errs.map((f) => `<li>${esc(f.subject || f.check || "")}: ${esc(f.message || "")}</li>`).join("")}</ul>` : ""}
        <br>O que já foi gravado continua gravado. Corrija e tente de novo.`);
      render();
    }
  }
  function confirmNoUc() {
    const M = E.M, n = M.noUc;
    n.tried = true;
    if (!n.text.trim()) { render("#e1-nouc"); msg("<b>Falta:</b> o motivo", "warn"); return; }
    if (M.owns.length) { msg("Remova os casos de uso escritos por você antes.", "warn"); return; }
    n.ok = true; n.text = n.text.trim();
    M.ucs.forEach((u) => { u.sel = false; });
    render('[data-e1="nouc-off"]');
  }
  // Enter no formulario confirma, como o botao
  function onKey(e) {
    if (e.key !== "Enter" || !e.target.dataset) return;
    const f = e.target.dataset.e1f;
    if (f === "nouc") { e.preventDefault(); confirmNoUc(); }
  }
  function onInput(e) {
    const el = e.target, f = el.dataset && el.dataset.e1f;
    if (!f || !E.el.contains(el) || isAuto()) return;
    const M = E.M;
    if (f === "nouc") M.noUc.text = el.value;
    else if (f === "cq-q") M.byId[el.dataset.id].q = el.value;
    else if (f === "cq-type") M.byId[el.dataset.id].type = el.value;
    else if (f === "cq-concepts") M.byId[el.dataset.id].concepts = el.value.split(",").map((x) => x.trim()).filter(Boolean);
    else if (f === "gl-meaning") M.byId[el.dataset.id].meaning = el.value;
    else if (f === "gl-convention") M.byId[el.dataset.id].convention = el.value;
    else if (f === "gl-reason") M.byId[el.dataset.id].reason = el.value;
    else if (f === "gd-text") { const c = M.byId[el.dataset.id]; const was = gdDone(c); c.text = el.value; if (was !== gdDone(c)) { const pos = el.selectionStart; render(); const t = $(`#${el.id}`, E.el); if (t) { t.focus(); t.setSelectionRange(pos, pos); } return; } }
    else if (f === "cq-reason") { const c = M.byId[el.dataset.id]; const was = cqDone(c); c.reason = el.value; if (was !== cqDone(c)) { const pos = el.selectionStart; render(); const t = $(`#${el.id}`, E.el); if (t) { t.focus(); t.setSelectionRange(pos, pos); } return; } }
    else if (f === "req") M.byId[el.dataset.id].value = el.value;
    refresh(el);
  }

  function mount(el, ctx) {
    if (E.wired !== el) {
      el.addEventListener("click", onClick);
      el.addEventListener("input", onInput);
      el.addEventListener("keydown", onKey);
      E.wired = el;
    }
    E.el = el;
    E.ctx = ctx || {};
    // um poll do servidor refaz a tela; quem estava digitando nao perde o foco nem o cursor
    const a = document.activeElement, keep = a && el.contains(a) ? {
      sel: a.id ? "#" + a.id : a.dataset.e1f ? `[data-e1f="${a.dataset.e1f}"]${a.dataset.id ? `[data-id="${a.dataset.id}"]` : ""}`
        : a.dataset.e1 ? `[data-e1="${a.dataset.e1}"]${a.dataset.id ? `[data-id="${a.dataset.id}"]` : ""}${a.dataset.v ? `[data-v="${a.dataset.v}"]` : ""}` : "",
      pos: typeof a.selectionStart === "number" ? [a.selectionStart, a.selectionEnd] : null } : null;
    E.M = buildModel(E.ctx.data, E.M);
    render();
    if (keep && keep.sel) {
      const t = $(keep.sel, el);
      if (t) { t.focus({ preventScroll: true }); if (keep.pos && t.setSelectionRange) t.setSelectionRange(keep.pos[0], keep.pos[1]); }
    }
  }

  window.AkmeEtapa1 = { mount, pendingCount, remaining, covers, aboutCard };
})();
