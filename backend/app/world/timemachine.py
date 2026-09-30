# -*- coding: utf-8 -*-
"""世界推演器（时间机器）：把业务时间推进 N 天，按因果模型生成未来数据。

因果规则（与生成器/打法库一致，均有据可查）：
1. 补货到货：confirmed 且 arrive_date<=当日 → on_hand+=qty, in_transit-=qty（库存门控销售）
2. 促销活动：active 且覆盖门店/品类 → lift = 1 + discount%×6，计入 cost_actual
3. 销售需求：BaselineMu × 日历 × 天气 × 促销，Poisson 噪声，qty=min(需求, 现货)
4. 客服整改：门店存在 pending 回访任务 → 该店客诉概率减半
5. 缺货：有需求但无货 → 概率性生成缺货工单
推演结果供评估层 T+7 复盘（执行前后真实指标对比）。
"""
import random
from datetime import timedelta

from sqlalchemy import insert
from sqlmodel import Session, select

from ..core import timeutil
from ..models import (BaselineMu, CalendarDay, Campaign, CompetitorPromo, Inventory,
                      Product, ReplenishmentOrder, SalesOrder, Store, Ticket, TicketTask,
                      Weather)
from . import model

COMPETITORS = ["惠康超市", "永达 mart", "百汇百货", "万家福", "优品汇"]


def _campaign_cover(camps: list[Campaign]) -> dict:
    """(store_id, category_id) -> (campaign, discount_pct) 覆盖表。"""
    cover: dict[tuple[str, str], tuple[str, float]] = {}
    for c in camps:
        stores = c.store_ids.split(",") if c.store_ids else [""]
        for st in stores:
            cover[(st or "*", c.category_id or "*")] = (c.id, c.discount_pct)
    return cover


