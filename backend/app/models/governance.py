# -*- coding: utf-8 -*-
"""治理层表：用户身份 / 审计日志 / 幂等记录。"""
import datetime as dt

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    username: str = Field(index=True, unique=True)
    token: str = Field(index=True, unique=True)
    name: str
    role_code: str
    store_id: str = ""   # 数据权限：门店范围（空=全量）
    region_id: str = ""  # 数据权限：区域范围
    status: str = "active"


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: str = Field(index=True)
    biz_date: str = Field(default="", index=True)
    trace_id: str = Field(default="", index=True)
    actor_type: str = "user"      # user / agent / system
    actor_id: str = Field(index=True)
    actor_role: str = ""
    action: str = Field(index=True)
    resource_type: str = Field(index=True)
    resource_id: str = ""
    result: str = "success"       # success / denied / error / dry_run
    detail: str = "{}"            # JSON 字符串


class IdempotencyRecord(SQLModel, table=True):
    key: str = Field(primary_key=True)
    scope: str = Field(index=True)
    request_hash: str
    response_snapshot: str = "{}"
    created_at: str = ""
