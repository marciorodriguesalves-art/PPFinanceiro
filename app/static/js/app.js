/* Sistema de Controle Orçamentário — SPA (vanilla JS + Chart.js) */
"use strict";

const State = {
  token: localStorage.getItem("orc_token") || null,
  user: null,
  year: new Date().getFullYear(),
  month: new Date().getMonth() + 1,
  view: "dashboard",
  categories: [],
  charts: {},
};

const MONTHS = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
const PALETTE = ["#1466b8","#16b6cf","#0f4f90","#e4483b","#7c3aed","#0891b2","#db2777","#1a9e63","#ea580c","#0d9488","#4f46e5","#a16207"];
const CY = "#e4483b";      // ano atual (linha de destaque)
const PY = "#2f7fc0";      // ano anterior
const ACCENT = "#16b6cf";  // teal

/* ---------- utils ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
function brl(v) {
  return "R$ " + (Number(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function pct(v) { return v == null ? "-" : (Number(v) * 100).toFixed(1).replace(".", ",") + "%"; }
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function toast(msg, isErr = false) {
  const t = document.createElement("div");
  t.className = "toast" + (isErr ? " err" : "");
  t.textContent = msg;
  $("#toastRoot").appendChild(t);
  setTimeout(() => t.remove(), 3200);
}

async function api(path, { method = "GET", body = null, form = null } = {}) {
  const headers = {};
  if (State.token) headers["Authorization"] = "Bearer " + State.token;
  let payload = null;
  if (form) { payload = form; }
  else if (body != null) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const res = await fetch("/api" + path, { method, headers, body: payload });
  if (res.status === 401) { logout(); throw new Error("Sessão expirada"); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? (Array.isArray(data.detail) ? data.detail.map(d => d.msg).join("; ") : data.detail) : "Erro na requisição");
  return data;
}

/* ---------- auth ---------- */
async function doLogin(email, password) {
  const form = new URLSearchParams();
  form.set("username", email); form.set("password", password);
  const res = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Falha no login");
  State.token = data.access_token;
  localStorage.setItem("orc_token", State.token);
}
function logout() {
  State.token = null; State.user = null;
  localStorage.removeItem("orc_token");
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
}

/* ---------- boot ---------- */
async function boot() {
  try {
    State.user = await api("/auth/me");
  } catch { logout(); return; }
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#whoami").innerHTML = `<b>${esc(State.user.name)}</b><br><span class="muted">${esc(State.user.email)}</span>`;
  $("#navUsers").style.display = State.user.role === "admin" ? "" : "none";
  buildPeriod();
  State.categories = await api("/categories").catch(() => []);
  bindNav();
  go("dashboard");
}

function buildPeriod() {
  const my = $("#selMonth"), yy = $("#selYear");
  my.innerHTML = MONTHS.map((m, i) => `<option value="${i + 1}" ${i + 1 === State.month ? "selected" : ""}>${m}</option>`).join("");
  const y0 = new Date().getFullYear();
  yy.innerHTML = [y0 - 2, y0 - 1, y0, y0 + 1].map(y => `<option value="${y}" ${y === State.year ? "selected" : ""}>${y}</option>`).join("");
  my.onchange = () => { State.month = +my.value; go(State.view); };
  yy.onchange = () => { State.year = +yy.value; go(State.view); };
}

function bindNav() {
  document.querySelectorAll(".nav-item[data-view]").forEach(b => {
    b.onclick = () => go(b.dataset.view);
  });
  $("#logout").onclick = logout;
}

const TITLES = { laudo: "Laudo comportamental", dashboard: "Dashboard", gastos: "Gastos", goals: "Metas de gasto", categories: "Categorias", imports: "Importar dados", users: "Usuários" };

async function go(view) {
  State.view = view;
  document.querySelectorAll(".nav-item[data-view]").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $("#viewTitle").textContent = TITLES[view] || view;
  const scoped = !["categories", "users", "imports"].includes(view);
  $("#periodBox").style.display = scoped ? "flex" : "none";
  $("#viewSub").textContent = scoped ? `Competência ${MONTHS[State.month - 1]}/${State.year}` : "";
  const host = $("#view");
  host.innerHTML = '<div class="empty">Carregando…</div>';
  try {
    await VIEWS[view](host);
  } catch (e) { host.innerHTML = `<div class="empty">Erro: ${esc(e.message)}</div>`; }
}

function catName(id) { const c = State.categories.find(c => c.id === id); return c ? c.name : "—"; }
function catOptions(sel) {
  return `<option value="">— sem categoria —</option>` +
    State.categories.map(c => `<option value="${c.id}" ${c.id === sel ? "selected" : ""}>${esc(c.name)}</option>`).join("");
}
function chart(id, cfg) {
  const ctx = document.getElementById(id);
  if (!ctx) return;
  if (State.charts[id]) State.charts[id].destroy();
  State.charts[id] = new Chart(ctx, cfg);
}

/* ================= VIEWS ================= */
const VIEWS = {};

/* ----- Dashboard ----- */
const TREND_METRICS = {
  gastos: { label: "Gastos", good: "down" },
  receita: { label: "Receita", good: "up" },
  saldo: { label: "Saldo", good: "up" },
  investimento: { label: "Investimento", good: "up" },
};

