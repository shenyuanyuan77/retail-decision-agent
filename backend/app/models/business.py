# -*- coding: utf-8 -*-
"""业务系统表：销售 / 库存供应链 / 会员CRM / 客服 / 外部数据。

sales_orders 粒度：store × product × day（含渠道与会员结构拆分列），
支持按门店、SKU、日期、渠道(online/offline)、会员结构(member_qty)查询。
"""
from sqlalchemy import Column, Index, JSON
from sqlmodel import Field, SQLModel


class SalesOrder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    biz_date: str = Field(index=True)
    store_id: str = Field(index=True)
    product_id: str = Field(index=True)
    category_id: str = ""
    qty: int = 0                  # 当日销量
    amount: float = 0.0           # 当日销售额
    unit_price: float = 0.0       # 加权均价
    cost_amount: float = 0.0      # 销售成本
    orders: int = 0               # 订单数
    member_qty: int = 0           # 会员购买件数
    online_qty: int = 0           # 线上渠道件数
    promo_flag: int = 0           # 是否促销日
    campaign_id: str = ""         # 关联促销活动


class Campaign(SQLModel, table=True):
    """促销活动（会员 CRM 域），写入受治理层控制。"""
    id: str = Field(primary_key=True)
    code: str = Field(index=True)
    name: str
    type: str = "category"        # member_day / category / near_expiry / churn / coupon
    store_ids: str = ""           # 逗号分隔
    category_id: str = ""
    product_ids: str = ""
    discount_pct: float = 0.0
    budget: float = 0.0
    cost_actual: float = 0.0
    start_date: str = Field(index=True)
    end_date: str
    status: str = "active"        # draft/active/ended/cancelled
    created_by: str = ""
    created_at: str = ""
    idempotency_key: str = Field(default="", index=True)


class Inventory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    store_id: str = Field(index=True)
    product_id: str = Field(index=True)
    on_hand: int = 0
    in_transit: int = 0
    safety_stock: int = 0
    expiry_date: str = ""         # 批次到期日（保质期商品）
    updated_at: str = ""


class ReplenishmentOrder(SQLModel, table=True):
    id: str = Field(primary_key=True)
    order_no: str = Field(index=True)
    idempotency_key: str = Field(index=True)
    store_id: str
    product_id: str
    supplier_id: str = ""
    qty: int
    unit_cost: float = 0.0
    amount: float = 0.0
    status: str = "confirmed"     # confirmed / cancelled / compensated / arrived
    dry_run: int = 0
    arrive_date: str = ""         # 预计到货日（下单日+交期）
    note: str = ""
    created_by: str = ""
    created_at: str
    trace_id: str = Field(default="", index=True)


class TransferOrder(SQLModel, table=True):
    id: str = Field(primary_key=True)
    order_no: str = Field(index=True)
    idempotency_key: str = Field(index=True)
    from_store_id: str
    to_store_id: str
    product_id: str
    qty: int
    status: str = "done"          # done / compensated / cancelled
    dry_run: int = 0
    note: str = ""
    created_by: str = ""
    created_at: str
    trace_id: str = Field(default="", index=True)


class Member(SQLModel, table=True):
    id: str = Field(primary_key=True)
    code: str = Field(index=True)
    name: str
    phone_masked: str = ""
    segment: str = "normal"       # vip / high / normal / new
    register_store_id: str = Field(index=True)
    register_date: str
    status: str = "active"


class MemberSegmentStat(SQLModel, table=True):
    """月度会员分层与复购统计（评估层计算 member_repurchase_rate 的数据源）。"""
    id: int | None = Field(default=None, primary_key=True)
    store_id: str = Field(index=True)
    month_start: str = Field(index=True)
    segment: str
    members: int = 0
    active_members: int = 0
    repurchase_members: int = 0


class Ticket(SQLModel, table=True):
    id: str = Field(primary_key=True)
    ticket_no: str = Field(index=True)
    biz_date: str = Field(index=True)
    store_id: str = Field(index=True)
    product_id: str = ""
    type: str = "service"         # quality / expiry / stockout / service / delivery
    severity: str = "normal"      # normal / high
    status: str = "open"          # open / processing / resolved / closed
    member_id: str = ""
    description: str = ""


class TicketTask(SQLModel, table=True):
    id: str = Field(primary_key=True)
    task_no: str = Field(index=True)
    idempotency_key: str = Field(index=True)
    store_id: str
    type: str = "callback"        # callback / investigate / compensation_review
    ticket_id: str = ""
    anomaly_id: str = ""
    assignee: str = "客服组"
    status: str = "pending"       # pending / done / cancelled / compensated
    dry_run: int = 0
    due_date: str = ""
    result_note: str = ""
    created_by: str = ""
    created_at: str
    trace_id: str = Field(default="", index=True)


class Weather(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    biz_date: str = Field(index=True)
    city: str = Field(index=True)
    condition: str = "sunny"      # sunny / overcast / rain / storm / cold_wave / hot
    temp_high: float = 0.0
    temp_low: float = 0.0
    precip_mm: float = 0.0


class CompetitorPromo(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    biz_date: str = Field(index=True)
    competitor_name: str
    category_id: str = Field(index=True)
    city: str = ""
    discount_pct: float = 0.0
    note: str = ""


class CalendarDay(SQLModel, table=True):
    biz_date: str = Field(primary_key=True)
    is_weekend: int = 0
    is_holiday: int = 0
    holiday_name: str = ""
    is_member_day: int = 0        # 每月 18 日会员日


class BaselineMu(SQLModel, table=True):
    """门店×商品 基线日需求 μ（世界推演器复用生成器的因果模型）。"""
    id: int | None = Field(default=None, primary_key=True)
    store_id: str = Field(index=True)
    product_id: str = Field(index=True)
    mu: float = 0.0
