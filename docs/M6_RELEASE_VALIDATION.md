# M6 V1 技术收尾验证

日期：2026-08-27

## 结论

M6 的代码、配置安全补口、README、全量自动化回归、依赖检查、分层扫描和
真实后端证据整理已完成。2026-08-28 的后续产品决定明确：V1 以及当前中间版本
只作为内部实现基线，不标记为 Release Candidate，也不对外发布。本文保留为
V1 技术验收历史记录。

本轮尝试使用 Windows Computer Use 捕获运行中的页面，但控制内核连续两次异常
退出，因此没有把“页面看起来正确”伪报为已验证。应用本身成功启动并返回 HTTP
200，Streamlit AppTest 也覆盖完整 UI 闭环；内部优化仍需用户在默认浏览器中
确认一次布局、复制按钮、页码控件和嵌入图像预览。

## M6 交付

- 新增根目录 `README.md`，覆盖安装、LLM Key、目标语言、Vault 路径、启动、
  隐私、备份、测试和已知局限。
- 修复架构第 20.1 节的实现缺口：`config.py` 现在支持根级 Streamlit
  secrets，并保持所有配置读取集中在该模块。
- 配置优先级固定为：进程环境变量 > Streamlit secrets > `.env` > 默认值。
- 新增 secrets 优先级与密钥 repr 脱敏回归测试。
- 三份核心文档当时从“V1 草案/待评审”同步为 V1 实现基线；后续发布状态已被
  2026-08-28 的“不发布 V1”决定取代。
- 没有新增依赖、数据库、后台服务或 V1 外能力。

## FR1–FR10 证据

| 需求 | 状态 | 主要证据 |
|------|------|----------|
| FR1 打开本地 PDF | 通过 | PDF 单测覆盖合法、缺失、非 PDF、错误魔数、损坏、超限与换文档；AppTest 覆盖打开 |
| FR2 阅读 PDF | 通过 | 页序、渲染、缩放、搜索、跳转、双栏顺序、文本块复制和嵌入位图测试；真实 5 页双栏 PDF 抽查 |
| FR3 选择文本 | 通过 | 当前页优先、跨页定位、未定位仍可用的 Core 单测与集成流 |
| FR4 翻译 | 通过 | 独立 Translation provider/service 单测；fake provider 集成与 AppTest |
| FR5 概念解释 | 通过 | 专用 prompt、ResearchContext、provider 与 UI 集成测试 |
| FR6 数学解释 | 通过 | 数学 prompt 与公式/符号任务路径测试 |
| FR7 算法解释 | 通过 | 算法 prompt 与任务路由测试 |
| FR8 论文上下文解释 | 通过 | 相邻块、元数据、预算截断、注入分隔与最小字段测试 |
| FR9 后续追问 | 通过 | 最近历史裁剪、同文档约束、集成流和 AppTest |
| FR10 Obsidian 沉淀 | 通过 | KnowledgeNote、Markdown、路径穿越、非覆盖写入、临时 Vault E2E 与真实测试 Vault smoke |

更细的阶段证据见 `M1_PDF_VALIDATION.md`、`M2_LLM_VALIDATION.md`、
`M3_CORE_FLOW_VALIDATION.md`、`M4_OBSIDIAN_VALIDATION.md`、
`M5_STREAMLIT_VALIDATION.md` 和 `M5_1_PDF_READING_VALIDATION.md`。

## 安全清单（ARCHITECTURE.md 第 20 节）

### 20.1 API Key — 通过

- `.env` 和 `.streamlit/secrets.toml` 均被 Git 忽略，模板只含占位值。
- 环境变量、dotenv 与 Streamlit secrets 只由 `config.py` 读取。
- `Settings.llm_api_key` 不进入 dataclass repr。
- LLM 异常只暴露归一化错误，不包含 Key、完整请求体或 provider 响应正文。
- 扫描未在源码、文档和待提交文件中发现非测试、非占位密钥模式。

