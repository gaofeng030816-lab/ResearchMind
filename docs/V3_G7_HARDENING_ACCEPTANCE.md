# ResearchMind V3-G7 加固与内部验收记录

状态：**Completed（用户已确认 V3 内部验收）**
启动日期：2026-09-19
自动门禁同步日期：2026-09-21
用户验收日期：2026-09-21
实现基线：提交 `561a61a`（V3-G6 完成）
发布状态：内部开发，不对外发布

## 1. 目的与边界

G7 不再引入新的产品能力。它验证 G1–G6 已实现能力能否在迁移、恢复、安全、
隐私、性能、打包和真实交互中组成稳定的本地研究工作台。G7 不授权新的数据库、
云同步、Zotero 写入、代码执行、T5-BX、公开发布或自动修改用户资料。

自动与人工门禁现已完成。用户于 2026-09-21 明确确认“G7通过验收并提交最终V3”。
内部版本字段更新为 `3.0.0rc1`；这表示 V3 本地内部候选通过验收，不是公开发布
或对外兼容性承诺。V2 `2.0.0rc1` 继续保留为历史回归基线。

## 2. 子门禁状态

| 子门禁 | 状态 | 结论 |
|---|---|---|
| G7-A 入口基线与完整性 | Completed | G6 基线、生产回归、迁移/恢复、安全边界、依赖一致性和编译通过 |
| G7-B 安全、隐私与依赖 | Completed（内部） | 漏洞、网络、密钥、wheel 内容与许可证完成复核；公开发布仍受 PyMuPDF 许可决策阻塞 |
| G7-C 恢复与性能 | Completed | 既有规模基准与新增持久化/草稿/备份恢复基准均通过 |
| G7-D 浏览器与旅程 | Completed（自动证据） | Edge 覆盖 PDF、草稿、公式、五语言和 Zotero 关闭态；无外部请求或页面错误 |
| G7-E 内部候选关闭 | Completed（用户确认） | wheel、隔离安装、启动、联合回归、文档和用户明确验收全部通过 |

## 3. G7-A：入口基线与完整性

- Git 基线：G6 独立提交为 `561a61a`；G7 修改与该提交分离。
- 入口生产回归：`498 passed, 1 skipped`；最终加入两个 G7 基准测试后为
  **500 passed, 1 skipped in 22.43s**。
- 唯一 skip：`tests/unit/test_code_change_writer.py:129`，本 Windows 主机不能
  创建测试 symlink；生产实现仍显式拒绝 symlink，不能把 skip 记为通过。
- 迁移、恢复与安全边界聚焦集：**141 passed, 1 skipped**。
- `pip check`：`No broken requirements found.`
- `compileall -q src tests`：通过。
- `.env` 和 `.streamlit/secrets.toml` 未被 Git 跟踪；生产路径扫描没有 API key
  形态命中，诊断不显示凭据或绝对资料库/Vault 路径。

## 4. G7-B：安全、隐私、依赖与许可证

### 4.1 网络与权限边界

静态审计确认生产网络出口仍只有：

1. 用户显式触发的 OpenAI-compatible LLM/翻译/公式 provider；
2. 用户显式启用并点击后的固定 `127.0.0.1:23119/api/` Zotero GET 边界。

数据库、PDF 解析、代码解析、草稿、备份、恢复和 Vault 写入没有遥测或后台网络。
任意源码执行、Shell、依赖安装、Zotero 写入和 T5-BX 仍不存在。公式流仍只允许在
精确 crop 预览、hash 和逐次确认后发送一个 PNG crop。

### 4.2 漏洞与依赖

- 使用临时 `pip-audit 2.10.1` 扫描当前生产 `.venv` 的 61 个依赖；
  **0 个已知漏洞、0 个修复建议**。
- 临时审计环境已删除，`pip-audit` 没有加入项目运行时依赖。
- 直接运行时依赖许可证已补入 `THIRD_PARTY_NOTICES.md`。
- G7 干净安装还验证了声明范围内较新版本组合，包括
  `openai 3.16.2` 与 `streamlit 1.64.0`；当前开发环境仍以已测试的
  `openai 3.5.0` 与 `streamlit 1.62.0` 为生产回归基线。

### 4.3 公开发布阻塞项

PyMuPDF 1.28.2 的上游分发为 AGPL-3.0 或商业许可双重模式。ResearchMind 仍是
本地内部项目；在公开分发、封闭源发布或商业部署前，必须单独完成法律/许可选择。
G7 内部验收不会消除这一阻塞，也不把本记录解释成法律意见。

## 5. G7-C：恢复与性能

### 5.1 既有规模基准

`evaluations/t6_c/benchmark.py` 在 Python 3.12.14 / Windows 11 上通过全部阈值：

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 配置读取 | 0.001614 s / 0.006 MiB | 通过 |
| 100 页 PDF 打开 | 0.052342 s / 1.05 MiB | 通过 |
| PDF 页面渲染 | 0.025965 s / 0.01 MiB | 通过 |
| 2,000 文件代码索引 | 3.447829 s / 5.14 MiB | 20 s 内 |
| 1,000 Markdown 备份 | 6.026222 s / 3.074 MiB | 通过 |
| 1,000 Markdown 恢复 | 1.191755 s / 1.231 MiB | 通过 |

### 5.2 V3 持久化基准

新增 `evaluations/g7/hardening_benchmark.py`，只使用临时合成数据：250 个唯一
托管代码记录、250 个 NoteDraft、列表、完整资料库备份和恢复到不存在的新目录。

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 250 个资料库记录 | 8.509680 s | 20 s |
| 250 个草稿 | 2.889137 s | 10 s |
| 资料库与草稿列表 | 0.058741 s | 2 s |
| 资料库备份 | 0.611197 s | 10 s |
| 资料库恢复 | 0.720743 s | 10 s |

