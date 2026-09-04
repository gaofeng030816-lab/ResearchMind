# T4 显式证据链接实现与验证

日期：2026-08-29
状态：Completed
基线：V1.3.2 + T1/T3/T4 内部增量，不对外发布

## 1. 问题与范围

T3 已能分别追溯论文选择和 Python 代码选择，但用户无法把“这段代码实现/
解释/支持论文中的这个公式或算法”作为一个可保存、可复核的主张记录下来。

T4 的目标是建立最小显式链接，而不是自动发现关系。实现范围：

- 论文端只接受具有可靠页码的 PDF `ReadingSelection`；
- 论文证据类型为 paper、mathematics 或 algorithm；
- 代码端只接受仍匹配当前 `CodeProject` 的 `CodeSelection`；
- 用户选择 relation、0–1 confidence，并可填写 rationale；
- 生产路径固定写入 `generation_method=user_confirmed`；
- 链接保存在当前 Streamlit 会话，并在生成 KnowledgeNote 时复制；
- Obsidian Markdown 输出双方 locator、关系、置信度、生成方式和片段。

明确排除：

- 自动 Paper–Code 发现或模型生成链接；
- 将 ResearchContext 与 CodeContext 合成联合 prompt；
- 跨会话链接库、SQLite 或其他数据库；
- 代码写入、执行、shell、测试、依赖安装或 Agent 工具。

## 2. Before / After

| 维度 | T3 之前 | T4 之后 |
|---|---|---|
| 论文来源 | page/block/bbox 可追溯 | 保留为 `PaperEvidenceReference` |
| 代码来源 | relative path/line/symbol 可追溯 | 保留为 `CodeEvidenceReference` |
| 双方关系 | 只能由用户在笔记中自由描述 | 强类型 relation + confidence + generation method |
| 生成语义 | 无法区分用户判断与模型推断 | UI/Markdown 明确显示“用户确认”等 origin |
| 知识沉淀 | CodeContext 不进入笔记 | 显式链接随 KnowledgeNote 进入 Markdown |
| 持久化 | 无代码数据库 | 仍无数据库；只有 Vault Markdown 是长期结果 |

## 3. 模型与数据流

`models/evidence_link.py` 定义：

- `PaperEvidenceReference`：document id/title、evidence kind、page/block/bbox、
  excerpt；
- `CodeEvidenceReference`：project id/name、relative path、line、symbol、
  extraction method、excerpt；
- `EvidenceLink`：paper、code、relation、confidence、generation method、
  rationale、created_at 和 id。

实际数据流：

```text
located ReadingSelection + current CodeSelection
→ app/use_cases.py
→ core/evidence_links.py validates both endpoints and source consistency
→ user_confirmed EvidenceLink
→ app/state.py session collection
→ capture_knowledge copies links
→ integration/obsidian/markdown.py
→ traceable Markdown in the configured Vault
```

链接创建不构造 provider、不调用网络。代码绝对根目录不进入 link 或 Markdown。

## 4. 安全与诚实性

- 没有页码的论文选择不能建立事实链接；
- 代码选择必须属于当前项目，行范围有效且文本仍与只读源码一致；
- confidence 必须是有限的 0–1 数值；
- 同一端点、relation 和 generation method 的重复主张被拒绝；
- 当前创建入口只能产生 `user_confirmed`；
- 模型层可表达 `deterministic` 和 `model_inference`，但 UI/Markdown 使用不同
  标签，不能冒充用户确认；
- 打开新 PDF 或新代码项目会清空链接，避免旧状态串入新来源；
- 代码片段用缩进 Markdown 渲染，避免源码内围栏破坏笔记结构。

## 5. Regression-first 证据

实现前的聚焦测试按预期在收集阶段失败：

- `researchmind.core` 尚无 `add_evidence_link` /
  `create_user_confirmed_evidence_link`；
- `researchmind.models` 尚无 `PaperEvidenceReference` /
  `CodeEvidenceReference` / `EvidenceLink`。

这证明测试针对的是 T4 缺失能力，而不是已有行为的偶发失败。

实现后的最终聚焦命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_core_evidence_links.py `
  tests/unit/test_knowledge_use_cases.py `
  tests/unit/test_obsidian_markdown.py `
  tests/e2e/test_streamlit_app.py `
  -q --basetemp=.pytest-tmp-t4-focused-final
```

结果：`26 passed in 7.81s`。

阶段实现后的首轮全量结果为 `197 passed in 10.99s`；补齐 algorithm 证据类型
回归后，最终全量、编译、依赖和文档/Skill 校验结果见本文件第 7 节。

## 6. T4 退出条件映射

| 退出条件 | 实现证据 |
|---|---|
| 来源、定位、关系、置信度和生成方式 | 双 reference + `EvidenceLink` 强类型字段 |
| UI 区分三种 origin | generation method 标签映射；当前入口只创建用户确认 |
| 持久化先评估 SQLite | 没有跨会话需求证据；采用会话内 + KnowledgeNote Markdown，无 SQLite |
| 模型猜测不能伪装成事实 | 生产创建函数固定 user_confirmed；模型推断必须保留独立枚举值 |
| Notes 可持久化链接 | `KnowledgeNote.evidence_links` + Obsidian 证据链接章节 |

## 7. 最终验证

- 聚焦 T4：`26 passed in 7.81s`；
- 全量 pytest：`198 passed in 9.38s`；
- `python -m compileall -q src tests scripts experiments`：退出码 0；
- `python -m pip check`：`No broken requirements found.`；
- 六个项目 Skills：官方 `quick_validate.py` 全部通过；
- `git diff --check`：无空白错误（Windows 行尾转换警告除外）；
- 人工视觉：沿用 T0/T3 的 Codex Windows 浏览器控制进程阻塞，不伪报通过。

## 8. 遗留限制与下一门禁

- 当前没有链接编辑/删除、跨会话恢复或多论文链接库；
- 链接质量来自用户判断，confidence 不是统计校准值；
- T4 不评估模型自动关联准确率，也不把链接用作联合 AI 请求；
- 下一步是 T5 受限智能助手。必须先批准
  [T5_AGENT_TOOLS_ENTRY_DECISION.md](./T5_AGENT_TOOLS_ENTRY_DECISION.md)
  的工具清单和权限边界，不能从 T4 自动获得工具权限。
