# -*- coding: utf-8 -*-
"""主数据服务（读）。"""
from sqlmodel import Session, select

from ..models import Category, Product, Region, Store, Supplier


def list_regions(session: Session) -> list[dict]:
    return [r.model_dump() for r in session.exec(select(Region).order_by(Region.id)).all()]


def list_stores(session: Session, region_id: str = "", tier: str = "") -> list[dict]:
    q = select(Store).where(Store.status == "active")
    if region_id:
        q = q.where(Store.region_id == region_id)
    if tier:
        q = q.where(Store.tier == tier)
    return [s.model_dump() for s in session.exec(q.order_by(Store.id)).all()]


def get_store(session: Session, store_id: str) -> dict | None:
    s = session.get(Store, store_id)
    return s.model_dump() if s else None


def list_categories(session: Session) -> list[dict]:
    return [c.model_dump() for c in session.exec(select(Category).order_by(Category.id)).all()]


def list_products(session: Session, category_id: str = "", keyword: str = "",
                  limit: int = 100, offset: int = 0) -> dict:
    q = select(Product).where(Product.status == "active")
    if category_id:
        q = q.where(Product.category_id == category_id)
    if keyword:
        q = q.where(Product.name.contains(keyword))
    items = session.exec(q.order_by(Product.id).offset(offset).limit(limit)).all()
    total = len(session.exec(q).all())
    return {"total": total, "items": [p.model_dump() for p in items]}


def get_product(session: Session, product_id: str) -> dict | None:
    p = session.get(Product, product_id)
    return p.model_dump() if p else None


def list_suppliers(session: Session) -> list[dict]:
    return [s.model_dump() for s in session.exec(select(Supplier).order_by(Supplier.id)).all()]
