# V1.3.2 选择驱动的 LaTeX 与知识沉淀验证

日期：2026-08-28

## 范围

V1.3.2 仍是内部开发版本，不对外发布。本阶段在 V1.3.1 数字文字层公式候选
基础上增加：

- 用户确认选择后，通过独立用例把数学文字转换为 LaTeX；
- 转换前构建有界 ResearchContext，并提供不调用网络的上下文证据预览；
- `llm/prompts.py` 要求模型只返回一个 `<latex>...</latex>` 表达式体；
- `llm/latex.py` 限制结果为 4000 字符，拒绝显示数学分隔符、Markdown
  围栏、嵌套输出、TeX 文档/宏/文件/链接/外部资源命令及不受支持的环境；
- 对话面板显示可复制 LaTeX 源码和 Streamlit 数学预览；
- `KnowledgeNote.latex` 和 Obsidian Markdown 保存一个或多个显示公式。

本阶段没有新增运行时依赖，没有安装或调用 TeX 编译器，没有读取图片公式、
执行 OCR、发送整篇 PDF、调用真实 API 或写入用户真实 Vault。

## 数据流

```text
ReadingSelection
→ build_research_context
→ build_latex_prompt
→ LlmProvider.complete
→ parse_latex_response
→ Message(task="convert:latex")
├─ Streamlit 可复制源码 + 数学预览
└─ capture_knowledge → KnowledgeNote.latex
   → Obsidian $$...$$
```

翻译仍是独立 Translation 路径；LaTeX 转换与解释共享 ResearchContext 约束，但
具有独立 prompt、响应协议、用例函数、UI 按钮和错误边界。

## 测试先行记录

新增测试在实现前按预期于收集阶段失败：

```text
ImportError: cannot import name 'convert_selection_to_latex'
from 'researchmind.app.use_cases'
```

实现后的聚焦测试：

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_latex_conversion.py `
  tests\unit\test_knowledge_use_cases.py `
  tests\unit\test_obsidian_markdown.py `
  tests\unit\test_llm_prompts.py -q
```

结果：`27 passed`。

跨模块与 Streamlit 测试：

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_latex_conversion.py `
  tests\unit\test_knowledge_use_cases.py `
  tests\unit\test_obsidian_markdown.py `
  tests\integration\test_research_flow.py `
  tests\e2e\test_streamlit_app.py -q
```

结果：`25 passed in 4.72s`。加固包装校验与多公式 Markdown 后的安全聚焦测试
结果为 `23 passed in 0.21s`。

全量测试：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest-tmp\v132-full
```

首次全量结果：`170 passed in 5.58s`；最终加固后复核：
`170 passed in 5.60s`。

附加检查：

```powershell
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pip check
```

结果：Python 编译退出码 0；依赖检查返回
`No broken requirements found.`。

## Skill 与规则验证

V1.3.2 实现当时，`AGENTS.md` 和四个项目技能已同步到该代码基线：

- `project-planner` 区分选择驱动 LaTeX 与 OCR/自动整页重建；
- `python-engineering` 固定 prompt、严格解析、UI 和 KnowledgeNote 所有权；
- `testing-review` 增加危险 TeX 拒绝、UI 和 Obsidian 覆盖；
- `learning-mode` 增加真实 LaTeX 数据流和“不等于原公式真值”的教学边界。

使用 skill-creator 的 `quick_validate.py` 分别校验四个技能，最终均返回
`Skill is valid!`。项目虚拟环境没有 PyYAML，因此首次执行校验器失败；未把
PyYAML 加入 ResearchMind 依赖，而是使用本机已有 PyYAML 的 Python 并启用
UTF-8 后完成校验。

> 后续治理状态（2026-08-29）：项目已新增 `pdf-research` 与
> `research-context`，形成六个职责分离的 Skills，并全部重新通过
> `quick_validate.py`。同日工作树基线重新验证为 `170 passed in 7.88s`，
> Python 编译通过且 `pip check` 无损坏依赖；T0 已开始处理人工视觉和评测集
> 缺口。该后续状态不改写上方 V1.3.2 首次实现时的历史结果。

> 最新治理状态（2026-08-29）：T0–T4 已完成；T1 加入一键选择和
> page/block/bbox provenance，T2 保留 PyMuPDF 并暂缓 OpenDataLoader-PDF 接入。
> T3 新增独立、只读 Python CodeContext；T4 新增用户确认的显式证据链接并
> 可随 KnowledgeNote 导出，但仍不改变 LaTeX/ResearchContext 与 CodeContext
> 的独立 prompt 边界；当前增量基线为 `198 passed`。

## 安全与限制

- LaTeX 是配置模型对用户选择的保守重建，不是 PDF 原始二维结构的可靠恢复；
- 扫描件、图片公式、缺字字体和被 PyMuPDF 打散的上下标仍可能无法重建；
- 结果只交给 Streamlit 数学组件和 Obsidian 显示数学，不交给 shell 或编译器；
- 当前是命令黑名单、环境白名单与大小/包装协议组合，不是通用 TeX 解释器；
- 多条已选择转换在 Markdown 中分别使用独立的 `$$...$$` 块。

## UI 验收状态

- Streamlit AppTest 已覆盖 LaTeX 按钮、会话消息、KnowledgeNote 和临时 Vault
  Markdown，不调用网络；
- 本地 Streamlit 服务已在测试端口正常启动；
- 应用内浏览器控制进程连续两次意外退出，因此本轮无法把真实窗口中的公式
  字体、窄窗口三列按钮和长公式换行记为人工视觉通过。临时服务已停止。

## 下一步建议

优先完成人工视觉补验，并给公式候选增加“一键带入选择框”和 bbox 原文位置
提示。随后建立小型公式样本集，对 LaTeX 结果记录 exact/structural match 与
人工可读性；图片公式 OCR 和自动二维重建继续作为独立架构评审。
