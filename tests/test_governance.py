# -*- coding: utf-8 -*-
"""目标8测试：治理层（权限矩阵 / Policy Engine / 审批流 / 审计 / Human-in-the-loop）。"""
import uuid

from sqlmodel import select

from app.governance.auth import Actor, ROLE_MAX_LEVEL
from app.governance.policy import evaluate
from app.models import Approval, AuditLog, DecisionCard

AGENT = Actor(id="usr_agent", username="agent_service", name="Agent",
              role="agent_service", is_agent=True)
PLANNER = Actor(id="usr_planner_01", username="p", name="计划员", role="supply_planner")
RISK = Actor(id="usr_risk_01", username="risk_approver_01", name="风控", role="risk_approver")


def test_role_matrix():
    assert ROLE_MAX_LEVEL["agent_service"] == 2
    assert ROLE_MAX_LEVEL["risk_approver"] == 3
    assert ROLE_MAX_LEVEL["store_manager"] == 2
    assert ROLE_MAX_LEVEL["hq_ops"] == 2


def test_policy_thresholds():
    # 补货金额阈值
    d = evaluate(AGENT, "replenish", {"amount": 8000})
    assert d.allowed and not d.requires_approval and d.risk_level == "low"
    d = evaluate(AGENT, "replenish", {"amount": 50000})
    assert d.allowed and d.requires_approval
    d = evaluate(AGENT, "replenish", {"amount": 200000})
    assert not d.allowed  # L4 硬上限
    # 促销折扣阈值
    d = evaluate(AGENT, "promo", {"discount_pct": 8, "budget": 5000})
    assert d.allowed and not d.requires_approval
    d = evaluate(AGENT, "promo", {"discount_pct": 15, "budget": 5000})
    assert d.requires_approval and any("10%" in r for r in d.reasons)
    d = evaluate(AGENT, "promo", {"discount_pct": 40, "budget": 5000})
    assert not d.allowed  # L4
    # 跨区域调拨
    d = evaluate(AGENT, "transfer", {"amount": 1000, "cross_region": True})
    assert d.requires_approval and any("跨区域" in r for r in d.reasons)
    d = evaluate(AGENT, "transfer", {"amount": 1000, "cross_region": False})
    assert d.allowed and not d.requires_approval
    # 价格变更一律审批
    d = evaluate(AGENT, "price_change", {})
    assert d.requires_approval
    # 白名单外动作
    d = evaluate(AGENT, "close_store", {})
    assert not d.allowed and "禁止" in d.denied_reason
    d = evaluate(AGENT, "unknown_action", {})
    assert not d.allowed and "白名单" in d.denied_reason


def test_policy_role_check():
    # 匿名（L0）不可写
    d = evaluate(None, "replenish", {"amount": 100})
    assert not d.allowed and "权限不足" in d.denied_reason
    # 计划员可低风险补货
    d = evaluate(PLANNER, "replenish", {"amount": 100})
    assert d.allowed


def test_approval_human_in_the_loop(client, session):
    """Human-in-the-loop：创建待审批 → 风控处理 → 决策卡状态联动。"""
    # 构造一张需要审批的决策卡
    card = DecisionCard(
        id=f"dcs_test_{uuid.uuid4().hex[:6]}", anomaly_id="ano_x", action_type="promo",
        action='{"name":"治理测试促销","discount_pct":15,"budget":20000}',
        rationale="测试", risk_level="high", requires_approval=1,
        status="pending_approval", created_at="2026-01-01T00:00:00")
    session.add(card)
    session.commit()
    from app.governance.approvals import create_approval
    ap = create_approval(session, card, ["折扣超过 10% 必须审批"])
    assert ap.status == "pending"

    # 无 token → 401
    r = client.post(f"/api/gov/approvals/{ap.id}/decide", json={"decision": "approve"})
    assert r.status_code == 401
    # 非 L3 角色 → 403
    r = client.post(f"/api/gov/approvals/{ap.id}/decide", json={"decision": "approve"},
                    headers={"X-Auth-Token": "tok_hq_01"})
    assert r.status_code == 403
    # 风控驳回 → 决策卡 rejected
    r = client.post(f"/api/gov/approvals/{ap.id}/decide",
                    json={"decision": "reject", "note": "折扣过大"},
                    headers={"X-Auth-Token": "tok_risk_01"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    session.expire_all()  # API 在另一会话提交，刷新本会话缓存
    assert session.get(DecisionCard, card.id).status == "rejected"
    # 重复处理 → 409
    r = client.post(f"/api/gov/approvals/{ap.id}/decide", json={"decision": "approve"},
                    headers={"X-Auth-Token": "tok_risk_01"})
    assert r.status_code == 409


def test_audit_log_immutable_record(client):
    """审计日志记录治理决策（拒绝也留痕）。"""
    r = client.get("/api/gov/audit-logs", params={"action": "approval", "limit": 20})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    denied = [i for i in items if i["result"] == "denied"]
    assert denied, "权限拒绝应写入审计"


def test_agent_cannot_execute_high_risk_without_approval(session):
    """Agent 直接执行高风险 → 被转审批而非执行。"""
    from app.agents import execution
    from app.governance.idempotency import WriteDenied
    card = DecisionCard(
        id=f"dcs_hr_{uuid.uuid4().hex[:6]}", anomaly_id="ano_y", action_type="transfer",
        action='{"from_store_id":"S001","to_store_id":"S004","product_id":"P00001","qty":10}',
        rationale="跨区调拨测试", risk_level="high", requires_approval=1,
        status="suggested", created_at="2026-01-01T00:00:00")
    session.add(card)
    session.commit()
    ex = execution.execute_decision(session, card)
    assert ex.tool_name == "request_approval"
    assert card.status == "pending_approval"
    assert session.exec(select(Approval).where(
        Approval.decision_id == card.id, Approval.status == "pending")).first()
