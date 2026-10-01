# -*- coding: utf-8 -*-
"""用 Word COM 打开 docx：更新目录域 → 保存 → 导出 PDF（页码与目录才正确）。"""
import os
import sys
import win32com.client as win32

DOCX = os.path.abspath(sys.argv[1])
PDF = os.path.splitext(DOCX)[0] + ".pdf"

word = win32.gencache.EnsureDispatch("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
try:
    doc = word.Documents.Open(DOCX, ReadOnly=False)
    # 更新所有目录与域
    for toc in doc.TablesOfContents:
        toc.Update()
    doc.Fields.Update()
    doc.Repaginate()
    doc.Save()
    doc.SaveAs(PDF, FileFormat=17)   # wdFormatPDF
    pages = doc.ComputeStatistics(2)  # wdStatisticPages
    words = doc.ComputeStatistics(0)  # wdStatisticWords
    print(f"pages={pages} words={words}")
    doc.Close(SaveChanges=0)
finally:
    word.Quit()
print("PDF:", PDF, os.path.getsize(PDF) // 1024, "KB")
