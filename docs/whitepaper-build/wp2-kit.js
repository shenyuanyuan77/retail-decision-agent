/* 零售经营决策系统 · 产品白皮书 V2.0 —— 严格跟随《V1.1-ZCode Enterprise 企业版使用手册》体例
 *
 * 体例对齐点（对照参考手册逐项镜像）：
 *   1. 封面：产品名（大号蓝）+ 文档名 + 版本 + 日期，居中，无图
 *   2. 功能目录：章 / 节 / 子节 全量清单
 *   3. 目录：TOC 域代码（Word 内可更新页码）
 *   4. 正文：篇 = Heading1（分页），章 = Heading2（N 标题），节 = Heading3（N.M 标题）
 *   5. 每个功能统一节奏：功能概述： → 正文 → 截图 → 图 N-M 图注 → 页面说明/操作流程：
 *   6. 表格：表 N-M 表题 + Table Grid；操作项 / 说明 两列表
 *   7. 页眉：产品名 + 文档名（右对齐）；页脚：页码（居中）
 *   8. 字号：正文 10.5pt / 图注 9pt 灰 / 表头 9.5pt 白字蓝底
 */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, PageBreak, Header, Footer, PageNumber, NumberFormat,
  AlignmentType, HeadingLevel, WidthType, BorderStyle, ShadingType,
  TableOfContents, VerticalAlign,
} = require("docx");
const fs = require("fs");
const path = require("path");
const { imageSize } = require("image-size");

const ROOT = path.resolve(__dirname, "../..");
const ASSETS = path.join(ROOT, "docs", "whitepaper-assets-v2", "doc");
const OUT = path.join(ROOT, "docs", "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf\u4ea7\u54c1\u767d\u76ae\u4e66_V2.0.docx");

const FONT = { ascii: "Microsoft YaHei", eastAsia: "\u5fae\u8f6f\u96c5\u9ed1", hAnsi: "Microsoft YaHei" };
const ACCENT = "1F4E79";        // 参考手册 Heading1 颜色
const ACCENT2 = "2F5597";       // Heading2
const ACCENT3 = "385D8A";       // Heading3
const CAP_GRAY = "646464";      // 图注灰
const INK = "222222";

/* ---------------- 段落构件 ---------------- */
const P = (opts) => new Paragraph(opts);

function body(runs, opts = {}) {
  const arr = Array.isArray(runs) ? runs : [{ text: runs }];
  return P({
    alignment: AlignmentType.BOTH,
    spacing: { line: 340, after: 90 },
    indent: opts.indent === false ? undefined : { firstLine: 420 },
    children: arr.map((r) =>
      new TextRun({ text: r.text, size: 21, font: FONT, color: INK, bold: !!r.bold,
        italics: !!r.italics, color: r.color || INK })),
  });
}

/* 功能概述：/ 操作流程：/ 页面说明： 这类引导行（参考手册中独立成段、加粗、主色） */
function lead(text) {
  return P({
    keepNext: true,
    spacing: { before: 130, after: 70, line: 340 },
    children: [new TextRun({ text, size: 21, bold: true, font: FONT, color: ACCENT })],
  });
}
function subLead(text) {
  return P({
    keepNext: true,
    spacing: { before: 110, after: 60, line: 340 },
    children: [new TextRun({ text, size: 21, bold: true, font: FONT, color: ACCENT3 })],
  });
}

/* 编号步骤：序号加粗主色 + 正文（参考手册 2.1 操作流程写法） */
function step(n, text) {
  return P({
    spacing: { after: 60, line: 330 },
    indent: { left: 420 },
    children: [
      new TextRun({ text: `${n}. `, size: 21, bold: true, font: FONT, color: ACCENT }),
      new TextRun({ text, size: 21, font: FONT, color: INK }),
    ],
  });
}

/* 项目符号（参考手册 List Bullet 写法） */
function bullet(text, bold = "") {
  return P({
    spacing: { after: 55, line: 330 },
    indent: { left: 420, hanging: 210 },
    children: [
      new TextRun({ text: "\u25aa  ", size: 21, font: FONT, color: ACCENT2, bold: true }),
      ...(bold ? [new TextRun({ text: bold, size: 21, bold: true, font: FONT, color: INK })] : []),
      new TextRun({ text, size: 21, font: FONT, color: INK }),
    ],
  });
}

