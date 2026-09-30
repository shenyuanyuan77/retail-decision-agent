# -*- coding: utf-8 -*-
"""评估 Agent：基于真实执行结果做 T+7 复盘（业务指标前后对比 + 有效/无效归因 + 策略权重更新）。

不评估文本相似度；所有对比数字来自 sales/tickets/inventory 实际数据（推演期生成的真实结果）。
"""
import json
from datetime import timedelta

from sqlmodel import Session, select

from ..core import timeutil
from ..governance.audit import audit
from ..governance.auth import AGENT_ACTOR
from ..models import (Anomaly, DecisionCard, Execution, ReviewReport, SalesOrder, Store,
                      StrategyWeight, Ticket)
from . import tools
from .llm import narrate


def _window_metrics(session: Session, store_id: str, product_id: str,
                    start: str, end: str) -> dict:
    rows = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == store_id, SalesOrder.product_id == product_id,
        SalesOrder.biz_date >= start, SalesOrder.biz_date <= end)).all()
    days = (timeutil.parse_date(end) - timeutil.parse_date(start)).days + 1
    qty = sum(r.qty for r in rows)
    tickets = session.exec(select(Ticket).where(
        Ticket.store_id == store_id, Ticket.product_id == product_id,
        Ticket.biz_date >= start, Ticket.biz_date <= end)).all()
    return {"window": [start, end], "days": days,
            "sales_qty": qty, "sales_amount": round(sum(r.amount for r in rows), 2),
            "daily_avg_qty": round(qty / days, 2),
            "tickets": len(tickets),
            "tickets_per_day": round(len(tickets) / days, 2)}


def _stockout_days(session: Session, store_id: str, product_id: str, start: str, end: str,
                   threshold: float) -> int:
    rows = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == store_id, SalesOrder.product_id == product_id,
        SalesOrder.biz_date >= start, SalesOrder.biz_date <= end)).all()
    by_date = {r.biz_date: r.qty for r in rows}
    d = timeutil.parse_date(start)
    n = 0
    while d <= timeutil.parse_date(end):
        if by_date.get(d.isoformat(), 0) == 0:
            n += 1
        d += timedelta(days=1)
    return n


def review_execution(session: Session, execution: Execution,
                     trace_id: str = "") -> ReviewReport:
    """对单个已执行动作做复盘（需已过 T+7，由调用方保证或自动推进）。"""
    trace_id = trace_id or execution.trace_id or timeutil.new_id("trc")
    decision = session.get(DecisionCard, execution.decision_id)
    anomaly = session.get(Anomaly, execution.anomaly_id) if execution.anomaly_id else None
    exec_day = timeutil.parse_date(execution.created_at[:10])
    today = timeutil.business_today(session)
    if (today - exec_day).days < 7:
        raise ValueError(f"执行日 {exec_day} 距今不足 7 天，无法复盘（当前 {today}）")

    before = _window_metrics(session, anomaly.store_id, anomaly.product_id,
                             (exec_day - timedelta(days=7)).isoformat(),
                             (exec_day - timedelta(days=1)).isoformat())
    after = _window_metrics(session, anomaly.store_id, anomaly.product_id,
                            (exec_day + timedelta(days=1)).isoformat(),
                            (exec_day + timedelta(days=7)).isoformat())
    baseline_daily = anomaly.expected if anomaly else 0.0

    reasons: list[str] = []
    if anomaly and anomaly.type in ("sales_drop", "complaint_surge"):
        gap_before = max(0.0, baseline_daily - before["daily_avg_qty"])
        gap_after = max(0.0, baseline_daily - after["daily_avg_qty"])
        recovery = 1 - (gap_after / gap_before) if gap_before > 0 else 1.0
        kpi_delta = {"recovery_pct": round(recovery * 100, 1),
                     "daily_qty_delta": round(after["daily_avg_qty"] - before["daily_avg_qty"], 2),
                     "tickets_delta": after["tickets"] - before["tickets"],
                     "amount_delta": round(after["sales_amount"] - before["sales_amount"], 2)}
        if recovery >= 0.6:
            verdict = "effective"
            reasons.append(f"销量恢复 {recovery*100:.0f}%（缺口 {gap_before:.1f}→{gap_after:.1f}/日）")
        elif recovery >= 0.3:
            verdict = "partial"
            reasons.append(f"销量部分恢复 {recovery*100:.0f}%")
        else:
            verdict = "ineffective"
            reasons.append(f"销量未恢复（缺口 {gap_after:.1f}/日），需检查到货与执行落地")
        if after["tickets_per_day"] < before["tickets_per_day"]:
            reasons.append(f"客诉率下降 {before['tickets_per_day']}→{after['tickets_per_day']} 件/日")
    else:  # sales_surge：目标是补货跟上需求
        sustained = after["daily_avg_qty"] >= baseline_daily * 0.8 if baseline_daily else True
        verdict = "effective" if sustained else "partial"
        kpi_delta = {"daily_qty_delta": round(after["daily_avg_qty"] - before["daily_avg_qty"], 2),
                     "amount_delta": round(after["sales_amount"] - before["sales_amount"], 2)}
        reasons.append("促销期后销量保持在基线 80% 以上" if sustained else "促销期后销量回落过快")

    # 促销 ROI（若有真实活动成本）
    impact = json.loads(decision.expected_impact) if decision else {}
    camp_cost = None
    if decision and decision.action_type in ("promo", "member_reach"):
        result = json.loads(execution.result or "{}")
        camp_id = result.get("id")
        if camp_id:
            from ..models import Campaign
            camp = session.get(Campaign, camp_id)
            if camp:
                camp_cost = camp.cost_actual
    if camp_cost is not None:
        gross_delta = after["sales_amount"] - before["sales_amount"]
        cost_delta = after["sales_amount"] * 0.28 - before["sales_amount"] * 0.28  # 毛利额代理
        kpi_delta["promo_roi"] = round(cost_delta / camp_cost, 2) if camp_cost else None
        kpi_delta["campaign_cost_actual"] = round(camp_cost, 2)
        reasons.append(f"活动实际让利成本 {camp_cost:.0f}，估算 ROI {kpi_delta['promo_roi']}")

    facts = {"action_type": decision.action_type if decision else "",
             "anomaly_type": anomaly.type if anomaly else "",
             "before": before, "after": after, "verdict": verdict, "kpi_delta": kpi_delta}
    narrative = narrate("总结这次执行动作的复盘结论", facts, template=(
        f"{decision.action_type if decision else ''} 执行{verdict}："
        f"日销量 {before['daily_avg_qty']}→{after['daily_avg_qty']}，"
        f"客诉/日 {before['tickets_per_day']}→{after['tickets_per_day']}"))

    report = ReviewReport(
        id=timeutil.new_id("rev"), execution_id=execution.id,
        decision_id=execution.decision_id, anomaly_id=execution.anomaly_id or "",
        action_type=decision.action_type if decision else "",
        period_before=json.dumps(before, ensure_ascii=False),
        period_after=json.dumps(after, ensure_ascii=False),
        kpi_delta=json.dumps(kpi_delta, ensure_ascii=False),
        verdict=verdict, reasons=json.dumps(reasons, ensure_ascii=False),
        narrative=narrative, trace_id=trace_id, created_at=timeutil.now_iso())
    session.add(report)

    # 策略权重更新：(action_type, anomaly_type) 维度
    if decision and anomaly:
        key = f"{decision.action_type}:{anomaly.type}"
        w = session.get(StrategyWeight, key)
        if w is None:
            w = StrategyWeight(id=key, action_type=decision.action_type, context=anomaly.type,
                               weight=1.0, updated_at=timeutil.now_iso())
        w.wins = w.wins + (1 if verdict == "effective" else 0)
        w.losses = w.losses + (1 if verdict == "ineffective" else 0)
        total = w.wins + w.losses
        if total:
            w.weight = round(0.5 + w.wins / total, 2)
        w.updated_at = timeutil.now_iso()
        session.add(w)
    session.commit()
    audit(session, AGENT_ACTOR, "evaluation.review", "review_report", report.id,
          detail={"execution_id": execution.id, "verdict": verdict,
                  "kpi_delta": kpi_delta}, trace_id=trace_id)
    return report


