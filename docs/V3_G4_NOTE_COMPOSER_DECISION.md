# V3-G4 划词翻译与显式笔记草稿：架构入口

日期：2026-09-08  
状态：**Completed · 用户于 2026-09-09 确认 G4 验收通过**  
进入基线：`2c27efe`（V3-G3 Completed）  
当前代码的最新数据库版本：schema v3；测试未读取或迁移用户真实资料库，不写
用户 Vault，也不调用真实翻译服务。

## 1. 为什么需要这一门禁

G3 已把可信的浏览器文字层选择映射为 `ReadingSelection`，但当前笔记仍是
`KnowledgeNote` 会话对象：消息用临时索引选择，Markdown 只能查看，重启后草稿
消失。G4 需要新增跨重启状态，并决定正文编辑和来源真实性如何同时保留，因此是
持久化和应用合同变更，不能只在 View 中增加几个控件。

## 2. G4 可见目标

1. 页面选择确认后自动打开翻译卡，并展示将发送的准确文本和目标语言；默认由
   用户点击“翻译并发送”后才调用现有 `TranslationProvider`。
2. 原文、翻译、当前 V2 LaTeX、问题和选定回答只有在用户点击“加入笔记”后才
   成为证据；未选择的聊天不会进入草稿。
3. 草稿正文可编辑并跨重启恢复；Markdown 编辑与渲染预览是两个明确状态。
4. 本地保存草稿不写 Obsidian。只有最后一次显式操作才通过现有唯一 Vault writer
   非覆盖写入 `.md`。
5. 来源发生变化或无法重开时，证据显示为 stale/detached，不伪造当前有效定位。

G4 不包含自动公式识别、图片 OCR、整篇 PDF→LaTeX、对话历史持久化、Zotero
写入/同步、非 Python 解析或代码执行。

## 3. 数据流与所有权

```text
CCv2 candidate
→ G3 PyMuPDF reconciliation
→ ReadingSelection
→ transfer preview → explicit translate → TranslationProvider
→ explicit add/remove/reorder
→ EvidenceSnapshot + editable NoteDraft
→ SQLite transaction
→ editor → rendered preview
→ explicit save → integration/obsidian → new Markdown file
```

- `models` 定义框架无关的 `NoteDraft` 和 `EvidenceSnapshot`。
- `core` 校验内容上限、证据类型、顺序、状态和 stale 规则。
- `database` 独占 schema v3、迁移、事务和 draft repository。
- `app/use_cases.py` 编排选择、翻译、草稿和最终导出。
- `app/state.py` 仍是唯一 Streamlit session-state 变更点；View 只展示和委托。
- `integration/obsidian` 仍是唯一 Vault writer。

## 4. 持久化方案比较

| 方案 | 优点 | 主要代价/风险 | 结论 |
|---|---|---|---|
| A. schema v3：`note_drafts` + `evidence_snapshots` 两表 | 正文和来源分离；可精确包含/排除、排序、stale 检查和恢复；沿用 sqlite3/备份 | 增加一次受测迁移和 repository | **推荐** |
| B. 每个草稿一个 JSON blob | 初始代码少 | 迁移、局部更新、约束和损坏诊断较弱；来源容易被正文覆盖 | 不推荐 |
| C. 数据目录内直接保存 Markdown 草稿 | 人工可读 | 数据库/文件双写、崩溃补偿和来源结构化更复杂；也容易与 Vault 混淆 | 不推荐 |

## 5. 推荐的 G4-A 合同

### 5.1 NoteDraft

草稿具有稳定 ID、可选的 `LibraryRecord`/`AssetReference` 来源、标题、可编辑
Markdown 正文、整数 revision、创建/更新时间和显式状态。资料库来源可以为空，
以兼容 V2 的临时本地 PDF；这种草稿跨重启仍可读，但若原文件未作为托管资产
重开，则来源标记为 detached。

### 5.2 EvidenceSnapshot

每个证据项保存稳定 ID、所属草稿、受限类型、内容快照、显示来源、结构化 locator、
origin、可选 record/asset/revision/hash、原 selection/message ID、包含状态、顺序和
创建时间。证据只在显式加入后持久化；删除聊天或编辑正文不会暗中改写它。

G4 支持当前已有的 `source_text`、`translation`、`latex`、`question`、`answer` 和
`code` 证据类型，但不会把 G5 公式候选伪装成已识别公式。stale 状态由保存的来源
修订与当前来源对比计算，而不是把旧快照当成当前事实。

### 5.3 编辑、预览和导出

