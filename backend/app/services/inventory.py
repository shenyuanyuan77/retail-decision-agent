# -*- coding: utf-8 -*-
"""库存与供应链服务：查库存 / 补货 / 调拨（受控写入：幂等 + dry-run + 审计 + Policy 校验 + 补偿）。"""
import json
from datetime import timedelta

from sqlmodel import Session, select

from ..core import timeutil
from ..models import Inventory, Product, ReplenishmentOrder, Store, TransferOrder
from ..governance.auth import Actor, check_data_scope
from ..governance.idempotency import WriteDenied, controlled_write
from ..governance.policy import evaluate
from . import master as master_svc


def query_inventory(session: Session, *, store_id: str = "", product_id: str = "",
                    below_safety: bool = False, out_of_stock: bool = False,
                    limit: int = 200, offset: int = 0) -> dict:
    q = select(Inventory)
    if store_id:
        q = q.where(Inventory.store_id == store_id)
    if product_id:
        q = q.where(Inventory.product_id == product_id)
    if below_safety:
        q = q.where(Inventory.on_hand <= Inventory.safety_stock)
    if out_of_stock:
        q = q.where(Inventory.on_hand == 0)
    rows = session.exec(q.order_by(Inventory.id).offset(offset).limit(limit)).all()
    return {"total": len(rows), "items": [r.model_dump() for r in rows]}


def get_inventory(session: Session, store_id: str, product_id: str) -> dict | None:
    row = session.exec(select(Inventory).where(
        Inventory.store_id == store_id, Inventory.product_id == product_id)).first()
    return row.model_dump() if row else None


def _norm_replenish(session: Session, p: dict) -> dict:
    store = session.get(Store, p["store_id"])
    product = session.get(Product, p["product_id"])
    if not store or not product:
        raise WriteDenied("门店或商品不存在", status_code=400)
    qty = int(p["qty"])
    if qty <= 0:
        raise WriteDenied("补货数量必须大于 0", status_code=400)
    amount = round(qty * product.cost_price, 2)
    return {"store": store, "product": product, "qty": qty, "amount": amount}


def create_replenishment(session: Session, actor: Actor | None, p: dict,
                         trace_id: str = "") -> dict:
    """创建补货单：policy 评估 → controlled_write。低风险金额阈值 1 万。"""
    ok, msg = check_data_scope(actor, p.get("store_id", ""))
    if not ok:
        raise WriteDenied(msg)
    norm = _norm_replenish(session, p)
    store, product, qty, amount = norm["store"], norm["product"], norm["qty"], norm["amount"]

    pol = evaluate(actor, "replenish", {"amount": amount})
    if not pol.allowed:
        raise WriteDenied(f"治理拒绝补货: {pol.denied_reason}")
    # 业务约束：MOQ 最小起订量（违反则拒绝并给出依据）
    if qty < product.moq:
        raise WriteDenied(f"低于供应商最小起订量 MOQ={product.moq}", status_code=400)
    if pol.requires_approval and not p.get("approved_by_approval_id"):
        raise WriteDenied(f"需人工审批后执行: {'; '.join(pol.reasons)} 或提供 approved_by_approval_id")

    def executor(s: Session) -> dict:
        today = timeutil.business_today(s)
        order = ReplenishmentOrder(
            id=timeutil.new_id("rpl"), order_no=f"RPL{timeutil.new_id('')[0:10].upper()}",
            idempotency_key=p.get("idempotency_key", ""),
            store_id=store.id, product_id=product.id, supplier_id=product.supplier_id,
            qty=qty, unit_cost=product.cost_price, amount=amount, status="confirmed",
            arrive_date=(today + timedelta(days=product.lead_time_days)).isoformat(),
            note=p.get("note", ""), created_by=actor.username if actor else "anonymous",
            created_at=timeutil.now_iso(), trace_id=trace_id,
        )
        s.add(order)
        inv = s.exec(select(Inventory).where(Inventory.store_id == store.id,
                                             Inventory.product_id == product.id)).first()
        if inv:
            inv.in_transit += qty
            inv.updated_at = timeutil.now_iso()
            s.add(inv)
        s.commit()
        return {"id": order.id, "order_no": order.order_no, "store_id": store.id,
                "product_id": product.id, "qty": qty, "amount": amount,
                "arrive_date": order.arrive_date, "status": order.status,
                "policy": pol.to_dict()}

    outcome = controlled_write(
        session, actor=actor, action="inventory.create_replenishment",
        resource_type="replenishment_order", scope="replenish",
        idempotency_key=p.get("idempotency_key", ""), dry_run=bool(p.get("dry_run")),
        payload={"store_id": store.id, "product_id": product.id, "qty": qty},
        executor=executor,
        previewer=lambda s: {"store_id": store.id, "product_id": product.id, "qty": qty,
                             "amount": amount, "would_add_in_transit": qty,
                             "policy": pol.to_dict()},
        trace_id=trace_id,
        extra_audit={"policy": pol.to_dict()},
    )
    return outcome.payload | {"replayed": outcome.replayed, "dry_run": outcome.dry_run}


