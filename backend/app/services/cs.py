# -*- coding: utf-8 -*-
"""客服服务：工单查询统计 + 回访任务受控创建。"""
from sqlmodel import Session, select

from ..core import timeutil
from ..models import Ticket, TicketTask
from ..governance.auth import Actor
from ..governance.idempotency import WriteDenied, controlled_write
from ..governance.policy import evaluate


def list_tickets(session: Session, *, store_id: str = "", type: str = "", status: str = "",
                 product_id: str = "", start: str = "", end: str = "",
                 limit: int = 200, offset: int = 0) -> dict:
    q = select(Ticket)
    if store_id:
        q = q.where(Ticket.store_id == store_id)
    if type:
        q = q.where(Ticket.type == type)
    if status:
        q = q.where(Ticket.status == status)
    if product_id:
        q = q.where(Ticket.product_id == product_id)
    if start:
        q = q.where(Ticket.biz_date >= start)
    if end:
        q = q.where(Ticket.biz_date <= end)
    rows = session.exec(q.order_by(Ticket.biz_date.desc()).offset(offset).limit(limit)).all()
    return {"total": len(rows), "items": [t.model_dump() for t in rows]}


def ticket_stats(session: Session, *, store_id: str = "", start: str, end: str) -> dict:
    q = select(Ticket).where(Ticket.biz_date >= start, Ticket.biz_date <= end)
    if store_id:
        q = q.where(Ticket.store_id == store_id)
    rows = session.exec(q).all()
    by_type: dict[str, int] = {}
    for t in rows:
        by_type[t.type] = by_type.get(t.type, 0) + 1
    return {"start": start, "end": end, "store_id": store_id, "total": len(rows),
            "by_type": by_type,
            "unresolved": sum(1 for t in rows if t.status in ("open", "processing"))}


def create_ticket_task(session: Session, actor: Actor | None, p: dict,
                       trace_id: str = "") -> dict:
    pol = evaluate(actor, "cs_followup", {"task_type": p.get("type", "callback")})
    if not pol.allowed:
        raise WriteDenied(f"治理拒绝客服任务: {pol.denied_reason}")
    if pol.requires_approval and not p.get("approved_by_approval_id"):
        raise WriteDenied(f"需人工审批后执行: {'; '.join(pol.reasons)}")

    def executor(s: Session) -> dict:
        task = TicketTask(
            id=timeutil.new_id("tsk"), task_no=f"TSK{timeutil.new_id('')[0:8].upper()}",
            idempotency_key=p.get("idempotency_key", ""),
            store_id=p["store_id"], type=p.get("type", "callback"),
            ticket_id=p.get("ticket_id", ""), anomaly_id=p.get("anomaly_id", ""),
            assignee=p.get("assignee", "客服组"),
            due_date=p.get("due_date", ""), status="pending",
            created_by=actor.username if actor else "anonymous",
            created_at=timeutil.now_iso(), trace_id=trace_id,
        )
        s.add(task)
        s.commit()
        return {"id": task.id, "task_no": task.task_no, "store_id": task.store_id,
                "type": task.type, "status": task.status, "policy": pol.to_dict()}

    outcome = controlled_write(
        session, actor=actor, action="cs.create_ticket_task", resource_type="ticket_task",
        scope="ticket_task", idempotency_key=p.get("idempotency_key", ""),
        dry_run=bool(p.get("dry_run")),
        payload={"store_id": p["store_id"], "type": p.get("type", "callback")},
        executor=executor,
        previewer=lambda s: {"store_id": p["store_id"], "would_create": True,
                             "policy": pol.to_dict()},
        trace_id=trace_id, extra_audit={"policy": pol.to_dict()},
    )
    return outcome.payload | {"replayed": outcome.replayed, "dry_run": outcome.dry_run}


def list_ticket_tasks(session: Session, *, store_id: str = "", status: str = "",
                      limit: int = 100) -> list[dict]:
    q = select(TicketTask)
    if store_id:
        q = q.where(TicketTask.store_id == store_id)
    if status:
        q = q.where(TicketTask.status == status)
    return [t.model_dump() for t in session.exec(q.order_by(TicketTask.created_at.desc())
                                           .limit(limit)).all()]
