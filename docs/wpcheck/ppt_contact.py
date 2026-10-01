# -*- coding: utf-8 -*-
"""把导出的 PPT 幻灯片拼成概览图（按页序），便于快速通检。"""
import os
import re
from PIL import Image

D = r"docs/wpcheck/pptslides"
files = [f for f in os.listdir(D) if f.lower().endswith(".png")]
seen = {}
for f in files:
    m = re.search(r"(\d+)", f)
    if m:
        n = int(m.group(1))
        p = os.path.join(D, f)
        if n not in seen or os.path.getsize(p) > os.path.getsize(seen[n]):
            seen[n] = p
order = sorted(seen)
print("slides:", order)

tw = 620
thumbs = []
for n in order:
    im = Image.open(seen[n]).convert("RGB")
    th = int(im.size[1] * tw / im.size[0])
    thumbs.append(im.resize((tw, th)))

cols = 4
rows = (len(thumbs) + cols - 1) // cols
ch = max(t.size[1] for t in thumbs)
sheet = Image.new("RGB", (cols * (tw + 10) + 10, rows * (ch + 10) + 10), "#cccccc")
for i, t in enumerate(thumbs):
    r, c = divmod(i, cols)
    sheet.paste(t, (10 + c * (tw + 10), 10 + r * (ch + 10)))
out = os.path.join(D, "_contact.png")
sheet.save(out)
print("contact:", sheet.size, "->", out)

# 同时保存单页便于细看
for n in order[:6]:
    Image.open(seen[n]).convert("RGB").save(os.path.join(D, f"slide{n:02d}.png"))
print("done")