VIEWS.dashboard = async (host) => {
  const [ov, serCY, serPY] = await Promise.all([
    api(`/dashboard/overview/${State.year}/${State.month}`),
    api(`/dashboard/series/${State.year}`),
    api(`/dashboard/series/${State.year - 1}`).catch(() => ({ pontos: [] })),
  ]);
  const k = ov.kpis;
  const m = State.month;
  // ponto do mês atual e do mês anterior (Dez do ano anterior quando m === 1)
  const cur = serCY.pontos[m - 1] || {};
  const prev = m >= 2 ? serCY.pontos[m - 2] : (serPY.pontos[11] || null);

  const invBadge = k.atende_meta_investimento ? '<span class="badge ok">Meta atingida</span>' : '<span class="badge bad">Abaixo da meta</span>';
  const invPctMeta = k.investimento_meta > 0 ? k.investimento_previsto / k.investimento_meta - 1 : null;

  host.innerHTML = `
    <div class="kpi-grid">
      ${kpiCard("Receita líquida", brl(k.receita_liquida), { accent: "accent",
        deltas: [deltaChip("vs mês ant.", cur.receita, prev && prev.receita, "up")] })}
      ${kpiCard("Gastos do mês", brl(k.total_gastos), {
        deltas: [deltaChip("vs mês ant.", cur.gastos, prev && prev.gastos, "down"),
                 `<span class="delta"><span class="cap">${pct(k.taxa_comprometimento)} da renda</span></span>`] })}
      ${kpiCard("Saldo disponível", brl(k.saldo_disponivel), { accent: k.saldo_disponivel >= 0 ? "good" : "bad",
        valueCls: k.saldo_disponivel >= 0 ? "pos" : "neg",
        deltas: [deltaChip("vs mês ant.", cur.saldo, prev && prev.saldo, "up")] })}
      ${kpiCard("Investimento previsto", brl(k.investimento_previsto), { accent: k.atende_meta_investimento ? "good" : "bad",
        valueCls: k.atende_meta_investimento ? "pos" : "neg",
        deltas: [deltaPct("vs meta", invPctMeta, "up")], sub: `Meta ${brl(k.investimento_meta)} ${invBadge}` })}
    </div>

    <div class="grid-3">
      <div class="card">
        <div class="chart-head">
          <div>
            <h3>Evolução mensal — ano atual vs anterior</h3>
            <p class="card-sub">Comparativo ${State.year} (CY) × ${State.year - 1} (PY)</p>
          </div>
          <div class="seg" id="trendSeg">
            ${Object.entries(TREND_METRICS).map(([kk, v], i) => `<button data-metric="${kk}" class="${i === 0 ? "active" : ""}">${v.label}</button>`).join("")}
          </div>
        </div>
        <div class="legend" style="margin-bottom:6px">
          <span><i class="dot cy"></i> ${State.year} (CY)</span>
          <span><i class="dot py"></i> ${State.year - 1} (PY)</span>
        </div>
        <div class="chart-wrap"><canvas id="cSeries" height="240"></canvas></div>
      </div>
      <div class="card">
        <h3>Composição dos gastos</h3>
        <p class="card-sub">Fixos · Variáveis · Cartão</p>
        <div class="chart-wrap"><canvas id="cComp" height="220"></canvas></div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3>Eficiência &amp; comprometimento</h3>
      <div class="stat-row" style="margin-top:14px">
        ${statTile("Comprometimento", pct(k.taxa_comprometimento))}
        ${statTile("Taxa de investimento", pct(k.taxa_investimento_prevista))}
        ${statTile("Meta de investimento", pct(k.investimento_meta / (k.receita_liquida || 1)))}
        ${statTile("Receita bruta", brl(k.receita_bruta))}
        ${statTile("Gastos fixos", brl(k.total_fixos))}
        ${statTile("Parcelas cartão", brl(k.total_parcelas))}
      </div>
    </div>

    <div class="grid-3" style="margin-top:16px">
      <div class="card"><h3>Gastos por categoria</h3><p class="card-sub">Top 8 do mês</p><div class="chart-wrap"><canvas id="cCat" height="240"></canvas></div></div>
      <div class="card"><h3>Plano de ação</h3><p class="card-sub">Ajustes priorizados</p><div id="planBox"></div></div>
    </div>`;

  // ---- Trend CY vs PY (com toggle de métrica) ----
  const labels = MONTHS;
  const renderTrend = (metric) => {
    const cy = Array.from({ length: 12 }, (_, i) => { const pt = serCY.pontos.find(x => x.mes === i + 1); return pt ? pt[metric] : null; });
    const py = Array.from({ length: 12 }, (_, i) => { const pt = serPY.pontos.find(x => x.mes === i + 1); return pt ? pt[metric] : null; });
    chart("cSeries", {
      type: "line",
      data: { labels, datasets: [
        { label: `${State.year}`, data: cy, borderColor: CY, backgroundColor: "transparent", tension: .4, borderWidth: 3, pointRadius: 3, pointBackgroundColor: CY },
        { label: `${State.year - 1}`, data: py, borderColor: PY, backgroundColor: "rgba(47,127,192,.10)", fill: true, tension: .4, borderWidth: 2.5, pointRadius: 3, pointBackgroundColor: PY },
      ] },
      options: baseOpts(),
    });
  };
  renderTrend("gastos");
  $("#trendSeg").querySelectorAll("button").forEach(b => b.onclick = () => {
    $("#trendSeg").querySelectorAll("button").forEach(x => x.classList.toggle("active", x === b));
    renderTrend(b.dataset.metric);
  });

  // ---- Composição (donut) ----
  const comp = ov.composicao.filter(c => c.value > 0);
  chart("cComp", {
    type: "doughnut",
    data: { labels: comp.map(c => c.label), datasets: [{ data: comp.map(c => c.value), backgroundColor: [PALETTE[0], ACCENT, PALETTE[3]], borderWidth: 2, borderColor: "#fff" }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: "62%",
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true } },
        tooltip: { callbacks: { label: c => `${c.label}: ${brl(c.raw)}` } } } },
  });

  // ---- Gastos por categoria (barra horizontal) ----
  const cats = ov.gastos_por_categoria.slice(0, 8);
  chart("cCat", {
    type: "bar",
    data: { labels: cats.map(c => c.category), datasets: [{ label: "Gasto", data: cats.map(c => c.amount), backgroundColor: PALETTE[0], borderRadius: 5, barThickness: 16 }] },
    options: barYOpts(false),
  });

  $("#planBox").innerHTML = renderPlan(ov.plano_acao);
};

