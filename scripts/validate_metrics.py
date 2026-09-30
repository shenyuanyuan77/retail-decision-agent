# -*- coding: utf-8 -*-
"""目标1校验脚本：检查指标字典/角色/场景/目标映射的完整性。退出码 0=通过。"""
import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
try:
    import yaml
except ImportError:
    print("ERROR: 需要 PyYAML (pip install pyyaml)"); sys.exit(2)

REQUIRED_METRICS = [
    "sales_amount", "sales_qty", "gross_margin_rate", "stockout_rate",
    "inventory_turnover", "promo_roi", "member_repurchase_rate", "complaint_rate",
    "anomaly_detection_latency", "root_cause_accuracy", "suggestion_adoption_rate",
    "auto_exec_success_rate",
]
REQUIRED_SCENARIOS = [
    "sales_drop", "sales_surge", "stockout", "near_expiry", "member_churn",
    "complaint_surge", "competitor_promo", "weather_impact",
]
REQUIRED_ROLES = [
    "region_manager", "store_manager", "supply_planner", "member_ops",
    "cs_supervisor", "hq_ops", "risk_approver",
]
METRIC_FIELDS = ["code", "name", "category", "unit", "direction", "definition", "formula", "source"]
SCENARIO_FIELDS = ["code", "name", "trigger", "metrics_impacted", "suggested_actions", "risk_level", "requires_approval"]

errors, warnings = [], []
data = yaml.safe_load((ROOT / "data" / "kb" / "metrics.yaml").read_text(encoding="utf-8"))

metrics = {m.get("code"): m for m in data.get("metrics", [])}
scenarios = {s.get("code"): s for s in data.get("scenarios", [])}
roles = {r.get("code"): r for r in data.get("roles", [])}
goals = data.get("business_goals", [])

for code in REQUIRED_METRICS:
    m = metrics.get(code)
    if not m:
        errors.append(f"缺少指标: {code}"); continue
    for f in METRIC_FIELDS:
        if not m.get(f):
            errors.append(f"指标 {code} 缺少字段 {f}")

for code in REQUIRED_SCENARIOS:
    s = scenarios.get(code)
    if not s:
        errors.append(f"缺少场景: {code}"); continue
    for f in SCENARIO_FIELDS:
        if not s.get(f):
            errors.append(f"场景 {code} 缺少字段 {f}")

for code in REQUIRED_ROLES:
    r = roles.get(code)
    if not r:
        errors.append(f"缺少角色: {code}"); continue
    if not r.get("permission_level") or not r.get("data_scope"):
        errors.append(f"角色 {code} 缺少权限级别或数据范围")

# 目标-指标映射完整性：每个业务目标的指标都必须存在于字典
for g in goals:
    for mc in g.get("metrics", []):
        if mc not in metrics:
            errors.append(f"目标 {g.get('code')} 引用了未定义指标 {mc}")

# 双向覆盖：每个业务指标至少被一个目标引用
referenced = {mc for g in goals for mc in g.get("metrics", [])}
for code in REQUIRED_METRICS:
    if code not in referenced:
        warnings.append(f"指标 {code} 未被任何业务目标引用")

# 场景引用的指标必须存在（market_share 为外部市场指标，允许扩展）
for code, s in scenarios.items():
    for mc in s.get("metrics_impacted", []):
        if mc not in metrics and mc not in ("market_share",):
            errors.append(f"场景 {code} 引用了未定义指标 {mc}")

print(f"指标 {len(metrics)} 个 | 场景 {len(scenarios)} 个 | 角色 {len(roles)} 个 | 目标 {len(goals)} 个")
for w in warnings:
    print(f"WARN: {w}")
if errors:
    for e in errors:
        print(f"FAIL: {e}")
    sys.exit(1)
print("指标字典完整性校验通过 ✓")
