# -*- coding: utf-8 -*-
"""数据生成入口：python scripts/generate.py [--days 180 --stores 50 --skus 500 --seed 42]"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.bootstrap import bootstrap  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--stores", type=int, default=50)
    ap.add_argument("--skus", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-inject", action="store_true")
    args = ap.parse_args()
    r = bootstrap(days=args.days, stores=args.stores, skus=args.skus,
                  seed=args.seed, inject=not args.no_inject)
    g = r["generation"]
    print(f"生成完成: 销售 {g['sales_rows']:,} 行 | 门店 {g['n_stores']} | SKU {g['n_skus']} "
          f"| 窗口 {g['period'][0]} ~ {g['period'][1]}")
    for st in r["storylines"]:
        print(f"  故事线 {st['type']:<16} {st['store']}/{st['product']} "
              f"真因={st['truth_root_cause']} 窗口={st['window'][0]}~{st['window'][1]}")


if __name__ == "__main__":
    main()
