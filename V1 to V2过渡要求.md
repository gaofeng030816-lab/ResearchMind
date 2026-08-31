# ResearchMind V1 → V2 过渡要求与治理总规划

版本：2026-08-31 · 当前产品基线：2.0.0rc1 本地内部候选 · 状态：T0–T6-D Completed；T5-BX 未批准 · 不对外发布

## 1. 文档目的与权威边界

本文件管理 ResearchMind 从已验证的 V1.3.2 内部基线走向 V2 的阶段顺序、进入条件、退出条件和开发纪律。它不是当前实现说明，也不会仅凭“写入路线图”就授权实现未来功能。

文档职责如下：

- `docs/ARCHITECTURE.md`：当前已经实现的产品边界、模块所有权、数据流和技术选择，是当前代码的事实来源；
- `docs/PRODUCT_SPEC.md`：当前用户能力和验收口径；
- `docs/DEVELOPMENT_PLAN.md`：V1 里程碑与已完成内部版本记录；
- `docs/POST_V1_DEVELOPMENT_PLAN.md`：V1.x 优化过程和已完成迭代；
- 本文件：V1.3.2 之后到 V2 的过渡治理与阶段门禁；
- `AGENTS.md`：所有开发任务都必须遵守的顶层规则；
- `.agents/skills/`：特定领域的决策、实现、验证和教学工作流。

发生冲突时：当前代码和当前范围遵循 `docs/ARCHITECTURE.md`；未来阶段的排期与门禁遵循本文件；产品方向变化必须先得到用户确认，再同步修改相关正式文档。计划中的能力不能被描述成已经实现。

2026-08-28 的治理升级已完成：`AGENTS.md` 与六个项目 Skills 已同步到
V1.3.2→V2 阶段体系。2026-08-29 用户进一步明确要求按本文件顺序推进到 V2，
因此允许从 T0 开始逐阶段执行；该授权不取消每个阶段的退出门禁，也不代替
T3/T5 所需的具体架构、数据源和工具权限确认。2026-08-30 用户进一步确认
T5-B1 推荐合同并人工通过 T6-C；两项完成证据已同步到架构、验证记录与项目 Skills。

## 2. 当前事实基线：2.0.0rc1 本地内部候选

ResearchMind 已经完成可运行、可自动回归的科研阅读闭环，不再处于“从零搭建 V1”或“准备开始 V1.1”的阶段。

当前已经实现：

1. 打开、校验和读取本地数字版 PDF；
2. 页面渲染、翻页、跳页、缩放和文本搜索；
3. 常见双栏阅读顺序、复制友好的文本块和嵌入位图区域预览；
4. 用户输入或复制文本后建立 `ReadingSelection`，并尽可能定位页码和文本块；
5. 独立翻译路径；
6. 基于 `ResearchContext` 的概念、数学、算法、上下文解释和多轮追问；
7. 章节标题、邻近图表说明、邻近公式文字层候选等保守结构线索；
8. 发送前上下文证据与请求体量预览；
9. 用户确认选择驱动的受限 LaTeX 转换、本地数学预览和严格输出校验；
10. `KnowledgeNote`、结构化 Markdown 和不覆盖写入 Obsidian Vault；
11. 单个本地文件夹、Python-first、只读 AST/文本选择和有界 `CodeContext`；
12. 用户确认的论文/数学/算法—代码证据链接及 KnowledgeNote/Obsidian 导出；
13. 论文、代码、只读助手三个顶层工作区，其中代码工作区不依赖 PDF，并提供
    面向零基础学习和科研复现的两种静态阅读目标与项目概览；
14. 一个已选 Python 行范围的受控替换路径：严格替换协议、相对路径 diff、
    逐动作确认、恢复副本、源快照哈希冲突保护、原子写入与外部编辑安全回滚；
15. 无网络配置诊断、Markdown-only 备份/恢复，以及 T6-C 隐私、安全、性能、
    错误恢复自动证据和用户确认的桌面/窄窗口人工门禁。
