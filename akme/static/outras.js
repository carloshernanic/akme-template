// Outras propostas (classes, relacoes, termos, mapeamentos, restricoes, precedencias, fontes e alteracoes)
// no mesmo padrao da etapa 1: card enxuto, decidido vira linha, criar ou alterar em janela central, nome so ao salvar.
// So muda a pagina: as decisoes viram as mesmas chamadas de /api/review, /api/propose e /api/apply.
// O review.js monta este modulo quando o seletor esta em "Outras propostas"; sem ele, volta a caixa antiga.
(function () {
  "use strict";

  // ordem dos grupos: primeiro o que constroi a ontologia (etapas 2 a 5), depois alteracoes de requisitos
  // alteracoes de pergunta, lacuna e divergencia sao da etapa 1 e travam as seguintes: vem primeiro
  const GROUP_ORDER = ["cq", "gap", "div", "uc", "glossary", "class", "relation", "term", "mapping", "constraint", "precedence", "source", "other"];
  const ONTO_GROUPS = new Set(["class", "relation", "term", "mapping", "constraint", "precedence", "source"]);
  const GROUP_LABEL = {
    class: "Classes", relation: "Relações", term: "Termos", mapping: "Mapeamentos", constraint: "Restrições",
    precedence: "Precedências", source: "Exportação Neo4j", cq: "Perguntas de competência", gap: "Lacunas",
    div: "Divergências", uc: "Caso de uso e requisitos", glossary: "Glossário", other: "Outros",
  };
  // motivos de rejeicao: o rotulo vira o reason enviado; "outro" pede texto livre
  const WHY = [["sentido", "Não faz sentido"], ["repetida", "Repetida"], ["escopo", "Fora do escopo"], ["dados", "Os dados não sustentam"], ["outro", "Outro motivo"]];
  const WHY_L = Object.fromEntries(WHY);
  const CQ_TYPES = [
    ["classificacao_hierarquia", "Classificação e hierarquia"], ["relacao_entre_conceitos", "Relação entre conceitos"],
    ["atributos", "Atributos"], ["quantidade_agregacao", "Quantidade e agregação"], ["tempo_estado", "Tempo e estado"],
    ["regras_restricoes", "Regras e restrições"],
  ];
  const TYPE_L = Object.fromEntries(CQ_TYPES);
  const PRIO = [["high", "Alta"], ["medium", "Média"], ["low", "Baixa"]];
  const PRIO_L = Object.fromEntries(PRIO);
  const GAP_OPTS = [["request_from_client", "Pedir o dado ao cliente"], ["reformulate", "Reformular a pergunta"], ["drop", "Descartar"], ["open", "Deixar em aberto"]];
  const DIV_OTHER = [["distinct_terms", "São coisas diferentes"], ["ask_expert", "Perguntar ao especialista"], ["dismiss", "Descartar"], ["open", "Deixar em aberto"]];
  const GAP_L = Object.fromEntries(GAP_OPTS);
  const DIV_L = Object.assign({ precedence: "Precedência" }, Object.fromEntries(DIV_OTHER));
  const STATUS_L = { proposed: "Proposta", approved: "Aprovada", reserved: "Reservada para o teste", rejected: "Rejeitada", deprecated: "Descontinuada" };
  // nomes dos campos na tabela "antes e depois" das alteracoes
  const FIELD_L = { question: "Pergunta", type: "Tipo", concepts: "Conceitos", priority: "Prioridade", status: "Situação", answer: "Resposta esperada",
    decision: "Decisão", note: "Nota", winner: "Fonte que vale", reason: "Motivo", use_cases: "Casos de uso" };
  // campos de texto corrido: aparecem como frase, nao como etiqueta e valor
  const PROSE = new Set(["Comentário", "Definição", "Regra", "Motivo", "Significado", "Descrição", "Valor", "Nota", "Hipótese da IA"]);
  const MULT_SHORT = { "muitos para um": ["n", "1"], "um para muitos": ["1", "n"], "um para um": ["1", "1"], "muitos para muitos": ["n", "n"] };
  const VIEW_ACTS = new Set(["det", "check", "ask"]);

  const O = { el: null, ctx: {}, M: null, wired: null, saving: false, showApplied: false };

  // ---------- utilidades ----------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (sel, el = document) => el.querySelector(sel);
  const list = (v) => (Array.isArray(v) ? v.map(String) : v ? [String(v)] : []);
  const splitList = (s) => String(s || "").split(",").map((x) => x.trim()).filter(Boolean);
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const cut = (s, n) => { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
  const req = (filled, txt) => `<span class="req"${filled ? " hidden" : ""}>${esc(txt || "obrigatório")}</span>`;
  const isAuto = () => document.body.dataset.decisionMode === "auto";
  const E1 = () => window.AkmeEtapa1 || null;
  // tudo o que a etapa 1 nao cobre aparece aqui, para nada sumir
  const covers = (p) => !(E1() && E1().covers(p));
  // tipos por coluna ({coluna: tipo}) viram texto "coluna: tipo, coluna: tipo"; o servidor confere de novo
  function mapText(v) {
    if (v && typeof v === "object" && !Array.isArray(v)) return Object.entries(v).map(([k, t]) => `${k}: ${t}`).join(", ");
    return String(v ?? "").trim();
  }
  function fmt(field, v) {
    if (v === undefined || v === null || v === "") return "—";
    if (Array.isArray(v)) return v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(", ") || "—";
    if (typeof v === "object") return JSON.stringify(v);
    if (field === "type") return TYPE_L[v] || v;
    if (field === "priority") return PRIO_L[v] || v;
    if (field === "status") return STATUS_L[v] || v;
    if (field === "decision") return GAP_L[v] || DIV_L[v] || v;
    return String(v);
  }
  // view de reserva para dados exportados por versoes antigas (sem bloco view)
  function viewOf(p) {
    if (p.view) return p.view;
    const pl = p.payload || {};
    return { title: pl.name || pl.question || pl.topic || pl.id || p.id, subtitle: "", group: "other", fields: [], evidence: [],
      observed: null, alerts: [], editable: [], rejectable: true, requirement_id: p.requirement_id || "", rationale: p.rationale || "" };
  }
  const stepText = (t) => (window.AkmeChannel ? window.AkmeChannel.step(t) : t || "");
  const originLow = (by) => (!by || by === "agent" || by === "IA" ? "proposta pela IA" : "proposta por " + by);

  // ---------- modelo ----------
  // valores editaveis: o que o revisor ja ajustou (review.edits) ou o que a IA propos
  function editVals(p) {
    const pl = p.payload || {}, e = (p.review && p.review.edits) || {}, out = {};
    (viewOf(p).editable || []).forEach((f) => {
      const v = e[f.key] !== undefined ? e[f.key] : pl[f.key];
      out[f.key] = f.kind === "list" ? list(v).join(", ") : f.kind === "map" ? mapText(v) : String(v ?? "");
    });
    return out;
  }
  // prev guarda o que o revisor ja decidiu nesta sessao; um reload do servidor nao apaga as escolhas
  // decisoes feitas e ainda nao salvas ficam num rascunho deste navegador: recarregar a pagina nao as apaga
  const DRAFT_SKIP = new Set(["p", "v", "saved", "open", "det", "editing"]);
  const draftKey = (project) => "akme-draft-outras:" + (project || "");
  function readDraft(project) {
    try { return JSON.parse(localStorage.getItem(draftKey(project)) || "null") || {}; } catch (e) { return {}; }
  }
  function writeDraft(M) {
    if (!M || isAuto()) return;
    const items = {};
    M.items.forEach((it) => {
      if (it.saved || (!it.dec && !Object.keys(diffOf(it)).length)) return;
      const o = {};
      Object.keys(it).forEach((k) => { if (!DRAFT_SKIP.has(k)) o[k] = it[k]; });
      items[it.id] = o;
    });
    try {
      if (Object.keys(items).length || M.own.length) localStorage.setItem(draftKey(M.project), JSON.stringify({ items, own: M.own }));
      else localStorage.removeItem(draftKey(M.project));
    } catch (e) { /* sem armazenamento: o rascunho fica so na memoria */ }
  }
  function buildModel(data, prev) {
    const old = (prev && prev.byId) || {};
    const project = (data && data.project) || "";
    // primeira montagem (pagina recem-aberta): recupera o rascunho; depois, o modelo anterior manda
    const draft = prev ? {} : readDraft(project), dItems = draft.items || {};
    const M = { items: [], byId: {}, own: prev ? prev.own : Array.isArray(draft.own) ? draft.own : [], apOpen: prev ? prev.apOpen : false, ctxOpen: prev ? prev.ctxOpen : false, project };
    M.req = (data && data.requirements) || {};
    M.stage = (data && data.stage) || {};
    for (const p of (data && data.pending) || []) {
      if (!covers(p)) continue;
      const rv = p.review, was = old[p.id];
      const fromDraft = !was && !rv && dItems[p.id] ? Object.assign({ open: false, det: false, editing: false }, dItems[p.id], { id: p.id }) : null;
      const it = was || fromDraft || { id: p.id, dec: rv ? (rv.decision === "reject" ? "rej" : "ok") : null, why: "",
        reason: rv && rv.decision === "reject" ? rv.reason || "" : "", open: false, det: false, editing: false, vals: editVals(p) };
      if (!was && !fromDraft && it.reason) { const k = WHY.find(([, l]) => l === it.reason); it.why = k ? k[0] : "outro"; }
      Object.assign(it, { p, v: viewOf(p), saved: !!rv });
      M.items.push(it); M.byId[p.id] = it;
    }
    const gi = (it) => { const i = GROUP_ORDER.indexOf(it.v.group); return i < 0 ? GROUP_ORDER.length : i; };
    // dentro do grupo, na ordem em que a IA propos: proposta nova entra no fim, nao acima do que se esta decidindo
    const at = (it) => String(it.p.created_at || "");
    M.items.sort((a, b) => gi(a) - gi(b) || at(a).localeCompare(at(b)));
    if (O.showApplied) { M.apOpen = true; O.showApplied = false; }
    return M;
  }
  const reasonOf = (it) => (it.why && it.why !== "outro" ? WHY_L[it.why] : it.reason.trim());
  const done = (it) => it.dec === "ok" || (it.dec === "rej" && !!reasonOf(it));
  // o que o revisor mudou no texto, no formato que /api/review espera
  function diffOf(it) {
    const pl = it.p.payload || {}, out = {};
    (it.v.editable || []).forEach((f) => {
      const cur = String(it.vals[f.key] ?? "").trim();
      // compara com o original normalizado do mesmo jeito: trim() do JS tira espacos e o BOM (﻿),
      // e sem isso um campo intocado parecia "ajustado" e ia para o servidor diferente do proposto
      if (f.kind === "list") { const l = splitList(cur); if (JSON.stringify(l) !== JSON.stringify(splitList(list(pl[f.key]).join(",")))) out[f.key] = l; }
      else if (f.kind === "map") { if (cur !== mapText(pl[f.key])) out[f.key] = cur; }
      else if (cur !== String(pl[f.key] ?? "").trim()) out[f.key] = cur;
    });
    return out;
  }
  // campos que o servidor exige preenchidos; os opcionais (convencao, nota, tipos) podem ficar vazios
  const REQUIRED_TEXT = new Set(["label", "comment", "definition", "rule", "reason", "meaning", "value", "name", "description"]);
  const emptied = (it) => Object.entries(diffOf(it)).some(([k, v]) => REQUIRED_TEXT.has(k) && !Array.isArray(v) && !v);
  function missing(M) {
    const m = [];
    const und = M.items.filter((it) => !it.dec).length;
    const nr = M.items.filter((it) => it.dec === "rej" && !reasonOf(it)).length;
    const ne = M.items.filter((it) => it.dec === "ok" && emptied(it)).length;
    if (und) m.push("decidir " + plural(und, "proposta", "propostas"));
    if (nr) m.push("motivo de " + plural(nr, "rejeição", "rejeições"));
    if (ne) m.push(plural(ne, "texto ajustado está vazio", "textos ajustados estão vazios"));
    return m;
  }
  // decididas aqui mas ainda nao gravadas no servidor (e perguntas/alteracoes escritas pelo revisor)
  const unsavedOf = (M) => M.items.filter((it) => done(it) && !it.saved).length + M.own.length;
  // o numero da aba so cai depois de salvar: decidir sem salvar nao muda nada na ontologia
  const remainingOf = (M) => M.items.filter((it) => !done(it)).length + unsavedOf(M);
  function pendingCount(data) {
    return ((data && data.pending) || []).filter(covers).length;
  }
  // quanto falta decidir: alimenta o numero do seletor "Outras propostas" e o da aba Revisao
  function remaining(data) {
    if (data) O.M = buildModel(data, O.M);
    return O.M ? remainingOf(O.M) : pendingCount(data);
  }

  // ---------- pecas do card ----------
  const labelOf = (it) => {
    const pl = it.p.payload || {};
    return ("label" in it.vals ? it.vals.label.trim() : "") || pl.label || pl.name || "";
  };
  function titleText(it) {
    const pl = it.p.payload || {}, t = it.p.type;
    if (t === "add_class" || t === "add_relation") return labelOf(it) || it.v.title;
    if (t === "add_term") return `${pl.name} (termo de ${pl.class})`;
    if (t === "add_mapping") return `${pl.term} → ${pl.source}.${pl.column}`;
    return it.v.title;
  }
  function titleHtml(it) {
    const pl = it.p.payload || {}, t = it.p.type, v = it.v;
    if (t === "add_class" || t === "add_relation") {
      const lab = labelOf(it);
      return `${esc(lab || v.title)}${pl.name && lab && lab !== pl.name ? ` <span class="ou-ident mono">${esc(pl.name)}</span>` : ""}`;
    }
    if (t === "add_term") return `<span class="mono">${esc(pl.name)}</span> <span class="ou-ident">termo de ${esc(pl.class)}</span>`;
    if (t === "add_mapping") return `<span class="mono">${esc(pl.term)}</span> <span class="ou-ident">→ ${esc(pl.source)}.${esc(pl.column)}</span>`;
    if (/^(update|remove)_/.test(t)) return esc(v.title);
    return `${esc(v.title)}${v.subtitle ? ` <span class="ou-ident">${esc(v.subtitle)}</span>` : ""}`;
  }
  // etiqueta curta para alteracao ou exclusao de algo ja aplicado
  function kindTag(it) {
    const t = it.p.type, id = (it.p.payload || {}).id || "";
    if (t === "update_competency_question") return `alteração da pergunta ${id}`;
    if (t === "remove_competency_question") return `exclusão da pergunta ${id}`;
    if (t === "update_gap") return `alteração da lacuna ${id}`;
    if (t === "update_divergence") return `alteração da divergência ${id}`;
    return "";
  }
  function srcLine(it) {
    const evs = it.v.evidence || [];
    const ev = evs.find((e) => e.path);
    if (ev) return `<span class="mono">${esc(ev.path + (ev.locator ? " · " + ev.locator : ""))}</span>`;
    const c = evs.find((e) => e.kind === "conversation");
    if (c) return `<span>conversa${c.who ? " com " + esc(c.who) : ""}${c.note ? ": " + esc(cut(c.note, 80)) : ""}</span>`;
    const n = evs.find((e) => e.note);
    if (n) return `<span>${esc(cut(n.note, 100))}</span>`;
    return '<span class="warn">sem evidência de fonte</span>';
  }
  function relDiagram(it) {
    const pl = it.p.payload || {};
    const mf = (it.v.fields || []).find((f) => f.label === "Multiplicidade"), mult = mf ? mf.value : "";
    const [a, b] = MULT_SHORT[mult] || ["", ""], lab = labelOf(it) || pl.name || "";
    return `<div class="rel-diagram" aria-label="${esc(pl.domain)} ${esc(lab)} ${esc(pl.range)}">
      <span class="node">${esc(pl.domain)}</span>
      <span class="arrow"><span class="lbl">${esc(lab)}</span><span class="line"><i class="m">${esc(a)}</i><i class="shaft"></i><i class="m">${esc(b)}</i></span><span class="mult">${esc(mult)}</span></span>
      <span class="node">${esc(pl.range)}</span></div>`;
  }
  function diffTable(cur, pl) {
    const ks = Object.keys(pl || {}).filter((k) => k !== "id" && k !== "evidence");
    if (!ks.length) return "";
    return `<div class="ou-diff"><table class="diff"><thead><tr><th>campo</th><th>antes</th><th>depois</th></tr></thead><tbody>${ks.map((k) =>
      `<tr><td>${esc(FIELD_L[k] || k)}</td><td class="secondary">${esc(fmt(k, cur ? cur[k] : undefined))}</td><td>${esc(fmt(k, pl[k]))}</td></tr>`).join("")}</tbody></table></div>`;
  }
  // o essencial fica sempre a vista: o desenho da relacao, o antes e depois ou a frase principal
  function gist(it) {
    const t = it.p.type, pl = it.p.payload || {};
    if (t === "add_relation") return relDiagram(it);
    if (/^update_/.test(t)) return diffTable(it.p.current, pl);
    if (t === "remove_competency_question") return `<p class="ou-gist"><b>Motivo da exclusão:</b> ${esc(pl.reason || "—")}</p>`;
    const f = (it.v.fields || []).find((x) => PROSE.has(x.label));
    if (!f) return "";
    const ed = (it.v.editable || []).find((e) => e.label === f.label);
    const val = ed ? it.vals[ed.key] : f.value;
    return val ? `<p class="ou-gist">${esc(val)}</p>` : "";
  }
  function evList(it) {
    return (it.v.evidence || []).map((ev) => {
      if (ev.kind === "conversation") return `<div class="ev">conversa${ev.who ? " com " + esc(ev.who) : ""}${ev.note ? ": " + esc(ev.note) : ""}</div>`;
      if (!ev.path) return ev.note ? `<div class="ev">${esc(ev.note)}</div>` : "";
      const check = O.ctx.api && ev.quote
        ? ` <button type="button" class="check" data-o="check" data-q="${esc(ev.quote)}">conferir</button><span class="checked" aria-live="polite"></span>` : "";
      return `<div class="ev"><span class="path">${esc(ev.path)}${ev.locator ? " · " + esc(ev.locator) : ""}</span>${ev.quote ? `<span class="quote">“${esc(ev.quote)}”${check}</span>` : ""}</div>`;
    }).join("");
  }
  function editFields(it) {
    const id = esc(it.id);
    return `<div class="ou-edit">${(it.v.editable || []).map((f) => {
      const fid = `ou-f-${id}-${esc(f.key)}`, val = it.vals[f.key] ?? "", miss = !val.trim() && REQUIRED_TEXT.has(f.key) ? " miss" : "";
      const ctl = f.kind === "textarea" || f.kind === "map"
        ? `<textarea id="${fid}" class="textarea${miss}" rows="${f.kind === "map" ? 2 : 3}" data-of="val" data-id="${id}" data-k="${esc(f.key)}">${esc(val)}</textarea>`
        : `<input id="${fid}" class="input${miss}" type="text" data-of="val" data-id="${id}" data-k="${esc(f.key)}" value="${esc(val)}">`;
      return `<div class="field"><label class="field-label" for="${fid}">${esc(f.label)}</label>${ctl}</div>`;
    }).join("")}</div>`;
  }
  function details(it) {
    const v = it.v, id = esc(it.id), t = it.p.type;
    const eyebrow = [GROUP_LABEL[v.group] || v.group_label || "Proposta", originLow(it.p.proposed_by), it.p.requirement_id ? "motivada por " + it.p.requirement_id : ""].filter(Boolean);
    // o que ja aparece no card (titulo, desenho, frase principal) nao se repete aqui
    const shown = new Set(["Rótulo"]);
    if (t === "add_relation") shown.add("Multiplicidade");
    const gistField = (v.fields || []).find((x) => PROSE.has(x.label));
    if (gistField && t !== "add_relation") shown.add(gistField.label);
    const meta = /^(update|remove)_/.test(t) ? [] : (v.fields || []).filter((f) => !shown.has(f.label) && !(it.editing && (v.editable || []).some((e) => e.label === f.label)));
    const metaHtml = meta.length ? `<dl class="meta">${meta.map((f) => `<div><dt>${esc(f.label)}</dt><dd${f.mono ? ' class="mono"' : ""}>${esc(f.value)}</dd></div>`).join("")}</dl>` : "";
    const obs = v.observed ? `<div><p class="field-label">O que o dado mostra</p><ul class="obs">${(v.observed.available ? v.observed.lines : [`Não foi possível ler o dado: ${v.observed.reason}`]).map((l) => `<li>${esc(l)}</li>`).join("")}</ul></div>` : "";
    const canEdit = (v.editable || []).length && it.dec !== "rej" && !isAuto();
    return `<div class="cq-det" id="ou-det-${id}">
      <p class="eyebrow">${eyebrow.map(esc).join(" · ")}</p>
      ${it.editing ? editFields(it) : ""}${metaHtml}${evList(it)}${obs}
      ${v.rationale ? `<p class="p secondary"><b>Justificativa da IA:</b> ${esc(v.rationale)}</p>` : ""}
      ${canEdit ? `<div><button type="button" class="lnk" data-o="edit" data-id="${id}">${it.editing ? "pronto" : "ajustar texto"}</button></div>` : ""}</div>`;
  }
  // "Situação: Aprovada → Reservada para o teste": o que a alteracao muda, sem abrir o cartao
  function changeText(it) {
    if (!/^update_/.test(it.p.type)) return "";
    const pl = it.p.payload || {}, cur = it.p.current || {};
    return Object.keys(pl).filter((k) => k !== "id" && k !== "evidence")
      .map((k) => `${FIELD_L[k] || k}: ${cut(fmt(k, cur[k]), 50)} → ${cut(fmt(k, pl[k]), 70)}`).join("; ");
  }
  function line(it) {
    const ok = it.dec === "ok", adj = ok && Object.keys(diffOf(it)).length, tag = kindTag(it), chg = changeText(it);
    return `<div class="e1-line ${ok ? "ok" : "rej"}" data-ou="${esc(it.id)}"><span class="i" aria-hidden="true">${ok ? "✓" : "✕"}</span>
      <span class="q">${tag ? `<span class="ou-tag">${esc(tag)}</span> ` : ""}${esc(titleText(it))}${chg ? `<span class="ou-chg">${esc(chg)}</span>` : ""}</span><span class="m">${esc(ok ? (adj ? "aceita com ajuste" : "aceita") : reasonOf(it))}</span>
      <button type="button" class="lnk" data-o="open" data-id="${esc(it.id)}" aria-label="Rever: ${esc(titleText(it))}">rever</button></div>`;
  }
  function card(it) {
    if (done(it) && !it.open) return line(it);
    const id = esc(it.id), v = it.v, tag = kindTag(it), adj = Object.keys(diffOf(it)).length;
    const off = isAuto() ? " disabled" : "";
    const big = (val, label, cls) => `<button type="button" class="${cls}" data-o="dec" data-id="${id}" data-v="${val}" aria-pressed="${it.dec === val}"${off}>${label}</button>`;
    let after = "";
    if (it.dec === "rej") {
      after = `<div class="choice"><span class="field-label">Por que rejeitar? ${req(it.why)}</span>
        <div class="why" role="group" aria-label="Motivo da rejeição">${WHY.map(([k, l]) => `<button type="button" data-o="why" data-id="${id}" data-v="${k}" aria-pressed="${it.why === k}">${esc(l)}</button>`).join("")}</div></div>
        ${it.why === "outro" ? `<div class="field"><label class="field-label" for="ou-r-${id}">Qual o motivo? ${req(it.reason.trim())}</label><textarea id="ou-r-${id}" class="textarea" rows="2" data-of="reason" data-id="${id}">${esc(it.reason)}</textarea></div>` : ""}`;
    }
    const close = done(it) ? `<div><button type="button" class="btn btn-outline btn-sm" data-o="close" data-id="${id}">recolher</button></div>` : "";
    const alerts = (v.alerts || []).map((a) => `<p class="ou-alert">Conferir antes de aceitar: ${esc(a)}</p>`).join("");
    return `<article class="rv-card cq-lean${it.dec === "ok" ? " st-ok" : it.dec === "rej" ? " st-rej" : ""}" data-ou="${id}">
      <div class="cq-body">
        <h3 class="cq-q">${titleHtml(it)}</h3>
        <div class="cq-sig">${tag ? `<span class="ou-tag">${esc(tag)}</span>` : ""}${srcLine(it)}
          <button type="button" class="lnk" data-o="det" data-id="${id}" aria-expanded="${it.det}" aria-controls="ou-det-${id}">${it.det ? "esconder detalhes" : "ver detalhes"}</button>
          ${askBtn(it)}${adj ? '<span class="mark">ajustada por você</span>' : ""}</div>
        ${gist(it)}${alerts}
        ${it.det ? details(it) : ""}
      </div>
      <div class="cq-decide"><div class="big">${big("ok", "✓ Aceitar", "bok")}${v.rejectable !== false ? big("rej", "✕ Rejeitar", "brej") : ""}</div>${after}${close}</div></article>`;
  }

  // abre a Conversa com o item citado, para a resposta do agente ficar ligada a ele
  const askRef = (it) => { const pl = it.p.payload || {}; return pl.id || pl.name || pl.source || it.id; };
  function askBtn(it) {
    const ch = window.AkmeChannel;
    return ch && ch.available() && !isAuto() ? `<button type="button" class="lnk" data-o="ask" data-id="${esc(it.id)}">Comentar com a IA</button>` : "";
  }

  // ---------- alteracoes do revisor (perguntas, lacunas e divergencias ja aplicadas, pergunta nova) ----------
  const ownText = (o) => (o.kind === "ncq" ? o.q : o.label);
  function ownSummary(o) {
    if (o.kind === "ncq") return `pergunta nova · ${PRIO_L[o.prio]}`;
    if (o.kind === "acq") return "alterar " + Object.keys(o.diff).map((k) => (FIELD_L[k] || k).toLowerCase()).join(", ");
    if (o.kind === "rcq") return "excluir: " + o.reason;
    if (o.kind === "agap") return GAP_L[o.decision] + (o.note ? ": " + o.note : "");
    if (o.kind === "adiv") return (o.decision === "precedence" ? `Vale ${o.winner}` : DIV_L[o.decision]) + (o.reason ? ": " + o.reason : "");
    return "";
  }
  function ownLine(o, i) {
    return `<div class="e1-line own"><span class="i" aria-hidden="true">✎</span><span class="q">${esc(ownText(o))} <span class="e1-seu">sua</span></span>
      <span class="m">${esc(cut(ownSummary(o), 80))}</span>
      ${isAuto() ? "" : `<button type="button" class="lnk" data-o="own-edit" data-i="${i}">editar</button><button type="button" class="lnk" data-o="own-del" data-i="${i}">remover</button>`}</div>`;
  }
  // ja ha uma alteracao (pendente no servidor ou feita aqui) para este item aplicado?
  function busyFor(M, id) {
    if (M.own.some((o) => o.id === id)) return "alteração sua acima";
    if (M.items.some((it) => /^(update|remove)_/.test(it.p.type) && (it.p.payload || {}).id === id)) return "alteração pendente acima";
    return "";
  }
  function appliedSection(M) {
    const r = M.req, cqs = r.competency_questions || [], gaps = r.gaps || [], divs = r.divergences || [];
    const total = cqs.length + gaps.length + divs.length;
    if (!total) return "";
    const can = !isAuto() && !!O.ctx.api;
    const acts = (id, btns) => { const b = busyFor(M, id); return b ? `<span class="m">${esc(b)}</span>` : can ? `<span class="ou-ap-acts">${btns}</span>` : ""; };
    // linha de item aplicado: cartao com fundo e texto forte, para ler e revisar
    const row = (txt, meta, btns, id) => `<div class="e1-line ok ou-ap"><span class="i" aria-hidden="true">✓</span><span class="q">${esc(txt)}</span>${meta ? `<span class="ou-ap-meta">${esc(meta)}</span>` : ""}${acts(id, btns)}</div>`;
    const bt = (o, id, label) => `<button type="button" class="btn btn-outline ou-ap-btn" data-o="${o}" data-ref="${esc(id)}">${label}</button>`;
    const cqRows = cqs.map((q) => row(q.question, [PRIO_L[q.priority] ? "Prioridade " + PRIO_L[q.priority].toLowerCase() : "", q.status && q.status !== "approved" ? STATUS_L[q.status] || q.status : ""].filter(Boolean).join(" · "),
      bt("acq", q.id, "Alterar") + bt("rcq", q.id, "Excluir"), q.id)).join("");
    const gapRows = gaps.map((g) => row(g.question, GAP_L[g.decision] || g.decision || "", bt("agap", g.id, "Alterar"), g.id)).join("");
    const divRows = divs.map((d) => row(d.topic, d.decision === "precedence" ? `Vale ${d.winner || "?"}` : DIV_L[d.decision] || d.decision || "", bt("adiv", d.id, "Alterar"), d.id)).join("");
    return `<details class="e1-more ou-ap-wrap" data-od="ap"${M.apOpen ? " open" : ""}><summary><b>Já aplicadas</b> <span class="ou-ap-n">${total}</span><span class="ou-ap-hint">${esc([plural(cqs.length, "pergunta", "perguntas"), plural(gaps.length, "lacuna", "lacunas"), plural(divs.length, "divergência", "divergências")].join(" · "))}; dá para alterar cada uma</span></summary>
      ${cqRows ? `<h3 class="e1-sub">Perguntas</h3>${cqRows}` : ""}${gapRows ? `<h3 class="e1-sub">Lacunas</h3>${gapRows}` : ""}${divRows ? `<h3 class="e1-sub">Divergências</h3>${divRows}` : ""}
      <p class="p secondary">A alteração vira uma proposta sua e entra junto quando você salvar.</p></details>`;
  }
  function sourcesRead(M) {
    const counts = new Map(), add = (path) => { if (path) counts.set(path, (counts.get(path) || 0) + 1); };
    const r = M.req;
    const fromItem = (it) => {
      (Array.isArray(it.evidence) ? it.evidence : []).forEach((e) => e && e.kind !== "conversation" && add(e.path));
      (Array.isArray(it.sources) ? it.sources : []).forEach((s) => s && add(s.path));
    };
    [].concat(r.competency_questions || [], r.gaps || [], r.divergences || []).forEach(fromItem);
    M.items.forEach((it) => (it.v.evidence || []).forEach((e) => e.kind === "source" && add(e.path)));
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }
  function contextSection(M) {
    const r = M.req, ucs = r.use_cases || [], srcs = sourcesRead(M);
    const R = { purpose: r.purpose || "", scope: r.scope || "", users: list(r.users).join(", ") };
    const E1 = window.AkmeEtapa1;
    // mesmo cartao de "Sobre o projeto" da etapa 1; sem o modulo, a lista simples
    const about = !(R.purpose || R.scope || R.users) ? ""
      : E1 && E1.aboutCard ? E1.aboutCard(R)
      : `<dl class="kv e1-kv">${[["Propósito", R.purpose], ["Escopo", R.scope], ["Usuários", R.users]].filter(([, x]) => x).map(([k, x]) => `<dt>${k}</dt><dd>${esc(x)}</dd>`).join("")}</dl>`;
    const ucHtml = ucs.length
      ? ucs.map((u) => `<article class="ou-uc"><div class="ou-uc-h"><b>${esc(u.name)}</b><span class="ou-ap-meta mono">${esc(u.id)}</span></div>${u.description ? `<p>${esc(u.description)}</p>` : ""}</article>`).join("")
      : `<article class="ou-uc"><p>${r.no_use_case ? "Sem caso de uso: " + esc(r.no_use_case) : "Nenhum caso de uso registrado."}</p></article>`;
    const srcHtml = srcs.length
      ? `<ul class="ou-src">${srcs.map(([p, n]) => { const i = p.lastIndexOf("/"); return `<li><span class="ou-src-f"><b class="mono">${esc(p.slice(i + 1))}</b>${i > 0 ? `<span class="mono">${esc(p.slice(0, i + 1))}</span>` : ""}</span><span class="ou-ap-meta">${plural(n, "citação", "citações")}</span></li>`; }).join("")}</ul>`
      : '<ul class="ou-src"><li><span class="ou-src-f">Nenhuma fonte citada ainda.</span></li></ul>';
    return `<details class="e1-more ou-ap-wrap" data-od="ctx"${M.ctxOpen ? " open" : ""}><summary><b>Caso de uso e fontes</b><span class="ou-ap-hint">${esc([ucs.length ? ucs.map((u) => u.name).join(", ") : r.no_use_case ? "sem caso de uso" : "nenhum caso de uso", plural(srcs.length, "fonte citada", "fontes citadas")].join(" · "))}</span></summary>
      <h3 class="e1-sub">Caso de uso</h3>${ucHtml}
      ${about ? `<h3 class="e1-sub">Sobre o projeto</h3>${about}` : ""}
      <h3 class="e1-sub">Fontes citadas <span class="ou-n">${srcs.length}</span></h3>${srcHtml}</details>`;
  }

  // ---------- render ----------
  function groupKeys(M) {
    return GROUP_ORDER.concat(Array.from(new Set(M.items.map((it) => it.v.group))).filter((g) => !GROUP_ORDER.includes(g)));
  }
  function screenHtml(M) {
    const auto = isAuto(), und = M.items.filter((it) => !it.dec).length, can = !auto && !!O.ctx.api, ns = unsavedOf(M);
    const bar = `<div class="e1-cqbar"><span class="e1-count">${und ? `<b>${und}</b> ${und === 1 ? "proposta para avaliar" : "propostas para avaliar"}` : M.items.length ? "Todas decididas" : "Nada pendente da IA"}</span>
      <span class="e1-cqbar-a">${und && can ? `<button type="button" class="btn btn-outline" data-o="all" title="Aceita as ${und} propostas ainda sem decisão, como a IA propôs. Dá para rever cada uma antes de salvar.">✓ Aceitar tudo (${und})</button>` : ""}
      ${can ? '<button type="button" class="btn btn-outline" data-o="ncq">+ Nova pergunta</button>' : ""}</span></div>`;
    const groups = groupKeys(M).map((g) => {
      const its = M.items.filter((it) => it.v.group === g);
      return its.length ? `<h3 class="e1-sub">${esc(GROUP_LABEL[g] || g)} <span class="ou-n">${its.length}</span></h3><div class="e1-cqs">${its.map(card).join("")}</div>` : "";
    }).join("");
    const own = M.own.length ? `<h3 class="e1-sub">Suas alterações <span class="ou-n">${M.own.length}</span></h3><div class="e1-cqs">${M.own.map(ownLine).join("")}</div>` : "";
    const st = M.stage || {};
    const nada = !M.items.length && !M.own.length
      ? `<div class="e1-empty"><b>Nada a decidir</b><span>${esc([st.label, stepText(st.next_step)].filter(Boolean).join(". ") || "Quando o agente propuser algo, aparece aqui.")}</span></div>` : "";
    const aviso = ns && can ? `<div class="unsaved" role="status"><span><b>${plural(ns, "decisão ainda não salva", "decisões ainda não salvas")}.</b> Só entram na ontologia depois de conferir e salvar.</span>
      <button type="button" class="btn" data-o="save">Conferir e salvar</button></div>` : "";
    return `${bar}${aviso}${nada}${groups}${own}${appliedSection(M)}${contextSection(M)}`;
  }
  function render(focusSel) {
    if (!O.el || !O.M) return;
    const M = O.M, auto = isAuto(), any = M.items.length || M.own.length;
    O.el.innerHTML = `<div class="e1 ou${auto ? " is-auto" : ""}">${auto ? '<p class="e1-auto">Modo automático: a IA decide e aplica. Aqui você acompanha.</p>' : ""}
      <p class="e1-lead">${M.items.length ? "Aceite ou rejeite cada proposta da IA. No fim, confira e salve." : "As propostas das etapas 2 a 5 aparecem aqui."}</p>
      <section class="e1-screen" data-screen="outras">${screenHtml(M)}</section>
      ${any && !auto ? `<div class="e1-foot"><span class="e1-msg" id="ou-msg" role="status" aria-live="polite"></span><button type="button" class="btn" data-o="save">Conferir e salvar</button></div>` : ""}</div>`;
    if (focusSel) { const t = $(focusSel, O.el); if (t) t.focus({ preventScroll: true }); }
    writeDraft(M);
    if (O.ctx.onCount) O.ctx.onCount(remainingOf(M));
  }
  function msg(text, kind) {
    const el = O.el && $("#ou-msg", O.el);
    if (!el) return;
    el.className = "e1-msg" + (kind ? " " + kind : "");
    el.innerHTML = text;
  }
  // depois de decidir um card, o foco vai para o proximo que ainda espera decisao
  function focusAfter(id) {
    const it = O.M.byId[id];
    if (!it || !done(it) || it.open) return null;
    const next = O.M.items.find((x) => !done(x) && x.id !== id);
    return next ? `[data-o="dec"][data-id="${next.id}"][data-v="ok"]` : `[data-o="open"][data-id="${id}"]`;
  }

  // ---------- eventos ----------
  function onClick(e) {
    const b = e.target.closest("[data-o]");
    if (!b || !O.el.contains(b) || b.disabled || !O.M) return;
    const M = O.M, act = b.dataset.o, id = b.dataset.id, it = id ? M.byId[id] : null;
    if (isAuto() && !VIEW_ACTS.has(act)) return;
    if (id && !it) return;
    switch (act) {
      case "det": it.det = !it.det; return render(`[data-o="det"][data-id="${id}"]`);
      case "check": return checkQuote(b);
      case "ask": return window.AkmeChannel && window.AkmeChannel.ask(`[${askRef(it)}] `);
      case "dec": {
        it.dec = b.dataset.v;
        if (it.dec === "ok") { it.open = false; return render(focusAfter(id)); }
        it.editing = false; it.open = true;
        return render(`[data-o="why"][data-id="${id}"]`);
      }
      case "why": {
        it.why = b.dataset.v;
        if (it.why === "outro") { if (WHY.some(([, l]) => l === it.reason)) it.reason = ""; return render(`#ou-r-${id}`); }
        it.reason = WHY_L[it.why]; it.open = false; return render(focusAfter(id));
      }
      case "close": if (!done(it)) return; it.open = false; return render(focusAfter(id));
      case "open": it.open = true; return render(`[data-o="dec"][data-id="${id}"][data-v="${it.dec}"]`);
      case "edit": {
        it.editing = !it.editing; it.det = true;
        if (it.editing && it.dec === "rej") { it.dec = null; it.why = ""; it.reason = ""; }
        return render(it.editing ? `[data-of="val"][data-id="${id}"]` : `[data-o="edit"][data-id="${id}"]`);
      }
      case "all": M.items.forEach((x) => { if (!x.dec) { x.dec = "ok"; x.open = false; } }); return render('[data-o="save"]');
      case "save": return onSave();
      case "ncq": return openDlg("ncq", { from: '[data-o="ncq"]' });
      case "acq": case "rcq": case "agap": case "adiv": return openDlg(act, { ref: b.dataset.ref, from: `[data-o="${act}"][data-ref="${b.dataset.ref}"]` });
      case "own-edit": { const i = Number(b.dataset.i), o = M.own[i]; if (o) openDlg(o.kind, { i, ref: o.id, from: `[data-o="own-edit"][data-i="${i}"]` }); return; }
      case "own-del": M.own.splice(Number(b.dataset.i), 1); return render('[data-o="save"]');
    }
  }
  function onInput(e) {
    const el = e.target, f = el.dataset && el.dataset.of;
    if (!f || !O.el.contains(el) || isAuto() || !O.M) return;
    const it = O.M.byId[el.dataset.id];
    if (!it) return;
    if (f === "val") {
      it.vals[el.dataset.k] = el.value;
      el.classList.toggle("miss", !el.value.trim() && REQUIRED_TEXT.has(el.dataset.k));
    } else if (f === "reason") {
      const was = done(it);
      it.reason = el.value;
      const lab = $(`label[for="${el.id}"] .req`, O.el); if (lab) lab.hidden = !!el.value.trim();
      if (was !== done(it)) { const pos = el.selectionStart; render(); const t = $(`#${el.id}`, O.el); if (t) { t.focus(); t.setSelectionRange(pos, pos); } return; }
    }
    msg("");
    writeDraft(O.M);
    if (O.ctx.onCount) O.ctx.onCount(remainingOf(O.M));
  }
  // details nao borbulha o toggle: escuta na captura para lembrar o que ficou aberto entre um reload e outro
  function onToggle(e) {
    const d = e.target;
    if (!d || !d.dataset || !d.dataset.od || !O.M) return;
    if (d.dataset.od === "ap") O.M.apOpen = d.open;
    if (d.dataset.od === "ctx") O.M.ctxOpen = d.open;
  }
  async function checkQuote(b) {
    const out = b.nextElementSibling, q = b.dataset.q || "", api = O.ctx.api;
    if (!api || !out) return;
    out.textContent = " conferindo…";
    try {
      const res = await api.get("/api/sources?q=" + encodeURIComponent(q) + "&case_sensitive=false");
      const n = (res.documents || []).length + (res.tables || []).length;
      out.textContent = res.found ? ` encontrada (${plural(n, "trecho", "trechos")})` : " não encontrada nas fontes";
    } catch (err) { out.textContent = " erro: " + err.message; }
  }

  // ---------- janela de criar ou alterar: centro da tela, fundo desfocado, fecha so ao confirmar ou cancelar ----------
  const D = { kind: null, i: null, ref: null, from: null, prio: "", choice: "" };
  const d0 = (sel) => document.querySelector("#ou-dlg " + sel);
  function dlgEl() {
    let d = document.getElementById("ou-dlg");
    if (d) return d;
    d = document.createElement("dialog");
    d.id = "ou-dlg"; d.className = "dlg e1-dlg"; d.setAttribute("aria-labelledby", "ou-dlg-t");
    document.body.appendChild(d);
    d.addEventListener("submit", (e) => { e.preventDefault(); dlgSubmit(); });
    // Esc fecha como cancelar; clicar fora nao fecha
    d.addEventListener("cancel", (e) => { e.preventDefault(); closeDlg(); });
    d.addEventListener("click", (e) => {
      const b = e.target.closest("[data-d], [data-p], [data-c]");
      if (!b) return;
      if (b.dataset.d === "cancel") { closeDlg(); return; }
      if (b.dataset.p) { D.prio = b.dataset.p; d.querySelectorAll("[data-p]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.p === D.prio))); }
      if (b.dataset.c) { D.choice = b.dataset.c; d.querySelectorAll("[data-c]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.c === D.choice))); }
      syncDlg();
    });
    d.addEventListener("input", () => syncDlg());
    d.addEventListener("change", () => syncDlg());
    return d;
  }
  // etiquetas "obrigatorio" somem quando o campo e preenchido
  function syncDlg() {
    const d = document.getElementById("ou-dlg");
    if (!d) return;
    const filledEl = (sel) => { const el = d0(sel); return !!(el && el.value && el.value.trim()); };
    d.querySelectorAll("[data-need]").forEach((tag) => {
      const need = tag.dataset.need;
      let filled;
      if (need === "prio") filled = !!D.prio;
      else if (need === "choice") filled = !!D.choice;
      else if (need === "why") filled = D.choice === "open" || filledEl("#ou-d-why");
      else filled = filledEl("#" + need);
      tag.hidden = filled;
      const el = need === "prio" ? d0("#ou-d-p") : need === "choice" ? d0("[data-c]") && d0("[data-c]").parentElement : d0(need === "why" ? "#ou-d-why" : "#" + need);
      if (el && filled) el.classList.remove("miss");
    });
    const opt = d0('label[for="ou-d-why"] .opt');
    if (opt) opt.hidden = D.choice !== "open";
    const note = d0("[data-open-note]");
    if (note) note.hidden = D.choice !== "open";
  }
  const tagReq = (need) => `<span class="req" data-need="${need}">obrigatório</span>`;
  function cqForm(o, isNew) {
    const ucs = O.M.req.use_cases || [];
    const ucField = isNew && ucs.length ? `<div class="field"><label class="field-label" for="ou-d-uc">Caso de uso <span class="opt">opcional</span></label>
      <select id="ou-d-uc" class="select"><option value="">nenhum</option>${ucs.map((u) => `<option value="${esc(u.id)}"${u.id === o.uc ? " selected" : ""}>${esc(u.name)}</option>`).join("")}</select></div>` : "";
    return `<div class="field"><label class="field-label" for="ou-d-q">Pergunta ${tagReq("ou-d-q")}</label>
        <textarea id="ou-d-q" class="textarea" rows="2" placeholder="Ex.: Quais produtos ficaram mais de 60 dias sem venda?">${esc(o.q)}</textarea></div>
      ${ucField}
      <div class="e1-dlg-2">
        <div class="field"><label class="field-label" for="ou-d-type">Tipo ${tagReq("ou-d-type")}</label>
          <select id="ou-d-type" class="select"><option value="">escolha</option>${CQ_TYPES.map(([v, l]) => `<option value="${v}"${v === o.type ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></div>
        <div class="field"><label class="field-label" for="ou-d-c">Conceitos ${tagReq("ou-d-c")}</label>
          <input id="ou-d-c" class="input" type="text" autocomplete="off" placeholder="Ex.: Produto, Pedido" value="${esc(o.concepts.join(", "))}"></div></div>
      <div class="field"><span class="field-label" id="ou-d-p-l">Prioridade ${tagReq("prio")}</span>
        <div class="seg" role="group" aria-labelledby="ou-d-p-l" id="ou-d-p">${PRIO.map(([v, l]) => `<button type="button" data-p="${v}" aria-pressed="${o.prio === v}">${l}</button>`).join("")}</div></div>`;
  }
  function findApplied(kind, ref) {
    const r = O.M.req;
    if (kind === "acq" || kind === "rcq") return (r.competency_questions || []).find((q) => q.id === ref);
    if (kind === "agap") return (r.gaps || []).find((g) => g.id === ref);
    if (kind === "adiv") return (r.divergences || []).find((x) => x.id === ref);
    return null;
  }
  const divLab = (x, k) => x.label || "Fonte " + String.fromCharCode(65 + k);
  function openDlg(kind, opts) {
    const M = O.M, i = opts.i ?? null, prev = i === null ? null : M.own[i];
    const cur = kind === "ncq" ? null : findApplied(kind, opts.ref);
    if (kind !== "ncq" && !cur) { if (O.ctx.toast) O.ctx.toast("Esse item não está mais na ontologia."); return; }
    const d = dlgEl();
    Object.assign(D, { kind, i, ref: opts.ref || null, from: opts.from || null, prio: "", choice: "" });
    let title = "", body = "", ok = i === null ? "Adicionar" : "Salvar";
    const ctxBox = (txt) => `<p class="ou-dlg-ctx">${esc(txt)}</p>`;
    const whyField = (val) => `<span class="choice-help" data-open-note hidden>Em aberto, a etapa 1 volta a ficar aberta até esta decisão.</span>
      <div class="field"><label class="field-label" for="ou-d-why">Por quê? <span class="req" data-need="why">obrigatório</span><span class="opt" hidden>opcional</span></label>
        <textarea id="ou-d-why" class="textarea" rows="2">${esc(val)}</textarea></div>`;
    if (kind === "ncq") {
      const o = prev || { q: "", uc: "", type: "", concepts: [], prio: "" };
      D.prio = o.prio; title = i === null ? "Nova pergunta" : "Editar pergunta";
      body = cqForm(o, true);
    } else if (kind === "acq") {
      const base = { q: cur.question || "", type: cur.type || "", concepts: list(cur.concepts), prio: cur.priority || "" };
      const df = prev ? prev.diff : {};
      const o = { q: df.question ?? base.q, type: df.type ?? base.type, concepts: df.concepts ?? base.concepts, prio: df.priority ?? base.prio };
      D.prio = o.prio; title = "Alterar pergunta"; ok = "Guardar alteração";
      body = `<p class="eyebrow">${esc([cur.id, STATUS_L[cur.status] || cur.status].filter(Boolean).join(" · "))}</p>${cqForm(o, false)}`;
    } else if (kind === "rcq") {
      title = "Excluir pergunta"; ok = "Guardar exclusão";
      body = `${ctxBox(cur.question)}<div class="field"><label class="field-label" for="ou-d-why">Motivo da exclusão ${tagReq("ou-d-why")}</label>
        <textarea id="ou-d-why" class="textarea" rows="2">${esc(prev ? prev.reason : "")}</textarea>
        <span class="choice-help">Se algo usa a pergunta, ela fica como descontinuada em vez de sumir.</span></div>`;
    } else if (kind === "agap") {
      D.choice = prev ? prev.decision : cur.decision || ""; title = "Alterar lacuna"; ok = "Guardar alteração";
      body = `${ctxBox(cur.question)}<div class="field"><span class="field-label" id="ou-d-c-l">O que fazer ${tagReq("choice")}</span>
        <div class="e1-opts" role="group" aria-labelledby="ou-d-c-l">${GAP_OPTS.map(([v, l]) => `<button type="button" data-c="${v}" aria-pressed="${D.choice === v}">${esc(l)}</button>`).join("")}</div></div>
        ${whyField(prev ? prev.note : cur.note || "")}`;
    } else if (kind === "adiv") {
      const srcs = Array.isArray(cur.sources) ? cur.sources : [];
      D.choice = prev ? (prev.decision === "precedence" ? "precedence|" + prev.winner : prev.decision)
        : cur.decision === "precedence" ? "precedence|" + (cur.winner || "") : cur.decision || "";
      title = "Alterar divergência"; ok = "Guardar alteração";
      body = `${ctxBox(`Qual definição de “${cur.topic || "?"}” vale?`)}<div class="field"><span class="field-label" id="ou-d-c-l">Qual vale, ou o que fazer ${tagReq("choice")}</span>
        ${srcs.length ? `<div class="e1-srcs" role="group" aria-labelledby="ou-d-c-l">${srcs.map((x, k) => `<button type="button" class="e1-src" data-c="precedence|${esc(divLab(x, k))}" aria-pressed="${D.choice === "precedence|" + divLab(x, k)}">
          <span class="l">${esc(divLab(x, k))}</span>${x.quote ? `<span class="qt">“${esc(x.quote)}”</span>` : ""}${x.path ? `<span class="pa">${esc(x.path)}${x.locator ? " · " + esc(x.locator) : ""}</span>` : ""}</button>`).join("")}</div>` : ""}
        <div class="e1-opts" role="group" aria-label="Outras opções">${DIV_OTHER.map(([v, l]) => `<button type="button" data-c="${v}" aria-pressed="${D.choice === v}">${esc(l)}</button>`).join("")}</div></div>
        ${whyField(prev ? prev.reason : cur.reason || "")}`;
    }
    d.innerHTML = `<form method="dialog" class="dlg-body" novalidate><h2 class="h3-semibold" id="ou-dlg-t">${esc(title)}</h2>${body}
      <p class="e1-dlg-msg" id="ou-dlg-msg" role="status" aria-live="polite"></p>
      <div class="dlg-actions"><button type="button" class="btn btn-outline" data-d="cancel">Cancelar</button><button type="submit" class="btn">${esc(ok)}</button></div></form>`;
    syncDlg();
    d.showModal();
    const first = d.querySelector("textarea, input, select, [data-c]");
    if (first) first.focus();
  }
  function closeDlg(focusSel) {
    const d = document.getElementById("ou-dlg");
    if (d && d.open) d.close();
    if (!O.el) return;
    const t = (focusSel && $(focusSel, O.el)) || (D.from && $(D.from, O.el)) || $('[data-o="save"]', O.el);
    if (t) t.focus({ preventScroll: true });
  }
  function dlgFail(items) {
    items.forEach(([sel]) => { const el = d0(sel); if (el) el.classList.add("miss"); });
    d0("#ou-dlg-msg").innerHTML = "<b>Falta:</b> " + items.map((x) => esc(x[1])).join(", ");
    const first = d0(items[0][0]);
    if (first) (first.matches("textarea, input, select") ? first : first.querySelector("button") || first).focus();
  }
  function dlgSubmit() {
    const M = O.M, k = D.kind, val = (sel) => { const el = d0(sel); return el ? el.value.trim() : ""; };
    // o servidor pode ter mudado com a janela aberta: o item alterado precisa continuar na ontologia
    if (k !== "ncq" && !findApplied(k, D.ref)) { d0("#ou-dlg-msg").textContent = "Esse item não está mais na ontologia. Cancele e confira a lista."; return; }
    let o = null;
    if (k === "ncq" || k === "acq") {
      const q = val("#ou-d-q"), type = val("#ou-d-type"), concepts = splitList(val("#ou-d-c"));
      const falta = [["#ou-d-q", !q, "a pergunta"], ["#ou-d-type", !type, "o tipo"], ["#ou-d-c", !concepts.length, "os conceitos"], ["#ou-d-p", !D.prio, "a prioridade"]].filter((x) => x[1]);
      if (falta.length) return dlgFail(falta.map(([s, , l]) => [s, l]));
      if (k === "ncq") o = { kind: "ncq", q, uc: val("#ou-d-uc"), type, concepts, prio: D.prio };
      else {
        const cur = findApplied(k, D.ref), diff = {};
        if (q !== (cur.question || "")) diff.question = q;
        if (type !== (cur.type || "")) diff.type = type;
        if (JSON.stringify(concepts) !== JSON.stringify(list(cur.concepts))) diff.concepts = concepts;
        if (D.prio !== (cur.priority || "")) diff.priority = D.prio;
        if (!Object.keys(diff).length) { d0("#ou-dlg-msg").innerHTML = "Nada mudou. Altere algum campo ou cancele."; return; }
        o = { kind: "acq", id: D.ref, label: cur.question, diff };
      }
    } else if (k === "rcq") {
      const reason = val("#ou-d-why");
      if (!reason) return dlgFail([["#ou-d-why", "o motivo"]]);
      o = { kind: "rcq", id: D.ref, label: findApplied(k, D.ref).question, reason };
    } else if (k === "agap" || k === "adiv") {
      const why = val("#ou-d-why"), falta = [];
      if (!D.choice) falta.push([".e1-opts", "a decisão"]);
      else if (D.choice !== "open" && !why) falta.push(["#ou-d-why", "o porquê (só Deixar em aberto dispensa)"]);
      if (falta.length) return dlgFail(falta);
      const cur = findApplied(k, D.ref);
      if (k === "agap") o = { kind: "agap", id: D.ref, label: cur.question, decision: D.choice, note: why };
      else {
        const prec = D.choice.startsWith("precedence|");
        o = { kind: "adiv", id: D.ref, label: `Qual definição de “${cur.topic || "?"}” vale?`, decision: prec ? "precedence" : D.choice, winner: prec ? D.choice.slice(11) : "", reason: why };
      }
    }
    if (!o) return;
    let i = D.i;
    if (i === null) { M.own.push(o); i = M.own.length - 1; } else M.own[i] = o;
    render();
    closeDlg(`[data-o="own-edit"][data-i="${i}"]`);
  }

  // ---------- conferir e salvar ----------
  function onSave() {
    const M = O.M, falta = missing(M);
    if (falta.length) {
      // leva ao primeiro item que falta, aberto
      const first = M.items.find((it) => !done(it) || (it.dec === "ok" && emptied(it)));
      if (first) {
        first.open = true;
        if (first.dec === "ok") { first.det = true; first.editing = true; }
        render(!first.dec ? `[data-o="dec"][data-id="${first.id}"][data-v="ok"]`
          : first.dec === "rej" ? (first.why === "outro" ? `#ou-r-${first.id}` : `[data-o="why"][data-id="${first.id}"]`) : `[data-of="val"][data-id="${first.id}"]`);
        const el = $(`[data-ou="${first.id}"]`, O.el);
        if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      msg(`<b>Falta:</b> ${falta.map(esc).join("; ")}`, "warn");
      return;
    }
    if (!M.items.length && !M.own.length) { msg("Nada para salvar."); return; }
    if (isAuto()) { msg("No modo automático, quem salva é a IA."); return; }
    openSave();
  }
  // traduz as escolhas para as mesmas chamadas de sempre: /api/review e /api/propose, depois /api/apply
  function planOps(M) {
    const ops = [];
    M.items.forEach((it) => {
      const label = `${(GROUP_LABEL[it.v.group] || "proposta").toLowerCase()}: “${cut(titleText(it), 60)}”`;
      if (it.dec === "rej") { ops.push({ label, path: "/api/review", body: { edit_id: it.id, decision: "reject", reason: reasonOf(it) } }); return; }
      const edits = diffOf(it);
      ops.push({ label, path: "/api/review", body: Object.assign({ edit_id: it.id, decision: "accept" }, Object.keys(edits).length ? { edits } : {}) });
    });
    M.own.forEach((o) => {
      const label = `“${cut(ownText(o), 60)}”`;
      let type = "", payload = null;
      if (o.kind === "ncq") { type = "add_competency_question"; payload = Object.assign({ question: o.q, type: o.type, concepts: o.concepts, priority: o.prio, status: "approved" }, o.uc ? { use_cases: [o.uc] } : {}); }
      else if (o.kind === "acq") { type = "update_competency_question"; payload = Object.assign({ id: o.id }, o.diff); }
      else if (o.kind === "rcq") { type = "remove_competency_question"; payload = { id: o.id, reason: o.reason }; }
      else if (o.kind === "agap") { type = "update_gap"; payload = Object.assign({ id: o.id, decision: o.decision }, o.note ? { note: o.note } : {}); }
      else if (o.kind === "adiv") { type = "update_divergence"; payload = Object.assign({ id: o.id, decision: o.decision }, o.decision === "precedence" ? { winner: o.winner } : {}, o.reason ? { reason: o.reason } : {}); }
      if (payload) ops.push({ label, path: "/api/propose", own: o, body: { type, payload } });
    });
    return ops;
  }
  function summaryHtml(M) {
    const li = (t, m, cls) => `<li class="${cls || ""}"><span class="q">${esc(t)}</span>${m ? `<span class="m">${esc(m)}</span>` : ""}</li>`;
    let html = "";
    groupKeys(M).forEach((g) => {
      const its = M.items.filter((it) => it.v.group === g);
      if (!its.length) return;
      const rows = its.map((it) => (it.dec === "rej" ? li(titleText(it), "rejeitada: " + reasonOf(it), "off") : li(titleText(it), Object.keys(diffOf(it)).length ? "aceita com ajuste" : "aceita")));
      html += `<h3 class="e1-sub">${esc(GROUP_LABEL[g] || g)}</h3><ul class="e1-sum">${rows.join("")}</ul>`;
    });
    if (M.own.length) html += `<h3 class="e1-sub">Suas alterações</h3><ul class="e1-sum">${M.own.map((o) => li(ownText(o), cut(ownSummary(o), 80))).join("")}</ul>`;
    return html;
  }
  function readName() {
    try { return localStorage.getItem("akme-reviewer") || ""; } catch (e) { return ""; }
  }
  function openSave() {
    let d = document.getElementById("ou-save");
    if (!d) {
      d = document.createElement("dialog");
      d.id = "ou-save"; d.className = "dlg e1-dlg e1-save"; d.setAttribute("aria-labelledby", "ou-save-t");
      document.body.appendChild(d);
      d.addEventListener("cancel", (e) => { e.preventDefault(); if (!O.saving) closeSave(); });
      d.addEventListener("click", (e) => {
        const b = e.target.closest("[data-s]");
        if (!b || b.disabled) return;
        if (b.dataset.s === "cancel") closeSave();
        else if (b.dataset.s === "done") { closeSave(); O.M = null; if (O.ctx.onDone) O.ctx.onDone(); }
      });
      d.addEventListener("submit", (e) => { e.preventDefault(); doSave(); });
    }
    const name = (O.ctx.reviewer || readName() || "").trim(), M = O.M;
    const acc = M.items.filter((it) => it.dec === "ok").length, rej = M.items.length - acc;
    const gate = (M.stage || {}).gate_active && M.items.some((it) => ONTO_GROUPS.has(it.v.group));
    d.innerHTML = `<form method="dialog" class="dlg-body" novalidate>
      <h2 class="h3-semibold" id="ou-save-t">Conferir e salvar</h2>
      <p class="p secondary">${plural(acc, "aceita", "aceitas")}, ${plural(rej, "rejeitada", "rejeitadas")}${M.own.length ? ` e ${plural(M.own.length, "alteração sua", "alterações suas")}` : ""}.</p>
      <div class="e1-sum-wrap">${summaryHtml(M)}</div>
      ${gate ? '<p class="ou-alert">Os requisitos ainda estão abertos: classes, relações e termos ficam esperando a etapa 1 fechar.</p>' : ""}
      <div class="field"><label class="field-label" for="ou-save-name">Seu nome <span class="req"${name ? " hidden" : ""}>obrigatório</span></label>
        <input id="ou-save-name" class="input" type="text" autocomplete="name" value="${esc(name)}" placeholder="quem aprova"></div>
      <p class="e1-dlg-msg" id="ou-save-msg" role="status" aria-live="polite">Salvar grava as decisões e aplica na ontologia. A validação roda antes; se aparecer erro novo, nada muda.</p>
      <div class="dlg-actions"><button type="button" class="btn btn-outline" data-s="cancel">Voltar</button><button type="submit" class="btn" data-s="ok">Salvar e aplicar</button></div></form>`;
    d.querySelector("#ou-save-name").addEventListener("input", (e) => { d.querySelector('label[for="ou-save-name"] .req').hidden = !!e.target.value.trim(); e.target.classList.remove("miss"); });
    d.showModal();
    (name ? d.querySelector('[data-s="ok"]') : d.querySelector("#ou-save-name")).focus();
  }
  function closeSave() {
    const d = document.getElementById("ou-save");
    if (d && d.open) d.close();
    const t = O.el && $('[data-o="save"]', O.el); if (t) t.focus({ preventScroll: true });
  }
  async function doSave() {
    const d = document.getElementById("ou-save"), M = O.M, api = O.ctx.api;
    const say = (h) => { d.querySelector("#ou-save-msg").innerHTML = h; };
    const inp = d.querySelector("#ou-save-name"), name = inp.value.trim();
    if (!name) { inp.classList.add("miss"); inp.focus(); say("<b>Falta:</b> seu nome"); return; }
    if (!api) { say("Esta página está só para leitura: abra com <code>akme review</code> para salvar."); return; }
    try { localStorage.setItem("akme-reviewer", name); } catch (e) { /* sem armazenamento: segue */ }
    const btns = d.querySelectorAll("button"), ok = d.querySelector('[data-s="ok"]');
    btns.forEach((b) => { b.disabled = true; }); O.saving = true;
    // enquanto grava, o poll da pagina nao redesenha nem anuncia as proprias propostas como novas
    if (O.ctx.setBusy) O.ctx.setBusy(true);
    const ops = planOps(M);
    let i = 0, applying = false;
    try {
      for (const o of ops) {
        i++;
        ok.textContent = `Salvando ${i} de ${ops.length}…`;
        await api.post(o.path, Object.assign({ reviewer: name }, o.body));
        // proposta feita sai da lista local; um novo clique nao duplica
        if (o.own) M.own.splice(M.own.indexOf(o.own), 1);
      }
      ok.textContent = "Aplicando…"; applying = true;
      const out = await api.post("/api/apply", { approved_by: name, stage: "all" });
      const after = (out && out.stage_after) || {}, n = (out.applied || []).length, nr = (out.rejected || []).length, held = (out.held_by_gate || []).length;
      O.saving = false;
      if (O.ctx.setBusy) O.ctx.setBusy(false);
      try { localStorage.removeItem(draftKey(M.project)); } catch (e) { /* sem armazenamento */ }
      d.querySelector("form").innerHTML = `<h2 class="h3-semibold" id="ou-save-t">Salvo e aplicado</h2>
        <div class="e1-empty"><b>${plural(n, "decisão entrou", "decisões entraram")} na ontologia</b>
          <span>${nr ? plural(nr, "rejeição ficou registrada", "rejeições ficaram registradas") + " no changelog. " : ""}${held ? plural(held, "proposta ficou", "propostas ficaram") + " esperando a etapa 1 fechar. " : ""}${window.AkmeChannel ? window.AkmeChannel.after() : "Volte para o chat: o agente segue para o próximo passo."}${after.label ? " Agora: " + esc(after.label) + "." : ""}</span></div>
        <div class="dlg-actions"><button type="button" class="btn" data-s="done">Fechar</button></div>`;
      d.querySelector('[data-s="done"]').focus();
    } catch (e) {
      O.saving = false;
      if (O.ctx.setBusy) O.ctx.setBusy(false);
      btns.forEach((b) => { b.disabled = false; }); ok.textContent = "Tentar de novo";
      const errs = (e.body && e.body.new_errors) || [];
      const where = applying ? "ao aplicar" : i ? `em ${esc(ops[i - 1].label)}` : "";
      say(`<b>Parou ${where}:</b> ${esc(e.message || String(e))}${errs.length ? `<ul>${errs.map((f) => `<li>${esc(f.subject || f.check || "")}: ${esc(f.message || "")}</li>`).join("")}</ul>` : ""}
        <br>O que já foi gravado continua gravado. Corrija e tente de novo.`);
      // traz do servidor o que ja foi gravado (o poll ficou parado durante o salvar)
      if (O.ctx.refresh) O.ctx.refresh(); else render();
    }
  }

  function mount(el, ctx) {
    if (O.wired !== el) {
      el.addEventListener("click", onClick);
      el.addEventListener("input", onInput);
      el.addEventListener("change", onInput);
      el.addEventListener("toggle", onToggle, true);
      O.wired = el;
    }
    O.el = el;
    O.ctx = ctx || {};
    // um poll do servidor refaz a tela; quem estava digitando nao perde o foco nem o cursor
    const a = document.activeElement, keep = a && el.contains(a) ? {
      sel: a.id ? "#" + a.id : a.dataset.o ? `[data-o="${a.dataset.o}"]${a.dataset.id ? `[data-id="${a.dataset.id}"]` : ""}${a.dataset.v ? `[data-v="${a.dataset.v}"]` : ""}${a.dataset.ref ? `[data-ref="${a.dataset.ref}"]` : ""}` : "",
      pos: typeof a.selectionStart === "number" ? [a.selectionStart, a.selectionEnd] : null } : null;
    O.M = buildModel(O.ctx.data, O.M);
    render();
    if (keep && keep.sel) {
      const t = $(keep.sel, el);
      if (t) {
        t.focus({ preventScroll: true });
        if (keep.pos && t.setSelectionRange) { try { t.setSelectionRange(keep.pos[0], keep.pos[1]); } catch (e) { /* campo sem cursor */ } }
      }
    }
  }
  // a etapa 1 manda para ca quem quer alterar algo ja aplicado: abre essa parte
  function showApplied() {
    if (O.M) O.M.apOpen = true; else O.showApplied = true;
  }

  window.AkmeOutras = { mount, remaining, pendingCount, covers, showApplied };
})();
