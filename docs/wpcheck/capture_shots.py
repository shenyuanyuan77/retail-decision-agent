# -*- coding: utf-8 -*-
"""采集白皮书/PPT 用真实页面截图（高清 2x）。

覆盖：经营总览 / 异常中心 / 异常详情（证据链+根因 Top3）/ 补货·促销建议 /
审批中心（含待审批）/ 执行记录 / 审计日志（trace 过滤）/ 接口文档。
"""
import asyncio, json, os, urllib.request
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8300"
OUT = r"docs/whitepaper-assets-v2"
os.makedirs(OUT, exist_ok=True)

# 取三条故事线对应的异常 ID（证据链最完整）
g = lambda p: json.load(urllib.request.urlopen(BASE + p))
items = g("/api/agent/anomalies?limit=300")["items"]
story = {x["storyline_id"]: x for x in items if x.get("storyline_id")}
print("storyline anomalies:", {k: v["id"] for k, v in story.items()})

SHOTS = [
    ("overview", "#/overview", None),
    ("anomalies", "#/anomalies", None),
    ("decisions", "#/decisions", None),
    ("approvals", "#/approvals", None),
    ("executions", "#/executions", None),
    ("audit", "#/audit", None),
]
DETAILS = [
    ("anomaly-detail-stockout", story.get("sl-stockout-01", {}).get("id")),
    ("anomaly-detail-promo", story.get("sl-promo-01", {}).get("id")),
    ("anomaly-detail-complaint", story.get("sl-complaint-01", {}).get("id")),
]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
        for name, route, _ in SHOTS:
            await pg.goto(BASE + "/" + route, wait_until="networkidle")
            await pg.wait_for_timeout(1500)
            await pg.screenshot(path=os.path.join(OUT, f"shot-{name}.png"), full_page=True)
            print("captured", name)
        for name, aid in DETAILS:
            if not aid:
                print("skip", name)
                continue
            await pg.goto(f"{BASE}/#/anomaly/{aid}", wait_until="networkidle")
            await pg.wait_for_timeout(2000)
            await pg.screenshot(path=os.path.join(OUT, f"shot-{name}.png"), full_page=True)
            print("captured", name)
        # 接口文档（Swagger）
        await pg.goto(BASE + "/docs", wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        await pg.screenshot(path=os.path.join(OUT, "shot-api-docs.png"), clip={"x": 0, "y": 0, "width": 1600, "height": 1000})
        print("captured api-docs")
        await b.close()

asyncio.run(main())
