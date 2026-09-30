# -*- coding: utf-8 -*-
"""一键引导：初始化库 → 生成数据 → 注入异常。

CLI: python -m app.bootstrap --days 180 --stores 50 --skus 500 --seed 42 [--no-inject]
"""
import argparse
import json

from .core.db import init_db, session_scope
from .governance.auth import seed_users
from .world.generator import generate_all
from .world.injector import inject_all


def bootstrap(*, days: int = 180, stores: int = 50, skus: int = 500, seed: int = 42,
              inject: bool = True, reset: bool = True) -> dict:
    init_db()
    with session_scope() as session:
        seed_users(session)
        if reset:
            _clear_agent_state(session)
        stats = generate_all(session, days=days, n_stores=stores, n_skus=skus,
                             seed=seed, reset=reset)
        stories = inject_all(session, seed=seed) if inject else []
    return {"generation": stats, "storylines": stories}


def _clear_agent_state(session):
    """重建世界时清空智能体运行痕迹（异常/诊断/决策/审批/执行/复盘/权重/审计/幂等）。"""
    from sqlalchemy import delete
    from .models import (Anomaly, Approval, AuditLog, DecisionCard, Diagnosis,
                         Execution, IdempotencyRecord, ReviewReport, Storyline,
                         StrategyWeight)
    for t in (ReviewReport, StrategyWeight, Execution, Approval, DecisionCard,
              Diagnosis, Anomaly, Storyline, AuditLog, IdempotencyRecord):
        session.execute(delete(t))
    session.commit()


def main():
    ap = argparse.ArgumentParser(description="生成 Mock 数据并注入异常故事线")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--stores", type=int, default=50)
    ap.add_argument("--skus", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-inject", action="store_true")
    ap.add_argument("--no-reset", action="store_true")
    args = ap.parse_args()
    result = bootstrap(days=args.days, stores=args.stores, skus=args.skus, seed=args.seed,
                       inject=not args.no_inject, reset=not args.no_reset)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
