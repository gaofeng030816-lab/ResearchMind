# ResearchMind

> 当前产品实现为已通过 V2 内部验收的 `2.0.0rc1` 本地基线，不作为公开发布版本。
> T6-C 自动门禁已通过，用户也已明确确认人工门禁通过；早期浏览器控制故障仍
> 保留在验证记录中。T5-B1 只开放当前 Python 选择的单范围受控替换，不开放执行。
> T6-D 已完成本地内部候选封口；不会上传包、创建公开 Release 或对外发布。
> 用户于 2026-09-01 确认 V2 验收通过，并已在独立对话给出 V3 要求。
> V3-G0/G1 已完成；V3-G2 已实现可选 Zotero Local API 元数据/来源链接，
> 直接附件导入待本地文件读取门禁，真实 Zotero desktop 人工验收未完成。页面划词、自动公式、持久笔记草稿和
> 多语言解析尚未进入生产。

ResearchMind 是一个本地运行的 AI 科研阅读与知识沉淀工作台。它负责打开
PDF、提取和选择文本、翻译、结合论文上下文进行 AI 解释与追问，并把理解整理
为可追溯的 Markdown 笔记写入 Obsidian Vault。

它连接的是 Zotero → ResearchMind → Obsidian 工作流：Zotero 继续管理文献，
Obsidian 继续管理长期知识，ResearchMind 专注于“读懂论文并沉淀理解”。已验收
2.0.0rc1 保持独立；V3-G1/G2 在其上增加工作资料库和可选 Zotero 来源，但仍不
包含 OCR、PDF 编辑、Zotero 写入/同步或其余 V3 能力。

## 当前能力（V2 Accepted + V3-G1/G2）

- 在“本地资料库”中点击/拖放上传 PDF 或 Python 目录，使用独立数据目录保存
  托管副本和 SQLite 元数据，应用重启后可列出并重新打开；
- 对相同内容精确去重；可为既有记录显式导入新修订，不静默覆盖；
- 资料库移除/恢复与“另行确认删除托管副本”分开；不会删除外部文件或 Vault；
- Zotero 默认关闭；显式启用后可按按钮读取个人资料库、选择一个条目/PDF 附件，
  为已上传论文建立来源链接；unlink 不删除任一侧文件。直接附件导入暂不可用；
- 可生成带 manifest/SHA-256 的资料库备份，并验证后恢复到全新的数据目录；
- 打开本地数字版 PDF，浏览、翻页、按页跳转、缩放和全文搜索；
- 按阅读顺序显示可复制文本块，并改善常见双栏论文的段落顺序；
- 对高置信度章节标题、相邻图表说明和数字文字层公式候选做轻量识别，为 AI 解释补充局部结构线索；
- 标记疑似数学公式文字块、保留可用换行并支持逐块复制；
- 普通文本块和公式候选可一键成为当前选择，并保留 page/block/bbox 来源；
- 把用户确认的数学文字层选择转换为受限 LaTeX，显示可复制源码和本地数学预览；
- 预览和下载 PDF 中可检测到的嵌入位图区域；
- 定位复制或手动输入的文本；
- 独立执行翻译，以及概念、数学、算法和上下文解释；
- 在 AI 解释或追问前预览将发送的来源类型、页码、文本块、bbox、章节、图表说明、邻近公式、周边文本和请求估算；
- 围绕当前论文和选择进行会话内追问；
- 预览并以非覆盖方式保存可追溯 Markdown 到 Obsidian Vault。
- 只读打开一个本地代码文件夹，在 2,000 文件/20 MB/单文件 1 MB 上限内
  索引 UTF-8 Python；
- 使用标准库 AST 定位 import、函数、类和方法，也可显式选择行范围；
- 无需先打开 PDF，即可直接进入“代码学习与复现”工作区；初学模式给出分步
  阅读引导，复现模式给出入口、import、候选第三方依赖和问题文件等静态线索；
- 在发送前预览相对路径、行号、符号、选中代码、预算内邻近代码和请求体量，
  再显式请求 AI 解释；不会 import 或执行源码。
