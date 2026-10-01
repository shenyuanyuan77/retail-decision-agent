# -*- coding: utf-8 -*-
"""零售经营决策系统 · 产品介绍 PPT —— 编辑部方向（Editorial）

视觉体系
  纸白 #F7F5F0 / 墨黑 #17161A / 朱红 #C0392B（唯一强调色）/ 暖灰 #6B6660
  衬线标题（Noto Serif SC）+ 无衬线正文（HarmonyOS Sans SC）+ 等宽数字（Cascadia Mono）
  细线分隔、大留白、一页一个观点；图形化图表为主，少量真实截图作证据锚点
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CH = os.path.join(ROOT, "docs", "whitepaper-assets-v2", "ppt-editorial")
SN = os.path.join(ROOT, "docs", "whitepaper-assets-v2", "doc")
OUT = os.path.join(ROOT, "docs", "零售经营决策系统_产品介绍_V2.0.pptx")

PAPER = RGBColor(0xF7, 0xF5, 0xF0)
INK = RGBColor(0x17, 0x16, 0x1A)
RED = RGBColor(0xC0, 0x39, 0x2B)
MID = RGBColor(0x6B, 0x66, 0x60)
GREY = RGBColor(0x8A, 0x81, 0x75)
FAINT = RGBColor(0xB5, 0xAE, 0xA3)
LINE = RGBColor(0xD9, 0xD3, 0xC9)
LINE2 = RGBColor(0xE7, 0xE2, 0xDA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x3F, 0x6B, 0x4A)

SERIF = "Noto Serif SC"
SANS = "HarmonyOS Sans SC"
MONO = "Cascadia Mono"

W, H = 13.333, 7.5
prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
BLANK = prs.slide_layouts[6]
PAGE = [0]


def slide(bg=PAPER):
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    r.fill.solid()
    r.fill.fore_color.rgb = bg
    r.line.fill.background()
    r.shadow.inherit = False
    PAGE[0] += 1
    return s


def line(s, x, y, w, color=LINE, h=0.014):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = color
    r.line.fill.background()
    r.shadow.inherit = False
    return r


def block(s, x, y, w, h, color):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = color
    r.line.fill.background()
    r.shadow.inherit = False
    return r


def text(s, x, y, w, h, paras, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         spacing=1.25, after=4):
    """paras: list[list[(text, size, bold, color, font)]]"""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(after)
        for item in para:
            t, size, bold, color = item[0], item[1], item[2], item[3]
            fam = item[4] if len(item) > 4 else SANS
            r = p.add_run()
            r.text = t
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
            r.font.name = fam
        # 中文字体也要设定（python-pptx 只设 latin）
        for item in para:
            pass
    return tb


def cn_font(shape, fam):
    """把 textbox 内所有 run 的东亚字体也设为 fam。"""
    from pptx.oxml.ns import qn
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            rPr = r._r.get_or_add_rPr()
            ea = rPr.find(qn('a:ea'))
            if ea is None:
                ea = rPr.makeelement(qn('a:ea'), {})
                rPr.append(ea)
            ea.set('typeface', fam)


def txt(s, x, y, w, h, paras, fam=SANS, **kw):
    tb = text(s, x, y, w, h, paras, **kw)
    cn_font(tb, fam)
    return tb


def pic(s, path, x, y, w, h):
    im = Image.open(path)
    ratio = im.size[0] / im.size[1]
    if ratio > w / h:
        pw, ph = w, w / ratio
    else:
        ph, pw = h, h * ratio
    s.shapes.add_picture(path, Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2),
                         Inches(pw), Inches(ph))


def page_run(kicker, no):
    """新建一页并画页眉：左标签 + 右页码。返回 (slide, 正文起始 y)。"""
    s = slide()
    line(s, 0.62, 0.62, 12.09, INK, 0.018)
    txt(s, 0.62, 0.30, 7.6, 0.28, [[(kicker, 11.5, False, GREY, MONO)]], spacing=1.0)
    txt(s, 0.62, 0.30, 12.09, 0.28,
        [[(f"{no:02d}", 11.5, True, INK, MONO)]], align=PP_ALIGN.RIGHT, spacing=1.0)
    return s, 1.06


def foot(s, note=""):
    txt(s, 0.62, 7.02, 9.6, 0.26, [[(note, 10, False, FAINT, SANS)]], spacing=1.0)
    txt(s, 0.62, 7.02, 12.09, 0.26,
        [[("零售经营决策系统 · 产品介绍 V2.0", 10, False, FAINT, MONO)]],
        align=PP_ALIGN.RIGHT, spacing=1.0)


# ==================================================== 01 封面
s = slide()
line(s, 0.62, 1.24, 12.09, INK, 0.02)
txt(s, 0.62, 0.86, 8.0, 0.3, [[("RETAIL DECISION AGENT", 12, False, GREY, MONO)]], spacing=1.0)
txt(s, 0.62, 0.86, 12.09, 0.3, [[("产品介绍 · V2.0", 12, False, GREY, MONO)]],
    align=PP_ALIGN.RIGHT, spacing=1.0)
txt(s, 0.62, 2.02, 11.0, 0.32, [[("2026 年 9 月 30 日 · 面向全国连锁零售企业", 13, False, RED, SANS)]], spacing=1.0)
txt(s, 0.62, 2.52, 11.9, 1.3, [[("零售经营决策系统", 66, True, INK, SERIF)]], spacing=1.02)
txt(s, 0.62, 3.86, 10.4, 1.0,
    [[("把「发现 → 归因 → 建议 → 执行」做成一条可审计的自动闭环，", 20, False, RGBColor(0x3A, 0x37, 0x33), SANS)],
     [("而不是再给门店加一张报表。", 20, False, RGBColor(0x3A, 0x37, 0x33), SANS)]], spacing=1.5)
line(s, 0.62, 5.62, 12.09, LINE)
items = [("自动发现异常", "统计检测主动扫描"), ("根因分析", "九类假设 + 证据链"),
         ("补货 / 促销建议", "约束检查 + ROI"), ("授权范围内执行", "低风险自动 · 高风险审批")]
for i, (t, d) in enumerate(items):
    x = 0.62 + i * 3.02
    txt(s, x, 5.86, 2.85, 0.3, [[(t, 13, True, INK, SANS)]], spacing=1.0)
    txt(s, x, 6.16, 2.85, 0.3, [[(d, 11.5, False, MID, SANS)]], spacing=1.0)
foot(s, "在线预览 https://shenyuanyuan77.github.io/retail-decision-agent/")

# ==================================================== 02 问题
s, y = page_run("问题 / THE PROBLEM", 2)
txt(s, 0.62, y + 0.20, 11.9, 1.15,
    [[("经营异常每天都在发生，", 34, True, INK, SERIF)],
     [("但发现它的人往往不是最该知道的人。", 34, True, INK, SERIF)]], spacing=1.18)
txt(s, 0.62, y + 1.52, 10.6, 0.5,
    [[("门店靠人巡检、靠经验判断。从异常发生到被处理，中间隔着好几层传递。", 14.5, False, MID, SANS)]], spacing=1.4)
line(s, 0.62, y + 2.22, 12.09, INK, 0.016)
prob = [("发现晚", "销量骤降往往在周会报表上才被看到，此时已经损失了数天销量。", "周报 → 损失数天"),
        ("归因难", "缺货、竞品、天气、客诉都能造成下跌，凭经验猜容易猜错方向。", "四类以上混淆因素"),
        ("动作慢", "分析完还要跨部门沟通，等补货到店，窗口期已经过去。", "跨部门传递"),
        ("不可控", "就算让系统自动执行，谁来保证它不会做出越界动作。", "缺少硬边界")]
for i, (t, d, tag) in enumerate(prob):
    x = 0.62 + i * 3.06
    if i:
        line(s, x - 0.14, y + 2.42, 0.014, LINE2, 1.9)
    txt(s, x, y + 2.42, 2.8, 0.36, [[(t, 19, True, INK, SERIF)]], spacing=1.0)
    txt(s, x, y + 2.94, 2.82, 1.0, [[(d, 12.5, False, MID, SANS)]], spacing=1.5)
    txt(s, x, y + 4.06, 2.82, 0.28, [[(tag, 11, False, RED, MONO)]], spacing=1.0)
line(s, 0.62, y + 4.62, 12.09, INK, 0.016)
txt(s, 0.62, y + 4.86, 12.09, 0.6,
    [[("传统数据看板只回答了「发生了什么」。", 16, True, INK, SERIF),
      ("  真正缺的是另外三件事：为什么发生、该怎么办、办了之后效果如何。", 16, False, MID, SANS)]], spacing=1.3)
foot(s, "50 店 · 500 SKU · 180 天 · 每天约 2.8 万个门店-SKU 组合待体检")

# ==================================================== 03 产品定位
s, y = page_run("产品定位 / POSITIONING", 3)
txt(s, 0.62, y + 0.18, 6.9, 1.6,
    [[("把「发现 → 归因 → 建议 → 执行」", 27, True, INK, SERIF)],
     [("做成一条自动闭环", 27, True, INK, SERIF)]], spacing=1.18)
txt(s, 0.62, y + 1.62, 6.5, 0.5,
    [[("并让每一步都可审计。接入门店、销售、库存供应链、会员、客服与外部数据六大系统。", 13, False, MID, SANS)]], spacing=1.45)
flow = [("自动发现", "持续扫描销售数据，主动发现销量异常，无需人工发起"),
        ("根因分析", "对每个异常并行验证九类假设，输出带证据链与置信度的根因 Top3"),
        ("建议生成", "按根因匹配打法库，生成补货或促销建议，含约束检查与成本收益估算"),
        ("授权执行", "低风险动作自动执行，高风险动作强制转人工审批，全程留痕")]
for i, (t, d) in enumerate(flow):
    yy = y + 2.30 + i * 0.78
    txt(s, 0.62, yy, 0.5, 0.3, [[(f"0{i+1}", 13, True, RED, SERIF)]], spacing=1.0)
    txt(s, 1.16, yy - 0.03, 1.86, 0.3, [[(t, 15, True, INK, SANS)]], spacing=1.0)
    txt(s, 3.10, yy, 3.86, 0.6, [[(d, 11.5, False, MID, SANS)]], spacing=1.35)
    if i < 3:
        line(s, 1.16, yy + 0.58, 5.8, LINE2)
# 右栏：设计立场
block(s, 7.55, y + 0.18, 5.16, 3.30, INK)
txt(s, 7.85, y + 0.48, 4.5, 0.36, [[("设计立场", 15, True, WHITE, SERIF)]], spacing=1.0)
line(s, 7.85, y + 0.94, 4.56, RGBColor(0x4A, 0x46, 0x40), 0.014)
txt(s, 7.85, y + 1.14, 4.56, 2.1,
    [[("系统不以「自动化」为唯一目标。", 14, False, RGBColor(0xC9, 0xC2, 0xB8), SANS)],
     [("所有高风险动作的判断权始终留在人手中，", 14, False, RGBColor(0xC9, 0xC2, 0xB8), SANS)],
     [("Agent 的服务身份硬上限为 L2。", 14, True, WHITE, SANS)]], spacing=1.6)
txt(s, 7.85, y + 2.96, 4.56, 0.4,
    [[("高风险动作 100% 转人工 · 拒绝同样留痕", 11.5, False, RGBColor(0xA8, 0xA0, 0x94), MONO)]], spacing=1.2)
line(s, 7.55, y + 3.78, 5.16, LINE)
txt(s, 7.55, y + 4.00, 5.16, 0.9,
    [[("与传统看板的本质区别", 12, True, INK, SANS)],
     [("看板回答「发生了什么」；本产品回答「为什么、怎么办、效果如何」，并把每一步交给可控可审计的 Agent 执行。", 11.5, False, MID, SANS)]],
    spacing=1.45)
foot(s)

# ==================================================== 04 七步闭环
s, y = page_run("工作方式 / THE LOOP", 4)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("一条异常，七个环节，环环相扣", 32, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.86, 11.0, 0.4,
    [[("从被发现，到被验证改善。每一步都留下可审计的痕迹。", 14, False, MID, SANS)]], spacing=1.35)
pic(s, os.path.join(CH, "chart-loop.png"), 0.62, y + 1.34, 12.09, 4.44)
foot(s, "七个环节由编排器以同一 trace_id 串联")

# ==================================================== 05 感知（真实时序）
s, y = page_run("能力 R2 · 感知 / PERCEPTION", 5)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("异常不是猜出来的，是从数据里算出来的", 32, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.86, 11.0, 0.4,
    [[("深圳 007 店 · 饮料 C01 · 商品 P00003：前 28 天日销稳定在 10 件，9 月 19 日起连续 12 天归零。", 14, False, MID, SANS)]], spacing=1.35)
pic(s, os.path.join(CH, "chart-stockout.png"), 0.62, y + 1.30, 8.44, 3.36)
# 右栏方法说明
bx = 9.28
line(s, bx, y + 1.30, 3.43, INK, 0.016)
txt(s, bx, y + 1.46, 3.43, 0.32, [[("检测算法", 13.5, True, INK, SERIF)]], spacing=1.0)
methods = [("建立基线", "前 28 天滚动中位数与 MAD（中位数绝对偏差）"),
           ("逐日打分", "近 14 天逐日计算 z-score 与偏差比例"),
           ("识别异常段", "连续 ≥2 天偏离成段，允许 1 天噪声桥接"),
           ("输出证据", "基线参数、逐日观测值与库存快照随异常同存")]
for i, (t, d) in enumerate(methods):
    yy = y + 1.92 + i * 0.66
    txt(s, bx, yy, 1.5, 0.28, [[(t, 12, True, INK, SANS)]], spacing=1.0)
    txt(s, bx, yy + 0.26, 3.43, 0.44, [[(d, 10.5, False, MID, SANS)]], spacing=1.3)
line(s, bx, y + 4.62, 3.43, INK, 0.016)
txt(s, bx, y + 4.78, 3.43, 0.5,
    [[("用统计而不是大模型", 12, True, RED, SANS)],
     [("同样的数据必须给出同样的结论。", 11, False, MID, SANS)]], spacing=1.4)
foot(s, "无需人工发起 · 支持每小时定时扫描")

# ==================================================== 06 诊断（假设验证）
s, y = page_run("能力 R3 · 诊断 / DIAGNOSIS", 6)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("九类假设逐一验证，只认证据不认感觉", 32, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.86, 11.0, 0.4,
    [[("证据 ≥2 条且方向相容者入选；证据不足时显式转人工，不强行给结论。", 14, False, MID, SANS)]], spacing=1.35)
pic(s, os.path.join(CH, "chart-hypotheses.png"), 0.62, y + 1.28, 9.30, 3.70)
bx = 10.14
line(s, bx, y + 1.30, 2.57, INK, 0.016)
txt(s, bx, y + 1.46, 2.57, 0.32, [[("证据从哪来", 13.5, True, INK, SERIF)]], spacing=1.0)
txt(s, bx, y + 1.92, 2.57, 1.1,
    [[("每类假设只调用只读工具取数：", 11, False, MID, SANS)],
     [("库存 · 补货单 · 客服工单", 11, False, MID, SANS)],
     [("促销活动 · 天气 · 竞品促销", 11, False, MID, SANS)],
     [("会员复购 · 价格记录", 11, False, MID, SANS)]], spacing=1.45)
line(s, bx, y + 3.14, 2.57, LINE2)
txt(s, bx, y + 3.30, 2.57, 0.9,
    [[("工具返回什么，Agent 就看到什么。", 11, False, MID, SANS)],
     [("不直接读底层表。", 11, True, INK, SANS)]], spacing=1.45)
line(s, bx, y + 4.24, 2.57, INK, 0.016)
txt(s, bx, y + 4.42, 2.57, 0.4, [[("每根因 ≥2 条证据", 12, True, RED, SANS)]], spacing=1.0)
txt(s, bx, y + 4.76, 2.57, 0.7,
    [[("证据不足时显式转人工，", 11, False, MID, SANS)],
     [("不强行给结论。", 11, False, MID, SANS)]], spacing=1.45)
foot(s, "本页数据来自缺货型异常 ano_a75909439adc 的真实诊断记录")

# ==================================================== 07 决策与建议
s, y = page_run("能力 R4 · 决策 / DECISION", 7)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("建议卡不是一句话，而是带参数与 ROI 的可执行方案", 30, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.88, 11.0, 0.4,
    [[("先建议后执行：每个动作都以建议卡形式产生，人能看到它要做什么、值不值。", 14, False, MID, SANS)]], spacing=1.35)
line(s, 0.62, y + 1.50, 12.09, INK, 0.016)
cards = [("补货下单", "缺货 / 供应链延迟", "¥50", "¥316", "6.38", "90%", False),
         ("补货下单", "自有促销拉动", "¥36", "¥67", "1.89", "90%", False),
         ("促销活动", "客诉 / 口碑恶化", "¥73", "¥78", "1.08", "—", False),
         ("促销活动", "竞品促销分流", "¥77", "¥74", "0.96", "—", True)]
for i, (t, rc, cost, bene, roi, rec, appr) in enumerate(cards):
    x = 0.62 + i * 3.06
    if i:
        line(s, x - 0.14, y + 1.66, 0.014, LINE2, 3.0)
    txt(s, x, y + 1.66, 2.8, 0.3,
        [[(t, 15, True, INK, SANS), ("   " + ("需审批" if appr else "自动执行"), 10.5, False, RED if appr else GREEN, SANS)]], spacing=1.0)
    txt(s, x, y + 2.02, 2.82, 0.28, [[("根因 · " + rc, 11, False, GREY, SANS)]], spacing=1.0)
    for j, (lab, val) in enumerate([("预估成本", cost), ("预估收益", bene), ("ROI", roi), ("销量恢复", rec)]):
        yy = y + 2.46 + j * 0.52
        txt(s, x, yy, 1.2, 0.26, [[(lab, 10, False, GREY, SANS)]], spacing=1.0)
        txt(s, x + 1.26, yy - 0.05, 1.5, 0.3, [[(val, 14, True, RED if j == 2 else INK, MONO)]], spacing=1.0)
    line(s, x, y + 4.58, 2.82, LINE2)
    cons = ("cover_days ≤ 21  ✓    moq_multiple  ✓" if i < 2
            else "margin_floor  ✓    discount ≤ 30  ✓    budget ≤ cap  ✓")
    txt(s, x, y + 4.74, 2.86, 0.5, [[(cons, 9, False, MID, MONO)]], spacing=1.3)
line(s, 0.62, y + 5.28, 12.09, INK, 0.016)
txt(s, 0.62, y + 5.44, 12.09, 0.4,
    [[("约束不通过的候选直接丢弃，不进入人工判断 —— 建议约束违反率 0。", 12.5, False, MID, SANS)]], spacing=1.0)
foot(s, "数据来源：本机演示系统实跑的 4 张建议卡")

# ==================================================== 08 治理（三条通道）
s, y = page_run("能力 R5 · 治理 / GOVERNANCE", 8)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("自动执行、转人工、直接拒绝：三条通道各有明确边界", 30, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.88, 11.0, 0.4,
    [[("边界写死在策略里，不依赖执行者的自觉；Agent 服务身份硬上限 L2。", 14, False, MID, SANS)]], spacing=1.35)
line(s, 0.62, y + 1.48, 12.09, INK, 0.016)
lanes = [("自动执行", "低风险 · Agent 授权范围内", RED,
          [("常规补货", "覆盖天数 ≤21 天，数量取整到 MOQ 倍数"),
           ("小额促销 / 临期折价", "折扣 ≤10% 且预算 ≤1 万且不破毛利底线"),
           ("客服回访任务", "针对客诉工单创建，由门店执行整改")]),
         ("转人工审批", "高风险 · L3 风控审批人决定", INK,
          [("折扣超过 10%", "直接影响毛利与品牌定位，必须由人判断"),
           ("预算超过 1 万", "涉及费用承诺，超出授权额度即转人工"),
           ("任何价格变更 / 跨区调拨", "竞争与合规双重敏感，一律人工确认")]),
         ("直接拒绝", "L4 禁止 · 策略层拦截", GREY,
          [("折扣超过 30%", "超出正常经营判断区间，直接拒绝"),
           ("预算超过 10 万", "重大费用支出不属于 Agent 权限"),
           ("白名单外的动作", "只可调用登记在册的写工具")])]
for i, (t, sub, col, rows) in enumerate(lanes):
    x = 0.62 + i * 4.06
    if i:
        line(s, x - 0.22, y + 1.66, 0.014, LINE2, 4.14)
    txt(s, x, y + 1.66, 3.84, 0.36, [[(t, 19, True, col, SERIF)]], spacing=1.0)
    txt(s, x, y + 2.06, 3.84, 0.28, [[(sub, 11, False, GREY, SANS)]], spacing=1.0)
    for j, (a, b) in enumerate(rows):
        yy = y + 2.50 + j * 1.03
        txt(s, x, yy, 3.84, 0.3, [[(a, 13, True, INK, SANS)]], spacing=1.0)
        txt(s, x, yy + 0.30, 3.84, 0.6, [[(b, 11, False, MID, SANS)]], spacing=1.3)
        line(s, x, yy + 0.80, 3.84, LINE2)
line(s, 0.62, y + 5.78, 12.09, INK, 0.016)
txt(s, 0.62, y + 5.94, 12.09, 0.42,
    [[("执行阶段 Policy Engine 会再校验一次，构成纵深防御；被拒绝的请求同样写入审计日志。", 12.5, False, MID, SANS)]], spacing=1.0)
foot(s)

# ==================================================== 09 写操作四保险
s, y = page_run("治理 / WRITE SAFETY", 9)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("写操作四保险：解决重复提交、误操作、无法追责、写错无法回退", 28, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.90, 11.0, 0.4,
    [[("所有写接口统一经过一个受控写入入口，业务系统不暴露裸写通道。", 14, False, MID, SANS)]], spacing=1.35)
line(s, 0.62, y + 1.52, 12.09, INK, 0.016)
safe = [("幂等", "相同幂等键 + 相同请求 → 重放首次结果，不重复下单；键相同但请求不同 → 直接拒绝",
         "重试与网络抖动导致重复下单"),
        ("预演", "任何写入可 dry-run，不落库但仍在审计日志留下一条 dry_run 记录",
         "误操作：先看预览再决定"),
        ("审计", "成功、拒绝、失败与预演均写审计日志，trace_id 贯穿全链路",
         "事后无法回答「谁做了什么」"),
        ("补偿", "补货、调拨、促销、工单均支持补偿回退，库存与单据同步恢复",
         "写错之后无法回退")]
for i, (t, d, s2) in enumerate(safe):
    x = 0.62 + i * 3.06
    if i:
        line(s, x - 0.14, y + 1.70, 0.014, LINE2, 4.2)
    txt(s, x, y + 1.70, 0.6, 0.4, [[(f"0{i+1}", 22, True, RED, SERIF)]], spacing=1.0)
    txt(s, x, y + 2.26, 2.82, 0.34, [[(t, 19, True, INK, SERIF)]], spacing=1.0)
    txt(s, x, y + 2.76, 2.82, 1.5, [[(d, 12, False, MID, SANS)]], spacing=1.5)
    line(s, x, y + 4.42, 2.82, LINE2)
    txt(s, x, y + 4.58, 2.82, 0.7,
        [[("解决：", 11, False, GREY, SANS), (s2, 11, True, INK, SANS)]], spacing=1.3)
foot(s, "受控写入 = 幂等检查 → dry-run 判定 → 真实写入 → 审计留痕 → 失败补偿")

# ==================================================== 10 全景截图（唯一截图页）
s, y = page_run("实证 / EVIDENCE", 10)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("跑一次 Agent，四步结果全部落库", 32, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.86, 11.0, 0.4,
    [[("本机演示系统实跑记录（业务日期 2026-10-07）：41 条异常完成诊断、3 张建议卡、2 条自动执行、1 条转审批。", 14, False, MID, SANS)]], spacing=1.35)
pic(s, os.path.join(SN, "shot-executions.png"), 0.62, y + 1.26, 8.62, 4.30)
bx = 9.44
line(s, bx, y + 1.32, 3.27, INK, 0.016)
txt(s, bx, y + 1.48, 3.27, 0.32, [[("执行记录说明什么", 13.5, True, INK, SERIF)]], spacing=1.0)
notes = [("每条执行都关联单据", "补货对应补货单号，促销对应活动编码，可回到业务系统核对"),
         ("状态机管理", "待执行 → 执行中 → 成功 / 失败 → 已补偿，失败同样可见"),
         ("trace 贯穿", "每条记录携带 trace_id，可在审计日志还原完整链路")]
for i, (t, d) in enumerate(notes):
    yy = y + 2.02 + i * 1.12
    txt(s, bx, yy, 3.27, 0.3, [[(t, 12.5, True, INK, SANS)]], spacing=1.0)
    txt(s, bx, yy + 0.30, 3.27, 0.72, [[(d, 10.5, False, MID, SANS)]], spacing=1.35)
    line(s, bx, yy + 0.90, 3.27, LINE2)
line(s, bx, y + 5.24, 3.27, INK, 0.016)
txt(s, bx, y + 5.40, 3.27, 0.4, [[("每一步都可回溯", 12.5, True, RED, SANS)]], spacing=1.0)
foot(s, "其余页面均以重绘图表呈现，保证版式统一")

# ==================================================== 11 交付验收
s, y = page_run("交付 / ACCEPTANCE", 11)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("验收指标全部达标，且都能用命令复现", 32, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.86, 11.0, 0.4,
    [[("三类注入异常召回率、根因命中率、约束违反率、审批合规率，均有对应的可执行命令。", 14, False, MID, SANS)]], spacing=1.35)
pic(s, os.path.join(CH, "chart-acceptance.png"), 0.62, y + 1.30, 8.44, 3.36)
bx = 9.28
line(s, bx, y + 1.32, 3.43, INK, 0.016)
txt(s, bx, y + 1.48, 3.43, 0.32, [[("复现命令", 13.5, True, INK, SERIF)]], spacing=1.0)
cmds = [("全量测试", "pytest tests/ -v"),
        ("指标字典", "python scripts/validate_metrics.py"),
        ("快速演示", "python scripts/demo.py --small"),
        ("接口文档", "/docs（Swagger UI）")]
for i, (t, c) in enumerate(cmds):
    yy = y + 1.98 + i * 0.74
    txt(s, bx, yy, 3.43, 0.26, [[(t, 11, False, GREY, SANS)]], spacing=1.0)
    txt(s, bx, yy + 0.24, 3.43, 0.3, [[(c, 11, True, INK, MONO)]], spacing=1.0)
    line(s, bx, yy + 0.58, 3.43, LINE2)
line(s, bx, y + 4.98, 3.43, INK, 0.016)
txt(s, bx, y + 5.14, 3.43, 0.44,
    [[("42 项测试全部通过", 13, True, RED, SANS)],
     [("单元 + 集成 + 端到端", 10.5, False, MID, SANS)]], spacing=1.3)
foot(s, "所有数据由 Mock 系统按固定种子生成，同一命令可完整复现")

# ==================================================== 12 部署与使用
s, y = page_run("落地 / ADOPTION", 12)
txt(s, 0.62, y + 0.16, 11.9, 0.62, [[("三种部署方式任选，本地零配置可跑通全链路", 32, True, INK, SERIF)]], spacing=1.1)
txt(s, 0.62, y + 0.86, 11.0, 0.4,
    [[("首次启动自动安装依赖并生成演示数据，约 1 分钟；在线只读预览供外部查看。", 14, False, MID, SANS)]], spacing=1.35)
line(s, 0.62, y + 1.48, 12.09, INK, 0.016)
ways = [("一键脚本（推荐）", "scripts\\start.bat / bash scripts/start.sh", "首次自动生成数据，适合演示与快速体验"),
        ("容器", "docker compose up --build", "适用于容器化环境与 CI，无需本机 Python"),
        ("手动", "pip install -r backend/requirements.txt", "便于二次开发，可指定数据规模与种子")]
for i, (t, c, d) in enumerate(ways):
    x = 0.62 + i * 4.06
    if i:
        line(s, x - 0.22, y + 1.66, 0.014, LINE2, 2.1)
    txt(s, x, y + 1.66, 3.84, 0.34, [[(t, 16, True, INK, SERIF)]], spacing=1.0)
    txt(s, x, y + 2.14, 3.84, 0.7, [[(c, 11, True, RED, MONO)]], spacing=1.35)
    txt(s, x, y + 2.92, 3.84, 0.7, [[(d, 11, False, MID, SANS)]], spacing=1.4)
line(s, 0.62, y + 3.80, 12.09, INK, 0.016)
txt(s, 0.62, y + 4.00, 11.9, 0.4, [[("三条典型使用路径", 15, True, INK, SERIF)]], spacing=1.0)
paths = [("首次体验", "10 分钟跑通闭环：启动服务 → 运行 Agent → 核对证据链 → 处理一条高风险审批"),
         ("日常巡检", "每天 5 分钟：总览看计数 → 异常按严重度处理 → 建议复核 ROI → 审计溯源"),
         ("对外演示", "先跑一次 Agent 让页面有真实数据，再用证据链与审计日志证明可核对")]
for i, (t, d) in enumerate(paths):
    yy = y + 4.36 + i * 0.60
    txt(s, 0.62, yy, 1.42, 0.3, [[(t, 13, True, INK, SANS)]], spacing=1.0)
    txt(s, 2.14, yy + 0.02, 10.57, 0.4, [[(d, 11.5, False, MID, SANS)]], spacing=1.2)
line(s, 0.62, y + 6.14, 12.09, LINE)
foot(s, "控制台 http://127.0.0.1:8300 ｜ 接口文档 /docs")

# ==================================================== 13 结尾
s = slide(INK)
line(s, 0.62, 1.24, 12.09, RGBColor(0x4A, 0x46, 0x40), 0.02)
txt(s, 0.62, 0.86, 8.0, 0.3, [[("RETAIL DECISION AGENT", 12, False, RGBColor(0x8A, 0x81, 0x75), MONO)]], spacing=1.0)
txt(s, 0.62, 0.86, 12.09, 0.3, [[("THANK YOU", 12, False, RGBColor(0x8A, 0x81, 0x75), MONO)]],
    align=PP_ALIGN.RIGHT, spacing=1.0)
txt(s, 0.62, 2.44, 11.9, 1.5,
    [[("让每一次经营异常，", 46, True, WHITE, SERIF)],
     [("都有人接得住。", 46, True, WHITE, SERIF)]], spacing=1.14)
block(s, 0.66, 4.42, 1.68, 0.05, RED)
txt(s, 0.62, 4.72, 11.9, 0.5,
    [[("自动发现 · 根因可查 · 建议可算 · 执行可控 · 全程可审计", 17, False, RGBColor(0xC9, 0xC2, 0xB8), SANS)]], spacing=1.3)
for i, (k, v) in enumerate([("在线预览", "https://shenyuanyuan77.github.io/retail-decision-agent/"),
                            ("代码仓库", "https://github.com/shenyuanyuan77/retail-decision-agent"),
                            ("本地启动", "scripts\\start.bat（Windows） / bash scripts/start.sh")]):
    yy = 5.62 + i * 0.44
    txt(s, 0.62, yy, 1.6, 0.3, [[(k, 12, False, RGBColor(0x8A, 0x81, 0x75), SANS)]], spacing=1.0)
    txt(s, 2.22, yy, 10.49, 0.3, [[(v, 12, False, RGBColor(0xC9, 0xC2, 0xB8), MONO)]], spacing=1.0)

prs.save(OUT)
print("已生成:", OUT)
print("页数:", len(prs.slides._sldIdLst))
