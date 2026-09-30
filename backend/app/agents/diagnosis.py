# -*- coding: utf-8 -*-
"""诊断 Agent：动态任务拆解 → 假设验证 → 根因排序（Top3 + 置信度 + 证据链 + 反证）。

假设库来自 data/kb/root_causes.yaml；每个假设只消费工具返回的数据（get_inventory /
get_tickets / get_campaigns / get_weather_calendar / get_competitor_promo /
get_sales_timeseries / 会员复购）；输出根因至少 2 条证据，无充分证据时转人工。
"""
import json
from datetime import timedelta

import yaml
from sqlmodel import Session, select

from ..core import config, timeutil
from ..governance.audit import audit
from ..governance.auth import AGENT_ACTOR
from ..models import Anomaly, Diagnosis, ReplenishmentOrder, Store
from ..world import model as world_model
from . import tools


def _load_root_causes() -> dict:
    path = config.KB_DIR / "root_causes.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {rc["code"]: rc for rc in data["root_causes"]}


def _hyp(code: str, name: str, direction: str, supports: list, counters: list,
         base_conf: float) -> dict:
    """direction: drop/surge/none — 与异常类型相容性；supports/counters 为证据条目。"""
    conf = min(1.0, base_conf + 0.15 * max(0, len(supports) - 1)) if supports else 0.0
    return {"code": code, "name": name, "direction": direction,
            "matched": bool(supports), "confidence": round(conf, 2),
            "evidence": supports, "counter_evidence": counters}


def _series_map(session: Session, anomaly: Anomaly) -> tuple[dict, dict, dict]:
    """窗口内/基线期 序列与统计（工具返回）。"""
    pts = tools.get_sales_timeseries(session, anomaly.store_id, anomaly.product_id, days=56)
    win_s, win_e = anomaly.window_start, anomaly.window_end
    win = [p for p in pts if win_s <= p["date"] <= win_e]
    base = [p for p in pts if p["date"] < win_s][-28:]
    return pts, win, base


