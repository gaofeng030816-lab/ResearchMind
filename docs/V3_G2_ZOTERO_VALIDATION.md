# V3-G2 Zotero 只读连接验证记录

日期：2026-09-04

状态：Active；元数据/来源链接已实现，直接附件导入停用；本地文件读取门禁和真实 Zotero 人工验收待完成

基线：`2.0.0rc1` V2 Accepted + V3-G1 Completed

## 1. 协议复核与更正

2026-09-02 的 331 passed、1 skipped、14.18 秒是当时实际自动测试结果，但当时
“实现与自动门禁完成”的结论过度：下载测试使用 HTTP-200 PDF 字节响应，未覆盖
真实 Local API 的附件行为。该结论由本记录更正，不能作为 G2 完成依据。

2026-09-04 复核 [Zotero 官方 Local API 文档](https://www.zotero.org/support/dev/web_api/v3/local_api)：

- `/items/<key>/file` 返回 `302` 跳转到本机 `file://`，不是 PDF 字节流；
- `/file/view/url` 返回本地 URL 文本；同样需要一个明确的文件读取安全边界；
- `Zotero-Server-ID` 的支持范围为 Zotero 10+。当前 adapter 强制稳定身份，
  缺失时安全失败，不假设老版本兼容，不生成伪身份；
- 用户需在 Zotero 高级设置中启用本机应用访问，并独立启用 ResearchMind 开关；
  不开放或转发 Local API 端口。

结论：真实附件导入尚未实现。直接导入按钮已停用；当前可用替代路径是
“G1 点击上传 PDF → 显式浏览 Zotero 条目 → 链接已有论文”。所有重定向继续拒绝。
留在 download/import 用例中的 HTTP-200 字节处理只属于原型，不能称为实际
Zotero PDF 导入；没有自动跟随 `file://` 或读取其路径。

## 2. 已实现与批准边界

- 固定 `http://127.0.0.1:23119/api/`、关闭代理、GET-only、有界响应和路径校验；
- `ZOTERO_LOCAL_API_ENABLED=false`；只有点击浏览或读取附件元数据才请求，
  启动、进入资料库、诊断、常规测试均不探测真实 Zotero；
- 个人资料库最近条目/搜索、选中条目 PDF 附件元数据、显式 link/unlink；
- schema v2 保存 server/library/item/version 与选中来源快照，v1 数据库和备份
  可迁移；浏览结果和附件列表仅在会话内；
- 来源关系不等于 PDF 内容哈希相同；已有来源关联不能被“再次导入”静默改标；
- UI 确认绑定来源、版本、目标论文和附件，切换后重置；读取失败清除旧详情；
- 外部标题/作者按文本显示；来源不会自动进入 AI prompt 或 Vault；
- 先软移除，存在来源链接时须先 unlink，才可独立确认删除托管副本；
- unlink 不删除任一侧文件；导入原型的补偿失败会给出可见错误，不静默忽略；
- Zotero 禁用、离线、identity 变化、缺失身份、损坏响应与不支持协议均有项目错误。

未采用 Web API、凭据、组资料库产品流、整库缓存、后台同步、Zotero 写操作，
也未读取 Zotero SQLite 或新增第三方运行时依赖。G3 不启动。

## 3. 本轮自动验证

最终全量命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-v3-g2-protocol-full-0904
```

结果：**341 passed，1 skipped，15.29 秒**。

跳过项：`tests/unit/test_code_change_writer.py:129`，既有 Windows symlink 能力
不可用。测试只用 fake HTTP/LLM 与临时资料，未访问真实 localhost/Zotero/用户数据。

| 类别 | 自动证据与局限 |
|---|---|
| HTTP/协议 | API v3、server ID、GET 路径、字段映射；拒绝 HTTP 跳转和路径逃逸 |
| 官方附件行为 | 仿真 `302 file://` 经真实 urllib handler 栈被拒绝，FileHandler 不可打开文件；错误不带私有路径 |
| 字节处理原型 | fake HTTP-200 的 PDF type/magic/大小和 G1 导入流程；不证明真实 Local API 导入 |
| 失败模式 | 403 disabled、412 identity changed、offline、malformed JSON、缺失身份、错误 API 版本 |
| 数据与恢复 | schema v1→v2、旧记录/外键/唯一来源身份、快照、unlink、重启、v1 备份迁移与篡改保护 |
| 文件所有权 | 已关联来源冲突不静默改标；unlink 后才删除已移除记录的托管副本，外部原件不受影响 |
| Streamlit AppTest | 初始 0 请求；browse/details 独立按钮；附件改变需要重新确认；失败清旧详情；直接导入始终禁用 |
| V2/G1 回归 | PDF、代码、笔记、托管资料库与受控写入路径包含在 341 项完整通过的套件中 |

其他检查：

- `.venv\Scripts\python.exe -m pip check`：No broken requirements found。
- project-planner、research-library、python-engineering、testing-review、learning-mode
  五个修改的 Skill 使用官方 quick_validate.py 验证；均有效。使用本机已有
  Anaconda Python 的 `-X utf8` 模式和已有 PyYAML，不安装新包。
- 规则、架构、产品、规划、README 和历史文档导航已同步；历史 V1/V2/G1 测试
  数字保留原始语境，不伪装成当前结果。
- `git diff --check` 通过；仅有仓库既有 LF/CRLF 转换提示。

这些是自动/静态证据，不等于真实 Zotero 或浏览器人工验收。

## 4. 待确认的本地附件读取边界（G2 内补充门禁）

建议批准后实现：

1. 仍只请求所选个人条目的一个 PDF 附件地址，不枚举磁盘、不读取整库。
2. 用户单独确认读取该附件；文件必须在用户批准的附件根目录内。
3. 拒绝 UNC/网络地址、路径逃逸、符号链接/重解析点、设备路径和非 PDF；
   只读打开并防止校验与读取之间被替换。路径不入日志、数据库或 AI prompt。
4. 校验大小、PDF magic/可解析性；通过 G1 暂存、哈希、事务和原子完成流程
   复制一份 ResearchMind 托管副本；绝不修改/删除 Zotero 原文件。
5. 补齐 Windows 路径与竞态安全测试，再启用导入 UI，进行真实 Zotero 验收。

这仍属于 Active G2，不是新主阶段。该方案尚未获批或实现；本轮没有读取
任何 Zotero 返回的文件地址。若不能批准此边界，则需要另行明确缩减 G2 退出
标准为上传后链接，不能默默把直接附件导入标记完成。

## 5. 人工验收（尚未执行）

当前可以先验收元数据/来源链接：

1. 使用支持 server identity 的 Zotero 版本，在高级设置启用本机应用通信；
   将 ResearchMind 的 `ZOTERO_LOCAL_API_ENABLED=true` 后重启。
2. 用自行选择的测试 PDF 点击上传；进入本地资料库，点击读取条目。
3. 选择个人条目并读取附件列表；确认没有自动连接或复制附件。
4. 链接已有论文，切换附件时重新确认，重启后核对来源和论文仍可打开。
5. 解除链接，确认 Zotero 条目/附件及 ResearchMind PDF 均仍存在。
6. 关闭 Zotero 再点击读取，确认出现可恢复错误且普通本地资料库继续可用。
7. 直接导入目前应禁用；它的成功/失败/重启/原件不变验收需在补充门禁实现后做。

当前未启动或重启 ResearchMind/Zotero，也未修改用户 .env 或读取真实资料库。
G2 的文件读取决定、实现与真实人工证据均关闭前保持 Active，不启动 G3。

## 6. 阅读入口与回退

- `src/researchmind/integration/zotero/local_api.py`：HTTP 信任边界与拒绝重定向；
- `src/researchmind/app/use_cases.py`：来源关联、冲突、删除门禁及原型编排；
- `src/researchmind/app/views/library.py`：显式按钮、确认与停用导入提示；
- `src/researchmind/database/schema.py`：schema v2 与迁移。

对初学者：来源链接就像“这份论文对应 Zotero 哪张卡片”的登记，不会自动复制
PDF，也不证明两份 PDF 字节相同。关闭 Zotero 开关即可停用入口；无需删除
数据库或托管文件。V2 2.0.0rc1 独立冻结基线未改写；本轮未提交或公开发布。
