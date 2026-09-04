# T0 基线封口与评测准备验证

日期：2026-08-29
状态：Completed
基线：ResearchMind V1.3.2 内部版本

## 目标与范围

T0 将 V1.3.2 从只有自动化回归的实现，收口为限制清楚、可复核且可供后续
Before/After 比较的基线。本阶段没有新增产品能力、运行时依赖、真实 API 调用或
真实 Vault 写入。

## 可复现评估语料

新增 `evaluations/v1_baseline/corpus.json`，覆盖三类最小真实样本：

- Selection：Tidy Data 英文段落与《统计学习方法》中文段落，记录页码、文本块、
  bbox、文件名和 SHA-256；
- ResearchContext：《统计学习方法》的章节/图注关联，以及 2408.02509v1 的邻近
  公式候选；
- Formula/LaTeX：Neural ODE 已验证提取片段和 2408.02509v1 的 `pass@k` 候选，
  只验证安全包装和结构片段，不调用模型。

语料不复制论文，不保存用户绝对路径。原 PDF 不存在时仍可离线运行确定性规则；
合法持有同一文件的开发者可用哈希确认来源。

## 人工视觉检查

本地 Streamlit 服务已成功启动于 `http://localhost:8510`，说明应用可进入真实
服务启动阶段。之后按浏览器控制 Skill 尝试应用内浏览器两次，控制进程均意外
退出；再按 Windows Computer Use 指南尝试桌面控制，运行时同样意外退出。

因此本次结果记录为：

| 检查项 | 结果 |
|---|---|
| 本地服务启动 | 通过 |
| 应用内浏览器连接 | 环境阻塞：控制进程退出 |
| 真实窗口公式字体 | 未执行，不记为通过 |
| 长公式换行 | 未执行，不记为通过 |
| 窄窗口布局 | 未执行，不记为通过 |
| 复制与按钮布局 | 自动化覆盖；人工视觉未执行 |

临时服务已停止。该环境阻塞满足 T0 “真实结果或明确环境阻塞”的退出语义，但仍是
发布前必须补验的限制，不得在 T6 前改写为人工通过。

## 自动化证据

新增语料聚焦测试：

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_evaluation_corpus.py -q `
  --basetemp=.pytest-tmp\t0-corpus-2
```

结果：`4 passed in 0.07s`。

完整收口检查：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest-tmp\t0-closure
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pip check
```

结果：`174 passed in 7.23s`；Python 编译成功；
`No broken requirements found.`

## T0 退出结论

- 人工视觉清单：有明确、可复述的环境阻塞；
- Selection、ResearchContext、公式：各有两个离线真实样本；
- 原 170 项基线：无回归，加入 4 项语料测试后为 174 项；
- 正式文档与六个项目 Skills：已同步到 V1.3.2→V2 门禁体系。

T0 完成，可以进入 T1 Selection 与 Provenance。尚未授权或实现 CodeContext、
OCR、第三方 PDF Parser、持久化、UI 重写或工具型助手。
