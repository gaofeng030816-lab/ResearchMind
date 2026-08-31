# T5-B1 单文件受控代码写入验证

日期：2026-08-30
状态：Completed / User-approved contract implemented and verified
前置：T5-A Completed；用户明确确认 T5-B1；T6-C 由用户确认通过
产品仍为内部基线，不对外发布

## 1. Problem / Before / After

此前 ResearchMind 能静态索引、选择和解释 Python，但任何模型输出都没有源码
写入权限。用户确认的 T5-B1 只解决一个更窄的问题：对当前 `CodeSelection` 所在
的一个既有 `.py` 行范围提出替换，并在用户检查 diff 后逐次应用或回滚。

实现后：

- “生成建议”只调用 LLM 并建立内存 `CodeChangeProposal`，不会写磁盘；
- 严格协议只接受一个 `<replacement>...</replacement>`，拒绝路径字段、命令、
  多 wrapper、外部说明、空内容、NUL 和超过 20,000 字符的输出；
- Core 只替换已选择行，最多改变 400 行，候选文件不超过 1 MiB，并对整个候选
  执行 UTF-8 编码和标准库 `ast.parse` 校验；
- UI 展示相对路径、行范围、字符/改变行数、语法结果和 unified diff；
- `apply_code_change_proposal(..., confirmed=False)` 在应用层也拒绝写入，确认不是
  只靠按钮外观；
- 写前建立项目内不覆盖的 `.researchmind-recovery/` 副本，同目录临时文件
  `flush`/`fsync` 后使用 `os.replace` 原子更新目标；
- 源文件从 proposal 后发生变化会因原始 SHA-256 不匹配而拒绝；回滚只在当前
  文件仍匹配已应用 SHA-256 时执行，防止覆盖外部编辑；
- 应用后只刷新被修改文件的项目模型，并使旧选择、解释、证据链接、KnowledgeNote
  和 T5-A 待继续状态失效；
- propose/apply/cancel/rollback 只在当前会话记录相对路径、行号、时间、截断展示
  的 hash、恢复相对路径和错误类型，不记录源码、修改要求、完整请求、绝对路径
  或 API Key。

## 2. 实际数据流与所有权

```text
current CodeSelection
→ app/use_cases.py 读取当前 CodeFileSnapshot 并核对索引/选择
→ core/code_context.py 构建有界 CodeContext
→ llm/prompts.py 构建受限 change prompt
→ LlmProvider
→ llm/code_change.py 严格解析 replacement
→ core/code_changes.py 拼接、diff、行数/大小/AST/hash 校验
→ CodeChangeProposal（仅内存预览）
→ 用户单独确认
→ code/change_writer.py 恢复副本 + 原子替换
→ app/state.py 刷新单文件项目模型并保存会话审计元数据
```

回滚使用 `CodeChangeReceipt` 的 applied/original SHA-256 和 recovery 相对路径；
恢复副本保留，不在回滚后删除。`models/` 仍为纯 dataclass，Core 不访问文件，
View 不直接修改 session state。

## 3. 明确没有的权限

- 没有 Shell、PowerShell、终端、`subprocess`、import、eval、exec 或测试执行；
- 没有依赖安装、Git、网络搜索、任意路径、创建/重命名/删除源码或多文件批改；
- 没有 PDF/Vault 修改、自动 EvidenceLink、后台循环、跨会话 Agent 或自主修复；
- T5-A 的三个无参数只读工具未改变，也不能隐式批准 T5-B1 写入。

## 4. Regression-first 证据

实现前先加入四组测试，首次收集按预期因缺少 `llm.code_change`、snapshot/writer
边界和应用用例而出现 4 个 collection error。

最终命令与真实结果：

