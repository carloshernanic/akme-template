/* Bootstrap da pagina: tema, menu, deteccao da API de `akme review`, carga dos dados e
   inicializacao das duas vistas (AkmeReview e AkmeGraph). Sem biblioteca, sem build. */
(function () {
  "use strict";
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function setTheme(mode) {
    document.documentElement.setAttribute("data-theme", mode);
    $("#icon-sun").style.display = mode === "dark" ? "" : "none";
    $("#icon-moon").style.display = mode === "dark" ? "none" : "";
    try { localStorage.setItem("akme-theme", mode); } catch (e) {}
  }
  setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light");
  $("#theme").addEventListener("click", () => setTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
  $("#menu").addEventListener("click", () => {
    const open = $("#sidebar").classList.toggle("open");
    $("#menu").setAttribute("aria-expanded", String(open));
  });

  // modo editavel quando servida por `akme review`; como arquivo, api = null (modo leitura)
  async function detectApi() {
    if (location.protocol !== "http:" && location.protocol !== "https:") return null;
    try {
      const r = await fetch("/api/status", { headers: { Accept: "application/json" } });
      if (!r.ok) return null;
      await r.json();
    } catch (e) { return null; }
    const call = async (path, opts) => {
      const r = await fetch(path, opts);
      let body = null;
      try { body = await r.json(); } catch (e) {}
      if (!r.ok) { const err = new Error((body && body.error) || "HTTP " + r.status); err.body = body; err.status = r.status; throw err; }
      return body;
    };
    return {
      get: (path) => call(path, { headers: { Accept: "application/json" } }),
      post: (path, data) => call(path, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(data) }),
    };
  }

  async function load(api) {
    if (api) return api.get("/api/data");
    if (window.AKME_DATA) return window.AKME_DATA;
    const r = await fetch("ontology.json");
    if (!r.ok) throw new Error("ontology.json não encontrado");
    return r.json();
  }

  detectApi().then((api) => load(api).then((data) => {
    $("#project-title").textContent = data.project || "Akme";
    $("#version").textContent = "v" + (data.version || "0.0.0");
    $("#tabs").hidden = false;
    const mode = data.stage && data.stage.decision_mode && data.stage.decision_mode.mode;
    if (mode) document.body.dataset.decisionMode = mode;
    window.AkmeGraph.init(data);
    window.AkmeReview.init(data, api, { onData: (d) => window.AkmeGraph.update(d) });
  })).catch((err) => {
    $("#tabs").hidden = false;
    $("#view-ontologia").hidden = false;
    $("#graph-empty").hidden = false;
    $("#graph-empty").innerHTML = `<div><div class="p-lg" style="font-weight:600">Não foi possível carregar os dados</div><div class="p secondary">${esc(err.message)}. Rode <code>uv run akme review</code>, que gera os dados e abre esta página.</div></div>`;
  });
})();