### 20.2 用户 PDF — 通过

- 打开与重新渲染前检查 `.pdf` 扩展名、`%PDF-` 魔数、文件类型和配置大小
  上限（默认 50 MB）。
- 解析和渲染异常在 PDF 边界转换为项目异常，UI 通过统一用户错误集合显示。

### 20.3 Prompt Injection — 通过

- 解释 prompt 用 `<paper_context>` 和 `<conversation_history>` 分隔并转义
  不可信内容，系统提示明确把论文与历史视为数据而非指令。
- 翻译 prompt 使用独立的 `<source_text>` 数据边界。
- provider 参数白名单拒绝 tools、function calling、web search 和 streaming；
  V1 模型没有工具或执行能力。
- UI 把内容标记为 AI 对话，并在发起调用前明示外发范围。

### 20.4 恶意文件 — 通过（运行期边界）

- PDF 大小受限，所有 PyMuPDF 使用集中在 `pdf/reader.py` 并受异常边界保护。
- PDF 内容不会作为 Python、Shell 或 HTML 执行。
- Vault 只写 UTF-8 纯文本 Markdown。
- 本记录不是第三方依赖漏洞数据库审计；依赖更新仍是每次发布的持续维护项。

### 20.5 用户数据与 Vault — 通过

- 启动器关闭 Streamlit usage telemetry；除用户主动点击 LLM 支持的动作外，
  ResearchMind 不发送论文数据。
- 网络请求只包含选择、最小上下文、当前问题和预算内历史，不上传整份 PDF。
- Vault 根路径来自配置，子目录拒绝绝对路径和路径穿越；文件名净化，只写
  `.md`，使用 exclusive-create，永不覆盖已有文件。
- 写入失败抛出项目错误，不静默丢失。

## 最终自动化结果

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-m6-final
```

结果：`116 passed in 4.07s`。

```powershell
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pip check
```

结果：编译通过；`No broken requirements found.`

静态审查结果：

- views 没有直接 import PDF、LLM、Translation 或 Obsidian 基础设施；
- Core/Models 没有 Streamlit 或 Application 依赖；
- PyMuPDF 只在 `pdf/` 中使用；
- 显式 Streamlit session-state 写入只在 `app/state.py`；
- 配置读取只在 `config.py`；
- production 独占文件创建只在 `integration/obsidian/vault.py`；
- `.env` 处于忽略状态，`git diff --check` 通过。

## 真实链路记录

- 真实 Dots Studio provider 已使用忽略的本地配置完成最小调用，返回非空文本；
  未记录 Key 或响应正文，详见 `M2_LLM_VALIDATION.md`。
- 真实 5 页双栏课程论文已通过 production PDF 用例打开、提取并渲染，首页
  18 个块按标题/摘要/左栏/右栏/页脚顺序输出。
- 真实测试笔记已非覆盖写入用户配置的测试 Vault，详见
  `M4_OBSIDIAN_VALIDATION.md`。
- M6 再次启动 production Streamlit：`http://localhost:8501/` 返回 HTTP
  200，日志无首次 Email 输入界面；停止后端口已释放。

## 内部人工视觉复核

请在默认浏览器中执行一次不调用 LLM 的检查：

1. 启动 `scripts/run_app.py`，确认浏览器自动打开；若系统关联失效，点击终端
   中的 Local URL。
2. 打开真实双栏 PDF，确认先读完整左栏再读右栏，段落内没有逐视觉行断裂。
3. 点击上一页、下一页和页码输入，确认立即换页。
4. 使用块级复制按钮复制一整段，并确认整页复制面板可用。
5. 展开嵌入图像区域，确认预览与下载按钮存在。

完成这五项后可关闭 M6 的视觉验证缺口，但不代表版本可以对外发布。最终发布
还需要代码识别与更高阶智能化的独立产品规格、架构实现和完整验收。
