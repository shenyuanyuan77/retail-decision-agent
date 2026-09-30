/* 零售经营决策系统 · 产品白皮书 V1.0 —— 模板跟随模式（参考 ZCode Enterprise 企业版使用手册格式）
 * 体例：文字封面（产品名+版本+日期）→ 功能目录 → 目录 → 篇(H1)/章(H2)/节(H3) 编号正文
 * 配图：系统真实截图（全屏宽）；页眉页脚：产品名 · 版本 | 页码
 */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, PageBreak, Header, Footer, PageNumber, NumberFormat,
  AlignmentType, HeadingLevel, WidthType, BorderStyle, ShadingType,
  TableOfContents,
} = require("docx");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "../..");
const ASSETS = path.join(ROOT, "docs", "whitepaper-assets");
const OUT = path.join(ROOT, "docs", "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf\u4ea7\u54c1\u767d\u76ae\u4e66_V1.0.docx");
const { imageSize } = require("image-size");

/* ---------- 基础工具 ---------- */
const CN = { ascii: "Times New Roman", eastAsia: "SimSun" };
const CN_HEI = { ascii: "Times New Roman", eastAsia: "SimHei" };
const ACCENT = "1E4A8F";          // 深蓝点缀（贴合参考手册的沉稳蓝灰）
const HEADER_TEXT = "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf \u4ea7\u54c1\u767d\u76ae\u4e66";  // 零售经营决策系统 产品白皮书
const FOOTER_LEFT = "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf \u4ea7\u54c1\u767d\u76ae\u4e66 \u00b7 V1.0";

function body(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 312, after: 80 },
    indent: { firstLine: 480 },
    children: [new TextRun({ text, size: 24, font: CN, color: "000000", ...opts })],
  });
}
function bodyRuns(runs) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 312, after: 80 },
    indent: { firstLine: 480 },
    children: runs.map(r => new TextRun({ size: 24, font: CN, color: "000000", ...r })),
  });
}
function bullet(text, bold = "") {
  return new Paragraph({
    spacing: { line: 312, after: 60 },
    indent: { left: 480, hanging: 240 },
    children: [
      new TextRun({ text: "\u2022 ", size: 24, font: CN, color: ACCENT, bold: true }),
      ...(bold ? [new TextRun({ text: bold, size: 24, font: CN, bold: true, color: "000000" })] : []),
      new TextRun({ text, size: 24, font: CN, color: "000000" }),
    ],
  });
}
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: true,
    spacing: { before: 240, after: 200, line: 312 },
    children: [new TextRun({ text, size: 32, bold: true, font: CN_HEI, color: ACCENT })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    keepNext: true,
    spacing: { before: 280, after: 140, line: 312 },
    children: [new TextRun({ text, size: 28, bold: true, font: CN_HEI, color: "0B1220" })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    keepNext: true,
    spacing: { before: 220, after: 110, line: 312 },
    children: [new TextRun({ text, size: 24, bold: true, font: CN_HEI, color: "0B1220" })],
  });
}
function figure(file, caption, width = 550) {
  const p = path.join(ASSETS, file);
  const buf = fs.readFileSync(p);
  const dim = imageSize(buf);
  const h = Math.round(width * dim.height / dim.width);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      keepNext: true,
      spacing: { before: 120, after: 40, line: 312 },
      children: [new ImageRun({ data: buf, transformation: { width, height: h }, type: "png" })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 160, line: 312 },
      children: [new TextRun({ text: caption, size: 21, font: CN, color: "666666" })],
    }),
  ];
}
function cell(text, { head = false, w = 25, align = AlignmentType.LEFT } = {}) {
  return new TableCell({
    children: [new Paragraph({
      alignment: align,
      spacing: { line: 312 },
      children: [new TextRun({ text, size: 21, font: CN, bold: head, color: head ? "FFFFFF" : "000000" })],
    })],
    shading: head ? { type: ShadingType.CLEAR, fill: ACCENT } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    width: { size: w, type: WidthType.PERCENTAGE },
  });
}
function table(headers, rows, widths) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 6, color: ACCENT },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT },
      left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "C9D2DE" },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: [
      new TableRow({
        tableHeader: true, cantSplit: true,
        children: headers.map((t, i) => cell(t, { head: true, w: widths[i] })),
      }),
      ...rows.map(r => new TableRow({
        cantSplit: true,
        children: r.map((t, i) => cell(t, { w: widths[i] })),
      })),
    ],
  });
}
function tableTitle(text) {
  return new Paragraph({
    keepNext: true, spacing: { before: 120, after: 80, line: 312 },
    children: [new TextRun({ text, bold: true, size: 21, font: CN, color: "333333" })],
  });
}

const pageHeader = () => new Header({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "BBBBBB", space: 2 } },
    children: [new TextRun({ text: HEADER_TEXT, size: 18, font: CN, color: "888888" })],
  })],
});
const pageFooter = () => new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: FOOTER_LEFT + "   |   ", size: 18, font: CN, color: "888888" }),
      new TextRun({ children: [PageNumber.CURRENT], size: 18, font: CN, color: "888888" }),
    ],
  })],
});

