# -*- coding: utf-8 -*-
"""决策 Agent：根因 + 打法库 → 候选方案（约束检查 / ROI 估算 / 风险等级 / 是否审批）。

所有估算参数来自 data/kb/playbooks.yaml 的 impact_model（与 Mock 世界因果模型一致），
数字全部来自工具返回（基线、价格、库存）；Policy Engine 决定风险与审批。
"""
import json
import math
from datetime import timedelta

import yaml
from sqlmodel import Session, select

from ..core import config, timeutil
from ..governance.audit import audit
from ..governance.auth import AGENT_ACTOR
from ..governance.policy import evaluate
from ..models import DecisionCard, Diagnosis, Inventory, Anomaly, Product, Store
from . import tools


def _load_playbooks() -> dict:
    return yaml.safe_load((config.KB_DIR / "playbooks.yaml").read_text(encoding="utf-8"))


def _type_map(anomaly_type: str) -> str:
    return {"complaint_surge": "sales_drop"}.get(anomaly_type, anomaly_type)


def _est_mu(session: Session, anomaly: Anomaly) -> float:
    """基线日销：优先感知层期望值（滚动中位数），回退 BaselineMu。"""
    mu = tools.get_baseline_mu(session, anomaly.store_id, anomaly.product_id)
    return max(anomaly.expected, mu or 0.0, 1.0)


def _find_donor(session: Session, anomaly: Anomaly, qty: int) -> dict | None:
    """同区域有富余库存的调出门店。"""
    store = session.get(Store, anomaly.store_id)
    invs = session.exec(select(Inventory).where(
        Inventory.product_id == anomaly.product_id)).all()
    best = None
    for inv in invs:
        if inv.store_id == anomaly.store_id:
            continue
        st = session.get(Store, inv.store_id)
        if not st or st.region_id != (store.region_id if store else ""):
            continue
        surplus = inv.on_hand - inv.safety_stock
        if surplus >= qty and (best is None or surplus < best["surplus"]):
            best = {"store_id": inv.store_id, "on_hand": inv.on_hand,
                    "safety_stock": inv.safety_stock, "surplus": surplus}
    return best


def _check_constraints(checks: list, rule: str, ok: bool, detail: dict):
    checks.append({"rule": rule, "passed": ok, "detail": detail})


