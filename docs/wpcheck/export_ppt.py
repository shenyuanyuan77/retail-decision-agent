# -*- coding: utf-8 -*-
"""用 PowerPoint COM 把 PPTX 导出为 PNG，供逐页视觉检查。"""
import os
import sys
import glob
import shutil
import win32com.client as win32

PPTX = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else r"docs/wpcheck/pptslides")
if os.path.isdir(OUT):
    shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)

app = win32.Dispatch("PowerPoint.Application")
pres = app.Presentations.Open(PPTX, WithWindow=False)
try:
    pres.Export(OUT, "PNG", 1600, 900)
finally:
    pres.Close()
    app.Quit()

files = sorted(glob.glob(os.path.join(OUT, "*.PNG")) + glob.glob(os.path.join(OUT, "*.png")))
print("exported", len(files), "slides")
for f in files[:5]:
    print(" ", os.path.basename(f))
