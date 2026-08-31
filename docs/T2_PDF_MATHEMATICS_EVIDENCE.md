# T2 PDF / Mathematics Evidence Upgrade

日期：2026-08-29
状态：Completed
生产决定：保留 PyMuPDF；OpenDataLoader-PDF 暂缓接入

## 技术问题

T2 回答两个问题：现有 PyMuPDF 轻量边界在哪些科研 PDF 上足够；
OpenDataLoader-PDF 是否已具备在 Windows 单进程 ResearchMind 中直接替换或补充
现有解析器的证据。

本阶段只在 `experiments/pdf_parser_spike/` 增加语料、脚本和结果，不修改
`src/researchmind/pdf/`，不安装依赖，不调用网络或真实 LLM。

## 同语料基准

语料以文件名和 SHA-256 固化，不提交论文或用户绝对路径：

| 样本 | 类别 | 当前结果 |
|---|---|---|
| 2408.02509v1 | 双栏、公式、图 | 14/14 页有文本；426 块；16 公式候选；12 图注；0 嵌入位图区域 |
| Tidy Data | 双栏、表格 | 24/24 页有文本；1463 块；20 图注；1 位图区域；无语义表格模型 |
| 《统计学习方法》 | 公式、图、中文 | 208/209 页有文本；16 公式候选；53 图注；587 位图区域 |
| chinese_scan | 扫描件、中文 | 0/1 页有文本；0 文本块；1 位图区域；确认无 OCR |
| PDF/UA Invoice | 表格 | 1/1 页有文本；18 块且全部为 body；确认没有表格结构 |

这些数字是确定性输出计数，不是 precision/recall。尤其 587 个位图区域可能包含
小图元或页面资源，不能宣称理解了 587 张科研图表。

单次 Windows 本地烟测中，数字 PDF 的全文件解析约为
`0.0056–0.0166 s/page`；209 页中文样本为 `1.175064 s`。扫描件虽然解析快，
但没有文本，因此速度不能掩盖能力缺失。`peak_python_bytes` 只覆盖 Python 跟踪
内存，不含 PyMuPDF 原生分配。关键匿名化统计见
`experiments/pdf_parser_spike/current_results_2026-08-29.json`。

## OpenDataLoader-PDF 隔离 Spike

只读检查了用户课程资料中的本地源码树。可确认：

- 开源核心为 Apache-2.0；源码包 Changelog 标注 0.1.0，但 Python 项目文件使用
  构建占位版本 0.0.0，且目录不是 Git checkout，无法记录 commit；
- Python 包本质是 Java CLI 包装；`runner.py` 调用 `java -jar`，要求 Java 11+；
- 源码树没有已构建 JAR；本机 `java`、`mvn`、`uv`、`bash` 和
  `opendataloader-pdf` 命令均不存在，只有 `wsl.exe`；
- 从源码构建需要 Maven 解析 PDFBox、Jackson、veraPDF 等依赖；本机当前不能做
  无网络、零安装构建，因此没有伪造 OpenDataLoader 本地质量或性能结果；
- 快速本地模式承诺 reading order、bbox、简单边框表格和结构化 JSON；这些能力
  与 ResearchMind 的候选需求相符，但本机尚未实测；
- OCR、复杂/无边框表格、公式 LaTeX 和图表描述属于 hybrid 路径，Python 可选依赖
  包含 `docling[easyocr]`、FastAPI、Uvicorn、python-multipart，并启动第二个本地
  服务。这会显著扩大安装、模型下载、内存、进程与维护面；
- 快速模式在运行时可本地处理，但源码构建需要下载 Maven 依赖；hybrid 的模型
  安装/首次运行也可能需要外部下载。无论哪种模式，论文内容是否离开本机都必须
  由实际部署配置和网络检查验证，不能只根据产品说明推断。

OpenDataLoader 自带的 benchmark 脚本还会 clone 外部 benchmark 仓库并运行
`uv sync`，不适合作为当前 ResearchMind 的离线例行测试。其 README 给出的速度和
精度是上游声明，不是本机同语料结果。

## 采用 / 拒绝 / 推迟结论

1. **保留（采用当前生产基线）**：继续使用 PyMuPDF 负责验证、页面渲染、数字文字
   层、bbox、轻量阅读顺序、公式候选和嵌入位图区域。它足以支撑当前选择驱动闭环。
2. **明确拒绝当前直接替换**：不把 OpenDataLoader JSON、Java 类型、JAR、混合
   服务或 Docling 对象直接引入 Core/UI，也不在 T2 修改生产 PDF 边界。
3. **推迟候选集成**：当 OCR 或语义表格/公式成为经样本量化的优先需求，并且用户
   接受 Java/模型/第二进程安装成本时，再建立可运行环境，用同一语料做真实
   PyMuPDF vs OpenDataLoader 输出对照。

若未来采用，转换只能发生在 `pdf/` 基础设施边界：vendor 元素先转换成
ResearchMind 自有 `Document` / `Page` / `TextBlock` / `FigureRegion` 或经批准的
新模型；坐标系、页码基准、阅读顺序、角色置信度、OCR/模型生成来源和错误语义都
必须显式转换。vendor JSON 不能成为 Core、UI 或 Obsidian 契约。

## 验证证据

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_pdf_spike_manifest.py -q `
  --basetemp=.pytest-tmp\t2-manifest
```

结果：`1 passed in 0.05s`。

五份真实论文基准由 `benchmark_current.py` 运行，所有 SHA-256 均匹配。完整回归：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest-tmp\t2-full
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts experiments
& .\.venv\Scripts\python.exe -m pip check
```

结果：`178 passed in 6.88s`；Python 编译成功；
`No broken requirements found.`

## T2 退出结论

- 双栏、公式、表格、图、扫描件都有同一清单下的可重复当前基准；
- OpenDataLoader 候选的 Windows 运行阻塞、能力、依赖、隐私、性能证据边界、
  许可证、维护和集成成本均已记录；
- 决策明确为当前不接入、保留 PyMuPDF、条件满足后再评估；
- 没有 vendor 类型泄漏或生产依赖变化。

T2 完成。T3 CodeContext 的进入条件尚需具体确认代码来源、语言、规模、隐私、UI
和成功标准；本记录不替代该架构选择。
