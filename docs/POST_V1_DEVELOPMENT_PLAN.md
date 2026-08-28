# ResearchMind V1 之后的内部开发计划

日期：2026-08-28

## 发布策略

V1 和当前中间版本全部用于内部开发与验证，不对外发布。V1 的职责仍是稳定
以下闭环：

```text
本地 PDF → 阅读/选择 → 翻译或 ResearchContext AI
→ 追问 → KnowledgeNote → Markdown → Obsidian Vault
```

最终公开发布需要在该闭环之上具备代码识别、论文—数学—代码—笔记关联和更
进一步的智能化。上述能力属于未来独立产品与架构阶段，不授权在 V1 中预建
`CodeElement`、数据库、REST 服务、Agent 工具或向量数据库。

## 当前阶段：V1.x 内部优化

按以下顺序推进：

1. **可靠性与可观察性**：真实 PDF 兼容矩阵、低文本覆盖诊断、明确错误恢复；
2. **阅读性能**：消除 Streamlit rerun 引起的重复渲染，建立大文档基线；
3. **阅读质量**：双栏顺序、段落复制、搜索和原文定位持续回归；
4. **上下文质量**：在不发送整篇 PDF 的前提下改进相邻块与章节相关性；
5. **知识沉淀质量**：提高来源追溯、用户理解和 Obsidian Markdown 可读性。

每项优化继续遵守现有模块边界，不增加运行时依赖，除非真实证据证明现有技术
无法满足需求。

## 已完成迭代：V1.1 PDF 响应与可提取性

目标：

- 同一文件修订、页码和缩放的页面/图像只渲染一次，减少 Streamlit rerun 延迟；
- 缓存有界，源文件发生变化后自动失效；
- 文本覆盖率不超过 10% 时明确提示扫描版或图像型 PDF 的 OCR 限制；
- 不实现 OCR、公式识别或语义表格识别。

数据流：

```text
OpenedDocument
├─ get_page_view → pdf/ revision-aware render cache → PageView
└─ get_document_text_coverage → DocumentTextCoverage → reader warning
```

验证：

- 重复页面与图表渲染只打开一次 PyMuPDF；
- 修改为损坏文件后不能命中旧缓存，必须抛出项目错误；
- 空文本和 10% 文本覆盖文档触发诊断，正常文本 PDF 不触发；
- Streamlit AppTest、完整研究流和全量 pytest 不回归；
- 使用真实数字版和低文本覆盖 PDF 记录基线。

本迭代的实测结果见
[V1_1_OPTIMIZATION_VALIDATION.md](./V1_1_OPTIMIZATION_VALIDATION.md)。

## 已完成迭代：V1.2 ResearchContext 结构线索

目标：

- 从 PDF 文本块中保守识别章节标题与 Figure / Fig. / Table / 图 / 表说明；
- 选中内容可定位时，附加最近前置章节标题和同页邻近图表说明；
- 保持上下文任务有界，不发送全文，不引入 RAG、数据库或新的运行时依赖；
- 所有新增论文内容继续作为不可信数据转义并包裹在
  `<paper_context>` 中。

数据流：

```text
PyMuPDF text blocks
→ pdf/layout.py role classification
→ TextBlock(role)
→ core/research_context.py landmark selection
→ ResearchContext(section_heading, related_caption)
→ llm/prompts.py escaped paper_context
```

验证：

- 中英文标题与图表说明的高置信度规则有单元测试；
- 章节标题支持从上一页继承，说明仅关联同页前后 2 个文本块；
- 无定位选择不附加任意结构内容，远距离说明不关联；
- 恶意闭合标签在标题/说明字段中同样被转义；
- 使用生成 PDF 的集成测试验证结构角色能到达解释提示词；
- Streamlit AppTest 和全量 pytest 不回归。

本迭代的实测结果见
[V1_2_CONTEXT_VALIDATION.md](./V1_2_CONTEXT_VALIDATION.md)。

## 当前迭代：V1.3 上下文证据可见性

目标：

- AI 解释前展示页码、章节、邻近图表说明、当前问题、选择和周边文本；
- 输入有效追问后展示同类证据和预算内历史消息数量；
- 预览与真实调用共享 ResearchContext 和 prompt builder，避免“显示一套、发送
  另一套”；
- 请求体量按实际 `ChatMessage.content` 字符数与 4 字符/token 规则估算；
- 打开预览不创建 provider、不发网络、不写 session state。

数据流：

```text
selection + document + question + conversation + settings
→ app/use_cases.py builds ResearchContext
→ prompt builder creates ChatMessage list
├─ ContextEvidencePreview → views/context_evidence.py
└─ button click → LlmProvider.complete
```

验证：

- 预览包含 V1.2 章节/图表说明、当前问题和预算内历史数量；
- 预览字符数与真实解释/追问调用的消息字符数完全一致；
- 空追问和非法解释模式沿用既有错误语义；
- Streamlit AppTest 验证调用前能够看到结构证据和 token 估算；
- 全量 pytest、Python 编译和依赖一致性检查通过。

本迭代的实测结果见
[V1_3_CONTEXT_VISIBILITY_VALIDATION.md](./V1_3_CONTEXT_VISIBILITY_VALIDATION.md)。

## 已完成实现：V1.3.1 上下文质量评测、纠错与公式文字层阅读

V1.3.1 是 V1.3 的内部修订，不使用 V1.4 版本号。完成范围：

- 对 V1.3 上下文展开区补充固定高度的长文本显示和 Streamlit 回归验证；
- 选择六份代表性中英文数字版论文，记录标题/图表说明的正确关联、漏识别和
  误关联；
- 为规则缺陷先补回归样本，再做小范围分类与关联规则修正；
- 在用户新增范围内标记数字文字层中的保守公式候选，保留公式换行，并把邻近
  公式片段加入 ResearchContext 和发送前预览；
- 没有引入 OCR、图片公式转 LaTeX、模型分类器、RAG、数据库或代码识别。

实现与验证结果见
[V1_3_1_CONTEXT_QUALITY_VALIDATION.md](./V1_3_1_CONTEXT_QUALITY_VALIDATION.md)。
自动化和真实论文离线评测已完成；受当前 Codex Windows 浏览器/图片查看进程
异常影响，人工截图视觉补验仍保留为待办，不计为通过。

## 后续内部阶段

### 阅读与上下文

- 精细文本选择与 bbox 原文定位；
- 基于真实论文语料评估并迭代结构规则，必要时再评审更高级的章节树；
- 为上下文预览建立真实论文正确/漏识别/误关联评测；
- 图片公式/LaTeX 重建、表格、图表和 OCR 分别建立语料与基准后决定依赖；
- Streamlit 无法满足精细选择时，按 ARCHITECTURE.md 第 3.4 节进行 UI 架构评审。

### 代码识别与关联

开始前必须先定义：

- 支持的代码来源、语言和项目规模；
- `CodeContext` 与现有 `ResearchContext` 的边界；
- 论文公式/算法到代码符号的证据模型与可追溯方式；
- 模型是否拥有工具、工具权限、沙箱和确认机制；
- 代码与论文数据发送到外部模型时的隐私边界；
- UI 是否仍适合 Streamlit，是否出现 REST/编辑器扩展的真实触发条件。

只有这些决策经过确认，才进入实现。最终发布版本号在该阶段规格确定后再决定。
