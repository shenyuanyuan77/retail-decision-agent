# -*- coding: utf-8 -*-
"""目标3测试：数据可重复生成 + 三条异常故事线证据链。"""
from datetime import timedelta

import pytest
from sqlmodel import select

from app.core import timeutil
from app.models import (Campaign, CompetitorPromo, Inventory, MemberSegmentStat,
                        ReplenishmentOrder, SalesOrder, Storyline, Ticket, Weather)


def _story(session, sid):
    return session.get(Storyline, sid)


@pytest.fixture(autouse=True, scope="module")
def _fresh_world():
    """本文件断言原始故事线数据，先重建世界（清除 Agent 推演影响）。"""
    from app.bootstrap import bootstrap
    bootstrap(days=45, stores=12, skus=100, seed=42)


def test_three_storylines_exist(session, world):
    assert len(world["storylines"]) == 3
    types = {s["type"] for s in world["storylines"]}
    assert types == {"stockout_drop", "promo_surge", "complaint_drop"}
    for s in world["storylines"]:
        assert s["truth_root_cause"] in ("stockout", "promo", "complaint")


def test_storyline_a_stockout_evidence(session, world):
    """缺货型下降：库存0 + 逾期补货单 + 缺货工单 + 竞品促销 + 降温（≥3 条证据）。"""
    sl = _story(session, "sl-stockout-01")
    assert sl.truth_root_cause == "stockout"
    # 证据1：库存为0
    inv = session.exec(select(Inventory).where(
        Inventory.store_id == sl.store_id, Inventory.product_id == sl.product_id)).first()
    assert inv is not None and inv.on_hand == 0
    # 证据2：逾期未到补货单
    rpl = session.exec(select(ReplenishmentOrder).where(
        ReplenishmentOrder.store_id == sl.store_id,
        ReplenishmentOrder.product_id == sl.product_id,
        ReplenishmentOrder.status == "confirmed")).all()
    assert any(r.arrive_date < timeutil.business_today(session).isoformat() for r in rpl)
    # 证据3：缺货工单
    tickets = session.exec(select(Ticket).where(
        Ticket.store_id == sl.store_id, Ticket.product_id == sl.product_id,
        Ticket.type == "stockout")).all()
    assert len(tickets) >= 3
    # 证据4：竞品促销
    promos = session.exec(select(CompetitorPromo).where(
        CompetitorPromo.category_id == sl.category_id,
        CompetitorPromo.biz_date >= sl.start_date, CompetitorPromo.biz_date <= sl.end_date)).all()
    assert len(promos) >= 3
    # 证据5：异常期销量显著低于基线
    before = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == sl.store_id, SalesOrder.product_id == sl.product_id,
        SalesOrder.biz_date >= (timeutil.parse_date(sl.start_date) - timedelta(days=14)).isoformat(),
        SalesOrder.biz_date < sl.start_date)).all()
    during = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == sl.store_id, SalesOrder.product_id == sl.product_id,
        SalesOrder.biz_date >= sl.start_date, SalesOrder.biz_date <= sl.end_date)).all()
    avg_before = sum(r.qty for r in before) / max(1, len(before))
    avg_during = sum(r.qty for r in during) / max(1, len(during))
    assert avg_before > 5 and avg_during < avg_before * 0.15


def test_storyline_b_promo_evidence(session, world):
    """促销型上升：促销活动存在 + 促销期价格折扣 + 销量上升（≥3 条证据）。"""
    sl = _story(session, "sl-promo-01")
    assert sl.truth_root_cause == "promo"
    camp = session.exec(select(Campaign).where(
        Campaign.start_date <= sl.end_date, Campaign.end_date >= sl.start_date,
        Campaign.category_id == sl.category_id)).all()
    assert any(sl.store_id in (c.store_ids or "") for c in camp)
    during = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == sl.store_id, SalesOrder.product_id == sl.product_id,
        SalesOrder.biz_date >= sl.start_date, SalesOrder.biz_date <= sl.end_date)).all()
    assert during and all(r.promo_flag == 1 for r in during)
    before = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == sl.store_id, SalesOrder.product_id == sl.product_id,
        SalesOrder.biz_date < sl.start_date,
        SalesOrder.biz_date >= (timeutil.parse_date(sl.start_date) - timedelta(days=14)).isoformat()
    )).all()
    avg_before = sum(r.qty for r in before) / max(1, len(before))
    avg_during = sum(r.qty for r in during) / max(1, len(during))
    assert avg_during > avg_before * 1.8


def test_storyline_c_complaint_evidence(session, world):
    """客诉型下降：临期库存 + 临期/质量客诉激增 + 会员复购下滑 + 销量下降。"""
    sl = _story(session, "sl-complaint-01")
    assert sl.truth_root_cause == "complaint"
    inv = session.exec(select(Inventory).where(
        Inventory.store_id == sl.store_id, Inventory.product_id == sl.product_id)).first()
    assert inv and inv.expiry_date  # 临期批次
    tickets = session.exec(select(Ticket).where(
        Ticket.store_id == sl.store_id, Ticket.product_id == sl.product_id,
        Ticket.type.in_(("expiry", "quality")))).all()  # type_.in_ for sqlmodel
    assert len(tickets) >= 5
    today = timeutil.business_today(session)
    ms = session.exec(select(MemberSegmentStat).where(
        MemberSegmentStat.store_id == sl.store_id,
        MemberSegmentStat.month_start == today.replace(day=1).isoformat())).all()
    assert ms and sum(m.repurchase_members for m in ms) / max(1, sum(m.active_members for m in ms)) < 0.4
    during = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == sl.store_id, SalesOrder.product_id == sl.product_id,
        SalesOrder.biz_date >= sl.start_date, SalesOrder.biz_date <= sl.end_date)).all()
    before = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == sl.store_id, SalesOrder.product_id == sl.product_id,
        SalesOrder.biz_date < sl.start_date,
        SalesOrder.biz_date >= (timeutil.parse_date(sl.start_date) - timedelta(days=14)).isoformat()
    )).all()
    avg_before = sum(r.qty for r in before) / max(1, len(before))
    avg_during = sum(r.qty for r in during) / max(1, len(during))
    assert avg_during < avg_before * 0.7


def test_data_reproducible(session, world):
    """同种子重复生成 → 销量行数一致（可重复生成）。"""
    from sqlalchemy import func
    from app.world.generator import generate_all
    from app.world.injector import inject_all
    generate_all(session, days=45, n_stores=12, n_skus=100, seed=42)   # 第一次纯生成
    n1 = session.exec(select(func.count()).select_from(SalesOrder)).one()
    generate_all(session, days=45, n_stores=12, n_skus=100, seed=42)   # 第二次纯生成
    n2 = session.exec(select(func.count()).select_from(SalesOrder)).one()
    assert n1 == n2
    inject_all(session, seed=42)  # 重新注入保证后续测试仍有故事线


def test_weather_injected_cold_wave(session, world):
    sl = _story(session, "sl-stockout-01")
    store_city = session.exec(select(Weather).where(
        Weather.biz_date >= sl.start_date, Weather.biz_date <= sl.end_date)).all()
    assert any(w.condition == "cold_wave" for w in store_city)
