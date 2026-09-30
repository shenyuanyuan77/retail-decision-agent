# -*- coding: utf-8 -*-
"""Mock 世界因果模型：品类定义 + 需求函数 + 天气/竞品/节假日基线。

生成器（180 天历史）、异常注入器、时间推演器（T+N）共用同一模型，
保证数据可重复生成（固定种子）且异常有数据证据。
"""
import math
import random
from datetime import date, timedelta

# 品类: (code, name, 保质期天数|None, 天气敏感度, 价格区间, 基础日销)
CATEGORIES = [
    ("C01", "饮料", None, 0.35, (3, 15), 1.1),
    ("C02", "冰品", 180, 0.50, (5, 20), 0.7),
    ("C03", "啤酒", 365, 0.30, (6, 18), 0.8),
    ("C04", "零食", 270, 0.10, (5, 30), 1.2),
    ("C05", "烘焙", 5, 0.15, (8, 30), 0.9),
    ("C06", "乳品", 14, 0.10, (6, 25), 1.0),
    ("C07", "生鲜", 3, 0.20, (5, 40), 1.3),
    ("C08", "粮油", 365, 0.05, (15, 80), 0.6),
    ("C09", "调味品", 540, 0.05, (6, 30), 0.5),
    ("C10", "日化", None, 0.05, (10, 50), 0.6),
    ("C11", "家清", None, 0.05, (8, 45), 0.5),
    ("C12", "纸品", None, 0.05, (10, 40), 0.6),
    ("C13", "个护", None, 0.05, (10, 60), 0.5),
    ("C14", "母婴", None, 0.05, (20, 120), 0.4),
    ("C15", "宠物", None, 0.05, (15, 90), 0.3),
    ("C16", "小家电", None, 0.08, (50, 400), 0.2),
    ("C17", "文具", None, 0.05, (3, 20), 0.4),
    ("C18", "家纺", None, 0.15, (30, 200), 0.25),
    ("C19", "保暖用品", None, 0.60, (20, 150), 0.3),
    ("C20", "雨具", None, 0.70, (10, 60), 0.2),
]

REGIONS = [
    ("R-east", "华东区", ["上海", "杭州", "南京"]),
    ("R-north", "华北区", ["北京", "天津"]),
    ("R-south", "华南区", ["广州", "深圳"]),
    ("R-west", "华西区", ["成都", "重庆"]),
    ("R-central", "华中区", ["武汉", "长沙"]),
]

TIER_FACTOR = {"flagship": 1.6, "large": 1.15, "standard": 0.8}
TIER_ASSORT = {"flagship": 1.00, "large": 0.72, "standard": 0.48}

# 天气对各品类销量的影响系数
WEATHER_CATEGORY_EFFECT = {
    "hot":         {"C02": 1.45, "C01": 1.30, "C03": 1.25, "C19": 0.80, "C07": 1.10},
    "cold_wave":   {"C19": 1.55, "C18": 1.30, "C01": 0.72, "C02": 0.55, "C03": 0.80},
    "rain":        {"C20": 1.90, "C07": 0.88},
    "storm":       {"C20": 2.30, "C07": 0.80},
}
WEATHER_ALL_EFFECT = {"rain": 0.92, "storm": 0.85}  # 全品类客流影响

# 固定节假日（演示窗口 2026-04 ~ 2026-10）
HOLIDAYS = {
    "2026-04-04": "清明节", "2026-04-05": "清明节", "2026-04-06": "清明节",
    "2026-05-01": "劳动节", "2026-05-02": "劳动节", "2026-05-03": "劳动节",
    "2026-05-04": "劳动节", "2026-05-05": "劳动节",
    "2026-06-19": "端午节", "2026-06-20": "端午节", "2026-06-21": "端午节",
    "2026-09-25": "中秋节", "2026-09-26": "中秋节",
    "2026-10-01": "国庆节", "2026-10-02": "国庆节", "2026-10-03": "国庆节",
}


def calendar_factors(d: date) -> dict:
    is_weekend = 1 if d.weekday() >= 5 else 0
    holiday_name = HOLIDAYS.get(d.isoformat(), "")
    return {
        "is_weekend": is_weekend,
        "is_holiday": 1 if holiday_name else 0,
        "holiday_name": holiday_name,
        "is_member_day": 1 if d.day == 18 else 0,
        "weekday_factor": {5: 1.32, 6: 1.28, 4: 1.10}.get(d.weekday(), 1.0),
        "holiday_factor": 1.45 if holiday_name else 1.0,
        "member_day_factor": 1.20 if d.day == 18 else 1.0,
    }


def weather_for_date(rng: random.Random, d: date, city: str) -> dict:
    """按季节生成天气（确定性：调用方保证 rng 序列确定）。"""
    m = d.month
    if m in (7, 8):
        base_hi, base_lo = 34, 26
    elif m in (6, 9):
        base_hi, base_lo = 30, 22
    elif m in (5, 10):
        base_hi, base_lo = 26, 18
    else:
        base_hi, base_lo = 21, 13
    r = rng.random()
    if m in (7, 8) and r < 0.10:
        cond = "hot"
    elif r < 0.02 and m in (11, 12, 1, 2, 3):
        cond = "cold_wave"
    elif r < 0.20:
        cond = "rain"
    elif r < 0.23:
        cond = "storm"
    elif r < 0.50:
        cond = "overcast"
    else:
        cond = "sunny"
    return {
        "condition": cond,
        "temp_high": round(base_hi + rng.uniform(-3, 3), 1),
        "temp_low": round(base_lo + rng.uniform(-3, 3), 1),
        "precip_mm": round(rng.uniform(5, 60), 1) if cond in ("rain", "storm") else 0.0,
    }


def weather_qty_factor(condition: str, category_id: str) -> float:
    f = WEATHER_CATEGORY_EFFECT.get(condition, {}).get(category_id, 1.0)
    allf = WEATHER_ALL_EFFECT.get(condition, 1.0)
    return f * allf


def baseline_daily_qty(mu: float, cal: dict, weather_cond: str, category_id: str,
                       promo_lift: float, rng: random.Random) -> int:
    """日需求 = 基线μ × 日历 × 天气 × 促销，Poisson 噪声。"""
    lam = (mu * cal["weekday_factor"] * cal["holiday_factor"]
           * cal["member_day_factor"] * weather_qty_factor(weather_cond, category_id)
           * promo_lift)
    lam = max(0.0, lam)
    return poisson(rng, lam)


def member_qty_share(rng: random.Random, promo: bool) -> float:
    return 0.62 if promo else rng.uniform(0.45, 0.60)


def poisson(rng: random.Random, lam: float) -> int:
    """纯 Python Poisson 采样（Knuth 算法，λ 大时用正态近似）。"""
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(rng.gauss(lam, math.sqrt(lam)) + 0.5))
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1
