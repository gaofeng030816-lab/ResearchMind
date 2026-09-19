# ResearchMind V2 → V3 过渡要求与实施门禁

版本：2026-09-16 · 当前实现基线：2.0.0rc1 V2 Accepted + V3-G1–G6 增量 · 当前阶段：V3-G0–G6 Completed；G7 Pending · 不对外发布

## 1. 文档目的与权威边界

本文件把用户已经明确提出的 V3 目标拆成可验证、可回退的阶段，并记录每个重大
技术选择需要的证据与确认。它描述目标和门禁，不把计划写成当前实现。

文档职责：

- docs/ARCHITECTURE.md：当前已经实现的 V2/V3 事实，始终是代码事实来源；
- docs/PRODUCT_SPEC.md：当前已验收用户能力；
- 本文件：V2→V3 的需求、架构决策、阶段顺序和进入/退出证据；
- V1 to V2过渡要求.md：冻结的 V1→V2 历史治理记录；
- AGENTS.md：所有任务必须遵守的顶层开发、安全和测试规则；
- .agents/skills：规划、实现、PDF、上下文、资料库、测试和学习工作流。

整体 V3 方向已经由用户明确批准。数据库/文件所有权、Zotero 只读模式、PDF
组件、公式服务和多语言解析已分别在 G1–G6 关闭门禁；最终加固与内部验收仍须
通过 G7。

## 2. V3 产品目标

V3 要把 ResearchMind 从“每次会话打开一个文件”推进为更成熟的本地研究工作台：

1. 建立可跨重启使用的论文/代码工作资料库；
2. 使用鼠标点击/拖放选择 PDF 或代码目录导入，不再要求手工输入路径；
3. 可选连接 Zotero，但 ResearchMind 不替代 Zotero 的引用与文献管理；
4. 在 PDF 原文文字层上划词，保留页码与几何位置并直接翻译/解释；
5. 识别积分、求和、上下标、分式、根式、矩阵等常用公式，生成可编辑、可校验、
   可追溯的 LaTeX 候选；
6. 在既有 CodeContext 架构内支持 Python、C、Java、Julia 和 R 静态阅读；
7. 只把用户主动选择的原文、翻译、公式和问答加入笔记；
8. 最终 Markdown 可编辑、可预览，再由用户明确选择是否保存到 Obsidian；
9. 只导入论文时 PDF 占主页面；同时打开论文和代码时分栏；AI 通过快捷键唤醒；
10. 保持本地优先、单进程、可理解、可回归和无代码执行的安全底线。

目标工作流：

    点击导入/资料库
    → 论文全宽或论文+代码分栏
    → 划词/选代码/选公式
    → 翻译或有界 AI 理解
    → 用户把有价值证据加入笔记篮
    → 编辑 Markdown → 预览
    → 可选保存到 Obsidian

## 3. 与 V2 的差距

| V3 需要 | V2 当前事实 | 为什么需要单独门禁 |
|---|---|---|
| 跨重启论文/代码库 | V3-G1 已实现 SQLite 工作资料库 | G1 只持久化记录/资产；草稿和对话仍属于后续门禁 |
| 点击导入 | V3-G1 已实现 PDF/代码目录原生上传 | 浏览器上传只有名称和字节，因此使用验证后的托管副本 |
| Zotero 连接 | V3-G2 已实现可选 Local API 元数据/来源链接 | 批准目录内 Windows 只读复制已实现；真实 Zotero desktop 人工验收已由用户确认通过 |
| 页面划词 | 页面图像 + 提取文本块 | 需要浏览器文字层和双向事件 |
| 公式识别 | 扁平文字层 + 选择驱动 LaTeX | 检测与识别质量、外发和错误编辑 |
| 五种代码语言 | Python 标准库 AST | 新解析器、语法映射、Windows 依赖 |
| 选择式笔记 | 当前 KnowledgeNote 预览/保存 | 需要持久草稿和明确包含/排除 |
| 自适应工作台/快捷键 | 三个顶层 Streamlit 工作区 | 需要新的页面状态和 CCv2 事件边界 |

## 4. 总体架构建议

### 4.1 本地资料库与 SQLite

比较：

