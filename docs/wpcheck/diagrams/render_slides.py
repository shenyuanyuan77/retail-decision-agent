# -*- coding: utf-8 -*-
"""渲染 PPT 专用示意图（比例更贴合 16:9 页面）。"""
import asyncio, os
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, r"..\..\whitepaper-assets-v2"))
os.makedirs(OUT, exist_ok=True)

JOBS = [
    ("slide-flow.html", "slide-flow.png", "c"),
    ("slide-arch.html", "slide-arch.png", "c"),
    ("slide-deploy.html", "slide-deploy.png", "c"),
    ("slide-gov.html", "slide-gov.png", "c"),
]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for html, png, sel in JOBS:
            src = os.path.join(HERE, html)
            pg = await b.new_page(viewport={"width": 1700, "height": 1200}, device_scale_factor=2)
            await pg.goto("file:///" + src.replace("\\", "/"))
            await pg.wait_for_timeout(700)
            el = await pg.query_selector("#" + sel)
            await el.screenshot(path=os.path.join(OUT, png))
            print("rendered", png)
            await pg.close()
        await b.close()

asyncio.run(main())

from PIL import Image
for f in ["slide-flow.png", "slide-arch.png", "slide-deploy.png"]:
    p = os.path.join(OUT, f)
    im = Image.open(p)
    print(f"{f:22s} {im.size[0]}x{im.size[1]}  ratio={im.size[0]/im.size[1]:.2f}")