def build_action(session: Session, anomaly: Anomaly, rc: dict, play: dict,
                 impact: dict, constraints: dict) -> dict | None:
    """单个候选动作构建：参数 + 约束检查 + 影响估算 + 治理评估。"""
    product = session.get(Product, anomaly.product_id) if anomaly.product_id else None
    store = session.get(Store, anomaly.store_id)
    mu = _est_mu(session, anomaly)
    checks: list = []
    today = timeutil.business_today(session)
    act_type = play["action_type"]
    params: dict = {"action_type": act_type}

    if act_type == "replenish":
        if not product:
            return None
        cover = 14 if "surge" not in anomaly.type else 10
        qty = int(math.ceil(mu * cover / product.moq) * product.moq)
        qty = max(qty, product.moq)
        _check_constraints(checks, "cover_days<=21", cover <= constraints["max_cover_days"],
                           {"cover_days": cover})
        _check_constraints(checks, "moq_multiple", qty % product.moq == 0,
                           {"qty": qty, "moq": product.moq})
        amount = round(qty * product.cost_price, 2)
        params |= {"amount": amount}
        action = {"store_id": anomaly.store_id, "product_id": anomaly.product_id,
                  "qty": qty, "amount": amount}
        # 估算：恢复销量 × 毛利 × 14 天 / (物流+资金成本≈5%订单额)
        daily_gap = max(0.0, mu - anomaly.observed) if anomaly.type != "sales_surge" \
            else mu * 0.2
        recovered = daily_gap * impact["replenish_recovery"] * 14
        benefit = round(recovered * (product.list_price - product.cost_price), 2)
        cost = round(amount * 0.05, 2)
        expected_impact = {"est_cost": cost, "est_benefit": benefit,
                           "est_recovery_pct": int(impact["replenish_recovery"] * 100),
                           "roi": round(benefit / cost, 2) if cost else None,
                           "basis": {"daily_gap": round(daily_gap, 2), "horizon_days": 14,
                                     "cost_rule": "物流+资金成本≈订单额5%"}}
    elif act_type == "transfer":
        qty = int(math.ceil(mu * 7))
        donor = _find_donor(session, anomaly, qty)
        if not donor:
            return None
        _check_constraints(checks, "donor_surplus", donor["surplus"] >= qty,
                           {"donor": donor["store_id"], "surplus": donor["surplus"], "qty": qty})
        amount = round(qty * (product.cost_price if product else 0), 2)
        params |= {"amount": amount, "cross_region": False}
        action = {"from_store_id": donor["store_id"], "to_store_id": anomaly.store_id,
                  "product_id": anomaly.product_id, "qty": qty, "amount": amount}
        daily_gap = max(0.0, mu - anomaly.observed)
        benefit = round(daily_gap * 0.9 * 7 * ((product.list_price - product.cost_price)
                                               if product else 0), 2)
        cost = round(amount * 0.03, 2)
        expected_impact = {"est_cost": cost, "est_benefit": benefit,
                           "est_recovery_pct": 90, "roi": round(benefit / cost, 2) if cost else None,
                           "basis": {"donor_store": donor["store_id"], "horizon_days": 7}}
    elif act_type == "promo":
        if not product:
            return None
        disc = float(play.get("discount_pct", 10))
        margin_pct = (product.list_price - product.cost_price) / product.list_price * 100
        max_disc = margin_pct - constraints["margin_floor_pct"]
        if disc > max_disc:
            _check_constraints(checks, "margin_floor", False,
                               {"discount_pct": disc, "margin_pct": round(margin_pct, 1),
                                "max_allowed": round(max_disc, 1)})
            disc = round(max_disc, 1)
        else:
            _check_constraints(checks, "margin_floor", True,
                               {"discount_pct": disc, "margin_pct": round(margin_pct, 1)})
        _check_constraints(checks, "discount<=30", disc <= constraints["max_discount_pct"],
                           {"discount_pct": disc})
        days = int(play.get("duration_days", 7))
        lift = 1 + disc / 100 * impact["promo_lift_coef"]
        est_qty = round(mu * days)
        budget = round(est_qty * product.list_price * disc / 100, 2)
        _check_constraints(checks, "budget<=cap", budget <= constraints["budget_cap"],
                           {"budget": budget, "cap": constraints["budget_cap"]})
        params |= {"discount_pct": disc, "budget": budget}
        action = {"name": f"{anomaly.store_id}-{anomaly.category_id}品类促销(根因:{rc['code']})",
                  "type": "near_expiry" if rc["code"] in ("near_expiry", "complaint") else "category",
                  "store_ids": [anomaly.store_id], "category_id": anomaly.category_id,
                  "discount_pct": disc, "budget": budget,
                  "start_date": (today + timedelta(days=1)).isoformat(),
                  "end_date": (today + timedelta(days=days)).isoformat()}
        incr_qty = est_qty * (lift - 1)
        benefit = round(incr_qty * (product.list_price * (1 - disc / 100) - product.cost_price), 2)
        expected_impact = {"est_cost": budget, "est_benefit": benefit,
                           "est_recovery_pct": None, "roi": round(benefit / budget, 2) if budget else None,
                           "basis": {"lift": round(lift, 2), "est_qty": est_qty, "days": days,
                                     "model": "promo_lift_coef=6"}}
    elif act_type == "member_reach":
        rule = play.get("budget_rule", "fixed_5000")
        if rule == "fixed_8000":
            budget = 8000.0
        elif rule == "fixed_5000":
            budget = 5000.0
        else:
            baseline_amount = mu * 30 * (product.list_price if product else 10)
            budget = round(baseline_amount * 0.02, 2)
        _check_constraints(checks, "budget<=cap", budget <= constraints["budget_cap"],
                           {"budget": budget})
        params |= {"budget": budget}
        action = {"name": f"{anomaly.store_id}会员定向触达(根因:{rc['code']})",
                  "store_ids": [anomaly.store_id], "budget": budget,
                  "type": "churn" if rc["code"] in ("member_churn", "complaint") else "coupon"}
        retained = mu * 30 * impact["member_reach_retention"]
        benefit = round(retained * ((product.list_price - product.cost_price)
                                    if product else 0), 2)
        expected_impact = {"est_cost": budget, "est_benefit": benefit,
                           "est_recovery_pct": 25, "roi": round(benefit / budget, 2) if budget else None,
                           "basis": {"retention": impact["member_reach_retention"]}}
    elif act_type == "cs_followup":
        task_type = play.get("task_type", "callback")
        params |= {"task_type": task_type}
        action = {"store_id": anomaly.store_id, "type": task_type,
                  "anomaly_id": anomaly.id}
        benefit = round(max(0.0, mu - anomaly.observed) * impact["cs_followup_recovery"]
                        * 14 * ((product.list_price - product.cost_price) if product else 0), 2)
        expected_impact = {"est_cost": 200.0, "est_benefit": benefit,
                           "est_recovery_pct": 30, "roi": round(benefit / 200, 2) if benefit else None,
                           "basis": {"recovery": impact["cs_followup_recovery"]}}
    else:
        return None

    if not all(c["passed"] for c in checks):
        return None  # 违反硬约束的动作不生成（约束违反率=0）

    pol = evaluate(AGENT_ACTOR, act_type, params)
    if not pol.allowed:
        return None
    action["_policy_params"] = params
    return {
        "action_type": act_type, "action": action, "rationale": play.get("rationale", ""),
        "risk_level": pol.risk_level, "requires_approval": 1 if pol.requires_approval else 0,
        "risk_reasons": pol.reasons, "expected_impact": expected_impact,
        "constraints_checked": checks, "priority": play.get("priority", 9),
        "policy": pol.to_dict(),
    }


