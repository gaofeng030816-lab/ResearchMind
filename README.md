# ResearchMind

ResearchMind 是一个本地运行的 AI 科研阅读与知识整理工作台，连接论文、数学公式、代码与笔记。
它适合需要阅读论文、理解研究代码，并把关键结论整理到 Obsidian 的学习者和研究者。

当前源码版本为 `3.0.0rc1`。这是可供本地使用和继续开发的候选版本，不是托管服务或公开软件包发布。

## 主要能力

### 论文阅读

- 从浏览器点击或拖放导入 PDF，并保存到独立的本地研究资料库；
- 使用本地 PDF.js 文字层阅读、搜索、缩放、翻页和鼠标划词；
- 改善常见双栏论文的文本顺序和复制体验；
- 对浏览器选择结果再次使用 PyMuPDF 校验页码、文字和几何位置；
- 仅在用户点击后翻译当前选择或请求 AI 解释；
- 论文单独打开时使用全宽阅读区，同时打开论文和代码时自动分栏；
- 使用 `Ctrl+Shift+A` 打开或收起 AI 面板，输入框聚焦时不会误触快捷键。

### 数学公式

- 在当前页本地检测有限的公式候选区域；
- 先预览一个受限 PNG 裁剪，再决定是否发送给已配置的视觉模型；
- 每一次公式识别都需要针对当前裁剪单独确认；
- 识别结果作为可编辑 LaTeX 候选，必须通过校验并由用户接受后才能进入笔记；
- 不上传整份 PDF，也不声称恢复原论文的 TeX 源码。

### 代码阅读

- 静态读取 Python、C、Java、Julia 和 R 项目；
- 支持 `.py`、`.c`、`.h`、`.java`、`.jl` 和 `.r` 文件；
- 显示相对路径、行范围、符号和解析来源；
- 为零基础用户提供分步阅读提示，为科研复现提供入口、依赖和问题文件线索；
- 不 import、编译或执行被读取的项目；
- 受控源码修改只适用于用户明确打开的外部 Python 项目、当前选中范围，并要求查看 diff、确认应用和确认回滚。

### 笔记与知识沉淀

- 只有用户明确选择的论文、代码、翻译或公式内容才能进入证据篮；
- 支持证据排序、移除和来源状态提示；
- Markdown 草稿可以本地保存、重新打开和编辑；
- 预览与写入 Obsidian 是两个独立动作；
- Obsidian 写入需要再次确认，并且不会覆盖同名笔记。

### 本地资料库与 Zotero

- SQLite 只保存元数据、哈希、相对路径、修订和显式来源链接；PDF 与代码不会作为数据库 blob 保存；
- 相同内容会精确去重，更新后的文件可作为新修订导入；
- 移除记录、恢复记录和删除 ResearchMind 托管副本是不同操作；
- Zotero 集成默认关闭，可选连接 Zotero Desktop Local API；
- Zotero 连接只执行用户触发的本机只读请求，不修改 Zotero 数据库、条目或附件；
- Windows 可在用户批准的附件目录内逐文件只读复制 PDF；其他情况继续使用手动上传和来源链接。

## 隐私与安全

ResearchMind 默认在本机处理 PDF、代码、资料库、草稿和笔记。只有以下操作可能访问配置的模型端点：

- 翻译当前选择；
- 解释当前论文或代码选择；
- 发送后续问题；
- 识别一个已经预览并确认的公式裁剪；
- 为当前 Python 选择生成受控修改建议。

应用不会自动上传整份 PDF、整个代码仓库、Obsidian Vault、Zotero 数据库或本地绝对路径。
发送前会显示内容范围；公式识别还会显示准确裁剪图和本次外发确认。

请勿把真实 API Key 写入源码、README、Issue、聊天记录或 Git 提交。`.env` 和
`.streamlit/secrets.toml` 已被 Git 忽略。

## 环境要求

- Python 3.12；
- Windows、macOS 或 Linux 桌面环境；
- 一个 OpenAI-compatible 文本/视觉模型端点；
- 可选：Zotero 10+；
- 可选：一个已经存在的 Obsidian Vault。

LaTeX 预览由应用直接渲染，不要求安装 TeX Live 或 MiKTeX。

## 安装

克隆仓库后，在项目根目录执行。

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install .
Copy-Item .env.example .env
```

### macOS 或 Linux

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install .
cp .env.example .env
```

需要运行测试或参与开发时，改用：

```powershell
& .\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

## 配置

复制 `.env.example` 后编辑本机 `.env`。最少需要配置模型、ResearchMind 数据目录；
Obsidian 和 Zotero 均为可选。

```dotenv
LLM_BASE_URL=https://your-openai-compatible-endpoint.example/v1
LLM_API_KEY=replace-with-your-api-key
LLM_API_KEY_HEADER=Authorization
LLM_MODEL=your-model-name

TRANSLATION_TARGET_LANGUAGE=zh-CN
RESEARCHMIND_DATA_DIR=D:\ResearchMindData

OBSIDIAN_VAULT_PATH=D:\ObsidianVault
OBSIDIAN_SUBDIRECTORY=ResearchMind

