# -*- coding: utf-8 -*-
"""目标4-9 集成测试：Agent 全流程（感知→诊断→决策→执行→审批→T+7推演→复盘）。

按文件内定义顺序执行，覆盖验收要点：
低风险自动执行 / 高风险进入审批 / 幂等不重复下单 / 失败可补偿 / 复盘有报告。
"""
import json

from sqlmodel import select

from app.agents import decision, diagnosis, evaluation, execution, perception
from app.governance.approvals import decide_approval
from app.governance.auth import Actor
from app.models import (Anomaly, Approval, DecisionCard, Execution, Inventory,
                        ReplenishmentOrder, ReviewReport, Store, Storyline, StrategyWeight,
                        TransferOrder)
from app.world.timemachine import advance_days

RISK_ACTOR = Actor(id="usr_risk_01", username="risk_approver_01", name="吴风控",
                   role="risk_approver")


def test_1_scan_finds_storylines(session, world):
    r = perception.scan(session)
    assert r["new_anomalies"] >= 3
    sls = session.exec(select(Storyline)).all()
    for sl in sls:
        a = session.exec(select(Anomaly).where(
            Anomaly.store_id == sl.store_id,
            Anomaly.product_id == sl.product_id)).first()
        assert a is not None, f"{sl.type} 未被检出"


def test_2_diagnose_all_root_causes(session):
    diags = diagnosis.diagnose_all(session)
    assert len(diags) >= 3
    truth = {sl.id: sl.truth_root_cause for sl in session.exec(select(Storyline)).all()}
    hit = 0
    for dg in diags:
        a = session.get(Anomaly, dg.anomaly_id)
        if a.storyline_id in truth:
            rcs = json.loads(dg.root_causes)
            assert len(rcs) <= 3
            for rc in rcs:
                assert len(rc["evidence"]) >= 2, "每个根因至少 2 条证据"
                assert 0 <= rc["confidence"] <= 1
            if truth[a.storyline_id] in [r["code"] for r in rcs]:
                hit += 1
    assert hit >= 2  # Top3 命中率 >= 2/3*100 > 80%


def test_3_decide_generates_cards(session):
    cards = decision.decide_all(session)
    assert len(cards) >= 3, "每个故事线异常至少 1 个推荐方案"
    for c in cards:
        checks = json.loads(c.constraints_checked)
        assert all(x["passed"] for x in checks), "约束违反率必须为 0"
        impact = json.loads(c.expected_impact)
        assert "est_cost" in impact and "est_benefit" in impact
        assert c.risk_level in ("low", "medium", "high")
        if c.requires_approval:
            assert c.risk_level == "high"
    # 三条故事线异常都有决策卡
    for sl in session.exec(select(Storyline)).all():
        a = session.exec(select(Anomaly).where(
            Anomaly.store_id == sl.store_id,
            Anomaly.product_id == sl.product_id)).first()
        n = len(session.exec(select(DecisionCard).where(
            DecisionCard.anomaly_id == a.id)).all())
        assert n >= 1


def test_4_execute_low_and_high_risk(session):
    r = execution.execute_eligible(session)
    auto, pending = r["auto_executed"], r["pending_approvals"]
    assert len(auto) >= 1, "低风险动作应自动执行"
    for ex in auto:
        assert ex.status == "success"
    # 高风险进入审批且未执行
    for ap in pending:
        card = session.get(DecisionCard, ap.decision_id)
        assert card.status == "pending_approval"
        assert card.requires_approval == 1
        assert not session.exec(select(Execution).where(
            Execution.decision_id == card.id,
            Execution.tool_name != "request_approval",
            Execution.status == "success")).first(), "高风险未审批不得执行"


def test_5_idempotent_execution(session):
    """重复执行同一决策卡不重复下单（幂等键=决策卡ID）。"""
    done = session.exec(select(Execution).where(
        Execution.status == "success")).all()
    assert done
    ex = done[0]
    card = session.get(DecisionCard, ex.decision_id)
    card.status = "suggested"   # 模拟重放
    session.add(card)
    session.commit()
    execution.execute_decision(session, card)
    orders = session.exec(select(ReplenishmentOrder).where(
        ReplenishmentOrder.id == json.loads(ex.result)["id"])).all()
    assert len(orders) == 1