/* wrapper simples usado por outras telas (ex.: Extrato mensal) */
function kpi(label, value, sub = null, cls = "") {
  return kpiCard(label, value, { sub, valueCls: cls });
}
function kpiCard(label, value, { sub = null, deltas = [], accent = "", valueCls = "" } = {}) {
  const chips = deltas.filter(Boolean).join("");
  return `<div class="card kpi ${accent}">
    <div class="label">${label}</div>
    <div class="value ${valueCls}">${value}</div>
    ${sub ? `<div class="sub">${sub}</div>` : ""}
    ${chips ? `<div class="deltas">${chips}</div>` : ""}
  </div>`;
}
function deltaChip(caption, current, previous, good = "up") {
  if (current == null || previous == null || previous === 0) return `<span class="delta"><span class="cap">${caption} —</span></span>`;
  const rate = (current - previous) / Math.abs(previous);
  return deltaPct(caption, rate, good);
}
function deltaPct(caption, rate, good = "up") {
  if (rate == null || !isFinite(rate)) return `<span class="delta"><span class="cap">${caption} —</span></span>`;
  const up = rate >= 0;
  const isGood = (good === "up") ? up : !up;
  const arrow = up ? "▲" : "▼";
  const sign = up ? "+" : "";
  return `<span class="delta ${isGood ? "up" : "down"}">${arrow} <b>${sign}${(rate * 100).toFixed(1).replace(".", ",")}%</b> <span class="cap">${caption}</span></span>`;
}
function statTile(label, value) {
  return `<div class="stat"><div class="s-label">${label}</div><div class="s-value">${value}</div></div>`;
}
function baseOpts() {
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: c => `${c.dataset.label}: ${brl(c.raw)}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: "#6b7a90" } },
      y: { grid: { color: "#eef2f7" }, border: { display: false }, ticks: { color: "#6b7a90", callback: v => "R$ " + v.toLocaleString("pt-BR") } },
    },
  };
}
/* opções para barras HORIZONTAIS (eixo de valor = x; categorias no y) */
function barYOpts(showLegend = false) {
  return {
    responsive: true, maintainAspectRatio: false, indexAxis: "y",
    plugins: {
      legend: showLegend ? { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true } } : { display: false },
      tooltip: { callbacks: { label: c => `${c.dataset.label ? c.dataset.label + ": " : ""}${brl(c.raw)}` } },
    },
    scales: {
      x: { grid: { color: "#eef2f7" }, border: { display: false }, ticks: { color: "#6b7a90", callback: v => "R$ " + v.toLocaleString("pt-BR") } },
      y: { grid: { display: false }, ticks: { color: "#6b7a90" } },
    },
  };
}
function renderPlan(plan) {
  let html = `<p style="font-size:13px;margin-top:0">${esc(plan.resumo)}</p>`;
  if (!plan.itens.length) return html + '<p class="muted">Sem ações pendentes. 👏</p>';
  html += plan.itens.map(it => {
    const cls = it.tipo === "comprometimento" ? "bad" : (it.tipo === "investimento" ? "warn" : "");
    return `<div class="plan-item"><div class="pri ${cls}">${it.prioridade}</div>
      <div class="txt"><span class="cat">${esc(it.categoria)}</span> — ${esc(it.mensagem)}
      ${it.valor_sugerido_corte > 0 ? `<br><span class="muted">Corte sugerido: <b>${brl(it.valor_sugerido_corte)}</b></span>` : ""}</div></div>`;
  }).join("");
  html += `<p style="margin-bottom:0"><b>Corte total sugerido:</b> ${brl(plan.corte_total_sugerido)} → saldo projetado ${brl(plan.saldo_projetado_pos_ajuste)}, investimento ${brl(plan.investimento_projetado_pos_ajuste)}.</p>`;
  return html;
}

/* ----- Extrato mensal ----- */
/* ----- Laudo — Finanças Comportamentais (estilo do laudo em PDF) ----- */
const CONF_LABEL = { alta: "CONFIANÇA ALTA", media: "CONFIANÇA MÉDIA", baixa: "CONFIANÇA BAIXA" };

VIEWS.laudo = async (host) => {
  const y = State.year, m = State.month;
  const periodo = `${y}-${String(m).padStart(2, "0")}`;
  const [diag, ov] = await Promise.all([
    api("/comportamental/diagnosticos", { method: "POST", body: { periodo, persistir: false } }),
    api(`/dashboard/overview/${y}/${m}`),
  ]);
  const k = ov.kpis;
  const cats = ov.gastos_por_categoria.filter(c => c.amount > 0);
  const maxCat = Math.max(1, ...cats.map(c => c.amount));
  const pctParcelas = k.total_gastos > 0 ? k.total_parcelas / k.total_gastos : 0;
  const ticket = diag.qtd_lancamentos > 0 ? k.total_gastos / diag.qtd_lancamentos : 0;

  host.innerHTML = `
    <div class="laudo">
      <div class="laudo-head">
        <div class="laudo-eyebrow">LAUDO · FINANÇAS COMPORTAMENTAIS</div>
        <h2>Revisor Comportamental de Gastos</h2>
        <div class="laudo-meta">Competência ${MONTHS[m - 1]}/${y} · ${diag.qtd_lancamentos} lançamento(s) analisados</div>
      </div>

      <div class="laudo-kpis">
        ${laudoTile(brl(k.total_gastos), "Total de gastos")}
        ${laudoTile(pct(pctParcelas), "Comprometido em parcelas")}
        ${laudoTile(String(diag.qtd_lancamentos), "Lançamentos")}
        ${laudoTile(brl(ticket), "Ticket médio")}
      </div>

      <div class="card">
        <h3>Para onde foi o dinheiro</h3>
        ${cats.length ? `<div class="laudo-bars">${cats.map(c => `
          <div class="lbar"><div class="lbar-name">${esc(c.category)}</div>
            <div class="lbar-track"><div class="lbar-fill" style="width:${Math.max(4, c.amount / maxCat * 100)}%"></div></div>
            <div class="lbar-val">${brl(c.amount)} <span class="muted">${pct(k.total_gastos ? c.amount / k.total_gastos : 0)}</span></div>
          </div>`).join("")}</div>` : '<div class="empty">Sem gastos nesta competência.</div>'}
      </div>

      <h3 class="laudo-sec">Diagnóstico — principais padrões</h3>
      ${diag.padroes.length ? diag.padroes.map((p, i) => `
        <div class="laudo-pattern conf-${p.confianca}">
          <div class="lp-head"><span class="lp-num">${i + 1}</span><span class="lp-title">${esc(p.titulo)}</span>
            <span class="conf-badge conf-${p.confianca}">${CONF_LABEL[p.confianca] || p.confianca}</span></div>
          <p class="lp-ev"><b>Evidência:</b> ${esc(p.evidencia)}</p>
          <p class="lp-bias"><b>Viés por trás:</b> ${esc(p.vies)}</p>
          <p class="lp-rec"><b>Recomendação:</b> ${esc(p.recomendacao)}</p>
        </div>`).join("") : '<div class="card"><div class="empty">Sem padrões relevantes nesta competência. Importe mais dados para um diagnóstico mais forte.</div></div>'}

      ${diag.ressalvas.length ? `<div class="card laudo-caveats"><h3>Ressalvas de honestidade</h3>
        <ul>${diag.ressalvas.map(r => `<li>${esc(r)}</li>`).join("")}</ul></div>` : ""}
    </div>`;
};
function laudoTile(value, label) {
  return `<div class="laudo-tile"><div class="lt-val">${value}</div><div class="lt-lbl">${label}</div></div>`;
}

/* ----- Gastos (tela consolidada: receitas + diários + fixas + parcelas, editável) ----- */
VIEWS.gastos = async (host) => {
  const y = State.year, m = State.month;
  const [rep, incomes, fixed, daily, insts] = await Promise.all([
    api(`/reports/monthly/${y}/${m}`),
    api(`/incomes?year=${y}&month=${m}`),
    fixedWithPayments(y, m),
    api(`/daily-expenses?year=${y}&month=${m}`),
    api(`/installments?active_year=${y}&active_month=${m}`),
  ]);
  const k = rep.kpis;
  host.innerHTML = `
    <div class="kpi-grid">
      ${kpi("Receita líquida", brl(k.receita_liquida))}
      ${kpi("Gastos", brl(k.total_gastos), `Fixos ${brl(k.total_fixos)} · Var ${brl(k.total_variaveis)} · Cartão ${brl(k.total_parcelas)}`)}
      ${kpi("Saldo", brl(k.saldo_disponivel), null, k.saldo_disponivel >= 0 ? "pos" : "neg")}
      ${kpi("Investimento", brl(k.investimento_previsto), `Meta ${brl(k.investimento_meta)}`, k.atende_meta_investimento ? "pos" : "neg")}
      ${kpi("Projeção economia 12m", brl(rep.projecao_economia_12m))}
    </div>
    <div class="grid-2">
      <div class="card"><h3>Resumo por categoria</h3><p class="card-sub">Gasto × meta</p><div class="chart-wrap sm"><canvas id="cMcat"></canvas></div></div>
      <div class="card"><h3>Plano de ação</h3><p class="card-sub">Ajustes priorizados</p>${renderPlan(rep.plano_acao)}</div>
    </div>

    ${crudSection("secIncome", CFG_INCOME, incomes, "💰 Receitas", "Você pode ter várias receitas por mês")}
    ${crudSection("secDaily", CFG_DAILY, daily, "🧾 Gastos diários", null)}

    <div class="card" id="secFixed" style="margin-top:16px">
      <div class="toolbar"><div><h3>📌 Despesas fixas</h3><p class="card-sub">Pagamento por competência (${MONTHS[m - 1]}/${y})</p></div><button class="btn addOne">+ Nova</button></div>
      ${tableFixedFull(fixed, y, m)}
    </div>

    ${crudSection("secInst", CFG_INST, insts, "💳 Parcelas do cartão", "Ativas nesta competência")}

    <div class="card" style="margin-top:16px"><h3>Desvios de meta</h3>${tableDeviations(rep.desvios)}</div>`;

  const cats = rep.gastos_por_categoria.slice(0, 10);
  chart("cMcat", {
    type: "bar",
    data: {
      labels: cats.map(c => c.category),
      datasets: [
        { label: "Gasto", data: cats.map(c => c.amount), backgroundColor: PALETTE[0], borderRadius: 4, barThickness: 12 },
        { label: "Meta", data: cats.map(c => c.target ?? 0), backgroundColor: "rgba(148,163,184,.55)", borderRadius: 4, barThickness: 12 },
      ],
    },
    options: barYOpts(true),
  });

  bindCrudSection("secIncome", CFG_INCOME, incomes);
  bindCrudSection("secDaily", CFG_DAILY, daily);
  bindCrudSection("secInst", CFG_INST, insts);
  const secFixed = document.getElementById("secFixed");
  secFixed.querySelector(".addOne").onclick = () => openForm(CFG_FIXED, null);
  secFixed.querySelectorAll(".editBtn").forEach(b => b.onclick = () => openForm(CFG_FIXED, fixed.find(r => r.id === +b.dataset.id)));
  secFixed.querySelectorAll(".delBtn").forEach(b => b.onclick = () => delRow(CFG_FIXED, +b.dataset.id));
  bindPayToggles(y, m);
};

/* Seção CRUD reutilizável dentro da tela consolidada (card + toolbar + tabela) */
function crudSection(id, cfg, rows, title, sub) {
  return `<div class="card" id="${id}" style="margin-top:16px">
    <div class="toolbar"><div><h3>${title}</h3>${sub ? `<p class="card-sub">${sub}</p>` : ""}</div><button class="btn addOne">+ Novo</button></div>
    ${rows.length ? cfg.table(rows) : '<div class="empty">Nenhum registro nesta competência.</div>'}
  </div>`;
}
function bindCrudSection(id, cfg, rows) {
  const root = document.getElementById(id);
  if (!root) return;
  const add = root.querySelector(".addOne");
  if (add) add.onclick = () => openForm(cfg, null);
  root.querySelectorAll(".editBtn").forEach(b => b.onclick = () => openForm(cfg, rows.find(r => r.id === +b.dataset.id)));
  root.querySelectorAll(".delBtn").forEach(b => b.onclick = () => delRow(cfg, +b.dataset.id));
}
/* Tabela de despesas fixas com baixa de pagamento + editar/excluir */
function tableFixedFull(rows, y, m) {
  if (!rows.length) return '<div class="empty">Nenhuma despesa fixa cadastrada.</div>';
  return `<table><thead><tr><th>Descrição</th><th>Categoria</th><th>Venc.</th><th class="num">Valor</th><th>Pagamento</th><th></th></tr></thead><tbody>
    ${rows.map(r => {
      const paid = r._pay && r._pay.paid;
      return `<tr><td>${esc(r.description)}</td><td>${esc(r.category ? r.category.name : catName(r.category_id))}</td>
        <td>${r.due_day ? "dia " + r.due_day : "—"}</td><td class="num">${brl(r.amount)}</td>
        <td>${paid ? `<span class="badge ok">Pago${r._pay.paid_date ? " " + fmtDate(r._pay.paid_date) : ""}</span>` : '<span class="badge warn">Pendente</span>'}
          <button class="btn sm ghost payToggle" data-id="${r.id}" data-paid="${paid ? 1 : 0}">${paid ? "Desmarcar" : "Marcar pago"}</button></td>
        <td>${actionBtns(r.id)}</td></tr>`;
    }).join("")}</tbody></table>`;
}

async function fixedWithPayments(y, m) {
  const list = await api("/fixed-expenses");
  await Promise.all(list.map(async fx => {
    const pays = await api(`/fixed-expenses/${fx.id}/payments`).catch(() => []);
    fx._pay = pays.find(p => p.year === y && p.month === m) || null;
  }));
  return list;
}
function tableIncomes(rows) {
  if (!rows.length) return '<div class="empty">Nenhuma receita lançada. Importe o contra cheque ou lance em "Receitas".</div>';
  return `<table><thead><tr><th>Descrição</th><th>Origem</th><th class="num">Bruto</th><th class="num">Líquido</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${esc(r.description)}</td><td class="muted">${esc(r.source || "")}</td><td class="num">${brl(r.gross_amount)}</td><td class="num">${brl(r.net_amount)}</td></tr>`).join("")}</tbody></table>`;
}
function tableFixed(rows, y, m) {
  if (!rows.length) return '<div class="empty">Nenhuma despesa fixa cadastrada.</div>';
  return `<table><thead><tr><th>Descrição</th><th>Categoria</th><th>Venc.</th><th class="num">Valor</th><th>Status</th><th></th></tr></thead><tbody>
    ${rows.filter(r => r.active).map(r => {
      const paid = r._pay && r._pay.paid;
      return `<tr><td>${esc(r.description)}</td><td>${esc(r.category ? r.category.name : catName(r.category_id))}</td>
        <td>${r.due_day ? "dia " + r.due_day : "—"}</td><td class="num">${brl(r.amount)}</td>
        <td>${paid ? `<span class="badge ok">Pago${r._pay.paid_date ? " " + fmtDate(r._pay.paid_date) : ""}</span>` : '<span class="badge warn">Pendente</span>'}</td>
        <td><button class="btn sm ghost payToggle" data-id="${r.id}" data-paid="${paid ? 1 : 0}">${paid ? "Desmarcar" : "Marcar pago"}</button></td></tr>`;
    }).join("")}</tbody></table>`;
}
function bindPayToggles(y, m) {
  document.querySelectorAll(".payToggle").forEach(b => {
    b.onclick = async () => {
      const paid = b.dataset.paid === "1";
      try {
        await api(`/fixed-expenses/${b.dataset.id}/payments`, { method: "POST", body: { year: y, month: m, paid: !paid, paid_date: !paid ? new Date().toISOString().slice(0, 10) : null } });
        toast(!paid ? "Pagamento registrado" : "Pagamento desmarcado");
        go(State.view);
      } catch (e) { toast(e.message, true); }
    };
  });
}
function tableInstMonth(rows, y, m) {
  if (!rows.length) return '<div class="empty">Sem parcelas ativas neste mês.</div>';
  return `<table><thead><tr><th>Descrição</th><th>Cartão</th><th>Parcela</th><th class="num">Valor</th></tr></thead><tbody>
    ${rows.map(r => {
      const n = instNumber(r, y, m);
      return `<tr><td>${esc(r.description)}</td><td class="muted">${esc(r.card || "")}</td><td>${n}/${r.installments_total}</td><td class="num">${brl(r.installment_amount)}</td></tr>`;
    }).join("")}</tbody></table>`;
}
function instNumber(r, y, m) { return (y - r.start_year) * 12 + (m - r.start_month) + 1; }
function tableDailyShort(rows) {
  if (!rows.length) return '<div class="empty">Nenhum lançamento diário no mês.</div>';
  const total = rows.reduce((s, r) => s + Number(r.amount), 0);
  return `<table><thead><tr><th>Data</th><th>Descrição</th><th>Categoria</th><th class="num">Valor</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${fmtDate(r.expense_date)}</td><td>${esc(r.description)}</td><td>${esc(r.category ? r.category.name : catName(r.category_id))}</td><td class="num">${brl(r.amount)}</td></tr>`).join("")}
    </tbody><tfoot><tr><th colspan="3">Total</th><th class="num">${brl(total)}</th></tr></tfoot></table>`;
}
function tableDeviations(rows) {
  if (!rows.length) return '<div class="empty">Nenhuma categoria acima da meta. 👏</div>';
  return `<table><thead><tr><th>Categoria</th><th class="num">Gasto</th><th class="num">Meta</th><th class="num">Desvio</th><th class="num">%</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${esc(r.category)}</td><td class="num">${brl(r.amount)}</td><td class="num">${brl(r.target)}</td><td class="num" style="color:var(--red)">${brl(r.deviation)}</td><td class="num">${pct(r.deviation_rate)}</td></tr>`).join("")}</tbody></table>`;
}
function fmtDate(d) { if (!d) return ""; const [y, m, dd] = d.split("-"); return `${dd}/${m}/${y}`; }

