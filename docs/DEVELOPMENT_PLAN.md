# ResearchMind V1–V1.3.2 内部开发记录

同步日期：2026-08-30 · 状态：M0–M6 与 V1.1–V1.3.2 已完成；过渡基线已推进至 T5-B1 / T6-C · 配套：[PRODUCT_SPEC.md](./PRODUCT_SPEC.md) · [ARCHITECTURE.md](./ARCHITECTURE.md) · [V1→V2 过渡门禁](../V1%20to%20V2过渡要求.md)

## 0. 计划原则

1. **里程碑式推进**：每个里程碑（M）结束时项目可运行、测试全绿，不积压半成品。
2. **自底向上**：先基础设施（PDF、LLM/翻译、Obsidian 写入），再核心逻辑，最后 UI——每一步都建立在已测的代码之上。
3. **每个里程碑含测试任务**：遵循 testing-review skill 的验证循环，DoD（完成定义）以真实测试结果为准。
4. **编码遵循 python-engineering skill**；每个里程碑完成后按 learning-mode skill 输出学习总结。

## 当前执行状态（2026-08-30）

本文保留为 V1 与 V1.3.2 的历史里程碑、依赖理由和验收记录，不再作为当前
待办清单。当前产品基线为 V1.3.2 + T1/T3/T4/T5-A/T5-B1/
T6-A/T6-B/T6-C；T5-B1 已完成一个已选 Python 行范围的受控替换、确认、
恢复副本、哈希冲突保护和安全回滚，仍不允许 Shell、测试执行或依赖安装。
T6-C 自动证据已通过，真实浏览器部分由用户于 2026-08-30 明确人工确认通过；
该确认不等同于自动浏览器截图证据。未来阶段不能回写成 M0–M6 的未完成工作，
也不能把 Proposed 能力描述为当前实现。

## 1. 里程碑总览

| 里程碑 | 内容 | 交付物 | 预估规模 |
|--------|------|--------|----------|
| M0 | 项目骨架 | 目录结构、依赖、配置、pytest 可跑 | 小 |
| M1 | PDF 基础设施 | pdf/reader.py + search.py + 错误处理 + fixture PDF 测试 | 中 |
| M2 | LLM 模块 | Provider 接口 + OpenAI 兼容实现 + 五个解释 prompt + 追问 prompt + mock 测试 | 中 |
| M3 | 翻译、核心逻辑与用例 | translation/ + core/ 纯函数 + use_cases 用例函数 + 集成测试 | 中 |
| M4 | 知识沉淀与 Obsidian 集成 | integration/obsidian/（Vault 写入 + Markdown 渲染）+ 全链路测试 | 中 |
| M5 | Streamlit UI | 4 个视图 + 状态管理 + AppTest 冒烟 | 大 |
| M6 | 收尾 | 安全清单、README、手动验收、全量回归 | 小 |
| V1.3.2 | 选择驱动的 LaTeX | 严格 LLM 输出解析、数学预览、KnowledgeNote/Obsidian 公式 | 中 |

> 注：V1 **没有数据库里程碑**——对话在会话内存活，知识以 Markdown 写入 Obsidian Vault（判断依据见 ARCHITECTURE.md 3.3）。

## 2. 里程碑详情

### M0 项目骨架

- **目标**：仓库可安装、可测试、密钥机制就位。
- **任务**：
  1. 按 ARCHITECTURE.md 第 18 节创建目录结构（src-layout）；
  2. `pyproject.toml`（Python 3.12）+ venv 安装依赖；
  3. `.gitignore`（.env、__pycache__ 等）、`.env.example`（LLM 端点/key/模型名、翻译目标语言、Obsidian Vault 路径）；
  4. `config.py`：读 .env（LLM 端点/key/模型名、目标语言、Vault 路径、上下文/历史预算、PDF 大小上限）；
  5. models/ 的 8 个 dataclass 初版（Document / Page / TextBlock / ReadingSelection / ResearchContext / Conversation / Message / KnowledgeNote）；
  6. pytest + conftest.py 骨架。
- **测试**：`pytest` 空跑通过；config 的密钥读取单测（伪造 env）。
- **DoD**：`pip install -e .` 成功；`pytest` 可执行；`git init` + 首次提交。

### M1 PDF 基础设施

- **目标**：能打开 PDF 并提取元数据/页面文本/文本块，能渲染页面图像（含缩放），能搜索文本。
- **任务**：
  1. `pdf/reader.py`：open（元数据）、extract_page（文本+blocks）、render_page_image（倍率缩放）；
  2. `pdf/search.py`：文档内文本搜索（返回页码 + 文本块摘录）；
  3. `pdf/errors.py`：PdfExtractionError 等；异常边界；
  4. `tests/fixtures/`：用 PyMuPDF 生成 fixture PDF（单页/多页/Unicode/数学符号/空白页/损坏文件）。