| 方案 | 优点 | 代价/结论 |
|---|---|---|
| 继续会话内存 | 无迁移 | 无法满足跨重启资料库和草稿，拒绝 |
| 标准库 sqlite3 | 单文件、本地、无新增运行时依赖、可事务 | 推荐；需 schema、迁移、备份和文件补偿 |
| ORM 或数据库服务器 | 抽象/并发能力更多 | 对单用户本地应用过重，当前拒绝 |

推荐的第一版：

- 新增 database 基础设施模块，独占 sqlite3、schema、迁移和事务；
- 数据库存元数据、稳定 ID、哈希、版本和相对托管路径，不存 PDF/源码 blob；
- 托管根目录由 V3 配置明确指定，不复用 Vault 或代码根目录；
- PDF 与目录上传先验证并暂存，再由数据库事务登记，最后原子完成；
- “解除来源链接”“删除资料库记录”“删除 ResearchMind 托管副本”是不同动作；
- 永不删除外部 PDF、外部代码目录、Zotero 附件或 Vault 笔记。

### 4.2 点击导入与文件所有权

当前安装的 Streamlit 支持 st.file_uploader 的单文件、多文件和 directory 模式。
浏览器不会向应用提供可信的原始绝对路径，因此 V3 的点击导入采用“上传并复制到
ResearchMind 托管目录”，而不是假装继续引用原文件。

PDF 导入校验扩展名、PDF magic bytes、大小、哈希和可解析性。代码目录导入校验
相对路径、遍历、隐藏/密钥/vendor/build 排除、文件数/总量/单文件大小和编码。

### 4.3 Zotero

首选官方 Zotero Local API 的只读集成。官方文档说明它在
http://localhost:23119/api/ 提供与 Web API v3 相近的本地接口，需用户在 Zotero
设置中启用；读取无需认证、离线且无网络限速。ResearchMind 必须保留 server ID、
library/item key 和 object version，并按 server ID 隔离缓存。

官方资料：

- https://www.zotero.org/support/dev/web_api/v3/local_api
- https://www.zotero.org/support/dev/web_api/v3/basics

第一版只读导入/链接元数据与附件引用，不写 Zotero。Web API、OAuth/API Key、
双向同步和写请求分别属于后续门禁。禁止直接读取 Zotero SQLite 数据库。

### 4.4 PDF 页面划词与自适应查看器

保留 PyMuPDF 作为当前后端验证、渲染、搜索和提取基础。V3 使用隔离 CCv2/pdf.js
Spike 验证浏览器文字层选择；通过后才决定生产采用。新的 Streamlit 组件只能使用
Custom Components v2。

组件必须返回 ResearchMind 可验证的文档修订、页码、文字、span/字符范围和 bbox。
同时验证双栏、Unicode、连字符、上下标、普通滚动归属、滚轮翻页防抖/边界/
触控板、快捷键焦点、rerun 状态恢复和事件清理。

### 4.5 数学公式

公式能力分成：

    公式区域候选 → 用户/规则确认 → 单个 crop
    → 专用识别器 → 严格 LaTeX 校验
    → 用户编辑/接受 → 上下文或笔记

现有 experiments/pdf_formula_latex_spike 是候选证据，不是生产实现。V3 先固定
公式语料和指标，再比较现有远程视觉模型、可接受的本地模型或继续使用受限 LLM。
评价积分/求和上下限、分式、根式、希腊字母、上下标、矩阵、多行对齐和编号。

目标是结构上可用且可编辑的 LaTeX，不承诺像素级复刻原论文。默认只外发一个明确
crop，不外发整篇 PDF；外发前必须可见。

### 4.6 多语言代码

CodeProject、CodeSelection、CodeContext、相对路径和非执行架构不变。推荐先以
Tree-sitter Python 绑定和各语言 grammar 做隔离 Spike。官方 Python 绑定提供主要
平台预编译 wheel，语言 grammar 也可分别提供 Python wheel：

- https://github.com/tree-sitter/py-tree-sitter
- https://github.com/tree-sitter/tree-sitter-python
- https://github.com/tree-sitter/tree-sitter-c
- https://github.com/tree-sitter/tree-sitter-java
- https://github.com/tree-sitter/tree-sitter-julia
- https://github.com/r-lib/tree-sitter-r

