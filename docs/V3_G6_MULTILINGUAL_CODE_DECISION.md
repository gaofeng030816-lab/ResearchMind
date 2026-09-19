# V3-G6 多语言 CodeContext：解析器 Spike 与采纳门禁

日期：2026-09-16
状态：**Completed · 方案 A 于 2026-09-16 获用户确认并完成生产验证**
进入基线：`0f31033`（V3-G4/G5 已提交）

## 1. 目标与不变边界

G6 要让 Python、C、Java、Julia 和 R 源码进入同一条静态阅读链路：

```text
受限源码目录 → 语言识别与静态 parser adapter → CodeSymbol
→ CodeSelection → 有预算的 CodeContext → 预览/解释/可选笔记证据
```

本阶段不运行、导入、编译、测试或安装被阅读项目；不解析依赖；不把静态阅读
称作代码可运行或可复现。相对路径、文件数量/大小、UTF-8、隐藏/敏感/vendor
目录、symlink/root containment、提示预览和绝对路径不外泄规则保持不变。
T5-B1 仍只允许显式打开的外部 Python 项目中的一个已选范围；ResearchMind
托管代码仍为只读。

## 2. 进入 G6 时的基线

- `code/reader.py` 当时只枚举 `.py`，使用标准库 AST，遇到语法错误降级为文字选择。
- `CodeFile`、`CodeSelection` 与 `CodeContext` 目前没有显式语言字段，解析方法只有
  `ast`/`text`。
- G1 的浏览器目录导入和托管存储只接受 `.py`，媒体类型仍是 Python directory。
- 现有 Python 路径不执行源码，并已覆盖数量/大小、UTF-8、敏感文件和相对路径。

因此 G6 需要一个小 parser protocol、显式语言来源和多语言导入验证；不需要改变
数据库 schema，也不需要合并 `ResearchContext` 与 `CodeContext`。

## 3. G6-A 隔离 Spike 结果

### 3.1 Windows/Python 3.12 wheel

在独立临时目录中下载并安装下列固定 wheel；没有改动 `.venv` 或
`pyproject.toml`：

| 包 | 固定版本 | Windows x86-64 / Python 3.12 结果 |
|---|---:|---|
| `tree-sitter` | 0.26.0 | 原生 cp312 wheel 可安装 |
| `tree-sitter-python` | 0.25.0 | cp310 abi3 wheel 可安装 |
| `tree-sitter-c` | 0.24.2 | cp310 abi3 wheel 可安装 |
| `tree-sitter-java` | 0.23.5 | cp39 abi3 wheel 可安装 |
| `tree-sitter-julia` | 0.23.1 | cp39 abi3 wheel 可安装 |

四种 grammar 与核心 ABI 的合成解析测试共执行 1,000 次：0 个 parse error，
232.24 ms，总平均 0.2322 ms/次，`tracemalloc` 峰值 3,063,906 bytes。该数字只
证明小样例的本机兼容性，不代表大型真实项目性能。

### 3.2 R 的包装缺口

官方 `r-lib/tree-sitter-r` 仓库包含 Python build 配置并采用 MIT，但 PyPI 当前
没有 `tree-sitter-r` distribution，配置的包索引也返回无匹配版本。因此它不能
像 C/Java/Julia 一样通过受支持的预编译 wheel 离线安装。两次浅克隆构建验证均因
本机到 GitHub 的连接失败而未能形成可复现 Windows wheel；这不是 parser 质量失败，
但仍是生产包装门禁失败。

`tree-sitter-language-pack==1.10.8` 有 Windows abi3 wheel，但隔离检查确认其 parser
按需从 GitHub release 下载并写本地 cache。它会引入约 5.1 MB 的本地绑定/SBOM、
运行时下载与额外缓存所有权，不符合 ResearchMind 默认本地、离线可复现和最小依赖
边界，因此不建议采纳。

## 4. 备选方案

### A. 推荐：混合适配器

- Python 保留标准库 AST，先做 parity 基线；
- C、Java、Julia 使用 `tree-sitter` 加各自独立官方 grammar wheel；
- R 使用项目内保守、非执行的 lexical adapter，首批只承诺 fixture 验证的
  `function` 与 `library`/`require`/namespace 引用；
- 所有适配器映射为项目自己的 `CodeSymbol`，vendor node 不离开 `code` 层。

优点是 Windows/Python 3.12 可离线安装，不增加运行时网络或自维护二进制。代价是
R 的首批符号范围比完整 grammar 窄，后续只有在官方 R wheel 或可复现构建证据充分
后才可替换 adapter。

