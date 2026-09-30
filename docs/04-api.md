# 04 接口说明（OpenAPI）

完整交互式文档：运行服务后打开 `http://127.0.0.1:8300/docs`（Swagger UI）或 `/openapi.json`。
所有写接口支持 `idempotency_key`（幂等重放/冲突检测）与 `dry_run`（预览不落库），并写审计日志。

## 1. Mock 业务系统

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/master/regions·stores·categories·products·suppliers | 主数据查询（分页/筛选） |
| GET | /api/sales/daily | 日销售查询：store_id/product_id/category_id/start/end/channel(online·offline)/member_only |
| GET | /api/sales/timeseries?store_id&product_id&days | 感知层数据源 |
| GET | /api/sales/summary?start&end | 汇总（额/量/毛利率） |
| GET | /api/inventory?below_safety&out_of_stock | 库存查询 |
| POST | /api/inventory/replenishments | 创建补货单（MOQ/金额阈值治理） |
| POST | /api/inventory/transfers | 创建调拨（跨区必审批；源库存校验） |
| POST | /api/inventory/replenishments/{id}/compensate · /transfers/{id}/compensate | 补偿 |
| GET | /api/members · /segments · /repurchase | 会员/分层/复购率 |
| POST | /api/members/campaigns | 创建促销（折扣/预算阈值治理） |
| GET | /api/cs/tickets · /tickets/stats · /tasks | 工单查询统计 |
| POST | /api/cs/tasks | 创建回访任务（compensation_review 需审批） |
| GET | /api/external/weather·competitor-promos·calendar | 外部数据 |

## 2. 治理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/gov/approvals?status=pending | 审批队列 |
| POST | /api/gov/approvals/{id}/decide | 审批（body: {decision: approve\|reject, note}；需 X-Auth-Token: tok_risk_01） |
| GET | /api/gov/audit-logs?trace_id&action&actor_id&result | 审计日志（多条件） |
| GET | /api/gov/permission-matrix | 权限矩阵与风险规则 |

## 3. 智能体

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/agent/scan | 感知扫描（幂等去重） |
| POST | /api/agent/diagnose[?anomaly_id] | 诊断归因（Top3 根因+证据） |
| POST | /api/agent/decide[?anomaly_id] | 生成决策卡 |
| POST | /api/agent/execute[?decision_id] | 执行（低风险自动/高风险转审批） |
| POST | /api/agent/compensate | 补偿执行 |
| POST | /api/agent/pipeline | 感知→诊断→决策→执行 |
| POST | /api/agent/demo-cycle | 完整闭环（含审批+推演+复盘） |
| POST | /api/agent/review[?execution_id] | T+7 复盘 |
| GET | /api/agent/anomalies?storyline_only=true | 异常列表 |
| GET | /api/agent/anomalies/{id} | 异常详情（证据链/根因/假设日志/决策） |
| GET | /api/agent/decisions·executions·reviews·strategy-weights·storylines | 各类记录 |
| GET | /api/kpi/overview·trend·stores | 看板指标 |

## 4. 世界

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/world/generate | 重新生成数据+注入（body: days/stores/skus/seed/inject） |
| POST | /api/world/advance | T+N 推演（body: {days: 7}） |
| GET | /api/world/status | 业务今天/种子/故事线 |

## 5. 示例请求

```bash
# 低风险补货（计划员身份，幂等键防重）
curl -X POST http://127.0.0.1:8300/api/inventory/replenishments \
  -H "X-Auth-Token: tok_planner_01" -H "Content-Type: application/json" \
  -d '{"store_id":"S001","product_id":"P00001","qty":50,"idempotency_key":"demo-001","dry_run":true}'

# 高风险促销（>10% 折扣 → 403 需审批）
curl -X POST http://127.0.0.1:8300/api/members/campaigns \
  -H "X-Auth-Token: tok_member_01" -H "Content-Type: application/json" \
  -d '{"name":"跟进竞品","store_ids":["S001"],"category_id":"C01","discount_pct":15,"budget":5000}'

# 审批（风控）
curl -X POST http://127.0.0.1:8300/api/gov/approvals/{id}/decide \
  -H "X-Auth-Token: tok_risk_01" -H "Content-Type: application/json" \
  -d '{"decision":"approve","note":"同意"}'

# 一键闭环 + 指标
curl -X POST http://127.0.0.1:8300/api/agent/demo-cycle
```
