/* 零售经营决策 Agent Console — shadcn/ui 浅色 · 无障碍/动效/响应式精修版
   范围：R1-R5 —— 多系统接入 / 自动发现异常 / 根因分析 / 补货·促销建议 / 授权执行 */
const API = "/api";
const CORE_ACTIONS = new Set(["replenish", "promo"]);
const REDUCED = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
const $ = (sel) => document.querySelector(sel);
const main = () => $("#main");

/* ── 线条图标系统：与侧栏同一 stroke=1.8 语言，全站替代 emoji ── */
const ICONS = {
  scan: '<circle cx="12" cy="12" r="7.5"/><path d="M12 1.8v3M12 19.2v3M1.8 12h3M19.2 12h3"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
  bolt: '<path d="M13 2.5 5 13.5h5.5L10 21.5l8-11h-5.5L13 2.5z"/>',
  play: '<path d="M7 4.8v14.4L19.5 12 7 4.8z"/>',
  down: '<path d="M22 17l-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
  up: '<path d="M22 7l-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.4 2.1L8 10a16 16 0 0 0 6 6l1.3-1.35a2 2 0 0 1 2.1-.45c.9.3 1.9.55 2.8.7a2 2 0 0 1 1.8 2z"/>',
  box: '<path d="M21 8.2 12 3 3 8.2v7.6L12 21l9-5.2V8.2z"/><path d="M3 8.2l9 5.2 9-5.2"/><path d="M12 13.4V21"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.8"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/>',
  search: '<circle cx="11" cy="11" r="7.5"/><path d="M21.3 21.3l-5.4-5.4"/>',
  bulb: '<path d="M9.5 18h5M10.2 21h3.6M12 3a6 6 0 0 0-3.6 10.8c.9.7 1.6 1.3 1.6 2.2h4c0-.9.7-1.5 1.6-2.2A6 6 0 0 0 12 3z"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="M8.3 12.4l2.5 2.5 4.9-5.3"/>',
  gear: '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.9M12 18.3v2.9M2.8 12h2.9M18.3 12h2.9M5.4 5.4l2 2M16.6 16.6l2 2M18.6 5.4l-2 2M7.4 16.6l-2 2"/>',
  doc: '<path d="M6 2h9l4 4v16H6V2z"/><path d="M9 12h7M9 16h7M9 8h3"/>',
  moon: '<path d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11z"/>',
};
function icon(name, size) {
  size = size || 16;
  return '<svg class="ic" viewBox="0 0 24 24" width="' + size + '" height="' + size +
    '" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
    (ICONS[name] || "") + "</svg>";
}
function acell(icName, label, size) {
  return '<span class="acell">' + icon(icName, size || 15) + esc(label) + "</span>";
}

