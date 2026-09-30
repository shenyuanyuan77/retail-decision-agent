# -*- coding: utf-8 -*-
"""六大 Mock 业务系统路由：主数据 / 销售 / 库存供应链 / 会员CRM / 客服 / 外部数据。

所有写接口均支持 idempotency_key + dry_run，经 Policy 校验并写审计日志。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ..governance.auth import Actor
from ..governance.idempotency import WriteDenied
from ..services import cs as cs_svc
from ..services import external as ext_svc
from ..services import inventory as inv_svc
from ..services import master as master_svc
from ..services import members as member_svc
from ..services import sales as sales_svc
from .deps import get_actor, get_session

master_router = APIRouter(prefix="/master", tags=["master-主数据服务"])
sales_router = APIRouter(prefix="/sales", tags=["sales-销售服务"])
inventory_router = APIRouter(prefix="/inventory", tags=["inventory-库存供应链服务"])
members_router = APIRouter(prefix="/members", tags=["members-会员CRM服务"])
cs_router = APIRouter(prefix="/cs", tags=["cs-客服服务"])
external_router = APIRouter(prefix="/external", tags=["external-外部数据服务"])


# ---------------- 主数据 ----------------
@master_router.get("/regions")
def regions(session: Session = Depends(get_session)):
    return {"items": master_svc.list_regions(session)}


@master_router.get("/stores")
def stores(region_id: str = "", tier: str = "", session: Session = Depends(get_session)):
    return {"items": master_svc.list_stores(session, region_id, tier)}


@master_router.get("/stores/{store_id}")
def store_detail(store_id: str, session: Session = Depends(get_session)):
    s = master_svc.get_store(session, store_id)
    if not s:
        raise HTTPException(404, "门店不存在")
    return s


@master_router.get("/categories")
def categories(session: Session = Depends(get_session)):
    return {"items": master_svc.list_categories(session)}


@master_router.get("/products")
def products(category_id: str = "", keyword: str = "", limit: int = 100,
             offset: int = 0, session: Session = Depends(get_session)):
    return master_svc.list_products(session, category_id, keyword, limit, offset)


@master_router.get("/products/{product_id}")
def product_detail(product_id: str, session: Session = Depends(get_session)):
    p = master_svc.get_product(session, product_id)
    if not p:
        raise HTTPException(404, "商品不存在")
    return p


@master_router.get("/suppliers")
def suppliers(session: Session = Depends(get_session)):
    return {"items": master_svc.list_suppliers(session)}


# ---------------- 销售 ----------------
@sales_router.get("/daily")
def sales_daily(store_id: str = "", product_id: str = "", category_id: str = "",
                start: str = "", end: str = "", channel: str = "",
                member_only: bool = False, limit: int = 1000, offset: int = 0,
                session: Session = Depends(get_session)):
    return sales_svc.query_daily(session, store_id=store_id, product_id=product_id,
                                 category_id=category_id, start=start, end=end,
                                 channel=channel, member_only=member_only,
                                 limit=limit, offset=offset)


@sales_router.get("/timeseries")
def sales_timeseries(store_id: str, product_id: str, days: int = 60, end: str = "",
                     session: Session = Depends(get_session)):
    return {"store_id": store_id, "product_id": product_id,
            "items": sales_svc.timeseries(session, store_id=store_id,
                                          product_id=product_id, days=days, end=end)}


@sales_router.get("/summary")
def sales_summary(start: str, end: str, store_id: str = "", category_id: str = "",
                  session: Session = Depends(get_session)):
    return sales_svc.summary(session, start=start, end=end, store_id=store_id,
                             category_id=category_id)


# ---------------- 库存供应链 ----------------
@inventory_router.get("")
def inventory_query(store_id: str = "", product_id: str = "", below_safety: bool = False,
                    out_of_stock: bool = False, limit: int = 200, offset: int = 0,
                    session: Session = Depends(get_session)):
    return inv_svc.query_inventory(session, store_id=store_id, product_id=product_id,
                                   below_safety=below_safety, out_of_stock=out_of_stock,
                                   limit=limit, offset=offset)


class ReplenishIn(BaseModel):
    store_id: str
    product_id: str
    qty: int
    idempotency_key: str = ""
    dry_run: bool = False
    note: str = ""
    approved_by_approval_id: str = ""


@inventory_router.post("/replenishments")
def create_replenishment(p: ReplenishIn, session: Session = Depends(get_session),
                         actor: Actor = Depends(get_actor)):
    try:
        return inv_svc.create_replenishment(session, actor, p.model_dump())
    except WriteDenied as e:
        raise HTTPException(e.status_code, e.reason)


@inventory_router.get("/replenishments")
def replenishments(store_id: str = "", status: str = "", limit: int = 100,
                   session: Session = Depends(get_session)):
    return {"items": inv_svc.list_replenishments(session, store_id=store_id, status=status,
                                                 limit=limit)}


class TransferIn(BaseModel):
    from_store_id: str
    to_store_id: str
    product_id: str
    qty: int
    idempotency_key: str = ""
    dry_run: bool = False
    note: str = ""
    approved_by_approval_id: str = ""


@inventory_router.post("/transfers")
def create_transfer(p: TransferIn, session: Session = Depends(get_session),
                    actor: Actor = Depends(get_actor)):
    try:
        return inv_svc.create_transfer(session, actor, p.model_dump())
    except WriteDenied as e:
        raise HTTPException(e.status_code, e.reason)


@inventory_router.get("/transfers")
def transfers(store_id: str = "", limit: int = 100, session: Session = Depends(get_session)):
    return {"items": inv_svc.list_transfers(session, store_id=store_id, limit=limit)}


@inventory_router.post("/replenishments/{order_id}/compensate")
def compensate_replen(order_id: str, session: Session = Depends(get_session),
                      actor: Actor = Depends(get_actor)):
    try:
        return inv_svc.compensate_replenishment(session, order_id, actor)
    except WriteDenied as e:
        raise HTTPException(e.status_code, e.reason)


@inventory_router.post("/transfers/{order_id}/compensate")
def compensate_transfer(order_id: str, session: Session = Depends(get_session),
                        actor: Actor = Depends(get_actor)):
    try:
        return inv_svc.compensate_transfer(session, order_id, actor)
    except WriteDenied as e:
        raise HTTPException(e.status_code, e.reason)


# ---------------- 会员 CRM ----------------
@members_router.get("")
def members(segment: str = "", store_id: str = "", limit: int = 100, offset: int = 0,
            session: Session = Depends(get_session)):
    return member_svc.list_members(session, segment=segment, store_id=store_id,
                                   limit=limit, offset=offset)


@members_router.get("/segments")
def member_segments(store_id: str = "", month_start: str = "",
                    session: Session = Depends(get_session)):
    return {"items": member_svc.segment_stats(session, store_id=store_id,
                                              month_start=month_start)}


@members_router.get("/repurchase")
def repurchase(store_id: str, session: Session = Depends(get_session)):
    return member_svc.repurchase_rate(session, store_id)


class CampaignIn(BaseModel):
    name: str
    type: str = "category"
    store_ids: list[str] = []
    category_id: str = ""
    product_ids: list[str] = []
    discount_pct: float = 0.0
    budget: float = 0.0
    start_date: str = ""
    end_date: str = ""
    idempotency_key: str = ""
    dry_run: bool = False
    approved_by_approval_id: str = ""


@members_router.post("/campaigns")
def create_campaign(p: CampaignIn, session: Session = Depends(get_session),
                    actor: Actor = Depends(get_actor)):
    try:
        return member_svc.create_campaign(session, actor, p.model_dump())
    except WriteDenied as e:
        raise HTTPException(e.status_code, e.reason)


@members_router.get("/campaigns")
def campaigns(status: str = "", active_on: str = "", limit: int = 100,
              session: Session = Depends(get_session)):
    return {"items": member_svc.list_campaigns(session, status=status, active_on=active_on,
                                               limit=limit)}


# ---------------- 客服 ----------------
@cs_router.get("/tickets")
def tickets(store_id: str = "", type: str = "", status: str = "", product_id: str = "",
            start: str = "", end: str = "", limit: int = 200, offset: int = 0,
            session: Session = Depends(get_session)):
    return cs_svc.list_tickets(session, store_id=store_id, type=type, status=status,
                               product_id=product_id, start=start, end=end,
                               limit=limit, offset=offset)


@cs_router.get("/tickets/stats")
def tickets_stats(store_id: str = "", start: str = "", end: str = "",
                  session: Session = Depends(get_session)):
    from ..core.timeutil import business_today
    from datetime import timedelta
    today = business_today(session)
    end = end or today.isoformat()
    start = start or (today - timedelta(days=13)).isoformat()
    return cs_svc.ticket_stats(session, store_id=store_id, start=start, end=end)


class TaskIn(BaseModel):
    store_id: str
    type: str = "callback"
    ticket_id: str = ""
    anomaly_id: str = ""
    assignee: str = "客服组"
    due_date: str = ""
    idempotency_key: str = ""
    dry_run: bool = False
    approved_by_approval_id: str = ""


@cs_router.post("/tasks")
def create_task(p: TaskIn, session: Session = Depends(get_session),
                actor: Actor = Depends(get_actor)):
    try:
        return cs_svc.create_ticket_task(session, actor, p.model_dump())
    except WriteDenied as e:
        raise HTTPException(e.status_code, e.reason)


@cs_router.get("/tasks")
def tasks(store_id: str = "", status: str = "", limit: int = 100,
          session: Session = Depends(get_session)):
    return {"items": cs_svc.list_ticket_tasks(session, store_id=store_id, status=status,
                                              limit=limit)}


# ---------------- 外部数据 ----------------
@external_router.get("/weather")
def weather(city: str = "", start: str = "", end: str = "", limit: int = 400,
            session: Session = Depends(get_session)):
    return {"items": ext_svc.get_weather(session, city=city, start=start, end=end, limit=limit)}


@external_router.get("/competitor-promos")
def competitor_promos(category_id: str = "", city: str = "", start: str = "", end: str = "",
                      limit: int = 400, session: Session = Depends(get_session)):
    return {"items": ext_svc.get_competitor_promos(session, category_id=category_id, city=city,
                                                   start=start, end=end, limit=limit)}


@external_router.get("/calendar")
def calendar(start: str = "", end: str = "", session: Session = Depends(get_session)):
    return {"items": ext_svc.get_calendar(session, start=start, end=end)}


ALL_BUSINESS_ROUTERS = [master_router, sales_router, inventory_router, members_router,
                        cs_router, external_router]
