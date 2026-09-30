# -*- coding: utf-8 -*-
"""世界 API：数据生成 / 异常注入 / 时间推演（演示与测试入口）。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ..bootstrap import bootstrap
from ..world.timemachine import advance_days
from .deps import get_session

world_router = APIRouter(prefix="/world", tags=["world-世界推演"])


class GenerateIn(BaseModel):
    days: int = 180
    stores: int = 50
    skus: int = 500
    seed: int = 42
    inject: bool = True


@world_router.post("/generate")
def api_generate(p: GenerateIn, session: Session = Depends(get_session)):
    return bootstrap(days=p.days, stores=p.stores, skus=p.skus, seed=p.seed, inject=p.inject)


class AdvanceIn(BaseModel):
    days: int = 7


@world_router.post("/advance")
def api_advance(p: AdvanceIn, session: Session = Depends(get_session)):
    return advance_days(session, p.days)


@world_router.get("/status")
def api_status(session: Session = Depends(get_session)):
    from ..core import timeutil
    from ..models import Storyline
    from sqlmodel import select
    today = timeutil.business_today(session)
    return {"today": today.isoformat(),
            "seed": timeutil.get_meta(session, "seed"),
            "horizon_days": timeutil.get_meta(session, "horizon_days"),
            "generated_at": timeutil.get_meta(session, "generated_at"),
            "storylines": [s.type for s in session.exec(select(Storyline)).all()]}


def register(app):
    from ..core import config
    app.include_router(world_router, prefix=config.API_PREFIX)
