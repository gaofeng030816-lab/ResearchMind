# PDF 公式识别与 LaTeX 隔离 Spike

日期：2026-08-31

状态：历史 V3 candidate Spike evidence；明确排除于 V2 验收。V3-G5 已采用独立的 production detector/single-crop recognizer 边界，本文件中的 Spike 代码仍未直接接入 `src/researchmind/`。最终决定见 [V3_G5_FORMULA_RECOGNITION_DECISION.md](./V3_G5_FORMULA_RECOGNITION_DECISION.md)

分支：`codex/spike-pdf-formula-latex`

## 问题与结论

目标不是继续把带等号的文本块简单标为 `formula`，而是回答三个问题：

1. 数字 PDF 能否定位真实公式区域并保留 page / source line / bbox；
2. 数字文字层能否直接可靠还原二维 LaTeX；
3. 当文字层损坏或公式本身是图片时，现有 dots 模型能否只接收一个用户确认的
   公式裁剪图并返回严格 LaTeX。

结论：

- PyMuPDF 的 span 字体、字号、基线和 bbox 足以在两张人工标注页上定位数字显示
  公式，并能把跨多个原始块的同一公式合并为一个有来源的区域；
- 真实复杂显示公式的数字文字层存在控制字符、字体编码损坏和分式二维关系丢失，
  三个英文显示公式均不能产生可信的确定性 LaTeX，因此“只改正则”不可采用；
- 中文数字版样本页的一条肉眼可见显示公式实际是宽而短的 JPEG，不存在 PDF
  文字层。隔离图片几何规则正确找到该一条区域，没有把整页扫描图或零碎小图元
  当成公式；