16. 独立 Code → Obsidian 笔记：校验当前 `CodeSelection` 和选择绑定解释，使用
    项目名、相对路径、行号、符号和代码专用 Markdown，先预览再显式非覆盖保存；
    不依赖 PDF、不记录绝对 root、不修改或执行代码。

历史 V1.3.2 首次全量结果为 `170 passed in 5.60s`；完成 T5-B1 后阶段基线为
`261 passed, 1 skipped`，`compileall` 退出码为 0，`pip check` 返回无损坏依赖。
跳过项是当前 Windows 主机不允许测试创建 symlink；生产代码仍有显式 symlink
拒绝逻辑，不能把该环境跳过描述成动态验证通过。历史
结果用于阶段对照，不代表未来改动自动通过。
T6-D 冻结前加入代码笔记与问题绑定后的源码回归为 `269 passed, 1 skipped`；最终 wheel、
安装、诊断、恢复和安全复验记录见 `docs/T6_D_RELEASE_CANDIDATE_VALIDATION.md`。

当前已知限制：

- 页面图像不能原生提供稳定的精细文字层选择，主要仍依赖文本面板；
- 选择到 bbox 原文位置的交互尚不完整；
- 复杂混排、扫描件、语义表格、矢量图表和图片公式尚不能可靠理解；
- 数字文字层公式可能被拆散，LaTeX 是模型对用户选择的保守重建，不是原始二维公式真值；
- T6-C 桌面/窄窗口清单由用户人工确认通过，但没有自动浏览器截图或可重放的
  浏览器控制证据；后续 UI 改动仍需重新做相应视觉回归；
- CodeContext 仅支持当前会话中的 UTF-8 Python，不做跨文件语义分析；
- 证据链接不跨会话、不自动发现，也不形成联合论文/代码 prompt；
- T5-B1 只替换一个已选择的 Python 行范围；没有 Shell、测试执行、依赖安装、
  任意路径写入、跨会话持久化、跨论文检索或可执行 Agent。

## 3. 当前开发阶段

项目正式处于：

```text
V1.3.2 verified internal baseline
→ V1 Optimization / V2 Preparation
→ stage-gated V2 work
→ final release candidate
```

过渡阶段使用 `T0`—`T6` 作为治理门禁，不把它们直接当作产品版本号。只有用户明确批准某一阶段进入实现，才能把该阶段标记为 `Active`。同一时间最多一个主要过渡阶段为 `Active`。

阶段状态：

- `Proposed`：只有问题、假设或候选方案，不能开始正式实现；
- `Approved`：目标、范围和验收已确认，可以排期；
- `Active`：当前正在执行；
- `Completed`：退出条件有真实证据支撑；
- `Blocked`：存在明确阻塞，不能伪报完成。

当前状态：T0–T4 已于 2026-08-29 完成。T2 用五份真实样本固化了双栏、公式、
表格、图和扫描件基准，并决定保留 PyMuPDF、暂缓 OpenDataLoader-PDF 生产接入。
T3 推荐方案已由用户明确确认并完成：一个本地文件夹、Python-first、
2,000 文件/20 MB/单文件 1 MB、Streamlit、会话内存、标准库 AST、最小上下文
外发且禁止执行和写代码。T4 已完成用户确认的 PDF/数学/算法选择到代码选择
证据链接，保留双方 locator、关系、置信度与 generation method，并随
KnowledgeNote 导出；无联合 prompt、自动关联或数据库。完整基线为
`198 passed`。用户随后明确批准 T5-A，现已实现三个当前会话、无参数、只读
证据工具，逐次用户继续、3 工具/4 LLM 硬上限、严格动作协议、会话内元数据
审计与可预测停止；最终全量为 `220 passed`。用户已批准并完成 T6-A：
继续使用 Streamlit、单进程和会话内存，建立彼此独立的论文、代码与助手入口，
代码页提供初学和静态复现目标、入口/import/依赖候选与问题文件概览，不读取
PDF，也不安装依赖、执行测试或修改代码；T6-B 又加入无网络/非敏感配置诊断、
Markdown-only manifest/SHA-256 备份与新目录恢复，并完成空 venv 安装和真实
Git 基线 wheel→当前 wheel→基线 wheel 回滚演练。T6-C 自动隐私/漏洞/性能/
错误恢复门禁已通过；用户随后明确人工确认桌面/窄窗口清单通过，因此 T6-C
Completed。用户同时确认 T5-B1 推荐合同：当前只实现一个已选择 Python 行范围
的严格替换，要求 diff 预览、逐动作确认、恢复副本、SHA-256 冲突保护、原子
写入、安全回滚和元数据审计。全量为 `261 passed, 1 skipped`。Shell、测试执行、
依赖安装或更广泛写权限属于尚未批准的 T5-BX，不能由 T5-B1 自动扩张。