/* ---------- 封面（模板跟随：产品名 + 文档名 + 版本 + 日期） ---------- */
const coverChildren = [
  new Paragraph({ spacing: { before: 2600, line: 312 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 160, line: 312 },
    children: [new TextRun({ text: "Retail Decision Agent", size: 56, bold: true, font: { ascii: "Times New Roman", eastAsia: "SimHei" }, color: ACCENT })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 900, line: 312 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 10 } },
    children: [new TextRun({ text: "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf \u00b7 \u4ea7\u54c1\u767d\u76ae\u4e66", size: 36, bold: true, font: CN_HEI, color: "0B1220" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 120, line: 312 },
    children: [new TextRun({ text: "\u7248\u672c V1.0", size: 26, font: CN, color: "444444" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 1400, line: 312 },
    children: [new TextRun({ text: "2026 \u5e74 9 \u6708 30 \u65e5", size: 24, font: CN, color: "444444" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 80, line: 312 },
    children: [new TextRun({ text: "\u5728\u7ebf\u9884\u89c8\uff1ahttps://shenyuanyuan77.github.io/retail-decision-agent/", size: 20, font: CN, color: "666666" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "\u4ee3\u7801\u4ed3\u5e93\uff1ahttps://github.com/shenyuanyuan77/retail-decision-agent", size: 20, font: CN, color: "666666" })],
  }),
];

/* ---------- 功能目录页（参考手册体例） ---------- */
const functionIndex = [
  new Paragraph({
    pageBreakBefore: true, spacing: { before: 200, after: 200, line: 312 },
    children: [new TextRun({ text: "\u529f\u80fd\u76ee\u5f55", size: 32, bold: true, font: CN_HEI, color: ACCENT })],
  }),
  ...[
    ["\u7b2c\u4e00\u7bc7 \u4ea7\u54c1\u6982\u8ff0", "1 \u4ea7\u54c1\u5b9a\u4f4d\u4e0e\u6838\u5fc3\u4ef7\u503c / 2 \u7cfb\u7edf\u67b6\u6784 / 3 \u6838\u5fc3\u80fd\u529b\u603b\u89c8\uff08R1-R5\uff09"],
    ["\u7b2c\u4e8c\u7bc7 \u6838\u5fc3\u529f\u80fd\u8be6\u89e3", "4 \u7ecf\u8425\u603b\u89c8 / 5 \u5f02\u5e38\u4e2d\u5fc3\uff1a\u81ea\u52a8\u53d1\u73b0 / 6 \u6839\u56e0\u5206\u6790 / 7 \u8865\u8d27\u4e0e\u4fc3\u9500\u5efa\u8bae / 8 \u6388\u6743\u6267\u884c\u4e0e\u5ba1\u6279 / 9 \u6267\u884c\u8bb0\u5f55\u4e0e\u5ba1\u8ba1"],
    ["\u7b2c\u4e09\u7bc7 \u6cbb\u7406\u4e0e\u5b89\u5168", "10 \u6743\u9650\u77e9\u9635\u4e0e\u7b56\u7565\u5f15\u64ce / 11 \u5199\u64cd\u4f5c\u56db\u4fdd\u9669"],
    ["\u7b2c\u56db\u7bc7 \u90e8\u7f72\u4e0e\u4f7f\u7528", "12 \u5feb\u901f\u542f\u52a8 / 13 \u5728\u7ebf\u9884\u89c8\u4e0e\u7248\u672c\u8fed\u4ee3 / 14 \u9a8c\u6536\u7ed3\u679c / 15 \u5e38\u89c1\u95ee\u9898"],
  ].flatMap(([t, sub]) => [
    new Paragraph({
      spacing: { before: 160, after: 40, line: 312 },
      children: [new TextRun({ text: t, size: 26, bold: true, font: CN_HEI, color: "0B1220" })],
    }),
    new Paragraph({
      spacing: { after: 80, line: 312 },
      children: [new TextRun({ text: sub, size: 22, font: CN, color: "555555" })],
    }),
  ]),
];

/* ---------- 目录页 ---------- */
const tocChildren = [
  new Paragraph({
    spacing: { before: 400, after: 240, line: 312 },
    children: [new TextRun({ text: "\u76ee\u5f55", size: 32, bold: true, font: CN_HEI, color: ACCENT })],
  }),
  new TableOfContents("\u76ee\u5f55", { hyperlink: true, headingStyleRange: "1-3" }),
  new Paragraph({
    spacing: { before: 200, line: 312 },
    children: [new TextRun({
      text: "\u6ce8\uff1a\u672c\u76ee\u5f55\u7531\u57df\u4ee3\u7801\u751f\u6210\u3002\u7f16\u8f91\u6587\u6863\u540e\u8bf7\u53f3\u952e\u76ee\u5f55\u9009\u62e9\u201c\u66f4\u65b0\u57df\u201d\u4ee5\u5237\u65b0\u9875\u7801\u3002",
      italics: true, size: 18, font: CN, color: "888888",
    })],
  }),
];

/* ---------- 正文 ---------- */
const bodyChildren = [];

/* ===== 第一篇 产品概述 ===== */
bodyChildren.push(
  h1("\u7b2c\u4e00\u7bc7 \u4ea7\u54c1\u6982\u8ff0"),

  h2("1 \u4ea7\u54c1\u5b9a\u4f4d\u4e0e\u6838\u5fc3\u4ef7\u503c"),
  body("\u96f6\u552e\u7ecf\u8425\u51b3\u7b56 Agent\uff08Retail Decision Agent\uff09\u9762\u5411\u5168\u56fd\u8fde\u9501\u96f6\u552e\u4f01\u4e1a\uff0c\u63a5\u5165\u95e8\u5e97\u3001\u4f1a\u5458\u3001\u4f9b\u5e94\u94fe\u3001\u5ba2\u670d\u7b49\u591a\u4e2a\u4e1a\u52a1\u7cfb\u7edf\uff0c\u4ee5\u4e00\u6761\u5b8c\u6574\u95ed\u73af\u5de5\u4f5c\u6d41\u66ff\u4ee3\u4eba\u5de5\u5de1\u68c0\u4e0e\u7ecf\u9a8c\u51b3\u7b56\uff1a"),
  bullet("\u7cfb\u7edf\u6301\u7eed\u626b\u63cf\u9500\u552e\u6570\u636e\uff0c\u81ea\u52a8\u53d1\u73b0\u9500\u91cf\u5f02\u5e38\uff0c\u65e0\u9700\u4eba\u5de5\u53d1\u8d77\uff1b", "\u81ea\u52a8\u53d1\u73b0"),
  bullet("\u5bf9\u6bcf\u4e2a\u5f02\u5e38\u81ea\u52a8\u8fdb\u884c\u591a\u7ef4\u5ea6\u5047\u8bbe\u9a8c\u8bc1\uff0c\u8f93\u51fa\u5e26\u8bc1\u636e\u94fe\u4e0e\u7f6e\u4fe1\u5ea6\u7684\u6839\u56e0 Top3\uff1b", "\u6839\u56e0\u5206\u6790"),
  bullet("\u6309\u6839\u56e0\u5339\u914d\u6253\u6cd5\u5e93\uff0c\u751f\u6210\u8865\u8d27\u6216\u4fc3\u9500\u5efa\u8bae\uff0c\u542b\u7ea6\u675f\u68c0\u67e5\u4e0e\u6210\u672c\u6536\u76ca\u4f30\u7b97\uff1b", "\u5efa\u8bae\u751f\u6210"),
  bullet("\u4f4e\u98ce\u9669\u52a8\u4f5c\u81ea\u52a8\u6267\u884c\uff0c\u9ad8\u98ce\u9669\u52a8\u4f5c\u5f3a\u5236\u8f6c\u4eba\u5de5\u5ba1\u6279\uff0c\u5168\u7a0b\u7559\u75d5\u53ef\u5ba1\u8ba1\u3002", "\u6388\u6743\u6267\u884c"),
  body("\u4e0e\u4f20\u7edf\u6570\u636e\u770b\u677f\u7684\u672c\u8d28\u533a\u522b\u5728\u4e8e\uff1a\u770b\u677f\u56de\u7b54\u201c\u53d1\u751f\u4e86\u4ec0\u4e48\u201d\uff0c\u672c\u4ea7\u54c1\u56de\u7b54\u201c\u4e3a\u4ec0\u4e48\u53d1\u751f\u3001\u8be5\u600e\u4e48\u529e\u3001\u529e\u4e86\u4e4b\u540e\u6548\u679c\u5982\u4f55\u201d\uff0c\u5e76\u628a\u6bcf\u4e00\u6b65\u4ea4\u7ed9\u53ef\u63a7\u53ef\u5ba1\u8ba1\u7684 Agent \u6267\u884c\u3002"),

  h2("2 \u7cfb\u7edf\u67b6\u6784"),
  body("\u7cfb\u7edf\u91c7\u7528\u201c\u5355\u4f53\u670d\u52a1\u3001\u5206\u57df\u8bbe\u8ba1\u201d\u67b6\u6784\uff1a\u516d\u5927\u4e1a\u52a1\u7cfb\u7edf\u4f5c\u4e3a\u4e8b\u5b9e\u6570\u636e\u6e90\uff0c\u56db\u4e2a Agent \u5c42\u5b8c\u6210\u53d1\u73b0\u5230\u6267\u884c\u7684\u63a8\u7406\u94fe\u8def\uff0c\u6cbb\u7406\u5c42\u8d2f\u7a7f\u6240\u6709\u5199\u5165\u8def\u5f84\uff1a"),
  tableTitle("\u8868 2-1 \u7cfb\u7edf\u5206\u5c42\u67b6\u6784"),
  table(
    ["\u5c42", "\u6a21\u5757", "\u804c\u8d23", "\u6280\u672f"],
    [
      ["\u4e1a\u52a1\u7cfb\u7edf\u5c42", "services/\uff086 \u4e2a\uff09", "\u4e3b\u6570\u636e / \u9500\u552e / \u5e93\u5b58\u4f9b\u5e94\u94fe / \u4f1a\u5458 / \u5ba2\u670d / \u5916\u90e8\u6570\u636e\uff0c\u63d0\u4f9b\u4e8b\u5b9e\u4e0e\u6267\u884c\u901a\u9053", "FastAPI REST + OpenAPI"],
      ["\u611f\u77e5\u5c42", "agents/perception", "\u6eda\u52a8\u4e2d\u4f4d\u6570 + MAD + z-score \u7edf\u8ba1\u68c0\u6d4b\uff0c\u4e3b\u52a8\u53d1\u73b0\u9500\u91cf\u5f02\u5e38", "\u7eaf Python \u7b97\u6cd5"],
      ["\u8bca\u65ad\u5c42", "agents/diagnosis", "9 \u7c7b\u5047\u8bbe\u9a8c\u8bc1\uff0c\u8f93\u51fa\u6839\u56e0 Top3 + \u7f6e\u4fe1\u5ea6 + \u8bc1\u636e\u94fe", "\u5047\u8bbe\u9a8c\u8bc1\u6846\u67b6"],
      ["\u51b3\u7b56\u5c42", "agents/decision", "\u6839\u56e0 \u00d7 \u6253\u6cd5\u5e93 \u2192 \u8865\u8d27/\u4fc3\u9500\u5efa\u8bae\uff0c\u7ea6\u675f\u68c0\u67e5 + ROI \u4f30\u7b97", "YAML \u77e5\u8bc6\u5e93"],
      ["\u6267\u884c\u5c42", "agents/execution", "\u516d\u5927\u5199\u5de5\u5177\uff0c\u72b6\u6001\u673a\u7ba1\u7406\uff0c\u5931\u8d25\u53ef\u8865\u507f", "\u5e42\u7b49 + \u8865\u507f"],
      ["\u6cbb\u7406\u5c42", "governance/", "\u6743\u9650\u77e9\u9635 L0-L4\u3001\u7b56\u7565\u5f15\u64ce\u3001\u5ba1\u6279\u3001\u5ba1\u8ba1\u3001\u5e72\u7ebf\u5199\u5165", "Policy Engine"],
      ["\u524d\u7aef", "web/", "\u7ecf\u8425\u63a7\u5236\u53f0\uff086 \u6838\u5fc3\u9875\u9762\uff09", "\u6d45\u8272\u4e3b\u9898\uff0c\u65e0\u6784\u5efa SPA"],
    ],
    [14, 18, 44, 24],
  ),
  body("\u5927\u6a21\u578b\u5728\u7cfb\u7edf\u4e2d\u53ea\u627f\u62c5\u201c\u53d9\u8ff0\u89e3\u91ca\u201d\u804c\u8d23\uff1a\u6240\u6709\u6570\u5b57\u5747\u6765\u81ea\u5de5\u5177\u8fd4\u56de\u7684\u4e8b\u5b9e\u6570\u636e\uff0c\u5e76\u5185\u7f6e\u9632\u7f16\u9020\u6821\u9a8c\uff08\u53d9\u8ff0\u4e2d\u51fa\u73b0\u4e8b\u5b9e\u8868\u4e4b\u5916\u7684\u6570\u5b57\u5373\u81ea\u52a8\u56de\u9000\u6a21\u677f\u53d9\u8ff0\uff09\uff0c\u4ece\u673a\u5236\u4e0a\u4fdd\u8bc1\u7ed3\u8bba\u53ef\u8ffd\u6eaf\u3002\u5df2\u7528 DeepSeek \u771f\u5b9e\u6a21\u578b\u5b9e\u6d4b\u9a8c\u8bc1\u3002"),

  h2("3 \u6838\u5fc3\u80fd\u529b\u603b\u89c8"),
  tableTitle("\u8868 3-1 \u6838\u5fc3\u80fd\u529b\u4e0e\u5b9e\u73b0\u65b9\u5f0f\uff08R1-R5\uff09"),
  table(
    ["\u7f16\u53f7", "\u80fd\u529b", "\u5b9e\u73b0\u65b9\u5f0f", "\u9a8c\u8bc1\u7ed3\u679c"],
    [
      ["R1", "\u591a\u7cfb\u7edf\u63a5\u5165", "6 \u5927 Mock \u4e1a\u52a1\u7cfb\u7edf\uff0c\u53ea\u8bfb\u5de5\u5177\u5c42\u7edf\u4e00\u63a5\u5165", "\u63a5\u53e3\u5b9e\u6d4b\u5168\u90e8\u8fd4\u56de\u771f\u5b9e\u6570\u636e"],
      ["R2", "\u81ea\u52a8\u53d1\u73b0\u5f02\u5e38", "\u7edf\u8ba1\u68c0\u6d4b\u4e3b\u52a8\u626b\u63cf\uff0c\u652f\u6301\u5b9a\u65f6\u8c03\u5ea6", "3 \u7c7b\u6ce8\u5165\u5f02\u5e38\u53ec\u56de\u7387 100%"],
      ["R3", "\u5206\u6790\u539f\u56e0", "9 \u7c7b\u5047\u8bbe\u9a8c\u8bc1\uff0c\u6bcf\u6839\u56e0\u81f3\u5c11 2 \u6761\u8bc1\u636e", "\u6839\u56e0 Top3 \u547d\u4e2d\u7387 100%"],
      ["R4", "\u8865\u8d27/\u4fc3\u9500\u5efa\u8bae", "\u6839\u56e0\u00d7\u6253\u6cd5\u5e93\uff0cMOQ/\u6bdb\u5229/\u9884\u7b97\u7ea6\u675f + ROI", "\u7ea6\u675f\u8fdd\u53cd\u7387 0"],
      ["R5", "\u6388\u6743\u8303\u56f4\u5185\u6267\u884c", "L0-L4 \u6743\u9650 + \u7b56\u7565\u5f15\u64ce + \u4eba\u5de5\u5ba1\u6279", "\u9ad8\u98ce\u9669\u5ba1\u6279\u5408\u89c4\u7387 100%"],
    ],
    [8, 22, 42, 28],
  ),
);

/* ===== 第二篇 核心功能详解 ===== */
bodyChildren.push(
  h1("\u7b2c\u4e8c\u7bc7 \u6838\u5fc3\u529f\u80fd\u8be6\u89e3"),

  h2("4 \u7ecf\u8425\u603b\u89c8"),
  body("\u63a7\u5236\u53f0\u9996\u9875\u5448\u73b0\u5168\u5c40\u7ecf\u8425\u6001\u52bf\uff1a\u8fd1 7 \u5929\u9500\u552e\u989d\u4e0e\u73af\u6bd4\u3001\u9500\u91cf\u3001\u6bdb\u5229\u7387\u3001\u5f85\u5904\u7406\u5f02\u5e38\u4e0e\u5f85\u5ba1\u6279\u8ba1\u6570\u4e00\u76ee\u4e86\u7136\uff0c\u5e76\u63d0\u4f9b 30 \u5929\u9500\u552e\u8d8b\u52bf\u4e0e\u95e8\u5e97\u6392\u884c\u3002\u53f3\u4e0a\u89d2\u201c\u8fd0\u884c Agent\u201d\u6309\u94ae\u4e00\u952e\u5b8c\u6210\u53d1\u73b0\u5f02\u5e38\u2192\u539f\u56e0\u5206\u6790\u2192\u751f\u6210\u5efa\u8bae\u2192\u6267\u884c\u5168\u6d41\u7a0b\u3002"),
  ...figure("shot-overview.png", "\u56fe 4-1 \u7ecf\u8425\u603b\u89c8\uff1aKPI \u3001\u8d8b\u52bf\u4e0e\u6700\u65b0\u5f02\u5e38"),

  h2("5 \u5f02\u5e38\u4e2d\u5fc3\uff1a\u81ea\u52a8\u53d1\u73b0"),
  h3("5.1 \u68c0\u6d4b\u7b97\u6cd5"),
  body("\u611f\u77e5\u5c42\u4ee5\u4f20\u7edf\u7edf\u8ba1\u7b97\u6cd5\u800c\u975e\u5927\u6a21\u578b\u731c\u6d4b\u53d1\u73b0\u5f02\u5e38\uff1a\u5148\u7528\u524d 28 \u5929\u6eda\u52a8\u4e2d\u4f4d\u6570\u4e0e MAD \u5efa\u7acb\u57fa\u7ebf\uff0c\u518d\u5bf9\u8fd1 14 \u5929\u9010\u65e5\u8ba1\u7b97 z-score \u4e0e\u504f\u5dee\u6bd4\u4f8b\uff0c\u8fde\u7eed 2 \u5929\u4ee5\u4e0a\u504f\u79bb\u5373\u8bc6\u522b\u4e3a\u5f02\u5e38\u6bb5\uff1b\u53e6\u8bbe\u5ba2\u8bc9\u6fc0\u589e\u3001\u5e93\u5b58\u5f52\u96f6\u7b49\u4e1a\u52a1\u89c4\u5219\u3002\u6bcf\u4e2a\u5f02\u5e38\u5747\u643a\u5e26\u89c2\u5bdf\u503c\u3001\u671f\u671b\u503c\u3001\u504f\u5dee\u3001\u4e25\u91cd\u5ea6\u4e0e\u6570\u636e\u8bc1\u636e\u3002"),
  h3("5.2 \u5f02\u5e38\u5217\u8868"),
  ...figure("shot-anomalies.png", "\u56fe 5-1 \u5f02\u5e38\u4e2d\u5fc3\uff1a\u81ea\u52a8\u53d1\u73b0\u7684\u5f02\u5e38\u5217\u8868\uff0c\u6309\u4e25\u91cd\u5ea6\u6807\u8bb0"),

  h2("6 \u6839\u56e0\u5206\u6790"),
  body("\u70b9\u51fb\u4efb\u4e00\u5f02\u5e38\u8fdb\u5165\u8be6\u60c5\u9875\uff0c\u5de6\u4fa7\u4e3a\u68c0\u6d4b\u8bc1\u636e\u94fe\uff08\u5168\u90e8\u6765\u81ea\u4e1a\u52a1\u7cfb\u7edf\u771f\u5b9e\u6570\u636e\uff09\uff0c\u53f3\u4fa7\u4e3a\u539f\u56e0\u5206\u6790\uff1a\u7cfb\u7edf\u5bf9\u7f3a\u8d27\u3001\u4f9b\u5e94\u94fe\u5ef6\u8fdf\u3001\u4fc3\u9500\u3001\u7ade\u54c1\u4fc3\u9500\u3001\u5929\u6c14\u3001\u5ba2\u8bc9\u3001\u4f1a\u5458\u6d41\u5931\u3001\u4e34\u671f\u3001\u4ef7\u683c\u4e5d\u7c7b\u5047\u8bbe\u5e76\u884c\u9a8c\u8bc1\uff0c\u4ec5\u5f53\u8bc1\u636e\u81f3\u5c11 2 \u6761\u4e14\u65b9\u5411\u76f8\u5bb9\u65f6\u65b9\u53ef\u5165\u9009\u6839\u56e0\uff0c\u6309\u7f6e\u4fe1\u5ea6\u6392\u5e8f\u53d6 Top3\uff1b\u8bc1\u636e\u4e0d\u8db3\u65f6\u663e\u5f0f\u8f6c\u4eba\u5de5\u800c\u975e\u786c\u7ed9\u7ed3\u8bba\u3002"),
  ...figure("shot-anomaly-detail.png", "\u56fe 6-1 \u5f02\u5e38\u8be6\u60c5\uff1a\u8bc1\u636e\u94fe\u3001\u6839\u56e0 Top3\uff08\u7f6e\u4fe1\u5ea6\u4e0e\u8d21\u732e\u5360\u6bd4\uff09\u4e0e\u7ed3\u8bba\u53d9\u8ff0"),

  h2("7 \u8865\u8d27\u4e0e\u4fc3\u9500\u5efa\u8bae"),
  body("\u51b3\u7b56\u5c42\u6309\u6839\u56e0\u5339\u914d\u6253\u6cd5\u5e93\u751f\u6210\u5efa\u8bae\u5361\uff1a\u8865\u8d27\u5efa\u8bae\u81ea\u52a8\u8ba1\u7b97\u8986\u76d6\u5929\u6570\u5e76\u5411\u4e0a\u53d6\u6574\u5230\u4f9b\u5e94\u5546\u6700\u5c0f\u8d77\u8ba2\u91cf\uff1b\u4fc3\u9500\u5efa\u8bae\u81ea\u52a8\u6821\u9a8c\u6bdb\u5229\u5e95\u7ebf\u3001\u6298\u6263\u4e0a\u9650\u4e0e\u9884\u7b97\u4e0a\u9650\u3002\u6bcf\u5f20\u5efa\u8bae\u5361\u5747\u7ed9\u51fa\u9884\u4f30\u6210\u672c\u3001\u9884\u4f30\u6536\u76ca\u3001ROI \u4e0e\u9500\u91cf\u6062\u590d\u6bd4\u4f8b\uff0c\u4f9b\u51b3\u7b56\u8005\u76f4\u89c2\u6bd4\u8f83\uff1b\u4efb\u4f55\u8fdd\u53cd\u786c\u7ea6\u675f\u7684\u65b9\u6848\u5728\u751f\u6210\u9636\u6bb5\u5373\u88ab\u4e22\u5f03\uff0c\u7ea6\u675f\u8fdd\u53cd\u7387\u4e3a 0\u3002"),
  ...figure("shot-decisions.png", "\u56fe 7-1 \u8865\u8d27/\u4fc3\u9500\u5efa\u8bae\uff1a\u98ce\u9669\u7b49\u7ea7\u3001ROI \u4e0e\u7ea6\u675f\u68c0\u67e5\u660e\u7ec6"),

  h2("8 \u6388\u6743\u6267\u884c\u4e0e\u5ba1\u6279"),
  body("\u6267\u884c\u5c42\u4e25\u683c\u9075\u5b88\u201c\u5148\u5efa\u8bae\u3001\u540e\u6267\u884c\u201d\uff1a\u4f4e\u98ce\u9669\u5efa\u8bae\uff08\u5982\u5e38\u89c4\u8865\u8d27\u300110% \u4ee5\u5185\u6298\u6263\uff09\u81ea\u52a8\u6267\u884c\uff1b\u8d85\u51fa Agent \u6388\u6743\u7684\u9ad8\u98ce\u9669\u52a8\u4f5c\uff08\u6298\u6263\u8d85\u8fc7 10%\u3001\u9884\u7b97\u8d85\u8fc7 1 \u4e07\u3001\u8de8\u533a\u57df\u8c03\u62e8\u7b49\uff09\u4e00\u5f8b\u751f\u6210\u5ba1\u6279\u5355\u8f6c\u4eba\u5de5\uff0c\u5ba1\u6279\u4e2d\u5fc3\u4ec5\u98ce\u63a7\u5ba1\u6279\u4eba\uff08L3\uff09\u53ef\u64cd\u4f5c\uff0c\u901a\u8fc7\u540e\u81ea\u52a8\u6267\u884c\u3002"),
  ...figure("shot-approvals.png", "\u56fe 8-1 \u5ba1\u6279\u4e2d\u5fc3\uff1a\u9ad8\u98ce\u9669\u52a8\u4f5c\u7684\u4eba\u5de5\u786e\u8ba4\u4e0e\u98ce\u9669\u539f\u56e0"),

  h2("9 \u6267\u884c\u8bb0\u5f55\u4e0e\u5ba1\u8ba1"),
  body("\u6bcf\u4e00\u6b65\u6267\u884c\u5747\u6709\u72b6\u6001\u673a\u7ba1\u7406\uff08\u5f85\u6267\u884c\u2192\u6267\u884c\u4e2d\u2192\u6210\u529f/\u5931\u8d25\u2192\u5df2\u8865\u507f\uff09\uff1b\u5ba1\u8ba1\u65e5\u5fd7\u8bb0\u5f55\u8c01\u5728\u4ec0\u4e48\u65f6\u5019\u5bf9\u4ec0\u4e48\u505a\u4e86\u4ec0\u4e48\uff0c\u901a\u8fc7\u8fc7 trace_id \u53ef\u4e00\u952e\u8fd8\u539f\u201c\u53d1\u73b0\u2192\u5206\u6790\u2192\u5efa\u8bae\u2192\u6267\u884c\u201d\u5b8c\u6574\u94fe\u8def\uff0c\u901a\u8fc7\u4e0e\u62d2\u7edd\u540c\u6837\u7559\u75d5\u3002"),
  ...figure("shot-executions.png", "\u56fe 9-1 \u6267\u884c\u8bb0\u5f55\uff1a\u72b6\u6001\u673a\u4e0e\u4e1a\u52a1\u5355\u636e\u5173\u8054"),
  ...figure("shot-audit.png", "\u56fe 9-2 \u5ba1\u8ba1\u65e5\u5fd7\uff1a\u652f\u6301 trace_id \u8fc7\u6ee4\u7684\u5168\u94fe\u8def\u7559\u75d5"),
);

/* ===== 第三篇 治理与安全 ===== */
bodyChildren.push(
  h1("\u7b2c\u4e09\u7bc7 \u6cbb\u7406\u4e0e\u5b89\u5168"),

  h2("10 \u6743\u9650\u77e9\u9635\u4e0e\u7b56\u7565\u5f15\u64ce"),
  tableTitle("\u8868 10-1 \u89d2\u8272\u6743\u9650\u77e9\u9635"),
  table(
    ["\u89d2\u8272", "\u6743\u9650\u7ea7", "\u80fd\u505a\u4ec0\u4e48"],
    [
      ["\u98ce\u63a7\u5ba1\u6279\u4eba", "L3", "\u552f\u4e00\u53ef\u5ba1\u6279\u9ad8\u98ce\u9669\u52a8\u4f5c"],
      ["\u4f9b\u5e94\u94fe\u8ba1\u5212\u5458/\u4f1a\u5458\u8fd0\u8425/\u533a\u57df\u7ecf\u7406/\u5e97\u957f/\u5ba2\u670d\u4e3b\u7ba1/\u603b\u90e8\u8fd0\u8425", "L2", "\u4f4e\u98ce\u9669\u5199\u5165\uff1b\u5e97\u957f\u4ec5\u9650\u672c\u5e97\u6570\u636e"],
      ["Agent \u670d\u52a1\u8eab\u4efd", "L2\uff08\u786c\u4e0a\u9650\uff09", "\u4f4e\u98ce\u9669\u81ea\u52a8\u6267\u884c\uff1b\u4efb\u4f55\u9ad8\u98ce\u9669\u4e00\u5f8b\u8f6c\u5ba1\u6279"],
      ["\u533f\u5408/\u672a\u6388\u6743", "L0", "\u53ea\u8bfb\uff0c\u5199\u5165\u4e00\u5f8b\u62d2\u7edd"],
    ],
    [34, 18, 48],
  ),
  tableTitle("\u8868 10-2 \u98ce\u9669\u89c4\u5219\uff08\u7b56\u7565\u5f15\u64ce\u6d88\u8d39\u673a\u5668\u53ef\u8bfb\u89c4\u5219\u5e93\uff09"),
  table(
    ["\u89c4\u5219", "\u5904\u7f6e"],
    [
      ["\u4fc3\u9500\u6298\u6263\u8d85\u8fc7 10%", "\u5fc5\u987b\u5ba1\u6279"],
      ["\u4fc3\u9500/\u89e6\u8fbe\u9884\u7b97\u8d85\u8fc7 1 \u4e07", "\u5fc5\u987b\u5ba1\u6279"],
      ["\u4efb\u4f55\u4ef7\u683c\u53d8\u66f4", "\u5fc5\u987b\u5ba1\u6279"],
      ["\u8de8\u533a\u57df\u5e93\u5b58\u8c03\u62e8", "\u5fc5\u987b\u5ba1\u6279"],
      ["\u6298\u6263\u8d85\u8fc7 30% / \u9884\u7b97\u8d85\u8fc7 10 \u4e07", "\u76f4\u63a5\u62d2\u7edd\uff08\u7981\u6b62\u52a8\u4f5c\uff09"],
      ["\u767d\u540d\u5355\u5916\u52a8\u4f5c", "\u62d2\u7edd\u6267\u884c"],
    ],
    [58, 42],
  ),

  h2("11 \u5199\u64cd\u4f5c\u56db\u4fdd\u9669"),
  bullet("\u76f8\u540c idempotency_key \u91cd\u590d\u63d0\u4ea4\u91cd\u653e\u9996\u6b21\u7ed3\u679c\uff0c\u4e0d\u91cd\u590d\u4e0b\u5355\uff1b\u540c\u952e\u4e0d\u540c\u8bf7\u6c42\u76f4\u63a5\u62d2\u7edd\uff1b", "\u5e42\u7b49\uff1a"),
  bullet("\u4efb\u4f55\u5199\u5165\u53ef\u9884\u6f14\uff0c\u4e0d\u843d\u5e93\u4e5f\u7559\u5ba1\u8ba1\u75d5\uff1b", "\u9884\u6f14\uff1a"),
  bullet("\u6210\u529f\u3001\u62d2\u7edd\u3001\u5931\u8d25\u5747\u5199\u5ba1\u8ba1\u65e5\u5fd7\uff0ctrace_id \u8d2f\u7a7f\u5168\u94fe\u8def\uff1b", "\u5ba1\u8ba1\uff1a"),
  bullet("\u8865\u8d27\u3001\u8c03\u62e8\u3001\u4fc3\u9500\u3001\u5de5\u5355\u5747\u652f\u6301\u8865\u507f\u56de\u9000\uff0c\u5e93\u5b58\u4e0e\u5355\u636e\u540c\u6b65\u6062\u590d\u3002", "\u8865\u507f\uff1a"),
);

/* ===== 第四篇 部署与使用 ===== */
bodyChildren.push(
  h1("\u7b2c\u56db\u7bc7 \u90e8\u7f72\u4e0e\u4f7f\u7528"),

  h2("12 \u5feb\u901f\u542f\u52a8"),
  bullet("Windows \u6267\u884c scripts\\start.bat\uff0c\u6216 macOS/Linux \u6267\u884c bash scripts/start.sh\uff1b\u9996\u6b21\u542f\u52a8\u81ea\u52a8\u5b89\u88c5\u4f9d\u8d56\u5e76\u751f\u6210\u6f14\u793a\u6570\u636e\uff1b", "\u4e00\u952e\u811a\u672c\uff1a"),
  bullet("docker compose up --build\uff0c\u9002\u7528\u4e8e\u5bb9\u5668\u5316\u73af\u5883\uff1b", "\u5bb9\u5668\uff1a"),
  bullet("pip install -r backend/requirements.txt \u540e python scripts/generate.py \u518d\u542f\u52a8\u670d\u52a1\uff1b", "\u624b\u52a8\uff1a"),
  bullet("\u6253\u5f00 http://127.0.0.1:8300\uff0c\u6309\u63a7\u5236\u53f0\u53f3\u4e0a\u89d2\u201c\u8fd0\u884c Agent\u201d\u5373\u53ef\u4f53\u9a8c\u5b8c\u6574\u95ed\u73af\u3002", "\u8bbf\u95ee\uff1a"),

  h2("13 \u5728\u7ebf\u9884\u89c8\u4e0e\u7248\u672c\u8fed\u4ee3"),
  body("\u7cfb\u7edf\u5df2\u90e8\u7f72\u81f3 GitHub Pages \u63d0\u4f9b\u53ea\u8bfb\u5728\u7ebf\u9884\u89c8\uff1b\u4ee3\u7801\u6258\u7ba1\u4e8e GitHub \u4ed3\u5e93\uff0c\u6bcf\u6b21\u63d0\u4ea4\u63a8\u9003\u540e Actions \u81ea\u52a8\u91cd\u5efa\u6f14\u793a\u6570\u636e\u5feb\u7167\u5e76\u53d1\u5e03\uff0c\u4ee3\u7801\u53d8\u66f4\u4e0e\u7248\u672c\u8fed\u4ee3\u5728 Commits \u4e2d\u5b8c\u6574\u53ef\u67e5\u3002"),
  ...figure("shot-pages.png", "\u56fe 13-1 GitHub Pages \u5728\u7ebf\u53ea\u8bfb\u9884\u89c8\uff08\u65e0\u540e\u7aef\u73af\u5883\u81ea\u52a8\u964d\u7ea7\u4e3a\u6570\u636e\u5feb\u7167\uff09"),

  h2("14 \u9a8c\u6536\u7ed3\u679c"),
  tableTitle("\u8868 14-1 \u5168\u91cf\u9a8c\u6536\u6307\u6807\uff08\u542b\u771f\u5b9e LLM \u73af\u5883\uff09"),
  table(
    ["\u9a8c\u6536\u9879", "\u7ed3\u679c"],
    [
      ["\u6d4b\u8bd5\u5957\u4ef6\uff08\u5355\u5143 + \u96c6\u6210 + Playwright \u7aef\u5230\u7aef\uff09", "42/42 \u5168\u90e8\u901a\u8fc7"],
      ["3 \u7c7b\u6ce8\u5165\u5f02\u5e38\u53ec\u56de\u7387", "100%\uff08\u9ad8\u4e8e 90% \u9a8c\u6536\u7ebf\uff09"],
      ["\u6839\u56e0 Top3 \u547d\u4e2d\u7387", "100%\uff08\u9ad8\u4e8e 80% \u9a8c\u6536\u7ebf\uff09"],
      ["\u5efa\u8bae\u7ea6\u675f\u8fdd\u53cd\u7387", "0"],
      ["\u9ad8\u98ce\u9669\u5ba1\u6279\u5408\u89c4\u7387", "100%"],
      ["\u81ea\u52a8\u6267\u884c\u6210\u529f\u7387", "100%"],
      ["LLM \u53d9\u8ff0\u9632\u7f16\u9020\u6821\u9a8c", "DeepSeek \u5b9e\u6d4b\u901a\u8fc7\uff0c\u6570\u5b57\u5168\u90e8\u6765\u81ea\u5de5\u5177\u4e8b\u5b9e"],
      ["GitHub Pages \u5728\u7ebf\u9884\u89c8", "\u5df2\u4e0a\u7ebf\u5e76\u9010\u9875\u9a8c\u8bc1"],
    ],
    [58, 42],
  ),

  h2("15 \u5e38\u89c1\u95ee\u9898"),
  bullet("\u9996\u6b21\u542f\u52a8\u9700\u751f\u6210\u6f14\u793a\u6570\u636e\uff0c\u7ea6 1 \u5206\u949f\uff1b\u540e\u7eed\u542f\u52a8\u76f4\u63a5\u8fd0\u884c\u3002", "Q\uff1a\u542f\u52a8\u591a\u4e45\u80fd\u7528\uff1f"),
  bullet("\u5728\u7ebf\u9884\u89c8\u4e3a\u53ea\u8bfb\u5feb\u7167\uff1b\u8fd0\u884c Agent\u3001\u5ba1\u6279\u3001\u6267\u884c\u7b49\u5199\u64cd\u4f5c\u9700\u672c\u5730\u542f\u52a8\u540e\u7aef\u3002", "Q\uff1a\u5728\u7ebf\u9884\u89c8\u80fd\u64cd\u4f5c\u5417\uff1f"),
  bullet("\u4e0d\u9700\u8981\u3002\u672a\u914d\u7f6e API Key \u65f6\u81ea\u52a8\u4f7f\u7528\u79bb\u7ebf\u6a21\u677f\u53d9\u8ff0\uff0c\u5168\u90e8\u529f\u80fd\u4e0d\u53d7\u5f71\u54cd\uff1b\u914d\u7f6e\u65b9\u5f0f\u89c1 .env.example\u3002", "Q\uff1a\u5fc5\u987b\u914d\u7f6e\u5927\u6a21\u578b\u5417\uff1f"),
  bullet("\u590d\u5236\u4ed3\u5e93\u540e\u6309 README \u542f\u52a8\u5373\u53ef\uff1b\u6240\u6709\u6570\u636e\u5747\u4e3a Mock \u751f\u6210\uff08\u56fa\u5b9a\u79cd\u5b50\u53ef\u91cd\u590d\uff09\uff0c\u4e0d\u4f9d\u8d56\u4efb\u4f55\u771f\u5b9e\u4f01\u4e1a\u7cfb\u7edf\u3002", "Q\uff1a\u5982\u4f55\u5728\u81ea\u5df1\u73af\u5883\u8dd1\u8d77\u6765\uff1f"),
);

/* ---------- 组装文档 ---------- */
const doc = new Document({
  creator: "Retail Decision Agent",
  title: "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf \u4ea7\u54c1\u767d\u76ae\u4e66 V1.0",
  styles: {
    default: {
      document: {
        run: { font: CN, size: 24, color: "000000" },
        paragraph: { spacing: { line: 312 } },
      },
      heading1: {
        run: { font: CN_HEI, size: 32, bold: true, color: ACCENT },
        paragraph: { spacing: { before: 240, after: 200, line: 312 }, outlineLevel: 0 },
      },
      heading2: {
        run: { font: CN_HEI, size: 28, bold: true, color: "0B1220" },
        paragraph: { spacing: { before: 280, after: 140, line: 312 }, outlineLevel: 1 },
      },
      heading3: {
        run: { font: CN_HEI, size: 24, bold: true, color: "0B1220" },
        paragraph: { spacing: { before: 220, after: 110, line: 312 }, outlineLevel: 2 },
      },
    },
  },
  sections: [
    { // 封面（无页眉页脚）
      properties: {
        page: { size: { width: 11906, height: 16838 }, margin: { top: 1417, bottom: 1417, left: 1701, right: 1701 } },
      },
      children: coverChildren,
    },
    { // 功能目录 + 目录（罗马页码）
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1417, bottom: 1417, left: 1701, right: 1701 },
          pageNumbers: { start: 1, formatType: NumberFormat.UPPER_ROMAN },
        },
      },
      headers: { default: pageHeader() },
      footers: { default: pageFooter() },
      children: [...functionIndex, ...tocChildren],
    },
    { // 正文（阿拉伯页码从 1）
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1417, bottom: 1417, left: 1701, right: 1701 },
          pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL },
        },
      },
      headers: { default: pageHeader() },
      footers: { default: pageFooter() },
      children: bodyChildren,
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  console.log("Written:", OUT, (buffer.length / 1024).toFixed(0) + "KB");
});
