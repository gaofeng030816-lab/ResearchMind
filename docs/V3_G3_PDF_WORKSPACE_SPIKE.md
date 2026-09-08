# V3-G3 PDF 文字层与自适应工作台

2026-09-08 · Completed / 正式 CCv2/pdf.js 已采用 · 不对外发布

## 起点与演进记录

用户确认 G2 验收后要求提交并启动 G3。G2 本地提交 `ee38a14`，提交前
回归 374 passed / 1 Windows symlink environment skip；未推送 GitHub。
V2 2.0.0rc1、G1/G2 存储与正式阅读区保持不变。

首批实现 experiments/pdf_selection_spike/contract.py 的候选选择事件契约。
数据流：可信页面快照 + 不可信选择事件 → 纯校验 → 实验 Selection。
校验修订、实例、页码、序号、span 范围、偏移与文字一致性；成功后调用方
才推进序号。它尚未接入正式 ReadingSelection、翻译、笔记或持久化。
实例匹配防意外串台，不是对恶意浏览器代码的认证。

Unicode 偏移按 code point 计数，未来 JS 必须转换 UTF-16 偏移。
仅支持同页有序范围，跨 span 明确换行拼接。bbox 是快照中的完整 span
粗框，不是选中字符的精确框，不能据此声称双栏或公式定位正确。
无新依赖、无网络、无私人文件或配置读取，生产代码不导入实验。

## 分步计划与采用门禁

1. G3-A：inline CCv2 合成文字实验与真实 Edge 检查已通过；官方模板下的
   PDF.js 合成 PDF 和五类代表性 PDF 也已完成浏览器检查。
   打包组件必须采用官方 v2 模板；记录固定版本、许可、Windows 打包、
   离线资源/worker、网络、延迟和内存。当前未选择或安装新依赖。
2. G3-B：纸面单独全宽、纸面+代码分栏、600px 窄屏降级、滚动归属/边界/
   方向/防抖及 AI 快捷键输入抑制已有 Edge 自动证据；用户已完成人工触控板验收。
3. G3-C：真实浏览器与回归证据完成；用户批准采用后已接入正式应用并验收。

比较现有 PyMuPDF 图像+文字块与候选 CCv2/pdf.js；原生查看器只有能提供
可验证选择定位才是替代方案。保留 PyMuPDF 后端与旧阅读区作为回退。

## 五类代表性 PDF 矩阵（已执行，见 2026-09-07 收口证据）

| 类型 | 验证点 |
| --- | --- |
| 单栏数字 PDF | 选择/复制、页码、缩放一致性 |
| 双栏论文 | 跨行/栏、连字符、阅读顺序 |
| 中文/Unicode | 连字、非 BMP、组合字符和偏移 |
| 数学/表格/图注 | 上下标与混合布局，不等于公式识别 |
| 扫描/空白/异常页 | 无文字层清楚降级，不伪造选择 |

真实浏览器另查文档切换、重复事件、多实例、rerun 恢复、挂载清理、
滚动/防抖/快捷键焦点和全宽/分栏/窄屏；记录环境、操作和实际结果。
本节建立时长文档性能、离线资源和打包证据尚未执行；后续实测结果见本文末尾。

## 已执行验证与回滚

`python -m pytest -q experiments/pdf_selection_spike --basetemp=.pytest-tmp-g3-contract`

31 passed in 0.14s：Unicode、多 span、旧修订/实例/页、重复序号、类型和
预算限制、越界/重叠/倒序、伪造文字/额外几何字段。
只有合成文字契约测试，未验证真实 PDF、CCv2 或浏览器。G3 未完成。
实验在 experiments 内，撤销实验无需数据迁移。G4/G5/G6 未启动。

联合回归：`python -m pytest -q tests experiments/pdf_selection_spike --basetemp=.pytest-tmp-g3-start`
结果 405 passed / 1 skipped in 16.21s；唯一跳过仍为 Windows 符号链接环境限制。
project-planner 与 testing-review 均通过官方 quick_validate；Git diff 空白检查通过。
G3 启动改动留在工作区，未混入已提交的 G2 验收提交。

