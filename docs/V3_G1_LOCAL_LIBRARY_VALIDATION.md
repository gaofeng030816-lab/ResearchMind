# V3-G1 本地工作资料库与点击导入验证记录

日期：2026-09-01

状态：Completed

基线：已验收 `2.0.0rc1` + 可回退 V3-G1 source increment

当时的下一门禁：V3-G2 Zotero 只读连接，Pending confirmation（历史记录）。
2026-09-04 导航：G2 方案已确认，元数据/链接已实现；附件读取门禁与人工验收
未完成，见 [G2 当前验证记录](V3_G2_ZOTERO_VALIDATION.md)。下文保留 G1 当时证据。

## 1. 决定与范围

用户确认 G1 推荐方案后，本阶段采用 Python 标准库 sqlite3、单一显式
`RESEARCHMIND_DATA_DIR`、数据库元数据 + ResearchMind 托管文件，不使用 ORM、
数据库服务器或文件 blob。

已实现：

- schema version 1、迁移、结构校验、事务、外键和 repository；
- 稳定 LibraryRecord 与不可变 AssetReference 修订；
- 原生 Streamlit PDF/目录上传，并立即转换为项目自有 UploadedFileData；
- PDF magic/大小/哈希/可解析性校验；
- Python 目录的路径、类型、UTF-8、数量/大小和排除规则；
- 精确 live hash 去重、并发重复导入收敛和显式新修订；
- 暂存 → 数据库事务登记 → 原子完成资产 → commit，失败时回滚/补偿；
- 跨重启列出并重新打开论文/代码；
- 软移除/恢复与单独确认删除 ResearchMind 托管副本；
- SQLite snapshot + assets + checksummed manifest 的备份，以及验证后恢复到
  全新数据目录；
- 托管代码只读，阻止 T5-B1 造成数据库哈希/修订静默分叉。

未实现：

- Zotero Local/Web API、来源链接或 Zotero 缓存；
- PDF 浏览器文字层、划词翻译、CCv2/pdf.js 生产组件；
- 自动公式检测/识别、图片公式 OCR；
- C/Java/Julia/R 解析；
- Conversation、Selection、EvidenceLink、NoteDraft 或 Markdown 草稿持久化。

## 2. 当前数据流

    Streamlit file_uploader
    → view 转成 UploadedFileData（名称 + bytes）
    → use case
    → storage 验证/哈希/暂存
    → repository 事务登记 record + asset
    → storage 原子完成托管资产
    → SQLite commit
    → LibraryEntry
    → 从资料库打开既有 PDF / CodeContext 旅程

浏览器上传不提供可信原始绝对路径。数据库只存 ResearchMind ID、类型、哈希、
大小、媒体类型、相对托管路径、修订和时间；PDF/源码不作为 SQLite blob。

## 3. 文件所有权与恢复合同

- `RESEARCHMIND_DATA_DIR` 不能与 Vault 或导入代码项目重叠；
- `assets/` 只包含 ResearchMind 管理的验证后副本，`.staging/` 不对用户可见；
- “移除”只写 removed_at，可恢复且不删文件；
- “删除托管副本”要求记录已移除并再次确认，只影响 ResearchMind managed asset；
- 外部 PDF、外部代码目录、Zotero 附件和 Vault Markdown 永不随资料库删除；
- 备份不覆盖已有 ZIP；恢复目标必须不存在，并在完整路径/hash/schema 验证后
  原子命名；
- 安装或源码回滚不会自动删除/降级数据库，旧数据目录和备份应保留。

## 4. 自动验证证据

最终命令：

```powershell
& .\.venv\Scripts\python.exe -m compileall -q src tests scripts
& .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-v3-g1-final
& .\.venv\Scripts\python.exe -m pip check
```

结果：

- compileall：通过；
- pytest：`316 passed, 1 skipped in 14.99s`；
- skip：`tests/unit/test_code_change_writer.py:129`，当前 Windows 主机不支持
  创建 symlink；生产代码仍显式拒绝 symlink；
- pip check：`No broken requirements found.`；
- `git diff --check`：通过（仅显示 Windows 工作树未来 LF→CRLF 提示，无空白错误）；
- project-planner、python-engineering、research-context、pdf-research、
  research-library、testing-review、learning-mode 均通过 skill-creator
  `quick_validate.py`（Windows 下以 UTF-8 模式运行）。

测试覆盖包括：

- 新库创建、当前/未来/损坏 schema、迁移回滚、并发初始化和外键；
- repository 修订、精确哈希、软移除/恢复；
- PDF/代码上传、去重、显式修订、重启重开、失败补偿和并发重复导入；
- 安全相对路径、根目录归一化、排除、UTF-8、文件/总量上限；
- 删除托管副本、备份覆盖拒绝、ZIP tamper/traversal、目标存在拒绝；
- 配置诊断和 maintenance CLI；
- Streamlit AppTest 的资料库导航、论文/代码重开和托管代码无 T5-B1 控件；
- 完整 V2 PDF → 选择 → 翻译/LaTeX/解释 → 笔记 → Vault，以及外部代码项目
  的既有回归。

所有 routine 测试使用临时数据库、托管目录、项目和 Vault，以及 fake/mock
provider；没有调用真实 API、没有产生模型费用、没有读取用户资料库或 Vault。

## 5. 人工证据边界

Streamlit AppTest 不能选择浏览器原生文件选择器中的真实文件，因此自动证据把
“上传后的受限 bytes 处理”与“资料库 UI 导航/打开”分别验证。真实浏览器中的
点击/拖放、上传进度与大目录交互仍列入后续整体验收；本记录不把 AppTest 声称
为 DOM 文件选择证据。

## 6. 关键实现入口

- `src/researchmind/database/schema.py`
- `src/researchmind/database/repository.py`
- `src/researchmind/database/storage.py`
- `src/researchmind/database/backup.py`
- `src/researchmind/models/library.py`
- `src/researchmind/app/views/library.py`
- `src/researchmind/app/use_cases.py`
- `src/researchmind/maintenance.py`

V3-G1 完成不自动启动 G2，也不授权 Zotero HTTP adapter、缓存 schema、凭据或
附件写入。G2 需要单独确认其本地 API Spike 和只读边界。