function h1(text) {
  // 与参考手册一致：章标题不强制分页，正文连续排版（参考手册全文仅封面后有一个显式分页符）
  return P({
    heading: HeadingLevel.HEADING_1,
    keepNext: true,
    spacing: { before: 320, after: 200, line: 340 },
    children: [new TextRun({ text, size: 21, bold: true, font: FONT, color: ACCENT })],
  });
}
function h2(text) {
  return P({
    heading: HeadingLevel.HEADING_2,
    keepNext: true,
    spacing: { before: 260, after: 130, line: 340 },
    children: [new TextRun({ text, size: 17, bold: true, font: FONT, color: ACCENT2 })],
  });
}
function h3(text) {
  return P({
    heading: HeadingLevel.HEADING_3,
    keepNext: true,
    spacing: { before: 210, after: 110, line: 340 },
    children: [new TextRun({ text, size: 13, bold: true, font: FONT, color: ACCENT3 })],
  });
}

/* ---------------- 图 ---------------- */
function figure(file, caption, widthIn = 630) {
  const p = path.join(ASSETS, file);
  const buf = fs.readFileSync(p);
  const dim = imageSize(buf);
  const width = widthIn;
  const height = Math.round(width * dim.height / dim.width);
  return [
    P({
      alignment: AlignmentType.CENTER,
      keepNext: true,
      spacing: { before: 120, after: 45 },
      children: [new ImageRun({ data: buf, transformation: { width, height }, type: "png" })],
    }),
    P({
      alignment: AlignmentType.CENTER,
      spacing: { after: 150 },
      children: [new TextRun({ text: caption, size: 18, font: FONT, color: CAP_GRAY })],
    }),
  ];
}

/* ---------------- 表 ---------------- */
function tcell(text, { head = false, w = 20, align = AlignmentType.LEFT, keepNext = false } = {}) {
  return new TableCell({
    verticalAlign: VerticalAlign.CENTER,
    children: [P({
      alignment: align,
      keepNext,
      spacing: { line: 300, before: 20, after: 20 },
      children: [new TextRun({
        text, size: head ? 19 : 18.5, font: FONT, bold: head,
        color: head ? "FFFFFF" : "333333",
      })],
    })],
    shading: head ? { type: ShadingType.CLEAR, fill: ACCENT } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    width: { size: w, type: WidthType.PERCENTAGE },
  });
}

function tableTitle(text) {
  return P({
    keepNext: true,
    spacing: { before: 130, after: 80, line: 340 },
    children: [new TextRun({ text, size: 18.5, bold: true, font: FONT, color: "333333" })],
  });
}

function table(headers, rows, widths, title) {
  const t = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "8EA9C1" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "8EA9C1" },
      left: { style: BorderStyle.SINGLE, size: 2, color: "C7D4E2" },
      right: { style: BorderStyle.SINGLE, size: 2, color: "C7D4E2" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "DCE5EF" },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "DCE5EF" },
    },
    rows: [
      new TableRow({
        tableHeader: true, cantSplit: true,
        children: headers.map((h, i) => tcell(h, { head: true, w: widths[i] })),
      }),
      ...rows.map((r) => new TableRow({
        // cantSplit：禁止单行跨页断裂（行内不被剖开）；表格整体仍可在行间自然分页
        cantSplit: true,
        children: r.map((c, i) => tcell(c, { w: widths[i] })),
      })),
    ],
  });
  return title ? [tableTitle(title), t, P({ spacing: { after: 130 } })] : [t, P({ spacing: { after: 130 } })];
}

/* ---------------- 页眉页脚（镜像参考手册） ---------------- */
const pageHeader = () => new Header({
  children: [P({
    alignment: AlignmentType.RIGHT,
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "C9D2DE", space: 3 } },
    children: [new TextRun({ text: "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf  \u4ea7\u54c1\u767d\u76ae\u4e66", size: 17, font: FONT, color: "828282" })],
  })],
});
const pageFooter = () => new Footer({
  children: [P({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ children: [PageNumber.CURRENT], size: 17, font: FONT, color: "828282" })],
  })],
});

/* ================================================================
   封面
   ================================================================ */
const cover = [
  P({ spacing: { before: 2400 } }),
  P({
    alignment: AlignmentType.CENTER, spacing: { after: 150 },
    children: [new TextRun({ text: "Retail Decision Agent", size: 48, bold: true,
      font: { ascii: "Microsoft YaHei", eastAsia: "\u5fae\u8f6f\u96c5\u9ed1" }, color: ACCENT })],
  }),
  P({
    alignment: AlignmentType.CENTER, spacing: { after: 620 },
    children: [new TextRun({ text: "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf \u00b7 \u4ea7\u54c1\u767d\u76ae\u4e66", size: 30, bold: true, font: FONT, color: "0F2A4A" })],
  }),
  P({
    alignment: AlignmentType.CENTER, spacing: { after: 110 },
    children: [new TextRun({ text: "\u7248\u672c V2.0", size: 23, font: FONT, color: "444444" })],
  }),
  P({
    alignment: AlignmentType.CENTER, spacing: { after: 1300 },
    children: [new TextRun({ text: "2026 \u5e74 9 \u6708 30 \u65e5", size: 21, font: FONT, color: "444444" })],
  }),
  P({
    alignment: AlignmentType.CENTER, spacing: { after: 70 },
    children: [new TextRun({ text: "\u5728\u7ebf\u9884\u89c8\uff1ahttps://shenyuanyuan77.github.io/retail-decision-agent/", size: 17.5, font: FONT, color: "707070" })],
  }),
  P({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "\u4ee3\u7801\u4ed3\u5e93\uff1ahttps://github.com/shenyuanyuan77/retail-decision-agent", size: 17.5, font: FONT, color: "707070" })],
  }),
];