生产采用前验证 Python 与现有 AST 的符号/行号一致性、C/Java/Julia/R 的主要符号
覆盖、语法错误容忍、性能、Windows 安装、许可证和维护成本。新增语言不扩大
T5-B1：源码写入仍仅限当前 Python 单范围，也不获得执行、Shell、测试或安装权限。

### 4.7 笔记草稿与 Obsidian

引入 NoteDraft 和 EvidenceSnapshot 概念，但 SQL schema 在 G1 决策后固定。用户
主动把原文、翻译、已验证公式、问题和选定回答加入证据篮；系统不得自动保存每段
对话。

编辑、预览、本地持久化和 Vault 保存是四个独立状态。只有
integration/obsidian 可以写 Vault，并继续遵循 Markdown-only、净化路径、禁止遍历、
重名编号、不覆盖和错误可见。

### 4.8 自适应 UI

- 只有论文：PDF/阅读区域全宽，辅助控制不永久挤占页面；
- 论文 + 代码：桌面端比例分栏，窄屏按可用性堆叠/切换；
- AI：由明确快捷键打开/关闭，但在输入框、编辑器和组件内部输入时不误触；
- 笔记：从证据篮进入可编辑 Markdown，再切换预览，最后显式保存；
- 优先使用原生 Streamlit；文字层选择与全局键盘事件等原生不具备的交互才用 CCv2。

## 5. V3 概念模型与物理边界

下列是 V3 架构词汇。G1 已落地 LibraryRecord/AssetReference，G2 已落地
ZoteroSourceLink；其余概念仍须在对应门禁固定 schema：

| 概念 | 作用 |
|---|---|
| LibraryRecord | 一篇论文或一个代码工作区的稳定 ResearchMind 身份 |
| AssetReference | 托管文件/目录、哈希、大小、类型、修订和相对路径 |
| ZoteroSourceLink | server/library/item/version 与可选 PDF attachment 来源快照 |
| NoteDraft | 用户可编辑、可跨重启恢复的 Markdown 草稿 |
| EvidenceSnapshot | 用户明确加入草稿的来源片段、locator、origin 和修订 |
| FormulaCandidate | page/bbox、输入类型、detector/recognizer 来源、候选 LaTeX 和接受状态 |

建议物理位置：

- models：上述项目 dataclass；
- core：纯验证、去重、状态、选择和草稿规则；
- database：SQLite/schema/migrations/repository；
- integration/zotero：可选 Zotero HTTP；
- pdf：PyMuPDF、viewer 事件转换和公式边界；
- code：语言解析器到现有 Code 模型；
- app/use_cases.py：跨边界编排；
- app/views 与 app/state.py：展示/事件和唯一 session state。

## 6. 阶段计划

| 阶段 | 状态 | 目标 | 主要退出证据 |
|---|---|---|---|
| V3-G0 规则与架构入口 | Completed | 同步 AGENTS/Skills/规划文档，固定门禁 | 七个 Skill 有效；文档/差异检查通过；无生产代码/依赖改动 |
| V3-G1 本地资料库与点击导入 | Completed | SQLite、迁移、托管文件、论文/代码导入和资料库打开 | 重启、迁移、补偿、去重、修订、删除、备份/恢复和 AppTest 已覆盖 |
| V3-G2 Zotero 只读连接 | Completed（用户确认） | API 浏览/链接及批准目录内 Windows 单 PDF 复制已实现 | 374 passed / 1 skip；真实 Zotero 人工验收已由用户确认通过 |
| V3-G3 PDF 文字层与自适应工作台 | Completed（用户确认） | CCv2/pdf.js 划词、全宽/分栏、AI 快捷键、滚轮交互 | 用户确认物理触控板并批准采用；正式 ReadingSelection 对账、回退、Edge 8/8、wheel 与 486 passed / 1 skip 已完成 |
| V3-G4 划词翻译与显式笔记草稿 | Completed（用户确认） | schema v3 草稿/证据、准确翻译预览、显式证据篮、可编辑正文、同版预览与明确 Vault 输出 | 42 focused；425 passed / 1 skip；G3 联合 524 passed / 1 skip；Edge 8/8；用户确认通过 |
| V3-G5 公式识别与 LaTeX | Completed | 区域检测、单 crop 识别、编辑接受和可选笔记证据 | 20 合成 + 18 真实标注、隐私/错误/性能、Edge 假服务旅程、全量回归 |
| V3-G6 多语言 CodeContext | Completed | Python/C/Java/Julia/R 静态解析 | 24 focused；22 AppTests；498 passed / 1 skip；联合 597 passed / 1 skip；wheel/性能 |
| V3-G7 V3 加固与内部验收 | Pending | 数据恢复、安全、性能、完整旅程和人工验收 | 全量回归、迁移/恢复、浏览器、隐私、用户确认 |

