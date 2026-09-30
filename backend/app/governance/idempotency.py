# -*- coding: utf-8 -*-
"""受控写入：幂等 + dry-run + 审计 三合一入口。

所有 Mock 业务系统的写接口都经过 controlled_write：
1. 幂等：相同 idempotency_key + 相同请求 → 重放首次结果，不重复写入；key 相同但请求不同 → 拒绝。
2. dry_run：只预览不落库（审计记录 result=dry_run）。
3. 审计：成功/拒绝/失败均写 audit_logs。
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Callable

from sqlmodel import Session

from ..core import timeutil
from ..models import IdempotencyRecord
from .audit import audit
from .auth import Actor


class WriteDenied(Exception):
    def __init__(self, reason: str, result: str = "denied", status_code: int = 403):
        super().__init__(reason)
        self.reason = reason
        self.result = result
        self.status_code = status_code


@dataclass
class WriteOutcome:
    payload: dict
    replayed: bool = False
    dry_run: bool = False


def _request_hash(scope: str, payload: dict) -> str:
    blob = json.dumps({"scope": scope, "payload": payload}, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def controlled_write(
    session: Session,
    *,
    actor: Actor | None,
    action: str,
    resource_type: str,
    scope: str,
    idempotency_key: str,
    dry_run: bool,
    payload: dict,
    executor: Callable[[Session], dict],          # 真实写入，返回业务结果
    previewer: Callable[[Session], dict] | None = None,  # dry-run 预览
    trace_id: str = "",
    extra_audit: dict | None = None,
) -> WriteOutcome:
    # 1) 幂等检查
    if idempotency_key:
        rec = session.get(IdempotencyRecord, f"{scope}:{idempotency_key}")
        if rec:
            if rec.request_hash != _request_hash(scope, payload):
                audit(session, actor, action, resource_type, idempotency_key,
                      detail={"error": "idempotency_key 冲突：相同 key 不同请求"},
                      result="denied", trace_id=trace_id)
                raise WriteDenied(f"idempotency_key={idempotency_key} 已用于不同请求", status_code=409)
            audit(session, actor, action, resource_type, idempotency_key,
                  detail={"replayed": True}, result="success", trace_id=trace_id)
            return WriteOutcome(payload=json.loads(rec.response_snapshot), replayed=True)

    # 2) dry-run：不执行写入
    if dry_run:
        preview = previewer(session) if previewer else {"would_execute": True, **payload}
        preview["dry_run"] = True
        audit(session, actor, action, resource_type, idempotency_key or "-",
              detail={**(extra_audit or {}), "preview": preview}, result="dry_run", trace_id=trace_id)
        return WriteOutcome(payload=preview, dry_run=True)

    # 3) 真实写入
    try:
        result = executor(session)
    except WriteDenied:
        raise
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        audit(session, actor, action, resource_type, idempotency_key or "-",
              detail={**(extra_audit or {}), "error": str(exc)}, result="error", trace_id=trace_id)
        raise

    if idempotency_key:
        session.add(IdempotencyRecord(
            key=f"{scope}:{idempotency_key}", scope=scope,
            request_hash=_request_hash(scope, payload),
            response_snapshot=json.dumps(result, ensure_ascii=False, default=str),
            created_at=timeutil.now_iso(),
        ))
    session.commit()
    audit(session, actor, action, resource_type, result.get("id", idempotency_key or "-"),
          detail={**(extra_audit or {}), "result": result}, result="success", trace_id=trace_id)
    return WriteOutcome(payload=result)
