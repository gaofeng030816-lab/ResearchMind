# V3-G5 公式识别架构与质量门禁

日期：2026-09-13

状态：**Completed — 生产边界、质量证据、隐私约束与回退均已闭合；不启动 G6**

## 1. 结论

G5 采用窄的 provider-neutral `FormulaRecognizer` 边界，首个生产 adapter 复用已配置
的 OpenAI-compatible 视觉端点。检测和裁剪始终在本机完成，远程服务每次只接收一张
经用户预览并对精确 SHA-256 单独同意的 PNG crop。候选 LaTeX 是不可信、可编辑内容；
通过严格校验且由用户明确接受后才能渲染，也只有已接受内容可选择加入 G4 证据篮。

本阶段没有采用本地模型、模型权重、TensorFlow/PyTorch 运行时或整篇
PDF→LaTeX。当前能力是“单个公式候选辅助”，不是原论文 TeX 源码复原。

## 2. 已采用数据流

```text
managed/opened PDF revision + current page
  → local bounded FormulaRegion detector
  → user selects one region
  → server revalidates document revision/page/bbox
  → PyMuPDF renders one bounded in-memory PNG crop
  → exact crop preview + recognizer/model/privacy disclosure
  → per-crop external-transfer checkbox + explicit click
  → FormulaRecognizer returns untrusted candidate + provenance
  → strict LaTeX validation
  → editable candidate → explicit acceptance → local rendering
  → optional accepted-formula EvidenceSnapshot → G4 draft/Vault flow
```

Viewer、parser、detector、recognizer 与 document understanding 继续分离。
`app/views` 只显示并委托，`app/state.py` 独占 Streamlit 会话状态，
`app/use_cases.py` 负责重校验和编排，`pdf/formulas.py` 负责本地检测/crop，
`llm/formula_recognizer.py` 独占远程公式识别边界。

raw crop、未接受候选和 provider 原始响应不写 SQLite/Vault。已接受 LaTeX 进入证据
时携带 document/revision/page/bbox、detector、recognizer、model 与 crop hash；来源
变更后仍由 G4 current/stale/detached 规则处理。

## 3. 候选审计与采用决定

### LaTeX_OCR_PRO

只读审计确认其 GPL-3.0、Python 3.5 + TensorFlow 1.12/1.15、缺少 data submodule/
weights，并含 `shell=True` 和外部命令边界。没有复制、安装或执行其代码。仅以
clean-room 方式复用了“参考 LaTeX→固定 crop→token/结构/视觉多指标”的实验思路。
哈希与完整结论见 `candidate_audit.json`。

### pix2tex 0.1.4

PyPI wheel 的许可证为 MIT，但 wheel 不含权重，默认构造会下载未在包元数据中锁定
哈希的 `weights.pth`/`image_resizer.pth` 并跟随重定向；依赖包含 torch、
transformers、tokenizers、固定旧版 x-transformers/timm 等，且元数据未声明
Requires-Python。没有安装 wheel、执行候选或下载权重。Python 3.12/Windows、
CPU/GPU、模型大小、冷启动、离线供应链与固定语料质量均未证明，因此本地 adapter
延后，不阻塞远程 crop-only 方案。证据见 `local_candidate_audit.json`。

### dots3-note-prev crop-only

同一批 20 个 hash-locked 合成 crop 达到全部预设阈值，因此作为当前首个 adapter。
它仍由现有 LLM 配置提供，不成为 Core 依赖；将来通过门禁的本地实现可替换 adapter，
无需改动 FormulaRegion、同意、编辑、接受或证据合同。

## 4. 固定语料与质量

### 合成集

`corpus.tex` 自行定义 20 条许可自由公式，覆盖积分/围道积分、求和、乘积、极限、
分式、根式、希腊字母、上下标、偏导、向量、矩阵、cases/aligned、条件概率与公式
编号。Tectonic 编译后由 PyMuPDF 三倍渲染并做紧边界灰度裁剪；`corpus.json`
锁定来源和每个 PNG 的 SHA-256。

最终远程结果（`remote_predictions_v2.json`）：

| 指标 | 预设阈值 | 结果 |
|---|---:|---:|
| coverage | ≥ 85% | 100% |
| strict valid | 100% of returned | 100% |
| normalized exact | ≥ 75% | 95% |
| mean token similarity | ≥ 95% | 99.41% |
| structural exact | ≥ 90% | 100% |

评分只把空白、`\left`/`\right`、dfrac/tfrac 与单 token 上下标括号视作等价；
复合下标、符号、环境与数学结构不会被吞掉。