## 4. 产品方向与不可变职责

长期方向：

```text
Paper ↔ Mathematics ↔ Code ↔ Notes
```

产品所有权保持不变：

- Zotero 负责文献和元数据管理；
- ResearchMind 负责阅读、选择、翻译、上下文构建、AI 理解、关联和知识捕获；
- Obsidian 负责长期知识组织；ResearchMind 只生成可追溯 Markdown 并安全写入用户 Vault。

V2 的“更智能”必须建立在证据、来源定位、可见上下文和明确权限上。默认不等于内置一个能够任意读写文件、执行代码或自主调用工具的 Agent。

## 5. 当前优化优先级

### Priority 0：封闭 V1.3.2 验证缺口

- 完成真实浏览器人工视觉检查；
- 记录公式字体、长公式、窄窗口、复制和按钮布局结果；
- 建立少量可重复使用的真实论文/公式评测样本；
- 不把环境无法执行的检查写成通过。

### Priority 1：Selection Workflow 与原文定位

降低“文本面板 → 手动复制 → 粘贴选择框 → 提问”的成本：

- 公式/文本候选一键带入当前选择；
- 保留 page、block、bbox 和原文来源；
- 提供可验证的定位提示；
- 是否实现页面高亮或更换 UI，必须由真实交互需求和 Spike 结果触发。

### Priority 2：ResearchContext 质量而非重新搭建

`ResearchContext` 已存在，下一步是评测与改进：

- 判断选择、周边文本、章节、图表说明、公式和历史是否相关；
- 比较 Before / After 的上下文质量和 token 成本；
- 保持来源可追溯；
- 不发送整篇 PDF，不用“API 返回成功”代替质量验证。

### Priority 3：科研 PDF 解析质量

继续评估 reading order、段落、标题、上下标、希腊符号、公式、表格、图、说明和 OCR。Viewer、Parser、Document Understanding 必须分开评价。OpenDataLoader-PDF、Docling、Marker 或 OCR 引擎只是候选技术，正式采用前必须做隔离 Spike。

### Priority 4：数学阅读证据

- 为文字层公式候选和 LaTeX 重建建立样本集；
- 分开记录 exact/structural match、人工可读性和来源定位；
- 图片公式 OCR、二维公式重建和整页 LaTeX 不并入现有轻量能力，先独立评估。

### Priority 5：AI 解释与对话上下文

优化概念、数学、算法、推导和上下文解释；长对话逐步评估 recent messages、relevant messages、summary 与 token budget。始终区分模型连通性和研究回答质量。

### Priority 6：Knowledge Capture 与 Obsidian

逐步把完整聊天导出提升为可选择的 Conversation / Concept / Formula / Algorithm / User Understanding 知识单元，同时改善来源、页码、YAML、标签和链接；不在 ResearchMind 内复制 Obsidian 的长期知识系统。

### Priority 7 以后：Code 与更高阶智能化

只有前述证据基础稳定后，才依次考虑 CodeContext、论文—数学—代码链接、受限工具型助手、跨论文检索和其他内容源。Zotero、VS Code、RAG、向量数据库不因长期愿景自动进入当前实现。

## 6. 过渡阶段与退出门禁

### T0：基线封口与评测准备

目标：把 V1.3.2 从“自动化通过”提升为“限制清楚、人工可复核、可作为后续优化对照”。

退出条件：

