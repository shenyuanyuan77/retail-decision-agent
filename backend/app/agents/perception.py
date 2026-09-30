# -*- coding: utf-8 -*-
"""感知 Agent：传统算法发现销量异常（滚动中位数 + MAD + z-score + 比例规则 + 业务规则）。

检测器：
1. store_sku 骤降/骤升：近14天逐日 vs 基线(前28天滚动中位数)，连续≥2天偏离成"异常段"
2. 缺货规则：库存=0 且 近14天有销售记录（并入 sales_drop 证据或独立 stockout 异常）
3. 门店客诉率激增：近7天 vs 前30天基线 2 倍
不依赖大模型猜测；所有异常带数据证据；重复扫描幂等（同实体同窗口去重）。
"""
import json
from datetime import timedelta

from sqlmodel import Session, select

from ..core import timeutil
from ..governance.audit import audit
from ..governance.auth import AGENT_ACTOR
from ..models import Anomaly, Inventory, Storyline, Ticket
from . import stats, tools

BASELINE_DAYS = 28
RECENT_DAYS = 14
MIN_BASELINE_MEDIAN = 3.0     # 基线中位数低于该值的不判定（慢销品噪声大）
DROP_RATIO = 0.55             # 观察均值 < 基线×0.55 → 骤降（Poisson 噪声下 3σ+ 安全）
SURGE_RATIO = 1.8             # 观察均值 > 基线×1.8 → 骤升
DAY_DROP_RATIO = 0.5
DAY_SURGE_RATIO = 1.9


def _find_runs(points: list[dict], recent_start: str, med_v: float, mad_v: float) -> list[dict]:
    """在近14天中寻找连续≥2天的异常段（z-score 或比例规则命中；允许 1 天噪声间断）。"""
    runs: list[dict] = []
    cur: list[dict] = []
    gap = 0
    for p in points:
        d, q = p["date"], p["qty"]
        if d < recent_start:
            continue
        z = stats.zscore(q, med_v, mad_v)
        is_drop = q <= med_v * DAY_DROP_RATIO or (z <= -3.5 and q < med_v)
        is_surge = q >= med_v * DAY_SURGE_RATIO and med_v >= MIN_BASELINE_MEDIAN
        kind = "drop" if is_drop else ("surge" if is_surge else None)
        if kind:
            if cur and cur[0]["kind"] != kind:
                if len(cur) >= 2:
                    runs.append(cur)
                cur, gap = [], 0
            cur.append({"date": d, "qty": q, "kind": kind, "z": round(z, 2)})
            gap = 0
        else:
            gap += 1
            if gap > 1:  # 连续 2 天正常 → 段结束（1 天噪声可桥接）
                if len(cur) >= 2:
                    runs.append(cur)
                cur, gap = [], 0
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def scan_store_sku(session: Session) -> list[Anomaly]:
    today = timeutil.business_today(session)
    matrix = tools.get_store_sku_sales_matrix(session, days=BASELINE_DAYS + RECENT_DAYS)
    recent_start = (today - timedelta(days=RECENT_DAYS - 1)).isoformat()
    found: list[Anomaly] = []

    # 一次性取库存快照（缺货证据）
    inv_map: dict[tuple[str, str], dict] = {}
    for inv in tools.get_inventory(session):
        inv_map[(inv["store_id"], inv["product_id"])] = inv

    for entry in matrix:
        points = entry["points"]
        if len(points) < RECENT_DAYS // 2:
            continue
        base_pts = [p for p in points if p["date"] < recent_start]
        recent_pts = [p for p in points if p["date"] >= recent_start]
        base_dates = {p["date"] for p in base_pts}  # noqa: F841（保留调试用）
        # 缺失日补 0（稀疏存储）
        d = today - timedelta(days=BASELINE_DAYS + RECENT_DAYS - 1)
        zero_filled = []
        pts_by_date = {p["date"]: p for p in points}
        while d <= today:
            p = pts_by_date.get(d.isoformat())
            zero_filled.append({"date": d.isoformat(), "qty": p["qty"] if p else 0,
                                "unit_price": p["unit_price"] if p else 0.0,
                                "promo_flag": p["promo_flag"] if p else 0,
                                "member_qty": p["member_qty"] if p else 0})
            d += timedelta(days=1)
        base_vals = [p["qty"] for p in zero_filled if p["date"] < recent_start]
        med_v = stats.med(base_vals)
        if med_v < MIN_BASELINE_MEDIAN:
            continue
        mad_v = stats.mad(base_vals, med_v)
        base_qty = {p["date"]: p["qty"] for p in base_pts}
        runs = _find_runs(zero_filled, recent_start, med_v, mad_v)
        if not runs:
            continue
        runs = [r for r in runs if len(r) <= RECENT_DAYS]
        if not runs:
            continue
        run = max(runs, key=lambda r: sum(abs(x["z"]) for x in r))
        kind = run[0]["kind"]
        observed = sum(x["qty"] for x in run) / len(run)
        expected = med_v
        dev = (observed - expected) / expected * 100
        if kind == "drop" and observed > expected * DROP_RATIO:
            continue
        if kind == "surge" and observed < expected * SURGE_RATIO:
            continue
        absdev = abs(dev)
        severity = ("critical" if absdev >= 80 else
                    "high" if absdev >= 60 else
                    "medium" if absdev >= 40 else "low")
        key = (entry["store_id"], entry["product_id"])
        inv = inv_map.get(key, {})
        evidence = [
            {"type": "baseline", "tool": "get_sales_timeseries",
             "data": {"baseline_days": len(base_vals), "baseline_median": round(med_v, 2),
                      "baseline_mad": round(mad_v, 2)}},
            {"type": "observation", "tool": "get_sales_timeseries",
             "data": {"window": [run[0]["date"], run[-1]["date"]],
                      "observed_daily_avg": round(observed, 2),
                      "points": [{"date": x["date"], "qty": x["qty"], "z": x["z"]} for x in run]}},
        ]
        if inv and inv["on_hand"] == 0:
            evidence.append({"type": "inventory_zero", "tool": "get_inventory",
                             "data": {"on_hand": 0, "in_transit": inv["in_transit"],
                                      "safety_stock": inv["safety_stock"]}})
        anomaly = Anomaly(
            id=timeutil.new_id("ano"),
            type="sales_drop" if kind == "drop" else "sales_surge",
            entity_type="store_sku",
            store_id=entry["store_id"], product_id=entry["product_id"],
            category_id=entry["category_id"],
            metric="sales_qty",
            observed=round(observed, 2), expected=round(expected, 2),
            deviation_pct=round(dev, 1), severity=severity,
            status="open", window_start=run[0]["date"], window_end=run[-1]["date"],
            detected_at=timeutil.now_iso(),
            method="rolling_median_mad_zscore_run",
            evidence=json.dumps(evidence, ensure_ascii=False),
        )
        # 发现时效：异常起点距今天数（业务小时≈天×24，扫描每小时可跑）
        started = timeutil.parse_date(anomaly.window_start)
        anomaly.detection_latency_h = round((today - started).days * 24, 1)
        # 关联故事线（真值仅用于评估，不参与检测逻辑）
        sl = session.exec(select(Storyline).where(
            Storyline.store_id == anomaly.store_id,
            Storyline.product_id == anomaly.product_id)).first()
        if sl and sl.start_date <= anomaly.window_end and sl.end_date >= anomaly.window_start:
            anomaly.storyline_id = sl.id
        found.append(anomaly)
    return found


