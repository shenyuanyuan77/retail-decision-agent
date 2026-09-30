# -*- coding: utf-8 -*-
"""Mock 数据生成器：180 天 × 50 门店 × 500 SKU，固定种子可重复生成。

生成：主数据 / 会员 / 日历 / 天气 / 基线促销 / 销售 / 库存 / 工单 / 竞品 / 会员分层统计。
"""
import math
import random
from datetime import date, timedelta

from sqlalchemy import delete, insert
from sqlmodel import Session

from ..core import timeutil
from ..models import (
    BaselineMu, CalendarDay, Campaign, Category, CompetitorPromo, Inventory, Member,
    MemberSegmentStat, Product, Region, SalesOrder, Store, Supplier, Ticket, Weather,
)
from . import model

COMPETITORS = ["惠康超市", "永达 mart", "百汇百货", "万家福", "优品汇"]


def _batch_insert(session: Session, table, rows: list[dict], chunk: int = 50000):
    for i in range(0, len(rows), chunk):
        session.execute(insert(table), rows[i:i + chunk])


def generate_all(session: Session, *, days: int = 180, n_stores: int = 50,
                 n_skus: int = 500, seed: int = 42, end_date: date | None = None,
                 reset: bool = True) -> dict:
    rng = random.Random(seed)
    end = end_date or date.today()
    start = end - timedelta(days=days - 1)

    if reset:
        for t in (SalesOrder, Inventory, Ticket, CompetitorPromo, Weather, CalendarDay,
                  Campaign, Member, MemberSegmentStat, Product, Category, Supplier,
                  Store, Region):
            session.execute(delete(t))
        session.commit()

    # ---------- 主数据 ----------
    regions = []
    for rid, rname, cities in model.REGIONS:
        regions.append(Region(id=rid, code=rid, name=rname))
        session.add(regions[-1])
    session.commit()

    city_pool = [(rid, c) for rid, _, cities in model.REGIONS for c in cities]
    stores: list[Store] = []
    for i in range(n_stores):
        tier = "flagship" if i < n_stores * 0.2 else ("large" if i < n_stores * 0.5 else "standard")
        rid, city = city_pool[i % len(city_pool)]
        stores.append(Store(id=f"S{i+1:03d}", code=f"S{i+1:03d}", name=f"{city}{i+1:03d}店",
                            region_id=rid, city=city, tier=tier,
                            open_date=(start - timedelta(days=365)).isoformat()))
        session.add(stores[-1])
    session.commit()

    suppliers = [Supplier(id=f"V{i+1:02d}", code=f"V{i+1:02d}", name=f"供应商{i+1:02d}",
                          rating=round(rng.uniform(3.0, 5.0), 1),
                          region_id=model.REGIONS[i % 5][0]) for i in range(15)]
    session.add_all(suppliers)

    cats = []
    for code, name, shelf, _sens, _pr, _base in model.CATEGORIES:
        cats.append(Category(id=code, code=code, name=name))
    session.add_all(cats)
    session.commit()

    n_per_cat = math.ceil(n_skus / len(model.CATEGORIES))
    products: list[Product] = []
    pop_rng = random.Random(seed + 1)
    popularity: dict[str, float] = {}
    for ci, (code, name, shelf, _sens, (lo, hi), base) in enumerate(model.CATEGORIES):
        for k in range(n_per_cat):
            if len(products) >= n_skus:
                break
            pid = f"P{len(products)+1:05d}"
            cost = round(pop_rng.uniform(lo, hi) * 0.72, 2)
            products.append(Product(
                id=pid, sku=pid, name=f"{name}-{k+1:02d}", category_id=code,
                brand=f"品牌{(k % 12) + 1}", cost_price=cost,
                list_price=round(cost / 0.72, 2), shelf_life_days=shelf,
                supplier_id=f"V{(ci * 3 + k) % 15 + 1:02d}",
                moq=pop_rng.choice([10, 20, 30, 50]), lead_time_days=pop_rng.choice([2, 3, 3, 4, 5]),
                safety_stock_default=pop_rng.choice([10, 15, 20, 30])))
            popularity[pid] = min(3.0, math.exp(pop_rng.gauss(0, 0.45)))
    session.add_all(products)
    session.commit()

    # ---------- 日历 ----------
    cal_rows = []
    d = start
    while d <= end:
        cal = model.calendar_factors(d)
        cal_rows.append(CalendarDay(biz_date=d.isoformat(), is_weekend=cal["is_weekend"],
                                    is_holiday=cal["is_holiday"], holiday_name=cal["holiday_name"],
                                    is_member_day=cal["is_member_day"]))
        d += timedelta(days=1)
    session.add_all(cal_rows)

    # ---------- 天气（按城市×天） ----------
    weather_rng = random.Random(seed + 2)
    cities = sorted({s.city for s in stores})
    weather: dict[tuple[str, str], dict] = {}
    w_rows = []
    for city in cities:
        d = start
        while d <= end:
            w = model.weather_for_date(weather_rng, d, city)
            weather[(city, d.isoformat())] = w["condition"]
            w_rows.append(dict(biz_date=d.isoformat(), city=city, condition=w["condition"],
                               temp_high=w["temp_high"], temp_low=w["temp_low"],
                               precip_mm=w["precip_mm"]))
            d += timedelta(days=1)
    _batch_insert(session, Weather.__table__, w_rows)

    # ---------- 基线促销：每月会员日 + 2 个品类促销 ----------
    promo_index: dict[tuple[str, str], tuple[str, float]] = {}  # (date, category) -> (campaign_id, discount)
    campaigns = []
    d0 = start.replace(day=1)
    promo_rng = random.Random(seed + 3)
    while d0 <= end:
        md = d0.replace(day=18)
        if start <= md <= end:
            cid = timeutil.new_id("cmp")
            campaigns.append(Campaign(
                id=cid, code=f"CMP-MD-{d0.strftime('%Y%m')}", name=f"{d0.month}月会员日全场活动",
                type="member_day", store_ids="", category_id="", discount_pct=8.0,
                budget=50000, start_date=md.isoformat(), end_date=md.isoformat(),
                status="active", created_by="member_ops_01",
                created_at=md.isoformat() + "T09:00:00"))
            dd = md.isoformat()
            for _, ccode, *_ in model.CATEGORIES:
                promo_index[(dd, ccode)] = (cid, 0.08)
        for _ in range(2):
            cat = promo_rng.choice(model.CATEGORIES)
            cs = d0 + timedelta(days=promo_rng.randint(1, 24))
            ce = cs + timedelta(days=6)
            if ce < start or cs > end:
                continue
            cid = timeutil.new_id("cmp")
            campaigns.append(Campaign(
                id=cid, code=f"CMP-{cat[0]}-{d0.strftime('%Y%m')}", name=f"{cat[1]}品类月度促销",
                type="category", store_ids="", category_id=cat[0], discount_pct=10.0,
                budget=30000, start_date=cs.isoformat(), end_date=ce.isoformat(),
                status="active", created_by="member_ops_01", created_at=cs.isoformat() + "T09:00:00"))
            dd2 = cs
            while dd2 <= ce:
                promo_index[(dd2.isoformat(), cat[0])] = (cid, 0.10)
                dd2 += timedelta(days=1)
        d0 = (d0 + timedelta(days=32)).replace(day=1)
    session.add_all(campaigns)
    session.commit()

    # ---------- 会员 ----------
    member_rng = random.Random(seed + 4)
    members = []
    for s in stores:
        for k in range(100):
            seg = member_rng.choices(["vip", "high", "normal", "new"], [0.10, 0.20, 0.55, 0.15])[0]
            members.append(Member(
                id=f"M{s.id[1:]}-{k:03d}", code=f"M{s.id}-{k:03d}", name=f"会员{s.code}{k:03d}",
                phone_masked=f"138****{member_rng.randint(1000, 9999)}", segment=seg,
                register_store_id=s.id,
                register_date=(start - timedelta(days=member_rng.randint(30, 700))).isoformat()))
    _batch_insert(session, Member.__table__, [m.model_dump() for m in members], chunk=20000)

    # ---------- 销售 + 库存 ----------
    cat_meta = {c[0]: c for c in model.CATEGORIES}
    sales_rows: list[dict] = []
    inv_rows: list[dict] = []
    baseline_mu: dict[tuple[str, str], float] = {}
    sales_rng = random.Random(seed + 5)
    store_noises = {s.id: random.Random(seed + 100 + i).uniform(0.85, 1.15)
                    for i, s in enumerate(stores)}

    # 商品按品类内流行度排序，门店按档位均衡选品
    by_cat: dict[str, list[Product]] = {}
    for p in products:
        by_cat.setdefault(p.category_id, []).append(p)
    for codelist in by_cat.values():
        codelist.sort(key=lambda p: -popularity[p.id])

    dates = [start + timedelta(days=i) for i in range(days)]
    cal_map = {d.isoformat(): model.calendar_factors(d) for d in dates}

    for s in stores:
        assort_frac = model.TIER_ASSORT[s.tier]
        per_cat = max(5, int(len(products) / len(model.CATEGORIES) * assort_frac))
        assortment: list[Product] = []
        for ccode, plist in by_cat.items():
            assortment.extend(plist[:per_cat])
        tier_f = model.TIER_FACTOR[s.tier]
        sn = store_noises[s.id]

        mu_map: dict[str, float] = {}
        for p in assortment:
            base = cat_meta[p.category_id][5]
            mu_map[p.id] = base * popularity[p.id] * tier_f * sn
            baseline_mu[(s.id, p.id)] = mu_map[p.id]

        for d in dates:
            diso = d.isoformat()
            cal = cal_map[diso]
            wcond = weather.get((s.city, diso), "sunny")
            for p in assortment:
                promo = promo_index.get((diso, p.category_id))
                lift, camp_id, disc = 1.0, "", 0.0
                if promo:
                    camp_id, disc = promo
                    lift = 1.0 + disc * 6   # 8% 折扣 → 1.48x；10% → 1.6x
                qty = model.baseline_daily_qty(mu_map[p.id], cal, wcond, p.category_id,
                                               lift, sales_rng)
                if qty <= 0:
                    continue
                unit_price = round(p.list_price * (1 - disc), 2)
                mshare = model.member_qty_share(sales_rng, bool(promo))
                sales_rows.append(dict(
                    biz_date=diso, store_id=s.id, product_id=p.id, category_id=p.category_id,
                    qty=qty, amount=round(qty * unit_price, 2), unit_price=unit_price,
                    cost_amount=round(qty * p.cost_price, 2),
                    orders=max(1, round(qty / 2.2)),
                    member_qty=round(qty * mshare),
                    online_qty=round(qty * sales_rng.uniform(0.12, 0.24)),
                    promo_flag=1 if promo else 0, campaign_id=camp_id))

        # 库存：约 12 天覆盖 + 安全库存
        for p in assortment:
            mu = mu_map[p.id]
            inv_rows.append(dict(
                store_id=s.id, product_id=p.id,
                on_hand=max(0, round(mu * sales_rng.uniform(8, 16))),
                in_transit=0,
                safety_stock=max(5, round(mu * 5)),
                expiry_date="", updated_at=timeutil.now_iso()))

    _batch_insert(session, SalesOrder.__table__, sales_rows)
    _batch_insert(session, Inventory.__table__, inv_rows, chunk=50000)
    _batch_insert(session, BaselineMu.__table__,
                  [{"store_id": s, "product_id": p, "mu": m} for (s, p), m in baseline_mu.items()],
                  chunk=50000)

    # 临期批次：为烘焙/生鲜/乳品随机赋予到期日（部分临近 → 支撑临期场景）
    exp_rng = random.Random(seed + 6)
    prod_by_id = {p.id: p for p in products}
    near_expire = []
    for inv in inv_rows:
        p = prod_by_id[inv["product_id"]]
        if p.shelf_life_days and p.shelf_life_days <= 14 and exp_rng.random() < 0.08:
            near_expire.append((inv["store_id"], inv["product_id"],
                                (end + timedelta(days=exp_rng.randint(2, 10))).isoformat()))
    from sqlmodel import select as _select
    for sid, pid, ed in near_expire:
        row = session.exec(_select(Inventory).where(Inventory.store_id == sid,
                                                    Inventory.product_id == pid)).first()
        if row:
            row.expiry_date = ed
    session.commit()

    # ---------- 客服工单基线 ----------
    ticket_rng = random.Random(seed + 7)
    ticket_rows = []
    tn = 0
    for s in stores:
        for d in dates:
            n = model.poisson(ticket_rng, 0.35)
            for _ in range(n):
                tn += 1
                ttype = ticket_rng.choices(
                    ["service", "quality", "delivery", "stockout", "expiry"],
                    [0.40, 0.20, 0.20, 0.10, 0.10])[0]
                ticket_rows.append(dict(
                    id=f"T{tn:07d}", ticket_no=f"TKT{tn:07d}", biz_date=d.isoformat(),
                    store_id=s.id, type=ttype,
                    severity="high" if ticket_rng.random() < 0.15 else "normal",
                    status="resolved" if ticket_rng.random() < 0.8 else "open",
                    description=f"{ttype}类客诉(基线)"))
    _batch_insert(session, Ticket.__table__, ticket_rows, chunk=50000)

    # ---------- 竞品促销 ----------
    cp_rng = random.Random(seed + 8)
    cp_rows = []
    for d in dates:
        for _ in range(model.poisson(cp_rng, 0.4)):
            cat = cp_rng.choice(model.CATEGORIES)
            city = cp_rng.choice(cities)
            disc = round(cp_rng.uniform(5, 25), 1)
            dur = cp_rng.randint(3, 10)
            comp = cp_rng.choice(COMPETITORS)
            dd = d
            for _k in range(dur):
                if dd > end:
                    break
                cp_rows.append(dict(biz_date=dd.isoformat(), competitor_name=comp,
                                    category_id=cat[0], city=city, discount_pct=disc,
                                    note=f"{comp} {cat[1]}促销{disc}%"))
                dd += timedelta(days=1)
    _batch_insert(session, CompetitorPromo.__table__, cp_rows)

    # ---------- 会员分层月度统计 ----------
    ms_rng = random.Random(seed + 9)
    ms_rows = []
    m0 = start.replace(day=1)
    while m0 <= end:
        for s in stores:
            for seg in ("vip", "high", "normal", "new"):
                n_seg = 100 * {"vip": 0.10, "high": 0.20, "normal": 0.55, "new": 0.15}[seg]
                active = round(n_seg * ms_rng.uniform(0.55, 0.75))
                rep = round(active * ms_rng.uniform(0.35, 0.45))
                ms_rows.append(dict(store_id=s.id, month_start=m0.isoformat(), segment=seg,
                                    members=round(n_seg), active_members=active,
                                    repurchase_members=rep))
        m0 = (m0 + timedelta(days=32)).replace(day=1)
    _batch_insert(session, MemberSegmentStat.__table__, ms_rows)

    # ---------- 元数据 ----------
    timeutil.set_meta(session, "today", end.isoformat())
    timeutil.set_meta(session, "seed", str(seed))
    timeutil.set_meta(session, "horizon_days", str(days))
    timeutil.set_meta(session, "generated_at", timeutil.now_iso())
    session.commit()
    from ..core.db import engine as _engine
    with _engine.connect() as _conn:
        _conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")

    return {
        "days": days, "n_stores": n_stores, "n_skus": len(products),
        "sales_rows": len(sales_rows), "inventory_rows": len(inv_rows),
        "ticket_rows": len(ticket_rows), "members": len(members),
        "campaigns": len(campaigns), "period": [start.isoformat(), end.isoformat()],
    }
