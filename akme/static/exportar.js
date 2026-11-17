/* Passo 8 (Neo4j: guia explicativo passo a passo) e Passo 9 (Exportação: download de arquivos gerados). */
(function () {
  "use strict";
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const S = { api: null, data: null };

  const code = (text, label) =>
    `<div class="ex-code"><pre>${esc(text)}</pre><button type="button" class="btn btn-outline btn-sm" data-copy="${esc(text)}" aria-label="Copiar ${esc(label || "o código")}">Copiar</button></div>`;

  function fmtBytes(n) {
    if (!n) return "0 B";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  }

  function wireCopy(root) {
    root.querySelectorAll("[data-copy]").forEach((btn) => {
      if (btn.dataset.wired) return;
      btn.dataset.wired = "1";
      btn.addEventListener("click", async () => {
        const text = btn.dataset.copy || "";
        try {
          if (navigator.clipboard) await navigator.clipboard.writeText(text);
        } catch (e) {}
        const prev = btn.textContent;
        btn.textContent = "Copiado";
        setTimeout(() => { btn.textContent = prev; }, 1400);
      });
    });
  }

  function init(api, data) {
    S.api = api;
    S.data = data || {};
  }

  function update(data) {
    S.data = data || S.data;
  }

  function show() {
    const el = $("#view-exportar");
    if (!el) return;
    const proj = (S.data && S.data.project) || "akme-template";
    const envBlock = [
      "AKME_NEO4J_URI=bolt://127.0.0.1:7687",
      "AKME_NEO4J_USER=neo4j",
      "AKME_NEO4J_PASSWORD=sua-senha-aqui",
    ].join("\n");
    const cypherOntology = `MATCH p = (a:Conceito {_projeto: "${proj}"})-[:RELACAO_ONTOLOGIA|SUBCLASSE_DE]->(b:Conceito)\nRETURN p LIMIT 200`;
    const cypherData = `MATCH (n)-[r]->(m)\nWHERE n._projeto = "${proj}" AND NOT n:Conceito\nRETURN n, r, m LIMIT 300`;

    el.innerHTML = `<div class="ex">
      <div class="card ex-step">
        <div class="ex-step-head"><span class="ex-num">1</span><h3 class="ex-title">Prepare seu banco Neo4j e o arquivo .env</h3></div>
        <p class="p secondary">Inicie uma instância local no Neo4j Desktop (ou Docker) e configure as credenciais na raiz do projeto no arquivo <code>.env</code>:</p>
        ${code(envBlock, "variáveis do .env")}
      </div>
      <div class="card ex-step">
        <div class="ex-step-head"><span class="ex-num">2</span><h3 class="ex-title">Execute a carga pelo terminal</h3></div>
        <p class="p secondary">Após aprovar os mapeamentos, chaves e tipos no passo <b>7 - Mapeamento</b>, execute o comando abaixo na pasta do projeto para enviar a ontologia e os dados:</p>
        ${code("uv run akme publish --target neo4j --no-dry-run", "comando de publicação Neo4j")}
      </div>
      <div class="card ex-step">
        <div class="ex-step-head"><span class="ex-num">3</span><h3 class="ex-title">Visualize no Neo4j Browser</h3></div>
        <p class="p secondary">Abra o Neo4j Browser (<code>http://localhost:7474</code> ou aba Query do Neo4j Desktop) e use as consultas abaixo:</p>
        <div class="field"><span class="field-label">Ver o modelo da ontologia</span>${code(cypherOntology, "consulta da ontologia")}</div>
        <div class="field"><span class="field-label">Ver os dados carregados</span>${code(cypherData, "consulta dos dados")}</div>
      </div>
    </div>`;
    wireCopy(el);
  }

  async function showDownloads() {
    const el = $("#view-downloads");
    if (!el) return;
    if (!S.api) {
      el.innerHTML = `<div class="callout callout-nota"><div><div class="t">Modo leitura</div><div class="b">Rode <code>uv run akme review</code> para baixar os arquivos gerados pelo projeto.</div></div></div>`;
      return;
    }
    el.innerHTML = `<div class="dl-wrap"><p class="p secondary">Carregando arquivos disponíveis…</p></div>`;
    try {
      const items = await S.api.get("/api/exports");
      if (!items.length) {
        el.innerHTML = `<div class="e1-empty"><b>Nenhum arquivo gerado ainda</b><span>Rode o export ou publish para gerar os artefatos da ontologia.</span></div>`;
        return;
      }
      const byGroup = new Map();
      items.forEach((x) => {
        if (!byGroup.has(x.group)) byGroup.set(x.group, []);
        byGroup.get(x.group).push(x);
      });
      const sections = Array.from(byGroup.entries()).map(([group, files]) => `
        <section>
          <h3 class="e1-sub" style="margin-top:0">${esc(group)}</h3>
          <div class="dl-list">${files.map((f) => `
            <div class="dl-row">
              <div class="dl-meta">
                <span class="dl-name mono">${esc(f.name)}</span>
                <span class="dl-desc">${esc(f.description)} · ${esc(fmtBytes(f.size))}</span>
              </div>
              <a class="btn btn-outline btn-sm" href="/api/download?file=${encodeURIComponent(f.id)}" download="${esc(f.name)}">Baixar</a>
            </div>`).join("")}
          </div>
        </section>`).join("");
      el.innerHTML = `<div class="dl-wrap"><div><h2 class="h2">Arquivos para download</h2><p class="p secondary">Artefatos gerados da ontologia, mapeamentos e publicação.</p></div>${sections}</div>`;
    } catch (e) {
      el.innerHTML = `<div class="callout callout-erro"><div><div class="t">Erro ao listar arquivos</div><div class="b">${esc(e.message)}</div></div></div>`;
    }
  }

  window.AkmeExport = { init, update, show, showDownloads };
})();