- 人工视觉清单有真实结果或明确环境阻塞；
- Selection、公式和 ResearchContext 各有最小真实样本集；
- 当前 170-test 基线无回归；
- 文档和六个 Skills 与 V1.3.2 一致。

### T1：Selection 与 Provenance

目标：让用户用更少操作把内容交给 AI，并能从选择追溯到 page / block / bbox。

非目标：不默认实现 PDF 编辑、标注系统或 UI 重写。

退出条件：

- 常规文本与公式候选可一键形成 `ReadingSelection`；
- 定位成功和失败都有明确语义；
- 选择来源能进入 ResearchContext 和 KnowledgeNote；
- 复制、选择、解释、LaTeX、追问和保存闭环无回归。

### T2：PDF / Mathematics Evidence Upgrade

目标：用真实论文基准决定现有 PyMuPDF 规则是否足够，以及哪些能力需要第三方 Parser 或 OCR。

退出条件：

- 对双栏、公式、表格、图、扫描件分别有可重复基准；
- 候选依赖经过 Spike，记录质量、性能、Windows、隐私和维护成本；
- 明确采用、拒绝或推迟，不因输出 JSON 更丰富而直接接入；
- 若采用第三方工具，其输出已定义到 ResearchMind 内部模型的转换边界。

### T3：CodeContext 基础

目标：为最终版本的代码识别建立只读、可追溯、不可执行的最小内容源。

进入条件：先确认代码来源、语言、项目规模、隐私、UI 和成功标准，并完成架构评审。

退出条件：

- `CodeContext` 与 `ResearchContext` 的关系有正式规格；
- 文件、行号、符号等 provenance 可追溯；
- 初期只做静态只读解析，不执行用户代码或模型代码；
- Parser 输出不成为 Core 的第三方数据模型。

### T4：Paper ↔ Mathematics ↔ Code ↔ Notes 证据链接

目标：以显式证据链接选择、公式、算法、代码符号和笔记。

状态：`Completed`（2026-08-29）。实现和证据见
`docs/T4_EVIDENCE_LINK_VALIDATION.md`。

退出条件：

- 链接模型表达来源、定位、关系、置信度和生成方式；
- UI 能区分用户确认、确定性提取和模型推断；
- 若跨会话链接确需持久化，先评估标准库 SQLite 和迁移/备份策略；
- 无来源的模型猜测不能伪装成论文—代码事实。

完成口径：

- `PaperEvidenceReference` 和 `CodeEvidenceReference` 保存双方强类型来源；
- `EvidenceLink` 表达 relation、0–1 confidence、generation method、rationale
  与时间；
- 当前生产路径只创建 `user_confirmed`，UI/Markdown 同时保留
  deterministic/model-inference 的差异标签，不自动产生后两者；
- 链接保持会话内存，只有 KnowledgeNote Markdown 进入 Vault；没有真实
  跨会话需求证据，因此不引入 SQLite；
- 链接不调用 LLM，不把 ResearchContext 和 CodeContext 合成联合 prompt。

### T5：受限智能助手

目标：在 ResearchContext / CodeContext 和证据链接之上评估有限工具能力。

进入条件：工具清单、读写边界、用户确认点、沙箱、预算、审计、Prompt Injection 威胁模型和停止机制均已批准。

退出条件：

- 默认最小权限，读操作与写/执行操作分离；
- 高影响动作逐次确认，可取消、可审计、可回滚；
- 有提示注入、越权、资源消耗和错误恢复评测；
- 没有“模型要求执行”即自动授权的路径。

完成口径（T5-A）：

- 用户已确认 `docs/T5_AGENT_TOOLS_ENTRY_DECISION.md` 的推荐范围；
- 只实现 `inspect_paper_context`、`inspect_code_context` 和
  `inspect_evidence_links`，均无参数且只读当前会话；
- 每次网络调用都由开始/继续按钮触发，工具结果先在 UI 展示，可随时停止；
- 严格文本动作解析、固定 Python 调度、提示注入转义、字符/调用预算和
  非敏感审计已验证；
- 最终回答不写 Conversation、KnowledgeNote、Vault 或代码；
- 退出证据见 `docs/T5_READ_ONLY_ASSISTANT_VALIDATION.md`。