def review_all(session: Session, trace_id: str = "") -> list[ReviewReport]:
    """对所有满足 T+7 的已执行动作复盘。"""
    done = {r.execution_id for r in session.exec(select(ReviewReport)).all()}
    out = []
    for ex in session.exec(select(Execution).where(Execution.status == "success")).all():
        if ex.id in done:
            continue
        try:
            out.append(review_execution(session, ex, trace_id))
        except ValueError:
            continue  # 未满 T+7，跳过
    return out


def agent_metrics(session: Session) -> dict:
    """评估看板：异常发现时效 / 根因准确率 / 建议采纳率 / 自动执行成功率 / 高风险合规率。"""
    anomalies = session.exec(select(Anomaly)).all()
    decisions = session.exec(select(DecisionCard)).all()
    executions = session.exec(select(Execution)).all()

    latencies = [a.detection_latency_h for a in anomalies if a.detection_latency_h is not None]
    adoption = sum(1 for d in decisions
                   if d.status in ("executed", "executing", "approved", "pending_approval"))
    auto_execs = [e for e in executions if e.tool_name != "request_approval"]
    # 成功率口径：只在真实落地的执行中统计（compensated 是成功后被人工主动回退，不算失败）
    decided = [e for e in auto_execs if e.status in ("success", "failed")]
    success = [e for e in decided if e.status == "success"]
    high_risk_executed = [e for e in success
                          if (session.get(DecisionCard, e.decision_id) or DecisionCard(
                              requires_approval=0)).requires_approval]
    compliant = 0
    for e in high_risk_executed:
        from ..models import Approval
        ap = session.exec(select(Approval).where(
            Approval.decision_id == e.decision_id, Approval.status == "approved")).first()
        if ap:
            compliant += 1

    # 根因准确率（对有故事线真值的异常）
    from ..models import Diagnosis, Storyline
    truth = {sl.id: sl.truth_root_cause for sl in session.exec(select(Storyline)).all()}
    hit, total = 0, 0
    for dg in session.exec(select(Diagnosis)).all():
        a = session.get(Anomaly, dg.anomaly_id)
        if a and a.storyline_id in truth:
            total += 1
            rcs = [r["code"] for r in json.loads(dg.root_causes)[:3]]
            if truth[a.storyline_id] in rcs:
                hit += 1

    def pct(a, b):
        return round(a / b * 100, 1) if b else None

    return {
        "anomaly_count": len(anomalies),
        "detection_latency_avg_h": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "detection_latency_max_h": max(latencies) if latencies else None,
        "root_cause_accuracy_pct": pct(hit, total),
        "root_cause_evaluated": total,
        "suggestion_adoption_pct": pct(adoption, len(decisions)),
        "decision_count": len(decisions),
        "auto_exec_success_pct": pct(len(success), len(decided)),
        "auto_exec_count": len(auto_execs),
        "high_risk_approval_compliance_pct": pct(compliant, len(high_risk_executed)),
        "high_risk_executed": len(high_risk_executed),
    }
