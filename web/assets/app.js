/* ══════════════════════════════════════════════════════════════════
   零售经营决策 Agent Console（原生 JS，无构建步骤）
   设计语言：shadcn/ui 浅色主题
   范围：R1-R5 核心 —— 多系统接入 / 自动发现异常 / 根因分析 / 补货·促销建议 / 授权执行
   ══════════════════════════════════════════════════════════════════ */
const API = "/api";
const CORE_ACTIONS = new Set(["replenish", "promo"]);   // R4：原问题只点名补货/促销
const $ = (sel) => document.querySelector(sel);
const main = () => $("#main");

/* 静态快照模式：GitHub Pages 无后端，fetch /api 失败时自动降级读 snapshot/*.json（只读预览） */
function snapPath(path) {
  const [p, q] = path.split("?");
  const qs = q ? "-" + q.replace(/[^a-z0-9]/gi, "") : "";
  return "snapshot/" + p.replace(/^\/(api\/)?/, "").replace(/\//g, "-") + qs + ".json";
}
async function fetchJSON(path) {
  try {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(r.status);
    if (!window.__static) return await r.json();
    throw new Error("static");
  } catch (e) {
    if (!window.__static) {
      window.__static = true;
      document.body.classList.add("static-mode");
    }
    const r2 = await fetch(snapPath(path));
    if (!r2.ok) throw new Error("快照缺失: " + path);
    return await r2.json();
  }
}
function staticReadonly() {
  if (window.__static) { toast("静态快照预览为只读 —— 完整交互请本地运行后端", false); return true; }
  return false;
}

function token() { return $("#role-select").value; }
function headers() { return { "X-Auth-Token": token(), "Content-Type": "application/json" }; }

async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: headers(), ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}
function toast(msg, ok = true) {
  const t = $("#toast");
  t.style.display = "block";
  t.style.background = ok ? "var(--primary)" : "var(--danger)";
  t.textContent = msg;
  setTimeout(() => (t.style.display = "none"), 4200);
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function badge(text, cls) { return `<span class="badge ${cls || text}">${esc(text)}</span>`; }
function money(v) { return v == null ? "-" : `¥${Number(v).toLocaleString("zh-CN", {maximumFractionDigits: 0})}`; }

function card(title, body, desc = "", actions = "", flush = false) {
  return `<section class="card">
    ${title ? `<div class="card-head">
      <div><div class="card-title">${title}</div>${desc ? `<div class="card-desc">${desc}</div>` : ""}</div>
      <div>${actions}</div></div>` : ""}
    <div class="card-body${flush ? " flush" : ""}">${body}</div>
  </section>`;
}
function kpi(label, value, unit = "", delta = "", color = "") {
  return `<div class="card kpi-card">
    <div class="label">${label}</div>
    <div class="value"${color ? ` style="color:${color}"` : ""}>${value}${unit ? `<span class="unit">${unit}</span>` : ""}</div>
    <div class="delta">${delta || ""}</div>
  </div>`;
}
function sparkline(data, color = "#4f46e5") {
  if (!data || data.length < 2) return "";
  const w = 118, h = 26, min = Math.min(...data), max = Math.max(...data);
  const x = (i) => i * w / (data.length - 1);
  const y = (v) => h - 2 - ((v - min) / (max - min || 1)) * (h - 4);
  const pts = data.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="margin-top:auto">
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6"/>
    <circle cx="${w}" cy="${y(data[data.length - 1])}" r="2.3" fill="${color}"/></svg>`;
}
function lineChart(points, color = "#4f46e5") {
  if (!points.length) return `<div class="empty">暂无数据</div>`;
  const w = 640, h = 210, padL = 54, padR = 14, padT = 14, padB = 26;
  const xs = points.map((_, i) => padL + i * (w - padL - padR) / Math.max(1, points.length - 1));
  const ys = points.map(p => p[1]);
  const min = Math.min(...ys) * 0.96, max = Math.max(...ys) * 1.04;
  const py = (v) => padT + (1 - (v - min) / (max - min || 1)) * (h - padT - padB);
  const path = points.map((p, i) => `${i ? "L" : "M"}${xs[i].toFixed(1)},${py(p[1]).toFixed(1)}`).join(" ");
  const area = path + ` L${xs[xs.length - 1]},${h - padB} L${padL},${h - padB} Z`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(t => {
    const v = min + (max - min) * (1 - t), y = padT + t * (h - padT - padB);
    return `<line x1="${padL}" y1="${y}" x2="${w - padR}" y2="${y}" stroke="#f1f5f9"/>
      <text x="${padL - 6}" y="${y + 3}" text-anchor="end" class="chart-tip">${money(v)}</text>`;
  }).join("");
  const labels = points.filter((_, i) => i % Math.ceil(points.length / 8) === 0)
    .map(p => `<text x="${xs[points.indexOf(p)]}" y="${h - 7}" text-anchor="middle" class="chart-tip">${p[0]}</text>`).join("");
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${color}" stop-opacity=".16"/><stop offset="1" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    ${ticks}<path d="${area}" fill="url(#cg)"/><path d="${path}" fill="none" stroke="${color}" stroke-width="2"/>
    ${labels}</svg>`;
}

/* ───────── 侧栏角标与顶栏信息 ───────── */
async function refreshBadges() {
  try {
    const [ov, anomalies, approvals] = await Promise.all([
      fetchJSON("/kpi/overview"),
      fetchJSON("/agent/anomalies?limit=100"),
      fetchJSON("/gov/approvals?status=pending"),
    ]);
    $("#biz-date").textContent = `业务日期 ${ov.biz_date}`;
    setBadge("#badge-anomaly", ov.anomalies_open);
    setBadge("#badge-approval", ov.approvals_pending, true);
    const suggested = anomalies.items.filter(a => a.status === "open" || a.status === "diagnosed").length;
    setBadge("#badge-decision", suggested, true);
  } catch (e) { /* 静默 */ }
}
function setBadge(sel, n, warn = false) {
  const el = $(sel);
  if (!el) return;
  if (n > 0) { el.textContent = n > 99 ? "99+" : n; el.classList.add("show"); el.classList.toggle("warn", warn); }
  else el.classList.remove("show");
}

/* ═══════════ 页面：经营总览 ═══════════ */
async function pageOverview() {
  const days = 30;
  const [ov, trend, anomalies, stores] = await Promise.all([
    fetchJSON("/kpi/overview"),
    fetchJSON(`/kpi/trend?days=${days}`),
    fetchJSON("/agent/anomalies?limit=8"),
    fetchJSON("/kpi/stores?limit=10"),
  ]);
  const mom = ov.sales_mom_pct;
  main().innerHTML = `
  <div class="grid kpi">
    ${kpi("销售额 · 近7天", money(ov.sales_7d), "", mom != null
      ? `<span class="${mom >= 0 ? "up" : "down"}">${mom >= 0 ? "▲" : "▼"} ${mom}% 环比</span>` : "")}
    ${kpi("销量 · 近7天", Number(ov.qty_7d || 0).toLocaleString(), "件", "", )}
    ${kpi("毛利率", (ov.gross_margin_rate ?? 0), "%")}
    ${kpi("待处理异常", ov.anomalies_open, "", `<span class="hint">自动发现</span>`,
      ov.anomalies_open > 0 ? "var(--danger)" : "")}
    ${kpi("待审批", ov.approvals_pending, "", `<span class="hint">高风险动作 · 人工确认</span>`,
      ov.approvals_pending > 0 ? "var(--warning)" : "")}
    ${kpi("已执行动作", ov.executed_actions, "", `<span class="up">授权范围内执行</span>`)}
  </div>
  <div class="grid two">
    ${card("销售额趋势", lineChart(trend.items.map(x => [x.date.slice(5), x.amount])), `最近 ${days} 天 · 全部门店`)}
    ${card("门店销售额排行 · 近7天", `<table>
      <tr><th>#</th><th>门店</th><th style="text-align:right">销售额</th></tr>
      ${stores.items.map((s, i) => `<tr><td class="hint num">${i + 1}</td>
        <td>${esc(s.store_name)}</td>
        <td class="num" style="text-align:right;font-weight:600">${money(s.amount_7d)}</td></tr>`).join("")}
      </table>`)}
  </div>
  ${card("最新发现异常", anomalyTable(anomalies.items.slice(0, 8)),
    "统计检测自动发现 · 点击行查看根因与建议", `<a class="btn sm" href="#/anomalies">查看全部 →</a>`, true)}`;
}

/* ═══════════ 页面：异常中心 ═══════════ */
function anomalyTable(items) {
  if (!items.length) return `<div class="empty">暂无异常 —— 点击右上角「扫描异常」或「运行 Agent」</div>`;
  return `<table><thead><tr>
    <th>严重度</th><th>类型</th><th>门店</th><th>商品</th>
    <th style="text-align:right">观察 / 期望</th><th style="text-align:right">偏差</th><th>时间窗口</th><th>状态</th></tr></thead><tbody>
    ${items.map(a => `
    <tr class="clickable" onclick="location.hash='#/anomaly/${a.id}'">
      <td>${badge(a.severity)}</td>
      <td>${a.type === "sales_drop" ? "📉 销量下降" : a.type === "sales_surge" ? "📈 销量上升" : "☎️ 客诉上升"}</td>
      <td>${esc(a.store_name || a.store_id)}</td><td class="mono">${esc(a.product_id)}</td>
      <td class="num" style="text-align:right">${a.observed} / ${a.expected}</td>
      <td class="num ${a.deviation_pct < 0 ? "down" : "up"}" style="text-align:right;font-weight:700">${a.deviation_pct}%</td>
      <td class="mono">${a.window_start.slice(5)} ~ ${a.window_end.slice(5)}</td>
      <td>${badge(a.status)}</td></tr>`).join("")}
  </tbody></table>`;
}
async function pageAnomalies() {
  const q = new URLSearchParams(location.hash.split("?")[1] || "");
  const status = q.get("status") || "";
  const anomalies = await fetchJSON(`/agent/anomalies?limit=100`);
  const items = status ? anomalies.items.filter(a => a.status === status) : anomalies.items;
  main().innerHTML = `
  <div class="toolbar"><b>异常中心</b>
    <select onchange="location.hash = this.value ? '#/anomalies?status=' + this.value : '#/anomalies'">
      <option value="">全部状态</option>
      ${["open", "diagnosed", "decided"].map(s => `<option value="${s}" ${status === s ? "selected" : ""}>${s}</option>`).join("")}
    </select>
    <span class="sep"></span>
    <span class="hint">系统自动扫描销售数据发现异常，无需人工发起</span>
  </div>
  ${card(`异常列表（${items.length}）`, anomalyTable(items), "", "", true)}`;
}
async function pageAnomalyDetail(id) {
  const a = await fetchJSON(`/agent/anomalies/${id}`);
  const dg = a.diagnosis;
  main().innerHTML = `
  <div class="toolbar">
    <a class="btn sm" href="#/anomalies">← 返回</a>
    <b>异常详情</b><span class="mono">${esc(a.id)}</span>
    ${badge(a.severity)} ${badge(a.status)}
    <span class="sep"></span><span class="hint">发现于 ${esc((a.detected_at || "").slice(0, 19))}</span>
  </div>
  <div class="detail-grid">
    <div>
      ${card("① 检测证据", (a.evidence || []).map((e, i) => `
        <div class="evidence">
          <span class="etool">${esc(e.tool)}</span>
          <span class="etype">证据 ${i + 1} · ${esc(e.type)}</span>
          <div class="edata">${esc(JSON.stringify(e.data, null, 1))}</div>
        </div>`).join("") || `<div class="empty">无证据</div>`,
        "全部来自业务系统真实数据")}
      <div style="height:14px"></div>
      ${card("③ 建议方案", (a.decisions || []).filter(d => CORE_ACTIONS.has(d.action_type)).map(d => decisionHtml(d)).join("")
        || `<div class="empty">暂无建议 —— 运行 Agent 生成（先建议后执行）</div>`,
        "补货 / 促销 · 含成本收益估算与风险等级")}
    </div>
    <div>
      ${card("② 原因分析", dg ? dg.root_causes.map((rc, i) => `
        <div class="rootcause ${i === 0 ? "top1" : ""}">
          <b>#${i + 1} ${esc(rc.name)}</b> <span class="hint mono">${esc(rc.code)}</span>
          <div class="hint" style="margin-top:2px">置信度 <b style="color:var(--accent)">${rc.confidence}</b>
            · 贡献占比 <b>${rc.contribution_pct}%</b></div>
          <div class="confbar"><div style="width:${rc.confidence * 100}%"></div></div>
          <div style="margin-top:8px">${rc.evidence.map(e =>
            `<div class="evidence"><span class="etype">${esc(e.type)}</span>
             <div class="hint">${esc(e.note || "")}</div></div>`).join("")}</div>
        </div>`).join("") : `<div class="empty">尚未分析</div>`,
        "按证据充分程度排序的根因候选")}
      ${dg ? `<div style="height:14px"></div>` + card("结论",
        `<div class="narrative">${esc(dg.narrative || dg.summary)}</div>`) : ""}
    </div>
  </div>`;
}

/* ═══════════ 页面：建议（补货/促销） ═══════════ */
function actionName(t) {
  return { replenish: "📦 补货下单", promo: "🎯 促销活动" }[t] || t;
}
function decisionHtml(d) {
  const impact = d.expected_impact || {};
  const params = Object.assign({}, d.action); delete params._policy_params;
  return `<section class="card" style="margin-bottom:12px"><div class="card-body">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
      <b>${actionName(d.action_type)}</b>
      <span>${badge(d.risk_level)} ${badge(d.status)}
        ${d.requires_approval ? badge("需审批", "critical") : badge("低风险 · 自动执行", "success")}</span>
    </div>
    <div class="hint" style="margin:7px 0">${esc(d.rationale || "")}</div>
    <div class="mono" style="word-break:break-all">${esc(JSON.stringify(params))}</div>
    <table style="margin-top:9px">
      <tr><th>预估成本</th><th>预估收益</th><th>ROI</th><th>销量恢复</th></tr>
      <tr><td class="down num">${money(impact.est_cost)}</td>
          <td class="up num">${money(impact.est_benefit)}</td>
          <td class="num" style="font-weight:700">${impact.roi ?? "-"}</td>
          <td class="num">${impact.est_recovery_pct != null ? impact.est_recovery_pct + "%" : "-"}</td></tr>
    </table>
    <div class="hint mono" style="margin-top:6px">约束: ${(d.constraints_checked || [])
      .map(c => `<span class="${c.passed ? "up" : "down"}">${c.rule}${c.passed ? "✓" : "✗"}</span>`).join(" · ")}</div>
    ${d.status === "suggested" ? `<div class="actions-row">
      <button class="btn sm primary" onclick="execDecision('${d.id}')">▶ 执行</button>
      <span class="hint">低风险自动执行，高风险转人工审批</span></div>` : ""}
  </div></section>`;
}
async function pageDecisions() {
  const decisions = await fetchJSON("/agent/decisions?limit=100");
  const items = decisions.items.filter(d => CORE_ACTIONS.has(d.action_type));
  main().innerHTML = `
  <div class="toolbar"><b>补货 / 促销建议</b>
    <span class="sep"></span>
    <span class="hint">先建议后执行 · 低风险自动执行 · 高风险（如折扣&gt;10%）转人工审批</span>
  </div>
  <div class="grid half">${items.map(d => decisionHtml(d)).join("")
    || `<div class="empty" style="grid-column:1/-1">暂无建议 —— 点击右上角「运行 Agent」</div>`}</div>`;
}

/* ═══════════ 页面：审批中心 ═══════════ */
async function pageApprovals() {
  const [pending, all] = await Promise.all([
    fetchJSON("/gov/approvals?status=pending"),
    fetchJSON("/gov/approvals?limit=50"),
  ]);
  main().innerHTML = `
  <div class="toolbar"><b>审批中心</b>
    <span class="sep"></span>
    <span class="hint">超出 Agent 授权范围的动作须人工确认 · 当前身份：<b style="color:var(--accent)">${$("#role-select").selectedOptions[0].text}</b>（需风控审批人）</span>
  </div>
  ${card(`待审批（${pending.items.length}）`, pending.items.length ? `<table>
    <tr><th>审批单</th><th>动作</th><th>摘要</th><th>风险原因</th><th>操作</th></tr>
    ${pending.items.map(a => `<tr>
      <td class="mono">${esc(a.id)}</td><td>${actionName(a.action_type)}</td>
      <td style="max-width:280px">${esc(a.summary)}</td>
      <td class="hint" style="max-width:240px">${(a.risk_reasons || []).map(r => `<div>• ${esc(r)}</div>`).join("")}</td>
      <td><div class="actions-row" style="margin:0">
        <button class="btn sm ok" onclick="decideApproval('${a.id}','approve')">通过</button>
        <button class="btn sm danger" onclick="decideApproval('${a.id}','reject')">驳回</button>
      </div></td></tr>`).join("")}</table>`
    : `<div class="empty">无待审批项 ✓</div>`, "高风险动作 100% 人工审批", "", true)}
  <div style="height:14px"></div>
  ${card("审批历史", `<table>
    <tr><th>审批单</th><th>动作</th><th>状态</th><th>发起时间</th><th>决定人</th><th>备注</th></tr>
    ${all.items.slice(0, 50).map(a => `<tr>
      <td class="mono">${esc(a.id)}</td><td>${actionName(a.action_type)}</td>
      <td>${badge(a.status)}</td><td class="mono">${esc((a.requested_at || "").slice(0, 19))}</td>
      <td>${esc(a.decided_by || "-")}</td><td class="hint">${esc(a.decision_note || "")}</td></tr>`).join("")}
    </table>`, "", "", true)}`;
}

/* ═══════════ 页面：执行记录 ═══════════ */
async function pageExecutions() {
  const execs = await fetchJSON("/agent/executions?limit=100");
  main().innerHTML = `
  <div class="toolbar"><b>执行记录</b>
    <span class="sep"></span><span class="hint">仅执行通过审批或低风险的动作 · 每一步可追溯</span></div>
  ${card("执行历史", execs.items.length ? `<table>
    <tr><th>执行 ID</th><th>动作</th><th>建议单</th><th>状态</th><th>业务单据</th><th>时间</th></tr>
    ${execs.items.map(e => `<tr>
      <td class="mono">${esc(e.id)}</td><td class="mono">${esc(e.tool_name.replace("create_", "").replace("_order", ""))}</td>
      <td class="mono">${esc(e.decision_id)}</td><td>${badge(e.status)}</td>
      <td class="mono">${esc(e.business_ref || "-")}</td>
      <td class="mono">${esc((e.created_at || "").slice(5, 19))}</td>
    </tr>`).join("")}</table>` : `<div class="empty">暂无执行记录</div>`, "", "", true)}`;
}

/* ═══════════ 页面：审计日志 ═══════════ */
async function pageAudit() {
  main().innerHTML = `
  <div class="toolbar"><b>审计日志</b>
    <input type="text" id="audit-trace" placeholder="按 trace_id 过滤" style="width:220px">
    <button class="btn sm" onclick="loadAudit()">查询</button>
    <span class="sep"></span>
    <span class="hint">谁在什么时候对什么做了什么 · 通过与拒绝均留痕</span></div>
  <div id="audit-card">${card("", `<div class="empty">查询中…</div>`, "", "", true)}</div>`;
  loadAudit();
}
async function loadAudit() {
  const trace = $("#audit-trace") ? $("#audit-trace").value.trim() : "";
  const logs = await fetchJSON(`/gov/audit-logs?limit=200`);
  const logItems = trace ? logs.items.filter(l => (l.trace_id || "").includes(trace)) : logs.items;
  $("#audit-card").innerHTML = card(
    `日志（${logItems.length}）`,
    logs.items.length ? `<table>
    <tr><th>时间</th><th>主体</th><th>动作</th><th>资源</th><th>结果</th><th>详情</th></tr>
    ${logItems.map(l => `<tr>
      <td class="mono">${esc((l.ts || "").slice(5, 19))}</td>
      <td>${l.actor_type === "agent" ? "🤖 " : ""}${esc(l.actor_id)}</td>
      <td class="mono">${esc(l.action)}</td>
      <td class="mono">${esc(l.resource_type)}</td>
      <td>${badge(l.result)}</td>
      <td class="mono" style="max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${esc(JSON.stringify(l.detail))}">${esc(JSON.stringify(l.detail))}</td></tr>`).join("")}
    </table>` : `<div class="empty">无日志</div>`,
    trace ? `trace: ${esc(trace)}` : "", "", true);
}

/* ═══════════ 动作 ═══════════ */
async function runScan() {
  if (staticReadonly()) return;
  toast("正在扫描销售数据…");
  try {
    const r = await api("/agent/scan", { method: "POST" });
    toast(`扫描完成：发现 ${r.found} 个异常，新增 ${r.new_anomalies} 个`);
    route(); refreshBadges();
  } catch (e) { toast("扫描失败: " + e.message, false); }
}
async function runPipeline() {
  if (staticReadonly()) return;
  toast("Agent 运行中：发现异常 → 原因分析 → 生成建议 → 执行…");
  try {
    const r = await api("/agent/pipeline", { method: "POST" });
    const s = r.steps.map(x => `${x.step}:${Object.values(x)[1]}`).join(" · ");
    toast(`完成 ${s}`);
    route(); refreshBadges();
  } catch (e) { toast("运行失败: " + e.message, false); }
}
async function execDecision(id) {
  if (staticReadonly()) return;
  try {
    const r = await api(`/agent/execute?decision_id=${id}`, { method: "POST" });
    toast("执行状态: " + r.execution.status);
    route(); refreshBadges();
  } catch (e) { toast("执行失败: " + e.message, false); }
}
async function decideApproval(id, decision) {
  if (staticReadonly()) return;
  try {
    await api(`/gov/approvals/${id}/decide`, {
      method: "POST",
      body: { decision, note: decision === "approve" ? "控制台审批通过" : "控制台驳回" },
    });
    toast(decision === "approve" ? "已通过，正在执行…" : "已驳回");
    await api("/agent/execute", { method: "POST" }).catch(() => null);
    route(); refreshBadges();
  } catch (e) { toast("审批失败: " + e.message, false); }
}

/* ═══════════ 路由 ═══════════ */
const PAGE_NAMES = {
  "#/overview": "经营总览", "#/anomalies": "异常中心", "#/decisions": "补货 / 促销建议",
  "#/approvals": "审批中心", "#/executions": "执行记录", "#/audit": "审计日志",
};
function route() {
  const hash = location.hash || "#/overview";
  const page = hash.split("?")[0];
  document.querySelectorAll(".nav a[data-page]").forEach(el =>
    el.classList.toggle("active", el.dataset.page === page.split("/")[1]));
  const name = PAGE_NAMES[page] || (page.startsWith("#/anomaly/") ? "异常详情" : "经营总览");
  $("#crumb-page").textContent = name;
  if (page.startsWith("#/anomaly/")) return pageAnomalyDetail(page.split("/")[2]);
  const pages = {
    "#/overview": pageOverview, "#/anomalies": pageAnomalies, "#/decisions": pageDecisions,
    "#/approvals": pageApprovals, "#/executions": pageExecutions, "#/audit": pageAudit,
  };
  (pages[page] || pageOverview)().catch(e => {
    main().innerHTML = card("加载失败", `<div class="empty">${esc(e.message)}</div>`);
  });
}
window.addEventListener("hashchange", route);
function boot() { route(); refreshBadges(); }
if (document.readyState === "loading") window.addEventListener("DOMContentLoaded", boot);
else boot();
