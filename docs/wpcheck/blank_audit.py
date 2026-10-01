# -*- coding: utf-8 -*-
"""排除页眉页脚后，统计正文区域的留白，定位需要收紧排版的页面。"""
import pymupdf
from PIL import Image
import numpy as np

PDF = r"docs/零售经营决策系统产品白皮书_V2.0.pdf"
doc = pymupdf.open(PDF)

print("page  body_top  body_bottom  fill_ratio")
bad = []
for i in range(doc.page_count):
    pix = doc[i].get_pixmap(dpi=60)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    a = np.asarray(im.convert("L"))
    h = a.shape[0]
    # 正文区域：排除页眉（上 8%）与页脚（下 8%）
    body = a[int(h * 0.09):int(h * 0.92)]
    ink = (body < 240).sum(axis=1)
    rows = np.where(ink > 2)[0]
    if len(rows) == 0:
        print(f"{i+1:>4}   EMPTY")
        continue
    top, bot = rows[0], rows[-1]
    fill = (bot - top) / body.shape[0]
    flag = "  <== 留白偏大" if fill < 0.70 else ""
    print(f"{i+1:>4}   {top/body.shape[0]:.2f}      {bot/body.shape[0]:.2f}       {fill:.2f}{flag}")
    if fill < 0.70:
        bad.append(i + 1)
print("\n需要关注的页面:", bad)
