# -*- coding: utf-8 -*-
"""执行 Agent：决策卡 → 业务动作（六大写工具 + 状态机 + 幂等 + 补偿）。

工具：create_replenishment_order / create_transfer_order / create_campaign /
     create_ticket_task / request_approval / audit_log。
状态机：pending → running → success | failed | rejected | compensated。
低风险自动执行；高风险（requires_approval）一律创建审批单转人工，禁止绕过。
"""
import json

from sqlmodel import Session, select

from ..core import timeutil
from ..governance.approvals import create_approval
from ..governance.audit import audit
from ..governance.auth import AGENT_ACTOR
from ..governance.idempotency import WriteDenied
from ..governance.policy import evaluate
from ..models import Approval, DecisionCard, Execution
from ..services import cs as cs_svc
from ..services import inventory as inv_svc
from ..services import members as member_svc

VALID_TRANSITIONS = {
    "pending": {"running", "rejected"},
    "running": {"success", "failed"},
    "success": {"compensated"},
    "failed": set(),
    "rejected": set(),
    "compensated": set(),
}


def _transition(execution: Execution, new_status: str):
    if new_status not in VALID_TRANSITIONS.get(execution.status, set()):
        raise ValueError(f"非法状态迁移 {execution.status} → {new_status}")
    execution.status = new_status


# ---------------- 六大执行工具（目标7 要求命名） ----------------

def create_replenishment_order(session: Session, action: dict, trace_id: str,
                               idempotency_key: str, approved_id: str = "") -> dict:
    return inv_svc.create_replenishment(
        session, AGENT_ACTOR,
        {**action, "idempotency_key": idempotency_key, "dry_run": False,
         "approved_by_approval_id": approved_id}, trace_id=trace_id)


def create_transfer_order(session: Session, action: dict, trace_id: str,
                          idempotency_key: str, approved_id: str = "") -> dict:
    return inv_svc.create_transfer(
        session, AGENT_ACTOR,
        {**action, "idempotency_key": idempotency_key, "dry_run": False,
         "approved_by_approval_id": approved_id}, trace_id=trace_id)


def create_campaign(session: Session, action: dict, trace_id: str,
                    idempotency_key: str, approved_id: str = "") -> dict:
    return member_svc.create_campaign(
        session, AGENT_ACTOR,
        {**action, "idempotency_key": idempotency_key, "dry_run": False,
         "approved_by_approval_id": approved_id}, trace_id=trace_id)


def create_ticket_task(session: Session, action: dict, trace_id: str,
                       idempotency_key: str, approved_id: str = "") -> dict:
    return cs_svc.create_ticket_task(
        session, AGENT_ACTOR,
        {**action, "idempotency_key": idempotency_key, "dry_run": False,
         "approved_by_approval_id": approved_id}, trace_id=trace_id)


def request_approval(session: Session, decision: DecisionCard, reasons: list,
                     trace_id: str) -> Approval:
    return create_approval(session, decision, reasons, trace_id=trace_id)


def audit_log(session: Session, action: str, detail: dict, trace_id: str) -> None:
    audit(session, AGENT_ACTOR, action, "execution", "", detail=detail, trace_id=trace_id)


TOOL_MAP = {
    "replenish": create_replenishment_order,
    "transfer": create_transfer_order,
    "promo": create_campaign,
    "member_reach": create_campaign,
    "cs_followup": create_ticket_task,
}


