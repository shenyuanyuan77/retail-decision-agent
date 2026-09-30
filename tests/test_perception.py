# -*- coding: utf-8 -*-
"""目标4测试：感知层异常检测（召回率>90%、统一JSON、证据、幂等去重）。"""
import json

from sqlmodel import select

from app.agents import perception
from app.models import Anomaly, Storyline


def test_stats_basics():
    from app.agents import stats
    vals = [8, 9, 10, 11, 12]
    m = stats.med(vals)
    assert m == 10
    assert stats.mad(vals, m) > 0
    assert abs(stats.zscore(16, m, stats.mad(vals, m))) > 1
    assert stats.mom_ratio(12, 10) == 0.2


def test_scan_detects_all_three_storylines(session, world):
    """注入的 3 类销量异常全部被发现（召回率 100% > 90%）。"""
    result = perception.scan(session)
    assert result["scanned"] is True
    assert result["new_anomalies"] >= 3
    story_sl = session.exec(select(Storyline)).all()
    assert len(story_sl) == 3
    hit = 0
    for sl in story_sl:
        found = session.exec(select(Anomaly).where(
            Anomaly.store_id == sl.store_id,
            Anomaly.product_id == sl.product_id,
            Anomaly.type.in_(("sales_drop", "sales_surge")))).all()
        if found:
            hit += 1
            assert found[0].storyline_id == sl.id  # 关联真值（仅评估用）
    assert hit / len(story_sl) >= 0.9


def test_anomaly_schema_and_evidence(session):
    """统一 JSON：每个异常有观察值/期望值/偏差/严重度/证据/时间戳。"""
    anomalies = session.exec(select(Anomaly).limit(5)).all()
    assert anomalies
    for a in anomalies:
        assert a.observed is not None and a.expected is not None
        assert a.deviation_pct is not None
        assert a.severity in ("critical", "high", "medium", "low")
        assert a.detected_at and a.window_start and a.window_end
        assert a.detection_latency_h is not None
        ev = json.loads(a.evidence)
        assert len(ev) >= 2
        for e in ev:
            assert "type" in e and "tool" in e and "data" in e


def test_scan_idempotent_no_duplicates(session):
    """重复扫描不产生重复异常（同实体同窗口去重）。"""
    before = len(session.exec(select(Anomaly)).all())
    perception.scan(session)
    after = len(session.exec(select(Anomaly)).all())
    assert after == before


def test_stockout_anomaly_has_inventory_evidence(session):
    sl = session.get(Storyline, "sl-stockout-01")
    a = session.exec(select(Anomaly).where(Anomaly.store_id == sl.store_id,
                                           Anomaly.product_id == sl.product_id)).first()
    assert a is not None
    types = [e["type"] for e in json.loads(a.evidence)]
    assert "inventory_zero" in types
