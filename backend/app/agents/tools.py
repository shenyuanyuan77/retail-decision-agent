# -*- coding: utf-8 -*-
"""Agent 数据接入工具层（只读）。Agent 的所有数字必须来自这些工具返回。

工具名与目标4要求一致：get_sales_timeseries / get_inventory / get_tickets /
get_campaigns / get_weather_calendar / get_competitor_promo。
"""
from datetime import timedelta

from sqlmodel import Session, select

from ..core.timeutil import business_today
from ..models import (BaselineMu, CalendarDay, CompetitorPromo, MemberSegmentStat,
                      SalesOrder, Weather)
from ..services import cs as cs_svc
from ..services import inventory as inv_svc
from ..services import master as master_svc
from ..services import members as member_svc
from ..services import sales as sales_svc


def get_sales_timeseries(session: Session, store_id: str, product_id: str,
                         days: int = 42) -> list[dict]:
    return sales_svc.timeseries(session, store_id=store_id, product_id=product_id, days=days)


def get_store_sku_sales_matrix(session: Session, days: int = 42) -> list[dict]:
    """感知层批量扫描：[{store_id, product_id, category_id, points:[{date,qty,...}]}]"""
    today = business_today(session)
    start = (today - timedelta(days=days - 1)).isoformat()
    rows = session.exec(select(SalesOrder).where(SalesOrder.biz_date >= start)
                        .order_by(SalesOrder.store_id, SalesOrder.product_id,
                                  SalesOrder.biz_date)).all()
    matrix: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r.store_id, r.product_id)
        entry = matrix.get(key)
        if entry is None:
            entry = {"store_id": r.store_id, "product_id": r.product_id,
                     "category_id": r.category_id, "points": []}
            matrix[key] = entry
        entry["points"].append({"date": r.biz_date, "qty": r.qty, "amount": r.amount,
                                "unit_price": r.unit_price, "promo_flag": r.promo_flag,
                                "member_qty": r.member_qty})
    return list(matrix.values())


def get_inventory(session: Session, store_id: str = "", product_id: str = "",
                  out_of_stock: bool = False, below_safety: bool = False) -> list[dict]:
    return inv_svc.query_inventory(session, store_id=store_id, product_id=product_id,
                                   out_of_stock=out_of_stock, below_safety=below_safety,
                                   limit=10000)["items"]


def get_inventory_one(session: Session, store_id: str, product_id: str) -> dict | None:
    return inv_svc.get_inventory(session, store_id, product_id)


def get_tickets(session: Session, store_id: str = "", product_id: str = "",
                types: list[str] | None = None, days: int = 30) -> list[dict]:
    today = business_today(session)
    start = (today - timedelta(days=days)).isoformat()
    items = cs_svc.list_tickets(session, store_id=store_id, product_id=product_id,
                                start=start, end=today.isoformat(), limit=10000)["items"]
    if types:
        items = [t for t in items if t["type"] in types]
    return items


def get_ticket_stats(session: Session, store_id: str, start: str, end: str) -> dict:
    return cs_svc.ticket_stats(session, store_id=store_id, start=start, end=end)


def get_campaigns(session: Session, active_between: tuple[str, str] | None = None) -> list[dict]:
    if active_between:
        s, e = active_between
        items = member_svc.list_campaigns(session, status="active", limit=1000)
        return [c for c in items if c["start_date"] <= e and c["end_date"] >= s]
    return member_svc.list_campaigns(session, limit=1000)


def get_weather_calendar(session: Session, city: str, start: str, end: str) -> dict:
    weather = session.exec(select(Weather).where(Weather.city == city,
                                                 Weather.biz_date >= start,
                                                 Weather.biz_date <= end)).all()
    cal = session.exec(select(CalendarDay).where(CalendarDay.biz_date >= start,
                                                 CalendarDay.biz_date <= end)).all()
    return {"weather": [w.model_dump() for w in weather],
            "calendar": [c.model_dump() for c in cal]}


def get_competitor_promo(session: Session, category_id: str, city: str,
                         start: str, end: str) -> list[dict]:
    rows = session.exec(select(CompetitorPromo).where(
        CompetitorPromo.category_id == category_id, CompetitorPromo.city == city,
        CompetitorPromo.biz_date >= start, CompetitorPromo.biz_date <= end)).all()
    return [c.model_dump() for c in rows]


def get_store_category_daily(session: Session, store_id: str, category_id: str,
                             start: str, end: str) -> list[dict]:
    """门店×品类 日销量聚合（竞品分流/品类趋势证据用）。"""
    from ..models import SalesOrder
    rows = session.exec(select(SalesOrder).where(
        SalesOrder.store_id == store_id, SalesOrder.category_id == category_id,
        SalesOrder.biz_date >= start, SalesOrder.biz_date <= end)).all()
    by_date: dict[str, int] = {}
    for r in rows:
        by_date[r.biz_date] = by_date.get(r.biz_date, 0) + r.qty
    return [{"date": d, "qty": q} for d, q in sorted(by_date.items())]


def get_product(session: Session, product_id: str) -> dict | None:
    return master_svc.get_product(session, product_id)


def get_store(session: Session, store_id: str) -> dict | None:
    return master_svc.get_store(session, store_id)


def get_member_repurchase(session: Session, store_id: str) -> dict:
    return member_svc.repurchase_rate(session, store_id)


def get_member_repurchase_prev(session: Session, store_id: str) -> dict | None:
    """当月 vs 上月复购率（会员流失假设验证）。"""
    rows = session.exec(select(MemberSegmentStat).where(
        MemberSegmentStat.store_id == store_id).order_by(MemberSegmentStat.month_start)).all()
    by_month: dict[str, dict] = {}
    for r in rows:
        agg = by_month.setdefault(r.month_start, {"active": 0, "rep": 0})
        agg["active"] += r.active_members
        agg["rep"] += r.repurchase_members
    months = sorted(by_month)
    if len(months) < 2:
        return None
    a, p = by_month[months[-1]], by_month[months[-2]]
    return {"month_start": months[-2],
            "prev_rate": round(p["rep"] / p["active"] * 100, 2) if p["active"] else None,
            "current_month": months[-1],
            "current_rate": round(a["rep"] / a["active"] * 100, 2) if a["active"] else None}


def get_baseline_mu(session: Session, store_id: str, product_id: str) -> float | None:
    row = session.exec(select(BaselineMu).where(BaselineMu.store_id == store_id,
                                                BaselineMu.product_id == product_id)).first()
    return row.mu if row else None


TOOL_REGISTRY = {
    "get_sales_timeseries": get_sales_timeseries,
    "get_inventory": get_inventory,
    "get_tickets": get_tickets,
    "get_campaigns": get_campaigns,
    "get_weather_calendar": get_weather_calendar,
    "get_competitor_promo": get_competitor_promo,
}
