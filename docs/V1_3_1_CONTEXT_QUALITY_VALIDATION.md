# V1.3.1 上下文质量纠错与公式文字层阅读验证

日期：2026-08-28

## 范围

V1.3.1 仍是内部版本，不对外发布。本轮按用户新增要求，在 V1.3 上下文质量
评测与纠错范围内加入数字版 PDF 数学公式阅读：

- `TextBlock.role` 增加 `formula`；
- `pdf/layout.py` 使用保守的确定性规则标记数字文字层公式/符号候选；
- 普通段落继续整理为复制友好的单段文本，公式候选保留可用行边界；
- 阅读器标记疑似公式块，允许逐块复制，并提示复杂排版需对照页面图像；
- `ResearchContext.related_formula` 合并选择前后 2 个块内的公式候选，限制为
  500 字符；
- 数学解释和追问的 prompt、发送前预览使用同一 `related_formula`；
- 上下文预览的当前问题、选择、公式和周边文本使用固定高度，长内容在区域内
  滚动；
- 收紧章节标题和图注规则，排除参考文献、编号列表、算法控制词、正文图表引用
  和文档标题页眉等真实误判。

没有新增依赖，没有读取或输出 `.env`，没有调用真实 API，也没有写入用户的
Obsidian Vault。公式能力不包含 OCR、图片公式转 LaTeX、二维结构重建、公式
渲染或数学语义识别。

## 回归过程

实现前新增测试在收集阶段按预期失败：

```text
ImportError: cannot import name 'normalize_formula_text' from 'researchmind.pdf.layout'
```

实现后的聚焦测试：

```powershell
$env:PYTEST_ADDOPTS='--basetemp=.pytest-tmp/v131-focused-4'
& .\.venv\Scripts\python.exe -m pytest tests/unit/test_core_research_context.py tests/unit/test_pdf_reader.py tests/unit/test_llm_prompts.py tests/unit/test_context_preview_use_cases.py tests/e2e/test_streamlit_app.py -q
```

结果：`72 passed in 5.31s`。

全量测试：

```powershell
$env:PYTEST_ADDOPTS='--basetemp=.pytest-tmp/v131-full'
& .\.venv\Scripts\python.exe -m pytest -q
```

最终复核结果：`154 passed`；同时运行 `compileall` 和 `pip check`，Python 编译
通过，依赖检查返回 `No broken requirements found.`。

## 真实论文结构评测

只读打开以下六份本地数字版 PDF：两份通用英文论文、Neural ODE、Tidy Data、
中文《统计学习方法》和 OpenDataLoader PDF 自带的代码安全论文样本。下表是规则
角色计数，不代表逐项人工标注的召回率；“公式”是文字层候选块/片段，不是完整
方程数量。

| 样本 | 标题块（修改前→后） | 图注块（修改前→后） | 公式候选（后） |
|------|----------------------|----------------------|----------------|
| 1201.0490v4 | 14 → 8 | 1 → 1 | 0 |
| 1907.10121v1 | 93 → 5 | 4 → 4 | 0 |
| Neural ODE | 30 → 13 | 12 → 11 | 242 |
| Tidy Data | 51 → 31 | 23 → 20 | 0 |
| 统计学习方法 | 198 → 170 | 67 → 53 | 16 |
| 2408.02509v1 | 40 → 18 | 12 → 12 | 16 |

核对结论：

- 1201 和 SciPy 样本中的短参考文献不再成为章节标题；
- Neural ODE 与代码安全论文中的算法编号、公式片段不再成为章节标题；
- Tidy Data 的编号列表，以及 `Table 3 reorganises...`、
  `Table 4 shows...` 等正文引用不再成为结构线索；
- 中文样本中 `图1.2给出了...` 等正文引用不再成为图注；
- `4 Tidy Data` 这类带页码的文档标题页眉在块角色层仍可能被标为 heading，
  但 ResearchContext 会按文档标题跳过，不再覆盖真实章节；
- Neural ODE 的 PDF 文字层把二维公式拆成大量小块，因此候选数较高；阅读器和
  上下文把它们诚实标为候选/片段，不宣称恢复了完整公式。

## 真实公式离线烟测

从 Neural ODE 第 1 页选择实际提取出的公式
`ht+1 = ht + f(ht, θt) / (1)`，使用显式 `Settings` 生成数学解释预览：

```text
selected_page=1
section=1 Introduction Residual Network ODE Network
related_formula=ht+1 = ht + f(ht, θt) / (1)
request_chars=2539
request_tokens_approx=635
```

该过程没有创建 LLM provider，也没有网络调用。

## PDF 与界面验收

- Poppler 成功把 Neural ODE 第 1 页、中文样本第 20 页和代码安全论文第 3 页
  渲染为 PNG；旧 PDF 字体产生 `No display font for Symbol/ArialUnicode` 警告，
  但输出文件均生成；
- Streamlit AppTest 验证公式页出现“疑似数学公式”说明和“数学公式候选”块，
  且完整 UI 回归通过；
- 当前 Codex 本地图片查看器仍因 Windows sandbox `helper_unknown_error` 无法读取
  PNG，Browser 的 Node 控制进程也连续退出，因此本轮无法把人工截图视觉检查
  记为通过。该限制不影响自动化结果，但真实窗口下的滚动高度、窄窗口换行和
  公式块密度仍需下一次人工打开应用确认。

## 已知限制

- 规则追求低误关联而非高召回，非标准标题或无显式分隔符的图注可能漏识别；
- 公式候选依赖 PDF 文字层，扫描版、图片公式和缺字字体无法恢复；
- 二维分式、上下标、矩阵和对齐方程可能被拆成多个片段，复制文本不能保证等价
  于原公式；
- 数学解释仍由配置的 LLM 完成；候选标记本身不理解数学含义；
- 公式邻近范围是确定性的 ±2 文本块和 500 字符上限，复杂版面可能漏关联；
- 视觉验收未完成，不能据此声称所有窗口尺寸下布局无缺陷。

## 下一步建议

下一轮优先完成 V1.3.1 的真实浏览器视觉补验，并建立小型人工标注集，为标题、
图注和公式候选分别记录 precision/recall。随后再做“公式候选一键带入选择框”和
bbox 原文定位；图片公式 OCR/LaTeX 重建应作为独立架构评审，不与当前轻量规则
混合。
