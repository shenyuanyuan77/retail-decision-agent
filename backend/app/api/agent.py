# -*- coding: utf-8 -*-
"""Agent API：感知/诊断/决策/执行/评估/编排 + 异常/决策/执行/复盘查询 + KPI。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..agents import decision, diagnosis, evaluation, execution, orchestrator, perception
from ..core import timeutil
from ..governance.auth import Actor, AGENT_ACTOR
from ..governance.idempotency import WriteDenied
from ..models import (Anomaly, Approval, DecisionCard, Diagnosis, Execution, ReviewReport,
                      SalesOrder, Store, Storyline, StrategyWeight)
from .deps import get_actor, get_session

agent_router = APIRouter(prefix="/agent", tags=["agent-智能体"])
kpi_router = APIRouter(prefix="/kpi", tags=["kpi-看板指标"])


@agent_router.post("/scan")
def api_scan(session: Session = Depends(get_session)):
    return perception.scan(session)


@agent_router.post("/diagnose")
def api_diagnose(session: Session = Depends(get_session), anomaly_id: str = ""):
    if anomaly_id:
        a = session.get(Anomaly, anomaly_id)
        if not a:
            raise HTTPException(404, "异常不存在")
        d = diagnosis.diagnose(session, a)
    else:
        diags = diagnosis.diagnose_all(session)
        return {"diagnosed": len(diags),
                "items": [json.loads(d.root_causes) for d in diags]}
    return {"anomaly_id": anomaly_id, "root_causes": json.loads(d.root_causes),
            "summary": d.summary, "narrative": d.narrative}


@agent_router.post("/decide")
def api_decide(session: Session = Depends(get_session), anomaly_id: str = ""):
    if anomaly_id:
        a = session.get(Anomaly, anomaly_id)
        if not a:
            raise HTTPException(404, "异常不存在")
        cards = decision.decide(session, a)
    else:
        cards = decision.decide_all(session)
    return {"decision_cards": len(cards),
            "items": [_card_dict(c) for c in cards]}


def _card_dict(c: DecisionCard) -> dict:
    d = c.model_dump()
    d["action"] = json.loads(c.action)
    d["risk_reasons"] = json.loads(c.risk_reasons or "[]")
    d["expected_impact"] = json.loads(c.expected_impact or "{}")
    d["constraints_checked"] = json.loads(c.constraints_checked or "[]")
    return d


@agent_router.post("/execute")
def api_execute(session: Session = Depends(get_session), decision_id: str = ""):
    if decision_id:
        card = session.get(DecisionCard, decision_id)
        if not card:
            raise HTTPException(404, "决策卡不存在")
        ex = execution.execute_decision(session, card)
        return {"execution": ex.model_dump()}
    r = execution.execute_eligible(session)
    return {"trace_id": r["trace_id"],
            "auto_executed": len(r["auto_executed"]),
            "pending_approvals": len(r["pending_approvals"])}


class CompensateIn(BaseModel):
    execution_id: str


@agent_router.post("/compensate")
def api_compensate(p: CompensateIn, session: Session = Depends(get_session),
                   actor: Actor = Depends(get_actor)):
    try:
        return execution.compensate(session, p.execution_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@agent_router.post("/pipeline")
def api_pipeline(session: Session = Depends(get_session)):
    return orchestrator.run_pipeline(session)


@agent_router.post("/demo-cycle")
def api_demo_cycle(session: Session = Depends(get_session)):
    """演示闭环：流水线 → 审批(演示自动通过) → T+7 推演 → 复盘 → 指标。"""
    return orchestrator.run_demo_cycle(session)


@agent_router.post("/review")
def api_review(session: Session = Depends(get_session), execution_id: str = ""):
    try:
        if execution_id:
            ex = session.get(Execution, execution_id)
            if not ex:
                raise HTTPException(404, "执行记录不存在")
            r = evaluation.review_execution(session, ex)
        else:
            reports = evaluation.review_all(session)
            return {"reviews": len(reports), "items": [_review_dict(x) for x in reports]}
        return _review_dict(r)
    except ValueError as e:
        raise HTTPException(409, str(e))


def _review_dict(r: ReviewReport) -> dict:
    d = r.model_dump()
    d["period_before"] = json.loads(r.period_before or "{}")
    d["period_after"] = json.loads(r.period_after or "{}")
    d["kpi_delta"] = json.loads(r.kpi_delta or "{}")
    d["reasons"] = json.loads(r.reasons or "[]")
    return d


@agent_router.get("/anomalies")
def api_anomalies(status: str = "", severity: str = "", storyline_only: bool = False,
                  limit: int = 100, session: Session = Depends(get_session)):
    q = select(Anomaly)
    if status:
        q = q.where(Anomaly.status == status)
    if severity:
        q = q.where(Anomaly.severity == severity)
    if storyline_only:
        q = q.where(Anomaly.storyline_id != "")
    rows = session.exec(q.order_by(Anomaly.deviation_pct).limit(limit)).all()
    items = []
    for a in rows:
        d = a.model_dump()
        d["evidence"] = json.loads(a.evidence or "[]")
        store = session.get(Store, a.store_id)
        d["store_name"] = store.name if store else ""
        items.append(d)
    return {"items": items}


@agent_router.get("/anomalies/{anomaly_id}")
def api_anomaly_detail(anomaly_id: str, session: Session = Depends(get_session)):
    a = session.get(Anomaly, anomaly_id)
    if not a:
        raise HTTPException(404, "异常不存在")
    d = a.model_dump()
    d["evidence"] = json.loads(a.evidence or "[]")
    d["diagnosis"] = None
    dg = session.exec(select(Diagnosis).where(
        Diagnosis.anomaly_id == anomaly_id).order_by(Diagnosis.created_at.desc())).first()
    if dg:
        d["diagnosis"] = {
            "id": dg.id, "summary": dg.summary, "narrative": dg.narrative,
            "root_causes": json.loads(dg.root_causes),
            "dimension_drill": json.loads(dg.dimension_drill or "[]"),
            "hypothesis_log": json.loads(dg.hypothesis_log or "[]")[:12],
            "created_at": dg.created_at}
    d["decisions"] = [_card_dict(c) for c in session.exec(
        select(DecisionCard).where(DecisionCard.anomaly_id == anomaly_id)).all()]
    return d


@agent_router.get("/decisions")
def api_decisions(status: str = "", limit: int = 200,
                  session: Session = Depends(get_session)):
    q = select(DecisionCard)
    if status:
        q = q.where(DecisionCard.status == status)
    rows = session.exec(q.order_by(DecisionCard.created_at.desc()).limit(limit)).all()
    return {"items": [_card_dict(c) for c in rows]}


@agent_router.get("/executions")
def api_executions(limit: int = 200, session: Session = Depends(get_session)):
    rows = session.exec(select(Execution).order_by(
        Execution.created_at.desc()).limit(limit)).all()
    return {"items": [e.model_dump() for e in rows]}


@agent_router.get("/reviews")
def api_reviews(limit: int = 100, session: Session = Depends(get_session)):
    rows = session.exec(select(ReviewReport).order_by(
        ReviewReport.created_at.desc()).limit(limit)).all()
    return {"items": [_review_dict(r) for r in rows]}


@agent_router.get("/strategy-weights")
def api_weights(session: Session = Depends(get_session)):
    return {"items": [w.model_dump() for w in session.exec(select(StrategyWeight)).all()]}


@agent_router.get("/storylines")
def api_storylines(session: Session = Depends(get_session)):
    rows = session.exec(select(Storyline)).all()
    return {"items": [s.model_dump() for s in rows]}


# ---------------- KPI 看板 ----------------

@kpi_router.get("/overview")
def kpi_overview(session: Session = Depends(get_session)):
    from datetime import timedelta
    from ..services import sales as sales_svc
    today = timeutil.business_today(session)
    d7 = (today - timedelta(days=6)).isoformat()
    p7 = (today - timedelta(days=13)).isoformat()
    prev7_start = (today - timedelta(days=13)).isoformat()
    prev7_end = (today - timedelta(days=7)).isoformat()
    cur = sales_svc.summary(session, start=d7, end=today.isoformat())
    prev = sales_svc.summary(session, start=prev7_start, end=prev7_end)
    anomalies_open = len(session.exec(select(Anomaly).where(
        Anomaly.status.in_(("open", "diagnosed", "decided", "acting")))).all())  # type: ignore
    approvals_pending = len(session.exec(select(Approval).where(
        Approval.status == "pending")).all())
    executed = len(session.exec(select(Execution).where(Execution.status == "success")).all())
    return {
        "biz_date": today.isoformat(),
        "sales_7d": cur["sales_amount"], "sales_prev7d": prev["sales_amount"],
        "sales_mom_pct": round((cur["sales_amount"] - prev["sales_amount"])
                               / prev["sales_amount"] * 100, 1) if prev["sales_amount"] else None,
        "qty_7d": cur["sales_qty"], "gross_margin_rate": cur["gross_margin_rate"],
        "anomalies_open": anomalies_open, "approvals_pending": approvals_pending,
        "executed_actions": executed,
        "agent_metrics": evaluation.agent_metrics(session),
    }


@kpi_router.get("/trend")
def kpi_trend(days: int = 30, session: Session = Depends(get_session)):
    from datetime import timedelta
    from sqlalchemy import func
    today = timeutil.business_today(session)
    start = (today - timedelta(days=days - 1)).isoformat()
    rows = session.exec(
        select(SalesOrder.biz_date, func.sum(SalesOrder.amount), func.sum(SalesOrder.qty))
        .where(SalesOrder.biz_date >= start)
        .group_by(SalesOrder.biz_date).order_by(SalesOrder.biz_date)).all()
    by_date = {r[0]: (round(r[1] or 0, 2), r[2] or 0) for r in rows}
    out = []
    d = today - timedelta(days=days - 1)
    while d <= today:
        amt, qty = by_date.get(d.isoformat(), (0.0, 0))
        out.append({"date": d.isoformat(), "amount": amt, "qty": qty})
        d += timedelta(days=1)
    return {"items": out}


@kpi_router.get("/stores")
def kpi_stores(limit: int = 50, session: Session = Depends(get_session)):
    from datetime import timedelta
    from ..services import sales as sales_svc
    from sqlmodel import func
    today = timeutil.business_today(session)
    start = (today - timedelta(days=6)).isoformat()
    rows = session.exec(select(SalesOrder.store_id, func.sum(SalesOrder.amount)).where(
        SalesOrder.biz_date >= start, SalesOrder.biz_date <= today.isoformat()
    ).group_by(SalesOrder.store_id)).all()
    stores = {s.id: s.name for s in session.exec(select(Store)).all()}
    items = sorted([{"store_id": sid, "store_name": stores.get(sid, sid),
                     "amount_7d": round(amt, 2)} for sid, amt in rows],
                   key=lambda x: -x["amount_7d"])[:limit]
    return {"items": items}


def register(app):
    from ..core import config
    app.include_router(agent_router, prefix=config.API_PREFIX)
    app.include_router(kpi_router, prefix=config.API_PREFIX)