def execute_decision(session: Session, decision: DecisionCard, trace_id: str = "",
                     approved_by_approval_id: str = "") -> Execution:
    """执行单张决策卡（治理硬校验：高风险无审批单 → 拒绝）。"""
    trace_id = trace_id or decision.trace_id or timeutil.new_id("trc")
    action = json.loads(decision.action)
    params = dict(action.get("_policy_params") or {})
    # 兜底：从动作参数推导治理字段（防止手工构造的决策卡绕过阈值判断）
    if "amount" not in params or params.get("amount") is None:
        from ..models import Product as _P
        prod = session.get(_P, action.get("product_id", ""))
        params["amount"] = round(action.get("qty", 0) * prod.cost_price, 2) if prod else 0
    if decision.action_type == "transfer" and "cross_region" not in params:
        from ..models import Store as _S
        sa = session.get(_S, action.get("from_store_id", ""))
        sb = session.get(_S, action.get("to_store_id", ""))
        params["cross_region"] = bool(sa and sb and sa.region_id != sb.region_id)
    params.setdefault("discount_pct", action.get("discount_pct", 0) or 0)
    params.setdefault("budget", action.get("budget", 0) or 0)
    params["task_type"] = action.get("type") if decision.action_type == "cs_followup" else "callback"

    # 治理二次校验（纵深防御：决策时与执行时各校验一次）
    pol = evaluate(AGENT_ACTOR, decision.action_type, params)
    if not pol.allowed:
        decision.status = "rejected"
        session.add(decision)
        session.commit()
        audit(session, AGENT_ACTOR, "execution.denied_by_policy", "decision_card",
              decision.id, detail={"reason": pol.denied_reason}, result="denied",
              trace_id=trace_id)
        raise WriteDenied(f"治理拒绝: {pol.denied_reason}")

    if pol.requires_approval and not approved_by_approval_id:
        decision.status = "pending_approval"
        session.add(decision)
        session.commit()
        ap = request_approval(session, decision, pol.reasons, trace_id)
        execution = Execution(
            id=timeutil.new_id("exe"), decision_id=decision.id, anomaly_id=decision.anomaly_id,
            tool_name="request_approval", idempotency_key=f"{decision.id}:approval",
            request=json.dumps({"action": action}, ensure_ascii=False),
            status="pending", trace_id=trace_id, created_at=timeutil.now_iso(),
            result=json.dumps({"approval_id": ap.id, "status": "pending_approval"},
                              ensure_ascii=False))
        session.add(execution)
        session.commit()
        return execution

    execution = Execution(
        id=timeutil.new_id("exe"), decision_id=decision.id, anomaly_id=decision.anomaly_id,
        tool_name=f"create_{decision.action_type}", idempotency_key=decision.id,
        request=json.dumps(action, ensure_ascii=False), status="pending",
        trace_id=trace_id, created_at=timeutil.now_iso())
    session.add(execution)
    session.commit()
    _transition(execution, "running")
    decision.status = "executing"
    session.add(decision)
    session.commit()

    tool_fn = TOOL_MAP.get(decision.action_type)
    try:
        if tool_fn is None:
            raise ValueError(f"未知动作类型 {decision.action_type}")
        result = tool_fn(session, action, trace_id, decision.id, approved_by_approval_id)
        _transition(execution, "success")
        execution.result = json.dumps(result, ensure_ascii=False, default=str)
        execution.business_ref = result.get("id") or result.get("order_no") or ""
        execution.finished_at = timeutil.now_iso()
        decision.status = "executed" if not result.get("replayed") else "executed"
        session.add(execution)
        session.add(decision)
        session.commit()
        audit(session, AGENT_ACTOR, f"execution.{decision.action_type}", "execution",
              execution.id,
              detail={"decision_id": decision.id, "result": result,
                      "replayed": result.get("replayed", False)},
              trace_id=trace_id)
    except WriteDenied as e:
        session.rollback()
        _rejudge_after_denial(session, decision, execution, str(e), trace_id)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        _transition(execution, "failed")
        execution.error = str(exc)[:500]
        execution.finished_at = timeutil.now_iso()
        decision.status = "failed"
        session.add(execution)
        session.add(decision)
        session.commit()
        audit(session, AGENT_ACTOR, "execution.failed", "execution", execution.id,
              detail={"decision_id": decision.id, "error": str(exc)[:300]},
              result="error", trace_id=trace_id)
    return execution