### V3-G0：规则与架构入口

范围：

- 更新 AGENTS 和 project-planner、python-engineering、research-context、
  pdf-research、testing-review、learning-mode；
- 新增 research-library；
- 建立本文件并同步架构、产品规格、历史计划和 README 的阶段导航；
- 核对官方 Streamlit、Zotero 和 Tree-sitter 可行性。

不包含生产代码和依赖。

完成证据（2026-09-01）：

- project-planner、python-engineering、research-context、pdf-research、
  testing-review、learning-mode 和新增 research-library 均通过官方
  quick_validate.py；
- docs/ARCHITECTURE.md、docs/PRODUCT_SPEC.md、历史计划、README 和两份过渡
  门禁的状态/导航已同步；
- git diff --check 无空白错误，pyproject.toml 与 src/researchmind 无本阶段差异；
- 官方能力核对确认 Streamlit directory upload、Zotero Local API 和 Tree-sitter
  多语言 grammar 可作为后续门禁候选，但未进入生产依赖。

### V3-G1：本地资料库与点击导入

用户于 2026-09-01 确认推荐架构；本阶段已按三个可回退子阶段完成：

1. G1-A：模型、sqlite3 schema、迁移、repository、配置与纯规则；
2. G1-B：PDF 上传、托管文件、去重和从资料库重新打开；
3. G1-C：代码 directory 上传、资料库列表/筛选/移除和重启恢复。

采用决定：

- 标准库 sqlite3 和 schema version 1，无 ORM/数据库服务器；
- RESEARCHMIND_DATA_DIR/researchmind.sqlite3 保存记录与资产元数据，
  assets/ 保存托管 PDF/Python 文件，.staging/ 只用于导入/恢复暂存；
- 上传字节先做路径、类型、大小、编码/可解析性和 SHA-256 校验；事务内登记，
  原子完成托管文件后提交，任一步失败都补偿；
- 精确哈希去重；同一记录的新内容创建不可变修订，不静默覆盖；
- 资料库“移除”是软删除；删除托管副本必须另行确认；外部文件、Vault 和
  Zotero 附件永不作为该动作的副作用删除；
- 托管代码修订只读，不能进入 T5-B1；V2 外部本地 Python 项目的既有 T5-B1
  边界不变；
- 提供带 manifest/SHA-256 的数据库快照 + assets 备份，并只恢复到不存在且
  不与当前数据目录/Vault 重叠的新目录。

退出条件：

- 新旧数据库创建/迁移/回滚与损坏版本有确定结果；
- 上传失败不留下可见半记录，数据库失败不覆盖已有托管文件；
- 重启后能列出并重新打开论文/代码；
- 重复、修订、删除和外部文件所有权清楚；
- V2 打开/阅读/代码/Obsidian 路径不回归。

完成证据见
[docs/V3_G1_LOCAL_LIBRARY_VALIDATION.md](docs/V3_G1_LOCAL_LIBRARY_VALIDATION.md)。
Streamlit AppTest 已验证资料库导航和重开；原生 file_uploader 的真实点击/拖放
仍保留为后续人工整体验收项目，不把 AppTest 伪装成浏览器文件选择证据。

### V3-G2：Zotero 只读连接

用户于 2026-09-02 确认推荐方案，当前已实现：