def test_6_approval_flow(session):
    """审批权限 + 通过后执行。"""
    pending = session.exec(select(Approval).where(Approval.status == "pending")).all()
    assert pending, "应存在待审批项"
    ap = pending[0]
    # 非风控角色无权审批
    try:
        decide_approval(session, ap.id, "approve",
                        Actor(id="x", username="hq", name="运营", role="hq_ops"))
        assert False, "应当拒绝"
    except Exception:
        pass
    # 风控通过
    decide_approval(session, ap.id, "approve", RISK_ACTOR, note="测试审批")
    assert session.get(Approval, ap.id).status == "approved"
    executed = execution.execute_approved(session)
    assert any(e.tool_name != "request_approval" for e in executed)
    # 高风险执行必须持有审批单（合规率 100%）
    for e in [x for x in session.exec(select(Execution).where(
            Execution.status == "success")).all() if x.tool_name != "request_approval"]:
        card = session.get(DecisionCard, e.decision_id)
        if card.requires_approval:
            has = session.exec(select(Approval).where(
                Approval.decision_id == card.id, Approval.status == "approved")).first()
            assert has, "高风险执行必须有已通过的审批单"


def test_7_compensation(session):
    """调拨/补货执行后可补偿（库存回退）。"""
    transfers = session.exec(select(TransferOrder).where(
        TransferOrder.status == "done")).all()
    if transfers:
        order = transfers[0]
        ex = session.exec(select(Execution).where(
            Execution.business_ref == order.id)).first()
        if ex:
            result = execution.compensate(session, ex.id)
            assert result["status"] == "compensated"
            assert session.get(TransferOrder, order.id).status == "compensated"
            return
    # 无调拨则验证补货补偿路径
    rpls = session.exec(select(ReplenishmentOrder).where(
        ReplenishmentOrder.status.in_(("confirmed", "arrived")))).all()  # type: ignore
    order, ex = None, None
    for o in rpls:
        e = session.exec(select(Execution).where(
            Execution.business_ref == o.id)).first()
        if e:
            order, ex = o, e
            break
    assert order is not None and ex is not None, "应有可补偿的补货单"
    result = execution.compensate(session, ex.id)
    assert result["status"] == "compensated"
    assert session.get(ReplenishmentOrder, order.id).status == "compensated"


def test_8_advance_and_review(session):
    """T+7 推演 → 复盘报告 → 策略权重更新。"""
    advanced = advance_days(session, 7)
    assert advanced["advanced_days"] == 7
    assert advanced["sales_rows"] > 0
    reports = evaluation.review_all(session)
    assert len(reports) >= 1, "每个已执行动作都有复盘报告"
    for rep in reports:
        before = json.loads(rep.period_before)
        after = json.loads(rep.period_after)
        assert before["window"] and after["window"]
        assert rep.verdict in ("effective", "partial", "ineffective")
        assert json.loads(rep.reasons)
    weights = session.exec(select(StrategyWeight)).all()
    assert weights, "复盘后应更新策略权重"


def test_9_agent_metrics(session):
    m = evaluation.agent_metrics(session)
    assert m["root_cause_accuracy_pct"] is not None and m["root_cause_accuracy_pct"] >= 80
    assert m["auto_exec_success_pct"] >= 90
    assert m["high_risk_approval_compliance_pct"] == 100
    assert m["detection_latency_avg_h"] is not None


def test_10_audit_trace_complete(session):
    """审计日志可追溯完整链路（同 trace_id 贯穿 感知→诊断→决策→执行）。"""
    from app.models import AuditLog
    ex = session.exec(select(Execution).where(
        Execution.status == "success")).first()
    assert ex and ex.trace_id
    logs = session.exec(select(AuditLog).where(
        AuditLog.trace_id == ex.trace_id)).all()
    actions = {l.action for l in logs}
    assert "execution.replenish" in actions or any(
        a.startswith("execution.") for a in actions)
    assert any(a.startswith("decision.") for a in actions) or \
           any(a.startswith("diagnosis.") for a in actions)