/* ================================================================
   功能目录（章 / 节 / 子节全清单，镜像参考手册）
   ================================================================ */
const INDEX_ITEMS = [
  ["1 系统概述", 0],
  ["1.1 产品定位", 1],
  ["1.2 产品形态与能力分层", 1],
  ["1.3 使用范围", 1],
  ["1.4 页面结构与使用约定", 1],
  ["2 系统架构", 0],
  ["2.1 总体架构", 1],
  ["2.2 分层职责与设计决策", 1],
  ["2.3 一条异常的数据流", 1],
  ["3 快速开始", 0],
  ["3.1 启动与访问", 1],
  ["3.2 身份与权限切换", 1],
  ["3.3 首次初始化流程", 1],
  ["3.4 日常巡检流程", 1],
  ["4 经营总览", 0],
  ["5 异常中心：自动发现", 0],
  ["5.1 检测算法", 1],
  ["5.2 异常列表", 1],
  ["5.3 异常详情：检测证据", 1],
  ["6 根因分析", 0],
  ["6.1 九类假设验证", 1],
  ["6.2 根因 Top3 与证据链", 1],
  ["7 补货与促销建议", 0],
  ["7.1 打法库与参数生成", 1],
  ["7.2 约束检查与成本收益估算", 1],
  ["8 审批中心", 0],
  ["9 执行记录", 0],
  ["10 审计日志", 0],
  ["11 权限矩阵与策略引擎", 0],
  ["11.1 角色与权限等级", 1],
  ["11.2 风险规则与授权边界", 1],
  ["12 写操作四保险", 0],
  ["13 典型操作流程", 0],
  ["13.1 从异常到执行的完整闭环", 1],
  ["13.2 高风险动作的审批流程", 1],
  ["13.3 审计追溯", 1],
  ["14 交付与验证", 0],
  ["14.1 部署形态", 1],
  ["14.2 验收结果", 1],
  ["15 使用规范与常见问题", 0],
  ["16 附录：接口与指标字典", 0],
];

const functionIndex = [
  P({
    pageBreakBefore: true, spacing: { before: 300, after: 220 },
    children: [new TextRun({ text: "\u529f\u80fd\u76ee\u5f55", size: 21, bold: true, font: FONT, color: ACCENT })],
  }),
  ...INDEX_ITEMS.map(([t, lv]) => P({
    spacing: { after: lv === 0 ? 70 : 30, line: 300 },
    indent: { left: lv === 0 ? 0 : (lv === 1 ? 420 : 840) },
    children: [new TextRun({
      text: t, size: lv === 0 ? 21 : 19, bold: lv === 0,
      font: FONT, color: lv === 0 ? "0F2A4A" : "55606E",
    })],
  })),
];

/* ================================================================
   目录页（TOC 域）
   ================================================================ */
const toc = [
  P({
    pageBreakBefore: true, spacing: { before: 300, after: 220 },
    children: [new TextRun({ text: "\u76ee\u5f55", size: 21, bold: true, font: FONT, color: ACCENT })],
  }),
  new TableOfContents("\u76ee\u5f55", { hyperlink: true, headingStyleRange: "1-3" }),
  P({
    spacing: { before: 220 },
    children: [new TextRun({
      text: "\u6ce8\uff1a\u672c\u76ee\u5f55\u7531\u57df\u4ee3\u7801\u751f\u6210\u3002\u7f16\u8f91\u6587\u6863\u540e\u8bf7\u53f3\u952e\u76ee\u5f55\u9009\u62e9\u201c\u66f4\u65b0\u57df\u201d\u4ee5\u5237\u65b0\u9875\u7801\u3002",
      size: 17.5, font: FONT, color: "8A8A8A",
    })],
  }),
];

module.exports = { P, body, lead, subLead, step, bullet, h1, h2, h3, figure, table, tableTitle,
  pageHeader, pageFooter, cover, functionIndex, toc, Document, Packer, fs, OUT, ROOT,
  ACCENT, ACCENT2, ACCENT3, FONT, INK, CAP_GRAY, ASSETS, TableOfContents, PageBreak };
