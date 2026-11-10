/* Conversa com o agente pela página (canal do Claude Code). Só funciona servida por `akme review`:
   GET /api/chat faz long-polling do log; POST /api/chat manda a mensagem ao agente; POST
   /api/chat/permission responde a um pedido de permissão de tool. Sem biblioteca, sem build. */
(function () {
  "use strict";
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const read = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const store = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const START_CMD = "claude --dangerously-load-development-channels server:akme";
  const NO_REPLY_MS = 45000;

  const S = { offset: 0, items: [], verdicts: {}, unread: 0, open: false, sending: false, waitTimer: null };

  async function call(path, opts) {
    const r = await fetch(path, opts);
    let body = null;
    try { body = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error((body && body.error) || "HTTP " + r.status);
    return body;
  }
  const post = (path, data) => call(path, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(data) });

  // markdown mínimo: escapa tudo antes; depois só código, negrito, listas e quebras de linha
  function md(text) {
    const blocks = esc(text).split(/```/);
    return blocks.map((b, i) => {
      if (i % 2) return `<pre><code>${b.replace(/^\w*\n/, "")}</code></pre>`;
      const lines = b.split("\n");
      let html = "", list = false;
      for (const raw of lines) {
        const line = raw.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        const m = /^\s*(?:[-*]|\d+\.)\s+(.*)$/.exec(line);
        if (m) { if (!list) { html += "<ul>"; list = true; } html += `<li>${m[1]}</li>`; continue; }
        if (list) { html += "</ul>"; list = false; }
        html += line.trim() ? `<p>${line}</p>` : "";
      }
      return html + (list ? "</ul>" : "");
    }).join("");
  }

  const time = (iso) => { try { return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };

  function renderItem(it) {
    if (it.role === "human") {
      return `<div class="chat-msg me"><div class="chat-bubble">${md(it.text)}</div><div class="chat-meta">${esc(it.author || "você")} · ${time(it.at)}</div></div>`;
    }
    if (it.role === "agent") {
      return `<div class="chat-msg agent"><div class="chat-bubble">${md(it.text)}</div><div class="chat-meta">agente · ${time(it.at)}</div></div>`;
    }
    if (it.role === "permission") {
      const v = S.verdicts[it.request_id];
      const state = v ? `<p class="chat-verdict ${v.behavior}">${v.behavior === "allow" ? "Permitido" : "Negado"}${v.author ? " por " + esc(v.author) : ""}</p>`
        : `<div class="chat-actions"><button type="button" class="btn btn-sm" data-perm="allow" data-id="${esc(it.request_id)}">Permitir</button><button type="button" class="btn btn-outline btn-sm" data-perm="deny" data-id="${esc(it.request_id)}">Negar</button></div>`;
      return `<div class="chat-perm" role="group" aria-label="Pedido de permissão">
        <div class="chat-perm-head">O agente pede permissão para usar <code>${esc(it.tool_name)}</code></div>
        ${it.text ? `<p>${esc(it.text)}</p>` : ""}
        ${it.input_preview ? `<pre><code>${esc(it.input_preview)}</code></pre>` : ""}
        ${state}</div>`;
    }
    return "";
  }

  function render() {
    const log = $("#chat-log");
    const visible = S.items.filter((i) => i.role !== "verdict" && i.role !== "event");
    log.innerHTML = visible.length ? visible.map(renderItem).join("")
      : `<div class="chat-empty"><p>Converse com o agente aqui, sem voltar ao terminal.</p><p class="tertiary">O Claude Code precisa estar aberto com o canal ligado:</p><pre><code>${esc(START_CMD)}</code></pre></div>`;
    log.scrollTop = log.scrollHeight;
    const last = [...S.items].reverse().find((i) => i.role === "human" || i.role === "agent");
    clearTimeout(S.waitTimer);
    const hint = $("#chat-hint");
    hint.hidden = true;
    if (last && last.role === "human") {
      const left = NO_REPLY_MS - (Date.now() - new Date(last.at).getTime());
      const show = () => { hint.hidden = false; hint.innerHTML = `Sem resposta ainda. Se o agente estiver parado, confira se o Claude Code foi aberto com <code>${esc(START_CMD)}</code>.`; };
      if (left <= 0) show(); else S.waitTimer = setTimeout(show, left);
    }
    const badge = $("#chat-unread");
    badge.hidden = !S.unread;
    badge.textContent = String(S.unread);
  }

  function ingest(items) {
    for (const it of items) {
      if (it.role === "verdict") S.verdicts[it.request_id] = it;
      if (!S.open && (it.role === "agent" || it.role === "permission")) S.unread++;
      S.items.push(it);
    }
    // pedido de permissão abre o painel sozinho: o agente está parado esperando
    if (items.some((i) => i.role === "permission" && !S.verdicts[i.request_id])) setOpen(true);
  }

  async function poll() {
    for (;;) {
      try {
        const r = await call(`/api/chat?offset=${S.offset}&timeout=25`, { headers: { Accept: "application/json" } });
        S.offset = r.offset;
        if (r.items.length) { ingest(r.items); render(); }
      } catch (e) {
        await new Promise((ok) => setTimeout(ok, 3000));
      }
    }
  }

  function setOpen(open) {
    S.open = open;
    document.body.classList.toggle("chat-open", open);
    $("#chat-panel").hidden = !open;
    $("#chat-toggle").setAttribute("aria-expanded", String(open));
    if (open) { S.unread = 0; render(); $("#chat-input").focus(); }
    store("akme-chat-open", open ? "1" : "0");
  }

  async function send() {
    const input = $("#chat-input"), text = input.value.trim();
    if (!text || S.sending) return;
    S.sending = true;
    $("#chat-send").disabled = true;
    $("#chat-error").hidden = true;
    try {
      await post("/api/chat", { text, author: read("akme-reviewer") || "" });
      input.value = "";
    } catch (e) {
      $("#chat-error").hidden = false;
      $("#chat-error").textContent = "Não foi possível enviar: " + e.message;
    } finally {
      S.sending = false;
      $("#chat-send").disabled = false;
      input.focus();
    }
  }

  async function verdict(btn) {
    const id = btn.dataset.id, behavior = btn.dataset.perm;
    btn.closest(".chat-actions").querySelectorAll("button").forEach((b) => { b.disabled = true; });
    try {
      await post("/api/chat/permission", { request_id: id, behavior, author: read("akme-reviewer") || "" });
    } catch (e) {
      $("#chat-error").hidden = false;
      $("#chat-error").textContent = "Não foi possível responder: " + e.message;
      btn.closest(".chat-actions").querySelectorAll("button").forEach((b) => { b.disabled = false; });
    }
  }

  async function init() {
    if (location.protocol !== "http:" && location.protocol !== "https:") return;
    let first;
    try { first = await call("/api/chat?offset=0&timeout=0", { headers: { Accept: "application/json" } }); } catch (e) { return; }
    $("#chat-toggle").hidden = false;
    S.offset = first.offset;
    ingest(first.items);
    S.unread = 0;
    $("#chat-toggle").addEventListener("click", () => setOpen(!S.open));
    $("#chat-close").addEventListener("click", () => setOpen(false));
    $("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); send(); });
    $("#chat-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
    });
    $("#chat-log").addEventListener("click", (e) => { const b = e.target.closest("[data-perm]"); if (b) verdict(b); });
    setOpen(read("akme-chat-open") !== "0");
    render();
    poll();
  }
  init();
})();
