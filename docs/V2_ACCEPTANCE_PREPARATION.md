# ResearchMind V2 内部验收准备与结论

准备日期：2026-08-31 · 用户确认日期：2026-09-01

候选：`2.0.0rc1`

冻结提交：`9b3ad5fdab7eb6485b38ac13994569ebb362de32`

状态：**Accepted as V2 local internal baseline**；不对外发布

## 1. 验收目标与边界

本轮判断冻结的 V2 内部候选是否可以成为后续 V3 开发的稳定回归基线。验收只
检查已经实现并写入 `docs/PRODUCT_SPEC.md` 的能力，不在验收期继续加功能。

V2 保留已实现的选择驱动 LaTeX：用户选择数字 PDF 文字层中的数学内容，系统用
有界 `ResearchContext` 请求一个受限表达式，经过严格解析后预览，并可进入
KnowledgeNote/Obsidian。以下内容由用户明确排除于 V2：

- 自动公式区域识别；
- 图片公式 OCR 或图片公式自动转 LaTeX；
- 整页/整篇 PDF 自动转 LaTeX；
- 公式 Spike 中的 `FormulaRegion`、视觉 provider 和 OpenDataLoader/Docling
  候选集成。

这些实验文件不得进入 V2 wheel、V2 测试计数或 V2 完成声明。PDF 阅读区滚轮
翻页 CCv2 也仍是 post-V2 Spike，不阻塞 V2。

## 2. 冻结对象

| 项目 | 验收对象 |
|---|---|
| Git | `main` 与当前分支 HEAD 均指向 `9b3ad5f`；当前仅有未提交公式 Spike/文档，生产源码无差异 |
| 版本 | `pyproject.toml` 与 `researchmind.__version__` 均为 `2.0.0rc1` |
| wheel | `.release-tmp/t6d-2.0.0rc1-final-2/researchmind-2.0.0rc1-py3-none-any.whl` |
| wheel SHA-256 | `F78830A38914068995DE4836FC93503652182C5684961A7CFD9DA200FF01A571` |
| 发布边界 | 本地内部验收；不上传 PyPI/GitHub Release，不 push，不创建公开 tag |

## 3. 2026-08-31 新跑自动证据

所有 routine tests 使用 fake/mock provider、生成 PDF、临时代码项目和临时 Vault；
没有调用真实 LLM，没有读取课程 PDF，没有写入真实 Vault。

| 检查 | 结果 |
|---|---|
| 冻结 V2 pytest（排除两个未跟踪公式 Spike 测试） | `269 passed, 1 skipped in 11.13s` |
| skip | Windows 主机不能创建测试 symlink；生产路径仍显式拒绝 symlink |
| `compileall`：`src tests scripts evaluations` | exit 0 |
| 当前 venv `pip check` | `No broken requirements found.` |
| `project-planner` / `testing-review` Skill 官方校验 | `Skill is valid!` / `Skill is valid!` |
| 100 页生成 PDF 打开/提取 | 0.041895 s / 5 s，Pass |
| 首页面渲染 | 0.026027 s / 2 s，Pass |
| 2,000 个 Python 文件静态索引 | 3.871373 s / 20 s，Pass |
| 1,000 条 Markdown 备份 | 7.941770 s / 10 s，Pass |
| 1,000 条 Markdown 恢复 | 0.862965 s / 5 s，Pass |

第一次 pytest 尝试因系统临时目录
`<system-temp>/pytest-of-<user>` 无访问权限而在 fixture
setup 阶段报错；改用经确认不存在的仓库内专用 `--basetemp` 后完整通过。该失败
属于验收环境诊断，不能计为产品失败，也没有被隐藏。

Skill 校验器最初在 bundled Python 中因缺少 `PyYAML` 无法启动；随后复用本机
已有 PyYAML 的 `<existing-python> -X utf8` 运行同一个官方 `quick_validate.py`，两个
Skill 均通过。没有把 PyYAML 加入 ResearchMind 运行时或测试依赖。

## 4. 可复用既有证据

- T6-B：非联网配置诊断、Markdown-only manifest/SHA-256 备份恢复、干净安装和
  wheel 升级/回滚已通过；
- T6-C：隐私/权限、依赖漏洞、极限性能和重启恢复已通过；用户确认桌面与窄窗口
  人工清单通过；
