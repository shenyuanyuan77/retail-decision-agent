# -*- coding: utf-8 -*-
"""逐页渲染 PDF 为 PNG，供视觉检查（排版、图注、表格、分页）。"""
import os
import sys
import pymupdf

PDF = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else r"docs/wpcheck/pdfpages"
os.makedirs(OUT, exist_ok=True)

doc = pymupdf.open(PDF)
print("pages:", doc.page_count)
for i in range(doc.page_count):
    pix = doc[i].get_pixmap(dpi=100)
    pix.save(os.path.join(OUT, f"p{i+1:02d}.png"))
print("rendered to", OUT)

# 拼接若干页为概览图（每行 6 页）
from PIL import Image
files = sorted(f for f in os.listdir(OUT) if f.endswith(".png"))
thumbs = []
tw = 320
for f in files:
    im = Image.open(os.path.join(OUT, f))
    th = int(im.size[1] * tw / im.size[0])
    thumbs.append(im.resize((tw, th)))
cols = 7
rows = (len(thumbs) + cols - 1) // cols
ch = max(t.size[1] for t in thumbs)
sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (ch + 8) + 8), "#dddddd")
for idx, t in enumerate(thumbs):
    r, c = divmod(idx, cols)
    sheet.paste(t, (8 + c * (tw + 8), 8 + r * (ch + 8)))
sheet.save(os.path.join(OUT, "_contact.png"))
print("contact sheet:", sheet.size)
