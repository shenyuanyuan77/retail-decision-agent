# -*- coding: utf-8 -*-
"""为文档与 PPT 准备尺寸合适的图：裁剪超长截图、统一输出到 assets-doc。"""
import os
from PIL import Image

SRC = r"docs/whitepaper-assets-v2"
OUT = r"docs/whitepaper-assets-v2/doc"
os.makedirs(OUT, exist_ok=True)


def crop(src, box, out, label):
    im = Image.open(os.path.join(SRC, src))
    c = im.crop(box)
    c.save(os.path.join(OUT, out))
    ratio = c.size[0] / c.size[1]
    print(f"{label:40s} {c.size[0]}x{c.size[1]}  ratio={ratio:.2f}  -> {out}")


# 异常详情（缺货型）：上半部 = 检测证据 + 原因分析 + 结论
crop("shot-anomaly-detail-stockout.png", (0, 0, 3200, 2820), "fig-detail-evidence.png", "异常详情·证据链+根因")
# 下半部 = 建议方案（补货/促销 + 约束 + ROI）
crop("shot-anomaly-detail-stockout.png", (0, 2750, 3200, 4716), "fig-detail-suggest.png", "异常详情·建议方案")
# 异常列表：取前 2100（含列表头部与严重度分布）
crop("shot-anomalies.png", (0, 0, 3200, 2100), "fig-anomalies-top.png", "异常中心·列表")
# 审计日志：trace 过滤 + 前 2100
crop("shot-audit-trace.png", (0, 0, 3200, 2100), "fig-audit-trace-top.png", "审计日志·trace 过滤")
# 审计总览：前 2100（不带过滤）
crop("shot-audit.png", (0, 0, 3200, 2100), "fig-audit-top.png", "审计日志·总览")

# 直接复制不需裁剪的
import shutil
for f in ["shot-overview.png", "shot-decisions.png", "shot-approvals.png",
          "shot-executions.png", "shot-executions-view.png", "shot-api-docs.png",
          "shot-anomalies-view.png", "shot-audit-trace-view.png",
          "shot-anomaly-detail-promo.png",
          "diagram-architecture.png", "diagram-flow.png",
          "diagram-governance.png", "diagram-deploy.png"]:
    shutil.copy(os.path.join(SRC, f), os.path.join(OUT, f))
print("\n== doc assets ==")
for f in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, f)
    im = Image.open(p)
    print(f"{f:36s} {im.size[0]}x{im.size[1]}  ratio={im.size[0]/im.size[1]:.2f}  {os.path.getsize(p)//1024}KB")