- 固定 `http://127.0.0.1:23119/api/` 的标准库 GET-only adapter，禁用代理与重定向；
- `ZOTERO_LOCAL_API_ENABLED=false` 为默认值，只在显式按钮后探测/读取；
- 个人资料库最近条目/搜索与选中条目的 PDF 附件元数据；
- schema version 2 `zotero_links`，保存 server/library/item/version、元数据快照和
  可选 attachment identity，不保存整库缓存、PDF blob 或凭据；
- 链接已有论文、重启读取和单独确认 unlink；来源关系不证明 PDF 内容相同；
- 切换来源/附件/目标论文后需要重新确认，读取失败清理旧详情；
- 存在 Zotero 来源链接时，必须先解除链接才能删除已软移除记录的托管副本；
- 403 disabled、offline、412/server mismatch、错误 API 版本、malformed response
  等错误可见，且不影响本地资料库；
- G1 schema v1 数据库和备份可迁移到 v2。

本阶段仍不写 Zotero、不做双向同步、不保存 Web API Key，不提供组资料库产品流，
也不直接读取 Zotero SQLite。2026-09-04 修正了上轮“实现/自动门禁全部完成”的
表述：官方 `/file` 返回 `302 file://`，不是 PDF 字节流。现有 HTTP-200 下载用例
只是模拟字节响应原型，不能证明真实附件导入。当时临时停用直接导入并提供
上传后链接回退；随后按下述用户批准边界完成 Windows 复制。最新自动回归和环境 skip 见
[docs/V3_G2_ZOTERO_VALIDATION.md](docs/V3_G2_ZOTERO_VALIDATION.md)。

补充门禁已于 2026-09-04 获得用户确认并实现：只读取用户选定且单独确认的
一个本地 PDF，限定 ZOTERO_ATTACHMENT_ROOT；采用 /file/view/url，不跟随重定向。
Windows 逐级保持祖先和文件句柄，禁止 write/delete sharing，拒绝网络盘/UNC、
路径逃逸、符号链接/junction/重解析点和硬链接。前后重验来源版本及 URL；
G1 校验大小、PDF magic/可解析性，再走暂存/哈希/事务/原子完成。目录、来源、
附件变化或读取失败后必须重新确认。非 Windows/未配置时保留上传后链接。
自动证据为 374 passed / 1 个既有环境 skip；用户已于 2026-09-04 确认 G2 验收通过。

