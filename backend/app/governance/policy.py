# -*- coding: utf-8 -*-
"""Policy Engine：动作 → 风险等级 / 是否需审批 / 是否允许。

规则来源 data/kb/policies.yaml；决策层标记审批、执行层硬校验均调用 evaluate()。
agent_service 权限上限 L2：即使规则允许自动，L3 语义动作也必须走审批。
"""
import json
import os
from dataclasses import dataclass, field

from ..core import config
from .auth import Actor

_DEFAULTS = {
    "replenish": {"base_level": 2, "amount": [(1e9, False, "low")]},
}


@dataclass
class PolicyDecision:
    action_type: str
    allowed: bool = True
    risk_level: str = "low"
    requires_approval: bool = False
    required_level: int = 2
    reasons: list = field(default_factory=list)
    denied_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type, "allowed": self.allowed,
            "risk_level": self.risk_level, "requires_approval": self.requires_approval,
            "required_level": self.required_level, "reasons": self.reasons,
            "denied_reason": self.denied_reason,
        }


_RULES: dict | None = None


def _load_rules() -> dict:
    global _RULES
    if _RULES is None:
        path = config.KB_DIR / "policies.yaml"
        if path.exists():
            import yaml
            _RULES = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            _RULES = {"action_types": {}, "forbidden_actions": []}
    return _RULES


def _cmp(op: str, a, b) -> bool:
    try:
        if op == "<=":
            return float(a) <= float(b)
        if op == ">":
            return float(a) > float(b)
        if op == "==":
            return str(a).lower() == str(b).lower()
    except (TypeError, ValueError):
        return False
    return False


def evaluate(actor: Actor | None, action_type: str, params: dict) -> PolicyDecision:
    rules = _load_rules()
    forbidden = rules.get("forbidden_actions", [])

    # L4：全局禁止动作
    if action_type in forbidden:
        return PolicyDecision(action_type, allowed=False, required_level=4, risk_level="high",
                              denied_reason=f"动作 {action_type} 在禁止清单（L4）中")

    spec = rules.get("action_types", {}).get(action_type)
    if not spec:
        return PolicyDecision(action_type, allowed=False, required_level=4,
                              denied_reason=f"动作 {action_type} 不在操作白名单中")

    d = PolicyDecision(action_type=action_type, required_level=int(spec.get("base_level", 2)))

    # 规则评估：每条规则取首个命中的阈值（有序），跨规则取最高风险、合并审批要求
    for rule in spec.get("rules", []):
        fname = rule.get("field")
        value = params.get(fname, params.get("always", True if fname == "always" else None))
        for th in rule.get("thresholds", []):
            if "deny" in th and th["deny"] and _cmp(th["op"], value, th["value"]):
                d.allowed = False
                d.denied_reason = th.get("reason", f"违反硬性上限 {rule['id']}")
                d.risk_level = "high"
                return d
            if _cmp(th["op"], value, th["value"]):
                risk = th.get("risk", "low")
                if ["low", "medium", "high"].index(risk) > ["low", "medium", "high"].index(d.risk_level):
                    d.risk_level = risk
                if th.get("approval"):
                    d.requires_approval = True
                    d.required_level = max(d.required_level, 3)
                if th.get("reason"):
                    d.reasons.append(th["reason"])
                break   # 首个命中阈值生效（如 折扣10% → 命中 <=10 低风险，不再看 <=30）

    # 角色权限校验（匿名视为 L0 只读）
    actor_level = actor.max_level if actor else 0
    if actor_level < 2 and d.required_level >= 2:
        d.allowed = False
        who = actor.role if actor else "anonymous(L0)"
        d.denied_reason = f"角色 {who} 权限不足（需 L{d.required_level}，当前 L{actor_level}）"
    elif actor is not None and actor.is_agent and d.requires_approval:
        d.reasons.append("Agent 服务身份上限 L2：高风险动作必须转人工审批")

    return d


def evaluate_json(actor: Actor | None, action_type: str, params: dict) -> str:
    return json.dumps(evaluate(actor, action_type, params).to_dict(), ensure_ascii=False)
