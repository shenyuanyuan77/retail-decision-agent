# -*- coding: utf-8 -*-
"""会员 CRM 服务：会员/分层/复购查询 + 促销活动受控创建。"""
from sqlmodel import Session, select

from ..core import timeutil
from ..models import Campaign, Member, MemberSegmentStat
from ..governance.auth import Actor
from ..governance.idempotency import WriteDenied, controlled_write
from ..governance.policy import evaluate


def list_members(session: Session, *, segment: str = "", store_id: str = "",
                 limit: int = 100, offset: int = 0) -> dict:
    q = select(Member)
    if segment:
        q = q.where(Member.segment == segment)
    if store_id:
        q = q.where(Member.register_store_id == store_id)
    rows = session.exec(q.order_by(Member.id).offset(offset).limit(limit)).all()
    return {"total": len(rows), "items": [m.model_dump() for m in rows]}


def segment_stats(session: Session, *, store_id: str = "", month_start: str = "") -> list[dict]:
    q = select(MemberSegmentStat)
    if store_id:
        q = q.where(MemberSegmentStat.store_id == store_id)
    if month_start:
        q = q.where(MemberSegmentStat.month_start == month_start)
    return [s.model_dump() for s in session.exec(q.order_by(MemberSegmentStat.month_start,
                                                      MemberSegmentStat.store_id)).all()]


def repurchase_rate(session: Session, store_id: str) -> dict:
    """最近一个月复购率（评估层/诊断层数据源）。"""
    latest = session.exec(select(MemberSegmentStat.month_start)
                          .order_by(MemberSegmentStat.month_start.desc())).first()
    if not latest:
        return {"store_id": store_id, "month_start": "", "repurchase_rate": None}
    rows = session.exec(select(MemberSegmentStat).where(
        MemberSegmentStat.month_start == latest,
        MemberSegmentStat.store_id == store_id)).all()
    active = sum(r.active_members for r in rows)
    rep = sum(r.repurchase_members for r in rows)
    return {"store_id": store_id, "month_start": latest,
            "active_members": active, "repurchase_members": rep,
            "repurchase_rate": round(rep / active * 100, 2) if active else None}


def create_campaign(session: Session, actor: Actor | None, p: dict, trace_id: str = "") -> dict:
    """创建促销活动：折扣/预算阈值治理。"""
    pol = evaluate(actor, "promo", {"discount_pct": float(p.get("discount_pct", 0)),
                                    "budget": float(p.get("budget", 0))})
    if not pol.allowed:
        raise WriteDenied(f"治理拒绝促销: {pol.denied_reason}")
    if pol.requires_approval and not p.get("approved_by_approval_id"):
        raise WriteDenied(f"需人工审批后执行: {'; '.join(pol.reasons)}")

    def executor(s: Session) -> dict:
        c = Campaign(
            id=timeutil.new_id("cmp"), code=f"CMP{timeutil.new_id('')[0:8].upper()}",
            name=p["name"], type=p.get("type", "category"),
            store_ids=",".join(p.get("store_ids", [])),
            category_id=p.get("category_id", ""), product_ids=",".join(p.get("product_ids", [])),
            discount_pct=float(p.get("discount_pct", 0)), budget=float(p.get("budget", 0)),
            start_date=p.get("start_date", timeutil.business_today(s).isoformat()),
            end_date=p.get("end_date", ""),
            status=p.get("status", "active"),
            created_by=actor.username if actor else "anonymous",
            created_at=timeutil.now_iso(), idempotency_key=p.get("idempotency_key", ""),
        )
        s.add(c)
        s.commit()
        return {"id": c.id, "code": c.code, "name": c.name, "discount_pct": c.discount_pct,
                "budget": c.budget, "start_date": c.start_date, "status": c.status,
                "policy": pol.to_dict()}

    outcome = controlled_write(
        session, actor=actor, action="members.create_campaign", resource_type="campaign",
        scope="campaign", idempotency_key=p.get("idempotency_key", ""),
        dry_run=bool(p.get("dry_run")),
        payload={"name": p["name"], "discount_pct": p.get("discount_pct", 0),
                 "budget": p.get("budget", 0), "type": p.get("type", "category")},
        executor=executor,
        previewer=lambda s: {"name": p["name"], "would_create": True, "policy": pol.to_dict()},
        trace_id=trace_id, extra_audit={"policy": pol.to_dict()},
    )
    return outcome.payload | {"replayed": outcome.replayed, "dry_run": outcome.dry_run}


def list_campaigns(session: Session, *, status: str = "", active_on: str = "",
                   limit: int = 100) -> list[dict]:
    q = select(Campaign)
    if status:
        q = q.where(Campaign.status == status)
    if active_on:
        q = q.where(Campaign.start_date <= active_on,
                    Campaign.end_date >= active_on, Campaign.status == "active")
    return [c.model_dump() for c in session.exec(q.order_by(Campaign.created_at.desc())
                                           .limit(limit)).all()]