根据 [Zotero 官方 Local API 文档](https://www.zotero.org/support/dev/web_api/v3/local_api)，
必需的 `Zotero-Server-ID` 由 Zotero 10+ 提供；缺失时安全失败，不虚构稳定身份。
用户于 2026-09-04 明确回复“G2通过验收”，据此关闭 G2 人工门禁并标记
Completed。未提供逐项截图、版本或哈希，不补造测量值；G3 已按后续用户要求启动隔离 Spike。

### V3-G3：PDF 文字层与工作台

2026-09-04 已按用户要求启动隔离事件契约实验，详见
[G3 实验记录](docs/V3_G3_PDF_WORKSPACE_SPIKE.md)。已补充合成文字 inline CCv2
实验页及自动测试；又以官方 v2 模板固定 PDF.js 6.3.289，完成本地两页合成
数字 PDF 的真实 Edge 鼠标划词、事件字段、回调后画布稳定、换页失效、双栏文字项
和无外部请求验证。后续隔离工作区又验证了专属滚动区的中部滚动、边缘 80px
累积翻页、650ms 锁定与静默解锁、首页/末页边界、选择保护、输入区快捷键抑制、
仅论文全宽、桌面分栏和 600px 自动堆叠。随后五类 hash 锁定代表性 PDF 完成
12/12 次数字文字选择、原生复制一致性和 PyMuPDF 服务端文字/几何对账；扫描
PDF 正确降级。跨行复制、双实例、209 页长文档按 revision 复用和清洁实验 wheel
安装运行也已记录。

用户于 2026-09-07 明确反馈物理触控板验收通过并确认正式采纳 CCv2/pdf.js。
2026-09-08 完成生产接入：pdf/viewer_component 本地加载 hash 绑定且不超过 10 MiB
的 PDF；客户端选择事件必须由当前页 PyMuPDF 重新核对文字和几何后才建立
ReadingSelection；重复、过期、跨页和伪造事件被拒绝。旧 PyMuPDF 页面图像和
文字块继续作为回退。正式 Edge 152 验收 8/8 项通过，0 页面错误、0 外部请求；
生产 wheel 为 1,041,404 bytes，恰有一个 JS 和一个 CSS，并含组件清单、声明与
Apache-2.0 许可证，不含 node_modules/source map。最终联合回归为 486 passed /
1 个既有 Windows symlink 环境 skip。G3 标记 Completed；G4 后续已单独启动并
于 2026-09-09 完成，本段保留 G3 关闭时的历史边界。

### V3-G4：划词翻译与显式笔记

把 G3 的 ReadingSelection 接入现有独立 TranslationProvider；引入证据篮和持久
NoteDraft。用户可编辑 Markdown，预览和保存分开，未选中的对话不进入笔记。

本阶段于 2026-09-08 启动，用户同日确认 G4-A。G4-B 已把数据库提升到 schema
v3，并实现 `note_drafts` 与 `evidence_snapshots`、纯校验、乐观 revision、显式
证据包含/排序、来源 stale/detached 判断、应用 use cases 和备份恢复。测试仅使用
临时数据；G4-B 专项 40 passed，联合回归 513 passed / 1 个既有 Windows symlink
环境 skip。G4-C 随后实现准确选择/目标语言预览、点击后才调用翻译、资料库修订
绑定、原文/译文独立加入，以及包含/排序/移除证据篮；兼容消息选择默认为空。
G4-C 当时的默认生产套件为 418 passed / 1 skip，含 G3 实验的联合回归为
517 passed / 1 skip。

G4-C 已把 G3 选择接入翻译卡和证据篮：划词只填充本地卡片，仍需点击后才将准确
选择发送给现有翻译服务；证据也只有点击后持久化。G4-D 已实现可编辑 Markdown
正文、显式本地保存、由持久修订与已包含证据确定性合成的预览，以及需再次确认的
非覆盖 Vault 交接。未保存编辑、证据/来源状态变化或预览 SHA-256 不一致都会阻止
旧预览写入；最终文件字节与所确认预览一致。

G4-E 的聚焦集合为 42 passed；默认生产回归为 425 passed / 1 个既有 Windows
symlink 环境 skip；包含两套 G3 PDF 实验的联合回归为 524 passed / 1 skip。
隔离本机 Edge 152 旅程 8/8 通过，覆盖无自动 Vault 写、未保存编辑拦截、显式
本地保存、当前来源预览、确认写入和新浏览器会话重开；0 page errors，0 external
requests。用户于 2026-09-09 明确回复“G4通过验收”，G4 据此标记 Completed。
该确认不启动 G5，也不授权公式识别器、OCR、远程 crop 传输或新依赖。方案、实现
证据与回滚见
[G4 架构与验证](docs/V3_G4_NOTE_COMPOSER_DECISION.md)。

### V3-G5：公式识别

固定真实数学论文/合成标注语料、现有 V2/Spike baseline 和采用阈值，再比较候选。
生产版本必须有公式 provenance、严格 LaTeX 校验、用户编辑/接受、失败回退和 crop
外发提示。整篇 PDF→LaTeX 不在本阶段。

G5 已完成。LaTeX_OCR_PRO 因 GPL-3.0、旧 TensorFlow、缺少数据/权重和 shell
边界被拒绝；pix2tex 0.1.4 虽为 MIT，但因默认下载未固定哈希的外部权重、重依赖、
Python 3.12/Windows/CPU 证据不足而延后，均未安装或执行。当前采用窄
FormulaRecognizer 协议和既有 dots3-note-prev 的单 crop 视觉 adapter。

生产链路只在本机检测当前页并生成一张 bounded PNG；显示精确 hash、模型和外发范围
后，用户必须为该 crop 单独勾选并点击。候选经过严格 LaTeX 校验，仍须编辑/接受才
渲染，且只有已接受内容可选加入 G4 证据篮。raw crop、未接受输出和 provider 原始
响应不持久化，不发送路径、PDF、正文、历史或笔记。

20 条合成集达到 100% coverage、95% normalized exact、99.41% mean token
similarity 和 100% structural exact，全部预设阈值通过。用户授权的三篇论文固定
18 个 region：detector 保留 18/18，候选由 128 减到 78；recognizer 18/18 返回且
100% strict-valid、95.09% token、100% structure。真实 exact 只有 11.11%，说明
它是需人工确认的候选而非原源码恢复。Edge 152 假服务完整旅程 10/10，无页面错误，
识别前无外联；生产回归 474 passed / 1 个既有环境 skip，加入 G3 实验为
573 passed / 1 skip。详见
[G5 架构与质量门禁](docs/V3_G5_FORMULA_RECOGNITION_DECISION.md)。G5 完成不自动
启动 G6，也不授权本地权重、批量/后台识别或整篇 PDF→LaTeX。

### V3-G6：多语言代码（Completed）

用户于 2026-09-16 确认方案 A。Python 保留标准库 AST；C/Java/Julia 采用
tree-sitter 0.26 与三个独立官方 grammar wheel；R 采用项目内保守、非执行的
lexical adapter。所有 parser 只返回项目自有 CodeSymbol，语法错误保留 UTF-8
文本并降级为显式行选择。

本地与托管目录接受 .py/.c/.h/.java/.jl/.r，继续执行 2,000 文件、20 MB 总量、
1 MB 单文件、UTF-8、相对路径、隐藏/敏感/vendor/build 排除及 symlink/root
containment。语言与提取方式贯穿 CodeFile、CodeSelection、CodeContext、prompt、
EvidenceLink 和 Markdown。非 Python 在 UI 与用例层都保持只读，T5-B1 仍仅限
外部 Python 项目。

退出证据为 24 项聚焦 G6 检查、22/22 Streamlit AppTests、498 production passed /
1 个既有 Windows symlink 环境 skip、加入 G3 实验为 597 passed / 1 skip；本地
wheel 构建成功。五语言 2,000 次合成解析平均 0.1388 ms/次。完整决策、拒绝项与
限制见 docs/V3_G6_MULTILINGUAL_CODE_DECISION.md。

### V3-G7：加固与内部验收

复跑 V2 全闭环和全部 V3 旅程；验证迁移/备份/恢复、托管文件一致性、Zotero 可选
失败、公式/解析质量、浏览器布局/快捷键、隐私、依赖漏洞、长文档/大项目性能。
只有所有自动证据和明确人工门禁完成后，才讨论 V3 内部版本号；不自动公开发布。

## 7. V3-G1 已确认架构决定

V3-G1 采用方案：

1. Python 标准库 sqlite3，不使用 ORM 或数据库服务器；
2. 新建 database 模块，唯一负责 schema、迁移、事务和 repository；
3. 新增显式 RESEARCHMIND_DATA_DIR 配置，数据库位于其下，托管文件放在独立
   assets 子目录；不默认放入 Vault 或代码项目；
4. 资料库存元数据/哈希/相对路径，PDF 与代码文件保存在托管目录；
5. 精确哈希去重；修订建立新 AssetReference，不静默覆盖；
6. 移除记录与删除托管副本分开确认；外部文件永不删除；
7. 先实现 G1-A/G1-B，再实现代码目录上传 G1-C。

用户已于 2026-09-01 确认该方案，G1 实现与自动验证已完成。用户又于
2026-09-02 确认 G2 的只读 Local API 方案。G2 元数据/来源链接已实现；2026-09-04
发现真实附件接口为本地文件重定向，随后用户批准安全读取边界；Windows 单 PDF
复制已实现并完成自动验证，真实 Zotero 人工验收已由用户确认通过。该状态不授权 Web API、写请求、同步或全库缓存。

## 8. 通用验证与停止条件

- routine 测试全部使用 fake provider、临时数据库/托管目录/项目/Vault；
- live Zotero、LLM 或公式服务测试必须单独授权并说明外发/成本；
- AppTest 不替代真实浏览器 DOM/滚轮/快捷键/响应式验收；
- API 连接、数据完整性、定位、上下文/回答、公式/解析器、视觉、安全、性能和
  恢复分别报告；
- 重大依赖未达到质量、Windows、隐私或维护门槛时，允许 reject/defer，不为了
  “完成路线图”强行进入生产；
- 任何阶段缺少退出证据时保持 Pending/Active，不能标记 Completed。
