# T6-D 内部发布候选封口与真实用户闭环

日期：2026-08-31
状态：Completed / 本地内部候选已冻结
发布策略：只形成可追溯的本地内部 RC，不上传包、不创建公开 Release、不对外发布
进入基线：T5-A/T5-B1 与 T6-A/T6-B/T6-C Completed；261 passed，1 项环境跳过
最终源码自动基线：269 passed，1 项环境跳过

## 1. Problem / Current / Expected

ResearchMind 已有论文阅读、ResearchContext、LaTeX、KnowledgeNote、Obsidian、
静态 CodeContext、EvidenceLink、T5-A 和 T5-B1，但当前工作区仍包含此前阶段的
此前未提交改动，包版本仍为 `0.1.0`，T6-C 的 2,000 文件冷索引也留下约
16 秒的等待信号。T6-D 已关闭这些问题，并在用户要求下于冻结前加入可选
Code → Obsidian 笔记；该补充不改变架构或代码执行权限。

T6-D 的目标是关闭这些发布治理问题，而不是再加入新功能：

- 冻结当前 Paper ↔ Mathematics ↔ Code ↔ Notes 范围；
- 重跑 wheel、干净安装、配置诊断、完整闭环、备份恢复、性能和安全证据；
- 对长代码索引等待给出明确产品决定；
- 形成一个本地内部 RC 的版本与 Git 可追溯点；
- 保留真实用户人工闭环与任何环境限制，不用自动化冒充人工证据。

## 2. 明确排除

- 不公开发布，不上传 PyPI/GitHub Release，不推送远端；
- 不加入 T5-BX Shell、测试执行、依赖安装或后台 Agent；
- 不引入数据库、REST、多进程、UI 重写、OCR、新 PDF 引擎、RAG 或自动 Paper ↔ Code；
- 不在真实用户代码或 Vault 上执行破坏性测试；
- 不因 RC 封口自动宣称科研结果已复现或 AI 回答质量已达到所有学科要求。

## 3. T6-D 退出检查表

| 门禁 | 通过条件 | 当前状态 |
|---|---|---|
| 范围冻结 | 架构、产品规格、README、规则与 Skills 对当前能力/排除项一致 | Pass：六个 Skills 官方 validator 通过；2.0.0rc1 文档同步 |
| 完整回归 | unit/integration/e2e 全量通过，skip 与环境限制如实记录 | Pass：269 passed，1 Windows symlink skip |
| 安装与工件 | 本地 wheel 可构建、哈希可记录、干净 Python 3.12 环境可安装并启动/诊断 | Pass：2.0.0rc1 最终工件 |
| 数据恢复 | 临时 Vault 的 Markdown-only backup/restore 仍不覆盖且校验一致 | Pass |
| 隐私与安全 | 无密钥/绝对敏感路径泄漏；无未批准的用户代码执行原语；依赖完整性/漏洞结果可追溯 | Pass |
| 性能决定 | 重跑 T6-C 基准，并对 2,000 文件等待选择优化、降限或明确进度反馈 | Pass：优化且不降限 |
| 用户闭环 | 自动闭环证据完成；真实用户确认论文与代码核心旅程，证据类型不混淆 | Pass：用户于 2026-08-31 明确确认三条旅程 |
| 版本与 Git | 用户确认内部 RC 版本；形成干净、可回滚、可定位的本地 Git 基线 | Pass：2.0.0rc1 本地提交；无 push/tag/upload |

只有全部必需项关闭后才能把 T6-D 标记为 Completed。真实用户确认、最终版本号
或 Git 冻结任一缺失时，保持 Active，不伪报发布候选完成。

## 4. 验证顺序

1. 静态检查版本、文档、秘密、依赖边界和未提交范围；
2. 用 fake provider 与临时 PDF/代码/Vault 跑完整自动化闭环；
3. 构建本地 wheel，在新 Python 3.12 venv 中非 editable 安装并执行诊断/启动检查；
4. 重跑性能与备份恢复，决定 2,000 文件等待 UX；
5. 必要时只修复 T6-D 范围内阻塞，并重跑受影响及全量测试；
6. 记录真实用户确认与剩余限制；
7. 由用户确认 RC 版本后再提交/冻结；不创建公开发布物。

## 5. 回滚

T6-D 验证只在仓库内测试临时目录、系统临时目录和全新 venv 中运行。未确认
版本前不改远端或公开状态。若发现阻塞，保留当前 T5-B1/T6-C 实现基线，删除
可丢弃构建/测试环境，并把 T6-D 保持为 Active。

## 6. 2026-08-31 自动验证证据

- 首次完整规模基准的 `code_index` 为 21.19 秒，超过 20 秒门槛；定位到
  逐文件读取/AST 阶段后，使用最多 8 个有界线程并保持候选顺序、限制与只读
  语义。两次同规模复测为 3.43 秒和 3.66 秒，峰值约 5.16 MiB；其余 PDF、
  备份与恢复指标也通过。
- 全量：`python -m pytest -q` 得到 `263 passed, 1 skipped in 10.67s`。skip 是
  当前 Windows 主机不能创建测试 symlink；生产代码仍显式拒绝 symlink。
- 临时 wheel：`researchmind-0.1.0-py3-none-any.whl`，当前 SHA-256 为
  `D7804A948F65D4D654AD6E4BD2C3DB402D36BCF29CC2A6594FF8592ADB2BEA16`。
  默认清华镜像首次没有返回 `setuptools>=75`；显式官方 PyPI 后构建成功，
  没有通过关闭隔离或删除约束规避失败。
- 新 Python 3.12 venv 非 editable 安装成功；包元数据/模块均为临时 `0.1.0`，
  `pip check` 无损坏依赖。已安装 `researchmind.exe` 在
  `127.0.0.1:8511/_stcore/health` 返回 `200 / ok` 后停止。