function snapPath(path) {
  const p = path.split("?")[0];
  const q = path.split("?")[1];
  const qs = q ? "-" + q.replace(/[^a-z0-9]/gi, "") : "";
  return "snapshot/" + p.replace(/^\/(api\/)?/, "").replace(/\//g, "-") + qs + ".json";
}
async function fetchJSON(path) {
  try {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(String(r.status));
    if (!window.__static) return await r.json();
    throw new Error("static");
  } catch (e) {
    if (!window.__static) { window.__static = true; document.body.classList.add("static-mode"); }
    const r2 = await fetch(snapPath(path));
    if (!r2.ok) throw new Error("snapshot missing: " + path);
    return await r2.json();
  }
}
function staticReadonly() {
  if (window.__static) { toast("静态快照预览为只读 —— 完整交互请本地运行后端", false); return true; }
  return false;
}
async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: headers(), ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}
function token() { return $("#role-select").value; }
function headers() { return { "X-Auth-Token": token(), "Content-Type": "application/json" }; }
function toast(msg, ok = true) {
  const t = $("#toast");
  t.style.display = "block";
  t.style.background = ok ? "var(--primary)" : "var(--danger)";
  t.textContent = msg;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.display = "none"; }, 4200);
}
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function badge(text, cls) { return '<span class="badge ' + (cls || text) + '">' + esc(text) + '</span>'; }
function money(v) { return v == null ? "-" : "\u00a5" + Number(v).toLocaleString("zh-CN", { maximumFractionDigits: 0 }); }
function fmtNum(v, fmt) {
  if (fmt === "money") return money(v);
  if (fmt === "pct") return (Math.round(v * 100) / 100) + "%";
  return Math.round(v).toLocaleString("zh-CN");
}
/* 计数动画占位：data-cnt 终值 + data-fmt 格式，由 animateCounters 在挂载后驱动 */
function cnt(n, fmt) {
  if (n == null || isNaN(Number(n))) return '<span class="cnt">-</span>';
  return '<span class="cnt" data-cnt="' + Number(n) + '" data-fmt="' + (fmt || "int") + '"></span>';
}
function emptyState(icName, text, action) {
  return '<div class="empty-state"><div class="glyph">' + icon(icName, 26) + '</div><div>' + esc(text) + "</div>" +
    (action ? '<div class="actions-row" style="justify-content:center">' + action + "</div>" : "") + "</div>";
}
function card(title, body, desc, actions, flush) {
  desc = desc || ""; actions = actions || "";
  return '<section class="card">' + (title ?
    '<div class="card-head"><div><div class="card-title">' + title + "</div>" +
    (desc ? '<div class="card-desc">' + desc + "</div>" : "") + "</div><div>" + actions + "</div></div>" : "") +
    '<div class="card-body' + (flush ? " flush" : "") + '">' + body + "</div></section>";
}
function kpi(label, value, unit, delta, color, spark) {
  return '<div class="card kpi-card"><div class="label">' + label + "</div>" +
    '<div class="value"' + (color ? ' style="color:' + color + '"' : "") + ">" + value +
    (unit ? '<span class="unit">' + unit + "</span>" : "") + "</div>" +
    '<div class="delta">' + (delta || "") + '</div><div class="spark">' + (spark || "") + "</div></div>";
}
function sparkline(data, color, w) {
  color = color || "#4f46e5";
  w = w || 118;
  if (!data || data.length < 2) return "";
  const h = w > 160 ? 44 : 26, min = Math.min.apply(null, data), max = Math.max.apply(null, data);
  const x = (i) => i * w / (data.length - 1);
  const y = (v) => h - 2 - ((v - min) / (max - min || 1)) * (h - 4);
  const pts = data.map((v, i) => x(i).toFixed(1) + "," + y(v).toFixed(1)).join(" ");
  return '<svg class="spark-svg" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + " " + h + '" aria-hidden="true">' +
    '<polyline class="spark-line" points="' + pts + '" fill="none" stroke="' + color + '" stroke-width="1.6"/>' +
    '<circle cx="' + w + '" cy="' + y(data[data.length - 1]) + '" r="2.3" fill="' + color + '"/></svg>';
}
/* 趋势图：等比缩放（无 preserveAspectRatio:none 变形），附带十字准线/tooltip 所需元数据 */
function chartHtml(points, color) {
  color = color || "#4f46e5";
  if (!points.length) return '<div class="empty">暂无数据</div>';
  const w = 640, h = 210, padL = 54, padR = 14, padT = 14, padB = 26;
  const xs = points.map((p, i) => padL + i * (w - padL - padR) / Math.max(1, points.length - 1));
  const ys = points.map(p => p[1]);
  const min = Math.min.apply(null, ys) * 0.96, max = Math.max.apply(null, ys) * 1.04;
  const py = (v) => padT + (1 - (v - min) / (max - min || 1)) * (h - padT - padB);
  const path = points.map((p, i) => (i ? "L" : "M") + xs[i].toFixed(1) + "," + py(p[1]).toFixed(1)).join(" ");
  const area = path + " L" + xs[xs.length - 1] + "," + (h - padB) + " L" + padL + "," + (h - padB) + " Z";
  let ticks = "";
  [0, 0.25, 0.5, 0.75, 1].forEach(t => {
    const v = min + (max - min) * (1 - t), y = padT + t * (h - padT - padB);
    ticks += '<line x1="' + padL + '" y1="' + y + '" x2="' + (w - padR) + '" y2="' + y + '" stroke="#f1f5f9"/>' +
      '<text x="' + (padL - 6) + '" y="' + (y + 3) + '" text-anchor="end" class="chart-tip">' + money(v) + "</text>";
  });
  const step = Math.ceil(points.length / 8);
  let labels = "";
  points.forEach((p, i) => { if (i % step === 0) {
    labels += '<text x="' + xs[i] + '" y="' + (h - 7) + '" text-anchor="middle" class="chart-tip">' + p[0] + "</text>";
  }});
  const meta = points.map((p, i) =>
    xs[i].toFixed(1) + "|" + py(p[1]).toFixed(1) + "|" + String(p[0]) + "|" + p[1]).join(";");
  const svg = '<svg class="chart" viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="销售额趋势图">' +
    '<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0" stop-color="' + color + '" stop-opacity=".18"/><stop offset="1" stop-color="' + color + '" stop-opacity="0"/></linearGradient></defs>' +
    ticks + '<path class="chart-area" d="' + area + '" fill="url(#cg)"/>' +
    '<path class="chart-line" d="' + path + '" fill="none" stroke="' + color + '" stroke-width="2"/>' +
    '<line class="xhair" x1="0" x2="0" y1="' + padT + '" y2="' + (h - padB) + '"/>' +
    '<circle class="xdot" r="0" cx="0" cy="0" stroke="' + color + '" stroke-width="2"/>' +
    labels + "</svg>";
  return '<div class="chart-box" data-pts="' + esc(meta) + '">' + svg + '<div class="tipbox"></div></div>';
}
async function refreshBadges() {
  try {
    const ov = await fetchJSON("/kpi/overview");
    const decisions = await fetchJSON("/agent/decisions?limit=100");
    $("#biz-date").textContent = "业务日期 " + ov.biz_date;
    setBadge("#badge-anomaly", ov.anomalies_open, false);
    setBadge("#badge-approval", ov.approvals_pending, true);
    const suggested = decisions.items.filter(d => d.status === "suggested" || d.status === "pending_approval").length;
    setBadge("#badge-decision", suggested, true);
  } catch (e) { /* silent */ }
}
function setBadge(sel, n, warn) {
  const el = $(sel);
  if (!el) return;
  if (n > 0) { el.textContent = n > 99 ? "99+" : n; el.classList.add("show"); el.classList.toggle("warn", !!warn); }
  else el.classList.remove("show");
}
const ANOMALY_META = {
  sales_drop: { ic: "down", label: "销量下降" },
  sales_surge: { ic: "up", label: "销量上升" },
  complaint_surge: { ic: "phone", label: "客诉上升" },
};
function anomalyName(t) {
  const m = ANOMALY_META[t];
  return m ? acell(m.ic, m.label) : esc(t);
}
function devBar(pct) {
  const mag = Math.min(100, Math.abs(pct));
  const color = Math.abs(pct) >= 80 ? "var(--danger)" : Math.abs(pct) >= 50 ? "var(--warning)" : "var(--accent)";
  return '<div class="devbar"><span class="num ' + (pct < 0 ? "down" : "up") + '" style="font-weight:700">' + pct +
    '%</span><span class="track"><span class="fill" style="width:' + mag + "%;background:" + color + '"></span></span></div>';
}
function anomalyTable(items, withWrapper) {
  if (!items.length) {
    return emptyState("moon", "暂无异常 —— 点击右上角「扫描异常」或「运行 Agent」",
      '<button class="btn sm primary" onclick="runPipeline(document.getElementById(\'btn-pipeline\'))">' +
      icon("bolt", 13) + " 运行 Agent</button>");
  }
  const rows = items.map(a =>
    '<tr class="clickable" tabindex="0" role="link" data-href="#/anomaly/' + a.id + '" aria-label="查看异常详情 ' + esc(a.id) + '">' +
    '<td data-th="严重度">' + badge(a.severity) + "</td>" +
    '<td data-th="类型">' + anomalyName(a.type) + "</td>" +
    '<td data-th="门店 / 商品">' + esc(a.store_name || a.store_id) + ' <span class="mono">' + esc(a.product_id) + "</span></td>" +
    '<td data-th="观察 / 期望" class="num" style="text-align:right">' + a.observed + " / " + a.expected + "</td>" +
    '<td data-th="偏差">' + devBar(a.deviation_pct) + "</td>" +
    '<td data-th="时间窗口" class="mono">' + a.window_start.slice(5) + " ~ " + a.window_end.slice(5) + "</td>" +
    '<td data-th="状态">' + badge(a.status) + "</td></tr>").join("");
  const inner = "<table><thead><tr><th>严重度</th><th>类型</th><th>门店 / 商品</th>" +
    '<th style="text-align:right">观察 / 期望</th><th style="text-align:right">偏差</th><th>时间窗口</th><th>状态</th></tr></thead><tbody>' +
    rows + "</tbody></table>";
  return withWrapper ? '<div class="table-wrap">' + inner + "</div>" : inner;
}
async function pageOverview() {
  const days = 30;
  const ov = await fetchJSON("/kpi/overview");
  const trend = await fetchJSON("/kpi/trend?days=" + days);
  const anomalies = await fetchJSON("/agent/anomalies?limit=8");
  const stores = await fetchJSON("/kpi/stores?limit=10");
  const decisions = await fetchJSON("/agent/decisions?limit=100");
  const dcnt = decisions.items.filter(d => CORE_ACTIONS.has(d.action_type)).length;
  const mom = ov.sales_mom_pct;
  const sparks = trend.items.slice(-14);
  const hero =
    '<section class="hero">' +
      '<div class="hero-left">' +
        '<div class="hero-kicker">今日经营 · Overview</div>' +
        '<div class="hero-value"><span class="hero-num">' + cnt(ov.sales_7d, "money") + "</span>" +
          '<span class="hero-unit">近 7 天销售额 · 全部门店</span></div>' +
        '<div class="hero-delta">' + (mom == null ? "" :
          '<span class="' + (mom >= 0 ? "up" : "down") + '">' + (mom >= 0 ? "\u25b2" : "\u25bc") + " " + mom + "% 环比上周</span>") + "</div>" +
        '<div class="hero-summary"><span class="sdot"></span>AI 经营摘要：<b>' + ov.anomalies_open + "</b> 个待处理异常 · 已生成 <b>" +
          dcnt + "</b> 条补货/促销建议 · 待审批 <b>" + ov.approvals_pending + "</b> 项</div>" +
      "</div>" +
      '<div class="hero-side"><div class="hint">近 14 天销售额走势</div>' +
        sparkline(sparks.map(x => x.amount), "#4f46e5", 230) + "</div>" +
    "</section>";
  return hero +
    '<div class="grid kpi">' +
    kpi("销量 · 近7天", cnt(ov.qty_7d), "件", "", "",
      sparkline(sparks.map(x => x.qty), "#059669")) +
    kpi("毛利率", ov.gross_margin_rate == null ? "-" : cnt(ov.gross_margin_rate, "pct")) +
    kpi("待处理异常", cnt(ov.anomalies_open), "", '<span class="hint">自动发现</span>',
      ov.anomalies_open > 0 ? "var(--danger)" : "") +
    kpi("待审批", cnt(ov.approvals_pending), "", '<span class="hint">高风险动作 · 人工确认</span>',
      ov.approvals_pending > 0 ? "var(--warning-strong)" : "") +
    kpi("已执行动作", cnt(ov.executed_actions), "", '<span class="up">授权范围内执行</span>') +
    "</div>" +
    '<div class="grid two">' +
    card("销售额趋势", chartHtml(trend.items.map(x => [x.date.slice(5), x.amount])), "最近 " + days + " 天 · 全部门店") +
    card("门店销售额排行 · 近7天", "<table><thead><tr><th>#</th><th>门店</th>" +
      '<th style="text-align:right">销售额</th></tr></thead><tbody>' +
      stores.items.map((s, i) => '<tr><td data-th="#" class="hint num">' + (i + 1) + '</td><td data-th="门店">' + esc(s.store_name) +
        '</td><td data-th="销售额" class="num" style="text-align:right;font-weight:600">' + money(s.amount_7d) + "</td></tr>").join("") +
      "</tbody></table>") +
    "</div>" +
    card("最新发现异常", anomalyTable(anomalies.items.slice(0, 8), false),
      "统计检测自动发现 · 点击行查看根因与建议", '<a class="btn sm" href="#/anomalies">查看全部 \u2192</a>', true);
}
async function pageAnomalies() {
  const hash = location.hash.split("?")[1] || "";
  const status = new URLSearchParams(hash).get("status") || "";
  const anomalies = await fetchJSON("/agent/anomalies?limit=100");
  const items = status ? anomalies.items.filter(a => a.status === status) : anomalies.items;
  let opts = '<option value="">全部状态</option>';
  ["open", "diagnosed", "decided"].forEach(s => {
    opts += '<option value="' + s + '"' + (status === s ? " selected" : "") + ">" + s + "</option>";
  });
  return '<div class="toolbar"><b>异常中心</b>' +
    '<select onchange="location.hash = this.value ? \'#/anomalies?status=\' + this.value : \'#/anomalies\'">' + opts + "</select>" +
    '<span class="sep"></span><span class="hint">系统自动扫描销售数据发现异常，无需人工发起</span></div>' +
    card("异常列表（" + items.length + "）", anomalyTable(items, true), "", "", true);
}
async function pageAnomalyDetail(id) {
  const a = await fetchJSON("/agent/anomalies/" + id);
  const dg = a.diagnosis;
  const evidence = (a.evidence || []).map((e, i) =>
    '<div class="evidence"><span class="etool">' + esc(e.tool) + "</span>" +
    '<span class="etype">证据 ' + (i + 1) + " · " + esc(e.type) + "</span>" +
    '<div class="edata" tabindex="0" role="button" aria-label="展开或收起证据数据" ' +
    'onclick="this.classList.toggle(\'expanded\')" title="点击展开 / 收起">' +
    esc(JSON.stringify(e.data, null, 1)) + "</div>" +
    '<div class="emore" onclick="this.previousElementSibling.classList.toggle(\'expanded\'); this.remove()">展开全部 \u25be</div></div>').join("");
  const decisions = (a.decisions || []).filter(d => CORE_ACTIONS.has(d.action_type)).map(d => decisionHtml(d)).join("");
  const causes = dg ? dg.root_causes.map((rc, i) =>
    '<div class="rootcause ' + (i === 0 ? "top1" : "") + '"><b>#' + (i + 1) + " " + esc(rc.name) + "</b> " +
    '<span class="hint mono">' + esc(rc.code) + "</span>" +
    '<div class="hint" style="margin-top:2px">置信度 <b style="color:var(--accent)">' + rc.confidence +
    "</b> · 贡献占比 <b>" + rc.contribution_pct + '%</b></div>' +
    '<div class="confbar"><div style="width:' + rc.confidence * 100 + '%"></div></div>' +
    '<div style="margin-top:8px">' + rc.evidence.map(e =>
      '<div class="evidence"><span class="etype">' + esc(e.type) + "</span>" +
      '<div class="hint">' + esc(e.note || "") + "</div></div>").join("") + "</div></div>").join("") : "";
  /* 阅读动线：左栏 01 检测证据 → 02 原因分析，右栏 03 建议方案 → 结论（编号与视觉流一致） */
  return '<div class="toolbar"><a class="btn sm" href="#/anomalies">\u2190 返回</a>' +
    "<b>异常详情</b> " + '<span class="mono">' + esc(a.id) + "</span> " + badge(a.severity) + " " + badge(a.status) +
    '<span class="sep"></span><span class="hint">发现于 ' + esc((a.detected_at || "").slice(0, 19)) + "</span></div>" +
    '<div class="detail-grid"><div>' +
    card('<span class="step-no">01</span>检测证据', evidence || '<div class="empty">无证据</div>', "全部来自业务系统真实数据 · 点击数据块展开") +
    '<div style="height:14px"></div>' +
    card('<span class="step-no">02</span>原因分析', causes || emptyState("search", "尚未分析 —— 运行 Agent 后自动归因"),
      "按证据充分程度排序的根因候选") +
    "</div><div>" +
    card('<span class="step-no">03</span>建议方案', decisions || emptyState("bulb", "暂无建议 —— 运行 Agent 生成（先建议后执行）"),
      "补货 / 促销 · 含成本收益估算与风险等级") +
    (dg ? '<div style="height:14px"></div>' + card("结论", '<div class="narrative">' + esc(dg.narrative || dg.summary) + "</div>") : "") +
    "</div></div>";
}
function actionName(t) {
  if (t === "replenish") return acell("box", "补货下单");
  if (t === "promo") return acell("target", "促销活动");
  return esc(t);
}
function paramChips(d) {
  const a = d.action || {};
  const chips = [];
  if (a.product_id) chips.push(["商品", a.product_id]);
  if (a.qty) chips.push(["补货量", a.qty + " 件"]);
  if (a.discount_pct) chips.push(["折扣", a.discount_pct + "%"]);
  if (a.budget) chips.push(["预算", money(a.budget)]);
  if (a.category_id) chips.push(["品类", a.category_id]);
  if (a.start_date) chips.push(["档期", a.start_date.slice(5) + " ~ " + (a.end_date || "").slice(5)]);
  return chips.map(kv => '<span class="param-chip">' + kv[0] + " <b>" + esc(kv[1]) + "</b></span>").join("");
}
function decisionHtml(d) {
  const impact = d.expected_impact || {};
  const rcTag = (d.rationale || "").match(/\[根因:([^\]]+)\]/);
  const reason = (d.rationale || "").replace(/\[根因:[^\]]+\]\s*/, "");
  let checks = "";
  (d.constraints_checked || []).forEach(c => {
    checks += '<span class="' + (c.passed ? "up" : "down") + '">' + c.rule + (c.passed ? "\u2713" : "\u2717") + "</span> · ";
  });
  return '<section class="card decision-card"><div class="card-body">' +
    '<div class="risk-strip ' + d.risk_level + '"></div>' +
    '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">' +
    "<b>" + actionName(d.action_type) + "</b><span>" + badge(d.risk_level) + " " + badge(d.status) + " " +
    (d.requires_approval ? badge("需审批", "critical") : badge("低风险 · 自动执行", "success")) + "</span></div>" +
    '<div class="hint" style="margin:8px 0 2px">' +
    (rcTag ? '<span class="rootcause-tag">根因 · ' + esc(rcTag[1]) + "</span>" : "") + esc(reason) + "</div>" +
    '<div class="params">' + paramChips(d) + "</div>" +
    '<div class="roi-grid">' +
    '<div class="roi-cell"><div class="rl">预估成本</div><div class="rv down">' + money(impact.est_cost) + "</div></div>" +
    '<div class="roi-cell"><div class="rl">预估收益</div><div class="rv up">' + money(impact.est_benefit) + "</div></div>" +
    '<div class="roi-cell"><div class="rl">ROI</div><div class="rv">' + (impact.roi == null ? "-" : impact.roi) + "</div></div>" +
    '<div class="roi-cell"><div class="rl">销量恢复</div><div class="rv">' +
    (impact.est_recovery_pct == null ? "-" : impact.est_recovery_pct + "%") + "</div></div></div>" +
    '<div class="hint mono" style="margin-top:8px">约束: ' + checks.replace(/ · $/, "") + "</div>" +
    (d.status === "suggested" ?
      '<div class="actions-row"><button class="btn sm primary" onclick="execDecision(\'' + d.id + '\', this)">' +
      icon("play", 12) + " 执行</button>" +
      '<span class="hint">低风险自动执行，高风险转人工审批</span></div>' : "") +
    "</div></section>";
}
async function pageDecisions() {
  const decisions = await fetchJSON("/agent/decisions?limit=100");
  const items = decisions.items.filter(d => CORE_ACTIONS.has(d.action_type));
  return '<div class="toolbar"><b>补货 / 促销建议</b><span class="sep"></span>' +
    '<span class="hint">先建议后执行 · 低风险自动执行 · 高风险（如折扣&gt;10%）转人工审批</span></div>' +
    '<div class="grid half">' + (items.map(d => decisionHtml(d)).join("") ||
    '<div class="empty-state" style="grid-column:1/-1"><div class="glyph">' + icon("bulb", 26) +
    '</div><div>暂无建议 —— 点击右上角「运行 Agent」</div></div>') + "</div>";
}
async function pageApprovals() {
  const pending = await fetchJSON("/gov/approvals?status=pending");
  const all = await fetchJSON("/gov/approvals?limit=50");
  return '<div class="toolbar"><b>审批中心</b><span class="sep"></span>' +
    '<span class="hint">超出 Agent 授权范围的动作须人工确认 · 当前身份：<b style="color:var(--accent)">' +
    $("#role-select").selectedOptions[0].text + "</b>（需风控审批人）</span></div>" +
    card("待审批（" + pending.items.length + "）",
      pending.items.length ? '<div class="table-wrap"><table><thead><tr><th>审批单</th><th>动作</th><th>摘要</th><th>风险原因</th><th>操作</th></tr></thead><tbody>' +
        pending.items.map(a =>
          '<tr><td data-th="审批单" class="mono">' + esc(a.id) + '</td><td data-th="动作">' + actionName(a.action_type) + "</td>" +
          '<td data-th="摘要" style="max-width:280px">' + esc(a.summary) + "</td>" +
          '<td data-th="风险原因" class="hint" style="max-width:240px">' + (a.risk_reasons || []).map(r => "<div>\u2022 " + esc(r) + "</div>").join("") + "</td>" +
          '<td data-th="操作"><div class="actions-row" style="margin:0">' +
          '<button class="btn sm ok ap-decide" data-id="' + a.id + '" data-decision="approve">通过</button> ' +
          '<button class="btn sm danger ap-decide" data-id="' + a.id + '" data-decision="reject">驳回</button></div></td></tr>').join("") +
        "</tbody></table></div>" : emptyState("check", "无待审批项 —— 所有高风险动作均已处理"),
      "高风险动作 100% 人工审批", "", true) +
    '<div style="height:14px"></div>' +
    card("审批历史", all.items.length ? '<div class="table-wrap"><table><thead><tr><th>审批单</th><th>动作</th><th>状态</th><th>发起时间</th><th>决定人</th><th>备注</th></tr></thead><tbody>' +
      all.items.slice(0, 50).map(a =>
        '<tr><td data-th="审批单" class="mono">' + esc(a.id) + '</td><td data-th="动作">' + actionName(a.action_type) + "</td>" +
        '<td data-th="状态">' + badge(a.status) + '</td><td data-th="发起时间" class="mono">' + esc((a.requested_at || "").slice(0, 19)) + "</td>" +
        '<td data-th="决定人">' + esc(a.decided_by || "-") + '</td><td data-th="备注" class="hint">' + esc(a.decision_note || "") + "</td></tr>").join("") +
      "</tbody></table></div>" : '<div class="empty">暂无审批历史</div>', "", "", true);
}
async function pageExecutions() {
  const execs = await fetchJSON("/agent/executions?limit=100");
  return '<div class="toolbar"><b>执行记录</b><span class="sep"></span>' +
    '<span class="hint">仅执行通过审批或低风险的动作 · 每一步可追溯</span></div>' +
    card("执行历史", execs.items.length ? '<div class="table-wrap"><table><thead><tr><th>执行 ID</th><th>动作</th><th>建议单</th><th>状态</th><th>业务单据</th><th>时间</th></tr></thead><tbody>' +
      execs.items.map(e =>
        '<tr><td data-th="执行 ID" class="mono">' + esc(e.id) + '</td><td data-th="动作" class="mono">' +
        esc(e.tool_name.replace("create_", "").replace("_order", "")) + "</td>" +
        '<td data-th="建议单" class="mono">' + esc(e.decision_id) + '</td><td data-th="状态">' + badge(e.status) + "</td>" +
        '<td data-th="业务单据" class="mono">' + esc(e.business_ref || "-") + "</td>" +
        '<td data-th="时间" class="mono">' + esc((e.created_at || "").slice(5, 19)) + "</td></tr>").join("") +
      "</tbody></table></div>" : emptyState("gear", "暂无执行记录 —— 运行 Agent 后这里会出现每一步业务动作"), "", "", true);
}
async function pageAudit() {
  return '<div class="toolbar"><b>审计日志</b>' +
    '<input type="text" id="audit-trace" placeholder="按 trace_id 过滤" style="width:220px">' +
    '<button class="btn sm" onclick="loadAudit()">查询</button><span class="sep"></span>' +
    '<span class="hint">谁在什么时候对什么做了什么 · 通过与拒绝均留痕</span></div>' +
    '<div id="audit-card">' + card("", '<div class="loading"><div class="spin-ring"></div>查询中…</div>', "", "", true) + "</div>";
}
async function loadAudit() {
  const trace = $("#audit-trace") ? $("#audit-trace").value.trim() : "";
  const logs = await fetchJSON("/gov/audit-logs?limit=200");
  const items = trace ? logs.items.filter(l => (l.trace_id || "").indexOf(trace) >= 0) : logs.items;
  $("#audit-card").innerHTML = card("日志（" + items.length + "）",
    items.length ? '<div class="table-wrap"><table><thead><tr><th>时间</th><th>主体</th><th>动作</th><th>资源</th><th>结果</th><th>详情</th></tr></thead><tbody>' +
      items.map(l =>
        '<tr><td data-th="时间" class="mono">' + esc((l.ts || "").slice(5, 19)) + "</td>" +
        "<td data-th=\"主体\">" + (l.actor_type === "agent" ? '<span class="actor-tag">AGENT</span>' : "") + esc(l.actor_id) + "</td>" +
        '<td data-th="动作" class="mono">' + esc(l.action) + '</td><td data-th="资源" class="mono">' + esc(l.resource_type) + "</td>" +
        '<td data-th="结果">' + badge(l.result) + "</td>" +
        '<td data-th="详情" class="mono" style="max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' +
        esc(JSON.stringify(l.detail)) + '">' + esc(JSON.stringify(l.detail)) + "</td></tr>").join("") +
      "</tbody></table></div>" : emptyState("doc", "无匹配日志"), trace ? "trace: " + esc(trace) : "", "", true);
}

