# -*- coding: utf-8 -*-
"""把 HTML 示意图渲染为高分辨率 PNG（2x），供 Word / PPT 使用。"""
import asyncio, os, sys
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, r"..\..\whitepaper-assets-v2"))
os.makedirs(OUT, exist_ok=True)

JOBS = [
    ("arch.html", "diagram-architecture.png", "c"),
    ("flow.html", "diagram-flow.png", "c"),
    ("gov.html", "diagram-governance.png", "c"),
    ("deploy.html", "diagram-deploy.png", "c"),
]


async def main(names=None):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for html, png, sel in JOBS:
            if names and html not in names:
                continue
            src = os.path.join(HERE, html)
            if not os.path.exists(src):
                print("missing", html)
                continue
            pg = await b.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
            await pg.goto("file:///" + src.replace("\\", "/"))
            await pg.wait_for_timeout(700)
            el = await pg.query_selector("#" + sel)
            await el.screenshot(path=os.path.join(OUT, png))
            print("rendered", png)
            await pg.close()
        await b.close()

asyncio.run(main(sys.argv[1:] or None))

from PIL import Image
for f in sorted(os.listdir(OUT)):
    if f.startswith("diagram-"):
        im = Image.open(os.path.join(OUT, f))
        print(f"{f:34s} {im.size[0]}x{im.size[1]}  {os.path.getsize(os.path.join(OUT,f))//1024}KB")