def scan_complaint_surge(session: Session) -> list[Anomaly]:
    """门店客诉率激增（近7天 vs 前30天基线，≥2倍且绝对量≥8）。"""
    today = timeutil.business_today(session)
    found = []
    from ..models import Store
    stores = session.exec(select(Store)).all()
    w1s, w1e = (today - timedelta(days=6)).isoformat(), today.isoformat()
    w2s = (today - timedelta(days=36)).isoformat()
    w2e = (today - timedelta(days=7)).isoformat()
    for st in stores:
        cur = tools.get_ticket_stats(session, st.id, w1s, w1e)
        prev = tools.get_ticket_stats(session, st.id, w2s, w2e)
        cur_n, prev_n = cur["total"], prev["total"]
        prev_daily = prev_n / 30 if prev_n else 0.4 * 30 / 30
        prev_daily = prev_n / 30 if prev_n else 0.4
        cur_daily = cur_n / 7
        if prev_daily <= 0:
            prev_daily = 0.4
        if cur_daily >= max(prev_daily * 2, 0.9) and cur_n >= 6:
            observed, expected = round(cur_daily, 2), round(prev_daily, 2)
            dev = (observed - expected) / expected * 100
            evidence = [
                {"type": "ticket_recent", "tool": "get_tickets",
                 "data": {"window": [w1s, w1e], "tickets_per_day": observed,
                          "total": cur_n, "by_type": cur["by_type"]}},
                {"type": "ticket_baseline", "tool": "get_tickets",
                 "data": {"window": [w2s, w2e], "tickets_per_day": expected, "total": prev_n}},
            ]
            found.append(Anomaly(
                id=timeutil.new_id("ano"), type="complaint_surge", entity_type="store",
                store_id=st.id, metric="complaints_per_day",
                observed=observed, expected=expected, deviation_pct=round(dev, 1),
                severity="high" if cur_n >= 12 else "medium", status="open",
                window_start=w1s, window_end=w1e, detected_at=timeutil.now_iso(),
                method="ratio_rule_2x", evidence=json.dumps(evidence, ensure_ascii=False),
                detection_latency_h=round((today - timeutil.parse_date(w1s)).days * 24, 1),
            ))
    return found


def _dedup(session: Session, candidates: list[Anomaly]) -> list[Anomaly]:
    """幂等去重：同实体+同类型已有 open/closed 异常且窗口重叠 → 跳过。"""
    out = []
    existing = session.exec(select(Anomaly)).all()
    for c in candidates:
        dup = any(
            e.type == c.type and e.store_id == c.store_id and e.product_id == c.product_id
            and e.status in ("open", "diagnosed", "decided", "acting")
            and not (e.window_end < c.window_start or c.window_end < e.window_start)
            for e in existing
        )
        if not dup:
            out.append(c)
    return out


def scan(session: Session, trace_id: str = "") -> dict:
    """感知 Agent 主入口：全量扫描 → 去重 → 落库 → 审计。"""
    trace_id = trace_id or timeutil.new_id("trc")
    cands = scan_store_sku(session) + scan_complaint_surge(session)
    fresh = _dedup(session, cands)
    for a in fresh:
        session.add(a)
    session.commit()
    audit(session, AGENT_ACTOR, "perception.scan", "anomaly", "-",
          detail={"found": len(cands), "new": len(fresh),
                  "anomalies": [a.id for a in fresh]},
          trace_id=trace_id)
    return {"trace_id": trace_id, "scanned": True, "found": len(cands),
            "new_anomalies": len(fresh),
            "anomalies": [{"id": a.id, "type": a.type, "store_id": a.store_id,
                           "product_id": a.product_id, "severity": a.severity,
                           "deviation_pct": a.deviation_pct,
                           "window": [a.window_start, a.window_end],
                           "storyline_id": a.storyline_id} for a in fresh]}
