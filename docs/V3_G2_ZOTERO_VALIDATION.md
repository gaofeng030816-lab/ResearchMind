# V3-G2 Zotero 只读连接验证记录

日期：2026-09-04

状态：**Completed；用户于 2026-09-04 明确确认“G2通过验收”，关闭本阶段人工门禁。**

基线：`2.0.0rc1` V2 Accepted + V3-G1 Completed。G3 不启动。

## 1. 决定与历史更正

- 用户于 2026-09-02 确认 GET-only Local API 方案。
- 当日 331 passed / 1 skipped / 14.18 秒是真实自动测试结果，但 HTTP-200 PDF
  模拟不能证明真实附件导入；此前“全部完成”的表述已撤回。
- 2026-09-04 官方协议复核：`/file` 返回 `302 file://`，
  `/file/view/url` 返回纯文本本地 URL；server identity 需要 Zotero 10+。
  当轮协议回归为 341 passed / 1 skipped / 15.29 秒，直接导入临时停用。
- 用户随后明确批准：只读复制选定、位于批准附件目录内的一个 PDF，拒绝
  网络路径、路径逃逸和符号链接，绝不修改 Zotero 原文件。
- 上传 GitHub 时暂停实现；本轮恢复 G2，新增下述 Windows 安全读取路径。
  没有新增第三方依赖、迁移或 Zotero 写权限。

