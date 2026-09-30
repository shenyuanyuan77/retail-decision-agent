# -*- coding: utf-8 -*-
"""智能体运营表：异常事件 / 诊断 / 决策卡 / 审批 / 执行 / 复盘 / 故事线 / 策略权重 / 元数据。"""
from sqlmodel import Field, SQLModel


class Anomaly(SQLModel, table=True):
    id: str = Field(primary_key=True)          # anomaly_id
    type: str = Field(index=True)              # sales_drop / sales_surge / stockout / complaint_surge
    entity_type: str = "store_sku"             # store_sku / store / store_category
    store_id: str = Field(default="", index=True)
    product_id: str = Field(default="", index=True)
    category_id: str = ""
    metric: str = "sales_qty"
    observed: float = 0.0
    expected: float = 0.0
    deviation_pct: float = 0.0
    severity: str = "medium"                   # critical / high / medium / low
    status: str = "open"                       # open/diagnosed/decided/acting/closed/ignored
    window_start: str = ""
    window_end: str = ""
    detected_at: str = ""
    detection_latency_h: float | None = None
    method: str = "rolling_median_mad"
    evidence: str = "[]"                       # JSON：感知层证据
    storyline_id: str = ""
    narrative: str = ""


class Diagnosis(SQLModel, table=True):
    id: str = Field(primary_key=True)
    anomaly_id: str = Field(index=True)
    root_causes: str = "[]"          # JSON [{code,name,confidence,contribution,evidence[],counter_evidence[]}]
    dimension_drill: str = "[]"      # JSON 维度下钻结果
    hypothesis_log: str = "[]"       # JSON 假设验证过程（可审计）
    summary: str = ""
    narrative: str = ""
    method: str = "hypothesis_test"
    trace_id: str = ""
    created_at: str = ""


class DecisionCard(SQLModel, table=True):
    id: str = Field(primary_key=True)           # decision_id
    anomaly_id: str = Field(index=True)
    action_type: str                            # replenish/transfer/promo/member_reach/cs_followup
    action: str = "{}"                          # JSON 动作参数
    rationale: str = ""
    risk_level: str = "low"                     # low/medium/high
    risk_reasons: str = "[]"
    requires_approval: int = 0
    expected_impact: str = "{}"                 # JSON {est_cost, est_benefit, est_recovery_pct, roi}
    constraints_checked: str = "[]"             # JSON 约束检查明细
    status: str = "suggested"                   # suggested/pending_approval/approved/rejected/executing/executed/failed/expired/compensated
    created_at: str = ""
    trace_id: str = ""
    decided_by: str = ""
    decided_at: str = ""


class Approval(SQLModel, table=True):
    id: str = Field(primary_key=True)           # approval_id
    decision_id: str = Field(index=True)
    anomaly_id: str = ""
    action_type: str = ""
    summary: str = ""                           # 人读摘要
    risk_reasons: str = "[]"
    status: str = "pending"                     # pending/approved/rejected/expired
    requested_by: str = "agent_service"
    requested_at: str = ""
    decided_by: str = ""
    decided_at: str = ""
    decision_note: str = ""


class Execution(SQLModel, table=True):
    id: str = Field(primary_key=True)           # execution_id
    decision_id: str = Field(index=True)
    anomaly_id: str = ""
    tool_name: str = Field(index=True)          # create_replenishment_order / ...
    idempotency_key: str = Field(index=True)
    request: str = "{}"
    result: str = "{}"
    status: str = "pending"                     # pending/running/success/failed/compensated/rejected
    dry_run: int = 0
    error: str = ""
    business_ref: str = ""                      # order_no / campaign id / task_no
    trace_id: str = ""
    created_at: str = ""
    finished_at: str = ""
    compensated_at: str = ""


class ReviewReport(SQLModel, table=True):
    id: str = Field(primary_key=True)           # review_id
    execution_id: str = Field(index=True)
    decision_id: str = ""
    anomaly_id: str = ""
    action_type: str = ""
    period_before: str = "{}"        # JSON 指标快照
    period_after: str = "{}"         # JSON 指标快照
    kpi_delta: str = "{}"            # JSON 前后对比
    verdict: str = "effective"       # effective / partial / ineffective
    reasons: str = "[]"
    narrative: str = ""
    trace_id: str = ""
    created_at: str = ""


class Storyline(SQLModel, table=True):
    """异常注入故事线（真值）：评估层用 truth_root_cause 计算根因准确率。"""
    id: str = Field(primary_key=True)           # storyline_id
    type: str = Field(index=True)               # stockout_drop / promo_surge / complaint_drop
    store_id: str = Field(index=True)
    product_id: str = Field(index=True)
    category_id: str = ""
    start_date: str
    end_date: str
    truth_root_cause: str                       # 根因真值代码（诊断层根因库 key）
    description: str = ""
    params: str = "{}"
    active: int = 1


class StrategyWeight(SQLModel, table=True):
    id: str = Field(primary_key=True)           # f"{action_type}:{context}"
    action_type: str = Field(index=True)
    context: str = ""
    weight: float = 1.0
    wins: int = 0
    losses: int = 0
    updated_at: str = ""


class MetaKV(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = ""