/* ----- Generic CRUD ----- */
function crudView(cfg) {
  return async (host) => {
    const params = cfg.periodScoped ? `?year=${State.year}&month=${State.month}` : "";
    const rows = await api(cfg.endpoint + params);
    host.innerHTML = `
      <div class="card">
        <div class="toolbar">
          <div class="muted">${rows.length} registro(s)${cfg.periodScoped ? ` · ${MONTHS[State.month - 1]}/${State.year}` : ""}</div>
          <button class="btn" id="addBtn">+ Novo</button>
        </div>
        ${rows.length ? cfg.table(rows) : '<div class="empty">Nenhum registro.</div>'}
      </div>`;
    $("#addBtn").onclick = () => openForm(cfg, null);
    host.querySelectorAll(".editBtn").forEach(b => b.onclick = () => openForm(cfg, rows.find(r => r.id === +b.dataset.id)));
    host.querySelectorAll(".delBtn").forEach(b => b.onclick = () => delRow(cfg, +b.dataset.id));
  };
}
async function delRow(cfg, id) {
  if (!confirm("Excluir este registro?")) return;
  try { await api(`${cfg.endpoint}/${id}`, { method: "DELETE" }); toast("Excluído"); go(State.view); }
  catch (e) { toast(e.message, true); }
}
function openForm(cfg, row) {
  const fields = cfg.fields(row);
  const body = fields.map(f => fieldHtml(f)).join("");
  const root = $("#modalRoot");
  root.innerHTML = `<div class="modal-bg"><div class="modal"><h3>${row ? "Editar" : "Novo"} — ${cfg.label}</h3>
    <form id="crudForm">${body}<div class="modal-actions"><button type="button" class="btn ghost" id="cancelBtn">Cancelar</button><button class="btn" type="submit">Salvar</button></div></form></div></div>`;
  $("#cancelBtn").onclick = () => root.innerHTML = "";
  $("#crudForm").onsubmit = async (e) => {
    e.preventDefault();
    const data = {};
    fields.forEach(f => {
      let v = $("#f_" + f.name).value;
      if (f.type === "number") v = v === "" ? null : Number(v);
      if (f.type === "checkbox") v = $("#f_" + f.name).checked;
      if (f.type === "select" && f.numeric) v = v === "" ? null : Number(v);
      if (v === "" && f.optional) v = null;
      data[f.name] = v;
    });
    try {
      if (row) await api(`${cfg.endpoint}/${row.id}`, { method: "PUT", body: data });
      else await api(cfg.endpoint, { method: "POST", body: data });
      root.innerHTML = ""; toast("Salvo"); go(State.view);
    } catch (err) { toast(err.message, true); }
  };
}
function fieldHtml(f) {
  const id = "f_" + f.name;
  if (f.type === "checkbox")
    return `<label style="display:flex;gap:8px;align-items:center;margin-top:14px"><input type="checkbox" id="${id}" ${f.value ? "checked" : ""} style="width:auto"> ${f.label}</label>`;
  if (f.type === "select")
    return `<label>${f.label}</label><select id="${id}">${f.options}</select>`;
  if (f.type === "textarea")
    return `<label>${f.label}</label><textarea id="${id}" rows="2">${esc(f.value ?? "")}</textarea>`;
  return `<label>${f.label}</label><input id="${id}" type="${f.type}" value="${esc(f.value ?? "")}" ${f.step ? `step="${f.step}"` : ""} ${f.min != null ? `min="${f.min}"` : ""}>`;
}

