# -*- coding: utf-8 -*-
"""审批流（Human-in-the-loop）：高风险动作 → 审批单 → 人工决定 → 回写决策卡。"""
from sqlmodel import Session, select

from ..core import timeutil
from ..models import Approval, DecisionCard
from .audit import audit
from .auth import Actor


def create_approval(session: Session, decision: DecisionCard, reasons: list[str],
                    trace_id: str = "") -> Approval:
    ap = Approval(
        id=timeutil.new_id("apr"),
        decision_id=decision.id,
        anomaly_id=decision.anomaly_id,
        action_type=decision.action_type,
        summary=(f"[{decision.action_type}] {decision.rationale[:120]} "
                 f"risk={decision.risk_level}"),
        risk_reasons=__import__("json").dumps(reasons, ensure_ascii=False),
        status="pending",
        requested_by="agent_service",
        requested_at=timeutil.now_iso(),
    )
    session.add(ap)
    session.commit()
    audit(session, Actor(id="usr_agent", username="agent_service", name="经营决策Agent",
                         role="agent_service", is_agent=True),
          "approval.request", "approval", ap.id,
          detail={"decision_id": decision.id, "reasons": reasons}, trace_id=trace_id)
    return ap


def decide_approval(session: Session, approval_id: str, decision: str,
                    approver: Actor, note: str = "") -> Approval:
    ap = session.get(Approval, approval_id)
    if not ap:
        raise KeyError(f"审批单不存在: {approval_id}")
    if ap.status != "pending":
        raise ValueError(f"审批单已处理: {ap.status}")
    if decision not in ("approve", "reject"):
        raise ValueError("decision 必须为 approve/reject")
    if approver is None or approver.max_level < 3:
        from .idempotency import WriteDenied
        audit(session, approver, "approval.decide", "approval", approval_id,
              detail={"error": "无审批权限（需 L3 风控审批人）"}, result="denied")
        raise WriteDenied("仅风控审批人（L3）可处理审批单")

    ap.status = "approved" if decision == "approve" else "rejected"
    ap.decided_by = approver.username
    ap.decided_at = timeutil.now_iso()
    ap.decision_note = note
    session.add(ap)

    card = session.get(DecisionCard, ap.decision_id)
    if card:
        card.status = "approved" if decision == "approve" else "rejected"
        card.decided_by = approver.username
        card.decided_at = timeutil.now_iso()
        session.add(card)
    session.commit()
    audit(session, approver, "approval.decide", "approval", approval_id,
          detail={"decision": decision, "note": note, "decision_card": ap.decision_id},
          result="success")
    return ap