## 本轮增量：可运行的隔离 CCv2 实验页

- `app.py`：原生样本/页码/重挂载控件、选择校验结果；不导入正式应用。
- `component.py`：inline HTML/CSS/JS，无构建链和外部资源；选择预览后点击
  提交才发送到本机 Python。使用 textContent，不把选中文字作为 HTML 执行。
- `fixtures.py`：单栏、双栏、Unicode、数学文字和空白五类**合成 DOM 文字**。
  它们不是上面五类真实 PDF 语料，不代表提取质量。
- `spike_state.py`：实验独立会话状态；回调校验事件，失败清空选择，成功更新
  序号；切样本/页码/代数更换实例并清空旧选择。不会改正式 app/state.py。
- `test_harness.py`：状态转换、AppTest 页面/切换/恢复、Node 字符偏移与
  JS → Python 事件契约一致性测试。AppTest 不模拟 DOM 拖选。

数据流为：合成页面快照 → 浏览器文本节点 → 本地选择预览 → 显式提交 →
实验回调校验 → 会话内结果展示。没有翻译、模型请求、数据库或 Vault 写入。
组件监听器包含清理函数；同一挂载点重建前先清理旧监听器，已接受文字从服务端
回传。真实 Edge 已验证重跑恢复与切换清理；多实例隔离仍需浏览器证据。