/* ----- CRUD configs (consts p/ reuso na tela consolidada de Gastos) ----- */
const CFG_DAILY = {
  label: "Gasto diário", endpoint: "/daily-expenses", periodScoped: true,
  table: rows => `<table><thead><tr><th>Data</th><th>Descrição</th><th>Categoria</th><th>Forma</th><th class="num">Valor</th><th></th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${fmtDate(r.expense_date)}</td><td>${esc(r.description)}</td><td>${esc(r.category ? r.category.name : catName(r.category_id))}</td><td>${esc(r.payment_method)}</td><td class="num">${brl(r.amount)}</td>
      <td>${actionBtns(r.id)}</td></tr>`).join("")}</tbody></table>`,
  fields: r => [
    { name: "expense_date", label: "Data", type: "date", value: r ? r.expense_date : new Date().toISOString().slice(0, 10) },
    { name: "description", label: "Descrição", type: "text", value: r?.description },
    { name: "category_id", label: "Categoria", type: "select", numeric: true, options: catOptions(r?.category_id) },
    { name: "amount", label: "Valor (R$)", type: "number", step: "0.01", min: 0, value: r?.amount },
    { name: "payment_method", label: "Forma de pagamento", type: "select", options: ["debito", "credito", "dinheiro", "pix", "boleto", "outro"].map(x => `<option ${r?.payment_method === x ? "selected" : ""}>${x}</option>`).join("") },
  ],
};

const CFG_FIXED = {
  label: "Despesa fixa", endpoint: "/fixed-expenses", periodScoped: false,
  table: rows => `<table><thead><tr><th>Descrição</th><th>Categoria</th><th>Venc.</th><th class="num">Valor</th><th>Ativa</th><th></th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${esc(r.description)}</td><td>${esc(r.category ? r.category.name : catName(r.category_id))}</td><td>${r.due_day ? "dia " + r.due_day : "—"}</td><td class="num">${brl(r.amount)}</td><td>${r.active ? '<span class="badge ok">sim</span>' : '<span class="badge">não</span>'}</td><td>${actionBtns(r.id)}</td></tr>`).join("")}</tbody></table>`,
  fields: r => [
    { name: "description", label: "Descrição", type: "text", value: r?.description },
    { name: "category_id", label: "Categoria", type: "select", numeric: true, options: catOptions(r?.category_id) },
    { name: "amount", label: "Valor (R$)", type: "number", step: "0.01", min: 0, value: r?.amount },
    { name: "due_day", label: "Dia do vencimento", type: "number", min: 1, value: r?.due_day, optional: true },
    { name: "active", label: "Ativa", type: "checkbox", value: r ? r.active : true },
  ],
};

