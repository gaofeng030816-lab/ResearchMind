# V1.2 ResearchContext 结构线索优化验证

日期：2026-08-28

## 范围

本轮继续优化 V1 内部基线，不对外发布。目标是在不发送整篇 PDF、不引入
RAG、数据库、OCR 或新运行时依赖的前提下，让解释和追问获得少量、可追溯的
论文结构线索。

实现内容：

- `TextBlock` 增加 `body / heading / caption` 角色，默认保持 `body`；
- `pdf/layout.py` 以确定性规则识别常见中英文编号章节标题、标准章节名和
  Figure / Fig. / Table / 图 / 表说明；
- `core/research_context.py` 从所选块向前寻找最近章节标题，并只在同页前后
  2 个文本块内关联最近图表说明；
- 标题最多 160 字符，图表说明最多 500 字符；选择无法定位到文本块时两个
  字段均为空；
- `llm/prompts.py` 将结构线索作为已转义字段放入现有
  `<paper_context>` 不可信数据边界；
- PDF、Core、LLM Prompt 和跨模块研究流均新增回归测试。

本轮没有增加依赖，没有改变 Streamlit、单进程、内存会话、Obsidian 持久化或
provider 接口等既定架构。

## 回归过程

实现前新增测试首先在收集阶段失败：

```text
ImportError: cannot import name 'classify_block_role'
```

这证明回归测试依赖的是尚未存在的新行为。实现后的聚焦测试：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/unit/test_pdf_reader.py tests/unit/test_core_research_context.py tests/unit/test_llm_prompts.py tests/integration/test_research_flow.py -q --tb=short --basetemp .pytest-tmp\v12-focus-20260828-b
```

结果：`49 passed in 0.71s`。

Streamlit 冒烟测试：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/e2e/test_streamlit_app.py -q --tb=short --basetemp .pytest-tmp\v12-streamlit-20260828-a
```

结果：`4 passed in 3.74s`。

全量验证：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp .pytest-tmp\v12-full-20260828-a
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pip check
```

结果：

- `132 passed in 4.71s`；
- Python 编译通过；
- `No broken requirements found.`

测试没有读取本地 `.env` 的真实密钥，没有调用真实 LLM，也没有写入用户的
真实 Obsidian Vault。

## 已知限制

- 角色识别依赖文本模式，不使用字号、字体或完整目录树，因此非标准标题可能
  漏识别，编号列表也可能被误认为标题；
- 图表说明关联使用文本块距离，不代表已经理解图表内容，也不处理跨页图表；
- 扫描版 PDF 没有文字层时仍无法获得这些线索；V1.x 不实现 OCR；
- 新字段提供的是解释证据，不自动在 UI 中展示，用户暂时无法在调用前检查它们；
- 复杂混排、公式、语义表格、矢量图表和代码识别仍属于后续独立工作。