### B. 暂缓 G6，等待官方 R wheel

技术整齐，但无法满足当前五语言目标，时间不确定。

### C. 采用 language-pack 并预下载 cache

可覆盖 R，但需要管理运行时下载能力、缓存路径、哈希、许可证和打包资产，依赖面
显著大于产品需求；本门禁拒绝。

### D. ResearchMind 自行构建/分发 R 二进制 wheel

可能获得统一 Tree-sitter 语义，但会让项目承担跨平台编译、ABI、许可证和供应链
维护；在没有可复现 CI/安装证据前不采纳。

## 5. 已完成的实现顺序

1. G6-B：加入 `CodeLanguage`、parser protocol 和 Python AST parity fixture；
2. G6-C：接入 C/Java/Julia adapter，扩展安全枚举和托管目录上传；
3. G6-D：实现保守 R adapter，完成五语言 fixture、错误降级和相对定位；
4. G6-E：接入现有代码阅读 UI/提示预览/显式笔记选择；
5. G6-F：运行无执行 sentinel、路径泄漏、限制/排除、AppTest、性能与全量回归，
   再进行人工验收。

## 6. 已确认的采纳门禁

用户确认方案 A 只授权以下生产依赖范围：

- `tree-sitter==0.26.*`
- `tree-sitter-c==0.24.*`
- `tree-sitter-java==0.23.*`
- `tree-sitter-julia==0.23.*`

不授权 `tree-sitter-language-pack`、运行时 grammar 下载、自建 R wheel、源码执行、
依赖安装器、编译/测试被阅读项目或扩大 T5-B1 写权限。


## 7. 生产实现

用户于 2026-09-16 明确确认方案 A。生产实现保持同一个 CodeProject /
CodeSelection / CodeContext 形状：

- .py 继续由标准库 AST 解析，既有符号输出 parity 保持；
- .c/.h、.java、.jl 由三个独立官方 grammar wheel 和 tree-sitter 核心解析，
  vendor node 只在 code/tree_sitter_parser.py 内；
- .r 由 code/r_parser.py 做保守词法定位，只承诺常见赋值函数、
  library/require 和 namespace 引用；
- CodeFile、选择、上下文、证据链接、提示预览和 Markdown 均显式携带语言与
  提取方式；语法树失败降级为同文件的显式文字行选择；
- 本地目录和托管上传统一接受 .py/.c/.h/.java/.jl/.r，继续执行原有上限、
  UTF-8、相对路径、隐藏/敏感/vendor/build 排除和 symlink containment；
- 非 Python 只读限制同时位于界面和应用用例层。T5-B1 仍只接受外部 Python
  选择，托管修订仍全部只读。

未采用 tree-sitter-python，因为 Python 保留标准库 AST；未采用
tree-sitter-r、language-pack、运行时下载、grammar cache 或自建 wheel。

## 8. 退出证据

- 22 项聚焦单元测试覆盖扩展名映射、五语言符号、Python parity、C/Julia
  类型、三种 Tree-sitter 语法错误降级、R 注释/字符串保守性、混合项目、
  无执行 sentinel、非 Python T5-B1 拒绝和 EvidenceLink 语言防篡改；
- 1 项资料库集成测试覆盖五语言托管导入、重启重开、语言汇总、敏感文件和
  vendor 排除；既有导入/修订/删除/恢复测试继续通过；
- 1 项 Java Streamlit AppTest 证明语言/提取方式可见且 T5-B1 控件不出现；
  全部 Streamlit AppTest 为 22/22；
- 五语言小样本共解析 2,000 次，277.51 ms，总平均 0.1388 ms/次，
  tracemalloc 峰值 66,485 bytes；这是本机合成性能证据，不外推到大型项目；
- 本地 wheel 构建成功，大小 1,080,710 bytes，包含四个新增 code 模块，
  METADATA 只声明批准范围内的 Tree-sitter 核心/C/Java/Julia 依赖；
- 最终生产测试为 **498 passed / 1 existing Windows symlink environment skip**；
  加入已采纳 G3 实验为 **597 passed / 1 skip**；
- compileall 与 git diff --check 通过。项目环境没有 Ruff，因此没有声称
  Ruff 结果。

## 9. 结论与后续

V3-G6 为 **Completed**。该结论只表示五语言静态阅读、选择、上下文、解释预览和
可选笔记证据进入现有架构；不表示编译、运行、依赖解析、调用图、Notebook、
C++ 或复现保证。下一主阶段是 V3-G7 加固与内部验收，尚未启动；本结论不自动
发布版本，也不扩大 T5-B1/T5-BX。
