# -*- coding: utf-8 -*-
"""销售服务（读）：日销售事实查询、时间序列、汇总。

sales_orders 粒度 store×product×day；channel=online/offline 通过 online_qty 拆分，
member 结构通过 member_qty 拆分（见 docs/03-data-and-anomalies.md 数据模型说明）。
"""
from sqlmodel import Session, select

from ..core.timeutil import business_today, parse_date
from ..models import SalesOrder


def query_daily(session: Session, *, store_id: str = "", product_id: str = "",
                category_id: str = "", start: str = "", end: str = "",
                channel: str = "", member_only: bool = False,
                limit: int = 1000, offset: int = 0) -> dict:
    today = business_today(session)
    q = select(SalesOrder)
    if store_id:
        q = q.where(SalesOrder.store_id == store_id)
    if product_id:
        q = q.where(SalesOrder.product_id == product_id)
    if category_id:
        q = q.where(SalesOrder.category_id == category_id)
    q = q.where(SalesOrder.biz_date >= (start or "0000-01-01"))
    q = q.where(SalesOrder.biz_date <= (end or today.isoformat()))
    if channel == "online":
        q = q.where(SalesOrder.online_qty > 0)
    elif channel == "offline":
        q = q.where(SalesOrder.qty > SalesOrder.online_qty)
    if member_only:
        q = q.where(SalesOrder.member_qty > 0)
    rows = session.exec(q.order_by(SalesOrder.biz_date, SalesOrder.id)
                        .offset(offset).limit(limit)).all()
    items = []
    for r in rows:
        d = r.model_dump()
        if channel == "online":
            d["qty"], d["amount"] = r.online_qty, round(r.unit_price * r.online_qty, 2)
        elif channel == "offline":
            off = r.qty - r.online_qty
            d["qty"], d["amount"] = off, round(r.unit_price * off, 2)
        if member_only:
            d["qty"], d["amount"] = min(r.member_qty, d["qty"]), round(r.unit_price * min(r.member_qty, d["qty"]), 2)
        items.append(d)
    return {"total": len(items), "items": items}


def timeseries(session: Session, *, store_id: str, product_id: str, days: int = 60,
               end: str = "") -> list[dict]:
    """感知层核心数据源：门店×SKU 日销量时间序列。"""
    from datetime import timedelta
    today = parse_date(end) if end else business_today(session)
    start = today - timedelta(days=days - 1)
    q = select(SalesOrder).where(
        SalesOrder.store_id == store_id, SalesOrder.product_id == product_id,
        SalesOrder.biz_date >= start.isoformat(), SalesOrder.biz_date <= today.isoformat(),
    ).order_by(SalesOrder.biz_date)
    rows = {r.biz_date: r for r in session.exec(q).all()}
    series = []
    d = start
    while d <= today:
        r = rows.get(d.isoformat())
        series.append({
            "date": d.isoformat(),
            "qty": r.qty if r else 0,
            "amount": round(r.amount, 2) if r else 0.0,
            "unit_price": round(r.unit_price, 2) if r else 0.0,
            "promo_flag": r.promo_flag if r else 0,
            "member_qty": r.member_qty if r else 0,
        })
        d += timedelta(days=1)
    return series


def summary(session: Session, *, start: str, end: str, store_id: str = "",
            category_id: str = "") -> dict:
    from sqlalchemy import func
    q = select(func.sum(SalesOrder.qty), func.sum(SalesOrder.amount),
               func.sum(SalesOrder.cost_amount), func.sum(SalesOrder.orders)).where(
        SalesOrder.biz_date >= start, SalesOrder.biz_date <= end)
    if store_id:
        q = q.where(SalesOrder.store_id == store_id)
    if category_id:
        q = q.where(SalesOrder.category_id == category_id)
    qty, amount, cost, orders = session.exec(q).one()
    qty = qty or 0
    amount = amount or 0.0
    cost = cost or 0.0
    orders = orders or 0
    return {
        "start": start, "end": end, "store_id": store_id, "category_id": category_id,
        "sales_amount": round(amount, 2), "sales_qty": qty, "orders": orders,
        "cost_amount": round(cost, 2),
        "gross_profit": round(amount - cost, 2),
        "gross_margin_rate": round((amount - cost) / amount * 100, 2) if amount else 0.0,
        "avg_daily_amount": round(amount / ((parse_date(end) - parse_date(start)).days + 1), 2),
    }