- **测试**：testing-review skill 中 PDF 模块全部用例（正常、多页、损坏、不存在路径、空白页、Unicode、数学、页码顺序、搜索命中）。
- **DoD**：全部 PDF 测试真实通过；用一篇**真实论文** PDF 手动验证提取质量（记录已知局限）——这是 V1 最大技术风险的首次探测。

### M2 LLM 模块

- **目标**：任意 provider 可插拔；解释类 prompt 构建可测。
- **任务**：
  1. `llm/base.py`（Protocol + ChatMessage）、`llm/errors.py`；
  2. `llm/prompts.py`：concept / math / algorithm / contextual / followup 五个 build 函数（接收 ResearchContext，含注入防御声明，见 ARCHITECTURE.md 20.3）；
  3. `llm/providers/openai_compatible.py`（超时、重试、错误映射）；`llm/factory.py`；
  4. （可选）`llm/providers/anthropic.py`。
- **测试**：mock provider 下验证每个任务的 messages 结构与注入防御；错误映射（超时/空响应/畸形响应→项目异常）。**绝不调真实 API**。
- **DoD**：LLM 测试全绿；用真实 API Key 手动跑一次解释（唯一允许的真实调用，结果如实记录）。

### M3 翻译、核心逻辑与用例

- **目标**：完整的"业务流"在无 UI 情况下可运行、可测试。
- **任务**：
  1. `translation/base.py`（TranslationProvider 协议）、`translation/errors.py`、`translation/service.py`、`translation/providers/llm_translation.py`（基于 LlmProvider 的 V1 唯一实现，prompt 内聚在 provider 内）；
  2. `core/selection.py`：locate_selection（当前页→全文档→降级不绑定）；
  3. `core/research_context.py`：build_research_context（相邻块、预算截断、整页回退）；
  4. `core/conversation.py`：对话历史裁剪（纯函数）；
  5. `app/use_cases.py`：ARCHITECTURE.md 第 15 节全部 9 个用例函数；
  6. conftest 中实现 FakeLlmProvider。
- **测试**：unit（三个纯函数的规则表全覆盖；翻译 provider 的 prompt 与错误映射）；integration（打开→选择→翻译→解释→追问的完整流，fake provider + fixture PDF）。
- **DoD**：集成测试全绿；可在无 UI 的 Python 脚本中完成一次完整闭环（Vault 写入部分见 M4）。

### M4 知识沉淀与 Obsidian 集成

- **目标**：KnowledgeNote → 结构化 Markdown → 写入 Vault 全链路可测。
- **任务**：
  1. `integration/obsidian/markdown.py`：KnowledgeNote → 结构化 Markdown（来源/原文/翻译/问答/我的理解/标签/时间）；
  2. `integration/obsidian/vault.py`：Vault 路径校验、子目录写入、文件名净化、防覆盖；
  3. `use_cases` 的 capture_knowledge / save_note_to_vault 落地；
  4. conftest 提供临时 Vault 目录 fixture。
- **测试**：unit（Markdown 渲染内容、文件名净化、防覆盖、路径校验）；integration（沉淀→写入临时 Vault→读回校验的完整流）。
- **DoD**：全部测试通过；临时 Vault 中生成的 .md 可被 Obsidian 正常打开（人工抽查一次）。

### M5 Streamlit UI

- **目标**：四视图上线，闭环可用。
- **任务**：
  1. `app/state.py`（会话状态集中管理）；
  2. 四个视图（reader / actions / conversation / knowledge）+ `app/app.py` 组装；
  3. 视图只调 use_cases；
  4. 错误展示（打开失败、LLM 失败、未定位提示、Vault 未配置）。
- **测试**：AppTest 冒烟（打开→翻页→选择→按钮→对话→知识面板→保存到临时 Vault）；手动验收清单（真实 PDF + 真实 API 一次）。
- **DoD**：冒烟测试通过；手动验收清单全部打勾；检查确认 UI 无一处直接 import pdf/llm/translation/integration。

### M5.1 PDF 阅读质量回访

- **目标**：根据真实双栏论文的人工验收，改善阅读顺序、段落复制和嵌入图表访问。
- **任务**：
  1. `pdf/layout.py`：基于 bbox 空白切分的常见双栏阅读顺序和视觉断行整理；
  2. `Page.figures` + PDF reader：轻量检测嵌入位图区域，按需裁剪 PNG；
  3. reader view：逐文本块复制、整页复制、图表预览和下载；
  4. launcher：自动打开默认浏览器，同时关闭 Email 提示与 Streamlit 遥测。
