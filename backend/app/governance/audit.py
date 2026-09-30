# -*- coding: utf-8 -*-
"""审计日志：所有决策与写入必须留痕（actor / action / resource / result / trace_id）。"""
import json

from sqlmodel import Session

from ..core import timeutil
from ..models import AuditLog
from .auth import Actor


def audit(
    session: Session,
    actor: Actor | None,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    detail: dict | None = None,
    result: str = "success",
    trace_id: str = "",
) -> AuditLog:
    biz_today = None
    try:
        biz_today = timeutil.business_today(session).isoformat()
    except Exception:
        biz_today = ""
    log = AuditLog(
        ts=timeutil.now_iso(),
        biz_date=biz_today,
        trace_id=trace_id,
        actor_type="agent" if (actor and actor.is_agent) else ("user" if actor else "system"),
        actor_id=actor.id if actor else "anonymous",
        actor_role=actor.role if actor else "anonymous",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        detail=json.dumps(detail or {}, ensure_ascii=False),
    )
    session.add(log)
    session.commit()
    return log