def advance_days(session: Session, days: int = 7) -> dict:
    today = timeutil.business_today(session)
    seed = int(timeutil.get_meta(session, "seed") or 42)

    stores = session.exec(select(Store)).all()
    store_by_id = {s.id: s for s in stores}
    products = session.exec(select(Product)).all()
    prod_by_id = {p.id: p for p in products}
    mus = session.exec(select(BaselineMu)).all()
    cat_by_prod = {p.id: p.category_id for p in products}
    invs = session.exec(select(Inventory)).all()
    inv_map = {(i.store_id, i.product_id): i for i in invs}
    cities = sorted({s.city for s in stores})

    sales_rows: list[dict] = []
    weather_rows: list[dict] = []
    cal_rows: list[CalendarDay] = []
    cp_rows: list[dict] = []
    ticket_rows: list[dict] = []
    tn = session.exec(select(Ticket).order_by(Ticket.id.desc())).first()
    try:
        tn = int(str(tn.id)[1:]) if tn else 0
    except ValueError:
        tn = 100000  # 注入工单号非数字，从安全起点继续
    campaign_costs: dict[str, float] = {}

    # 客服整改生效门店
    cs_active_stores = {t.store_id for t in session.exec(
        select(TicketTask).where(TicketTask.status == "pending")).all()}

    for day_i in range(1, days + 1):
        d = today + timedelta(days=day_i)
        rng = random.Random(seed * 100003 + day_i)
        cal = model.calendar_factors(d)
        cal_rows.append(CalendarDay(biz_date=d.isoformat(), is_weekend=cal["is_weekend"],
                                    is_holiday=cal["is_holiday"],
                                    holiday_name=cal["holiday_name"],
                                    is_member_day=cal["is_member_day"]))
        wcond = {}
        for city in cities:
            import zlib
            city_seed = zlib.crc32(city.encode("utf-8"))
            w = model.weather_for_date(
                random.Random(seed * 100019 + day_i * 131 + city_seed % 9973), d, city)
            wcond[city] = w["condition"]
            weather_rows.append(dict(biz_date=d.isoformat(), city=city,
                                     condition=w["condition"], temp_high=w["temp_high"],
                                     temp_low=w["temp_low"], precip_mm=w["precip_mm"]))
        # 竞品促销基线
        for _ in range(model.poisson(rng, 0.4)):
            cat = rng.choice(model.CATEGORIES)
            city = rng.choice(cities)
            disc = round(rng.uniform(5, 25), 1)
            comp = rng.choice(COMPETITORS)
            for _k in range(rng.randint(3, 10)):
                cp_rows.append(dict(biz_date=(d + timedelta(days=_k)).isoformat(),
                                    competitor_name=comp, category_id=cat[0], city=city,
                                    discount_pct=disc, note=f"{comp} {cat[1]}促销{disc}%"))

        # 1) 补货到货
        for rpl in session.exec(select(ReplenishmentOrder).where(
                ReplenishmentOrder.status == "confirmed")).all():
            if rpl.arrive_date <= d.isoformat():
                rpl.status = "arrived"
                session.add(rpl)
                inv = inv_map.get((rpl.store_id, rpl.product_id))
                if inv:
                    inv.on_hand += rpl.qty
                    inv.in_transit = max(0, inv.in_transit - rpl.qty)
                    session.add(inv)

        # 2) 促销覆盖
        camps = session.exec(select(Campaign).where(
            Campaign.status == "active",
            Campaign.start_date <= d.isoformat(), Campaign.end_date >= d.isoformat())).all()
        cover = _campaign_cover(camps)
        stockout_marked: set = set()

        # 3) 需求与销售（库存门控）
        for mu_row in mus:
            sid, pid = mu_row.store_id, mu_row.product_id
            inv = inv_map.get((sid, pid))
            if inv is None:
                continue
            cat_id = cat_by_prod.get(pid, "")
            camp_id, disc = cover.get((sid, cat_id)) or cover.get(("*", cat_id)) \
                or cover.get((sid, "*")) or cover.get(("*", "*")) or ("", 0.0)
            store = store_by_id[sid]
            lift = 1 + disc / 100 * 6
            demand = model.baseline_daily_qty(mu_row.mu, cal, wcond.get(store.city, "sunny"),
                                              cat_id, lift, rng)
            qty = min(demand, inv.on_hand)
            if qty > 0:
                p = prod_by_id[pid]
                unit_price = round(p.list_price * (1 - disc / 100), 2)
                sales_rows.append(dict(
                    biz_date=d.isoformat(), store_id=sid, product_id=pid, category_id=cat_id,
                    qty=qty, amount=round(qty * unit_price, 2), unit_price=unit_price,
                    cost_amount=round(qty * p.cost_price, 2),
                    orders=max(1, round(qty / 2.2)),
                    member_qty=round(qty * (0.62 if camp_id else rng.uniform(0.45, 0.6))),
                    online_qty=round(qty * rng.uniform(0.12, 0.24)),
                    promo_flag=1 if camp_id else 0, campaign_id=camp_id))
                inv.on_hand -= qty
                session.add(inv)
                if camp_id and disc > 0:
                    campaign_costs[camp_id] = campaign_costs.get(camp_id, 0) + qty * unit_price * disc / 100
            elif (demand > 0 and inv.on_hand == 0 and mu_row.mu >= 1.0
                  and rng.random() < 0.05 and sid not in stockout_marked):
                stockout_marked.add(sid)
                tn += 1
                ticket_rows.append(dict(
                    id=f"T{tn:07d}", ticket_no=f"TKT{tn:07d}", biz_date=d.isoformat(),
                    store_id=sid, product_id=pid, member_id="", type="stockout",
                    severity="normal", status="open", description="缺货自动工单（推演期）"))

        # 4) 基线工单（客服整改减半）
        for st in stores:
            lam = 0.35 if st.id not in cs_active_stores else 0.18
            for _ in range(model.poisson(rng, lam)):
                tn += 1
                ttype = rng.choices(["service", "quality", "delivery", "stockout", "expiry"],
                                    [0.40, 0.20, 0.20, 0.10, 0.10])[0]
                ticket_rows.append(dict(
                    id=f"T{tn:07d}", ticket_no=f"TKT{tn:07d}", biz_date=d.isoformat(),
                    store_id=st.id, product_id="", member_id="", type=ttype,
                    severity="high" if rng.random() < 0.15 else "normal",
                    status="open", description=f"{ttype}类客诉(推演期)"))
        session.commit()

    if sales_rows:
        for i in range(0, len(sales_rows), 50000):
            session.execute(insert(SalesOrder.__table__), sales_rows[i:i + 50000])
    if weather_rows:
        session.execute(insert(Weather.__table__), weather_rows)
    if cp_rows:
        session.execute(insert(CompetitorPromo.__table__), cp_rows)
    if ticket_rows:
        session.execute(insert(Ticket.__table__), ticket_rows)
    if cal_rows:
        session.add_all(cal_rows)

    for cid, cost in campaign_costs.items():
        camp = session.get(Campaign, cid)
        if camp:
            camp.cost_actual = round((camp.cost_actual or 0) + cost, 2)
            session.add(camp)

    new_today = timeutil.advance_business_today(session, days)
    session.commit()
    return {"advanced_days": days, "new_today": new_today.isoformat(),
            "sales_rows": len(sales_rows), "tickets": len(ticket_rows),
            "campaign_costs": {k: round(v, 2) for k, v in campaign_costs.items()}}
