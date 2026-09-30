# -*- coding: utf-8 -*-
"""业务时间：系统使用 meta 表中的 today 作为"业务今天"，支持时间推演（T+N 复盘）。"""
import datetime as dt
import uuid
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from . import config


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def get_meta(session: Session, key: str, default=None):
    from ..models import MetaKV
    row = session.get(MetaKV, key)
    return row.value if row else default


def set_meta(session: Session, key: str, value: str):
    from ..models import MetaKV
    row = session.get(MetaKV, key)
    if row:
        row.value = value
    else:
        row = MetaKV(key=key, value=value)
        session.add(row)


def business_today(session: Session) -> date:
    """业务今天：由数据生成器写入 meta.today；未初始化时回退系统日期。"""
    v = get_meta(session, "today")
    if v:
        return date.fromisoformat(v)
    return date.today()


def advance_business_today(session: Session, days: int) -> date:
    d = business_today(session) + timedelta(days=days)
    set_meta(session, "today", d.isoformat())
    return d


def parse_date(s) -> date:
    return s if isinstance(s, date) else date.fromisoformat(str(s))


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def iso(d) -> str:
    return d.isoformat() if isinstance(d, (date, datetime)) else str(d)
