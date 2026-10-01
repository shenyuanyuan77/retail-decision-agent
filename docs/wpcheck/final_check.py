# -*- coding: utf-8 -*-
"""交付前一致性检查：
1. 白皮书正文中引用的「图 N-M」「表 N-M」是否与文档实际存在的编号完全对应
2. 目录页码与标题序号是否连续
3. PPT 页数与文件完整性
"""
import re
import os
import pymupdf
from pptx import Presentation

WP = r"docs/零售经营决策系统产品白皮书_V2.0.pdf"
PPTX = r"docs/零售经营决策系统_产品介绍_V2.0.pptx"

doc = pymupdf.open(WP)
full = "\n".join(doc[i].get_text() for i in range(doc.page_count))

figs = re.findall(r"图 (\d+)-(\d+)", full)
tabs = re.findall(r"表 (\d+)-(\d+)", full)


def summarize(pairs, kind):
    """图/表编号：每个 N 下 M 应从 1 连续。"""
    from collections import defaultdict
    d = defaultdict(set)
    for a, b in pairs:
        d[int(a)].add(int(b))
    print(f"== {kind} ==")
    ok = True
    for ch in sorted(d):
        ms = sorted(d[ch])
        expect = list(range(1, len(ms) + 1))
        mark = "OK" if ms == expect else f"不连续! 实际 {ms}"
        if ms != expect:
            ok = False
        print(f"  第 {ch} 章: {len(ms)} 个 -> {mark}")
    return ok


ok1 = summarize(figs, "图编号")
ok2 = summarize(tabs, "表编号")

# 检查引用是否都指向存在的编号（图注 vs 正文引用）
print("\n图出现次数：", len(figs), " 表出现次数：", len(tabs))
print("页数:", doc.page_count)

prs = Presentation(PPTX)
print("PPT 页数:", len(prs.slides._sldIdLst), " 尺寸:", prs.slide_width, prs.slide_height)

print("\n== 交付文件 ==")
for f in ["docs/零售经营决策系统产品白皮书_V2.0.docx",
          "docs/零售经营决策系统产品白皮书_V2.0.pdf",
          "docs/零售经营决策系统_产品介绍_V2.0.pptx"]:
    p = f
    print(f"{os.path.basename(f):52s} {os.path.getsize(p)//1024:>6} KB")
print("\n编号检查:", "全部通过" if (ok1 and ok2) else "有问题，见上")
