# V1.3 上下文证据可见性验证

日期：2026-08-28

## 范围

本轮继续优化内部 V1.x，不对外发布。目标是让用户在 AI 解释或追问发生前检查
ResearchMind 将使用的论文证据和近似请求体量，降低上下文误关联与数据外发的
不透明性。

实现内容：

- `app/use_cases.py` 新增只读 `ContextEvidencePreview`；
- `preview_explanation_context` 和 `preview_followup_context` 与真实调用
  共享 ResearchContext 和 prompt builder；
- 预览包含文档、作者、页码、章节、邻近图表说明、当前问题、选中文本、周边
  文本、预算内历史消息数量；
- 请求字符数来自真实待发送 `ChatMessage.content`，token 数按
  4 字符/token 向上取整；
- `app/views/context_evidence.py` 统一展示解释与追问预览；
- 翻译界面明确说明翻译只发送选中文本和目标语言，不使用 ResearchContext；
- 预览不创建 LLM provider、不发网络、不写 session state。

没有新增依赖，没有改变 Streamlit、单进程、内存会话、Obsidian 持久化、
provider 接口或 V1 数据边界。

## 回归过程

实现前新增测试在收集阶段失败：

```text
ImportError: cannot import name 'preview_explanation_context'
```

实现后的聚焦测试：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/unit/test_context_preview_use_cases.py tests/integration/test_research_flow.py tests/e2e/test_streamlit_app.py -q --tb=short --basetemp .pytest-tmp\v13-focus-20260828-b
```

结果：`9 passed in 4.44s`。

全量验证：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp .pytest-tmp\v13-full-20260828-a
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pip check
```

结果：

- `135 passed in 5.31s`；
- Python 编译通过；
- `No broken requirements found.`

测试使用生成 PDF、FakeLlmProvider 和临时目录。没有依赖本地 `.env`，没有
调用真实 LLM，也没有写入用户的真实 Obsidian Vault。

## 人工视觉复核

本地 Streamlit 服务已在 `http://localhost:8513` 成功启动，但内置浏览器控制
进程连续两次因 Windows 沙箱初始化错误退出，未能完成页面截图与人工布局检查；
临时服务随后已停止。该项不计为通过，当前 UI 证据来自 Streamlit AppTest。

## 已知限制

- token 数是确定性工程估算，不是具体模型 tokenizer 的精确结果或费用承诺；
- UI 展示预算内历史消息数量，但历史正文仍在上方对话区查看；
- 展开区的实际长文本滚动与不同窗口宽度布局仍需人工浏览器复核；
- 预览展示的是 ResearchMind 发送的请求内容，不代表模型一定正确使用这些证据；
- V1.2 的章节/图表说明仍来自规则分类，可能漏识别或误关联；
- 复杂公式、语义表格、图表理解、OCR 和代码识别仍未实现。

## 下一步

下一次内部修改命名为 **V1.3.1 上下文质量评测与纠错**，不使用 V1.4。
V1.3.1 优先补齐人工视觉验收和真实论文关联评测，再根据失败样本修正规则。
