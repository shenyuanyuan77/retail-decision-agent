# -*- coding: utf-8 -*-
"""异常检测统计算法：滚动中位数 / MAD / z-score / 环比 / 同比。传统算法负责发现和计算。"""
from statistics import median


def rolling_median(values: list[float], window: int = 28) -> list[float]:
    out = []
    for i in range(len(values)):
        lo = max(0, i - window)
        out.append(median(values[lo:i + 1]))
    return out


def med(values: list[float]) -> float:
    return median(values) if values else 0.0


def mad(values: list[float], m: float | None = None) -> float:
    """中位数绝对偏差；为 0 时回退到 0.25×med 保证 z-score 有意义。"""
    if not values:
        return 0.0
    m = med(values) if m is None else m
    d = median([abs(v - m) for v in values])
    return d if d > 0 else max(0.25 * abs(m), 0.5)


def zscore(x: float, m: float, d: float) -> float:
    return (x - m) / d if d else 0.0


def mom_ratio(cur: float, prev: float) -> float:
    """环比：相对上一周期变化率。"""
    return (cur - prev) / prev if prev else 0.0


def yoy_ratio(cur: float, same_period_prev: float) -> float:
    """同比（此处用 28 天前同期代理）。"""
    return (cur - same_period_prev) / same_period_prev if same_period_prev else 0.0