完成口径（T5-B1）：

- 用户已确认 `docs/T5_B_PERMISSION_DECISION.md` 的推荐合同；
- 只对当前已索引项目中一个已选择的 UTF-8 Python 行范围生成候选替换；
- 严格响应协议只接受一个 `<replacement>`，拒绝路径、命令、多个动作、空输出、
  NUL、超限内容和包装扩张；
- 应用前展示仅含相对路径的 unified diff，并校验项目/选择/索引快照、源文件
  SHA-256、语法和体量；每次应用与回滚分别确认；
- `.researchmind-recovery/` 保存不覆盖恢复副本，目标原子替换，外部编辑冲突会
  阻止应用或回滚，恢复副本保留；
- 不执行 Shell、测试、安装依赖或写入其他文件；退出证据见
  `docs/T5_B1_CONTROLLED_CODE_WRITE_VALIDATION.md`。

### T6：架构定型与发布加固

目标：基于前述真实需求决定最终 UI、持久化和进程形态，并完成发布质量门禁。

注意：如果 T1/T3 提前证明 Streamlit 无法满足精细选择或代码工作区，UI 架构评审可以提前触发，但不得直接跳到重写。

当前进度（T6-A/T6-B/T6-C/T6-D Completed）：

- `docs/T6_ARCHITECTURE_FINALIZATION_DECISION.md` 已批准保留 Streamlit、
  单 Python 进程和会话内存，不引入 UI 重写、数据库或额外服务；
- 顶层入口拆分为论文阅读与笔记、代码学习与复现、只读研究助手；
- 代码工作区不依赖当前 PDF，提供初学和科研复现两种阅读目标；项目入口、
  import、第三方依赖和问题文件仅为静态候选，不代表已运行或可复现；
- T6-A 验证见 `docs/T6_A_CODE_WORKSPACE_VALIDATION.md`；
- T6-B 已完成显式本地配置诊断、只读 Vault 目标检查、Markdown-only ZIP、
  manifest/SHA-256 校验、恢复到新目录、干净安装和 wheel 升级/回滚演练；
- T6-B 验证见 `docs/T6_B_INSTALL_RECOVERY_VALIDATION.md`；
- T6-C 自动隐私/已知漏洞/性能/错误恢复门禁已通过，用户于 2026-08-30 明确
  人工确认桌面与窄窗口清单通过；验证见
  `docs/T6_C_PRIVACY_SECURITY_PERFORMANCE_VALIDATION.md`；
- 该人工确认没有伪装成自动浏览器截图证据；后续 UI 变化必须重新验证；
- 用户已明确完成 T6-D 真实用户闭环与本地内部发布候选封口；
- T6-D 已把 2,000 文件索引从首次超门槛的 21.19 秒优化到重复实测
  3.43/3.66 秒，保留原 2,000 文件/20 MB/1 MB 安全上限；
- 临时 `0.1.0` wheel 曾完成构建、隔离安装、包内 `researchmind` 启动命令、
  本地健康检查、诊断、备份恢复与复扫；随后内部版本冻结为 `2.0.0rc1`；
- 用户于 2026-08-31 明确确认 T6-D 论文、独立代码和 T5-B1 三条人工旅程
  通过；该证据不伪装成自动浏览器结果；
- 用户要求在冻结前加入的 Code → Obsidian 可选笔记已通过单元/Vault/Streamlit
  和完整回归，并随 `2.0.0rc1` 工件与本地 Git 基线共同进入内部冻结；
- Completed 只表示本地内部候选可追溯，不授权上传、远端 push、公开 tag 或发布；
- T5-B1 已按 `docs/T5_B_PERMISSION_DECISION.md` 的确认合同完成；T5-BX 未批准。

退出条件至少包括：

- V2 产品规格与架构已批准；
- 安装、升级、数据备份、隐私与错误恢复有验证；
- 自动化、人工场景、性能、安全和真实用户闭环均有证据；
- 最终发布版本号在范围稳定后确定。

## 7. Preserve Working V1

任何优化默认采用增量修改。除非存在明确且经验证的技术原因，不得：

