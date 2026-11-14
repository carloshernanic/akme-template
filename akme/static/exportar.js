/* Aba "Exportar": leva a ontologia e os dados para o Neo4j em quatro passos (banco, previa, carga, ver o grafo).
   Le /api/neo4j (somente leitura) e dispara a carga em /api/neo4j/carga, sempre com a confirmacao de quem esta na
   pagina. A senha nunca passa por aqui: fica no .env. Sem biblioteca, sem build. */
(function () {
  "use strict";
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n) => Number(n || 0).toLocaleString("pt-BR");
  const I = {
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
    warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3l9.5 17h-19L12 3z"/><path d="M12 10v5M12 17.5h.01"/></svg>',
    err: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/></svg>',
    ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.7 2.7L16 9.5"/></svg>',
  };
  const NAMES = { AKME_NEO4J_URI: "endereço do banco", AKME_NEO4J_USER: "usuário", AKME_NEO4J_PASSWORD: "senha" };

  // como a pessoa roda o Neo4j: "docker" (comando no terminal, grafo visto no Neo4j Browser) ou "desktop" (Neo4j
  // Desktop, grafo visto no Query dele). A escolha vale do passo 1 ao 4; o akme so precisa de um banco respondendo no
  // endereco do .env. null = a pessoa ainda nao escolheu
  const VIA_KEY = "akme-neo4j-via";
  const readVia = () => { try { const v = localStorage.getItem(VIA_KEY); return v === "desktop" || v === "docker" ? v : null; } catch (e) { return null; } };
  const saveVia = (v) => { try { localStorage.setItem(VIA_KEY, v); } catch (e) { /* sem armazenamento: vale so nesta visita */ } };

  const S = { api: null, status: null, loading: false, error: "", confirmed: false, typed: "", running: false, loaded: null, loadError: null, opened: false, via: readVia() };

  // caminho em uso: a escolha guardada; sem ela, com o banco conectado, o que o servidor sabe dele
  // (conteiner do akme -> Docker; outro banco local -> quase sempre o Neo4j Desktop)
  const viewingOf = (st) => (S.loaded && S.loaded.viewing) || (st && st.database && st.database.connected ? st.viewing : null);
  const guessVia = (st) => {
    const v = viewingOf(st);
    if (v && v.container_ours === true) return "docker";
    if (v && v.aura_url && v.container_ours === false) return "desktop";
    return null;
  };
  const viaOf = (st) => S.via || guessVia(st) || "docker";

  const callout = (kind, icon, title, body) =>
    `<div class="callout callout-${kind}">${icon}<div><div class="t">${title}</div>${body ? `<div class="b">${body}</div>` : ""}</div></div>`;
  const code = (lines, label) => {
    const text = (Array.isArray(lines) ? lines : [lines]).join("\n");
    return `<div class="ex-code"><pre>${esc(text)}</pre><button type="button" class="btn btn-outline btn-sm" data-copy="${esc(text)}" aria-label="Copiar ${esc(label || "o comando")}">Copiar</button></div>`;
  };
  const badge = (kind, text) => `<span class="badge badge-sm badge-outline badge-${kind}">${esc(text)}</span>`;
  // passo indisponivel: uma linha so, com o motivo ao lado do titulo
  const step = (n, title, state, body, off) => off
    ? `<section class="card ex-step ex-off" aria-labelledby="ex-t${n}">
         <div class="ex-step-head"><span class="ex-num" aria-hidden="true">${n}</span><h3 class="ex-title" id="ex-t${n}">${title}</h3><span class="ex-hint">${body}</span></div>
       </section>`
    : `<section class="card ex-step" aria-labelledby="ex-t${n}">
         <div class="ex-step-head"><span class="ex-num" aria-hidden="true">${n}</span><h3 class="ex-title" id="ex-t${n}">${title}</h3>${state || ""}</div>
         ${body}
       </section>`;
  // sequencia numerada de acoes: o titulo de cada item e o verbo; o corpo, o que copiar ou clicar
  const seq = (items) => `<ol class="ex-seq">${items.filter(Boolean).map(([title, body, opt]) =>
    `<li${opt ? ' class="ex-opt"' : ""}><div class="ex-seq-t">${title}${opt ? ' <span class="ex-tag">opcional</span>' : ""}</div>${body || ""}</li>`).join("")}</ol>`;
  // par rotulo-valor em destaque: o que a pessoa digita em outra tela
  const field = (label, value, copyText) =>
    `<div class="ex-kv"><span class="ex-k">${label}</span><span class="ex-v">${value}</span>${copyText
      ? `<button type="button" class="btn btn-outline btn-sm" data-copy="${esc(copyText)}" aria-label="Copiar ${esc(label.toLowerCase())}">Copiar</button>` : ""}</div>`;
  const againBtn = () => `<div><button type="button" class="btn btn-outline btn-sm" data-act="refresh" ${S.loading || S.running ? "disabled" : ""}>Conferir de novo</button></div>`;

  // ---------- 1. banco ----------
  // escolha entre os dois jeitos de ter um Neo4j local; so aparece enquanto o banco nao conecta
  const pick = (via) => {
    const card = (key, title, who) =>
      `<button type="button" class="ex-pick-c" data-act="via" data-via="${key}" aria-pressed="${via === key}"><b>${title}</b><span>${who}</span></button>`;
    return `<div class="ex-pick" role="group" aria-label="Como rodar o Neo4j">${card("docker", "Docker", "um comando no terminal")}${card("desktop", "Neo4j Desktop", "aplicativo, sem terminal")}</div>`;
  };

  // Quem chega aqui pela primeira vez nao tem Neo4j: a tela diz isso antes de qualquer outra hipotese.
  function stepDatabase(st) {
    const env = st.env, db = st.database, setup = st.setup, box = st.container || {};
    const via = viaOf(st), desk = via === "desktop";
    const raw = (text) => `<details class="ex-details"><summary>Mensagem técnica</summary><p class="p secondary mono">${esc(text)}</p></details>`;
    const createCmd = code(setup.docker, "o comando do Docker");
    const dockerNote = `<p class="p secondary">Precisa do Docker aberto. Na primeira vez, leva alguns minutos.</p>`;
    const create = ["Crie o banco no terminal, na pasta do projeto", `${createCmd}${dockerNote}`];
    const wait = ["Espere uns 20 segundos e confira", againBtn()];
    // Neo4j Desktop: rotulos conferidos no teste de 13/11/2026 (Instances, Create, RUNNING, Connection URI)
    const deskGet = ["Baixe e abra o Neo4j Desktop",
      `<div><a class="btn btn-outline btn-sm" href="https://neo4j.com/download/" target="_blank" rel="noopener">neo4j.com/download</a></div>`];
    const deskCreate = ["Crie uma instância local",
      `<p class="p">Em <b>Instances</b>, clique em <b>Create</b>. Senha com 8 caracteres ou mais, só letras e números. Espere ficar <b>RUNNING</b>.</p>
       <p class="p secondary">Se o banco do Docker estiver ligado, pare antes: <code>docker stop akme-neo4j</code>.</p>`];
    const deskCheck = ["Confira", againBtn()];
    const envLines = (what) => ["Cole estas linhas no arquivo <code>.env</code>, na pasta do projeto",
      `${code(desk ? setup.env.map((l) => l.replace(/<invente[^>]*>/, "<a senha que você criou na instância>")) : setup.env, "as linhas do .env")}<p class="ex-must">${I.warn}${desk ? "Troque a senha pela que você criou na instância." : "Troque a senha por uma sua, com 8 caracteres ou mais."}</p>
       ${desk ? `<p class="p secondary">O Desktop mostra o endereço em <b>Connection URI</b> (<code>neo4j://127.0.0.1:7687</code>). Se a porta for outra, use a dele.</p>` : ""}
       <p class="p secondary">Falta hoje: ${esc(what)}.</p>`];
    // passo 1 ainda nao verde: a escolha vem antes das instrucoes
    const open = (badgeHtml, body) => step(1, "Banco", badgeHtml, `${pick(via)}${body}`);

    if (env.missing.length) {
      const what = env.missing.map((v) => NAMES[v]).join(", ");
      return open(badge("warning", "falta configurar"),
        seq(desk ? [deskGet, deskCreate, envLines(what), deskCheck] : [envLines(what), create, wait]));
    }
    if (env.password_chars) {
      return open(badge("warning", "senha inválida"),
        `${desk
          ? callout("atencao", I.warn, "Troque a senha do .env: ela tem caractere especial", "Use só letras e números em <code>AKME_NEO4J_PASSWORD</code>. Se a instância já tem essa senha, crie outra instância com uma senha assim.")
          : callout("atencao", I.warn, "Troque a senha do .env: ela tem caractere especial", "Use só letras, números e <code>_ - . @</code> em <code>AKME_NEO4J_PASSWORD</code>. O comando que cria o banco lê a senha pelo terminal, que troca <code>$</code>, espaço, aspas e <code>#</code>; o banco nasceria com outra senha.")}
         ${againBtn()}`);
    }
    if (env.password_short || env.password_placeholder) {
      const why = env.password_placeholder ? "ainda é o texto de exemplo" : "tem menos de 8 caracteres";
      return open(badge("warning", "senha inválida"),
        `${callout("atencao", I.warn, `Troque a senha do .env: ela ${why}`, desk ? "Use em <code>AKME_NEO4J_PASSWORD</code> a senha que você criou na instância e salve." : "Use 8 caracteres ou mais em <code>AKME_NEO4J_PASSWORD</code> e salve.")}
         ${againBtn()}`);
    }
    if (!db) return step(1, "Banco", "", "Conferido depois da prévia (passo 2).", true);
    if (!db.connected && desk) {
      if (db.kind === "senha") {
        return open(badge("error", "senha recusada"),
          `${callout("erro", I.err, "O banco recusou a senha do .env", "Use no <code>.env</code> a senha que você criou junto com a instância.")}
           ${againBtn()}
           <details class="ex-details"><summary>Não lembra a senha?</summary><p class="p">Em <b>Instances</b>, clique em <b>Create</b>, crie outra instância e use a senha nova no <code>.env</code>.</p></details>
           ${raw(db.error)}`);
      }
      if (db.kind !== "desligado") {
        return open(badge("error", "sem conexão"),
          `${callout("erro", I.err, `Sem conexão com ${esc(env.destination)}`, esc(db.error))}${againBtn()}`);
      }
      return open(badge("warning", "banco desligado"),
        `${callout("nota", I.info, `Nada responde em ${esc(env.destination)}`, "No Desktop, em <b>Instances</b>, a instância precisa estar <b>RUNNING</b>, e a porta do <b>Connection URI</b> tem de ser a do <code>.env</code>.")}
         ${seq([deskGet, deskCreate, deskCheck])}${raw(db.error)}`);
    }
    if (!db.connected) {
      const name = esc(box.name || "akme-neo4j");
      const remove = code([`docker rm -f ${box.name || "akme-neo4j"}`, `docker volume rm ${box.name || "akme-neo4j"}-data`], "os comandos de limpeza");
      if (db.kind === "senha") {
        return open(badge("error", "senha recusada"),
          `${callout("erro", I.err, "O banco recusou a senha do .env", "Volte no <code>.env</code> a senha com que o banco foi criado.")}
           ${againBtn()}
           <details class="ex-details"><summary>Não lembra a senha? Recrie o banco (apaga o que está nele)</summary>${remove}${createCmd}</details>
           ${raw(db.error)}`);
      }
      if (db.kind !== "desligado") {
        return open(badge("error", "sem conexão"),
          `${callout("erro", I.err, `Sem conexão com ${esc(env.destination)}`, esc(db.error))}${againBtn()}`);
      }
      // nada responde no endereco: o caso de quem nunca criou o banco, ou de banco parado
      let body;
      if (box.exists && box.reason === "senha_curta") {
        body = `${callout("erro", I.err, "O banco não subiu: a senha da criação era curta", `A senha do <code>.env</code> agora serve. Recrie o contêiner <code>${name}</code>.`)}
                ${seq([["Apague o banco que falhou", remove], create, wait])}`;
      } else if (box.exists && box.status === "running") {
        body = `${callout("nota", I.info, "O banco está ligando", "Espere uns 20 segundos.")}${againBtn()}`;
      } else if (box.exists) {
        body = `${callout("atencao", I.warn, "O banco está desligado", `Contêiner <code>${name}</code> parado.`)}
                ${seq([["Ligue o banco no terminal", `${code(`docker start ${box.name}`, "o comando para ligar")}<p class="p secondary">Se desligar de novo, veja o motivo com <code>docker logs ${name}</code>.</p>`], wait])}`;
      } else {
        const noDocker = box.docker === false ? callout("atencao", I.warn, "O Docker não respondeu", "Abra (ou instale) o Docker Desktop antes.") : "";
        body = `${callout("nota", I.info, "Ainda não há banco", `Nada responde em <code>${esc(env.destination)}</code>. O banco nasce com a senha do <code>.env</code>.`)}
                ${noDocker}${seq([create, wait])}`;
      }
      return open(badge("warning", "banco desligado"), `${body}${raw(db.error)}`);
    }
    if (db.refusal) {
      return step(1, "Banco", badge("error", "banco recusado"),
        `${callout("erro", I.err, "Este banco não pode receber a carga", `${esc(db.refusal)}. Use um banco vazio ou o deste projeto.`)}
         <p class="p secondary">Conectado a <code>${esc(env.destination)}</code>.</p>`);
    }
    // por qual caminho, so quando se sabe: conteiner do akme, escolha guardada ou banco local de fora (Desktop)
    const v = viewingOf(st);
    const by = v && v.container_ours === true ? "Docker" : desk && (S.via || guessVia(st)) ? "Neo4j Desktop" : S.via === "docker" ? "Docker" : "";
    return step(1, "Banco", badge("success", "conectado"),
      `<p class="p">Conectado a <code>${esc(env.destination)}</code>${by ? ` · pelo ${by}` : ""} · ${db.has_project ? "já tem este projeto" : "banco vazio"}</p>`);
  }

  // ---------- 2. previa ----------
  function stepPreview(st) {
    if (st.plan_error) {
      return step(2, "O que vai para o grafo", badge("error", "sem prévia"),
        callout("erro", I.err, "Não deu para montar a prévia", `${esc(st.plan_error)}. Peça ao agente: "prepare a exportação para o Neo4j".`));
    }
    const plan = st.plan, db = st.database && st.database.connected ? st.database : null;
    const dbCol = db ? "<th>No banco</th>" : "";
    const delta = (cur) => {
      if (!db || !cur) return db ? "<td>0</td>" : "";
      return `<td>${num(cur.now)}${cur.now > cur.then ? ` <span class="ex-note ex-warn">${num(cur.now - cur.then)} a remover</span>` : ""}</td>`;
    };
    const nodes = plan.nodes.map((n) => `<tr><td><code>${esc(n.label)}</code>${n.linked ? "" : ' <span class="ex-note">sem ligações</span>'}</td><td>${num(n.rows)}</td>${delta(db && db.nodes[n.label])}</tr>`).join("");
    const rels = plan.relationships.map((r) => `<tr><td><code>${esc(r.relation)}</code></td><td>${num(r.rows)}</td>${delta(db && db.relationships[r.relation])}</tr>`).join("");
    const problems = plan.problems.length
      ? callout("erro", I.err, `${plan.problems.length === 1 ? "1 problema impede" : plan.problems.length + " problemas impedem"} a carga`,
          `<ul>${plan.problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul><p>Peça a correção ao agente no chat e aprove na aba Revisão.</p>`)
      : "";
    // fontes que a etapa 5 deixou de fora viram uma linha so: sao decisao ja tomada, nao um alerta por fonte
    const OUT = "fonte excluida na etapa 5: ";
    const skipped = plan.warnings.filter((w) => w.startsWith(OUT)).map((w) => w.slice(OUT.length));
    const other = plan.warnings.filter((w) => !w.startsWith(OUT));
    const warnings = other.length
      ? callout("atencao", I.warn, other.length === 1 ? "1 aviso" : `${other.length} avisos`, `<ul>${other.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>`)
      : "";
    const loose = plan.nodes.filter((n) => !n.linked).map((n) => n.label);
    const looseNote = loose.length
      ? callout("nota", I.info, `${loose.length === 1 ? "1 classe fica solta" : loose.length + " classes ficam soltas"} no grafo`,
          `${loose.map((l) => `<code>${esc(l)}</code>`).join(", ")}: sem ligação com as outras. Se deveriam ter, peça a relação ao agente.`)
      : "";
    const removes = db && (db.removed_nodes || db.removed_relationships);
    const stats = `<div class="ex-stats">
        <div class="ex-stat"><span class="ex-stat-n">${num(plan.total_nodes)}</span><span class="ex-stat-l">registros</span></div>
        <div class="ex-stat"><span class="ex-stat-n">${num(plan.total_relationships)}</span><span class="ex-stat-l">ligações</span></div>
        ${removes ? `<div class="ex-stat ex-stat-warn"><span class="ex-stat-n">${num(db.removed_nodes || db.removed_relationships)}</span><span class="ex-stat-l">${db.removed_nodes ? "registros" : "ligações"} a remover</span></div>` : ""}
        <div class="ex-stat ex-stat-sub"><span class="ex-stat-l">projeto <b>${esc(plan.project)}</b>, mais a ontologia</span></div>
      </div>`;
    const without = plan.concepts_without_data.length
      ? `<p class="p secondary">Sem registros (entram só como definição): ${plan.concepts_without_data.map((c) => `<code>${esc(c)}</code>`).join(", ")}.</p>`
      : "";
    const skippedLine = skipped.length
      ? `<p class="p secondary">${skipped.length === 1 ? "Fonte deixada" : "Fontes deixadas"} de fora na etapa 5: ${skipped.map((x) => `<code>${esc(x)}</code>`).join(", ")}.</p>`
      : "";
    const state = plan.problems.length ? badge("error", "bloqueado") : badge("success", "pronto");
    return step(2, "O que vai para o grafo", state,
      `${stats}${problems}${warnings}${looseNote}
       <details class="ex-details"${removes ? " open" : ""}><summary>Ver por classe e ligação</summary>
         <div class="ex-tables${db ? " ex-tables-db" : ""}">
           <div class="ex-table"><table><thead><tr><th>Classe</th><th>Registros</th>${dbCol}</tr></thead><tbody>${nodes || '<tr><td colspan="3">nenhuma</td></tr>'}</tbody></table></div>
           <div class="ex-table"><table><thead><tr><th>Ligação</th><th>Quantidade</th>${dbCol}</tr></thead><tbody>${rels || '<tr><td colspan="3">nenhuma</td></tr>'}</tbody></table></div>
         </div>${without}${skippedLine}
       </details>`);
  }

  // ---------- 3. carga ----------
  function ready(st) {
    return !!(st.plan && !st.plan.problems.length && st.database && st.database.connected && !st.database.refusal);
  }

  function stepLoad(st) {
    const cli = `<details class="ex-details"><summary>Prefere o terminal?</summary>${code(st.cli, "o comando da carga")}</details>`;
    if (S.loaded) {
      const r = S.loaded, rm = r.removed || {};
      const removed = (rm.nodes || rm.relationships) ? ` Removidos: ${num(rm.nodes)} registros e ${num(rm.relationships)} ligações.` : "";
      return step(3, "Carregar", badge("success", "carregado"),
        `${callout("ok", I.ok, "Carga concluída e conferida", `${num(r.total_nodes)} registros e ${num(r.total_relationships)} ligações gravados.${removed}`)}
         <div><button type="button" class="btn btn-outline btn-sm" data-act="again">Carregar de novo</button></div>`);
    }
    if (!ready(st)) return step(3, "Carregar", "", "Libera quando os passos 1 e 2 estiverem prontos.", true);
    const db = st.database;
    const removes = db.removed_nodes || db.removed_relationships;
    const sync = removes
      ? `<p class="ex-must">${I.warn}Também apaga ${num(db.removed_nodes)} registros e ${num(db.removed_relationships)} ligações que saíram da origem.</p>`
      : `<p class="p secondary">${db.has_project ? "Atualiza o projeto; não apaga nada." : "Banco vazio: só grava."}</p>`;
    const big = db.large_removal
      ? callout("atencao", I.warn, "A carga apaga boa parte de uma classe", `Se a origem veio incompleta, pare. Para seguir, digite <b>${num(db.large_removal)}</b> abaixo.`)
      : "";
    const typed = db.large_removal
      ? `<label class="ex-field"><span class="p-em">Total de registros removidos</span><input class="input" id="ex-typed" inputmode="numeric" autocomplete="off" value="${esc(S.typed)}"></label>`
      : "";
    const typedOk = !db.large_removal || S.typed.trim().replace(/\./g, "") === String(db.large_removal);
    const err = S.loadError
      ? callout("erro", I.err, S.loadError.started ? "A carga começou e parou com erro" : "A carga não foi feita", `${S.loadError.started ? "O banco pode ter sido alterado. Leia a mensagem, clique em <b>Conferir de novo</b> para ver como ele ficou e, se for o caso, carregue de novo (repetir a carga é seguro). " : ""}${esc(S.loadError.message)}${S.loadError.problems ? `<ul>${S.loadError.problems.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : ""}`)
      : "";
    return step(3, "Carregar", "",
      `<p class="p">Grava <b>${num(st.plan.total_nodes)}</b> registros e <b>${num(st.plan.total_relationships)}</b> ligações em <code>${esc(st.env.destination)}</code>.</p>
       ${sync}${big}${err}
       <div class="ex-do">
         ${typed}
         <label class="checkbox"><input type="checkbox" id="ex-confirm" ${S.confirmed ? "checked" : ""} ${S.running ? "disabled" : ""}> Entendi que a carga altera o banco e não tem como desfazer</label>
         <div class="ex-actions"><button type="button" class="btn ex-go" data-act="load" ${S.confirmed && typedOk && !S.running ? "" : "disabled"}>${S.running ? "Carregando…" : "Carregar no Neo4j"}</button>
         ${S.running ? '<span class="p secondary" role="status">Pode levar minutos. Não feche a página.</span>' : ""}</div>
       </div>
       ${cli}`);
  }

  // ---------- 4. ver o grafo ----------
  // troca de roteiro no proprio passo 4: a mesma escolha do passo 1, em formato compacto
  const viaSwitch = (via) => {
    const b = (key, title) => `<button type="button" data-act="via" data-via="${key}" aria-pressed="${via === key}">${title}</button>`;
    return `<div class="ex-via"><span class="ex-via-l">Ver pelo</span><div class="seg" role="group" aria-label="Ver o grafo pelo">${b("docker", "Neo4j Browser")}${b("desktop", "Neo4j Desktop")}</div></div>`;
  };

  function stepView(st) {
    const v = (S.loaded && S.loaded.viewing) || st.viewing;
    const has = !!S.loaded || !!(st.database && st.database.connected && st.database.has_project);
    if (!v || !has) return step(4, "Ver o grafo", "", "Libera depois da carga.", true);
    const via = viaOf(st), desk = via === "desktop";
    const silent = v.browser_answers ? "" : `${callout("atencao", I.warn, `O Neo4j Browser não respondeu em ${esc(v.browser_url)}`,
      "Se ele usa outra porta, acrescente esta linha ao <code>.env</code> e clique em <b>Conferir de novo</b>:")}${code("AKME_NEO4J_BROWSER_URL=http://localhost:<porta>", "a linha do .env")}`;
    // endereco so aparece se nao for o padrao que o Browser ja sugere
    const addr = st.setup.bolt_port && st.setup.bolt_port !== 7687 && st.env.destination
      ? field("Endereço", `<code>${esc(st.env.destination)}</code>`, st.env.destination) : "";
    const file = (path) => `publish/${esc(path.split("/").pop())}`;
    // console da Aura: gerador de Cypher a partir de texto, ligado ao banco local; so funciona com o APOC
    let aura = "";
    if (v.aura_url) {
      const noApoc = v.apoc === false ? "Este banco não tem o APOC" : "Não deu para conferir o APOC";
      const apoc = v.apoc === true
        ? `<p class="p"><span class="badge badge-sm badge-outline badge-success">APOC instalado</span> O banco está pronto para o gerador.</p>`
        : desk
          ? callout("atencao", I.warn, noApoc, "O gerador de perguntas só funciona com ele. No Neo4j Desktop, o APOC é um plugin da instância: instale-o nela, reinicie a instância e clique em <b>Conferir de novo</b>.")
          : `${callout("atencao", I.warn, noApoc, "O gerador de perguntas só funciona com ele. Recrie o contêiner com o comando abaixo: o grafo e a senha ficam guardados, nada se perde.")}
           ${v.container_ours ? code(st.setup.recreate, "o comando que recria o banco com o APOC") : `<p class="p secondary">O seu contêiner não é o <code>akme-neo4j</code>: recrie-o com o mesmo nome, portas e volume, acrescentando a linha <code>--env NEO4J_PLUGINS='["apoc"]'</code>.</p>`}`;
      aura = `<details class="ex-details"><summary>Escrever a pergunta e receber a consulta pronta</summary>
        ${apoc}
        <p class="p">Abra <a href="https://console.neo4j.io" target="_blank" rel="noopener">console.neo4j.io</a>, entre em <b>Query</b> e, em <b>Connect</b>, aba <b>Self-managed</b>, use:</p>
        <div class="ex-login">${field("Endereço", `<code>${esc(v.aura_url)}</code>`, v.aura_url)}${field("Usuário", `<code>${esc(v.user)}</code>`, v.user)}${field("Senha", `a do seu <code>.env</code>`)}</div>
        <p class="p secondary">Antes de usar com dado de cliente, combine com ele: a pergunta e o esquema vão para a nuvem da Neo4j. Confira a consulta que o gerador propõe; o akme testou a conexão, não o gerador.</p>
      </details>`;
    }
    // roteiro do Neo4j Browser: o caminho do Docker e o unico que abre o tutorial (:guide)
    const browserSeq = (go) => [
      ["Abra o Neo4j Browser", `<div><a class="btn ${go}" href="${esc(v.browser_url)}" target="_blank" rel="noopener">Abrir o Neo4j Browser</a></div>`],
      ["Entre com", `<div class="ex-login">${addr}${field("Usuário", `<code>${esc(v.user)}</code>`, v.user)}${field("Senha", `a do seu <code>.env</code> <span class="ex-v-sub">(<code>AKME_NEO4J_PASSWORD</code>)</span>`)}</div>`],
      ["Rode o tutorial: cole no campo do topo e aperte <b>Run</b>", `${code(v.guide_command, "o comando do tutorial")}<p class="p secondary">Deixe esta página aberta: é ela que entrega o tutorial.</p>`],
    ];
    // roteiro do Neo4j Desktop: rotulos conferidos em capturas do Desktop (Instances, Query, RUNNING, Database information)
    const deskSeq = [
      ["No Neo4j Desktop, abra <b>Query</b>", `<p class="p secondary">Com a instância <b>RUNNING</b> em <b>Instances</b>.</p>`],
      ["Veja o mapa das classes", code("CALL db.schema.visualization()", "a consulta do mapa")],
      ["Veja os registros", `${code("MATCH p=()-[]->() RETURN p LIMIT 25", "a consulta dos registros")}<p class="p secondary">Se <b>Database information</b> mostrar a contagem antiga, clique no ícone de atualizar.</p>`],
    ];
    const queries = desk
      ? `<p class="p">O arquivo tem consultas para copiar e colar no <b>Query</b>.</p>`
      : `<p class="p">No Browser: <b>Queries</b> › <b>Upload</b>.</p>`;
    const common = [
      ...(aura ? [["Perguntas em português, pelo console da Aura", aura, true]] : []),
      ["Consultas prontas", `${queries}<div><a class="btn btn-outline btn-sm" href="${file(v.files.queries)}" download>Baixar as consultas</a></div>`, true],
    ];
    // no Desktop, o tutorial fica recolhido: so abre no Browser, em outro endereco
    const guided = ["Tutorial guiado do akme", `<details class="ex-details"><summary>Só abre no Neo4j Browser, em <code>${esc(v.browser_url)}</code></summary>
        ${silent}${seq(browserSeq("btn-outline btn-sm"))}</details>`, true];
    return step(4, "Ver o grafo", badge("success", "disponível"),
      desk
        ? `${viaSwitch(via)}${seq([...deskSeq, guided, ...common])}`
        : `${viaSwitch(via)}${silent}${seq([...browserSeq("ex-go"), ...common])}`);
  }

  // ---------- pagina ----------
  function render() {
    const el = $("#view-exportar");
    if (!el) return;
    const head = `<div class="ex-head"><div class="intro"><h2 class="h2">Exportar para o Neo4j</h2>
        <p class="p secondary">Quatro passos. Nada é gravado até você clicar em carregar.</p></div>
        <button type="button" class="btn btn-outline btn-sm" data-act="refresh" ${S.loading || S.running ? "disabled" : ""}>${S.loading ? "Conferindo…" : "Conferir de novo"}</button></div>`;
    if (!S.api) {
      el.innerHTML = `<div class="ex">${head}${callout("nota", I.info, "Abra a página pelo akme", "Rode <code>uv run akme review</code> e abra o endereço que ele mostra.")}</div>`;
      return;
    }
    if (S.error) {
      el.innerHTML = `<div class="ex">${head}${callout("erro", I.err, "Não foi possível conferir a exportação", esc(S.error))}</div>`;
      return;
    }
    if (!S.status) {
      el.innerHTML = `<div class="ex">${head}<p class="p secondary" role="status">Lendo as fontes e conferindo o banco…</p></div>`;
      return;
    }
    const st = S.status;
    el.innerHTML = `<div class="ex" aria-busy="${S.loading}">${head}${stepDatabase(st)}${stepPreview(st)}${stepLoad(st)}${stepView(st)}</div>`;
  }

  async function refresh() {
    if (!S.api || S.loading) return;
    S.loading = true; S.error = "";
    render();
    try { S.status = await S.api.get("/api/neo4j"); } catch (e) { S.error = e.message; S.status = null; }
    S.loading = false;
    render();
  }

  async function load() {
    if (S.running || !S.status || !ready(S.status)) return;
    S.running = true; S.loadError = null;
    render();
    try {
      S.loaded = await S.api.post("/api/neo4j/carga", { confirmed: true, removed: S.typed.trim().replace(/\./g, "") || null, token: S.status.token || null });
      S.confirmed = false; S.typed = "";
    } catch (e) {
      S.loadError = { message: e.message, problems: e.body && e.body.problems, started: !!(e.body && e.body.started) };
    }
    S.running = false;
    render();
    if (S.loaded) refresh();  // as contagens "no banco hoje" passam a ser as novas
  }

  async function copy(btn) {
    const text = btn.dataset.copy;
    try { await navigator.clipboard.writeText(text); } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch (e2) {}
      ta.remove();
    }
    btn.textContent = "Copiado";
    setTimeout(() => { btn.textContent = "Copiar"; }, 1500);
  }

  function onClick(ev) {
    const copyBtn = ev.target.closest("[data-copy]");
    if (copyBtn) return void copy(copyBtn);
    const act = ev.target.closest("[data-act]");
    if (!act) return;
    if (act.dataset.act === "via") {
      S.via = act.dataset.via === "desktop" ? "desktop" : "docker";
      const where = act.closest(".ex-via") ? ".ex-via" : ".ex-pick";
      saveVia(S.via); render();
      const again = $(`#view-exportar ${where} [data-act="via"][data-via="${S.via}"]`);
      if (again) again.focus();  // o redesenho troca o botao: o foco fica nele
      return;
    }
    if (act.dataset.act === "refresh") { S.loaded = null; S.loadError = null; refresh(); }
    if (act.dataset.act === "load") load();
    if (act.dataset.act === "again") { S.loaded = null; S.loadError = null; render(); }
  }

  function onInput(ev) {
    if (ev.target.id === "ex-confirm") { S.confirmed = ev.target.checked; render(); }
    if (ev.target.id === "ex-typed") {
      S.typed = ev.target.value;
      const db = S.status.database;
      const ok = S.typed.trim().replace(/\./g, "") === String(db.large_removal);
      const btn = $('#view-exportar [data-act="load"]');
      if (btn) btn.disabled = !(S.confirmed && ok && !S.running);  // sem redesenhar: o campo nao perde o foco
    }
  }

  function init(api) {
    S.api = api || null;
    const el = $("#view-exportar");
    if (el && !el.dataset.wired) {
      el.dataset.wired = "1";
      el.addEventListener("click", onClick);
      el.addEventListener("input", onInput);
      el.addEventListener("change", onInput);
    }
    render();
  }

  // chamada quando a aba abre: confere na primeira vez; depois, so pelo botao (a previa le todas as fontes)
  function show() {
    if (!S.opened) { S.opened = true; refresh(); } else render();
  }

  window.AkmeExport = { init, show };
})();
