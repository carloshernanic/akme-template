// Revisao da etapa 1 em tres telas: caso de uso, perguntas, lacunas e divergencias.
// So muda a pagina: as decisoes viram as mesmas chamadas de /api/review e /api/propose de sempre.
// O review.js monta este modulo quando o seletor esta em "Etapa 1"; o resto da aba segue na caixa de entrada.
(function () {
  "use strict";

  // add_requirement destes campos e decidido na tela 1; os demais ficam na caixa de entrada
  const REQ_FIELDS = ["purpose", "scope", "users"];
  const REQ_LABEL = { purpose: "Propósito", scope: "Escopo", users: "Usuários" };
  // tipos que ja tem tela pronta; o resto continua em "Outras propostas" para nada sumir
  const READY = new Set(["add_use_case", "add_requirement", "add_competency_question"]);
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
  function buildModel(data, prev) {
    const old = (prev && prev.byId) || {};
    // owns: casos escritos pelo revisor; o rascunho vive na janela (dialogo), fora do modelo
    const M = { step: prev ? prev.step : 0, ucs: [], reqs: [], owns: prev ? prev.owns : [],
      seq: prev ? prev.seq : 0, noUc: prev ? prev.noUc : null, noUcSeen: prev ? prev.noUcSeen : {}, cqs: [], ownCqs: prev ? prev.ownCqs : [],
      applied: { ucs: [] }, byId: {}, reqEditing: prev ? prev.reqEditing : false };
    const r = (data && data.requirements) || {};
    M.applied.ucs = r.use_cases || [];
    M.applied.cqs = r.competency_questions || [];
    M.appliedReq = { purpose: r.purpose || "", scope: r.scope || "", users: list(r.users).join(", "), no_use_case: r.no_use_case || "" };
    for (const p of (data && data.pending) || []) {
      if (!covers(p)) continue;
      const pl = p.payload || {}, rv = p.review, was = old[p.id];
      if (p.type === "add_use_case") {
        const it = was || { edit_id: p.id, sel: rv ? rv.decision === "accept" : false };
        Object.assign(it, { kind: "uc", payload: pl, src: sourceOf(p), saved: !!rv });
        M.ucs.push(it); M.byId[p.id] = it;
      } else if (p.type === "add_competency_question") {
        const e = (rv && rv.edits) || {};
        const it = was || { edit_id: p.id, dec: rv ? (rv.decision === "accept" ? "ok" : "rej") : null,
          prio: rv && rv.decision === "accept" ? e.priority || "" : "", reason: rv && rv.decision === "reject" ? rv.reason || "" : "",
          why: "", open: false, det: false, editing: false,
          q: String(e.question ?? pl.question ?? ""), type: e.type ?? pl.type ?? "", concepts: list(e.concepts ?? pl.concepts) };
        if (!was && it.reason) { const k = WHY.find(([, l]) => l === it.reason); it.why = k ? k[0] : "outro"; }
        Object.assign(it, { kind: "cq", payload: pl, rationale: p.rationale || "", saved: !!rv });
        M.cqs.push(it); M.byId[p.id] = it;
      } else if (pl.field === "no_use_case") {
        // registro de "sem caso de uso" ja proposto: aparece como a opcao marcada
        // so na primeira vez: se o revisor desfez, um reload nao traz de volta
        if (!M.noUcSeen[p.id]) { M.noUcSeen[p.id] = true; if (!M.noUc) M.noUc = { text: String(pl.value || ""), edit_id: p.id, ok: true }; }
      } else {
        const it = was || { edit_id: p.id, ok: rv ? rv.decision === "accept" : false, editing: false, value: String((rv && rv.edits && rv.edits.value) ?? pl.value ?? "") };
        Object.assign(it, { kind: "req", field: pl.field, proposed: String(pl.value ?? ""), src: sourceOf(p), saved: !!rv });
        M.reqs.push(it); M.byId[p.id] = it;
      }
    }
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
      <button type="button" class="btn" data-e1="cq-new">+ Criar pergunta</button></div>`;
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

  // ---------- tela 1: caso de uso ----------
  function ucCard(u) {
    const pl = u.payload;
    return `<button type="button" class="e1-uc" data-e1="uc" data-id="${esc(u.edit_id)}" aria-pressed="${u.sel}">
      <span class="ck" aria-hidden="true">${u.sel ? "✓" : ""}</span>
      <span class="t">${esc(pl.name)}</span>
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
  function screenUc(M) {
    const cards = M.ucs.map(ucCard).join("") + M.applied.ucs.map(appliedUcCard).join("") + M.owns.map(ownCard).join("") + addTile();
    const reqs = M.reqs.length
      ? `<h3 class="e1-sub">Sobre o projeto</h3>${reqCard(M)}`
      : M.appliedReq.purpose || M.appliedReq.scope
        ? `<h3 class="e1-sub">Sobre o projeto</h3><dl class="kv e1-kv">${REQ_FIELDS.filter((f) => M.appliedReq[f]).map((f) => `<dt>${REQ_LABEL[f]}</dt><dd>${esc(M.appliedReq[f])}</dd>`).join("")}</dl>`
        : "";
    const nada = !M.ucs.length && !M.reqs.length && (chosenUcs(M).length || M.appliedReq.no_use_case)
      ? `<div class="e1-empty"><b>Nada a decidir</b><span>Caso de uso já aprovado.</span></div>` : "";
    return `${nada}<div class="e1-ucgrid">${cards}</div>
      ${noUcBlock(M)}
      ${reqs}`;
  }

  // ---------- telas 2 e 3 (proximas tarefas) ----------
  function screenTodo() {
    return `<div class="e1-empty"><b>Em construção</b><span>Por enquanto, lacunas e divergências ficam em <button type="button" class="lnk" data-e1="outras">Outras propostas</button>.</span></div>`;
  }

  // ---------- render ----------
  function stepperHtml(M) {
    return STEPS.map((s, i) => {
      const cur = i === M.step, done = !cur && i <= 1 && !missing(M, i).length;
      return `<button type="button" class="${cur ? "cur" : done ? "done" : ""}" data-e1="go" data-step="${i}"${cur ? ' aria-current="step"' : ""}>
        <span class="n">${done ? "✓" : i + 1}</span><span class="lbl">${esc(s.title)}</span></button>`;
    }).join("");
  }
  function screenHtml(M) {
    const s = STEPS[M.step];
    const body = M.step === 0 ? screenUc(M) : M.step === 1 ? screenCq(M) : screenTodo();
    return `<p class="e1-lead">${esc(s.lead)}</p>${body}`;
  }
  function footHtml(M) {
    const last = M.step === STEPS.length - 1;
    const next = last ? "Conferir e salvar" : `Próximo: ${STEPS[M.step + 1].title} →`;
    return `<span class="e1-msg" id="e1-msg" role="status" aria-live="polite"></span>
      ${M.step ? '<button type="button" class="btn btn-outline" data-e1="back">← Voltar</button>' : ""}
      <button type="button" class="btn" data-e1="next">${esc(next)}</button>`;
  }
  function render(focusSel) {
    if (!E.el) return;
    const M = E.M;
    E.el.innerHTML = `<div class="e1"><nav class="e1-steps" aria-label="Etapa 1">${stepperHtml(M)}</nav>
      <section class="e1-screen" data-screen="${STEPS[M.step].id}">${screenHtml(M)}</section>
      <div class="e1-foot">${footHtml(M)}</div></div>`;
    if (focusSel) { const t = $(focusSel, E.el); if (t) t.focus({ preventScroll: true }); }
  }
  // depois de digitar: atualiza so o stepper e as marcas de obrigatorio, sem perder o foco
  function refresh(input) {
    const nav = $(".e1-steps", E.el);
    if (nav) nav.innerHTML = stepperHtml(E.M);
    if (input) input.classList.toggle("miss", !input.value.trim());
    const label = input && input.id ? $(`label[for="${input.id}"] .req`, E.el) : null;
    if (label) label.hidden = !!input.value.trim();
    msg("");
  }
  function msg(text, kind) {
    const el = $("#e1-msg", E.el);
    if (!el) return;
    el.className = "e1-msg" + (kind ? " " + kind : "");
    el.innerHTML = text;
  }

  // ---------- eventos ----------
  function goStep(i) {
    E.M.step = Math.max(0, Math.min(STEPS.length - 1, i));
    render();
    const top = $(".e1", E.el);
    if (top) window.scrollTo({ top: Math.max(0, top.getBoundingClientRect().top + window.scrollY - 72), behavior: "smooth" });
  }
  function onNext() {
    const falta = missing(E.M, E.M.step);
    if (falta.length) { msg(`<b>Falta:</b> ${falta.map(esc).join("; ")}`, "warn"); return; }
    if (E.M.step < STEPS.length - 1) { goStep(E.M.step + 1); return; }
    msg("Ainda não grava: o salvar entra com a tela de lacunas e divergências.", "");
  }
  function onClick(e) {
    const b = e.target.closest("[data-e1]");
    if (!b || !E.el.contains(b)) return;
    const M = E.M, act = b.dataset.e1, it = b.dataset.id ? M.byId[b.dataset.id] : null;
    switch (act) {
      case "go": return goStep(Number(b.dataset.step));
      case "back": return goStep(M.step - 1);
      case "next": return onNext();
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
    if (!f || !E.el.contains(el)) return;
    const M = E.M;
    if (f === "nouc") M.noUc.text = el.value;
    else if (f === "cq-q") M.byId[el.dataset.id].q = el.value;
    else if (f === "cq-type") M.byId[el.dataset.id].type = el.value;
    else if (f === "cq-concepts") M.byId[el.dataset.id].concepts = el.value.split(",").map((x) => x.trim()).filter(Boolean);
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

  window.AkmeEtapa1 = { mount, pendingCount, covers };
})();