def test_hypotheses(session: Session, anomaly: Anomaly, log: list) -> list[dict]:
    store = session.get(Store, anomaly.store_id)
    city = store.city if store else ""
    _, win, base = _series_map(session, anomaly)
    win_s, win_e = anomaly.window_start, anomaly.window_end
    hyps: list[dict] = []

    def record(tool: str, params: dict, result_summary: dict):
        log.append({"tool": tool, "params": params, "result": result_summary})

    # H1 缺货
    inv = tools.get_inventory_one(session, anomaly.store_id, anomaly.product_id)
    record("get_inventory", {"store_id": anomaly.store_id, "product_id": anomaly.product_id},
           {"on_hand": inv["on_hand"] if inv else None,
            "in_transit": inv["in_transit"] if inv else None})
    overdue = session.exec(select(ReplenishmentOrder).where(
        ReplenishmentOrder.store_id == anomaly.store_id,
        ReplenishmentOrder.product_id == anomaly.product_id,
        ReplenishmentOrder.status == "confirmed")).all()
    overdue = [o for o in overdue if o.arrive_date < timeutil.business_today(session).isoformat()]
    record("query_replenishments", {"store_id": anomaly.store_id},
           {"overdue_orders": len(overdue)})
    stockout_tickets = [t for t in tools.get_tickets(
        session, store_id=anomaly.store_id, product_id=anomaly.product_id,
        types=["stockout"], days=30) if win_s <= t["biz_date"] <= win_e]
    record("get_tickets", {"store_id": anomaly.store_id, "type": "stockout"},
           {"window_tickets": len(stockout_tickets)})
    sup = []
    if inv and inv["on_hand"] == 0:
        sup.append({"type": "inventory_zero", "data": inv,
                    "note": "门店该商品库存为 0"})
    if overdue:
        sup.append({"type": "overdue_replenishment",
                    "data": [{"order_no": o.order_no, "arrive_date": o.arrive_date,
                              "qty": o.qty} for o in overdue],
                    "note": "存在逾期未到补货单"})
    if len(stockout_tickets) >= 2:
        sup.append({"type": "stockout_ticket",
                    "data": {"count": len(stockout_tickets)},
                    "note": "窗口内缺货客诉工单≥2"})
    hyps.append(_hyp("stockout", "缺货", "drop", sup, [], 0.55))

    # H2 供应链延迟（独立于缺货的可执行根因）
    sup2 = []
    if overdue:
        sup2.append({"type": "overdue_replenishment",
                     "data": [{"order_no": o.order_no, "arrive_date": o.arrive_date} for o in overdue],
                     "note": "补货单逾期未到"})
        sup2.append({"type": "inventory_zero", "data": inv or {},
                     "note": "库存无法满足需求"})
    hyps.append(_hyp("supply_delay", "供应链延迟", "drop", sup2, [], 0.5))

    # H3 自有促销
    camps = tools.get_campaigns(session, active_between=(win_s, win_e))
    matched_camps = [c for c in camps
                     if (not c["store_ids"] or anomaly.store_id in c["store_ids"].split(","))
                     and (not c["category_id"] or c["category_id"] == anomaly.category_id
                          or anomaly.product_id in (c.get("product_ids") or "").split(","))]
    record("get_campaigns", {"active_between": [win_s, win_e]},
           {"matched": len(matched_camps)})
    promo_days = sum(1 for p in win if p["promo_flag"] == 1)
    member_share_win = (sum(p["member_qty"] for p in win) / max(1, sum(p["qty"] for p in win)))
    member_share_base = (sum(p["member_qty"] for p in base) / max(1, sum(p["qty"] for p in base)))
    sup3 = []
    if matched_camps:
        sup3.append({"type": "active_campaign",
                     "data": [{"id": c["id"], "name": c["name"], "discount_pct": c["discount_pct"]}
                              for c in matched_camps], "note": "窗口内有覆盖本店本品的促销"})
    if win and promo_days / len(win) >= 0.5:
        sup3.append({"type": "promo_flag", "data": {"promo_days_ratio": round(promo_days / len(win), 2)},
                     "note": "促销标记覆盖大部分异常窗口"})
    if member_share_win > member_share_base + 0.1:
        sup3.append({"type": "member_share_up",
                     "data": {"window": round(member_share_win, 2), "baseline": round(member_share_base, 2)},
                     "note": "会员购买占比显著上升"})
    hyps.append(_hyp("promo", "自有促销拉动", "surge", sup3, [], 0.6))

    # H4 竞品促销
    comp = tools.get_competitor_promo(session, anomaly.category_id, city, win_s, win_e)
    record("get_competitor_promo", {"category_id": anomaly.category_id, "city": city},
           {"count": len(comp)})
    sup4 = []
    if len(comp) >= 2:
        sup4.append({"type": "competitor_promo_active",
                     "data": [{"competitor": c["competitor_name"], "discount_pct": c["discount_pct"]}
                              for c in comp[:5]], "note": "竞品同品类窗口内促销"})
        cat_win = tools.get_store_category_daily(session, anomaly.store_id,
                                                 anomaly.category_id, win_s, win_e)
        cat_base = tools.get_store_category_daily(
            session, anomaly.store_id, anomaly.category_id,
            (timeutil.parse_date(win_s) - timedelta(days=28)).isoformat(),
            (timeutil.parse_date(win_s) - timedelta(days=1)).isoformat())
        win_avg = (sum(x["qty"] for x in cat_win) / max(1, len(cat_win))) if cat_win else 0
        base_avg = (sum(x["qty"] for x in cat_base) / max(1, len(cat_base))) if cat_base else 0
        if base_avg and win_avg < base_avg * 0.9:
            sup4.append({"type": "category_sales_down",
                         "data": {"window_daily": round(win_avg, 1),
                                  "baseline_daily": round(base_avg, 1),
                                  "drop_pct": round((1 - win_avg / base_avg) * 100, 1)},
                         "note": "本店同品类销量同步下滑>10%"})
    hyps.append(_hyp("competitor_promo", "竞品促销分流", "drop", sup4, [], 0.45))

    # H5 天气
    wc = tools.get_weather_calendar(session, city, win_s, win_e)
    record("get_weather_calendar", {"city": city},
           {"conditions": sorted({w["condition"] for w in wc["weather"]})})
    sens = world_model.WEATHER_CATEGORY_EFFECT
    weather_hits = [w for w in wc["weather"]
                    if anomaly.category_id in sens.get(w["condition"], {})]
    sup5 = []
    if weather_hits:
        effect = sens[weather_hits[0]["condition"]][anomaly.category_id]
        direction = "surge" if effect > 1 else "drop"
        sup5.append({"type": "weather_anomaly",
                     "data": [{"date": w["biz_date"], "condition": w["condition"],
                               "category_effect": effect} for w in weather_hits[:5]],
                     "note": f"天气 {weather_hits[0]['condition']} 对该品类系数 {effect}"})
        hyps.append(_hyp("weather", "天气影响", direction, sup5, [], 0.4))
    else:
        hyps.append(_hyp("weather", "天气影响", "none", [], [], 0.4))

    # H6 客诉/口碑
    complaint_tickets = [t for t in tools.get_tickets(
        session, store_id=anomaly.store_id, product_id=anomaly.product_id,
        types=["expiry", "quality"], days=30) if win_s <= t["biz_date"] <= win_e]
    record("get_tickets", {"store_id": anomaly.store_id, "types": ["expiry", "quality"]},
           {"window_tickets": len(complaint_tickets)})
    sup6 = []
    if len(complaint_tickets) >= 3:
        sup6.append({"type": "ticket_surge",
                     "data": {"count": len(complaint_tickets),
                              "types": sorted({t["type"] for t in complaint_tickets})},
                     "note": "窗口内临期/质量客诉≥3"})
    if inv and inv.get("expiry_date"):
        days_to_expiry = (timeutil.parse_date(inv["expiry_date"])
                          - timeutil.business_today(session)).days
        if 0 <= days_to_expiry <= 14:
            sup6.append({"type": "expiry_date_close",
                         "data": {"expiry_date": inv["expiry_date"], "days_left": days_to_expiry},
                         "note": "库存批次临期(≤14天)"})
    rep = tools.get_member_repurchase_prev(session, anomaly.store_id)
    if rep and rep["prev_rate"] and rep["current_rate"] \
            and rep["current_rate"] < rep["prev_rate"] * 0.85:
        sup6.append({"type": "repurchase_down", "data": rep,
                     "note": "门店会员复购率环比下滑>15%"})
    hyps.append(_hyp("complaint", "客诉/口碑恶化", "drop", sup6, [], 0.5))

    # H7 临期未处置
    sup7 = []
    if inv and inv.get("expiry_date"):
        days_to_expiry = (timeutil.parse_date(inv["expiry_date"])
                          - timeutil.business_today(session)).days
        if 0 <= days_to_expiry <= 14:
            sup7.append({"type": "expiry_date_close",
                         "data": {"expiry_date": inv["expiry_date"], "days_left": days_to_expiry}})
            if not matched_camps:
                sup7.append({"type": "no_discount_campaign", "data": {"active_campaigns": 0},
                             "note": "临期但无折价活动"})
    hyps.append(_hyp("near_expiry", "临期未处置", "drop", sup7, [], 0.45))

    # H8 会员流失
    sup8 = []
    if rep and rep["prev_rate"] and rep["current_rate"] \
            and rep["current_rate"] < rep["prev_rate"] * 0.8:
        sup8.append({"type": "repurchase_down", "data": rep})
        if member_share_win < member_share_base - 0.05:
            sup8.append({"type": "member_qty_share_down",
                         "data": {"window": round(member_share_win, 2),
                                  "baseline": round(member_share_base, 2)}})
    hyps.append(_hyp("member_churn", "会员流失", "drop", sup8, [], 0.4))

    # H9 价格变化
    price_win = (sum(p["qty"] * p["unit_price"] for p in win) / max(1, sum(p["qty"] for p in win)))
    price_base = (sum(p["qty"] * p["unit_price"] for p in base) / max(1, sum(p["qty"] for p in base)))
    sup9 = []
    if price_base and price_win > price_base * 1.05:
        sup9.append({"type": "unit_price_up",
                     "data": {"window": round(price_win, 2), "baseline": round(price_base, 2)}})
        sup9.append({"type": "qty_down", "data": {"observed": anomaly.observed,
                                                  "expected": anomaly.expected}})
    hyps.append(_hyp("price_change", "价格变化", "drop", sup9, [], 0.45))
    return hyps