def _rejudge_after_denial(session: Session, decision: DecisionCard,
                          execution: Execution, reason: str, trace_id: str):
    """治理在执行期拦截（如库存已变化）→ 转审批或失败。"""
    if "审批" in reason:
        decision.status = "pending_approval"
        _transition(execution, "rejected")
        execution.result = json.dumps({"denied": reason}, ensure_ascii=False)
        session.add(execution)
        session.add(decision)
        session.commit()
        request_approval(session, decision, [reason], trace_id)
    else:
        _transition(execution, "failed")
        execution.error = reason[:500]
        decision.status = "failed"
        session.add(execution)
        session.add(decision)
        session.commit()
    audit(session, AGENT_ACTOR, "execution.rejected", "execution", execution.id,
          detail={"decision_id": decision.id, "reason": reason}, result="denied",
          trace_id=trace_id)


def execute_approved(session: Session, trace_id: str = "") -> list[Execution]:
    """审批通过的决策 → 执行（携带审批单号）。"""
    out = []
    approved_cards = session.exec(select(DecisionCard).where(
        DecisionCard.status == "approved")).all()
    for card in approved_cards:
        ap = session.exec(select(Approval).where(
            Approval.decision_id == card.id, Approval.status == "approved")).first()
        approved_id = ap.id if ap else ""
        out.append(execute_decision(session, card, trace_id, approved_id))
    return out


def execute_eligible(session: Session, trace_id: str = "") -> dict:
    """执行 Agent 主入口：低风险自动执行，高风险创建审批。"""
    summary_trace = trace_id or timeutil.new_id("trc")
    suggested = session.exec(select(DecisionCard).where(
        DecisionCard.status == "suggested")).all()
    auto, to_approval = [], []
    for card in suggested:
        case_trace = card.trace_id or summary_trace  # 继承案例 trace，保证链路可追溯
        if card.requires_approval:
            ap = request_approval(session, card, json.loads(card.risk_reasons or "[]"), case_trace)
            card.status = "pending_approval"
            session.add(card)
            session.commit()
            to_approval.append(ap)
        else:
            auto.append(execute_decision(session, card, case_trace))
    audit(session, AGENT_ACTOR, "execution.execute_eligible", "execution", "-",
          detail={"auto_executed": len(auto), "pending_approvals": len(to_approval)},
          trace_id=trace_id)
    return {"trace_id": trace_id, "auto_executed": auto, "pending_approvals": to_approval}


def compensate(session: Session, execution_id: str, trace_id: str = "") -> dict:
    """补偿：按业务类型反向操作。"""
    execution = session.get(Execution, execution_id)
    if not execution:
        raise KeyError(f"执行记录不存在: {execution_id}")
    if execution.status != "success":
        return {"execution_id": execution_id, "status": execution.status, "skipped": True}
    trace_id = trace_id or execution.trace_id
    decision = session.get(DecisionCard, execution.decision_id)
    result = json.loads(execution.result or "{}")
    biz_id = result.get("id", "")
    if decision is None:
        raise KeyError("关联决策卡不存在")
    if decision.action_type == "replenish":
        inv_svc.compensate_replenishment(session, biz_id, AGENT_ACTOR, trace_id)
    elif decision.action_type == "transfer":
        inv_svc.compensate_transfer(session, biz_id, AGENT_ACTOR, trace_id)
    elif decision.action_type in ("promo", "member_reach"):
        from ..models import Campaign
        camp = session.get(Campaign, biz_id)
        if camp:
            camp.status = "cancelled"
            session.add(camp)
            session.commit()
    elif decision.action_type == "cs_followup":
        from ..models import TicketTask
        task = session.get(TicketTask, biz_id)
        if task:
            task.status = "cancelled"
            session.add(task)
            session.commit()
    _transition(execution, "compensated")
    execution.compensated_at = timeutil.now_iso()
    decision.status = "compensated"
    session.add(execution)
    session.add(decision)
    session.commit()
    audit(session, AGENT_ACTOR, "execution.compensate", "execution", execution_id,
          detail={"decision_id": decision.id, "business_ref": execution.business_ref},
          trace_id=trace_id)
    return {"execution_id": execution_id, "status": "compensated"}