- wheel 扫描：没有 `.env`、tests、密钥形状或本机绝对路径。启动器的固定
  `subprocess.run` 只调用当前 Python 的包内 Streamlit 应用，不使用 Shell、
  不读取或执行用户代码；T5-BX 仍未批准。
- 独立 `pip-audit 2.10.1` 首次只报告新 venv 自带 `pip 25.0.1` 的 7 条已知
  漏洞；将候选环境 pip 升至 26.2.1 后复扫为无已知漏洞。本地未上传的
  `researchmind` 包按预期无法从 PyPI 审计，并被明确记录为 skip。
- 临时 Vault 中一篇合成 Markdown 通过 CLI 备份/恢复，前后 SHA-256 相同；
  对相同恢复目标的第二次操作返回退出码 2，没有覆盖。

## 7. 尚未关闭

T6-D 必需门禁已经关闭。剩余的 PDF 鼠标滚轮交互是后续 CCv2 Spike，不属于
当前工件。Code → Obsidian 新界面有自动 AppTest 和 Vault 证据，但尚未取得用户
对该新增折叠面板的专项人工确认；在任何未来公开发布前仍建议做一次针对性人工
视觉/交互复查，此限制不伪装成已完成的人工证据。

## 8. 真实用户确认清单

自动验证完成后，由用户在真实桌面完成并明确回复结果：

1. **论文旅程**：打开一份测试 PDF，完成翻页/双栏文本选择、翻译或 LaTeX、
   ResearchContext 解释与追问，并把一条内容预览为 KnowledgeNote；如要写入，
   只使用测试 Vault。
2. **代码旅程**：不打开 PDF，进入代码工作区，打开一个可丢弃 Python 项目，
   选择“零基础学习”或“科研代码复现”，检查静态项目概览，选择一个函数并
   预览/请求非执行解释。
3. **T5-B1（可选但推荐）**：仅在可丢弃项目中生成一项替换提案，确认 diff、
   apply 与 rollback 的逐动作提示；不要运行被修改代码。
4. 记录是否出现阻塞、误导性文案、无法理解的按钮或数据丢失。只有用户明确
   确认论文与代码两条核心旅程通过，才关闭“用户闭环”门禁。

### 8.1 人工结果

用户于 2026-08-31 在已安装候选 wheel 的本地 Streamlit 界面明确报告：

- 论文旅程：通过；
- 独立代码旅程：通过；
- T5-B1 提案/diff/apply/rollback 旅程：通过。

这是用户报告的人工证据，不是 AppTest、HTTP health 或自动浏览器证据。

### 8.2 非阻塞后续反馈

人工验收同时提出两项改进；其中一项按用户后续要求在冻结前实现：

1. **PDF 鼠标滚轮翻页**：分类为交互优化。Streamlit 没有原生“滚轮即换页”
   控件，应先做 CCv2 隔离 Spike，验证只在指针位于 PDF 阅读区域时触发、阈值/
   防抖、页首页尾、触控板连续事件、普通页面滚动不被劫持，以及一次手势只换
   一页；不改变 PyMuPDF 阅读/提取边界。
2. **Code → Obsidian 可选笔记（Implemented）**：复用当前 `CodeSelection`、
   `KnowledgeNote` 和非覆盖 Vault writer；代码专用 Markdown 记录项目名、相对
   路径、行范围、符号/提取方式、问题、可用解释和用户理解，不生成 PDF 页码或
   绝对 root。预览与保存分别确认，重选/重新解释/应用/回滚会使旧预览失效；
   不扩大 T5-B1 或执行权限。解释另绑定产生它的问题，编辑问题后旧解释不会
   伪装成当前回答。聚焦 40 项与全量 269 项测试通过。

## 9. 2.0.0rc1 最终工件证据

- `pyproject.toml` 与 `researchmind.__version__` 均为 `2.0.0rc1`；wheel 元数据一致。
- 最终 wheel：`researchmind-2.0.0rc1-py3-none-any.whl`，105,949 bytes，SHA-256：
  `F78830A38914068995DE4836FC93503652182C5684961A7CFD9DA200FF01A571`。
- wheel 共 78 个 entry；不含 tests、`.env`、`secrets.toml`、API Key 形状或本机
  `D:/ResearchMind` 路径。
- 全新 Python 3.12 venv 非 editable 安装成功；导入路径位于该环境
  `site-packages`，`pip check` 返回 `No broken requirements found.`。
- 安装后的 `researchmind.exe` 仅监听 `127.0.0.1:8514` 进行检查，
  `/_stcore/health` 返回 `200 / ok`，随后进程已停止。
- 无配置诊断返回无 error，并只给出 LLM/Vault 可选 warning；不联网或泄露值。
- 合成 Markdown 的 backup/restore SHA-256 一致；第二次恢复到同名目录被退出码
  2 拒绝，没有覆盖。
- `pip-audit 2.10.1` 对最终 `site-packages` 报告无已知漏洞；本地未上传的
  `researchmind 2.0.0rc1` 按预期标记为无法从 PyPI 审计。
- `compileall` 退出码 0；最终完整回归为
  `269 passed, 1 skipped in 10.77s`。skip 仍是当前 Windows 主机不能创建
  symlink，生产边界仍显式拒绝 symlink。
- 六个项目 Skills 使用 skill-creator 官方 `quick_validate.py` 在 UTF-8 模式下
  均返回 `Skill is valid!`；项目 venv 缺少 PyYAML、系统 Python 默认 GBK 的两次
  启动失败被保留为校验环境诊断，不冒充 skill 内容失败。