def _dimension_drill(session: Session, anomaly: Anomaly) -> list[dict]:
    """维度下钻：本品对门店/品类的贡献、同店同品类其他商品、渠道与会员结构。"""
    drills = []
    try:
        _, win, base = _series_map(session, anomaly)
        drills.append({
            "dimension": "sku_contribution",
            "data": {"window_qty": sum(p["qty"] for p in win),
                     "baseline_qty": sum(p["qty"] for p in base),
                     "member_share_window": round(sum(p["member_qty"] for p in win)
                                                  / max(1, sum(p["qty"] for p in win)), 2),
                     "online_share_window": None}})
    except Exception:
        pass
    return drills


def diagnose(session: Session, anomaly: Anomaly, trace_id: str = "") -> Diagnosis:
    trace_id = trace_id or timeutil.new_id("trc")
    log: list = []
    hyps = test_hypotheses(session, anomaly, log)

    want = "drop" if anomaly.type in ("sales_drop", "complaint_surge") else "surge"
    rc_lib = _load_root_causes()

    compatible = [h for h in hyps
                  if h["matched"] and h["direction"] in (want, "none") and len(h["evidence"]) >= 2]
    compatible.sort(key=lambda h: -h["confidence"])
    total_conf = sum(h["confidence"] for h in compatible) or 1.0
    root_causes = []
    for h in compatible[:3]:
        contribution = round(h["confidence"] / total_conf * 100, 1)
        rc = {
            "code": h["code"], "name": h["name"], "confidence": h["confidence"],
            "contribution_pct": contribution,
            "evidence": h["evidence"], "counter_evidence": h["counter_evidence"],
            "kb_description": rc_lib.get(h["code"], {}).get("description", ""),
        }
        root_causes.append(rc)

    uncertain = not root_causes
    if uncertain:
        root_causes = [{"code": "unknown", "name": "证据不足，转人工分析",
                        "confidence": 0.0, "contribution_pct": 0,
                        "evidence": [], "counter_evidence": [],
                        "kb_description": "无满足≥2条证据的根因假设，需人工介入"}]

    summary = (f"{anomaly.store_id}/{anomaly.product_id} {anomaly.type}"
               f" 观察值{anomaly.observed} vs 期望{anomaly.expected}"
               f"（偏差{anomaly.deviation_pct}%），Top根因: "
               + (", ".join(f"{r['name']}({r['confidence']})" for r in root_causes)))
    facts = {"anomaly": {"type": anomaly.type, "observed": anomaly.observed,
                         "expected": anomaly.expected, "deviation_pct": anomaly.deviation_pct},
             "root_causes": [{"name": r["name"], "confidence": r["confidence"],
                              "evidence_count": len(r["evidence"])} for r in root_causes]}
    from .llm import narrate
    narrative = narrate("用一句话解释该销量异常的主要原因", facts, template=(
        f"{anomaly.type} 偏差 {anomaly.deviation_pct}%："
        + "；".join(f"{r['name']}（置信度{r['confidence']}，{len(r['evidence'])}条证据）"
                    for r in root_causes)))

    diag = Diagnosis(
        id=timeutil.new_id("dgn"), anomaly_id=anomaly.id,
        root_causes=json.dumps(root_causes, ensure_ascii=False),
        dimension_drill=json.dumps(_dimension_drill(session, anomaly), ensure_ascii=False),
        hypothesis_log=json.dumps(log, ensure_ascii=False, default=str),
        summary=summary, narrative=narrative, method="hypothesis_test",
        trace_id=trace_id, created_at=timeutil.now_iso(),
    )
    session.add(diag)
    anomaly.status = "diagnosed"
    anomaly.narrative = narrative
    session.add(anomaly)
    session.commit()
    audit(session, AGENT_ACTOR, "diagnosis.diagnose", "diagnosis", diag.id,
          detail={"anomaly_id": anomaly.id, "root_causes": [r["code"] for r in root_causes],
                  "uncertain": uncertain},
          trace_id=trace_id)
    return diag


def diagnose_all(session: Session, trace_id: str = "") -> list[Diagnosis]:
    open_anomalies = session.exec(select(Anomaly).where(Anomaly.status == "open")).all()
    return [diagnose(session, a, trace_id) for a in open_anomalies]
