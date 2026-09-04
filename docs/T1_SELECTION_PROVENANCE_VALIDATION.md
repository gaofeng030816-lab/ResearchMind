# T1 Selection 与 Provenance 验证

日期：2026-08-29
状态：Completed
前置基线：T0 / 174 tests

## 问题与完成口径

修改前，用户需要“复制文本块 → 粘贴选择框 → 确认选择”三步；定位成功只保留
page/block，ResearchContext 发送前预览和 KnowledgeNote 也只展示页码。公式候选
虽然可复制，但不能直接进入选择。

T1 的完成口径是：常规文本和公式候选都能一键生成 `ReadingSelection`；成功定位
保留 page/block/bbox，失败仍明确保持 locator 为空；来源进入 ResearchContext、
prompt、发送前预览、KnowledgeNote 和 Obsidian Markdown；原闭环无回归。

## 实现结果

- `core/selection.py` 新增纯函数 `select_text_block`，手动文本匹配与直接块选择共用
  page/block/bbox locator 语义；
- `app/use_cases.py` 新增 `create_block_selection`，视图不直接查找业务对象；
- 阅读器每个普通文本块提供“选择此文本块”，每个公式候选提供“选择此公式”；
- 一键选择会同步到操作面板的选中文本框，并显示 page、源 block_index 与 bbox；
- `ResearchContext` 和 `ContextEvidencePreview` 增加 block_index/bbox，prompt 只发送
  `pdf` 来源类型和数值定位，不发送本地 PDF 路径；
- `KnowledgeNote` 增加 source_type/block_index/bbox，Obsidian Markdown 在来源区
  明确写出这些字段；
- 未定位的手动文本继续可翻译、解释和转换，不伪造 bbox。

## Before / After

| 用户问题 | Before | After |
|---|---|---|
| 把候选交给 AI | 复制、粘贴、确认三步 | 文本或公式块一次点击 |
| 成功定位 | page + block | page + block + bbox |
| 发送前检查 | 页码和语义上下文 | 来源类型、页码、块、bbox 和语义上下文 |
| 知识笔记追溯 | 文档 + 页码 | 文档 + 来源类型 + 页码 + 块 + bbox |
| 定位失败 | locator 为空，仍可用 | 语义保持不变 |

## 测试证据

实现前的聚焦测试按预期在收集阶段失败：

```text
ImportError: cannot import name 'select_text_block'
```

实现后的聚焦回归：

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_core_selection.py `
  tests\unit\test_evaluation_corpus.py `
  tests\unit\test_context_preview_use_cases.py `
  tests\unit\test_llm_prompts.py `
  tests\unit\test_knowledge_use_cases.py `
  tests\unit\test_obsidian_markdown.py `
  tests\e2e\test_streamlit_app.py -q `
  --basetemp=.pytest-tmp\t1-green-2
```

结果：`38 passed in 5.86s`。

完整回归与环境检查：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest-tmp\t1-full
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pip check
```

结果：`177 passed in 7.24s`；Python 编译成功；
`No broken requirements found.`

## 限制与回滚

- bbox 是 PDF 点坐标 provenance，不等于页面图像高亮；T1 没有 PDF 编辑或标注；
- Streamlit 页面图像仍不能原生精细框选文字；直接选择单位是提取文本块；
- 错误阅读顺序或被拆散的公式仍会忠实继承当前 PyMuPDF 提取结果；
- 如需回滚，可移除 reader 按钮和新增 DTO/Note 字段；原手动
  `create_selection` 路径仍独立存在。

T1 退出条件全部满足，可以进入 T2 PDF / Mathematics Evidence Upgrade。
