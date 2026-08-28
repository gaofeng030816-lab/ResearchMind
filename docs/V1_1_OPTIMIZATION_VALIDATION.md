# V1.1 PDF 响应与可提取性优化验证

日期：2026-08-28

## 范围

本轮继续优化 V1 内部基线，不进行任何公开发布，也不提前实现代码识别、OCR、
数据库、Agent 工具或跨论文 RAG。

实现内容：

- `pdf/reader.py` 为页面 PNG 和嵌入图像 PNG 增加最多 32 项的进程内 LRU
  缓存；
- 缓存键包含解析后的绝对路径、文件大小、修改时间、创建/元数据变更时间、
  文件标识、页码、缩放和图像 bbox；
- 每次公开渲染调用仍检查扩展名、PDF 魔数、文件类型和大小上限；
- 源文件发生变化时缓存失效；已缓存页面对应的源文件变为损坏文件时仍抛出
  项目错误；
- `app/use_cases.py` 新增 `DocumentTextCoverage` 和
  `get_document_text_coverage`；
- 有文本页面比例不超过 10% 时，阅读器明确提示扫描版/图像型 PDF 与 V1 无
  OCR 的限制，并允许用户继续查看页面图像或手动输入文本。

没有新增依赖，模块边界保持不变。

## 基线与真实样本

优化前：

- 真实 5 页数字版双栏论文：首次打开约 1.79 秒；同进程再次打开约
  0.09–0.10 秒；同页重复生成 `PageView` 约 0.044 秒；
- 真实 802 页数字版 PDF：全文提取 802/802 页、13,139 个文本块，耗时约
  6.22 秒。该结果暂不支持立即进行高风险的分页懒加载重构；
- 真实 442 页低文本覆盖 PDF：仅 1 页有可提取文本，覆盖率 0.23%。

优化后在同一 5 页真实论文上：

- 首次页面视图约 0.036 秒；
- 同文件修订、同页、同缩放的缓存页面约 0.0016 秒；
- 本次样本约 23.2 倍加速，PNG 输出一致。

这些数字是本机单次工程基线，不作为跨设备性能承诺。

## 回归过程

实现前先观察到：

- 重复页面渲染测试失败：两次调用底层 `pymupdf.open`，预期一次；
- 文本覆盖诊断测试因用例不存在而在收集阶段失败。

实现后的受影响测试：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/unit/test_pdf_reader.py tests/unit/test_document_use_cases.py tests/e2e/test_streamlit_app.py -q --basetemp=.pytest-tmp-v11-focused-final
```

结果：`31 passed in 4.22s`。

全量验证：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-v11-final
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pip check
```

结果：

- `122 passed in 4.64s`；
- Python 编译通过；
- `No broken requirements found.`

## 已知限制

- 文件修订键避免正常的源文件替换命中旧缓存，但不是内容加密哈希；
- 缓存只优化重复渲染，不改变 PDF 首次文本提取策略；
- 文本覆盖率只是透明诊断，不等同于扫描件分类模型；
- V1 仍不执行 OCR、公式结构识别、语义表格或图表理解；
- Streamlit 页面最终视觉效果仍需要人工浏览器检查。
