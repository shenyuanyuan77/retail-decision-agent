# -*- coding: utf-8 -*-
"""补拍：审计日志 trace 过滤后的视口级截图（适合文档排版），并输出全部截图尺寸清单。"""
import asyncio, json, os, urllib.request
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8300"
OUT = r"docs/whitepaper-assets-v2"

logs = json.load(urllib.request.urlopen(BASE + "/api/gov/audit-logs?limit=400"))["items"]
from collections import Counter
c = Counter(l["trace_id"] for l in logs if l.get("trace_id"))
best = c.most_common(1)[0][0]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1600, "height": 1050}, device_scale_factor=2)
        await pg.goto(BASE + "/#/audit", wait_until="networkidle")
        await pg.wait_for_timeout(1000)
        await pg.fill("#audit-trace", best)
        await pg.click("text=查询")
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path=os.path.join(OUT, "shot-audit-trace-view.png"))
        print("captured audit-trace-view")

        # 异常中心视口版（列表顶部，含严重度/偏差/时间窗）
        await pg.goto(BASE + "/#/anomalies", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path=os.path.join(OUT, "shot-anomalies-view.png"))
        print("captured anomalies-view")

        # 执行记录视口版
        await pg.goto(BASE + "/#/executions", wait_until="networkidle")
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path=os.path.join(OUT, "shot-executions-view.png"))
        print("captured executions-view")
        await b.close()

asyncio.run(main())

from PIL import Image
print("\n== assets ==")
for f in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, f)
    if f.lower().endswith(".png"):
        im = Image.open(p)
        print(f"{f:36s} {im.size[0]}x{im.size[1]}  {os.path.getsize(p)//1024}KB")
