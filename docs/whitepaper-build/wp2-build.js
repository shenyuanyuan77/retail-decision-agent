/* 白皮书 V2.0 主生成脚本：封面 → 功能目录 → 目录 → 正文九章 → 打包 */
const K = require("./wp2-kit");
const { ch1, ch2, ch3 } = require("./wp2-ch1-3");
const { ch4 } = require("./wp2-ch4");
const { ch5, ch6, ch7, ch8, ch9 } = require("./wp2-ch5-9");
const {
  Document, Packer, fs, OUT, pageHeader, pageFooter, cover, functionIndex, toc,
} = K;

const children = [
  ...cover,
  ...functionIndex,
  ...toc,
  ...ch1, ...ch2, ...ch3, ...ch4, ...ch5, ...ch6, ...ch7, ...ch8, ...ch9,
];

const doc = new Document({
  creator: "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56 Agent",
  title: "\u96f6\u552e\u7ecf\u8425\u51b3\u7b56\u7cfb\u7edf \u4ea7\u54c1\u767d\u76ae\u4e66 V2.0",
  description: "\u53c2\u8003 ZCode Enterprise \u4f01\u4e1a\u7248\u4f7f\u7528\u624b\u518c\u4f53\u4f8b\u7f16\u5236",
  styles: {
    default: {
      document: {
        run: { font: K.FONT, size: 21, color: K.INK },
        paragraph: { spacing: { line: 340 } },
      },
      heading1: { run: { font: K.FONT, size: 21, bold: true, color: K.ACCENT } },
      heading2: { run: { font: K.FONT, size: 17, bold: true, color: K.ACCENT2 } },
      heading3: { run: { font: K.FONT, size: 13, bold: true, color: K.ACCENT3 } },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },   // Letter，与参考手册一致
        margin: { top: 1000, bottom: 1000, left: 1150, right: 1150 },
      },
    },
    headers: { default: pageHeader() },
    footers: { default: pageFooter() },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("\u5df2\u751f\u6210:", OUT, (buf.length / 1024 / 1024).toFixed(2), "MB");
});
