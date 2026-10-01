# -*- coding: utf-8 -*-
"""把方向对比画布里的每一屏单独截图，用于逐屏视觉检查。"""
import asyncio, os, sys
from playwright.async_api import async_playwright

SRC = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
os.makedirs(OUT, exist_ok=True)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
        await pg.goto("file:///" + SRC.replace("\\", "/"))
        await pg.wait_for_timeout(900)
        screens = await pg.query_selector_all(".scr")
        print("screens:", len(screens))
        cells = await pg.query_selector_all("figure.cell")
        for i, el in enumerate(screens):
            label = ""
            if i < len(cells):
                cap = await cells[i].query_selector("figcaption")
                if cap:
                    label = (await cap.inner_text()).replace("\n", " ")
            grp = await el.evaluate("""e => {
                const s = e.closest('section'); const g = s && s.querySelector('.gcode');
                return g ? g.textContent.trim() : '?';
            }""")
            await el.screenshot(path=os.path.join(OUT, f"{grp}-{i+1:02d}.png"))
            print(f"{grp}-{i+1:02d}.png  {label}")
        # 整页概览
        await pg.screenshot(path=os.path.join(OUT, "_full.png"), full_page=True)
        await b.close()

asyncio.run(main())