def _norm_transfer(session: Session, p: dict) -> dict:
    src, dst = session.get(Store, p["from_store_id"]), session.get(Store, p["to_store_id"])
    product = session.get(Product, p["product_id"])
    if not src or not dst or not product:
        raise WriteDenied("门店或商品不存在", status_code=400)
    if src.id == dst.id:
        raise WriteDenied("调出与调入门店不能相同", status_code=400)
    qty = int(p["qty"])
    if qty <= 0:
        raise WriteDenied("调拨数量必须大于 0", status_code=400)
    inv = session.exec(select(Inventory).where(Inventory.store_id == src.id,
                                               Inventory.product_id == product.id)).first()
    if not inv or inv.on_hand < qty:
        have = inv.on_hand if inv else 0
        raise WriteDenied(f"调出门店库存不足: 可用 {have}, 需要 {qty}", status_code=400)
    return {"src": src, "dst": dst, "product": product, "inv": inv, "qty": qty,
            "amount": round(qty * product.cost_price, 2),
            "cross_region": src.region_id != dst.region_id}


def create_transfer(session: Session, actor: Actor | None, p: dict, trace_id: str = "") -> dict:
    ok, msg = check_data_scope(actor, p.get("from_store_id", ""))
    if not ok:
        raise WriteDenied(msg)
    norm = _norm_transfer(session, p)
    src, dst, product, qty = norm["src"], norm["dst"], norm["product"], norm["qty"]

    pol = evaluate(actor, "transfer", {"amount": norm["amount"], "cross_region": norm["cross_region"]})
    if not pol.allowed:
        raise WriteDenied(f"治理拒绝调拨: {pol.denied_reason}")
    if pol.requires_approval and not p.get("approved_by_approval_id"):
        raise WriteDenied(f"需人工审批后执行: {'; '.join(pol.reasons)}")

    def executor(s: Session) -> dict:
        order = TransferOrder(
            id=timeutil.new_id("trf"), order_no=f"TRF{timeutil.new_id('')[0:10].upper()}",
            idempotency_key=p.get("idempotency_key", ""),
            from_store_id=src.id, to_store_id=dst.id, product_id=product.id, qty=qty,
            status="done", created_by=actor.username if actor else "anonymous",
            created_at=timeutil.now_iso(), note=p.get("note", ""), trace_id=trace_id,
        )
        s.add(order)
        src_inv = norm["inv"]
        src_inv.on_hand -= qty
        src_inv.updated_at = timeutil.now_iso()
        s.add(src_inv)
        dst_inv = s.exec(select(Inventory).where(Inventory.store_id == dst.id,
                                                 Inventory.product_id == product.id)).first()
        if dst_inv:
            dst_inv.on_hand += qty
            dst_inv.updated_at = timeutil.now_iso()
            s.add(dst_inv)
        s.commit()
        return {"id": order.id, "order_no": order.order_no, "from_store_id": src.id,
                "to_store_id": dst.id, "product_id": product.id, "qty": qty,
                "cross_region": norm["cross_region"], "status": order.status,
                "policy": pol.to_dict()}

    outcome = controlled_write(
        session, actor=actor, action="inventory.create_transfer",
        resource_type="transfer_order", scope="transfer",
        idempotency_key=p.get("idempotency_key", ""), dry_run=bool(p.get("dry_run")),
        payload={"from_store_id": src.id, "to_store_id": dst.id, "product_id": product.id, "qty": qty},
        executor=executor,
        previewer=lambda s: {"from_store_id": src.id, "to_store_id": dst.id,
                             "product_id": product.id, "qty": qty, "amount": norm["amount"],
                             "cross_region": norm["cross_region"], "policy": pol.to_dict()},
        trace_id=trace_id, extra_audit={"policy": pol.to_dict()},
    )
    return outcome.payload | {"replayed": outcome.replayed, "dry_run": outcome.dry_run}