const CFG_INST = {
  label: "Parcela de cartão", endpoint: "/installments", periodScoped: false,
  table: rows => `<table><thead><tr><th>Descrição</th><th>Cartão</th><th>Início</th><th>Parcelas</th><th class="num">Valor/mês</th><th></th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${esc(r.description)}</td><td>${esc(r.card || "")}</td><td>${String(r.start_month).padStart(2, "0")}/${r.start_year}</td><td>${r.installments_total}x</td><td class="num">${brl(r.installment_amount)}</td><td>${actionBtns(r.id)}</td></tr>`).join("")}</tbody></table>`,
  fields: r => [
    { name: "description", label: "Descrição", type: "text", value: r?.description },
    { name: "card", label: "Cartão", type: "text", value: r?.card, optional: true },
    { name: "category_id", label: "Categoria", type: "select", numeric: true, options: catOptions(r?.category_id) },
    { name: "installment_amount", label: "Valor da parcela (R$)", type: "number", step: "0.01", min: 0, value: r?.installment_amount },
    { name: "installments_total", label: "Total de parcelas", type: "number", min: 1, value: r?.installments_total ?? 1 },
    { name: "start_year", label: "Ano da 1ª parcela", type: "number", value: r?.start_year ?? State.year },
    { name: "start_month", label: "Mês da 1ª parcela", type: "number", min: 1, value: r?.start_month ?? State.month },
  ],
};

const CFG_INCOME = {
  label: "Receita", endpoint: "/incomes", periodScoped: true,
  table: rows => `<table><thead><tr><th>Competência</th><th>Descrição</th><th>Origem</th><th class="num">Bruto</th><th class="num">Líquido</th><th></th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${String(r.month).padStart(2, "0")}/${r.year}</td><td>${esc(r.description)}</td><td class="muted">${esc(r.source || "")}</td><td class="num">${brl(r.gross_amount)}</td><td class="num">${brl(r.net_amount)}</td><td>${actionBtns(r.id)}</td></tr>`).join("")}</tbody></table>`,
  fields: r => [
    { name: "year", label: "Ano", type: "number", value: r?.year ?? State.year },
    { name: "month", label: "Mês", type: "number", min: 1, value: r?.month ?? State.month },
    { name: "description", label: "Descrição", type: "text", value: r?.description ?? "Salário" },
    { name: "source", label: "Origem", type: "text", value: r?.source, optional: true },
    { name: "gross_amount", label: "Valor bruto (R$)", type: "number", step: "0.01", min: 0, value: r?.gross_amount },
    { name: "net_amount", label: "Valor líquido (R$)", type: "number", step: "0.01", min: 0, value: r?.net_amount },
  ],
};

const CFG_GOALS = {
  label: "Meta de gasto", endpoint: "/goals", periodScoped: false,
  table: rows => `<table><thead><tr><th>Categoria</th><th>Competência</th><th class="num">% da renda</th><th class="num">Valor teto</th><th></th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${esc(r.category ? r.category.name : catName(r.category_id))}</td><td>${r.year ? String(r.month).padStart(2, "0") + "/" + r.year : "padrão"}</td><td class="num">${r.target_rate != null ? pct(r.target_rate) : "—"}</td><td class="num">${r.target_amount != null ? brl(r.target_amount) : "—"}</td><td>${actionBtns(r.id)}</td></tr>`).join("")}</tbody></table>`,
  fields: r => [
    { name: "category_id", label: "Categoria", type: "select", numeric: true, options: State.categories.map(c => `<option value="${c.id}" ${r?.category_id === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("") },
    { name: "year", label: "Ano (0 = padrão p/ todo mês)", type: "number", value: r?.year ?? 0 },
    { name: "month", label: "Mês (0 = padrão)", type: "number", min: 0, value: r?.month ?? 0 },
    { name: "target_rate", label: "% da renda líquida (ex.: 0.08 = 8%)", type: "number", step: "0.0001", min: 0, value: r?.target_rate, optional: true },
    { name: "target_amount", label: "Valor teto (R$)", type: "number", step: "0.01", min: 0, value: r?.target_amount, optional: true },
  ],
};