/* ── 渲染后处理：数字滚动 / 描线动画 / 图表 hover ── */
function animateCounters(root) {
  root.querySelectorAll("[data-cnt]").forEach(el => {
    const target = Number(el.dataset.cnt) || 0;
    const fmt = el.dataset.fmt || "int";
    if (REDUCED || root.classList.contains("no-anim")) { el.textContent = fmtNum(target, fmt); return; }
    const t0 = performance.now(), dur = 620;
    const tick = (now) => {
      const t = Math.min(1, (now - t0) / dur);
      el.textContent = fmtNum(target * (1 - Math.pow(1 - t, 3)), fmt);
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}
function drawIn(el, dur, delay) {
  try {
    const len = el.getTotalLength();
    el.style.strokeDasharray = String(len);
    el.style.strokeDashoffset = "0";
    if (REDUCED || (el.closest && el.closest(".no-anim"))) return;
    el.style.strokeDashoffset = String(len);
    el.getBoundingClientRect(); /* 强制回流，确保过渡从起点开始 */
    el.style.transition = "stroke-dashoffset " + dur + "ms cubic-bezier(.22,.61,.36,1) " + delay + "ms";
    el.style.strokeDashoffset = "0";
  } catch (e) { el.style.strokeDashoffset = "0"; }
}
function initChartHover(box) {
  const svg = box.querySelector("svg.chart");
  const tip = box.querySelector(".tipbox");
  if (!svg || !tip) return;
  const pts = (box.dataset.pts || "").split(";").filter(Boolean).map(s => {
    const q = s.split("|");
    return { x: +q[0], y: +q[1], label: q[2], v: +q[3] };
  });
  if (pts.length < 2) return;
  const xh = svg.querySelector(".xhair"), dot = svg.querySelector(".xdot");
  const show = (pt, on) => {
    xh.style.opacity = dot.style.opacity = on ? 1 : 0;
    if (pt) {
      xh.setAttribute("x1", pt.x); xh.setAttribute("x2", pt.x);
      dot.setAttribute("cx", pt.x); dot.setAttribute("cy", pt.y); dot.setAttribute("r", on ? 3.6 : 0);
      tip.innerHTML = "<b>" + esc(pt.label) + "</b>" + money(pt.v);
      const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
      tip.style.left = (pt.x / vb.width * r.width) + "px";
      tip.style.top = (pt.y / vb.height * r.height) + "px";
    }
    tip.style.opacity = on ? 1 : 0;
  };
  svg.addEventListener("mousemove", (ev) => {
    const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
    const mx = (ev.clientX - r.left) / r.width * vb.width;
    let best = pts[0];
    pts.forEach(p => { if (Math.abs(p.x - mx) < Math.abs(best.x - mx)) best = p; });
    show(best, true);
  });
  svg.addEventListener("mouseleave", () => show(null, false));
}
function initCharts(root) {
  root.querySelectorAll("path.chart-line").forEach(p => drawIn(p, 1100, 150));
  root.querySelectorAll(".spark-line").forEach((pl, i) => drawIn(pl, 700, 80 + i * 70));
  root.querySelectorAll(".chart-box").forEach(initChartHover);
}
function afterRender(root) {
  animateCounters(root);
  initCharts(root);
}

/* ── 路由：延迟 spinner（快数据无闪烁）+ View Transition 交叉淡入 ── */
function applyHtml(html, soft) {
  const m = main();
  const apply = () => { m.innerHTML = html; afterRender(m); };
  if (!soft && !REDUCED && document.startViewTransition) {
    try { document.startViewTransition(apply); return; } catch (e) { /* 降级为直接渲染 */ }
  }
  apply();
}
const PAGE_NAMES = {
  "#/overview": "经营总览", "#/anomalies": "异常中心", "#/decisions": "补货 / 促销建议",
  "#/approvals": "审批中心", "#/executions": "执行记录", "#/audit": "审计日志",
};
async function route(soft) {
  const hash = location.hash || "#/overview";
  const page = hash.split("?")[0];
  document.querySelectorAll(".nav a[data-page]").forEach(el =>
    el.classList.toggle("active", el.dataset.page === page.split("/")[1]));
  const name = PAGE_NAMES[page] || (page.indexOf("#/anomaly/") === 0 ? "异常详情" : "经营总览");
  $("#crumb-page").textContent = name;
  if (window.innerWidth <= 768) document.body.classList.remove("drawer-open");
  const detail = page.indexOf("#/anomaly/") === 0;
  const pages = {
    "#/overview": pageOverview, "#/anomalies": pageAnomalies, "#/decisions": pageDecisions,
    "#/approvals": pageApprovals, "#/executions": pageExecutions, "#/audit": pageAudit,
  };
  const fn = detail ? () => pageAnomalyDetail(page.split("/")[2]) : (pages[page] || pageOverview);
  let spinT = null;
  if (!soft) spinT = setTimeout(() => {
    main().innerHTML = '<div class="loading"><div class="spin-ring"></div>加载中…</div>';
  }, 200);
  try {
    const html = await fn();
    if (spinT) clearTimeout(spinT);
    applyHtml(html, soft);
    if (page === "#/audit") loadAudit();
  } catch (e) {
    if (spinT) clearTimeout(spinT);
    applyHtml(card("加载失败", '<div class="empty">' + esc(e.message) + "</div>"), true);
  }
}
/* 操作成功后的软刷新：不清空页面、不重放入场动画 */
async function refreshCurrent() {
  const m = main();
  m.classList.add("no-anim");
  try { await route(true); }
  finally { requestAnimationFrame(() => m.classList.remove("no-anim")); }
}

function btnLoading(btn, on) { if (btn) btn.classList.toggle("loading", !!on); }
async function runScan(btn) {
  if (staticReadonly()) return;
  btnLoading(btn, true);
  try {
    const r = await api("/agent/scan", { method: "POST" });
    toast("扫描完成：发现 " + r.found + " 个异常，新增 " + r.new_anomalies + " 个");
    refreshCurrent(); refreshBadges();
  } catch (e) { toast("扫描失败: " + e.message, false); }
  finally { btnLoading(btn, false); }
}
/* flow-pills 微剧场：步骤依次点亮（当前步呼吸、已完成打勾、箭头流动）；
   ≤1180px pills 隐藏时降级为 toast 步骤序列 */
function theater(promise) {
  const pills = Array.prototype.slice.call(document.querySelectorAll(".flow-pills span[data-step]"));
  const arrows = Array.prototype.slice.call(document.querySelectorAll(".flow-pills i"));
  const stepNames = ["自动发现", "根因分析", "补货/促销建议", "授权执行"];
  if (REDUCED) return;
  const pillsVisible = pills.length > 0 && pills[0].offsetParent !== null;
  let idx = 0, finished = false;
  const clear = () => {
    pills.forEach(p => { p.classList.remove("active"); p.classList.remove("done"); });
    arrows.forEach(a => a.classList.remove("flow"));
  };
  const show = () => {
    if (finished) return;
    if (pillsVisible) {
      pills.forEach((p, j) => { p.classList.toggle("active", j === idx); p.classList.toggle("done", j < idx); });
      arrows.forEach((a, j) => a.classList.toggle("flow", j === idx - 1));
    } else {
      toast("Agent · " + stepNames[idx] + "…");
    }
  };
  show();
  const iv = setInterval(() => {
    if (finished) return;
    if (idx < stepNames.length - 1) { idx += 1; show(); }
  }, 900);
  const finish = () => {
    finished = true;
    clearInterval(iv);
    if (pillsVisible) {
      pills.forEach(p => { p.classList.add("done"); p.classList.remove("active"); });
      arrows.forEach(a => a.classList.remove("flow"));
      setTimeout(clear, 2400);
    } else { clear(); }
  };
  promise.then(finish, () => { finished = true; clearInterval(iv); clear(); });
}
async function runPipeline(btn) {
  if (staticReadonly()) return;
  btnLoading(btn, true);
  const p = api("/agent/pipeline", { method: "POST" });
  theater(p);
  try {
    const r = await p;
    const s = r.steps.map(x => x.step + ":" + Object.values(x)[1]).join(" · ");
    toast("完成 " + s);
    refreshCurrent(); refreshBadges();
  } catch (e) { toast("运行失败: " + e.message, false); }
  finally { btnLoading(btn, false); }
}
async function execDecision(id, btn) {
  if (staticReadonly()) return;
  btnLoading(btn, true);
  try {
    const r = await api("/agent/execute?decision_id=" + id, { method: "POST" });
    toast("执行状态: " + r.execution.status);
    refreshCurrent(); refreshBadges();
  } catch (e) { toast("执行失败: " + e.message, false); }
  finally { btnLoading(btn, false); }
}
async function decideApproval(id, decision, btn) {
  if (staticReadonly()) return;
  btnLoading(btn, true);
  try {
    await api("/gov/approvals/" + id + "/decide", {
      method: "POST",
      body: { decision: decision, note: decision === "approve" ? "控制台审批通过" : "控制台驳回" },
    });
    toast(decision === "approve" ? "已通过，正在执行…" : "已驳回");
    await api("/agent/execute", { method: "POST" }).catch(() => null);
    refreshCurrent(); refreshBadges();
  } catch (e) { toast("审批失败: " + e.message, false); }
  finally { btnLoading(btn, false); }
}

/* ── 全局事件：审批按钮 / 表格行（含键盘）/ 证据块键盘 ── */
window.addEventListener("hashchange", () => route());
document.addEventListener("click", (ev) => {
  if (!ev.target.closest) return;
  const ap = ev.target.closest(".ap-decide");
  if (ap) { decideApproval(ap.dataset.id, ap.dataset.decision, ap); return; }
  const row = ev.target.closest("tr.clickable[data-href]");
  if (row) { location.hash = row.dataset.href; }
});
document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Enter" && ev.key !== " ") return;
  const t = ev.target;
  if (!t || !t.classList) return;
  if (t.tagName === "TR" && t.classList.contains("clickable") && t.dataset.href) {
    ev.preventDefault(); location.hash = t.dataset.href;
  } else if (t.classList.contains("edata")) {
    ev.preventDefault(); t.classList.toggle("expanded");
  }
});
if ($("#burger")) $("#burger").addEventListener("click", () => document.body.classList.toggle("drawer-open"));
if ($("#drawer-mask")) $("#drawer-mask").addEventListener("click", () => document.body.classList.remove("drawer-open"));
function boot() { route(); refreshBadges(); }
if (document.readyState === "loading") window.addEventListener("DOMContentLoaded", boot);
else boot();
