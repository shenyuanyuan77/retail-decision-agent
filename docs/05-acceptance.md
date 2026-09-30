# 05 验收清单（总目标 8 项验收 × 证据）

| # | 验收项 | 证据 | 状态 |
|---|---|---|---|
| 1 | 一键启动后所有服务启动 | `scripts\start.bat` / `bash scripts/start.sh` / `docker compose up --build`；`/health` 200；前端 `/` 200 | ✅ |
| 2 | 自动生成 180 天/50 店/500 SKU 数据 | `python scripts/generate.py` → 销售 1,645,039 行 + 库存 16,400 + 工单 3,106 + 会员 5,000 + 促销 18 + 天气/竞品/日历 | ✅ |
| 3 | 注入 ≥3 类销量异常 | 3 条故事线（缺货型下降/促销型上升/客诉型下降），每条 ≥3 证据（docs/03 验证 SQL） | ✅ |
| 4 | Agent 发现异常，输出根因 Top3/建议/风险/证据链 | 3/3 故事线检出（召回 100%）；根因 Top3 命中真因 100%；每根因 ≥2 证据 | ✅ |
| 5 | 低风险自动执行、高风险进入审批 | 流水线：12 低风险自动执行成功；9 高风险创建审批单 → 风控通过后执行；合规率 100% | ✅ |
| 6 | 看板可查看异常/审批/执行/审计 | web/ 六个核心页面 + Playwright e2e 断言（复盘/世界页按 2026-09-30 产品审计裁决降级为可选 API，UI 入口移除） | ✅ |
| 7 | pytest 与 Playwright e2e 通过 | `python -m pytest tests/` → 42 passed（含 Playwright 核心闭环 UI 端到端 3 项） | ✅ |
| 8 | README 完整演示步骤 | README「演示路径（8 步）」+ `python scripts/demo.py` | ✅ |

## 分目标验收对照

| 目标 | 验收要点 | 证据 |
|---|---|---|
| 1 业务定义 | 指标字典完整性校验 | `python scripts/validate_metrics.py` → 通过 ✓（13 指标/8 场景/8 角色/4 目标） |
| 2 Mock 系统 | 服务启动/OpenAPI/四类写入/幂等 | tests/test_mock_systems.py（18 项）；重复 idempotency_key 重放不重复下单 |
| 3 数据与异常 | 可查询/≥3 证据/可重复 | tests/test_world.py（6 项）；同种子两次生成行数一致 |
| 4 感知层 | 召回>90%/统一JSON/误报可解释 | tests/test_perception.py；3/3=100%；evidence 字段含工具与数据 |
| 5 诊断层 | Top3 命中>80%/每根因≥2证据 | tests/test_agent_pipeline.py::test_2；100% 命中 |
| 6 决策层 | ≥1 方案/约束违反率 0/高风险标记 | tests/test_agent_pipeline.py::test_3；constraints_checked 全 passed |
| 7 执行层 | 自动执行/审批/幂等/补偿 | tests/test_agent_pipeline.py::test_4-7；补偿后库存/状态回退 |
| 8 治理层 | 审批合规 100%/禁止拒绝/审计链路 | tests/test_governance.py；L4 动作 403；trace 贯穿 |
| 9 评估层 | 每执行有复盘/权重更新/指标改善 | tests/test_agent_pipeline.py::test_8-9；strategy_weights 更新 |
| 10 前端 | 端到端演示闭环 | tests/test_e2e_playwright.py（真实浏览器全流程） |
| 11 交付 | 测试/README/架构图/脚本 | tests/ + docs/ + scripts/ + docker-compose.yml |

## 复验命令

```bash
python scripts/validate_metrics.py        # 目标1
python -m pytest tests/ -v                # 全部 41 项（含 e2e）
python scripts/demo.py --small            # 1 分钟完整闭环演示
bash scripts/start.sh                     # 启动后按 README 演示路径操作看板
```
