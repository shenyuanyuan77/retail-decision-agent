# 零售经营决策 Agent 系统

一套**可运行、可演示、可测试**的零售经营决策 Agent：接入门店 / 销售 / 库存供应链 / 会员 / 客服 / 外部数据多个系统，**自动发现销量异常 → 分析原因 → 提出补货或促销建议 → 在授权范围内执行**。所有数据 Mock 生成、固定种子可重复，不依赖任何真实企业系统。

```
自动发现 → 根因分析 → 补货/促销建议 → 授权执行（低风险自动 · 高风险人工审批）
```

> **范围说明（2026-09-30 产品审计裁决）**：本系统按原问题最小集交付核心能力；曾建的世界推演/T+7 复盘/策略自学习等扩展能力已**冻结为可选后端 API**（代码保留、UI 入口移除），调拨/会员触达/客服跟进三类动作经 `data/kb/playbooks.yaml` 配置收缩停用。裁决详情见 [docs/06-product-audit.md](docs/06-product-audit.md)。

## 核心能力

- **多系统接入（R1）**：六大 Mock 业务系统（主数据/销售/库存/会员/客服/外部数据），REST API + OpenAPI
- **自动发现异常（R2）**：滚动中位数 + MAD + z-score 统计检测，主动全量扫描（可定时），无需人工指定目标；全部异常带数据证据
- **原因分析（R3）**：9 类假设验证（缺货/供应链延迟/促销/竞品/天气/客诉/临期/会员流失/价格），Top3 根因 + 置信度 + 每根因 ≥2 条证据；证据不足显式转人工
- **补货 / 促销建议（R4）**：根因 × 打法库 → 决策卡（补货量、折扣、预算），MOQ/覆盖天数/毛利率下限/折扣与预算硬上限约束检查 + 成本收益与 ROI 估算
- **授权范围内执行（R5）**：L0-L4 权限矩阵 + Policy Engine（折扣>10%、预算>1万、跨区调拨必须审批；折扣>30%、预算>10万直接拒绝）+ Agent 服务身份上限 L2 + 风控审批人 Human-in-the-loop + 全链路审计日志

## 启动

```bash
# 方式一：一键脚本（自动装依赖+生成数据）
scripts\start.bat          # Windows
bash scripts/start.sh      # Linux / macOS / Git Bash

# 方式二：docker compose
docker compose up --build

# 方式三：手动
pip install -r backend/requirements.txt
python scripts/generate.py && cd backend && python -m uvicorn app.main:app --port 8300
```

打开 <http://127.0.0.1:8300>。

**在线只读预览（GitHub Pages 快照版）**：<https://shenyuanyuan77.github.io/retail-decision-agent/>
每次 push main 后 Actions 自动重建演示数据快照并发布；完整交互（运行 Agent/审批/执行）请本地启动。

## 演示路径（6 步）

1. **经营总览**：销售额/毛利率 KPI、30 天趋势、待处理异常与待审批计数
2. 点右上角 **「⚡ 运行 Agent」**：一次完成 发现异常 → 原因分析 → 生成建议 → 执行
3. **异常中心**：点击任一异常 → 查看检测证据链（①）与原因分析 Top3 根因（②，置信度+证据）
4. **补货 / 促销建议**：查看决策卡（成本/收益/ROI/约束检查）；低风险标记"自动执行"，高风险标记"需审批"
5. **审批中心**：身份选「风控审批人（L3）」→ 通过/驳回高风险动作（如 12% 折扣促销）→ 自动执行
6. **执行记录 / 审计日志**：每一步执行与审批留痕，trace_id 可还原完整链路

## 测试

```bash
python -m pytest tests/ -v        # 42 项：单元 + 集成 + Playwright 端到端（核心闭环）
python scripts/validate_metrics.py
# 首次运行 Playwright 前: playwright install chromium
```

## 设计与技术

- **前端**：设计语言取自 [shadcn/ui](https://github.com/shadcn-ui/ui)（~80K★，Radix + Tailwind 设计体系，浅色主题）：白底卡片、slate 中性色、indigo 点缀、Inter 字体；原生 JS SPA，无构建步骤
- **后端**：FastAPI + SQLModel + SQLite（WAL）；Agent 为纯 Python 状态机；LLM 叙述层可选（OpenAI 兼容接口，未配置时离线模板，含防编造校验）
- **治理贯穿**：所有写操作幂等（idempotency_key）+ 可 dry-run + 审计留痕；先只读后写入、先建议后执行

## 仓库结构

```
backend/app/
  services/     六大 Mock 业务系统（R1）
  agents/       感知/诊断/决策/执行 + 编排 + 只读工具层（R2-R4）
  governance/   权限矩阵 / Policy Engine / 审批 / 审计 / 幂等（R5）
  world/        数据生成 / 异常注入 / 时间推演（测试夹具与可选 API）
  api/          REST 路由（/api/master /sales /inventory /members /cs /external /gov /agent /kpi /world）
web/            前端控制台（6 核心页面，shadcn/ui 浅色）
data/kb/        指标字典 / 治理规则 / 根因库 / 打法库（YAML）
tests/          pytest + Playwright（42 项）
docs/           业务目标 / 架构 / 数据与异常 / API / 验收清单 / 产品审计报告
scripts/        一键启动 / 数据生成 / 演示 / 指标校验
```

## 演示身份（X-Auth-Token）

| 角色 | Token | 权限 |
|---|---|---|
| 风控审批人 | `tok_risk_01` | L3（唯一可审批高风险动作） |
| 供应链计划员 | `tok_planner_01` | L2 |
| 会员运营 / 区域经理 / 店长 / 总部运营 | `tok_member_01` / `tok_region_01` / `tok_store_01` / `tok_hq_01` | L2 |

## 已知边界

- 单机演示环境，未覆盖真实并发与长期运行稳定性
- LLM 叙述层默认离线模板（未接真实 API Key）
- 冻结的可选能力（`POST /api/world/advance`、`POST /api/agent/review`、调拨/触达/客服动作）后端 API 保留，恢复方式见 docs/06 审计报告
