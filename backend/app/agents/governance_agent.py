# -*- coding: utf-8 -*-
"""治理 Agent：所有写入动作的统一治理入口（权限校验 → Policy 评估 → 审批/放行 → 留痕）。

供执行层与人工路径复用；Agent 自动执行硬上限 L2，L3 一律转人工审批，L4 一律拒绝。
"""
from sqlmodel import Session

from ..governance.approvals import decide_approval, create_approval
from ..governance.audit import audit
from ..governance.auth import AGENT_ACTOR, Actor
from ..governance.policy import PolicyDecision, evaluate


def policy_check(actor: Actor | None, action_type: str, params: dict) -> PolicyDecision:
    """执行前治理校验（决策层与执行层各调用一次，纵深防御）。"""
    return evaluate(actor, action_type, params)


def request_approval(session: Session, decision, reasons: list[str], trace_id: str = ""):
    """高风险动作 → 审批单（Human-in-the-loop）。"""
    return create_approval(session, decision, reasons, trace_id=trace_id)


def human_decide(session: Session, approval_id: str, decision: str, approver: Actor,
                 note: str = ""):
    """人工审批决定（仅 L3 风控审批人）。"""
    return decide_approval(session, approval_id, decision, approver, note)


def audit_log(session: Session, action: str, detail: dict, trace_id: str = "",
              resource_type: str = "", resource_id: str = "", result: str = "success"):
    """治理留痕。"""
    return audit(session, AGENT_ACTOR, action, resource_type, resource_id,
                 detail=detail, result=result, trace_id=trace_id)