- 对当前 `CodeSelection` 可生成一个严格、仅预览的 Python 行范围替换建议；
  检查相对路径 unified diff 后逐次确认应用/回滚，写前创建
  `.researchmind-recovery/` 副本并使用 SHA-256 冲突保护；
- T5-B1 不提供 Shell、测试、安装、Git、任意路径、多文件或后台修改权限；
- 把一个已定位的论文/数学/算法选择与一个代码符号或行范围显式关联；链接只在
  用户确认后产生，并显示双方来源、关系、置信度和“用户确认”生成方式；
- 把当前会话中的证据链接随 KnowledgeNote 写入 Obsidian Markdown；不建立链接
  数据库，不自动合并论文和代码提示词。
- 在独立代码工作区把当前代码选择、相对路径、行号、符号、当前问题、可用的
  AI 解释和自己的理解预览为代码专用 Markdown，并显式保存到 Obsidian；
  不依赖 PDF，不记录绝对项目路径，也不修改源码。

## 环境要求

- Python 3.12；
- Windows、macOS 或 Linux 的本地桌面环境；
- 一个 OpenAI 兼容的文本生成端点，或本地兼容端点；
- 如需知识沉淀，一个已经存在的 Obsidian Vault 目录。

LaTeX 公式预览使用 Streamlit 内置渲染，Obsidian 笔记使用显示数学 Markdown；
不需要安装 TeX Live、MiKTeX 或单独的 LaTeX 编译器。

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

面向发布验证时应另建空虚拟环境并使用非 editable 安装：

```powershell
py -3.12 -m venv .venv-clean
& .\.venv-clean\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-clean\Scripts\python.exe -m pip install .
& .\.venv-clean\Scripts\python.exe -m pip check
& .\.venv-clean\Scripts\researchmind.exe
```

如果安装在 `setuptools` 等构建依赖处报告“找不到可用版本”，先检查本机 pip
镜像配置：

```powershell
& .\.venv-clean\Scripts\python.exe -m pip config list -v
```

确认是失效或不同步的镜像后，可临时指定一个可用索引，例如
`--index-url https://pypi.org/simple`。不要通过关闭依赖校验或删除版本约束来
掩盖镜像问题。

## 配置

编辑本地 `.env`。不要把真实 API Key 写入 README、源码、错误报告或 Git
提交。

```dotenv
LLM_BASE_URL=https://note3-prev-api.askdiandian.com/v1
LLM_API_KEY=replace-with-your-api-key
LLM_API_KEY_HEADER=api-key
LLM_MODEL=dots3-note-prev

TRANSLATION_TARGET_LANGUAGE=zh-CN

RESEARCHMIND_DATA_DIR=D:\ResearchMindData
ZOTERO_LOCAL_API_ENABLED=false

OBSIDIAN_VAULT_PATH=D:\ObsidianVault
OBSIDIAN_SUBDIRECTORY=ResearchMind

CONTEXT_TOKEN_BUDGET=6000
HISTORY_TOKEN_BUDGET=3000
PDF_MAX_SIZE_MB=50
```

- Dots Studio 使用 `LLM_API_KEY_HEADER=api-key`；使用标准 OpenAI Bearer
  鉴权的端点则设置为 `Authorization`。
- `RESEARCHMIND_DATA_DIR` 必须是专门给 ResearchMind 的数据根目录，不能位于
  Vault 内，也不能复用要导入/修改的代码项目目录。首次资料库操作会在其下创建
  `researchmind.sqlite3`、`assets/` 和暂存目录。
