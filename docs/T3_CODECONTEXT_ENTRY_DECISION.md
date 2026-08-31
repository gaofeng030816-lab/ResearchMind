# T3 CodeContext 进入决策

日期：2026-08-29
状态：Approved and completed
前置门禁：T0–T2 Completed

## 为什么需要具体确认

用户已批准按门禁推进到 V2，但 CodeContext 会新增代码内容源、领域模型和模块边界。
代码从哪里读取、先支持什么语言、多少文件可进入内存、哪些内容可发送给外部模型，
都会直接改变隐私与架构。顶层批准不等于自动选择这些参数。

T3 只建立只读、可追溯、不可执行的代码上下文。它不执行用户代码或模型代码，
不写代码文件，不安装 VS Code 扩展，不新增数据库，也不授权 T5 工具型助手。

## 推荐的最小方案

| 决策项 | 推荐值 | 理由 |
|---|---|---|
| 代码来源 | 用户显式选择的一个本地文件夹 | 最符合当前本地产品；无需 IDE/云连接 |
| 首批语言 | Python `.py` | 与 ResearchMind 自身和用户当前学习方向一致；标准库 `ast` 可只读解析 |
| 规模上限 | 最多 2,000 个候选文件、20 MB 源码、单文件 1 MB | 防止 Streamlit 卡死和无界 prompt；超限时明确拒绝/缩小范围 |
| 默认排除 | `.git`、虚拟环境、缓存、构建产物、隐藏目录、vendor/node_modules、二进制和秘密文件 | 降低噪声、泄密与资源消耗 |
| 解析方式 | 标准库 `ast`；语法错误时只提供带行号的纯文本，不执行 import | 无新依赖、无代码执行、错误语义可控 |
| provenance | 项目标识、相对路径、起止行、符号类型/名称、提取方式 | 能从 AI 解释回到真实代码位置 |
| 与 ResearchContext 的关系 | 独立 `CodeContext`；应用用例按任务显式组合，不把二者合成无界“万能上下文” | 保持论文证据与代码证据来源清楚 |
| UI | 继续使用 Streamlit：文件夹路径、文件/符号列表、源码预览和显式选择 | 先验证工作流，不提前重写 UI |
| 持久化 | 无；会话内存 | T3 尚无跨会话必要性，不引入 SQLite |
| 外部模型传输 | 默认不发送整个项目；只发送用户选择的代码、最小邻近代码、相对路径/行号和当前问题，发送前预览 | 延续 ResearchContext 的最小披露原则 |

## 建议模型与模块边界

批准后再把以下内容写入正式架构并实现：

- `models/code_selection.py`：用户选择的相对路径、行号与源码；
- `models/code_context.py`：选择、邻近代码、符号、项目元数据、问题与预算；
- `code/reader.py`：只读目录校验、排除规则、大小限制和 UTF-8/可解释文本读取；
- `code/python_parser.py`：把 `ast` 转成 ResearchMind 自有符号模型；
- `core/code_context.py`：纯函数组装有界上下文；
- `app/use_cases.py`：唯一的代码打开、选择、预览与解释应用 API；
- `app/state.py`：唯一的 Streamlit 代码会话状态写入点；
- `app/views/`：只展示和委托事件。

第三方 AST/CST/IDE 类型不得泄漏到 Core、UI 或 Markdown。初始实现不需要新依赖。

## T3 成功标准

1. 在包含合法、语法错误、超大、非 UTF-8 和被排除文件的夹具项目上行为明确；
2. Python 函数、类、方法和 import 可定位到相对路径与行号；
3. 用户可显式选择一个符号/行区间，并在发送前看到 CodeContext 证据与体量；
4. 没有 import、subprocess、eval、exec 或测试运行路径；
5. 自动化不读取 `.env`、密钥、虚拟环境或用户真实私有仓库；
6. 现有 PDF → ResearchContext → KnowledgeNote → Obsidian 闭环无回归。

## 需要用户确认的句子

若接受上述推荐值，请明确回复：

> 同意 T3 推荐方案：本地单文件夹、Python-first、2,000 文件/20 MB、Streamlit、
> 会话内存、只读 AST、最小上下文外发、禁止执行和写代码。

若任一项不同，请指出代码来源、语言、规模或隐私/UI 选择。确认后 T3 才能从
`Proposed` 变为 `Active`。

## 最终决定

用户于 2026-08-29 明确回复上述推荐句，全部推荐值获批。实现和验证证据见
[T3_CODECONTEXT_VALIDATION.md](./T3_CODECONTEXT_VALIDATION.md)。T3 已完成，
该确认不授权 T4 自动生成证据链接，也不授权 T5 的代码写入或执行工具。