def compensate_replenishment(session: Session, order_id: str, actor: Actor | None,
                             trace_id: str = "") -> dict:
    """补偿：取消补货单并回退在途库存。"""
    order = session.get(ReplenishmentOrder, order_id)
    if not order:
        raise WriteDenied("补货单不存在", status_code=404)
    if order.status in ("compensated", "cancelled"):
        return {"id": order.id, "status": order.status, "replayed": True}
    inv = session.exec(select(Inventory).where(Inventory.store_id == order.store_id,
                                               Inventory.product_id == order.product_id)).first()
    if inv:
        if order.status == "arrived":
            inv.on_hand = max(0, inv.on_hand - order.qty)  # 已到货的单回退现货
        else:
            inv.in_transit = max(0, inv.in_transit - order.qty)
        inv.updated_at = timeutil.now_iso()
        session.add(inv)
    order.status = "compensated"
    session.add(order)
    session.commit()
    from ..governance.audit import audit
    audit(session, actor, "inventory.compensate_replenishment", "replenishment_order",
          order_id, detail={"order_no": order.order_no, "qty": order.qty}, trace_id=trace_id)
    return {"id": order.id, "order_no": order.order_no, "status": "compensated"}


def compensate_transfer(session: Session, order_id: str, actor: Actor | None,
                        trace_id: str = "") -> dict:
    """补偿：反向调拨，恢复双方库存。"""
    order = session.get(TransferOrder, order_id)
    if not order:
        raise WriteDenied("调拨单不存在", status_code=404)
    if order.status != "done":
        return {"id": order.id, "status": order.status, "replayed": True}
    src = session.exec(select(Inventory).where(Inventory.store_id == order.from_store_id,
                                               Inventory.product_id == order.product_id)).first()
    dst = session.exec(select(Inventory).where(Inventory.store_id == order.to_store_id,
                                               Inventory.product_id == order.product_id)).first()
    if src:
        src.on_hand += order.qty
        session.add(src)
    if dst:
        dst.on_hand = max(0, dst.on_hand - order.qty)
        session.add(dst)
    order.status = "compensated"
    session.add(order)
    session.commit()
    from ..governance.audit import audit
    audit(session, actor, "inventory.compensate_transfer", "transfer_order", order_id,
          detail={"order_no": order.order_no, "qty": order.qty}, trace_id=trace_id)
    return {"id": order.id, "order_no": order.order_no, "status": "compensated"}


def list_replenishments(session: Session, *, store_id: str = "", status: str = "",
                        limit: int = 100) -> list[dict]:
    q = select(ReplenishmentOrder)
    if store_id:
        q = q.where(ReplenishmentOrder.store_id == store_id)
    if status:
        q = q.where(ReplenishmentOrder.status == status)
    return [r.model_dump() for r in session.exec(q.order_by(ReplenishmentOrder.created_at.desc())
                                           .limit(limit)).all()]


def list_transfers(session: Session, *, store_id: str = "", limit: int = 100) -> list[dict]:
    q = select(TransferOrder)
    if store_id:
        q = q.where((TransferOrder.from_store_id == store_id) | (TransferOrder.to_store_id == store_id))
    return [r.model_dump() for r in session.exec(q.order_by(TransferOrder.created_at.desc())
                                           .limit(limit)).all()]
