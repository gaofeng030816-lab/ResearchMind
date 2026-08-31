# T6-A 独立代码学习与复现工作区验证

日期：2026-08-29
状态：Completed（T6 总阶段仍为 Active）
基线：V1.3.2 + T1/T3/T4/T5-A/T6-A 内部增量，不对外发布

## 1. 实现范围

用户确认 T6 后，首个切片解决代码功能被埋在 PDF 长页面中的问题：

- 应用顶层改为“论文阅读与笔记 / 代码学习与复现 / 只读研究助手”三个工作区；
- 代码工作区在没有 `OpenedDocument` 时也能打开一个本地 Python 文件夹；
- 提供“零基础学习”和“科研复现”两种目标及独立默认解释问题；
- 从已索引的 `CodeProject` / AST 纯计算 `CodeProjectSummary`；
- 静态概览展示文件、行、定义、导入、入口候选、外部依赖候选和问题文件；
- 论文证据链接降为代码页中的可选折叠区，不是代码主路径前置条件。

没有新增依赖、数据库、服务、代码执行、import、Shell、测试运行、依赖安装、
写入或 T5-B 权限。

## 2. Before / After

| 维度 | T5 基线 | T6-A |
|---|---|---|
| 顶层结构 | 六个面板纵向连续显示 | 三个可独立进入的工作区 |
| 代码入口 | 位于 PDF/对话/笔记之后 | 顶层“代码学习与复现” |
| PDF 前置 | 逻辑上非必需，但界面心智依附 PDF | 无 PDF 时完整打开项目并选择/解释代码 |
| 用户差异 | 单一默认代码问题 | 零基础与科研复现独立引导/问题 |
| 项目视角 | 文件数和总体积 | path-safe `CodeProjectSummary` |
| 复现语义 | 无明确复现线索 | 静态入口/导入/依赖候选/问题文件；明确尚未运行 |

## 3. 数据流与边界

```text
workspace_navigation = code
→ render_code_workspace()
→ open_code_project() 的既有只读边界
→ CodeProject（当前会话）
→ core.summarize_code_project() 纯函数
→ CodeProjectSummary（不含 root_path）
→ 入门或复现概览
→ 显式 CodeSelection
→ 有界 CodeContext 预览
→ 用户点击后才调用 LLM
```

`CodeProjectSummary` 只消费现有项目模型，不读取新文件。第三方依赖候选来自
AST import 根名，排除 Python 标准库和项目本地顶层模块；它不是 requirements、
版本兼容、数据集、GPU 或成功运行证明。

## 4. Regression-first 证据

实现前先添加：

- `tests/unit/test_code_project_summary.py`；
- 无 PDF 代码工作区和双目标 AppTest。

首次命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_code_project_summary.py `
  tests/e2e/test_streamlit_app.py `
  -q --basetemp=.pytest-tmp-t6-red
```

结果按预期在收集阶段失败：
`ImportError: cannot import name 'summarize_code_project'`。

实现后的聚焦命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests/unit/test_code_project_summary.py `
  tests/unit/test_core_code_context.py `
  tests/unit/test_code_context_use_cases.py `
  tests/e2e/test_streamlit_app.py `
  -q --basetemp=.pytest-tmp-t6-focused-2
```

首轮结果：`18 passed in 7.84s`。最终源码复核又发现包内相对 import 会被误标为
第三方依赖候选；新增测试先以 `1 failed, 2 passed` 复现，再保留相对导入的
可见名称并将其排除出第三方候选。最终聚焦结果为 `19 passed in 10.87s`。

## 5. T6-A 完成映射

| 条件 | 证据 |
|---|---|
| 代码独立于 PDF | 条件渲染；AppTest 在 `opened_document is None` 时打开项目 |
| 适合零基础 | 分步入口说明、符号类型/行号、通俗默认问题 |
| 支持复现工作者 | 静态入口/导入/依赖候选/问题文件和复现风险问题 |
| 不夸大复现 | UI 明示“尚未运行”；依赖候选限制说明 |
| 保留权限边界 | 复用 T3 reader/AST/CodeContext；无执行或写入路径 |
| 保留已有闭环 | 全量 224 项回归 |

## 6. 最终自动化验证

- T6-A 最终聚焦：`19 passed in 10.87s`；
- 全量 pytest：`224 passed in 12.20s`；
- `python -m compileall -q src tests scripts experiments`：退出码 0；
- `python -m pip check`：`No broken requirements found.`；
- README、产品规格、架构、开发计划、V1→V2 门禁与 AGENTS 规则已同步为
  “T6 Active / T6-A Completed”；
- skill-creator 官方 `quick_validate.py` 对六个项目 Skills 逐一返回
  `Skill is valid!`；
- routine tests 使用临时项目与 fake provider，没有运行用户代码或真实付费 API。

## 7. 当时遗留与后续状态

- 尚未读取 README、requirements、environment.yml、Notebook、配置或数据说明；
- 入口和外部依赖只是静态候选，未验证安装与运行；
- 尚无受控运行沙箱、实验记录、结果对比或跨会话项目库；
- T6-A 关闭时尚未完成真实浏览器人工视觉、Windows 安装/升级/恢复、性能和隐私
  发布检查；后续 T6-B/T6-C 已完成，其中 T6-C 视觉清单由用户人工确认通过。

后续已经按顺序完成 T6-B 的首次启动、配置诊断、可重复安装、升级/回滚和备份
验证，以及 T6-C 的安全/性能/人工门禁。当前下一阶段是尚未开始的 T6-D 发布候选；
Shell、测试执行或依赖安装仍需独立 T5-BX 决策。
