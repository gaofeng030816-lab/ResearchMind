# T5-A 只读研究助手实现与验证

日期：2026-08-29
状态：Completed
基线：V1.3.2 + T1/T3/T4/T5-A 内部增量，不对外发布

## 1. 问题、批准与范围

T4 已能保存用户确认的论文—代码证据链接，但普通解释仍是一次固定上下文调用。
用户已明确批准
[T5_AGENT_TOOLS_ENTRY_DECISION.md](./T5_AGENT_TOOLS_ENTRY_DECISION.md)
中的 T5-A：模型可以在一个当前会话内逐步请求三个无参数只读来源，每次新的
网络调用必须由用户点击开始或继续。

实现严格限制为：

- `inspect_paper_context`：重新构建当前选择的有界 `ResearchContext`；
- `inspect_code_context`：重新构建当前选择的有界 `CodeContext`；
- `inspect_evidence_links`：读取当前会话链接及双方 locator/片段；
- 最多 3 次工具调用、4 次 LLM 调用；
- 每个工具结果最多 16,000 字符，总工具结果最多 32,000 字符；
- 最终回答只保存在独立会话状态，不进入 Conversation、KnowledgeNote、Vault
  或源码。

没有新增依赖、数据库、服务、后台 worker、原生 provider tool calling、shell、
任意路径读取、代码执行/修改、测试运行、依赖安装、Git、网络搜索或 Vault 写入
工具。

## 2. Before / After

| 维度 | T4 | T5-A |
|---|---|---|
| 模型调用 | 用户点击后一次回答 | 用户每次点击触发恰好一次模型决策 |
| 证据获取 | 每个用例预先确定一个上下文 | 模型只能从三个固定只读来源选择下一步 |
| 工具结果 | 无工具步骤 | 先在 UI 完整预览，用户继续后才外发 |
| 权限 | 无工具权限 | 仅当前会话、无参数、只读白名单 |
| 循环控制 | 不适用 | 重复工具、非法协议、预算或错误立即停止 |
| 审计 | 普通错误展示 | 会话内记录动作、工具、状态、字符数、时间和停止原因 |

## 3. 模块与数据流

- `models/read_only_assistant.py`：动作、工具结果、审计事件和会话 dataclass；
- `core/read_only_assistant.py`：纯会话状态转换与调用/字符预算；
- `llm/read_only_assistant.py`：严格
  `<assistant_action>{...}</assistant_action>` 解析；
- `llm/prompts.py`：白名单、权限声明以及不可信问题/工具结果转义；
- `app/use_cases.py`：每步一次 provider 调用、固定 `if/elif` 工具调度和
  ResearchContext/CodeContext/EvidenceLink 序列化；
- `app/state.py`：唯一会话状态写入口；来源、选择、对话或链接变化时使助手
  会话失效；
- `app/views/read_only_assistant.py`：工具可用性、待发送结果、继续/停止、
  元数据审计与最终回答。

实际数据流：

```text
用户问题 + 点击开始
→ 严格动作 prompt → LlmProvider
→ final，或三个白名单工具之一
→ 本地固定只读用例重新构建有界证据
→ UI 展示待发送结果与审计元数据
→ 用户点击继续
→ 上一步结果作为不可信数据转义后发送
→ 最多四次模型调用，最终回答或可审计停止
```

每一步只使用当前内存对象。代码工具只输出项目名、相对路径、行/符号和有界
源码，不输出绝对根目录；论文工具不发送整个 PDF；审计不保存完整 payload。

## 4. 安全与停止行为

- 动作解析器要求完整单一 wrapper 和精确 JSON 字段；工具不接受参数；
- 未知工具、shell、路径参数、额外字段、多个动作、空 final 和协议外文本均拒绝；
- prompt 对用户问题和工具结果做 HTML 转义，并声明它们是数据而不是指令；
- 工具调度不使用动态 import、反射、`eval`、`exec` 或模型生成 callable；
- 同一工具不得重复；调用预算在 provider/tool 边界前后分别检查；
- provider 失败、工具来源不一致、非法协议、预算耗尽和用户停止都会记录
  非敏感审计事件并终止；
- 打开新 PDF/代码项目、改变选择、对话或链接时清空当前助手会话；
- 已有 Conversation、KnowledgeNote、EvidenceLink、Vault 和代码不被助手修改。

## 5. Regression-first 证据

实现前先加入协议、用例和 Streamlit 测试。首次聚焦运行按预期在收集阶段失败：

- `researchmind.llm` 尚无 `build_read_only_assistant_prompt`；
- `researchmind.app.use_cases` 尚无 `continue_read_only_assistant`。

实现和预算/失败补测后的聚焦命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_read_only_assistant_core.py `
  tests/unit/test_read_only_assistant_protocol.py `
  tests/unit/test_read_only_assistant_use_cases.py `
  tests/e2e/test_streamlit_app.py `
  -q --basetemp=.pytest-tmp-t5-ui-final
```

结果：`31 passed in 7.51s`。

## 6. T5 退出条件映射

| 退出条件 | 实现与测试证据 |
|---|---|
| 默认最小权限、读写/执行分离 | 三个无参数只读工具；无写入/执行工具 |
| 每次继续可见、可取消、可审计 | 待发送结果预览；开始/继续/停止按钮；会话内元数据审计 |
| 提示注入与越权 | 工具结果转义；shell/参数/多动作/额外字段拒绝测试 |
| 资源消耗可预测停止 | 3 工具、4 LLM、单项/总字符硬上限与纯 Core 测试 |
| provider/tool 错误恢复 | provider_error、tool_error、user_stopped 回归 |
| 没有模型自动授权路径 | 每次网络调用只发生于一次明确用户点击 |

## 7. 最终验证

- 聚焦 T5-A：`31 passed in 7.51s`；
- 全量 pytest：`220 passed in 8.59s`；
- `python -m compileall -q src tests scripts experiments`：退出码 0；
- `python -m pip check`：`No broken requirements found.`；
- 六个项目 Skills：官方 `quick_validate.py` 全部通过（使用已有 PyYAML 环境的
  UTF-8 模式，未给项目安装依赖）；
- `git diff --check`：无空白错误（仅现有 Windows LF/CRLF 转换警告）；
- 未调用真实付费 API，自动化全部使用 fake provider；
- 未完成新的人工视觉检查；它继续作为 T6 发布门禁，不伪报通过。

## 8. 遗留限制与下一门禁

- 会话刷新后不恢复，不能在后台继续；
- 只支持当前论文选择、当前 Python 代码选择和当前链接，不搜索新来源；
- 严格文本协议不是 provider 原生 function calling，但其更小且不新增依赖；
- 自动化证明权限/状态行为，不证明真实模型回答质量或费用表现；
- T5-A 不授权 T5-B 写入/执行工具。

下一步是 T6 架构定型与发布加固。开始实现前应先形成并确认 T6 进入决策：
最终产品范围、是否继续 Streamlit、是否需要跨会话持久化、安装/升级/备份、
隐私与安全门禁、性能指标、人工视觉场景和发布候选版本号。未确认前不重写 UI、
不引入数据库，也不增加工具权限。