ZOTERO_LOCAL_API_ENABLED=false
ZOTERO_ATTACHMENT_ROOT=
```

配置说明：

- 标准 OpenAI Bearer 鉴权使用 `LLM_API_KEY_HEADER=Authorization`；
- Dots Studio 使用 `LLM_API_KEY_HEADER=api-key`；
- `RESEARCHMIND_DATA_DIR` 必须是独立目录，不能位于 Obsidian Vault 或待导入代码项目内；
- `OBSIDIAN_VAULT_PATH` 指向已经存在的 Vault 根目录；未配置时仍可阅读和使用 AI；
- `ZOTERO_LOCAL_API_ENABLED` 默认为 `false`；只有需要 Zotero 时才改为 `true`；
- `ZOTERO_ATTACHMENT_ROOT` 只用于 Windows 上经过批准的本地附件目录，不能填写磁盘根目录、网络路径或 UNC 路径。

也可以把同名值写入 `.streamlit/secrets.toml`。配置优先级为：进程环境变量、
Streamlit secrets、`.env`、应用默认值。

修改配置后可运行不会联网、不会显示密钥的诊断：

```powershell
& .\.venv\Scripts\python.exe -m researchmind.maintenance diagnose --env-file .env
```

## 启动

安装完成后运行：

```powershell
& .\.venv\Scripts\researchmind.exe
```

macOS 或 Linux：

```bash
./.venv/bin/researchmind
```

源码开发也可以运行：

```powershell
& .\.venv\Scripts\python.exe .\scripts\run_app.py
```

启动器会尝试打开默认浏览器。若没有自动打开，请访问终端显示的本地地址，通常为
`http://localhost:8501`。使用 `Ctrl+C` 停止服务。

## 基本使用流程

1. 配置 `RESEARCHMIND_DATA_DIR` 并启动应用；
2. 进入“本地资料库”，点击或拖放导入 PDF 或代码目录；
3. 从资料库打开论文、代码，或同时打开两者；
4. 在 PDF 中划词，或在代码视图中选择符号/行范围；
5. 查看发送范围后，再点击翻译、解释、公式识别或追问；
6. 把确实需要的内容加入证据篮；
7. 编辑 Markdown 草稿并生成预览；
8. 如已配置 Obsidian，确认后将当前预览保存到 Vault。

所有重要动作都需要点击确认。选择内容不会自动进入笔记，本地保存草稿也不会自动写入 Obsidian。

## Zotero 使用说明

1. 在 Zotero Desktop 中启用 Local API；
2. 在 `.env` 中设置 `ZOTERO_LOCAL_API_ENABLED=true`；
3. 启动 ResearchMind，在资料库页面点击读取 Zotero；
4. 选择个人资料库条目并链接到已经导入的论文；
5. 如需 Windows 直接复制附件，先把 `ZOTERO_ATTACHMENT_ROOT` 设置为所选 PDF 所在的批准附件目录，再逐次确认复制。

ResearchMind 不读取 Zotero SQLite 文件，不写入 Zotero，也不会后台同步整个资料库。
Local API 说明见 [Zotero 官方文档](https://www.zotero.org/support/dev/web_api/v3/local_api)。

## 数据与备份

资料库目录通常包含：

```text
RESEARCHMIND_DATA_DIR/
├── researchmind.sqlite3
├── assets/
└── .staging/
```

资料库备份：

```powershell
& .\.venv\Scripts\python.exe -m researchmind.maintenance library-backup `
  --env-file .env `
  --output "D:\Backups\researchmind-library.zip"
```

恢复必须写入一个尚不存在的新目录：

```powershell
& .\.venv\Scripts\python.exe -m researchmind.maintenance library-restore `
  --archive "D:\Backups\researchmind-library.zip" `
  --data-dir "D:\ResearchMindRecovered" `
  --env-file .env
```

只备份 ResearchMind 写入的 Obsidian Markdown：

```powershell
& .\.venv\Scripts\python.exe -m researchmind.maintenance backup `
  --env-file .env `
  --output "D:\Backups\researchmind-notes.zip"
```

这些备份不包含 API Key。整个 Obsidian Vault 仍应使用你原有的备份或同步方案。

## 已知限制

- 复杂多栏、图文混排或扫描版 PDF 的文字顺序和复制效果可能不完整；
- 当前没有整页 OCR、整篇 PDF 转 LaTeX、表格语义识别或图表理解；
- 公式识别结果是需要人工核对的候选，不是原始 TeX 真值；
- 代码阅读是静态分析，不解析完整依赖图，不编译、不运行测试，也不保证科研结果可复现；
- C、Java、Julia 和 R 只读；受控修改仅支持外部 Python 项目的当前选择；
- Zotero 仅支持可选、只读、个人资料库工作流，不支持写入、组资料库同步或 Web API 凭据；
- 当前没有多人协作、云同步、移动端或后台自主 Agent。

## 开发与验证

```powershell
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-local
& .\.venv\Scripts\python.exe -m pip check
```

自动测试使用 fake/mock provider，不读取用户资料，也不会调用付费 API。

开发者可继续阅读：

- [系统架构](docs/ARCHITECTURE.md)
- [产品规格](docs/PRODUCT_SPEC.md)
- [第三方声明](THIRD_PARTY_NOTICES.md)

## 致谢

ResearchMind 的 PDF 与公式能力在设计和评估阶段参考了以下优秀开源项目：

- [LaTeX_OCR_PRO](https://github.com/LinXueyuanStdio/LaTeX_OCR_PRO)：感谢其对公式图像识别、数据构建、序列建模和评估流程的公开实践；
- [OpenDataLoader PDF](https://github.com/opendataloader-project/opendataloader-pdf)：感谢其对 PDF 阅读顺序、版面几何、文本块、图像、表格和文档解析边界的启发。

ResearchMind 没有复制或捆绑上述两个项目的源码、模型权重、Java 包或二进制文件；
相关成果被用作研究、设计与对照参考。运行时依赖和许可证信息见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 发布与许可证说明

当前仓库提供 V3 候选源码，但尚未创建公开软件包 Release，也没有声明稳定公共 API。
项目没有在当前树中授予单独的开源许可证；第三方组件仍受各自许可证约束。
特别是 PyMuPDF 采用 AGPL-3.0/商业许可双重模式，在重新分发、闭源部署或商业使用前，
请自行评估并选择符合要求的许可路线。本说明不构成法律意见。