- Markdown 正文是用户可编辑内容；证据篮控制证据的包含、排除和顺序。
- 预览由当前正文和所选证据的只读 provenance 部分确定性合成。
- 预览必须与最终交给 Vault writer 的字节一致；预览不产生文件。
- 用户可以编辑解释文字，但不能通过正文编辑静默覆盖数据库中的来源快照。
- Vault 保存保留现有路径净化、遍历拒绝、Markdown-only、重名编号和不覆盖合同。

### 5.4 翻译与隐私

划词本身只更新本地 UI。翻译卡展示精确选择和目标语言，默认点击后才外发；G4
不增加后台请求或自动上传整页/整篇论文。调用继续只发送选择文本和目标语言，
失败不创建“成功翻译”证据。测试只使用 fake provider。

## 6. 迁移、删除与回滚

- schema v2→v3 必须在一个 `BEGIN IMMEDIATE` 事务中完成；失败保持 v2。
- 草稿删除与 Vault 文件删除无关；G4 不提供删除 Vault 笔记的能力。
- 软移除资料库记录不会删除草稿/证据；来源在 UI 中显示不可用或 stale。
- 删除托管副本前仍遵循现有确认，并先展示受影响草稿；外部 PDF、Zotero 附件、
  代码目录和 Vault 笔记永不作为草稿操作的副作用删除。
- schema 迁移没有自动降级。进入生产迁移前必须创建并验证资料库备份；若放弃 G4，
  使用 G3 代码和迁移前备份恢复到一个新的数据目录，而不是修改原备份。

## 7. 确认后的实施切片

1. **G4-B 数据合同**：模型、纯校验、schema v3、repository、v2→v3/回滚/外键/
   重启/备份恢复测试。
2. **G4-C 证据与翻译**：G3 选择到翻译卡、fake provider、显式加入/移除/排序、
   stale/detached 展示和 AppTest。
3. **G4-D 编辑与输出**：Markdown 编辑/预览一致性、显式本地保存、显式 Vault
   非覆盖写入和失败可见性。
4. **G4-E 关闭门禁**：受影响的 V2/G1/G2/G3 回归、安全/恢复检查、真实浏览器
   人工旅程；全部证据完成后才把 G4 标记 Completed。

## 8. 决定记录

用户于 2026-09-08 明确确认 **G4-A 推荐方案**。该确认授权 schema v2→v3、
`NoteDraft`/`EvidenceSnapshot` 模型与 repository，不授权真实翻译调用、自动
Vault 写入、公开发布或 G5。

## 9. G4-B 实现与验证

已实现：

- schema v3 新增 `note_drafts` 和 `evidence_snapshots`，并用外键保证资产属于
  对应 record；v2→v3 在现有迁移事务中完成；
- 框架无关模型与纯校验：内容/locator 上限、时区、SHA-256、相对路径、来源
  完整性和受限类型；
- 独立 `NoteDraftRepository`：创建/读取/列出/乐观更新/确认删除、显式证据加入、
  包含/排除、精确排序、内部级联和 current/stale/detached 来源判断；
- `app/use_cases.py` 提供对应应用入口，本地草稿操作不会调用 Vault writer；
- 资料库备份/恢复自然包含 schema v3 草稿和证据，不新增文件双写。

验证结果：

- G4-B 专项与受影响迁移/备份：`40 passed`；
- 默认生产测试目录：`414 passed / 1 Windows symlink environment skip`；
- `tests/` 加两套 G3 隔离实验的联合回归：`513 passed / 1 environment skip`，
  相比 G3 的 486 项联合基线新增 27 项且无回归。

G4-C 已实现翻译卡和证据篮；下文记录随后完成的 G4-D/G4-E。

## 10. G4-C 实现与验证

已实现：

- 当前 ReadingSelection 生成不含绝对路径的稳定指纹；正式 PDF.js 选择的文档
  revision、viewer engine、server-reconciled bboxes/client ranges、几何覆盖率和
  locator 状态以受限 JSON 保存；
- 划词后显示本次翻译的准确原文和目标语言。查看卡片不联网，只有点击
  “翻译所选文本”才调用现有 TranslationProvider；预览和真实调用复用同一个
  规范化请求函数；
- 从资料库打开论文时，app/state.py 同时保存准确的 LibraryEntry 修订。加入
  证据前重新核对 PDF SHA-256；来源不匹配、已移除或已删除时失败关闭；
- “加入原文”和“加入译文”是两个独立按钮。第一次明确加入才建立持久草稿；
  同一选择/类型的重复加入被拒绝，对话本身仍只存在于会话；
- 证据篮可显式包含/排除、上移/下移和移除，并显示 current/stale/detached；
  每个操作使用乐观 revision。所有这些操作只写 ResearchMind 数据库，不写 Vault；
