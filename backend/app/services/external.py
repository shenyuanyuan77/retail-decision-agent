# -*- coding: utf-8 -*-
"""外部数据服务（读）：天气 / 竞品促销 / 电商日历。"""
from sqlmodel import Session, select

from ..models import CalendarDay, CompetitorPromo, Weather


def get_weather(session: Session, *, city: str = "", start: str = "", end: str = "",
                limit: int = 400) -> list[dict]:
    q = select(Weather)
    if city:
        q = q.where(Weather.city == city)
    if start:
        q = q.where(Weather.biz_date >= start)
    if end:
        q = q.where(Weather.biz_date <= end)
    return [w.model_dump() for w in session.exec(q.order_by(Weather.biz_date).limit(limit)).all()]


def get_competitor_promos(session: Session, *, category_id: str = "", city: str = "",
                          start: str = "", end: str = "", limit: int = 400) -> list[dict]:
    q = select(CompetitorPromo)
    if category_id:
        q = q.where(CompetitorPromo.category_id == category_id)
    if city:
        q = q.where(CompetitorPromo.city == city)
    if start:
        q = q.where(CompetitorPromo.biz_date >= start)
    if end:
        q = q.where(CompetitorPromo.biz_date <= end)
    return [c.model_dump() for c in session.exec(q.order_by(CompetitorPromo.biz_date)
                                           .limit(limit)).all()]


def get_calendar(session: Session, *, start: str = "", end: str = "") -> list[dict]:
    q = select(CalendarDay)
    if start:
        q = q.where(CalendarDay.biz_date >= start)
    if end:
        q = q.where(CalendarDay.biz_date <= end)
    return [c.model_dump() for c in session.exec(q.order_by(CalendarDay.biz_date)).all()]
