# 03 数据模型与异常故事线（含验证 SQL）

## 1. 数据规模与生成

| 维度 | 值 | 说明 |
|---|---|---|
| 时间窗 | 180 天 | 结束于业务今天（meta.today），可推演 T+N |
| 门店 | 50 | 5 大区 11 城；flagship 10 / large 15 / standard 25 |
| SKU | 500 | 20 品类 × 25；含保质期品类（烘焙5天/乳品14天/生鲜3天） |
| 会员 | 5,000 | 每店 100，四层分层（vip/high/normal/new） |
| 销售行 | ~165 万 | 稀疏存储（零销量不落行）；门店×SKU×天 粒度 |
| 随机种子 | 42 | `python scripts/generate.py --seed 42` 完全可重复 |

需求模型：`日销量 ~ Poisson(μ × 周末/节假日/会员日 × 天气品类系数 × 促销弹性)`，
μ = 品类基线 × 商品流行度(lognormal) × 门店档位系数 × 门店噪声；促销弹性 = `1 + 折扣% × 6`。

## 2. 核心表

| 表 | 域 | 说明 |
|---|---|---|
| stores / regions / products / categories / suppliers | 主数据 | 门店档位决定选品宽度与需求系数 |
| sales_orders | 销售 | 粒度 store×product×day；含 member_qty / online_qty / promo_flag / campaign_id |
| inventory | 库存 | on_hand / in_transit / safety_stock / expiry_date |
| replenishment_orders / transfer_orders | 供应链 | 写入受控；支持补偿 |
| members / member_segment_stats / campaigns | 会员 CRM | 月度复购统计（评估数据源） |
| tickets / ticket_tasks | 客服 | 类型 quality/expiry/stockout/service/delivery |
| weather / competitor_promos / calendar_days | 外部 | 天气有品类效应系数；每月18日会员日 |
| anomalies / diagnoses / decision_cards / approvals / executions / review_reports / strategy_weights / storylines | 智能体运营 | 全链路状态 |
| users / audit_logs / idempotency_records | 治理 | token 演示身份；trace_id 审计 |

## 3. 三条异常故事线（注入窗口 [today-11, today-4]，缺货型持续到今天）

### A. 缺货型下降 `sl-stockout-01`（标准店 × 饮料 C01）
| 要素 | 内容 | 数据证据 |
|---|---|---|
| 根因真值 | `stockout` | — |
| 机制 | 供应商延迟→库存清零→销量≈0（×0.05） | inventory.on_hand=0 |
| 佐证1 | 逾期补货单 | replenishment_orders: status=confirmed 且 arrive_date < today |
| 佐证2 | 缺货工单 5 条 | tickets: type=stockout（产品级） |
| 混淆因素 | 竞品饮料促销 15% + 降温（cold_wave） | competitor_promos / weather |
| 基线 | 近 45 天垫高至日销 ~10 | sales_orders 历史改写 |

### B. 促销型上升 `sl-promo-01`（旗舰店 × 零食 C04）
| 要素 | 内容 |
|---|---|
| 根因真值 | `promo`（自有会员日加码 15% 折扣） |
| 机制 | campaign `cmp-inj-memberday` 覆盖本店本品，销量 ×2.2，member_qty 占比 0.78 |
| 反证设计 | 窗口内无竞品促销（诊断层应排除 competitor_promo） |

### C. 客诉型下降 `sl-complaint-01`（大店 × 乳品 C06）
| 要素 | 内容 |
|---|---|
| 根因真值 | `complaint`（临期未折价引发口碑恶化） |
| 机制 | 临期批次（expiry_date=today+6）未折价 → 临期/质量工单 12 条 → 会员复购 ×0.7 → 销量 ×0.40 |

## 4. 验证 SQL（生成+注入后执行；sqlite3 backend/data_local/retail.db）

```sql
-- 4.1 三条故事线就位
SELECT id, type, store_id, product_id, truth_root_cause, start_date, end_date
FROM storyline;

-- 4.2 缺货型：库存为0 + 逾期补货单 + 缺货工单 ≥3（证据链）
SELECT 'inventory' src, store_id, product_id, on_hand FROM inventory i
 WHERE i.store_id=(SELECT store_id FROM storyline WHERE id='sl-stockout-01')
   AND i.product_id=(SELECT product_id FROM storyline WHERE id='sl-stockout-01');
SELECT order_no, status, arrive_date FROM replenishmentorder
 WHERE store_id=(SELECT store_id FROM storyline WHERE id='sl-stockout-01')
   AND product_id=(SELECT product_id FROM storyline WHERE id='sl-stockout-01');
SELECT COUNT(*) FROM ticket
 WHERE type='stockout' AND store_id=(SELECT store_id FROM storyline WHERE id='sl-stockout-01');

-- 4.3 促销型：窗口销量高于基线 80%+
SELECT AVG(CASE WHEN biz_date BETWEEN '2026-09-19' AND '2026-09-25' THEN qty END) AS win_avg,
       AVG(CASE WHEN biz_date BETWEEN '2026-09-05' AND '2026-09-18' THEN qty END) AS base_avg
FROM salesorder
WHERE store_id=(SELECT store_id FROM storyline WHERE id='sl-promo-01')
  AND product_id=(SELECT product_id FROM storyline WHERE id='sl-promo-01');

-- 4.4 客诉型：临期 + 客诉激增 + 复购下滑
SELECT expiry_date FROM inventory
 WHERE store_id=(SELECT store_id FROM storyline WHERE id='sl-complaint-01')
   AND product_id=(SELECT product_id FROM storyline WHERE id='sl-complaint-01');
SELECT type, COUNT(*) FROM ticket
 WHERE store_id=(SELECT store_id FROM storyline WHERE id='sl-complaint-01')
   AND type IN ('expiry','quality') GROUP BY type;
SELECT month_start, SUM(repurchase_members)*1.0/SUM(active_members) AS repurchase_rate
FROM membersegmentstat
WHERE store_id=(SELECT store_id FROM storyline WHERE id='sl-complaint-01')
GROUP BY month_start ORDER BY month_start;

-- 4.5 数据可重复性：同种子两次生成的行数一致（脚本断言，见 tests/test_world.py）
SELECT COUNT(*) FROM salesorder;
```

## 5. 时间推演（T+N）因果规则

| 规则 | 公式/条件 | 影响 |
|---|---|---|
| 补货到货 | confirmed 且 arrive_date≤当日 | on_hand+=qty，in_transit-=qty |
| 促销弹性 | lift = 1 + 折扣%×6 | 覆盖门店×品类销量提升，cost_actual 累计 |
| 库存门控 | 销量 = min(需求, on_hand) | 未补货的缺货商品销量持续为 0 |
| 客服整改 | 门店存在 pending 回访任务 | 该店客诉生成率 0.35→0.18/天 |
| 缺货工单 | 有需求且无货 | 每店每天至多 1 条 stockout 工单 |
| 天气/竞品/日历 | 与生成器同模型 | 推演期外部数据继续生成 |