### 三篇真实论文

用户提供并授权 `1707.06347v2.pdf`、`2205.07246v3.pdf`、
`2507.04247v1.pdf` 用于本阶段受限评测；它们没有用于训练模型。报告只存来源 ID、
PDF/crop hash、page/bbox 与参考 LaTeX，不存私有路径或正文。

- detector：128 个初始候选收紧到 78 个（减少 39.06%），18/18 标注公式仍命中；
  10 条小型审计集准确率 70%，8 个不需要候选中拒绝 5 个；
- 已知 detector 失败：一个多公式合并、一个不完整片段和一个含 inline math 的正文
  块仍会出现，因此用户选区和 crop 预览不能取消；
- recognizer：18/18 返回、100% strict valid、95.09% mean token similarity、
  100% structural exact；
- normalized exact 仅 11.11%，主要来自 `\operatorname`/`\text`、可见标点、
  条件文字和等价排版选择。该结果明确阻止“原源码复原”宣传，并支持保留编辑/接受
  门禁；
- 5 条代表 crop 的视觉复核全部保留数学结构，其中 2 条带少量邻近内容；记录在
  `visual_spot_check_2026-09-13.json`，且明确不是一次独立用户“通过”声明。

## 5. 第五项失败复盘

首次真实请求有两条返回失败，其中第 5 个失败样本的 HTTP 请求和 PNG 均有效。
诊断显示响应以 `finish_reason=length` 截断：1600 completion-token 预算被隐藏
reasoning 大量消耗，最终 `content` 不完整；即使 `reasoning_effort=low`，
1600 仍不足。将公式专用上限设为 3200 并固定 low 后，两条均成功，最终为 18/18。

这不是 detector、crop 损坏或网络路径错误。生产仍把 timeout、连接、HTTP/API 和
坏响应转换为不含 crop、密钥、路径或原始 provider 内容的用户错误。真实运行平均
16.36 s，中位 12.62 s，单个长尾 77.63 s；因此识别保持显式单次操作，不做后台批量。

## 6. UI、隐私与浏览器证据

Edge 152 的独立假服务生产旅程通过 10/10：

1. 20 页合成 PDF 打开并定位目标页；
2. 本地 detector 只给出一个 bounded region；
3. crop 预览显示尺寸、bytes、精确 hash、recognizer/model 与外发范围；
4. 未同意前识别按钮禁用，且候选编辑器不存在；
5. 精确 crop 同意后只启用本次按钮；
6. 假 recognizer 收到一张 PNG，不含 PDF、路径、正文、历史或笔记；
7. 输出在接受前可编辑且未保存；
8. 接受后才渲染；
9. 只有已接受 LaTeX 可加入持久证据篮；
10. 页面 0 error，识别前 0 external request。

本轮重验时独立实例健康端点为 `200 / ok`，21 项 Streamlit AppTest 与 48 项 G5
聚焦测试通过。桌面浏览器控制内核异常退出，故没有把本轮失败的控制工具冒充新的
浏览器记录；采用证据仍是 2026-09-12 的完整 Edge 152 报告。

## 7. 测试与退出证据

- G5 聚焦：48 passed；
- Streamlit AppTest：21 passed；
- 生产全量：474 passed / 1 个既有 Windows symlink 环境 skip；
- 加两套已采纳 G3 PDF 实验：573 passed / 1 skip；
- 假服务请求边界：1 PNG、0 PDF、0 path、0 history；
- 合成/真实识别结果均不含 API key、私有路径、PDF bytes 或 raw provider response；
- 用户已授权这 18 个固定 crop 的远程评测，并允许独立验收实例；没有自动/批量
  外发，也没有复用同意到另一个 crop。

因此 G5 工程与质量门禁关闭。最终 V3 内部验收仍在 G7 重新执行完整人工旅程；本文
不伪造一次用户逐项“G5通过”回复。

## 8. 回滚与非目标

删除生产 formula models、`pdf/formulas.py`、recognizer adapter、use-case/state/UI
接线和对应测试即可回到 G4；schema 未因 G5 迁移，既有 G4 数据无需转换。已保存的
公式 EvidenceSnapshot 使用既有通用证据结构，回滚后仍能作为只读已保存内容处理。

不在 G5 范围：

- 整页/整篇 PDF→LaTeX、原论文 TeX 源码恢复或视觉完全一致保证；
- 自动外发、后台扫描、批量识别或训练；
- 本地 OCR 权重、扫描整页 OCR、语义表格/图表理解；
- 启动 G6 多语言代码或扩大代码执行/写入权限。
