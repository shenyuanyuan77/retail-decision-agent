# -*- coding: utf-8 -*-
"""一键演示脚本：完整走一遍「目标—感知—诊断—决策—执行—治理—评估」闭环。

用法:
    python scripts/demo.py            # 全量规模（180天/50店/500SKU，首次约 4-6 分钟）
    python scripts/demo.py --small    # 小规模快速演示（45天/12店/100SKU，约 1 分钟）
步骤:
    1. 重新生成 Mock 数据并注入 3 类异常故事线
    2. 感知扫描（算法发现异常）
    3. 诊断归因（Top3 根因 + 证据链）
    4. 决策生成（补货/调拨/促销/触达/客服，含约束与 ROI）
    5. 执行（低风险自动；高风险创建审批单）
    6. 治理（风控审批人通过高风险审批 → 执行）
    7. T+7 世界推演（到货/促销效果/库存门控的真实后果）
    8. 评估复盘（前后指标对比 + 策略权重更新）
"""
import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", action="store_true", help="小规模快速演示")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    scale = dict(days=45, stores=12, skus=100) if args.small else \
        dict(days=180, stores=50, skus=500)

    from app.bootstrap import bootstrap
    from app.core.db import session_scope
    from app.agents import orchestrator
    from app.models import Anomaly, Storyline, Approval, DecisionCard
    from sqlmodel import select

    t0 = time.time()
    print("=" * 72)
    print("全国连锁零售经营决策 Agent —— 端到端演示")
    print(f"规模: {scale['days']}天 × {scale['stores']}店 × {scale['skus']}SKU, 种子={args.seed}")
    print("=" * 72)

    print("\n[1/6] 生成 Mock 世界数据 + 注入 3 类异常故事线 …")
    result = bootstrap(**scale, seed=args.seed)
    g = result["generation"]
    print(f"      销售 {g['sales_rows']:,} 行 | 库存 {g['inventory_rows']:,} | 工单 {g['ticket_rows']:,}"
          f" | 会员 {g['members']:,} | 促销 {g['campaigns']} | 窗口 {g['period'][0]}~{g['period'][1]}")
    for st in result["storylines"]:
        print(f"      · {st['type']:<16} {st['store']}/{st['product']} 真因={st['truth_root_cause']}")

    print("\n[2/6] 感知扫描（滚动中位数+MAD+z-score）…")
    with session_scope() as s:
        r = orchestrator.run_pipeline(s)
        for step in r["steps"]:
            print(f"      {step['step']:<12} {list(step.values())[1]}")
        trace = r["trace_id"]

        print("\n[3/6] 三条故事线诊断结果（Top 根因）:")
        for sl in s.exec(select(Storyline)).all():
            cands = s.exec(select(Anomaly).where(
                Anomaly.store_id == sl.store_id,
                Anomaly.product_id == sl.product_id,
                Anomaly.window_start >= sl.start_date).order_by(
                Anomaly.detected_at.desc())).all()
            a = cands[0] if cands else None
            if not a:
                print(f"      {sl.type}: 未检出!")
                continue
            dg = s.exec(select(Anomaly).where(Anomaly.id == a.id)).first()
            from app.models import Diagnosis
            d = s.exec(select(Diagnosis).where(Diagnosis.anomaly_id == a.id)).first()
            rcs = json.loads(d.root_causes)
            hit = "✓命中" if any(x["code"] == sl.truth_root_cause for x in rcs) else "✗未命中"
            print(f"      {sl.type:<16} {hit} → " +
                  ", ".join(f"{x['name']}({x['confidence']},{len(x['evidence'])}证据)" for x in rcs))

        n_auto = sum(1 for x in s.exec(select(DecisionCard)).all() if not x.requires_approval)
        n_high = sum(1 for x in s.exec(select(DecisionCard)).all() if x.requires_approval)
        print(f"\n[4/6] 决策卡: 自动执行候选 {n_auto} 张，高风险待审批 {n_high} 张")

        print("\n[5/6] 治理审批（风控审批人通过全部高风险项）→ 执行 → T+7 推演 → 复盘 …")
        full = orchestrator.run_demo_cycle(s)
        print(f"      审批通过 {full['approvals_approved']} | 审批后执行 {full['executed_after_approval']}"
              f" | 推演至 {full['world_advanced']['new_today']}"
              f"（新增销售 {full['world_advanced']['sales_rows']:,} 行）| 复盘报告 {full['reviews']} 份")

        print("\n[6/6] Agent 评估指标:")
        m = full["metrics"]
        for k, v in m.items():
            print(f"      {k:<36} {v}")

        print(f"\n闭环 trace_id = {trace}（可在审计日志页查询完整链路）")
        print(f"总耗时 {time.time() - t0:.0f}s")
        print("\n▶ 打开看板: http://127.0.0.1:8300  （python -m uvicorn app.main:app --port 8300）")
        print("  演示路径: 异常中心(仅故事线) → 异常详情(证据链/根因) → 审批中心 → 执行记录 → 复盘报告")


if __name__ == "__main__":
    main()
