# -*- coding: utf-8 -*-
"""异常注入器：三条可解释、可追溯的销量异常故事线（真值写入 storylines 表）。

故事线（窗口 [today-11, today-4]，缺货型持续到今天形成"待处置"状态）：
A 缺货型下降  stockout_drop  ：库存清零 + 逾期补货单 + 缺货工单 + 竞品促销 + 天气转凉
B 促销型上升  promo_surge    ：会员日品类加码促销 + 无竞品促销 + 销量骤升
C 客诉型下降  complaint_drop ：临期未折价 + 临期/质量客诉激增 + 会员复购下滑

注入前先"垫高基线"（故事线商品近 45 天日销 ~10），保证异常幅度大、证据充分。
"""
import json
import random
from datetime import timedelta

from sqlmodel import Session, select

from ..core import timeutil
from ..models import (Campaign, CompetitorPromo, Inventory, MemberSegmentStat, Product,
                      ReplenishmentOrder, SalesOrder, Store, Storyline, Ticket, Weather)
from . import model


def _pick_store(session: Session, tier: str, idx: int) -> Store:
    stores = session.exec(select(Store).where(Store.tier == tier).order_by(Store.id)).all()
    return stores[idx % len(stores)]


def _pick_product(session: Session, store: Store, category_id: str) -> Product | None:
    """选该店近 30 天销量最高的指定品类商品（证据最充分）。"""
    today = timeutil.business_today(session)
    start = (today - timedelta(days=30)).isoformat()
    rows = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == store.id, SalesOrder.category_id == category_id,
        SalesOrder.biz_date >= start).order_by(SalesOrder.qty.desc()).limit(300)).all()
    pids = list(dict.fromkeys(r.product_id for r in rows))
    return session.get(Product, pids[0]) if pids else None


def _boost_history(session: Session, store: Store, product: Product,
                   start, end, mu: float, rng: random.Random):
    """垫高历史基线：日销 ~ Poisson(mu)（无行则插入），保证异常幅度与证据链。"""
    rows = {r.biz_date: r for r in session.exec(select(SalesOrder).where(
        SalesOrder.store_id == store.id, SalesOrder.product_id == product.id,
        SalesOrder.biz_date >= start, SalesOrder.biz_date <= end)).all()}
    d = timeutil.parse_date(start)
    end_d = timeutil.parse_date(end)
    while d <= end_d:
        diso = d.isoformat()
        qty = model.poisson(rng, mu)
        r = rows.get(diso)
        if r is None:
            r = SalesOrder(biz_date=diso, store_id=store.id, product_id=product.id,
                           category_id=product.category_id)
            session.add(r)
        r.qty = qty
        r.amount = round(qty * product.list_price, 2)
        r.unit_price = product.list_price
        r.cost_amount = round(qty * product.cost_price, 2)
        r.orders = max(1, round(qty / 2.2))
        r.member_qty = round(qty * rng.uniform(0.45, 0.6))
        r.online_qty = round(qty * rng.uniform(0.12, 0.24))
        r.promo_flag = 0
        r.campaign_id = ""
        session.add(r)
        d += timedelta(days=1)
    session.commit()


def _scale_window(session: Session, store_id: str, product_id: str, start, end,
                  factor: float, unit_price: float | None = None, promo: Campaign | None = None):
    """按系数改写窗口销量（金额/成本/会员量同步缩放，保持账实一致）。"""
    rows = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == store_id, SalesOrder.product_id == product_id,
        SalesOrder.biz_date >= start, SalesOrder.biz_date <= end)).all()
    for r in rows:
        unit_cost = r.cost_amount / r.qty if r.qty else 0.0
        new_qty = int(r.qty * factor)
        r.qty = new_qty
        if unit_price is not None:
            r.unit_price = unit_price
        r.amount = round(new_qty * r.unit_price, 2)
        r.cost_amount = round(new_qty * unit_cost, 2)
        if promo is not None:
            r.promo_flag = 1
            r.campaign_id = promo.id
            r.member_qty = round(new_qty * 0.78)
        session.add(r)
    session.commit()