VIEWS.categories = crudView({
  label: "Categoria", endpoint: "/categories", periodScoped: false,
  table: rows => `<table><thead><tr><th>Nome</th><th>Tipo</th><th class="num">Meta padrão</th><th></th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${esc(r.name)}</td><td>${esc(r.kind)}</td><td class="num">${r.default_target_rate != null ? pct(r.default_target_rate) : "—"}</td><td>${State.user.role === "admin" ? actionBtns(r.id) : ""}</td></tr>`).join("")}</tbody></table>`,
  fields: r => [
    { name: "name", label: "Nome", type: "text", value: r?.name },
    { name: "kind", label: "Tipo", type: "select", options: ["variavel", "fixa", "ambos"].map(x => `<option ${r?.kind === x ? "selected" : ""}>${x}</option>`).join("") },
    { name: "default_target_rate", label: "Meta padrão (% renda, ex.: 0.08)", type: "number", step: "0.0001", min: 0, value: r?.default_target_rate, optional: true },
  ],
});

function actionBtns(id) {
  return `<button class="btn sm ghost editBtn" data-id="${id}">Editar</button> <button class="btn sm danger delBtn" data-id="${id}">Excluir</button>`;
}

/* ----- Metas (sugeridas pelo diagnóstico + CRUD) ----- */
VIEWS.goals = async (host) => {
  const y = State.year, m = State.month;
  const periodo = `${y}-${String(m).padStart(2, "0")}`;
  const [goals, sug] = await Promise.all([
    api("/goals"),
    api(`/comportamental/metas-sugeridas/${periodo}`).catch(() => []),
  ]);
  const aplicaveis = sug.filter(s => s.category_id != null);
  host.innerHTML = `
    <div class="card">
      <div class="toolbar"><div><h3>Metas sugeridas pelo diagnóstico</h3>
        <p class="card-sub">Baseadas no gasto de ${MONTHS[m - 1]}/${y} — corte de 20% nas categorias de impulso. Edite o teto e aplique.</p></div>
        ${aplicaveis.length ? '<button class="btn" id="applyAll">Aplicar todas</button>' : ""}</div>
      ${aplicaveis.length ? `<table><thead><tr><th>Categoria</th><th class="num">Gasto atual</th><th class="num">Meta atual</th><th class="num">Teto sugerido (R$)</th><th>Motivo</th><th></th></tr></thead><tbody>
        ${aplicaveis.map(s => `<tr data-cat="${s.category_id}">
          <td>${esc(s.category)} ${s.impulso ? '<span class="badge warn">impulso</span>' : ""}</td>
          <td class="num">${brl(s.gasto_atual)}</td>
          <td class="num">${s.meta_atual != null ? brl(s.meta_atual) : "—"}</td>
          <td class="num"><input class="sugInput" type="number" step="0.01" min="0" value="${s.sugerido}" style="width:120px;text-align:right"></td>
          <td class="muted">${esc(s.motivo)}</td>
          <td><button class="btn sm applyOne">Aplicar</button></td></tr>`).join("")}</tbody></table>`
        : '<div class="empty">Sem sugestões: cadastre/importe gastos nesta competência para gerar propostas.</div>'}
    </div>

    ${crudSection("secGoals", CFG_GOALS, goals, "Minhas metas", "Metas por categoria (específicas do mês ou padrão)")}`;

  bindCrudSection("secGoals", CFG_GOALS, goals);

  const applyMeta = async (catId, value) => {
    const existing = goals.find(g => g.category_id === catId && g.year === 0 && g.month === 0);
    const body = { category_id: catId, year: 0, month: 0, target_amount: value, target_rate: null };
    if (existing) await api(`/goals/${existing.id}`, { method: "PUT", body });
    else await api("/goals", { method: "POST", body });
  };
  host.querySelectorAll(".applyOne").forEach(b => b.onclick = async () => {
    const tr = b.closest("tr");
    const catId = +tr.dataset.cat;
    const value = Number(tr.querySelector(".sugInput").value);
    try { await applyMeta(catId, value); toast("Meta aplicada"); go("goals"); }
    catch (e) { toast(e.message, true); }
  });
  const all = $("#applyAll");
  if (all) all.onclick = async () => {
    try {
      for (const tr of host.querySelectorAll("tr[data-cat]"))
        await applyMeta(+tr.dataset.cat, Number(tr.querySelector(".sugInput").value));
      toast("Metas aplicadas"); go("goals");
    } catch (e) { toast(e.message, true); }
  };
};

/* ----- Usuários (admin) ----- */
VIEWS.users = async (host) => {
  const rows = await api("/users");
  host.innerHTML = `<div class="card"><div class="toolbar"><div class="muted">${rows.length} usuário(s)</div><button class="btn" id="addU">+ Novo usuário</button></div>
    <table><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Ativo</th><th></th></tr></thead><tbody>
    ${rows.map(u => `<tr><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td><span class="badge role">${u.role}</span></td><td>${u.is_active ? "sim" : "não"}</td>
      <td><button class="btn sm ghost euser" data-id="${u.id}">Editar</button> <button class="btn sm danger duser" data-id="${u.id}">Excluir</button></td></tr>`).join("")}
    </tbody></table></div>`;
  $("#addU").onclick = () => userForm(null);
  host.querySelectorAll(".euser").forEach(b => b.onclick = () => userForm(rows.find(r => r.id === +b.dataset.id)));
  host.querySelectorAll(".duser").forEach(b => b.onclick = async () => {
    if (!confirm("Excluir usuário?")) return;
    try { await api(`/users/${b.dataset.id}`, { method: "DELETE" }); toast("Excluído"); go("users"); } catch (e) { toast(e.message, true); }
  });
};
function userForm(u) {
  const root = $("#modalRoot");
  root.innerHTML = `<div class="modal-bg"><div class="modal"><h3>${u ? "Editar" : "Novo"} usuário</h3><form id="uf">
    <label>Nome</label><input id="un" value="${esc(u?.name ?? "")}">
    <label>E-mail</label><input id="ue" type="email" value="${esc(u?.email ?? "")}">
    <label>Perfil</label><select id="ur"><option value="user" ${u?.role === "user" ? "selected" : ""}>Usuário</option><option value="admin" ${u?.role === "admin" ? "selected" : ""}>Administrador</option></select>
    <label>Senha ${u ? "(deixe em branco p/ manter)" : ""}</label><input id="up" type="password">
    <label style="display:flex;gap:8px;align-items:center;margin-top:14px"><input type="checkbox" id="ua" ${u ? (u.is_active ? "checked" : "") : "checked"} style="width:auto"> Ativo</label>
    <div class="modal-actions"><button type="button" class="btn ghost" id="uc">Cancelar</button><button class="btn" type="submit">Salvar</button></div></form></div></div>`;
  $("#uc").onclick = () => root.innerHTML = "";
  $("#uf").onsubmit = async (e) => {
    e.preventDefault();
    const data = { name: $("#un").value, email: $("#ue").value, role: $("#ur").value, is_active: $("#ua").checked };
    const pw = $("#up").value;
    if (pw) data.password = pw;
    try {
      if (u) await api(`/users/${u.id}`, { method: "PUT", body: data });
      else { if (!pw) throw new Error("Senha obrigatória"); await api("/users", { method: "POST", body: data }); }
      root.innerHTML = ""; toast("Salvo"); go("users");
    } catch (err) { toast(err.message, true); }
  };
}

/* ----- Importação ----- */
VIEWS.imports = async (host) => {
  host.innerHTML = `
    <div class="grid-2">
      <div class="card"><h3>📥 Importar fatura / extrato (CSV)</h3>
        <p class="muted">Fatura de cartão (ex.: Nubank <code>date,title,amount</code>) ou extrato de conta.
        Você pode selecionar <b>vários arquivos</b>. O <b>mês de cada lançamento vem da data no próprio arquivo</b>,
        então um arquivo pode ter vários meses — ideal para avaliar um ou mais meses de uma vez.</p>
        <form id="fStmt">
          <label>Layout</label><select id="sl"><option value="auto">Detectar automaticamente</option><option value="cartao">Fatura de cartão</option><option value="extrato">Extrato de conta</option></select>
          <label style="display:flex;gap:8px;align-items:center;margin-top:12px"><input type="checkbox" id="sci" checked style="width:auto"> Criar parcelas a partir de "Parcela X/Y"</label>
          <label>Arquivos CSV (um ou vários)</label><input type="file" id="sf" accept=".csv,text/csv" multiple required>
          <details style="margin-top:10px"><summary class="muted" style="cursor:pointer">Opções avançadas</summary>
            <p class="muted" style="margin:8px 0 4px">Competência de referência (usada só para linhas sem data):</p>
            <div class="row"><div><label>Ano</label><input type="number" id="sy" value="${State.year}"></div>
            <div><label>Mês</label><input type="number" id="sm" min="1" max="12" value="${State.month}"></div></div>
          </details>
          <button class="btn" type="submit" style="margin-top:14px">Importar</button>
        </form>
        <div id="sres" class="muted" style="margin-top:12px"></div>
      </div>
      <div class="card"><h3>💰 Importar contra cheque (CSV)</h3>
        <p class="muted">Formato <code>descricao,tipo,valor</code> (tipo = provento/desconto) ou colunas <code>bruto,liquido</code>.</p>
        <form id="fPay">
          <div class="row"><div><label>Ano</label><input type="number" id="py" value="${State.year}"></div>
          <div><label>Mês</label><input type="number" id="pm" min="1" max="12" value="${State.month}"></div></div>
          <label>Descrição</label><input id="pd" value="Salário">
          <label>Arquivo CSV</label><input type="file" id="pf" accept=".csv,text/csv" required>
          <button class="btn" type="submit" style="margin-top:14px">Importar</button>
        </form>
        <div id="pres" class="muted" style="margin-top:12px"></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px"><h3>Modelos de arquivo</h3>
      <p class="muted">Baixe exemplos para conferir o formato aceito:</p>
      <p><a href="/static/samples/fatura_nubank_exemplo.csv" download>fatura_nubank_exemplo.csv</a> ·
         <a href="/static/samples/extrato_exemplo.csv" download>extrato_exemplo.csv</a> ·
         <a href="/static/samples/contra_cheque_exemplo.csv" download>contra_cheque_exemplo.csv</a></p>
    </div>`;

  $("#fStmt").onsubmit = async (e) => {
    e.preventDefault();
    const files = Array.from($("#sf").files);
    if (!files.length) return;
    $("#sres").innerHTML = `Importando ${files.length} arquivo(s)…`;
    const out = [];
    for (const file of files) {
      const fd = new FormData();
      fd.set("year", $("#sy").value); fd.set("month", $("#sm").value);
      fd.set("layout", $("#sl").value); fd.set("create_installments", $("#sci").checked);
      fd.set("file", file);
      try {
        const r = await api("/imports/statement", { method: "POST", form: fd });
        out.push(`<div>✅ <b>${esc(file.name)}</b> — ${r.lancamentos_criados} lançamento(s), ${r.parcelas_criadas} parcela(s), ${r.ignorados_duplicados} ignorado(s). Meses: <b>${r.competencias.join(", ") || "—"}</b>. Total ${brl(r.total_importado)}.</div>`);
      } catch (err) {
        out.push(`<div style="color:var(--red)">✖ ${esc(file.name)}: ${esc(err.message)}</div>`);
      }
    }
    State.categories = await api("/categories");
    $("#sres").innerHTML = out.join("");
    toast("Importação concluída");
  };
  $("#fPay").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData();
    fd.set("year", $("#py").value); fd.set("month", $("#pm").value);
    fd.set("description", $("#pd").value); fd.set("file", $("#pf").files[0]);
    try {
      const r = await api("/imports/payslip", { method: "POST", form: fd });
      $("#pres").innerHTML = `✅ Receita ${r.criado ? "criada" : "atualizada"} para ${String(r.month).padStart(2, "0")}/${r.year}: bruto ${brl(r.gross_amount)}, líquido <b>${brl(r.net_amount)}</b>.`;
      toast("Contra cheque importado");
    } catch (err) { $("#pres").innerHTML = `<span style="color:var(--red)">${esc(err.message)}</span>`; }
  };
};

/* ---------- init ---------- */
$("#loginForm").onsubmit = async (e) => {
  e.preventDefault();
  $("#loginErr").textContent = "";
  try { await doLogin($("#email").value, $("#password").value); await boot(); }
  catch (err) { $("#loginErr").textContent = err.message; }
};

if (State.token) boot();
