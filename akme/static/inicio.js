/* Passo 1 - Início: configuração inicial centralizada na página web (modo, projeto, usuário e tabelas a perfilar). */
(function () {
  "use strict";
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const S = { el: null, api: null, state: null, filter: "", saving: false, onSaved: null, mode: "human", project: "", user: "", selected: new Set() };

  function readSavedName() {
    try { return localStorage.getItem("akme-reviewer") || ""; } catch (e) { return ""; }
  }
  function saveReviewerName(name) {
    try { if (name) localStorage.setItem("akme-reviewer", name); } catch (e) {}
  }

  async function mount(el, ctx) {
    S.el = el;
    S.api = ctx.api;
    S.onSaved = ctx.onSaved || null;
    if (!S.api) {
      el.innerHTML = `<div class="callout callout-nota"><div><div class="t">Modo leitura</div><div class="b">Rode <code>uv run akme review</code> para configurar o projeto pela página.</div></div></div>`;
      return;
    }
    if (!S.state) await refresh();
    render();
  }

  async function refresh() {
    if (!S.api) return;
    S.state = await S.api.get("/api/setup");
    S.mode = (S.state.decision_mode && S.state.decision_mode.mode) || "human";
    S.project = S.state.project || "";
    S.user = (S.state.decision_mode && S.state.decision_mode.authorized_by) || readSavedName() || "";
    S.selected = new Set(S.state.selected_sources || S.state.available_sources || []);
  }

  function render() {
    if (!S.el || !S.state) return;
    const sources = S.state.available_sources || [];
    const q = S.filter.trim().toLowerCase();
    const visible = sources.filter((s) => !q || s.toLowerCase().includes(q));
    const btnMode = (val, label, desc) => `<button type="button" data-setup-mode="${val}" aria-pressed="${S.mode === val}" title="${esc(desc)}">${esc(label)}</button>`;
    const sourceRows = visible.length
      ? visible.map((src) => `<label class="setup-source-item"><input type="checkbox" data-setup-src="${esc(src)}"${S.selected.has(src) ? " checked" : ""}><span class="mono">${esc(src)}</span></label>`).join("")
      : `<div class="p secondary" style="padding:8px">${sources.length ? "Nenhuma tabela encontrada com esse filtro." : "Nenhuma tabela listada pelo adaptador."}</div>`;

    S.el.innerHTML = `<div class="card setup-card">
      <div><h2 class="h2">Configuração inicial</h2><p class="p secondary">Defina como a ontologia será criada e quais tabelas devem ser perfiladas.</p></div>
      <div class="field">
        <span class="field-label">Modo de criação</span>
        <div class="seg" role="group" aria-label="Modo de criação">${btnMode("human", "Manual (eu aprovo)", "Você revisa e aprova cada etapa na página.")}${btnMode("auto", "Automático (IA decide)", "A IA decide e aplica as etapas em seu nome.")}</div>
      </div>
      <div class="setup-grid">
        <div class="field">
          <label class="field-label" for="setup-project">Nome do projeto</label>
          <input id="setup-project" class="input" type="text" value="${esc(S.project)}" placeholder="Ex.: olist, vendas">
        </div>
        <div class="field">
          <label class="field-label" for="setup-user">Seu nome</label>
          <input id="setup-user" class="input" type="text" autocomplete="name" value="${esc(S.user)}" placeholder="Ex.: João Braga">
        </div>
      </div>
      <div class="setup-sources">
        <div class="setup-sources-bar">
          <span class="field-label" style="margin-right:auto">Tabelas a perfilar (${S.selected.size} de ${sources.length})</span>
          <input id="setup-filter" class="input" style="max-width:220px; min-height:28px; padding:4px 8px" type="search" value="${esc(S.filter)}" placeholder="Filtrar tabelas">
          <button type="button" class="btn btn-outline btn-sm" data-setup-act="all">Todas</button>
          <button type="button" class="btn btn-outline btn-sm" data-setup-act="none">Nenhuma</button>
        </div>
        <div class="setup-source-list">${sourceRows}</div>
      </div>
      <div class="row" style="align-items:center; gap:12px">
        <button type="button" class="btn" id="setup-save"${S.saving ? " disabled" : ""}>${S.saving ? "Salvando e perfilando…" : S.state.setup_done ? "Atualizar configuração" : "Salvar e iniciar"}</button>
        <span class="p secondary" id="setup-msg" role="status" aria-live="polite">${S.saving ? "Salvando configurações e perfilando as tabelas selecionadas…" : ""}</span>
      </div>
    </div>`;

    wireEvents();
  }

  function wireEvents() {
    S.el.querySelectorAll("[data-setup-mode]").forEach((b) => b.addEventListener("click", () => {
      S.mode = b.dataset.setupMode;
      render();
    }));
    const projEl = $("#setup-project", S.el);
    const userEl = $("#setup-user", S.el);
    const filterEl = $("#setup-filter", S.el);
    if (projEl) projEl.addEventListener("input", () => { S.project = projEl.value; });
    if (userEl) userEl.addEventListener("input", () => { S.user = userEl.value; });
    if (filterEl) filterEl.addEventListener("input", () => {
      const pos = filterEl.selectionStart;
      S.filter = filterEl.value;
      render();
      const next = $("#setup-filter", S.el);
      if (next) { next.focus(); if (typeof pos === "number") next.setSelectionRange(pos, pos); }
    });
    S.el.querySelectorAll("[data-setup-src]").forEach((cb) => cb.addEventListener("change", () => {
      if (cb.checked) S.selected.add(cb.dataset.setupSrc);
      else S.selected.delete(cb.dataset.setupSrc);
      const lbl = S.el.querySelector(".setup-sources-bar .field-label");
      if (lbl) lbl.textContent = `Tabelas a perfilar (${S.selected.size} de ${(S.state.available_sources || []).length})`;
    }));
    const allBtn = $('[data-setup-act="all"]', S.el);
    const noneBtn = $('[data-setup-act="none"]', S.el);
    if (allBtn) allBtn.addEventListener("click", () => { (S.state.available_sources || []).forEach((s) => S.selected.add(s)); render(); });
    if (noneBtn) noneBtn.addEventListener("click", () => { S.selected.clear(); render(); });

    const saveBtn = $("#setup-save", S.el);
    if (saveBtn) saveBtn.addEventListener("click", save);
  }

  async function save() {
    const msg = $("#setup-msg", S.el);
    const project = S.project.trim();
    const user_name = S.user.trim();
    if (!project) { if (msg) msg.textContent = "Informe o nome do projeto."; $("#setup-project", S.el).focus(); return; }
    if (!user_name) { if (msg) msg.textContent = "Informe o seu nome."; $("#setup-user", S.el).focus(); return; }
    S.saving = true;
    render();
    try {
      const out = await S.api.post("/api/setup", {
        project,
        mode: S.mode,
        user_name,
        selected_sources: Array.from(S.selected),
      });
      S.state = out;
      saveReviewerName(user_name);
      S.saving = false;
      render();
      const m = $("#setup-msg", S.el);
      if (m) {
        const n = out && out.profile && typeof out.profile.sources === "number" ? out.profile.sources : null;
        m.textContent = n !== null
          ? `Configuração salva e ${n} ${n === 1 ? "tabela perfilada" : "tabelas perfiladas"} em docs/profile.json.`
          : "Configuração salva.";
      }
      if (S.onSaved) S.onSaved(out);
    } catch (e) {
      S.saving = false;
      render();
      const m = $("#setup-msg", S.el);
      if (m) m.textContent = "Erro: " + e.message;
    }
  }

  window.AkmeInicio = { mount, refresh };
})();