def inject_all(session: Session, seed: int = 42) -> list[dict]:
    today = timeutil.business_today(session)
    rng = random.Random(seed + 100)
    stories: list[dict] = []
    for sl in session.exec(select(Storyline)).all():
        session.delete(sl)
    session.commit()

    # ---------- A. 缺货型下降（饮料，标准店） ----------
    store_a = _pick_store(session, "standard", 6)
    prod_a = _pick_product(session, store_a, "C01")
    if prod_a:
        w_start = (today - timedelta(days=11)).isoformat()
        w_end = (today - timedelta(days=4)).isoformat()
        _boost_history(session, store_a, prod_a,
                       (today - timedelta(days=56)).isoformat(), today.isoformat(), 10.0, rng)
        inv = session.exec(select(Inventory).where(Inventory.store_id == store_a.id,
                                                   Inventory.product_id == prod_a.id)).first()
        if inv:
            inv.on_hand, inv.in_transit = 0, 0
            session.add(inv)
        session.add(ReplenishmentOrder(
            id=timeutil.new_id("rpl"), order_no="RPL-OVERDUE-01", idempotency_key="inj-rpl-01",
            store_id=store_a.id, product_id=prod_a.id, supplier_id=prod_a.supplier_id,
            qty=max(prod_a.moq, 100), unit_cost=prod_a.cost_price,
            amount=round(max(prod_a.moq, 100) * prod_a.cost_price, 2), status="confirmed",
            arrive_date=(today - timedelta(days=5)).isoformat(),
            note="注入：供应商延迟，逾期未到货", created_by="supply_planner_01",
            created_at=(today - timedelta(days=10)).isoformat() + "T09:00:00"))
        for i in range(5):
            session.add(Ticket(id=f"TINJ-A{i}", ticket_no=f"TKTINJ-A{i}",
                               biz_date=(today - timedelta(days=10 - i)).isoformat(),
                               store_id=store_a.id, product_id=prod_a.id, type="stockout",
                               severity="high", status="open",
                               description=f"{prod_a.name} 货架无货，顾客投诉买不到"))
        for i in range(7):
            session.add(CompetitorPromo(biz_date=(today - timedelta(days=10 - i)).isoformat(),
                                        competitor_name="惠康超市", category_id="C01",
                                        city=store_a.city, discount_pct=15.0,
                                        note="注入：竞品饮料促销 15%"))
        for i in range(7):
            d = (today - timedelta(days=10 - i)).isoformat()
            for w in session.exec(select(Weather).where(Weather.city == store_a.city,
                                                        Weather.biz_date == d)).all():
                w.condition, w.temp_high, w.temp_low = "cold_wave", 12.0, 4.0
                session.add(w)
        # 窗口内销量压至 5%，窗口后至今维持 10%（缺货持续待处置）
        _scale_window(session, store_a.id, prod_a.id, w_start, w_end, 0.05)
        _scale_window(session, store_a.id, prod_a.id,
                      (today - timedelta(days=3)).isoformat(), today.isoformat(), 0.10)
        sl = Storyline(id="sl-stockout-01", type="stockout_drop", store_id=store_a.id,
                       product_id=prod_a.id, category_id=prod_a.category_id,
                       start_date=w_start, end_date=w_end, truth_root_cause="stockout",
                       description=(f"缺货型下降：{store_a.name} {prod_a.name} 供应商延迟导致库存为0，"
                                    "叠加竞品促销与降温；基线日销~10，异常期降至~0.5"),
                       params=json.dumps({"baseline_mu": 10, "qty_factor": 0.05,
                                          "competitor_promo": True, "cold_wave": True,
                                          "overdue_replenishment": True}))
        session.add(sl)
        stories.append({"storyline_id": sl.id, "type": "stockout_drop", "store": store_a.id,
                        "product": prod_a.id, "category": prod_a.category_id,
                        "truth_root_cause": "stockout", "window": [w_start, w_end]})

    # ---------- B. 促销型上升（零食，旗舰店） ----------
    store_b = _pick_store(session, "flagship", 2)
    prod_b = _pick_product(session, store_b, "C04")
    if prod_b:
        w_start = (today - timedelta(days=10)).isoformat()
        w_end = (today - timedelta(days=4)).isoformat()
        _boost_history(session, store_b, prod_b,
                       (today - timedelta(days=55)).isoformat(), today.isoformat(), 12.0, rng)
        camp = Campaign(
            id="cmp-inj-memberday", code="CMP-INJ-MD", name="零食品类会员日加码促销",
            type="member_day", store_ids=store_b.id, category_id="C04",
            product_ids=prod_b.id, discount_pct=15.0, budget=8000,
            start_date=w_start, end_date=w_end, status="active", created_by="member_ops_01",
            created_at=(today - timedelta(days=11)).isoformat() + "T09:00:00",
            idempotency_key="inj-camp-01")
        session.add(camp)
        session.commit()
        _scale_window(session, store_b.id, prod_b.id, w_start, w_end, 2.2,
                      unit_price=round(prod_b.list_price * 0.85, 2), promo=camp)
        sl = Storyline(id="sl-promo-01", type="promo_surge", store_id=store_b.id,
                       product_id=prod_b.id, category_id=prod_b.category_id,
                       start_date=w_start, end_date=w_end, truth_root_cause="promo",
                       description=(f"促销型上升：{store_b.name} {prod_b.name} 会员日加码 15% 折扣，"
                                    "竞品当期无促销；基线日销~12，异常期~26"),
                       params=json.dumps({"baseline_mu": 12, "qty_factor": 2.2,
                                          "discount_pct": 15.0, "competitor_promo": False}))
        session.add(sl)
        stories.append({"storyline_id": sl.id, "type": "promo_surge", "store": store_b.id,
                        "product": prod_b.id, "category": prod_b.category_id,
                        "truth_root_cause": "promo", "window": [w_start, w_end]})

    # ---------- C. 客诉型下降（乳品，大店） ----------
    store_c = _pick_store(session, "large", 12)
    prod_c = _pick_product(session, store_c, "C06")
    if prod_c:
        w_start = (today - timedelta(days=11)).isoformat()
        w_end = (today - timedelta(days=4)).isoformat()
        _boost_history(session, store_c, prod_c,
                       (today - timedelta(days=56)).isoformat(), today.isoformat(), 10.0, rng)
        inv = session.exec(select(Inventory).where(Inventory.store_id == store_c.id,
                                                   Inventory.product_id == prod_c.id)).first()
        if inv:
            inv.expiry_date = (today + timedelta(days=6)).isoformat()
            session.add(inv)
        for i in range(12):
            session.add(Ticket(id=f"TINJ-C{i}", ticket_no=f"TKTINJ-C{i}",
                               biz_date=(today - timedelta(days=11 - i)).isoformat(),
                               store_id=store_c.id, product_id=prod_c.id,
                               type="expiry" if i % 2 == 0 else "quality",
                               severity="high", status="open",
                               description=f"{prod_c.name} 临期未折价，购买后发现问题要求退换"))
        _scale_window(session, store_c.id, prod_c.id, w_start, w_end, 0.40)
        _scale_window(session, store_c.id, prod_c.id,
                      (today - timedelta(days=3)).isoformat(), today.isoformat(), 0.45)
        month = (today.replace(day=1)).isoformat()
        for ms in session.exec(select(MemberSegmentStat).where(
                MemberSegmentStat.store_id == store_c.id,
                MemberSegmentStat.month_start == month)).all():
            ms.repurchase_members = round(ms.repurchase_members * 0.7)
            session.add(ms)
        sl = Storyline(id="sl-complaint-01", type="complaint_drop", store_id= store_c.id,
                       product_id=prod_c.id, category_id=prod_c.category_id,
                       start_date=w_start, end_date=w_end, truth_root_cause="complaint",
                       description=(f"客诉型下降：{store_c.name} {prod_c.name} 临期商品未折价引发客诉，"
                                    "会员复购下滑；基线日销~10，异常期~4.5"),
                       params=json.dumps({"baseline_mu": 10, "qty_factor": 0.45,
                                          "expiry_soon": True, "ticket_surge": "expiry/quality",
                                          "churn_factor": 0.7}))
        session.add(sl)
        stories.append({"storyline_id": sl.id, "type": "complaint_drop", "store": store_c.id,
                        "product": prod_c.id, "category": prod_c.category_id,
                        "truth_root_cause": "complaint", "window": [w_start, w_end]})

    session.commit()
    return stories
