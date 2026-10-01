# -*- coding: utf-8 -*-
"""把编辑部方向的 SVG 图渲染成高分辨率 PNG（PPT 用）。"""
import asyncio, os
from playwright.async_api import async_playwright

D = os.path.abspath(r"docs/whitepaper-assets-v2/ppt-editorial")
FILES = ["chart-stockout", "chart-hypotheses", "chart-loop", "chart-acceptance"]

WRAP = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0}}body{{background:#F7F5F0}}
svg{{display:block}}
</style></head><body>{}</body></html>"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1180, "height": 470}, device_scale_factor=2)
        for f in FILES:
            svg = open(os.path.join(D, f + ".svg"), encoding="utf-8").read()
            await pg.set_content(WRAP.format(svg))
            await pg.wait_for_timeout(450)
            await pg.screenshot(path=os.path.join(D, f + ".png"))
            print("rendered", f + ".png")
        await b.close()

asyncio.run(main())

from PIL import Image
for f in FILES:
    p = os.path.join(D, f + ".png")
    im = Image.open(p)
    print(f"{f}.png  {im.size[0]}x{im.size[1]}  {os.path.getsize(p)//1024}KB")
