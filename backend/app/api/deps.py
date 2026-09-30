# -*- coding: utf-8 -*-
"""FastAPI 依赖：会话与身份。"""
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from ..core.db import get_session
from ..governance.auth import Actor, resolve_actor


def db_session():
    return Depends(get_session)


def get_actor(x_auth_token: str | None = Header(default=None, alias="X-Auth-Token"),
              session: Session = Depends(get_session)) -> Actor | None:
    actor = resolve_actor(session, x_auth_token)
    if x_auth_token and actor is None:
        raise HTTPException(status_code=401, detail="无效的 X-Auth-Token")
    return actor


def require_actor(actor: Actor | None = Depends(get_actor)) -> Actor:
    if actor is None:
        raise HTTPException(status_code=401, detail="写操作需要 X-Auth-Token 身份")
    return actor