- T6-D：最终 wheel、隔离安装、launcher 健康检查、诊断、恢复和安全扫描已通过；
- 用户于 2026-08-31 已确认论文、独立代码和 T5-B1 三条旅程通过。

既有用户确认是历史人工证据，不伪装成本轮 AppTest、浏览器自动化或截图。

## 5. 用户验收清单（由用户总体确认关闭）

使用测试 PDF、可丢弃 Python 项目和测试 Vault。任何源码 apply/rollback 只针对
可丢弃项目，不运行被修改代码。

以下清单保留为可重复执行的人工路径。用户于 2026-09-01 明确要求“完成 V2
验收”，因此人工门禁按用户的总体结论关闭；这不是逐项自动浏览器、AppTest、
截图或本轮重新执行的声明。

### A. 启动与配置

- [ ] 从已安装的 `2.0.0rc1` 启动，Local URL 可直接打开；
- [ ] “启动与配置检查”不显示 API Key 或绝对 Vault 路径；
- [ ] 论文、代码、助手三个顶层工作区均可进入。

### B. 论文旅程

- [ ] 打开测试 PDF，完成翻页、缩放、搜索和双栏文本块复制；
- [ ] 一键选择文本/文字层公式块，确认 page/block/bbox 来源可见；
- [ ] 完成一次翻译、一次 ResearchContext 解释和一次追问；
- [ ] 对用户选择的数学文字运行现有受限 LaTeX，检查源码可复制、预览可见且
  明确提示需要对照原图；
- [ ] 预览并保存一条论文 KnowledgeNote 到测试 Vault，确认不覆盖既有 Markdown。

### C. 代码与证据旅程

- [ ] 不打开 PDF 也能进入代码工作区；
- [ ] “零基础学习”和“科研代码复现”两种目标均可理解；
- [ ] 打开可丢弃 Python 项目，检查静态概览、相对路径、符号/行选择和有界
  CodeContext；确认界面不声称代码已运行；
- [ ] 建立一条用户确认的 Paper/Math/Algorithm ↔ Code 链接，确认双方 locator、
  关系、置信度和 generation method 可见；
- [ ] 运行一次 T5-A，确认每个工具结果需要用户继续，且没有写入/执行权限。

### D. 写入、恢复与知识沉淀

- [ ] 在可丢弃项目完成一次 T5-B1 proposal → diff → apply → rollback；确认每个
  动作单独确认、恢复凭据可见，且没有自动运行测试或 Shell；
- [ ] 专项补验 Code → Obsidian：预览当前代码选择的 Markdown，再显式保存到测试
  Vault；确认只有项目名、相对路径、行/符号，没有绝对代码根路径或 PDF 页码；
- [ ] 对测试 Vault 完成一次 Markdown-only backup/restore 到新目录；重复恢复必须
  被拒绝，原笔记不被覆盖。

### E. 视觉与错误恢复

- [ ] 桌面和约 390×844 窄窗口中导航、按钮、代码、公式和错误消息没有关键内容
  被横向截断；
- [ ] 无效 PDF、无效代码目录或无效 Vault 至少触发一种可恢复错误；
- [ ] 停止并重新启动应用后仍可进入，但会话内状态不应被误认为持久化。

## 6. 通过规则

V2 内部验收通过需要同时满足：

1. 第 3 节自动证据保持通过；
2. 第 5 节没有阻断核心旅程的数据丢失、安全越界、无法启动或不可恢复错误；
3. 用户明确回复 V2 通过，或列出失败项；
4. 任何失败只按冻结 V2 合同判断。自动公式识别、图片公式 OCR、整页
   PDF→LaTeX、CCv2 滚轮和未批准的代码执行都不是 V2 失败项。

## 7. 最终用户结论

用户于 2026-09-01 明确确认完成 V2 验收，并说明 V3 开发要求将在另一个对话中
提出。结合第 3 节自动证据、T6-B/T6-C/T6-D 既有证据和此前已确认的论文、独立
代码、T5-B1 人工旅程，V2 人工与自动门禁均关闭，`2.0.0rc1` 成为后续 V3 的
本地内部回归基线。

该结论是用户确认的阶段验收，不伪装成新增浏览器自动化证据。验收不授权公开
发布、远端 push、公开 tag、公式实验合并或版本号变更；当前对话不开始 V3。
