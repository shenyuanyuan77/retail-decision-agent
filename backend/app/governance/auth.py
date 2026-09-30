# -*- coding: utf-8 -*-
"""身份与权限：角色权限矩阵 L0-L4。

L0 只读 / L1 建议 / L2 低风险写入 / L3 高风险写入 / L4 禁止。
Agent 服务身份上限 L2：任何 L3 动作必须转人工审批，L4 一律拒绝。
"""
from dataclasses import dataclass

from sqlmodel import Session

from ..models import User

# 角色最大权限级（来自 data/kb/metrics.yaml roles.permission_level）
ROLE_MAX_LEVEL = {
    "region_manager": 2,
    "store_manager": 2,
    "supply_planner": 2,
    "member_ops": 2,
    "cs_supervisor": 2,
    "hq_ops": 2,
    "risk_approver": 3,
    "agent_service": 2,   # Agent 自动执行硬上限
    "system": 4,
}

LEVEL_NAMES = {0: "L0-只读", 1: "L1-建议", 2: "L2-低风险写入", 3: "L3-高风险写入", 4: "L4-禁止"}


@dataclass
class Actor:
    id: str
    username: str
    name: str
    role: str
    store_id: str = ""
    region_id: str = ""
    is_agent: bool = False

    @property
    def max_level(self) -> int:
        return ROLE_MAX_LEVEL.get(self.role, 0)


AGENT_ACTOR = Actor(
    id="usr_agent", username="agent_service", name="经营决策Agent",
    role="agent_service", is_agent=True,
)


def resolve_actor(session: Session, token: str | None) -> Actor | None:
    """通过 X-Auth-Token 解析用户；token 为空返回匿名（仅 L0）。"""
    if not token:
        return None
    user = session.exec(
        __import__("sqlmodel").select(User).where(User.token == token, User.status == "active")
    ).first()
    if not user:
        return None
    return Actor(
        id=user.id, username=user.username, name=user.name, role=user.role_code,
        store_id=user.store_id, region_id=user.region_id,
        is_agent=user.role_code == "agent_service",
    )


def check_data_scope(actor: Actor | None, store_id: str) -> tuple[bool, str]:
    """数据权限：店长仅本店，区域经理仅本区域，其余全量；匿名只读允许。"""
    if actor is None:
        return True, "anonymous-readonly"
    if actor.role == "store_manager" and actor.store_id and store_id and store_id != actor.store_id:
        return False, f"店长数据范围仅限本店 {actor.store_id}"
    return True, ""


def seed_users(session: Session) -> None:
    """预置演示用户（密码体系略，Mock 使用固定 token）。"""
    seeds = [
        ("usr_region_01", "region_manager_01", "tok_region_01", "华东区域经理-王区域", "region_manager", "", "R-east"),
        ("usr_store_01", "store_manager_s001", "tok_store_01", "S001店长-李店长", "store_manager", "S001", ""),
        ("usr_planner_01", "supply_planner_01", "tok_planner_01", "供应链计划员-赵计划", "supply_planner", "", ""),
        ("usr_member_01", "member_ops_01", "tok_member_01", "会员运营-钱运营", "member_ops", "", ""),
        ("usr_cs_01", "cs_supervisor_01", "tok_cs_01", "客服主管-孙主管", "cs_supervisor", "", ""),
        ("usr_hq_01", "hq_ops_01", "tok_hq_01", "总部运营-周运营", "hq_ops", "", ""),
        ("usr_risk_01", "risk_approver_01", "tok_risk_01", "风控审批人-吴风控", "risk_approver", "", ""),
        ("usr_agent", "agent_service", "tok_agent", "经营决策Agent", "agent_service", "", ""),
    ]
    for uid, username, token, name, role, store_id, region_id in seeds:
        if not session.get(User, uid):
            session.add(User(id=uid, username=username, token=token, name=name,
                             role_code=role, store_id=store_id, region_id=region_id))
    session.commit()