- `ZOTERO_LOCAL_API_ENABLED` 默认 `false`。只有你已在 Zotero desktop 中启用
  Local API 并需要连接时才设为 `true`；ResearchMind 仍只在资料库按钮点击后读取。
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
RESEARCHMIND_DATA_DIR = "D:\\ResearchMindData"
ZOTERO_LOCAL_API_ENABLED = false
OBSIDIAN_VAULT_PATH = "D:\\ObsidianVault"
OBSIDIAN_SUBDIRECTORY = "ResearchMind"
```

`.env` 与 `.streamlit/secrets.toml` 都已被 Git 忽略。配置优先级从高到低
为：进程环境变量、Streamlit secrets、`.env`、安全默认值。

首次启动或修改配置后，可运行本地诊断：

```powershell
& .\.venv\Scripts\python.exe -m researchmind.maintenance diagnose --env-file .env
```

也可添加 `--json` 生成机器可读结果。诊断只检查 Python、配置格式、LLM 地址、
凭据、Vault、资料库配置状态和资源限制；不会联网、不会显示 API Key/私有绝对
数据目录，也不会创建 Vault/资料库目录。应用顶部“启动与配置检查”提供同一检查。

## 启动

安装 wheel 或非 editable 包后，直接运行包内启动命令：

```powershell
& .\.venv\Scripts\researchmind.exe
```

在源码仓库开发时，也可继续使用兼容启动器：

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

1. 配置 `RESEARCHMIND_DATA_DIR`，进入“本地资料库”；
2. 通过 PDF 上传框选择/拖放一份 PDF，或通过目录上传框选择一个 Python 目录；
   如需 Zotero，另行显式启用 Local API，点击读取后选择条目/附件并链接已有论文；
3. 从资料库列表点击“打开”，进入既有 PDF 或代码工作区；
4. 翻页、搜索或调整缩放，从按阅读顺序排列的文本/公式块一键选择内容；
5. 也可复制或手动输入文字并确认；随后翻译、转换为 LaTeX 或选择 AI 解释模式；
6. 展开“上下文证据（发送前预览）”，检查本次 AI 调用会使用的论文证据；
7. 在“研究对话”中继续追问，再显式整理、预览 Markdown 并保存到 Vault。

V2 的本地路径打开入口仍保留，便于只读临时阅读而不导入资料库。浏览器上传不会
提供可信原始 OS 路径，因此 G1 会复制验证后的内容到 ResearchMind 数据目录。

代码上下文、证据链接与受控修改流程：

1. 切换到“代码学习与复现”并输入一个本地文件夹；
2. 选择 Python 文件，再选择 AST 符号或明确的起止行；
3. 检查源码和发送前 CodeContext 预览；
4. 点击“AI 解释代码”后，才发送选中代码和最小邻近代码。
5. 如需独立沉淀代码理解，展开“可选：保存为 Obsidian 代码笔记”，补充标题、
   自己的理解和标签，先预览 Markdown，再明确点击保存；
6. 如已打开 PDF 并有可靠页码选择，可填写论文证据类型、关系、置信度与可选
   判断依据，再点击“确认建立证据链接”；
7. 生成论文知识笔记时，当前会话链接会作为可追溯 Markdown 一并导出。
8. 如需修改当前选择，展开“受控单文件修改（T5-B1）”，输入要求并点击
   “生成修改建议（不写盘）”；
9. 检查 diff、字符数、改变行数和语法状态；只有勾选确认并点击应用才会写盘；
10. 应用后界面显示恢复副本的相对位置；回滚需再次勾选确认。若文件已被外部
   编辑，SHA-256 保护会拒绝覆盖。

T4 链接不会调用模型，也不会把整个仓库发给模型或自动关联当前论文。
`ResearchContext` 与 `CodeContext` 仍是两条独立的 LLM 请求路径。

只有点击“翻译”“转换为 LaTeX”“AI 解释”“发送追问”或“生成修改建议”时才会调用配置的网络端点。每次调用
只发送当前选择、最小必要论文上下文（含受限的章节标题/相邻图表说明/邻近公式候选）、当前
问题和预算内的最近历史；PDF 文件本身不会整体上传。需要完全本地处理时，可
配置 Ollama 等 OpenAI 兼容本地端点。打开上下文预览不会发起网络请求；请求
体量使用 4 字符/token 的近似值，实际计费以服务商为准。

## 数据与备份

Zotero 兼容性说明（2026-09-04）：当前身份校验要求 Zotero 10+ 提供的
`Zotero-Server-ID`，缺失时提示错误。官方附件接口返回 `302 file://`，因此直接
导入暂被禁用，待确认安全本地读取方案；可先点击上传 PDF 再链接来源。依据见
[官方 Local API 文档](https://www.zotero.org/support/dev/web_api/v3/local_api)。

- 经 G1 点击导入的 PDF/Python 目录复制到 `RESEARCHMIND_DATA_DIR/assets/`；
  `researchmind.sqlite3` 保存记录、哈希、相对路径、修订和显式 Zotero 来源快照，
  不保存文件 blob、Zotero 凭据或全库缓存。
- V2 本地路径入口仍只读原文件，不自动复制或登记。浏览器上传不声称保留原始
  OS 路径。
- 资料库记录和托管资产跨重启保留；当前打开页、对话、选择、解释、证据链接和
  笔记预览仍只存在于当前 Streamlit 会话。
- G1 托管代码修订不可由 T5-B1 修改；需要修改时使用另行管理的外部本地项目，
  避免托管资产与数据库哈希静默不一致。
- T5-B1 proposal 与审计只在当前会话；已确认修改会写回一个原文件，并在项目内
  `.researchmind-recovery/` 保留不覆盖的原始 bytes。恢复副本不会进入隐藏目录
  已排除的代码索引，也不属于 Obsidian 备份。
- 证据链接只有随 KnowledgeNote 导出的 Markdown 才成为长期结果；G1 SQLite
  不保存链接、对话或草稿。

资料库与 Obsidian 是两类独立数据，应分别备份。G1 资料库 ZIP 包含一致 SQLite
快照、托管 assets 和 checksummed manifest，不含 `.env`、Vault 或暂存内容：

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
& .\.venv\Scripts\python.exe -m researchmind.maintenance library-backup --env-file .env --output "D:\Backups\researchmind-library-$stamp.zip"
```

恢复会先验证路径、数量/体量、manifest、逐文件 SHA-256 和数据库 schema，只能
写入尚不存在且不与当前数据目录/Vault 重叠的新目录。恢复成功后，人工把
`RESEARCHMIND_DATA_DIR` 更新为该目录再启动应用：

```powershell
& .\.venv\Scripts\python.exe -m researchmind.maintenance library-restore --archive "D:\Backups\researchmind-library-20260901-120000.zip" --data-dir "D:\ResearchMindRecovered" --env-file .env
```

整个 Obsidian Vault 的既有备份/同步仍是长期知识的主备份方案。T6-B 另外提供
只包含 ResearchMind 子目录中 `.md` 和校验清单的便携 ZIP：

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
& .\.venv\Scripts\python.exe -m researchmind.maintenance backup --env-file .env --output "D:\Backups\researchmind-$stamp.zip"
```

恢复前会验证归档路径、文件数/体量、清单和 SHA-256；目标子目录必须尚不存在，
因此不会覆盖现有笔记：

```powershell
& .\.venv\Scripts\python.exe -m researchmind.maintenance restore --archive "D:\Backups\researchmind-20260830-120000.zip" --vault "D:\ObsidianVault" --subdirectory "ResearchMind-Recovered"
```

- Vault 定向 ZIP 不包含 `.env`、`secrets.toml`、PDF、代码、图片或其他 Vault 内容；
  密钥配置必须单独安全保管。
- `.env` 或 `secrets.toml` 应单独安全保管，不要放入 Vault、云端公开仓库或
  普通聊天记录；API Key 泄露时应在服务商处撤销并更换。
- 应用不会覆盖同名笔记；发生冲突时会追加序号。

## 升级与回滚

当前是已验收 V2 基线加 G1/G2 source increment（G2 附件导入和人工验收未完成）；它不是公开发布，也不承诺稳定
公共 API。升级前：

1. 记录当前 Git commit 或保存当前 wheel/source 工件；
2. 运行配置诊断；
3. 分别生成 G1 资料库 ZIP、ResearchMind Markdown ZIP，并备份整个 Vault；
4. 在独立虚拟环境安装新工件，运行 `pip check`、诊断和启动检查；
5. 验证完成前保留旧环境和旧工件。

回滚时重新安装已保存的旧 wheel/source 工件，不要删除或改写 Vault：

```powershell
& .\.venv\Scripts\python.exe -m pip install --force-reinstall "D:\Releases\researchmind-previous-py3-none-any.whl"
```

代码回滚不会自动降级或删除 G1 数据库。保留原数据目录和资料库 ZIP；只有兼容
版本才应继续打开该目录。需要恢复时始终恢复到新目录，再切换配置，不就地覆盖。
Vault 恢复仍写入新子目录并由用户人工比较后合并。

## 测试

```powershell
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-local
& .\.venv\Scripts\python.exe -m pip check
```

自动测试使用 fake 或 mock provider，不调用真实 API，也不会产生模型费用。

## 已知局限

- 文本顺序优化面向常见数字版双栏论文，复杂混排仍可能需要人工调整；
- 公式候选与 LaTeX 转换依赖数字版 PDF 已有文字层；转换结果由 LLM 保守重建，
  必须对照页面图像，不保证等价于原始二维公式；
- 不做图片公式 OCR、自动整页公式重建或通用 TeX 文档编译；模型生成的 LaTeX
  经过受限命令校验，只用于 Streamlit 预览和 Obsidian 显示数学；
- 自动公式区域识别、图片公式 OCR 和整页 PDF→LaTeX 已明确移至 post-V2/V3
  候选范围，不属于 `2.0.0rc1` 的验收缺口；
- 只识别嵌入位图区域，不识别纯矢量图、表格语义或图表含义；
- 扫描版 PDF 没有 OCR，因此可能没有可复制文本；
- 资料库记录/资产跨重启，但会话、对话、选择、证据链接和笔记草稿尚不持久化；
- 代码目录点击导入在 G1 只接受符合边界的 UTF-8 Python 文件；托管修订只读；
- Streamlit 自动测试不能真实操作浏览器文件选择器；服务端上传边界和 AppTest
  导航已覆盖，点击/拖放仍需真实浏览器人工验收；
- 自动打开页面依赖操作系统存在有效的默认 HTTP 浏览器关联。
- T3 仅支持 UTF-8 Python；语法错误文件可按行选择，非 UTF-8 文件只显示诊断；
  不支持 Jupyter、Julia、R、IDE 插件、跨文件语义分析或代码执行。
- T4 只创建用户确认的显式链接，不自动发现论文—代码对应关系，不删除或编辑
  已建链接，也不把链接作为联合论文/代码 prompt 发送给模型。
- T5-B1 只保证目标、语法、体量、恢复与冲突安全，不运行代码或测试，因此不证明
  修改逻辑正确或科研结果可复现；当前 Windows 测试主机无法创建 symlink，动态
  symlink 拒绝用例在该主机跳过，生产边界仍显式拒绝 symlink。

当前实现、产品规格、历史里程碑、V1.x 优化记录和 V1→V2 阶段门禁分别见
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、
[docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md)、
[docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)、
[docs/POST_V1_DEVELOPMENT_PLAN.md](docs/POST_V1_DEVELOPMENT_PLAN.md)、
[docs/V2_ACCEPTANCE_PREPARATION.md](docs/V2_ACCEPTANCE_PREPARATION.md)、
[V2 to V3过渡要求.md](./V2%20to%20V3过渡要求.md) 和
[V1 to V2过渡要求.md](./V1%20to%20V2过渡要求.md)。T3/T4 实现证据见
[docs/T3_CODECONTEXT_VALIDATION.md](docs/T3_CODECONTEXT_VALIDATION.md) 和
[docs/T4_EVIDENCE_LINK_VALIDATION.md](docs/T4_EVIDENCE_LINK_VALIDATION.md)。
V3-G1/G2、T5-B1/T6-C 证据见
[docs/V3_G1_LOCAL_LIBRARY_VALIDATION.md](docs/V3_G1_LOCAL_LIBRARY_VALIDATION.md)、
[docs/V3_G2_ZOTERO_VALIDATION.md](docs/V3_G2_ZOTERO_VALIDATION.md)、
[docs/T5_B1_CONTROLLED_CODE_WRITE_VALIDATION.md](docs/T5_B1_CONTROLLED_CODE_WRITE_VALIDATION.md) 和
[docs/T6_C_PRIVACY_SECURITY_PERFORMANCE_VALIDATION.md](docs/T6_C_PRIVACY_SECURITY_PERFORMANCE_VALIDATION.md)。
