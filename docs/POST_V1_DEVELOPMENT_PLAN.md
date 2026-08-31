# ResearchMind V1 之后的内部开发计划

同步日期：2026-08-31 · 状态：V1.1–V1.3.2、T5-A/T5-B1 与 T6-A–T6-D 已完成；当前为 2.0.0rc1 本地内部候选

> 本文保留 V1.x 优化的历史过程。当前阶段状态、进入/退出条件和 T1–T6 顺序以
> [V1→V2 过渡要求](../V1%20to%20V2过渡要求.md)为准。

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

## 已完成阶段：V1.x 内部优化

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

## 已完成迭代：V1.3 上下文证据可见性

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

## 已完成基线：V1.3.2 选择驱动的 LaTeX 与知识沉淀

本阶段把 V1.3.1 已能复制的公式文字层候选继续接入数学阅读闭环：

- 用户确认选择后，可在独立按钮发起 LaTeX 转换；
- 转换与数学解释一样先构建有界 ResearchContext，并提供无网络的发送前预览；
- 模型只允许返回一个 `<latex>...</latex>` 表达式体；应用拒绝整篇 TeX、
  显示分隔符、宏、文件/链接命令、外部资源和不受支持的环境；
- 对话面板同时显示可复制 LaTeX 源码和 Streamlit 数学预览；
- `KnowledgeNote.latex` 把选择、转换和来源一起沉淀到 Obsidian
  `$$...$$` 显示公式；
- 没有新增运行时依赖，不安装或调用 TeX 编译器，不读取图片公式。

实现与验证结果记录在
[V1_3_2_LATEX_VALIDATION.md](./V1_3_2_LATEX_VALIDATION.md)。

## 当前过渡阶段

| 门禁 | 状态 | 当前口径 |
|---|---|---|
| T0 基线封口与评测准备 | Completed | 环境阻塞已记录；真实小型评测集；174 项回归 |
| T1 Selection 与 provenance | Completed | 一键选择、page/block/bbox 来源、Context/KnowledgeNote 追溯；177 项回归 |
| T2 PDF / Mathematics evidence | Completed | 五份同语料基准；保留 PyMuPDF，OpenDataLoader 暂缓接入 |
| T3 CodeContext | Completed | 本地单文件夹、Python-first、固定上限、只读 AST、行/符号 provenance、有界预览；188 项回归 |
| T4 证据链接 | Completed | 用户确认的 Paper/Math/Algorithm–Code 双端点、关系、置信度、generation method 与 KnowledgeNote 导出；198 项回归 |
| T5 受限智能助手 | Completed（T5-A/T5-B1） | 三个当前会话只读证据工具；另有一个已选 Python 行范围的受控替换，逐动作确认、恢复副本、哈希冲突保护、安全回滚、无执行权限；261 项回归，1 项环境跳过 |
| T6 发布加固 | T6-A/T6-B/T6-C/T6-D Completed | 269 项源码回归通过（1 项环境 skip）；性能、2.0.0rc1 wheel、隔离启动、诊断和恢复复扫通过；用户于 2026-08-31 确认论文/代码/T5-B1 人工旅程通过；本地 Git 冻结且不公开发布 |

T6-D 人工验收提出的 Code → Obsidian 可选笔记已在冻结前实现并验证：当前代码
选择可生成带相对路径/行/符号 provenance 的专用 Markdown，先预览再显式保存，
不扩大源码写入或执行权限。PDF 阅读区域的防误触滚轮翻页仍是冻结后的 CCv2
Spike 候选，尚未实现。

以下旧“后续”条目保留为历史需求来源；T1–T5 已完成内容以架构和对应
验证记录为准：

### 阅读与上下文

- 精细文本选择与 bbox 原文定位；
- 基于真实论文语料评估并迭代结构规则，必要时再评审更高级的章节树；
- 为上下文预览建立真实论文正确/漏识别/误关联评测；
- 图片公式 OCR、自动整页 LaTeX 重建、表格、图表和 OCR 分别建立语料与基准后决定依赖；
- Streamlit 无法满足精细选择时，按 ARCHITECTURE.md 第 3.4 节进行 UI 架构评审。

### 代码识别与关联

T3 已完成：

- 代码来源为用户明确选择的一个本地文件夹，Python-first，2,000 文件/20 MB/
  单文件 1 MB；
- `CodeContext` 与 `ResearchContext` 为独立模型和 prompt；
- 代码外发仅含选择、最小邻近代码、相对路径/行/符号和问题；
- Streamlit 足以承载当前最小工作流，尚无 UI 重写证据。

T4 已完成：

- 论文/公式/算法选择与代码符号/行范围由用户显式确认；
- 链接记录双方 locator、关系、置信度、generation method 和可选依据；
- 链接只在会话内，随 KnowledgeNote 导出；当前没有跨会话需求证据，因此未
  引入 SQLite；
- 链接不调用模型，不自动关联，也不合并两个上下文 prompt。

T5-A 已完成：

- 工具固定为当前论文上下文、当前代码上下文和当前 EvidenceLink；
- 无参数、无写入/执行/网络搜索，逐次点击继续，3 工具/4 LLM 上限；
- 提示注入、越权、资源、停止和 provider/tool 错误已有自动化验收。

T5-B1 已完成：

- 只允许对当前已索引项目中一个已选择的 UTF-8 Python 行范围生成和预览替换；
- 模型协议只接受一个有界 `<replacement>`，不接受路径、命令、多个动作或包装扩张；
- 每次应用和回滚都要求独立确认；应用前校验相对路径、项目归属、索引快照、
  SHA-256、语法、体量和 symlink/普通文件边界；
- 写入前在项目 `.researchmind-recovery/` 下创建不覆盖恢复副本，目标使用原子
  替换；外部编辑会阻止应用或回滚，恢复副本不会自动删除；
- 不执行 Shell、测试、安装或生成依赖；验证见
  [T5_B1_CONTROLLED_CODE_WRITE_VALIDATION.md](./T5_B1_CONTROLLED_CODE_WRITE_VALIDATION.md)。

T6-A 已完成最终范围、UI/持久化与进程形态决策：保留 Streamlit、单进程和
会话内存，代码工作区可脱离 PDF 独立使用，并提供初学与静态复现两个目标。
验证见 [T6_A_CODE_WORKSPACE_VALIDATION.md](./T6_A_CODE_WORKSPACE_VALIDATION.md)。
T6-B 已完成，证据见
[T6_B_INSTALL_RECOVERY_VALIDATION.md](./T6_B_INSTALL_RECOVERY_VALIDATION.md)。
T6-C 自动证据及用户人工确认记录见
[T6_C_PRIVACY_SECURITY_PERFORMANCE_VALIDATION.md](./T6_C_PRIVACY_SECURITY_PERFORMANCE_VALIDATION.md)。
T5-B1 的已确认权限合同见
[T5_B_PERMISSION_DECISION.md](./T5_B_PERMISSION_DECISION.md)；任何执行沙箱或更广泛
写权限仍属于独立的 T5-BX 决策，不能由 T5-B1 推导。

最终发布版本号在这些阶段稳定后再决定。