协议依据：[Zotero Local API](https://www.zotero.org/support/dev/web_api/v3/local_api)。
Windows 句柄依据：[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
和 [GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)。

## 2. 当前数据流与权限

    默认关闭 → 显式浏览个人条目/附件
    → 配置批准目录 + 单附件逐次确认
    → GET 元数据和 /file/view/url
    → Windows 锁定祖先/文件句柄 → 有界只读 PDF 字节
    → 再查元数据/版本/URL → G1 解析/哈希/暂存/事务/托管副本
    → ZoteroSourceLink → 重启后从资料库重开

- 固定 `127.0.0.1:23119/api/`，禁用代理，GET-only，所有 HTTP 重定向仍拒绝。
- `ZOTERO_LOCAL_API_ENABLED=false` 默认关闭；不自动探测 localhost。
- `ZOTERO_ATTACHMENT_ROOT` 默认空，必须由用户填写批准的本地附件目录，
  不默认扫描或猜测 Zotero 路径。界面不显示私有路径，Settings repr 隐藏该字段。
- 复制确认绑定所选来源/版本/附件及配置目录指纹；重读详情、配置/附件变化、
  成功或失败均使旧复制操作失效。用例再次核对确认和配置指纹。
- 文件读取仅支持 Windows；其他系统/未配置时保持上传 PDF 后显式链接。
- URL/路径严格校验：拒绝 UNC、设备路径、网络盘、路径逃逸、非法组件、ADS、
  保留设备名、非 PDF、符号链接、junction、其他重解析点和硬链接。
- 从盘根到目标逐级 OPEN_REPARSE_POINT 打开；所有句柄在读取完成前不共享写入
  或删除，检查句柄最终路径、类型和大小，防止检查后替换/重命名。
- 有界读取并检查 PDF magic；G1 再检验可解析性/大小/hash。只复制，不改原件。
- 读取前后重验条目、附件快照及 URL；变化时拒绝并要求重新读取详情确认。
  这不是对 Zotero 数据库加锁或后台同步。
- 本地 URL/路径只在适配器栈内暂用，不写数据库、来源快照、prompt 或 Vault。
- schema 仍为 v2；只持久化用户选择的来源快照，不保存整库、对话或草稿。
- 重复来源关联先拒绝；相同 PDF 使用 G1 精确去重，不能静默改标已有来源。
- 来源链接失败时，新增托管副本通过既有移除/删除逻辑补偿；重复文件不删除。
  补偿失败可见，不宣称 SQL 可以回滚全部文件操作。
- unlink 只删除关系；删除已软移除记录的托管副本前须先解除链接。
- 不读 Zotero SQLite、不使用 Web API Key、不写 Zotero、不同步、不提供组资料库流。

## 3. 自动验证（本轮）

首次新增文件安全测试在实现前失败：缺少 local_files 模块；实现后通过。

| 检查 | 实际结果 |
|---|---|
| Windows 文件边界独立测试 | 24 passed，0.20 秒 |
| fake HTTP + 实际临时 PDF + G1/SQLite 完整复制/重启/补偿 | 6 passed，0.52 秒 |
| G2 相关用例/API/配置/AppTest 中间回归 | 68 passed，11.50 秒 |
| 增强后的逐次确认 AppTest | 1 passed / 17 deselected，2.62 秒 |
| 实现后完整回归 | 374 passed / 1 skipped，18.11 秒 |
| 最终差异复核后重跑 | **374 passed / 1 skipped，15.91 秒** |
| pip check | No broken requirements found |
| 五个相关 Skills 的官方 quick_validate.py | 均为 Skill is valid（使用本机已有 Python/PyYAML，不安装依赖） |

规则同步使用 skill-creator：只更新已批准读取边界和验收状态，不扩大权限。
git diff --check 通过；本轮复核时没有检测到监听 8500–8509 的 Streamlit。

完整命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-g2-local-copy-full
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-g2-copy-final-review
.\.venv\Scripts\python.exe -m pip check
```

跳过仍为既有 `tests/unit/test_code_change_writer.py:129` 的 Windows symlink
创建能力。新增 junction/硬链接和写入、删除、文件替换、祖先目录重命名冲突
测试均实际执行并通过，不以该 skip 代替安全证据。

所有测试仅使用 fake HTTP/LLM 和临时合成文件/数据库。未连接真实 Zotero，
未读取用户论文、Zotero 数据库或 .env 内容，也未修改真实配置。

证据分类：

- **协议**：纯文本 URL 路径、响应身份与大小、重定向拒绝、复制前后版本/URL 变化。
- **数据完整性/恢复**：实际 PDF 解析、托管导入、去重、重建 repository 后重开、
  原件字节/修改时间不变、来源解除/托管删除、来源写入失败补偿；原有迁移/备份回归。
- **安全**：危险 URL/路径、网络盘、真实 junction/hardlink、句柄共享冲突和释放。
- **UI**：无按钮不请求，目录/附件更换重置确认，复制成功/失败清理旧详情。
- **局限**：AppTest 不证明实际浏览器点击/文件选择体验；fake API 不证明桌面兼容。
  不把 API 成功宣称为论文识别质量；本轮未采用公式/新 PDF 组件。

## 4. 真实桌面验收（用户确认通过）

2026-09-04，用户在收到下述验收清单后明确回复“G2通过验收”。本记录以此
作为用户人工验收结论，关闭 G2；不是代理本轮重新运行 Zotero 的证明。用户未
提供逐项日志、Zotero 版本、截图或原件哈希，不补造这些数据。此前自动回归
374 passed / 1 skipped 保留原始执行记录；本次仅同步文档和规则，未重跑测试。

配置排障曾确认：相关设置写入了 .env.example，而实际 .env 缺失；已向用户
说明程序读取 .env。未记录私人目录或密钥，也不推断用户具体修改过程。

以下保留验收清单，便于未来回归：

先由用户指定批准附件目录、测试论文条目和单个 PDF；不自动选择私人资料。
需要 Zotero 10+ 的 server identity、Zotero 高级设置允许本机应用通信，以及
ResearchMind 明确启用开关。不要开放/转发 Local API 端口。

1. 配置独立 ResearchMind 数据目录及 ZOTERO_ATTACHMENT_ROOT；后者填写实际
   附件所在目录，不填整个磁盘/网络路径，也不把 ResearchMind 数据放进 Zotero。
2. 进入资料库，确认不会自动浏览或复制；点击读取条目，选择指定论文和附件。
3. 勾选本次只读复制确认并复制，核对 PDF 在 ResearchMind 可打开、来源身份正确。
4. 再次复制同一来源应有明确冲突提示；更换附件/目录后旧确认应失效。
5. 重启 ResearchMind 后重新打开托管 PDF、查看来源；关闭 Zotero 后本地阅读仍可用。
6. Zotero 关闭时显式读取应显示可恢复错误，不能展示可执行的旧复制操作。
7. 解除链接不删两侧文件；另行移除/删除测试托管副本后，Zotero 原件仍存在且未修改。

以上旅程由用户给出阶段级通过确认；不将其拆写为代理观测到的逐项测试结果。
**G2 Completed，G3 Pending。** 本次不提交/推送或创建 Release；未来如需代理
重新读取真实资料，仍须指定批准目录和测试附件。

## 5. 阅读入口、限制与回退

1. `integration/zotero/local_api.py`：GET 协议、快照重验、URL 到文件边界。
2. `integration/zotero/local_files.py`：Windows 文件句柄、路径/网络/别名拒绝。
3. `app/use_cases.py`：确认与配置作用域、G1 导入和来源失败补偿。
4. `app/views/library.py` / `app/state.py`：显式操作与确认失效。
5. `tests/integration/test_zotero_local_copy.py`：不依赖真实 Zotero 的完整数据流。

关闭 Zotero 开关或清空批准目录即可禁用直接复制，已有托管 PDF/来源不丢失。
锁冲突、云文件重解析点或不支持的平台使用手动上传后链接；不放宽安全边界。
V2 2.0.0rc1 独立基线、G1 schema/备份语义保持不变。
