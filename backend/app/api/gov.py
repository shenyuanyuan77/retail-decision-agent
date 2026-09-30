# -*- coding: utf-8 -*-
"""治理 API：审批中心 / 审计日志查询 / 权限矩阵。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..governance.approvals import decide_approval
from ..governance.auth import Actor, LEVEL_NAMES, ROLE_MAX_LEVEL
from ..governance.idempotency import WriteDenied
from ..models import Approval, AuditLog
from .deps import get_actor, get_session, require_actor

gov_router = APIRouter(prefix="/gov", tags=["governance-治理层"])


@gov_router.get("/approvals")
def list_approvals(status: str = "", limit: int = 100,
                   session: Session = Depends(get_session)):
    q = select(Approval)
    if status:
        q = q.where(Approval.status == status)
    rows = session.exec(q.order_by(Approval.requested_at.desc()).limit(limit)).all()
    items = []
    for a in rows:
        d = a.model_dump()
        d["risk_reasons"] = json.loads(a.risk_reasons or "[]")
        items.append(d)
    return {"items": items}


class ApprovalDecisionIn(BaseModel):
    decision: str          # approve / reject
    note: str = ""


@gov_router.post("/approvals/{approval_id}/decide")
def decide(approval_id: str, p: ApprovalDecisionIn,
           session: Session = Depends(get_session), actor: Actor = Depends(require_actor)):
    try:
        ap = decide_approval(session, approval_id, p.decision, actor, p.note)
    except WriteDenied as e:
        raise HTTPException(e.status_code, e.reason)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return ap.model_dump()


@gov_router.get("/audit-logs")
def audit_logs(trace_id: str = "", actor_id: str = "", action: str = "",
               resource_type: str = "", result: str = "", limit: int = 200,
               session: Session = Depends(get_session)):
    q = select(AuditLog)
    if trace_id:
        q = q.where(AuditLog.trace_id == trace_id)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if action:
        q = q.where(AuditLog.action.contains(action))
    if resource_type:
        q = q.where(AuditLog.resource_type == resource_type)
    if result:
        q = q.where(AuditLog.result == result)
    rows = session.exec(q.order_by(AuditLog.id.desc()).limit(limit)).all()
    items = []
    for r in rows:
        d = r.model_dump()
        try:
            d["detail"] = json.loads(r.detail or "{}")
        except Exception:
            d["detail"] = {"raw": r.detail}
        items.append(d)
    return {"items": items}


@gov_router.get("/permission-matrix")
def permission_matrix():
    return {
        "levels": LEVEL_NAMES,
        "role_max_level": ROLE_MAX_LEVEL,
        "rules": {
            "discount_gt_10_pct": "促销折扣>10% 必须审批",
            "budget_gt_10k": "促销/触达预算>1万 必须审批",
            "price_change": "价格变更必须审批",
            "cross_region_transfer": "跨区域调拨必须审批",
            "discount_gt_30_pct": "折扣>30% 禁止（L4）",
            "budget_gt_100k": "预算>10万 禁止（L4）",
            "agent_max_L2": "Agent 自动执行上限 L2，L3 一律转审批",
        },
    }