- **依赖决定**：审查 OpenDataLoader PDF 后不引入其 Java/JAR、Docling、OCR 或混合服务；继续只使用既有 PyMuPDF。
- **测试**：双栏/断词/图表 fixture 单测、Streamlit AppTest、真实双栏论文顺序抽查、全量回归。
- **DoD**：测试通过；真实双栏首页按左栏后右栏排列；明确记录矢量图表、扫描件和复杂混排限制。

### M6 收尾

- **目标**：闭环交付。
- **状态**：V1 技术收尾已完成；根据 2026-08-28 的产品决定，本版本仅作
  内部实现基线，不作为 Release Candidate。人工视觉复核状态见
  [M6_RELEASE_VALIDATION.md](./M6_RELEASE_VALIDATION.md)。
- **任务**：
  1. 安全清单逐项核对（ARCHITECTURE.md 第 20 节）；
  2. README（安装、配置 LLM Key/目标语言/Vault 路径、启动与备份提示）；
  3. 全量测试回归；`git diff` 复核。
- **测试**：全量回归。
- **DoD**：全量测试真实通过；安全清单通过；按 learning-mode skill 输出 V1 学习总结。

### V1.3.2 选择驱动的 LaTeX

- **状态**：已完成；V1.3.2 首次基线为 170 tests。T0–T2 增量基线为
  178 tests；完成 T3 后为 188 tests，完成 T4 后最新基线为 198 tests。
  人工视觉环境阻塞继续在 T0/T3
  记录中如实保留。
- **目标**：把 V1.3.1 公式文字层阅读接入 Paper ↔ Mathematics ↔ Notes 闭环，
  同时保持选择驱动、上下文有界和结果可追溯。
- **任务**：
  1. `llm/prompts.py` 增加 ResearchContext-grounded LaTeX prompt；
  2. `llm/latex.py` 严格解析单个表达式，拒绝 TeX 文档、宏、文件/链接和
     外部资源能力；
  3. `app/use_cases.py` 增加转换和无网络上下文预览；
  4. 对话同时展示可复制源码与 Streamlit 数学预览；
  5. `KnowledgeNote` 和 Obsidian Markdown 保存可选显示公式。
- **依赖决定**：复用 Streamlit 与现有 LLM provider，不新增运行时依赖，不
  安装或调用 TeX 编译器，不实现图片公式 OCR。
- **测试**：prompt/解析安全单测、fake provider 用例测试、完整研究流、
  Streamlit AppTest、Obsidian Markdown 和全量回归。
- **DoD**：验证记录见
  [V1_3_2_LATEX_VALIDATION.md](./V1_3_2_LATEX_VALIDATION.md)。

## 3. 依赖清单（每个都需理由）

| 依赖 | 用途 | 为什么需要 |
|------|------|-----------|
| streamlit | UI | V1 界面唯一框架（选型见 ARCHITECTURE.md 3.4） |
| PyMuPDF | PDF | 唯一同时提供文本+坐标+页面渲染的库（第 9.4 节） |
| openai | LLM | OpenAI 兼容协议客户端，同时覆盖 DeepSeek/通义/Kimi/Ollama 等；V1 翻译复用同一 provider（LlmTranslationProvider），不新增依赖 |
| python-dotenv | 配置 | .env 读取（密钥不入代码） |
| pytest | 测试 | 标准测试框架 |
| （可选）anthropic | LLM | 第二个 provider，需要时再加 |

## 4. V1 内部验收标准

1. PRODUCT_SPEC.md 中 FR1–FR10 全部通过验收（有真实测试/手动记录支撑）；
2. `pytest` 全量通过（unit + integration + e2e）；
3. 安全清单 20.1–20.5 逐项通过；
4. 真实 PDF + 真实 LLM 的手动验收记录存在；
5. 代码分层检查通过：UI 不直接碰 pdf/llm/translation/integration；Domain 不 import UI；
6. README 能让另一个初/中级开发者装好、配好 Key 与 Vault、跑起来。

这些标准证明 V1 闭环可用，不代表允许公开发布。V1.x 已完成优化记录见
[POST_V1_DEVELOPMENT_PLAN.md](./POST_V1_DEVELOPMENT_PLAN.md)；当前 T0–T6
状态与最终发布门禁见 [V1→V2 过渡要求](../V1%20to%20V2过渡要求.md)。