- 为了“更漂亮”大规模重写已经工作的代码；
- 无理由替换稳定模块、主框架或目录结构；
- 同时修改多个无关模块；
- 引入微服务、复杂基础设施或推测性扩展点；
- 为未来阶段预先实现大量代码。

较大修改开始前必须写明：Problem、Current Behavior、Expected Behavior、Affected Modules、Risk、Test Plan、Regression Plan、Rollback 和 Definition of Done。

## 8. Optimization-first Development

默认流程：

```text
Classify → Observe → Define → Measure → Compare → Improve → Verify
```

每个任务先分类为 bug fix、optimization、spike、new feature 或 architecture decision。对优化必须回答：

1. 用户遇到的具体问题是什么；
2. 当前实现为何不足；
3. 是否有更简单方案；
4. Before / After 如何比较；
5. 是否需要 Spike；
6. 会影响哪些模块和现有闭环；
7. 如何验证改善而非只验证“没有报错”。

## 9. Spike Before Major Dependency

OpenDataLoader-PDF、Docling、Marker、OCR、新 PDF 引擎、Zotero、VS Code、数据库、embedding、RAG 或工具型 Agent 正式进入产品前，原则上先在 `experiments/` 建立与业务代码隔离的 Spike。

Spike 至少记录：

- 要回答的技术问题与样本；
- Windows / 本地部署可行性；
- 输出质量与失败类型；
- 性能和内存；
- 隐私与网络行为；
- 依赖、许可证和维护风险；
- 内部模型转换与集成复杂度；
- 对现有 V1 的影响；
- 采用、拒绝或继续评估的结论。

Spike 不是正式功能，不得让实验对象的数据结构泄漏进 Core。

## 10. External Dependency Boundary

外部工具提供能力，ResearchMind 使用自己的模型和错误语义：

- PDF Parser 输出转换为 `Document` / `Page` / `TextBlock` / `FigureRegion` 或未来经批准的内部模型；
- LLM SDK 响应转换为项目 `Message` 或受约束结果；
- Translation Provider 响应转换为项目翻译结果/错误；
- 未来代码 Parser 输出也必须经过适配层。

禁止让 OpenDataLoader JSON、PyMuPDF 对象、SDK Response 或其他 vendor 类型无控制地传播到 Core、UI 和持久化层。

## 11. Regression-first 与评测要求

每次正式修改都必须保护以下核心闭环：

```text
open PDF → read/search/select → translate/LaTeX/explain → follow up
→ KnowledgeNote → Markdown → Obsidian Vault
```

验证遵循改动风险分层：

- Bug：先有可复现失败和回归测试；
- PDF：根据范围覆盖单栏、双栏、中英文、Unicode、上下标、希腊符号、公式、标题、表格、图、长文档、空白/损坏/扫描件；
- ResearchContext：验证 selection、surrounding、page、source、结构线索、history、token 和 provenance；
- AI：把 API Connectivity Test 与 Research Context / Answer Quality Eval 分开；
- 第三方 Spike：使用同一语料与指标比较 Before / After；
- 文档/Skill：运行 Skill validator，检查链接、术语、阶段状态和职责冲突；文档-only 修改不要求重跑完整 pytest。

自动化测试不得调用真实付费 API、用户真实 Vault 或包含隐私的论文。人工/真实 API 检查必须由用户明确授权并单独记录。

## 12. Learning-oriented Development

ResearchMind 同时是学习型项目。重要阶段完成后，需要用当前真实代码说明：

1. 解决了什么问题；
2. 修改了哪些模块；
3. 数据如何流动；
4. 为什么这样设计；
5. 使用了哪些 Python 与软件工程概念；
6. 哪些限制仍然存在；
7. 推荐阅读的 3—5 个文件；
8. 下一阶段应理解什么。

不得用抽象术语代替代码事实，也不得把 Proposed/Approved 能力讲成已实现。

## 13. 六个 Skills 的职责边界

本阶段保留四个现有 Skill，并且只新增两个专业 Skill：