结果保存在 `evaluations/g7/results_2026-09-21.json`；两个可重复测试通过。完整测试
还覆盖 schema v1/v2→v3、损坏/新版本拒绝、事务回滚、并发初始化、篡改、穿越、
中断导入、托管资产漂移、软删除、备份和只恢复到不存在目录。

## 6. G7-D：浏览器与旅程

由于 Codex Windows CUA 在启动时返回
`windows sandbox failed: helper_unknown_error: setup refresh had errors`，本轮没有
把 CUA 失败伪装成产品失败或人工视觉证据。改用项目既有 Playwright 脚本和本机
Microsoft Edge 153.0.4234.48，对隔离 Streamlit、临时资料库/Vault、合成 PDF/代码
及本地 fake formula provider 执行确定性检查。

- **PDF/G3：8/8**。论文单栏、真实鼠标文本选择与 PyMuPDF 对账、中部普通滚动、
  边缘防抖翻页、末页边界、输入安全快捷键、桌面分栏和 600px 堆叠均通过。
- **草稿/G4：8/8**。选择和证据捕获不写 Vault；未保存编辑使旧预览失效；本地
  草稿保存不写 Vault；预览与 provenance 一致；明确导出只生成一个非覆盖
  Markdown；新浏览器会话可重新打开持久草稿。
- **公式/G5：10/10**。20 页合成 PDF、有限和式页面、一个有界 region、crop hash/
  外发范围、确认前禁用、单次确认、可编辑候选、明确接受和可选证据均通过。
  fake provider 只收到一个 5,187-byte PNG；crop SHA-256 与 UI 报告一致，没有
  PDF、路径、历史或笔记。
- **代码/G6：9 项检查**。同一项目索引 Python/C/Java/Julia/R；每种选择均保留
  language/extraction provenance；C/Java/Julia/R 显示只读权限提示且没有 T5-B1；
  Python 保留既有受控入口；Zotero 关闭态正常。
- 所有上述浏览器旅程：**0 external requests、0 page errors**。公式假服务只在
  用户确认后的单 crop 请求中使用本机回环端口。

此前用户已经分别确认 G2 Zotero 人工验收、G3 物理触控板验收与
CCv2/pdf.js 正式采纳、G4 人工验收。这些按原日期保留为用户报告，不改写成
本轮 agent 观察。用户于 2026-09-21 明确确认“G7通过验收并提交最终V3”，因此
G7 的整体人工验收现已关闭；这仍是内部候选验收，不是公开发布授权。

## 7. G7-E：内部候选自动关闭证据

### 7.1 最终回归

- 生产：**500 passed, 1 skipped in 22.43s**。
- 生产加完整已采纳 G3 实验目录：**599 passed, 1 skipped in 26.10s**。
- 唯一 skip 与 G7-A 相同。
- 较早只指定 `test_wrapper.py` 的 569/1 命令漏掉 30 项
  `test_provenance.py`；最终结果使用完整目录，不能用较小计数替代。

### 7.2 wheel 与隔离安装

- wheel：`researchmind-3.0.0rc1-py3-none-any.whl`
- 大小：**1,081,267 bytes**
- SHA-256：`108ce1329f31aed5f6221bd74360b66f5aa979c1d8f85c0c22781a4362f57664`
- 113 个条目；恰好一个 JS、一个 CSS；包含 pdf.js license 和第三方 notices；
  不含 tests、`.env`、`secrets.toml`、`node_modules`、source map、API key
  形态或本机私有绝对路径。
- 首次 `--no-build-isolation` 因开发 `.venv` 没有 setuptools 而在元数据阶段
  失败，没有生成 wheel；随后使用 pyproject 声明的标准隔离构建与
  `setuptools 80.10.2` 成功。临时构建后端不属于运行时依赖。
- 新 Python 3.12.14 venv 从该 wheel 非 editable 安装成功；导入路径位于新环境
  `site-packages`；`pip check` 无损坏依赖；包元数据与模块版本均为
  `3.0.0rc1`。
- 安装后的固定 launcher 仅监听验收专用的 `127.0.0.1:8524`；根页面返回
  `200 text/html`，`/_stcore/health` 返回 `200 / ok`，随后服务已停止。
- 配置诊断 `has_errors=false`，没有联网或显示凭据/绝对路径。

## 8. 剩余限制与用户验收

自动门禁已关闭，但以下边界继续保留：

- 不公开发布，不创建 tag，不推送 release；
- 不声称公式候选等同原始 TeX，也不提供整篇 PDF→LaTeX；
- Zotero 仍为可选、个人资料库、GET-only、逐文件同意；
- 非 Python 代码仍只读，T5-B1 仍只适用于外部本地 Python 的一个已选范围；
- PyMuPDF 许可在任何公开/封闭源分发前必须单独解决；
- Codex CUA 本轮不可用；自动证据使用 Edge/Playwright，未被重写成人工证据。

用户于 2026-09-21 在隔离候选中完成最终人工检查，并明确回复
“G7通过验收并提交最终V3”。该确认关闭 G7-E 和 V3 内部验收门禁。论文/PDF、
逐 crop 公式候选、五语言只读代码边界、显式证据/草稿/Vault 保存与 Zotero
可选失败语义均按现有合同保留。人工验收不解除 PyMuPDF 许可、非公开发布、
无 T5-BX、无 Zotero 写入及无整篇 PDF→LaTeX 等限制。
