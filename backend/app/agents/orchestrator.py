# -*- coding: utf-8 -*-
"""主 Agent（编排器）：目标—感知—诊断—决策—执行—治理—评估 全流程状态机。"""
from sqlmodel import Session

from ..core import timeutil
from ..governance.audit import audit
from ..governance.auth import AGENT_ACTOR
from . import decision, diagnosis, evaluation, execution, perception


def run_pipeline(session: Session) -> dict:
    """感知 → 诊断 → 决策 → 执行（低风险自动 / 高风险转审批）。"""
    trace_id = timeutil.new_id("trc")
    steps = []
    r1 = perception.scan(session, trace_id)
    steps.append({"step": "perception", "new_anomalies": r1["new_anomalies"]})
    diags = diagnosis.diagnose_all(session, trace_id)
    steps.append({"step": "diagnosis", "diagnosed": len(diags)})
    cards = decision.decide_all(session, trace_id)
    steps.append({"step": "decision", "decision_cards": len(cards)})
    r4 = execution.execute_eligible(session, trace_id)
    steps.append({"step": "execution",
                  "auto_executed": len(r4["auto_executed"]),
                  "pending_approvals": len(r4["pending_approvals"])})
    audit(session, AGENT_ACTOR, "orchestrator.run_pipeline", "pipeline", trace_id,
          detail={"steps": steps}, trace_id=trace_id)
    return {"trace_id": trace_id, "steps": steps}


def run_demo_cycle(session: Session, approve_high_risk: bool = True) -> dict:
    """演示闭环：扫描→诊断→决策→执行→（人工审批）→ T+7 推演 → 复盘 → 指标。"""
    from ..governance.approvals import decide_approval
    from ..governance.auth import Actor
    from ..models import Approval
    from ..world.timemachine import advance_days
    from sqlmodel import select

    result = run_pipeline(session)
    approvals = session.exec(select(Approval).where(Approval.status == "pending")).all()
    approved = 0
    if approve_high_risk:
        risk_actor = Actor(id="usr_risk_01", username="risk_approver_01",
                           name="风控审批人-吴风控", role="risk_approver")
        for ap in approvals:
            decide_approval(session, ap.id, "approve", risk_actor,
                            note="演示：风控审批通过")
            approved += 1
    executed = execution.execute_approved(session, result["trace_id"])
    advanced = advance_days(session, 7)
    reviews = evaluation.review_all(session, result["trace_id"])
    metrics = evaluation.agent_metrics(session)
    result |= {"approvals_approved": approved, "executed_after_approval": len(executed),
               "world_advanced": advanced, "reviews": len(reviews), "metrics": metrics}
    return result
