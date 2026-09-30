# -*- coding: utf-8 -*-
"""主数据服务表：regions / stores / categories / products / suppliers。"""
from sqlmodel import Field, SQLModel


class Region(SQLModel, table=True):
    id: str = Field(primary_key=True)
    code: str = Field(index=True)
    name: str


class Store(SQLModel, table=True):
    id: str = Field(primary_key=True)
    code: str = Field(index=True)
    name: str
    region_id: str = Field(index=True)
    city: str
    tier: str  # flagship / large / standard
    open_date: str
    status: str = "active"


class Category(SQLModel, table=True):
    id: str = Field(primary_key=True)
    code: str = Field(index=True)
    name: str


class Supplier(SQLModel, table=True):
    id: str = Field(primary_key=True)
    code: str
    name: str
    rating: float = 3.5
    region_id: str = ""


class Product(SQLModel, table=True):
    id: str = Field(primary_key=True)
    sku: str = Field(index=True)
    name: str
    category_id: str = Field(index=True)
    brand: str = ""
    unit: str = "件"
    cost_price: float
    list_price: float
    shelf_life_days: int | None = None  # None=非保质期商品
    supplier_id: str = ""
    moq: int = 10               # 最小起订量
    lead_time_days: int = 3     # 供应商交期
    safety_stock_default: int = 20
    status: str = "active"
