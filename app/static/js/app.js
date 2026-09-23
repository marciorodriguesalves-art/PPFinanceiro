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
const PALETTE = ["#2563eb","#16a34a","#d97706","#dc2626","#7c3aed","#0891b2","#db2777","#65a30d","#ea580c","#0d9488","#4f46e5","#a16207"];

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

const TITLES = { dashboard: "Dashboard", monthly: "Extrato mensal", daily: "Gastos diários", fixed: "Despesas fixas", installments: "Parcelas do cartão", incomes: "Receitas", goals: "Metas de gasto", categories: "Categorias", imports: "Importar dados", users: "Usuários" };

async function go(view) {
  State.view = view;
  document.querySelectorAll(".nav-item[data-view]").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $("#viewTitle").textContent = TITLES[view] || view;
  $("#periodBox").style.display = ["categories", "users", "imports"].includes(view) ? "none" : "flex";
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
VIEWS.dashboard = async (host) => {
  const [ov, ser] = await Promise.all([
    api(`/dashboard/overview/${State.year}/${State.month}`),
    api(`/dashboard/series/${State.year}`),
  ]);
  const k = ov.kpis;
  const invBadge = k.atende_meta_investimento ? '<span class="badge ok">Meta atingida</span>' : '<span class="badge bad">Abaixo da meta</span>';
  host.innerHTML = `
    <div class="kpi-grid">
      ${kpi("Receita líquida", brl(k.receita_liquida))}
      ${kpi("Gastos do mês", brl(k.total_gastos), `${pct(k.taxa_comprometimento)} da renda`)}
      ${kpi("Saldo disponível", brl(k.saldo_disponivel), null, k.saldo_disponivel >= 0 ? "pos" : "neg")}
      ${kpi("Investimento previsto", brl(k.investimento_previsto), `Meta: ${brl(k.investimento_meta)} ${invBadge}`, k.atende_meta_investimento ? "pos" : "neg")}
    </div>
    <div class="grid-3">
      <div class="card"><h3>Evolução anual — ${State.year}</h3><canvas id="cSeries" height="120"></canvas></div>
      <div class="card"><h3>Composição do mês</h3><canvas id="cComp" height="120"></canvas></div>
    </div>
    <div class="grid-3" style="margin-top:16px">
      <div class="card"><h3>Gastos por categoria</h3><canvas id="cCat" height="120"></canvas></div>
      <div class="card"><h3>Plano de ação</h3><div id="planBox"></div></div>
    </div>`;

  const p = ser.pontos;
  chart("cSeries", {
    type: "line",
    data: {
      labels: p.map(x => MONTHS[x.mes - 1]),
      datasets: [
        { label: "Receita", data: p.map(x => x.receita), borderColor: PALETTE[1], backgroundColor: "transparent", tension: .3 },
        { label: "Gastos", data: p.map(x => x.gastos), borderColor: PALETTE[3], backgroundColor: "transparent", tension: .3 },
        { label: "Saldo", data: p.map(x => x.saldo), borderColor: PALETTE[0], backgroundColor: "rgba(37,99,235,.08)", fill: true, tension: .3 },
      ],
    },
    options: baseOpts(),
  });
  const comp = ov.composicao.filter(c => c.value > 0);
  chart("cComp", {
    type: "doughnut",
    data: { labels: comp.map(c => c.label), datasets: [{ data: comp.map(c => c.value), backgroundColor: PALETTE.slice(0, comp.length) }] },
    options: { plugins: { legend: { position: "bottom" } } },
  });
  const cats = ov.gastos_por_categoria.slice(0, 8);
  chart("cCat", {
    type: "bar",
    data: { labels: cats.map(c => c.category), datasets: [{ label: "Gasto", data: cats.map(c => c.amount), backgroundColor: PALETTE[0] }] },
    options: { ...baseOpts(), indexAxis: "y", plugins: { legend: { display: false } } },
  });
  $("#planBox").innerHTML = renderPlan(ov.plano_acao);
};

function kpi(label, value, sub = null, cls = "") {
  return `<div class="card kpi"><div class="label">${label}</div><div class="value ${cls}">${value}</div>${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;
}
function baseOpts() {
  return { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } },
    scales: { y: { ticks: { callback: v => "R$ " + v.toLocaleString("pt-BR") } } } };
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
VIEWS.monthly = async (host) => {
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
      <div class="card"><h3>Resumo por categoria</h3><canvas id="cMcat" height="150"></canvas></div>
      <div class="card"><h3>Plano de ação inteligente</h3>${renderPlan(rep.plano_acao)}</div>
    </div>

    <div class="card" style="margin-top:16px"><h3>Receitas (contra cheque)</h3>${tableIncomes(incomes)}</div>

    <div class="card" style="margin-top:16px"><h3>Despesas fixas</h3>${tableFixed(fixed, y, m)}</div>

    <div class="card" style="margin-top:16px"><h3>Parcelas ativas no mês</h3>${tableInstMonth(insts, y, m)}</div>

    <div class="card" style="margin-top:16px"><h3>Lançamentos diários</h3>${tableDailyShort(daily)}</div>

    <div class="card" style="margin-top:16px"><h3>Desvios de meta</h3>${tableDeviations(rep.desvios)}</div>`;

  const cats = rep.gastos_por_categoria.slice(0, 10);
  chart("cMcat", {
    type: "bar",
    data: {
      labels: cats.map(c => c.category),
      datasets: [
        { label: "Gasto", data: cats.map(c => c.amount), backgroundColor: PALETTE[0] },
        { label: "Meta", data: cats.map(c => c.target ?? 0), backgroundColor: "rgba(148,163,184,.5)" },
      ],
    },
    options: { ...baseOpts(), indexAxis: "y" },
  });

  bindPayToggles(y, m);
};

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
        go("monthly");
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

/* ----- CRUD configs ----- */
VIEWS.daily = crudView({
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
});

VIEWS.fixed = crudView({
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
});

VIEWS.installments = crudView({
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
});

VIEWS.incomes = crudView({
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
});

VIEWS.goals = crudView({
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
});

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
        <p class="muted">Fatura de cartão (ex.: Nubank <code>date,title,amount</code>) ou extrato de conta. Detecta parcelas automaticamente.</p>
        <form id="fStmt">
          <div class="row"><div><label>Ano</label><input type="number" id="sy" value="${State.year}"></div>
          <div><label>Mês</label><input type="number" id="sm" min="1" max="12" value="${State.month}"></div></div>
          <label>Layout</label><select id="sl"><option value="auto">Detectar automaticamente</option><option value="cartao">Fatura de cartão</option><option value="extrato">Extrato de conta</option></select>
          <label style="display:flex;gap:8px;align-items:center;margin-top:12px"><input type="checkbox" id="sci" checked style="width:auto"> Criar parcelas a partir de "Parcela X/Y"</label>
          <label>Arquivo CSV</label><input type="file" id="sf" accept=".csv,text/csv" required>
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
    const fd = new FormData();
    fd.set("year", $("#sy").value); fd.set("month", $("#sm").value);
    fd.set("layout", $("#sl").value); fd.set("create_installments", $("#sci").checked);
    fd.set("file", $("#sf").files[0]);
    try {
      const r = await api("/imports/statement", { method: "POST", form: fd });
      $("#sres").innerHTML = `✅ Layout <b>${r.layout}</b> · ${r.lancamentos_criados} lançamento(s), ${r.parcelas_criadas} parcela(s), ${r.ignorados_duplicados} duplicado(s) ignorado(s). Total: <b>${brl(r.total_importado)}</b>.`;
      State.categories = await api("/categories");
      toast("Importação concluída");
    } catch (err) { $("#sres").innerHTML = `<span style="color:var(--red)">${esc(err.message)}</span>`; }
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