Shadow DOM 选择优先使用 getComposedRanges，并校验两端都在当前实验页中；
不支持可定位选择时降级提示，不采用可能跨根失真的 getRangeAt 回退。
依据：[MDN 的 Shadow DOM 选择说明](https://developer.mozilla.org/en-US/docs/Web/API/Selection/getComposedRanges)。
范围转为 Unicode code point；切到代理对中间的偏移拒绝。跨 span 换行是
当前契约的明确规范，不保证等同浏览器剪贴板格式。原生 Ctrl+C 未被拦截。
当前不拦截滚轮或快捷键，尚未实现翻页防抖和 AI 唤醒。

### 本轮实际测试

- `python -m pytest -q experiments/pdf_selection_spike --basetemp=.pytest-tmp-g3-harness`
  → **39 passed in 3.48s**（此前 31 项 + 本轮 8 项）。
- `python -m pytest -q tests experiments/pdf_selection_spike --basetemp=.pytest-tmp-g3-inline`
  → **413 passed / 1 skipped in 18.12s**；跳过仍是原有 Windows 符号链接限制。
- 实验 `/_stcore/health` → HTTP 200。用户已授权独立启动与浏览器检查。
- 本机浏览器控制工具初始化异常后，改用相同主机上的 Playwright + Edge 152
  执行真实 DOM 鼠标拖选。通过单栏选择/回传、重跑恢复、Unicode 偏移、换页清理、
  右栏映射、480px 无页面横向溢出、空白不可提交共 7 项；无页面脚本错误和外部请求。
- 浏览器检查发现并修复两项实验问题：Shadow DOM 中 document selection 的
  `isCollapsed` 不能代表 composed range；重复渲染若未先清理会积累监听器并产生
  重复序号。修复只位于隔离实验。

## 本轮继续：官方模板 PDF.js 打包实验

`experiments/rm-g3-pdf-viewer/` 由 Streamlit 官方 v2 组件模板提交
`0b042aaa95e9080be93b079fd0c1519ee84e85cf` 生成，并固定 `pdfjs-dist` 6.3.289。
它是纯 TypeScript + CCv2 打包实验，不导入 ResearchMind 正式应用：

- Python 边界只接受 `%PDF-` 开头、最大 10 MiB 的 bytes，并校验页码和 0.5–2.5
  缩放；浏览器接收 base64 与 SHA-256 revision；
- PDF.js worker 随本地构建加载。实验选取文字后先只在浏览器预览，点击提交才发送
  revision、page、sequence、text、item range、归一化 bboxes、viewport 和 engine；
- 该事件是**不可信候选**。尚未与 PyMuPDF 当前页可信 span/文字/几何重新核对，
  因而不能生成正式 ReadingSelection，也不能进入翻译、prompt、资料库或笔记；
- 后续 G3-B 增量只在获得焦点的专属滚动容器页边缘拦截有效相邻页手势；
  Python 会重验 revision、instance、current page、page count、sequence 和单步
  delta。快捷键与响应式布局仍是无网络的隔离工作区实验；
- 模板占位许可已替换为内部实验声明；PDF.js Apache-2.0 边界和来源记录在
  `THIRD_PARTY_NOTICES.md`。`node_modules`、构建物、测试 PDF 和截图均被忽略。

构建使用 Node 24.15.0；`npm ci/install` 共 38 个包且当次审计为 0 vulnerabilities。
最终 `npm run build` 的 TypeScript 检查和 Vite 8.2.2 构建通过：CSS 1.29 kB
（gzip 0.59 kB），JS 3404.59 kB（gzip 878.07 kB）。该体积是继续评估项，不能
直接当作生产性能合格。

浏览器夹具由 `generate_fixture.py` 生成两页 2794-byte 非私人数字 PDF：第一页
单栏，第二页双栏。PyPDF 重开得到 2 页且提取到预期文字；Poppler 与 Edge canvas
截图人工核对均显示页面完整、左右栏对齐、无裁切重叠。Edge 152 自动检查通过：

1. 本地 PDF canvas 与 PDF.js text layer 渲染；
2. 真实鼠标拖选产生 revision/page/item/bbox/engine 事件；
3. trigger 回调重跑前后 canvas 像素签名完全一致；
4. 换页重新渲染并清除上一页候选；
5. 第二页左右栏文字项均存在；
6. 无页面错误、无非 `127.0.0.1:8504` 请求。

Python wrapper 边界已有 25 项单元测试。上述合成 PDF 只证明“打包链路和最小
选择闭环可运行”，不替代五类代表性真实论文、跨行/跨栏复制、中文与连字、扫描
降级、多实例、滚轮/触控板、快捷键焦点、窄屏、长文档性能、Windows wheel 安装
以及可信后端 provenance 对账。

### 2026-09-05 打包实验首轮自动验证

- `python -m pytest -q experiments/pdf_selection_spike experiments/rm-g3-pdf-viewer/test_wrapper.py`
  → **48 passed in 3.88s**；
- `python -m pytest -q tests experiments/pdf_selection_spike experiments/rm-g3-pdf-viewer/test_wrapper.py`
  → **422 passed / 1 skipped in 19.34s**；唯一 skip 仍是既有 Windows 主机无法
  创建符号链接，不是 G3 新失败；
- `npm run build` → TypeScript typecheck 与 Vite 构建通过；
- `browser_pdf_smoke.cjs` → Edge 152 上 5 项逻辑检查通过，0 page errors，
  0 outbound requests；另对两页 canvas 截图完成人工视觉核对；
- project-planner 与 testing-review 通过官方 `quick_validate.py`。主虚拟环境未新增
  PyYAML；校验使用既有忽略目录中的隔离工具环境。

以上结果不包含生产应用接入测试，也不把 localhost 浏览器脚本加入日常 pytest。

## 本轮继续：滚轮、快捷键与响应式工作区

`example.py` 现在先用 PyMuPDF 验证内存 PDF 并取得可信页数，再把受限 bytes、
SHA-256 revision、当前页、页数、缩放和固定 instance 交给 PDF.js。页面只提供
“仅论文”全宽与“论文 + 代码”3:2 分栏；Streamlit 原生 `wrap=True` 在 600px
视口按论文→代码顺序堆叠。代码区和 AI 区均为静态/无网络占位，不读取项目、
不执行代码、不发模型请求。

滚轮只监听 `.viewer-scroll`：用户点击使它获得焦点；中部滚轮保持普通滚动，
到页边缘后以 80px 累积阈值、180ms 方向/间隔重置、单事件 120px 限幅、650ms
锁定和 250ms 静默释放请求相邻一页。选择待提交、修饰键、横向手势和非聚焦
状态均不翻页；第一页向上、末页向下不 `preventDefault`。浏览器事件不能直接
改页，Python 拒绝旧修订、错实例、错当前页、重复序号、跨页和越界请求。

独立 inline CCv2 监听 `Ctrl+Shift+A`，只切换无网络 AI 占位面板。输入框、
textarea、select、button、role textbox/button、contenteditable、CodeMirror 和
Monaco 路径以及 repeat/IME 组合输入均不触发；重渲染前清理旧 listener。

实际证据（2026-09-05）：

- Edge 152 的 `browser_workspace_smoke.cjs` 通过 13 项：仅论文宽度、首页放行、
  中部滚动、非聚焦不翻页、Ctrl+wheel 放行、三次 30px 边缘 burst 单次翻页、
  末页放行、反向翻页回到底部、选择保护、AI 输入保护、桌面分栏、代码备注
  输入保护、600px 堆叠且无页面横向溢出；
- 原有 `browser_pdf_smoke.cjs` 5 项继续通过；两次检查均为 0 page errors、
  0 outbound requests；
- `experiments/pdf_selection_spike` 与 packaged wrapper 合计 **64 passed**；正式
  `tests/` 为 **374 passed / 1 skipped**；组合总数 **438 passed / 1 skipped**。
  唯一 skip 仍是 Windows 主机无法创建符号链接；首次全量测试因系统 Temp ACL
  在 fixture setup 报错，改用仓库内全新 `--basetemp` 后全部通过；
- `npm run build` 的 TypeScript typecheck/Vite 构建继续通过：CSS 1.36 kB
  （gzip 0.62 kB），JS 3406.19 kB（gzip 878.67 kB）；
- Windows 本机 `pip wheel --no-deps --no-build-isolation` 成功生成 879354-byte
  `py3-none-any` wheel（SHA-256 `f7a5a69435aeb1ed42767043b3a444506bd97d404c055c95989fc9c3111745f6`），
  检查确认包含快捷键模块、PDF.js/CSS 构建资源、METADATA 和第三方许可；尚未以
  此结果替代新环境安装/长文档运行证据；
- `generate_fixture.py` 的 ReportLab 现显式属于 `[fixture]` 可选依赖。重新生成
  后 pypdf 重开为 2 页、提取字符数分别为 259/212；Poppler 两页渲染人工检查
  无裁切、重叠或双栏错位。Poppler 报本机 Symbol/ArialUnicode display font
  警告，但夹具只使用 Helvetica，渲染内容完整。

截至 2026-09-05 仍未关闭：浏览器 wheel 自动事件不等于物理触控板；尚无五类代表性真实论文的
选择/复制与几何质量；packaged selection 仍是客户端候选，尚未逐 span/字符偏移
与 PyMuPDF 当前页快照对账；长文档仍会为每页传输并重新解析完整 base64 PDF，
性能和内存门禁未过；多实例与真实文档切换矩阵仍待补。因此 G3 保持 Active，
不得接入正式 `src/` 或启动 G4。

### 启动与人工检查

inline 合成 DOM 实验使用 8503；本轮 packaged PDF.js 工作区使用 8504；两者都
不是正式 8501 应用。若实验进程结束，可在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run experiments/pdf_selection_spike/app.py --server.address=127.0.0.1 --server.port=8503 --server.headless=true --browser.gatherUsageStats=false
```

packaged 实验按其 README 安装 `[fixture]` extra 并完成前端构建后，可运行：

```powershell
python -m streamlit run experiments/rm-g3-pdf-viewer/example.py --server.address=127.0.0.1 --server.port=8504 --server.headless=true --browser.gatherUsageStats=false
```

1. single 样本鼠标拖选几词，确认预览，点击提交；服务端展示相同文字。
2. unicode 样本选中 emoji、中文与组合字符，检查无错位/乱码。
3. columns 样本跨行/跨栏选择并 Ctrl+C；比较剪贴板和规范化预览的差异。
4. 点击“仅重新运行”后已验证文字仍在；切换页码/样本/代数后应清空。
5. empty 样本不能提交；选取实验区外文字也不能提交到本实验。
6. 检查窄窗口、普通滚动和输入操作不受影响。此处没有滚轮翻页功能。

截至 2026-09-05，下一步是建立五类非敏感代表性 PDF 语料清单，逐一验证复制与定位；随后完成滚轮、
快捷键在物理触控板/输入法/真实编辑器上的人工矩阵，并设计浏览器事件与 PyMuPDF
可信页面快照的逐 span/字符偏移对账适配器。完成质量、性能、许可、打包和回退证据后，才提出生产采用
决定；当前不关闭 G3。

## 2026-09-07 收口证据

### 可信来源与代表性语料

浏览器事件继续作为不可信候选。provenance.py 使用当前 PDF bytes 在服务端重新
提取目标页，重验 revision、instance、page、sequence、Unicode code-point ranges、
文字、viewport、engine 与几何覆盖；最终 bbox 只来自 PyMuPDF。只有文字在当前
页唯一且客户端锚点足够接近时，才允许 verified_unique_text_anchor 回退，客户端
bbox 从不直接成为 provenance。

五类 hash 锁定 PDF 在 Edge 152 重新运行，结果写入
[current_corpus_results_2026-09-06.json](../experiments/rm-g3-pdf-viewer/current_corpus_results_2026-09-06.json)：

- 5/5 文档通过；四份数字 PDF 共 12/12 次鼠标选择、原生复制与服务端对账成功；
- 10 次为 verified_text_geometry，2 次为 verified_unique_text_anchor；
- 扫描 PDF 的文字项为 0，界面正确降级且不伪造可提交选择；
- 0 页面错误、0 外部请求；结果不保存绝对路径、文件名或选中文字。

同栏跨行选择得到 2 个 client ranges 和 2 个可信行框；原生剪贴板比预览多一个
换行字符，规范化后完全一致。两个同时挂载的 viewer 分别提交选择，预览、按钮
和已接受结果互不串台。固定结果分别见
[跨行证据](../experiments/rm-g3-pdf-viewer/current_cross_line_results_2026-09-06.json)
和
[双实例证据](../experiments/rm-g3-pdf-viewer/current_multi_instance_results_2026-09-06.json)。

### 长文档性能与按需载荷

初始实现已经复用 pdf.js document，但每次 rerun 仍重复发送完整 base64 PDF。
在 9,115,188-byte、209 页样本上，页面 20/21 分别约 869/1132 ms，强制 GC 后
浏览器堆从约 56.5 MiB 增至 93.7/118.2 MiB。加入 loaded-revision CCv2 状态握手
后，浏览器缓存存在时只传 revision、页码和缩放；缓存缺失时组件清空 loaded
revision，下一次 rerun 自动重发验证后的完整 bytes。

代表性单次复测中，页面 20/21 为 resource reused、payload omitted，分别约
230/238 ms；强制 GC 后为 45,174,052 和 45,293,472 bytes，仅增加 119,420 bytes。
首次渲染约 1.54 s，0 页面错误、0 外部请求。完整前后数据与限制见
[性能证据](../experiments/rm-g3-pdf-viewer/current_performance_results_2026-09-07.json)。
这些是代表性单次测量，不是统计分布。

### 构建、安装与回归

Vite 产物改为固定 index.js/index.css，避免 setuptools 历史 build/lib 把多个
旧哈希资源带入 wheel。清理已确认可重建的实验 build 缓存后，Windows wheel
大小为 885,440 bytes，SHA-256 为
116AE4701536D306A62C9C101C22DEAACBC429E74D2C30C1128F1D5B73630BAE；
其中恰有一个 JS、一个 CSS、组件清单、METADATA 和许可证。非 editable 安装后，
Edge smoke 得到 5 个文字项、settled payload omitted、0 页面错误和 0 外部请求。

最新联合回归为 473 passed / 1 skipped；唯一 skip 仍是既有 Windows 主机不能
创建符号链接。npm TypeScript/Vite 构建、选择 smoke 5 项、工作区 13 项、跨行、
双实例与五类语料均通过。

### 2026-09-07 门禁结论（历史）

隔离 Spike 的代表性语料、可信来源、浏览器交互、性能、Windows 打包、许可和
回退证据已达到提出采纳建议的条件。当前建议为“有条件采纳”：先由用户完成
物理触控板的滚动归属、防误触、边界和防抖人工矩阵，再明确确认是否把该候选接入
正式 ReadingSelection。人工门禁和生产采用确认完成前，G3 保持 Active，正式
src、G4 翻译/草稿、G5 公式和 G6 多语言代码均不启动。

## 2026-09-08 正式采用与验收

用户在上一轮明确反馈“触控板验收通过，正式采纳 CCv2/pdf.js”。这是用户报告的
物理设备人工验收，不改写为代理自动观察；生产接入和下列自动检查由本轮执行。

正式数据流为：

    open_pdf 校验/提取并固定 SHA-256
    → load_pdf_viewer_source 重验路径、大小和内容 hash（上限 10 MiB）
    → 本地 CCv2/pdf.js 渲染 canvas + text layer
    → 用户拖选并在组件内显式确认
    → app/state.py 暂存带 revision/page/instance/sequence 的不可信事件
    → pdf/viewer_component 用当前 bytes 建立 PyMuPDF 页面快照并核对文字/几何
    → 只用服务端文字和 bbox 建立 ReadingSelection
    → 复用现有翻译、LaTeX、解释与知识流程

`pdf/viewer_component` 是唯一组件/对账边界，`app/use_cases.py` 只编排，所有
Streamlit 状态写入仍在 `app/state.py`。重复、过期、跨页、错误实例、错误引擎和
伪造文字/几何均失败关闭。组件注册或浏览器文字层不可用、PDF 超过 10 MiB、
文件打开后改变或缩放超出 0.5–2.5 时，正式阅读区继续提供 PyMuPDF 页面图像和
复制友好文字块，不丢失 V2 阅读能力。

正式工作台同时采用仅论文全宽、论文+已打开代码 3:2 原生响应式分栏，以及
输入框/按钮/编辑器/IME/repeat 安全的 Ctrl+Shift+A AI 面板开关。滚轮只在 PDF
滚动区获得焦点、到达相应页边缘、无待确认选择且累积越过阈值时请求相邻一页；
中部滚动、修饰键、未聚焦、首页/末页越界均不捕获。

本轮实际证据：

- `npm run build`：TypeScript 检查及 Vite production build 通过；产物为固定
  `index.js` 与 `index.css`；
- 正式边界/PDF/AppTest 定向回归：77 passed；包含 viewer hash/大小、可信
  selection、伪造/过期事件、快捷键序号和 PyMuPDF 回退；
- 独立 `127.0.0.1:8505` 正式实例上的 Edge 152：8/8 检查通过，覆盖真实鼠标
  拖选→ReadingSelection、滚轮归属/防抖/边界、快捷键输入抑制、仅论文全宽、
  桌面分栏及 600px 堆叠；0 page errors，0 external requests；
- 生产 wheel：1,041,404 bytes，恰好一个 JS、一个 CSS、组件清单、第三方声明
  与 Apache-2.0 全文；0 node_modules，0 source maps；安装到全新临时目录后可
  导入，并能找到全部资源；
- 最终联合回归：486 passed / 1 skipped；唯一 skip 仍是本 Windows 主机无法
  创建符号链接，不是产品失败。

因此 G3 的实验、人工设备、采用、正式实现、回退、浏览器、打包和回归门禁均已
关闭，状态为 Completed。PyMuPDF 仍是后端可信来源；PDF.js 只负责本地浏览器
显示与候选选择。本轮没有启动 G4，也没有实现公式识别、图片 OCR、持久
NoteDraft 或非 Python 解析。