def decide(session: Session, anomaly: Anomaly, trace_id: str = "") -> list[DecisionCard]:
    """对一个已诊断异常生成决策卡。"""
    trace_id = trace_id or timeutil.new_id("trc")
    diag = session.exec(select(Diagnosis).where(
        Diagnosis.anomaly_id == anomaly.id).order_by(Diagnosis.created_at.desc())).first()
    if diag is None:
        return []
    pb = _load_playbooks()
    impact, constraints = pb["impact_model"], pb["constraints"]
    want_type = _type_map(anomaly.type)
    rcs = json.loads(diag.root_causes)
    cards = []
    for rc in rcs:
        if rc["code"] == "unknown":
            continue
        for play in pb["playbooks"]:
            trig = play["trigger"]
            if trig["anomaly_type"] == want_type and trig.get("root_cause") == rc["code"]:
                for act in play.get("actions", []):
                    built = build_action(session, anomaly, rc, act, impact, constraints)
                    if built is None:
                        continue
                    dup = session.exec(select(DecisionCard).where(
                        DecisionCard.anomaly_id == anomaly.id,
                        DecisionCard.action_type == built["action_type"],
                        DecisionCard.status.not_in(  # type: ignore
                            ["rejected", "expired", "failed", "compensated"]))).first()
                    if dup:
                        continue
                    card = DecisionCard(
                        id=timeutil.new_id("dcs"), anomaly_id=anomaly.id,
                        action_type=built["action_type"],
                        action=json.dumps(built["action"], ensure_ascii=False),
                        rationale=f"[根因:{rc['name']}] {built['rationale']}",
                        risk_level=built["risk_level"],
                        risk_reasons=json.dumps(built["risk_reasons"], ensure_ascii=False),
                        requires_approval=built["requires_approval"],
                        expected_impact=json.dumps(built["expected_impact"], ensure_ascii=False),
                        constraints_checked=json.dumps(built["constraints_checked"], ensure_ascii=False),
                        status="suggested", created_at=timeutil.now_iso(), trace_id=trace_id)
                    session.add(card)
                    cards.append(card)
    session.commit()
    if cards:
        anomaly.status = "decided"
        session.add(anomaly)
        session.commit()
    audit(session, AGENT_ACTOR, "decision.decide", "decision_card",
          anomaly.id, detail={"cards": [
              {"id": c.id, "action_type": c.action_type, "risk": c.risk_level,
               "requires_approval": bool(c.requires_approval)} for c in cards]},
          trace_id=trace_id)
    return cards


def decide_all(session: Session, trace_id: str = "") -> list[DecisionCard]:
    diagnosed = session.exec(select(Anomaly).where(Anomaly.status == "diagnosed")).all()
    out = []
    for a in diagnosed:
        out.extend(decide(session, a, trace_id))
    return out