```text
.venv\Scripts\python.exe -m pytest tests\unit\test_code_change_protocol.py tests\unit\test_code_change_core.py tests\unit\test_code_change_writer.py tests\unit\test_code_change_use_cases.py tests\e2e\test_streamlit_app.py -q --basetemp D:\ResearchMind\.pytest-tmp\t5b1-final-focused
→ 34 passed, 1 skipped in 8.45s

.venv\Scripts\python.exe -m pytest -q --basetemp D:\ResearchMind\.pytest-tmp\full-t5b1-2
→ 261 passed, 1 skipped in 10.55s

.venv\Scripts\python.exe -m compileall -q src tests evaluations
→ exit 0

.venv\Scripts\python.exe -m pip check
→ No broken requirements found.

git -c safe.directory=D:/ResearchMind diff --check
→ exit 0（仅既有 LF/CRLF 提示）
```

覆盖包括严格协议与注入、多动作/超长输出、选择/索引一致性、Python 语法、
400 行限制、相对 diff、未确认零写入、proposal 后磁盘冲突、恢复副本、原子写入
失败、外部编辑安全回滚、取消、会话审计和完整 Streamlit 应用/回滚。

唯一跳过项：当前 Windows 主机不允许测试进程创建符号链接，因此
`test_writer_rejects_symlink_target_when_platform_allows_it` 跳过。生产边界仍逐层
检查目标与恢复路径的每个组件并拒绝 symlink；应在允许创建 symlink 的 Windows
Developer Mode 或其他受控主机补跑，不能把本机 skip 描述成动态通过。

## 5. 门禁结论与遗留限制

T5-B1 的确认合同已实现并通过自动回归，状态为 `Completed`。它是一个用户逐次
控制的单文件写入能力，不等于任意 Agent、代码生成器或执行沙箱。

遗留限制：

- 只支持当前已索引的 UTF-8 Python 文件和一个选择范围；
- 模型建议可能逻辑错误，`ast.parse` 只证明语法有效，用户仍须检查 diff；
- 不运行测试，因此不证明行为正确或科研结果可复现；
- 恢复副本与审计不跨设备管理；审计仅在当前 Streamlit 会话；
- 符号链接动态测试需在允许创建 symlink 的受控主机补跑。

下一步不是直接加入 Shell。若确需执行测试，应先确认 T5-BX 隔离沙箱 Spike，并
证明文件、网络、子进程和终止隔离；当前无此授权。

## 6. 用户触发的 T5-B1 复验（2026-08-30）

用户再次要求“进行 T5-B1”后，在仓库内可丢弃临时项目上重新执行了协议、Core、
writer、应用用例和两条 Streamlit AppTest 验收路径。测试使用 deterministic fake
provider，不读取 `.env`、不调用真实 API，也不运行修改后的 Python。

第一次命令在 9 项无临时目录依赖的协议测试通过后，因上一轮已清理
`D:\ResearchMind\.pytest-tmp` 父目录，其余 14 项在 pytest fixture 建立阶段出现
`FileNotFoundError`。这次失败没有进入产品写入逻辑，也不是 T5-B1 产品缺陷。
确认临时目录仍位于仓库后重建父目录并原样重跑：

```text
.venv\Scripts\python.exe -m pytest tests\unit\test_code_change_protocol.py tests\unit\test_code_change_core.py tests\unit\test_code_change_writer.py tests\unit\test_code_change_use_cases.py tests\e2e\test_streamlit_app.py::test_t5_b1_previews_requires_confirmation_applies_and_rolls_back tests\e2e\test_streamlit_app.py::test_t5_b1_cancel_keeps_disk_unchanged_and_audits_metadata_only -q --basetemp D:\ResearchMind\.pytest-tmp\t5b1-execution-2
→ 22 passed, 1 skipped in 2.79s
```

本次复验证实：proposal 前后磁盘零变化、未勾选时应用按钮禁用、应用层再次校验
确认、相对路径 diff、恢复副本、原子应用、旧选择失效、安全回滚、取消零写入和
元数据审计均保持有效。唯一 skip 仍是当前 Windows 主机不允许创建测试 symlink。
没有启动新的本地 Streamlit 服务，因此本记录是自动交互/AppTest 证据，不新增
真实浏览器截图或人工视觉结论。