- `dots3-note-prev` 的官方模型说明支持图像输入；两次许可自由裁剪的真实端点
  探针分别正确返回带上下标集合和堆叠分式的 LaTeX。官方多模态输入说明见
  [dots3-note README_CN](https://github.com/studio-dots-ai/dots3-note-prev/blob/main/README_CN.md)；
- 生产推荐不是安装 OpenDataLoader/Docling，而是先采用“本地定位与裁剪、用户确认、
  只外发公式 crop、严格解析、预览后接受”的小边界。正式接入仍需确认新的
  `FormulaRegion` 与窄 `FormulaVisionProvider` 架构。

## Before / After 证据

| 样本 | 当前生产基线 | Spike 结果 | 人工标签 |
|---|---:|---:|---:|
| 英文双栏页 3 | 4 个 formula 文本块 | 3 个 display region；27 个 inline 候选仅作观察 | 3 个 display |
| 中文数字版页 20 | 0 个 formula 文本块；1 个普通 image region | 0 个数字 display；1 个 image-formula 候选；8 个 inline 候选 | 0 个数字 display；1 个图片公式 |
| 中文扫描页 1 | 0 文本块；1 整页 image region | 0 数字候选；0 图片公式候选 | 未做公式级标签 |

英文页 3 个真实显示公式的定位为 3/3，但确定性 LaTeX 为 0/3。后者是有价值的
失败证据：区域 bbox 可用于视觉转换，损坏的扁平文本不能冒充二维公式真值。
inline 数量没有完整人工标签，因此不写 precision / recall；若进入产品，默认只展示
display / embedded-image 公式，inline 候选应折叠为可选项。

19 项离线 Spike 测试全部通过：

- 10 项数字几何：上下标、Unicode 映射、inline 边界、中英文正文误报、代码误报、
  跨块合并、图片/分式/矩阵能力边界、真实 PyMuPDF dict；
- 9 项 vision：宽短图片候选、整页扫描排除、crop 页边界/像素/字节限制、固定
  data URL 请求、严格 `<latex>` / `<unreadable/>` 协议、危险 TeX/任意认证头拒绝和
  fake provider。

项目全量回归为 `288 passed, 1 skipped in 13.52s`；跳过项仍是当前 Windows
主机不允许测试创建 symlink。`pip check` 返回 `No broken requirements found.`。

两次 live 调用只使用
`output/pdf/formula-spike-visual-corpus.pdf` 中的许可自由公式，没有发送课程论文、
整页、PDF 路径或 API Key：

| 合成类别 | crop | 结果 |
|---|---:|---|
| 嵌入位图、集合与上下标 | 18,493 bytes | `T = \\{(x_i, y_i)\\}_{i=1}^{N}` |
| 堆叠分式 | 3,060 bytes | `\\frac{a + b}{c + d}` |

端点成功只证明当前请求格式可用，不证明真实论文公式质量。课程论文的真实 crop
不得因为本 Spike 自动外发；必须在界面显示 crop 和外发提示后由用户逐条确认。

## OpenDataLoader-PDF 复核

本地源码确认 `--enrich-formula` 可产生带 page / bbox / LaTeX content 的 formula
JSON，但它要求：

- 安装 `docling[easyocr]`、FastAPI、Uvicorn 和 multipart 等 hybrid extras；
- 运行第二个本地服务，并在客户端使用 whole-document/full routing，否则 enrichment
  可能被静默跳过；
- 当前机器没有 docling、easyocr、opendataloader-pdf、Java 或构建 JAR；
- whole-document 路由扩大内存、安装、进程和隐私边界。

因此延续 T2 决定：OpenDataLoader/Docling 仍是候选，不作为当前公式能力的生产依赖。
只有在 crop-only 多模态路径的质量或隐私不满足需求、且用户接受本地大模型/OCR
安装成本时，才重新建立同语料可运行对照。

## V3 候选生产合同（待 V3 要求确认）

```text
PyMuPDF page
  -> FormulaRegion detector (local, no network)
  -> display / embedded-image candidate + page/bbox/origin/confidence
  -> user previews and selects one region
  -> size-limited PNG crop
  -> explicit external-transfer confirmation
  -> FormulaVisionProvider(dots3-note-prev)
  -> strict <latex> parser
  -> st.latex preview + editable source + provenance
  -> optional KnowledgeNote / Obsidian save
```

建议新增 ResearchMind 自有 `FormulaRegion`，不让 PyMuPDF dict、Docling element 或
provider response 进入 Core/UI。`FormulaVisionProvider` 应与当前 text-only
`LlmProvider` 分开，输入只接收 PNG bytes 与固定 prompt；不开放路径、整页、PDF、
任意 message、工具或自动循环。

生产 UI 默认只显示 display 与 embedded-image 候选；inline 置于“更多公式候选”。
转换和保存必须分开点击。结果标记为 `model_reconstructed`，不能称为原文真值。

## V3 进入门禁

在任何 post-V2 产品集成前至少还需：

1. 用户确认上述 `FormulaRegion + FormulaVisionProvider + 逐条 crop 外发` 合同；
2. 对至少 3 份论文建立 15–20 条人工公式区域和参考 LaTeX，分开记录 display
   region 命中、bbox、normalized/structural match、人工可读性和失败；
3. 真实论文 crop 的外发由用户逐条确认；自动回归只用许可自由 fixture/fake provider；
4. 验证 Streamlit crop 预览、重复点击防护、错误/超时、`<unreadable/>`、危险 TeX、
   重选失效、KnowledgeNote 来源和无网络打开 PDF 回归；
5. 不改动 `2.0.0rc1` V2 冻结主线；只有 V3 要求明确批准后，生产化才在独立
   内部版本分支完成并保持可整体回滚。

## 验证命令

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_pdf_formula_latex_spike.py `
  tests\unit\test_pdf_formula_vision_spike.py -q `
  --basetemp .release-tmp\formula-vision-unit

& .\.venv\Scripts\python.exe experiments\pdf_formula_latex_spike\benchmark.py `
  --sample code_security=D:\path\2408.02509v1.pdf `
  --sample statistical_learning=D:\path\统计学习方法李航(非扫描版).pdf `
  --sample chinese_scan=D:\path\chinese_scan.pdf
```

详细匿名化结果见
`experiments/pdf_formula_latex_spike/current_results_2026-08-31.json`。
