# T3 CodeContext 实现与验证

日期：2026-08-29
状态：Completed
基线：V1.3.2 + T1/T3 内部增量，不对外发布

## 用户结果

ResearchMind 现在可以只读打开用户明确指定的一个本地文件夹，索引受限规模内的
UTF-8 Python 文件，定位 import、函数、类和方法，或让用户选择明确行范围。
用户在调用模型前可以看到相对路径、起止行、符号、提取方式、选中源码、预算内
邻近源码和近似请求体量。

这不是代码 Agent：应用不 import、不执行、不测试、不安装依赖、不修改源码，
也不自动建立论文—代码关系。

## 已实现边界

| 层 | 实现 |
|---|---|
| Models | `CodeProject`、`CodeFile`、`CodeSymbol`、`CodeSelection`、`CodeContext` |
| Infrastructure | `code/reader.py` 校验路径、排除规则和 2,000 文件/20 MB/单文件 1 MB 上限；`code/python_parser.py` 只调用标准库 `ast.parse` |
| Core | 明确符号/行选择；按现有 context token budget 组装最近邻行，选择本身过大时拒绝并要求缩小 |
| Application | 打开项目、选择符号/行、预览 CodeContext、显式解释代码 |
| LLM | 独立 `<code_context>` prompt；源码按不可信数据转义；明确无工具与执行权限 |
| UI/State | 第五个 Streamlit 视图；代码状态与 PDF 对话分离并仅存在于会话内存 |

`ResearchContext` 继续只表达论文阅读证据，`CodeContext` 只表达代码证据。
T3 的应用用例一次选择一种上下文；二者的显式证据链接属于 T4。

## 隐私与失败语义

- 默认排除隐藏目录、VCS、虚拟环境、缓存、构建产物、vendor、
  `node_modules` 和已知秘密文件名；
- 只考虑 `.py`，不跟随符号链接越出用户选择的根目录；
- 非 UTF-8 文件保留相对路径和诊断，但不保留或展示源码；
- Python 语法错误不会阻断项目，可退化为带行号的纯文本选择；
- 任何文件数、总字节或单文件字节超限都会明确拒绝并要求缩小范围；
- Prompt 只包含项目名、相对路径、行号、符号、选中源码、预算内邻近源码和
  当前问题；不包含绝对根目录或整个仓库。

## 可重复证据

回归优先红灯：

```text
ModuleNotFoundError: No module named 'researchmind.code'
ImportError: cannot import name 'build_code_context'
ImportError: cannot import name 'create_code_symbol_selection'
```

聚焦验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest-tmp-t3-ui `
  tests/unit/test_code_reader.py `
  tests/unit/test_core_code_context.py `
  tests/unit/test_code_context_use_cases.py `
  tests/e2e/test_streamlit_app.py -k "code or code_workspace"
```

结果：`10 passed, 7 deselected in 2.12s`。

完整回归：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-t3-final2
```

最终复测结果：`188 passed in 9.54s`。

对仓库自身 `src/` 的只读烟雾测试：58 个 Python 文件、173,030 bytes、
620 个静态符号、0 个语法错误、0 个非 UTF-8 文件，耗时约 0.122 秒。
该数字是一次本机小样本，不是性能承诺。

## T3 退出条件映射

| 退出条件 | 证据 |
|---|---|
| CodeContext 与 ResearchContext 有正式关系 | 独立模型、独立 prompt、应用层显式选择；架构文档同步 |
| 文件/行号/符号 provenance | `CodeSelection` + UI/Prompt 单元与 AppTest |
| 只读静态解析 | 标准库 AST；sentinel 测试证明源码中的写文件语句未执行 |
| Parser 类型不进入 Core | AST 节点在 `code/` 内转换成 `CodeSymbol` dataclass |
| 失败与规模边界明确 | 合法、语法错误、非 UTF-8、排除文件和三类上限测试 |
| V1 闭环无回归 | 完整 188 项测试通过 |

## 剩余限制

- 未完成真实浏览器人工视觉验收：Streamlit 在 8511 端口正常启动，但宿主
  浏览器控制进程连续两次在连接前异常退出。该限制继续作为发布门禁记录。
- 当前只支持 Python 文本文件，不支持 Notebook、Julia、R、C/C++、跨文件
  调用图或运行时行为。
- AST 只能说明静态语法结构，不能证明函数真实运行结果。
- 在 T3 完成时，CodeContext 尚不进入 KnowledgeNote，也不与论文选择关联。

> 后续状态（2026-08-29）：T4 已增加用户确认的 `EvidenceLink`，并可随
> KnowledgeNote 导出；代码解释 Message 仍不自动进入论文 Conversation，
> ResearchContext/CodeContext prompt 仍分离，也没有自动关联。T4 验证见
> [T4_EVIDENCE_LINK_VALIDATION.md](./T4_EVIDENCE_LINK_VALIDATION.md)。