- 兼容 KnowledgeNote 流仍暂时保留，但消息 multiselect 默认改为空；未明确勾选
  的对话不会进入兼容笔记。

自动验证：

- G4-C 翻译/草稿/Streamlit 聚焦集合：32 passed；
- 默认生产测试目录：418 passed / 1 Windows symlink environment skip；
- tests/ 加两套 G3 隔离实验联合回归：517 passed / 1 environment skip；
- AppTest 覆盖未点击不调用 provider、原文/译文分别加入、修订绑定、排序、排除、
  移除以及全过程无 Vault Markdown 写入；
- 正式 G3 PDF.js 选择到 EvidenceSnapshot 的测试保留 document revision、engine、
  bboxes 和 client ranges，并验证 detached 降级。

## 11. G4-D 编辑与输出实现

已实现：

- 用户可新建或重新打开当前论文的持久 `NoteDraft`，标题与 Markdown 正文仅在
  点击“保存草稿到本地资料库”后使用乐观 revision 更新；编辑和保存均不写 Vault；
- 预览只从已持久化的一个草稿修订、已包含且已排序的 `EvidenceSnapshot` 以及
  实时计算的 current/stale/detached 来源状态确定性合成；正文与不可变来源附录
  分离，编辑解释文字不会静默改写证据快照；
- `NoteDraftPreview` 绑定 draft ID、revision、准确 Markdown、纳入证据数和 SHA-256。
  未保存编辑暂停旧预览；草稿、证据或来源状态变化以及预览篡改都会要求重新预览；
- 最终按钮需要针对该预览的显式确认，并由 `integration/obsidian` 唯一 writer
  写入完全相同的 UTF-8 Markdown 字节；仍使用安全相对目录、文件名净化、排斥式
  新建和重名编号，不覆盖既有 Vault 文件；失败作为项目错误显示，不报告假成功；
- V2 `KnowledgeNote` 流保留在兼容区域，消息选择默认仍为空。G4 的持久证据 UI
  当前直接提供原文和译文捕获；其他已定义 evidence kind 不应被描述为全部已有
  对应 UI，公式捕获仍受 G5 门禁约束。

关键实现：

- `src/researchmind/app/views/knowledge.py`：恢复/选择草稿、编辑、本地保存、预览和
  明确输出；
- `src/researchmind/app/use_cases.py`：当前论文草稿列表、revision-bound 预览及
  写入前重新验证；
- `src/researchmind/integration/obsidian/markdown.py`：确定性正文与来源附录合成；
- `src/researchmind/integration/obsidian/vault.py`：预渲染 Markdown 的唯一非覆盖
  文件写入；
- `src/researchmind/app/state.py`：当前草稿、预览与最近输出路径的唯一 UI 状态入口。

## 12. G4-E 验证与关闭

自动证据：

- G4-D/G4-E 聚焦集合：`42 passed`；
- 默认生产测试：`425 passed / 1 skipped`；
- `tests/` 加两套 G3 PDF 实验联合回归：`524 passed / 1 skipped`；
- 唯一 skip 仍是当前 Windows 主机不能创建测试符号链接，不是 G4 产品失败；
- `git diff --check` 无空白错误，Node 对浏览器验收脚本的语法检查通过。

浏览器与人工证据：

- 桌面 CUA 因本机 Windows sandbox helper 初始化错误不可用，未把工具故障记为
  产品失败；随后使用 Codex 内置 Playwright 与本机 Edge 152.0.4191.66，在独立
  `8514` 实例、合成 PDF、临时资料库和临时 Vault 上完成 8/8 旅程；
- 旅程验证选择本身、证据加入、本地草稿保存和预览均不创建 Vault 文件；未保存
  编辑不能导出旧预览；确认后生成一份含来源 SHA-256 的 Markdown；新的浏览器
  会话可重新打开正文；0 page errors，0 external requests；
- AppTest 另覆盖预览字节与最终文件一致、重名不覆盖、Vault 写失败可见、排除的
  证据不进入预览，以及来源由 current 变 stale 后旧预览被拒绝；
- 用户于 2026-09-09 两次明确回复“G4通过验收”。验收用 `8514` 进程、合成 PDF、
  临时 SQLite、日志和临时 Vault 已在记录结果后删除。

因此 V3-G4 标记 **Completed**。Conversation、ReadingSelection、解释、T5-A 会话、
EvidenceLink 和兼容 KnowledgeNote 仍不自动持久化；G4 没有启动 G5，没有采用公式
识别/OCR 服务，也没有扩大 Zotero、代码执行或源文件写入权限。
