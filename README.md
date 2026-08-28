# ResearchMind

> 当前为内部开发基线，不作为公开发布版本。现阶段持续优化 PDF 阅读、上下文
> 理解和知识沉淀；代码识别与更高阶智能化将在后续独立版本中设计。

ResearchMind 是一个本地运行的 AI 科研阅读与知识沉淀工作台。它负责打开
PDF、提取和选择文本、翻译、结合论文上下文进行 AI 解释与追问，并把理解整理
为可追溯的 Markdown 笔记写入 Obsidian Vault。

它连接的是 Zotero → ResearchMind → Obsidian 工作流：Zotero 继续管理文献，
Obsidian 继续管理长期知识，ResearchMind 专注于“读懂论文并沉淀理解”。V1
不包含文献库、数据库、OCR、PDF 编辑、知识图谱或 Zotero 集成。

## V1 能力

- 打开本地数字版 PDF，浏览、翻页、按页跳转、缩放和全文搜索；
- 按阅读顺序显示可复制文本块，并改善常见双栏论文的段落顺序；
- 对高置信度章节标题和相邻图表说明做轻量识别，为 AI 解释补充局部结构线索；
- 预览和下载 PDF 中可检测到的嵌入位图区域；
- 定位复制或手动输入的文本；
- 独立执行翻译，以及概念、数学、算法和上下文解释；
- 在 AI 解释或追问前预览将发送的页码、章节、图表说明、周边文本和请求估算；
- 围绕当前论文和选择进行会话内追问；
- 预览并以非覆盖方式保存可追溯 Markdown 到 Obsidian Vault。

## 环境要求

- Python 3.12；
- Windows、macOS 或 Linux 的本地桌面环境；
- 一个 OpenAI 兼容的文本生成端点，或本地兼容端点；
- 如需知识沉淀，一个已经存在的 Obsidian Vault 目录。

## 安装

在项目根目录执行。Windows PowerShell：

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[test]"
Copy-Item .env.example .env
```

macOS 或 Linux：

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e '.[test]'
cp .env.example .env
```

`[test]` 会同时安装 pytest；只使用应用时可将安装命令改为
`pip install -e .`。

## 配置

编辑本地 `.env`。不要把真实 API Key 写入 README、源码、错误报告或 Git
提交。

```dotenv
LLM_BASE_URL=https://note3-prev-api.askdiandian.com/v1
LLM_API_KEY=replace-with-your-api-key
LLM_API_KEY_HEADER=api-key
LLM_MODEL=dots3-note-prev

TRANSLATION_TARGET_LANGUAGE=zh-CN

OBSIDIAN_VAULT_PATH=D:\ObsidianVault
OBSIDIAN_SUBDIRECTORY=ResearchMind

CONTEXT_TOKEN_BUDGET=6000
HISTORY_TOKEN_BUDGET=3000
PDF_MAX_SIZE_MB=50
```

- Dots Studio 使用 `LLM_API_KEY_HEADER=api-key`；使用标准 OpenAI Bearer
  鉴权的端点则设置为 `Authorization`。
- `OBSIDIAN_VAULT_PATH` 必须指向已经存在的 Vault 根目录。应用会在其中
  创建 `OBSIDIAN_SUBDIRECTORY`，而不是把该子目录当作 Vault 根目录。
- Vault 不是必需配置：未配置时仍可阅读和调用 AI，但不能保存笔记。
- 翻译与 AI 解释复用同一个兼容端点，但在产品和代码中是两个独立动作。

也可以把同名配置写在本机的 `.streamlit/secrets.toml` 中，例如：

```toml
LLM_BASE_URL = "https://note3-prev-api.askdiandian.com/v1"
LLM_API_KEY = "replace-with-your-api-key"
LLM_API_KEY_HEADER = "api-key"
LLM_MODEL = "dots3-note-prev"
TRANSLATION_TARGET_LANGUAGE = "zh-CN"
OBSIDIAN_VAULT_PATH = "D:\\ObsidianVault"
OBSIDIAN_SUBDIRECTORY = "ResearchMind"
```

`.env` 与 `.streamlit/secrets.toml` 都已被 Git 忽略。配置优先级从高到低
为：进程环境变量、Streamlit secrets、`.env`、安全默认值。

## 启动

Windows PowerShell：

```powershell
& .\.venv\Scripts\python.exe .\scripts\run_app.py
```

macOS 或 Linux：

```bash
./.venv/bin/python ./scripts/run_app.py
```

启动器会请求系统默认浏览器打开 ResearchMind，不显示 Streamlit 的首次 Email
收集界面，并关闭 Streamlit 使用统计。如果浏览器没有自动打开，点击终端中的
`http://localhost:8501`；在传统 PowerShell 主机中也可以复制该地址到浏览器。
按 `Ctrl+C` 停止本地服务。

## 使用流程

1. 在“PDF 阅读”中输入本地 PDF 路径并打开；
2. 翻页、搜索或调整缩放，从按阅读顺序排列的文本块中复制段落；
3. 把段落粘贴到“选中文本”，确认选择后翻译或选择一种 AI 解释模式；
4. 展开“上下文证据（发送前预览）”，检查本次 AI 调用会使用的论文证据；
5. 在“研究对话”中继续追问，并可在发送前检查追问上下文；
6. 点击“沉淀为知识”，选择对话内容，补充自己的理解与标签；
7. 预览 Markdown 后保存到配置的 Vault。

只有点击“翻译”“AI 解释”或“发送追问”时才会调用配置的网络端点。每次调用
只发送当前选择、最小必要论文上下文（含受限的章节标题/相邻图表说明）、当前
问题和预算内的最近历史；PDF 文件本身不会整体上传。需要完全本地处理时，可
配置 Ollama 等 OpenAI 兼容本地端点。打开上下文预览不会发起网络请求；请求
体量使用 4 字符/token 的近似值，实际计费以服务商为准。

## 数据与备份

- PDF 保留在原位置；ResearchMind 不维护论文副本或文献数据库。
- 打开的论文和对话只存在于当前 Streamlit 会话，刷新或停止应用后不会恢复。
- 长期数据是 Vault 中的 Markdown。请把整个 Obsidian Vault 纳入你现有的备份
  或同步方案，并在升级前确认备份可恢复。
- `.env` 或 `secrets.toml` 应单独安全保管，不要放入 Vault、云端公开仓库或
  普通聊天记录；API Key 泄露时应在服务商处撤销并更换。
- 应用不会覆盖同名笔记；发生冲突时会追加序号。

## 测试

```powershell
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-local
& .\.venv\Scripts\python.exe -m pip check
```

自动测试使用 fake 或 mock provider，不调用真实 API，也不会产生模型费用。

## 已知局限

- 文本顺序优化面向常见数字版双栏论文，复杂混排仍可能需要人工调整；
- 只识别嵌入位图区域，不识别纯矢量图、表格语义、公式结构或图表含义；
- 扫描版 PDF 没有 OCR，因此可能没有可复制文本；
- 会话不跨应用重启持久化；
- 自动打开页面依赖操作系统存在有效的默认 HTTP 浏览器关联。

架构边界、产品规格和里程碑验收分别见
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、
[docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) 和
[docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)。