| Skill | 负责 | 不负责 |
|---|---|---|
| `project-planner` | 阶段、分类、范围、优先级、Spike 决策、DoD | Python 细节或专业 PDF 算法 |
| `python-engineering` | Python 组织、接口、错误、边界、增量实现 | 产品阶段批准或质量结论 |
| `testing-review` | 测试、回归、验收、证据报告 | 决定产品范围 |
| `learning-mode` | 结合当前代码教学与阶段总结 | 代替实现或验收 |
| `pdf-research` | Viewer/Parser/PDF Understanding、解析基准和 PDF Spike | 通用项目排期或 Prompt 设计 |
| `research-context` | Selection、Context Builder、Prompt 输入边界、上下文质量与 provenance | PDF 引擎选型或 LLM Provider 网络实现 |

通用规则只保留在 `AGENTS.md`；专业方法放在对应 Skill。暂不新增 obsidian、zotero、llm、prompt、ui、database、rag、api 或 vscode Skill。只有某领域形成独立、稳定、反复出现的工作流后才重新评估。

## 14. Future Work Boundary

以下能力必须有单独批准的阶段、规格和验证方案，不能从长期愿景直接推导为当前任务：

- 图片公式 OCR、整页公式重建、语义表格和图表理解；
- CodeContext 和静态 Python 代码识别已实现；代码执行、依赖安装和 VS Code 集成
  仍需独立批准；
- Paper ↔ Code 自动链接；
- SQLite、跨会话状态、跨论文检索；
- advanced RAG、embedding、向量数据库或知识图谱；
- T5-A/T5-B1 以外的 Agent 工具、任意或自动文件写入、自动执行代码或后台自主循环；
- UI 框架替换、REST 后端或多进程形态；
- Zotero API、云同步、多用户或复杂认证。

## 15. 当前执行顺序

T0–T5-A、T5-B1 与 T6-A/T6-B/T6-C 已完成，证据见 `docs/T0_BASELINE_CLOSURE.md`、
`docs/T1_SELECTION_PROVENANCE_VALIDATION.md` 与
`docs/T2_PDF_MATHEMATICS_EVIDENCE.md`；T3 决策与验证分别见
`docs/T3_CODECONTEXT_ENTRY_DECISION.md` 和
`docs/T3_CODECONTEXT_VALIDATION.md`；T4 验证见
`docs/T4_EVIDENCE_LINK_VALIDATION.md`；T5 决策与验证见
`docs/T5_AGENT_TOOLS_ENTRY_DECISION.md` 和
`docs/T5_READ_ONLY_ASSISTANT_VALIDATION.md`；T6 决策与 T6-A 验证见
`docs/T6_ARCHITECTURE_FINALIZATION_DECISION.md`、
`docs/T6_A_CODE_WORKSPACE_VALIDATION.md`、
`docs/T6_B_INSTALL_RECOVERY_VALIDATION.md` 与
`docs/T6_C_PRIVACY_SECURITY_PERFORMANCE_VALIDATION.md`。T5-B1 决策与验证见
`docs/T5_B_PERMISSION_DECISION.md` 和
`docs/T5_B1_CONTROLLED_CODE_WRITE_VALIDATION.md`。下一步：

1. 用可丢弃的代表性 Python 项目做 T5-B1 人工易用性/恢复演练，验证新手能看懂
   diff、确认边界和恢复凭据；这不是扩大权限；
2. 继续评估 ResearchContext、CodeContext、T5-A 回答质量和 T4 链接实用性；
3. 只有真实跨会话需求出现时才评估 SQLite；
4. 用户明确进入 T6-D 后，关闭剩余真实用户阻塞项、冻结正式版本号并形成可追溯
   发布候选；若要 Shell/测试/安装能力，先单独批准并验证 T5-BX 执行沙箱。

每完成一个阶段，必须同步状态、验证记录、遗留限制和下一阶段建议。用户已经
批准向 V2 持续推进，但仍必须逐门禁验证；当下一阶段涉及未确定的代码来源、
UI 框架、持久化模型、写入/执行工具权限或其他高影响架构选择时，先给出证据和
候选方案并取得该具体选择的确认。
