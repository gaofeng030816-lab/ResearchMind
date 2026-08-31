# T6-B 安装、配置、升级回滚与备份恢复验证

日期：2026-08-30
状态：Completed（T6 总阶段仍为 Active）
基线：V1.3.2 + T1/T3/T4/T5-A/T6-A/T6-B 内部增量，不对外发布

## 1. Problem / Before / After

**Before**：

- 安装说明以开发用 editable venv 为主，没有空环境非 editable 证据；
- 配置错误只会在具体功能调用时暴露，缺少不联网、不泄密的集中检查；
- README 只建议备份整个 Vault，没有 ResearchMind Markdown 的可校验恢复演练；
- 没有真实包工件的升级/回滚演练。

**After**：

- 应用和 CLI 都可由用户显式运行本地配置诊断；
- 诊断不联网、不显示 Key、不显示绝对 Vault 路径，也不创建目录；
- 可生成只含 ResearchMind `.md`、版本化 manifest、大小和 SHA-256 的新 ZIP；
- 恢复会完整预检归档，并只写入一个尚不存在的新 Vault 子目录；
- 空 venv 非 editable 安装、依赖导入、`pip check`、配置检查和备份恢复已演练；
- 真实 Git 基线 wheel → 当前 wheel → 基线 wheel 已离线切换，包外 Markdown
  哈希始终不变。

## 2. 实现边界

新增：

- `models/maintenance.py`：非敏感诊断与备份/恢复结果模型；
- `maintenance.py`：`diagnose / backup / restore` 本地 CLI；
- `integration/obsidian/backup.py`：Markdown 归档、manifest、哈希和恢复；
- `validate_vault_destination()`：只读 Vault 目标校验；
- `app/views/configuration.py`：用户点击后才运行的配置检查。

保持不变：

- `config.py` 仍是环境变量和 secrets 的唯一读取入口；
- `integration/obsidian/` 仍是唯一 Vault 写入边界；
- 不增加第三方依赖、数据库、后台服务或 T5-B 工具；
- 不备份 Key、PDF、代码、图片或任意 Vault 内容；
- 不调用真实 LLM，也不执行科研代码。

## 3. 备份与恢复安全规则

- 归档必须是新建 `.zip`，绝不覆盖；
- 只递归读取配置输出子目录中的普通 `.md`，遇到符号链接即拒绝；
- 上限为 10,000 个 Markdown、总解压体量 500 MB、manifest 1 MB；
- manifest 记录格式版本、应用版本、相对路径、大小和 SHA-256；
- 恢复拒绝重复成员、加密成员、符号链接、路径穿越、非 Markdown、
  清单不一致、大小不一致和哈希不一致；
- 所有内容验证完成后先写 Vault 内临时目录，再重命名为目标目录；
- 目标子目录必须不存在，父目录必须已存在，因此不会合并或覆盖现有笔记。

定向 ZIP 是整个 Obsidian Vault 备份的补充，不替代用户既有 Vault 备份方案。

## 4. Regression-first 证据

实现前命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_configuration_diagnostics.py tests\unit\test_obsidian_backup.py tests\unit\test_maintenance_cli.py tests\e2e\test_streamlit_app.py -q --basetemp=.pytest-tmp-t6b-red
```

结果：收集阶段 4 个预期错误，分别缺少 `researchmind.maintenance`、
`VaultBackupError` 和配置诊断模型。

实现后聚焦命令覆盖诊断、备份恢复、CLI、既有 Vault 写入、配置和 Streamlit：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\unit\test_configuration_diagnostics.py tests\unit\test_obsidian_backup.py tests\unit\test_maintenance_cli.py tests\unit\test_obsidian_vault.py tests\unit\test_config.py tests\e2e\test_streamlit_app.py -q --basetemp=.pytest-tmp-t6b-focused-1
```

结果：`39 passed in 11.81s`。

## 5. 真实配置诊断

对当前 `.env` 运行：

```powershell
& .\.venv\Scripts\python.exe -m researchmind.maintenance diagnose --env-file .env
```

Python、配置格式、LLM 端点格式、LLM 凭据完整性、Obsidian Vault 和资源限制
六项均为 `OK`。该命令没有联网或显示凭据。

首次输出出现乱码后，CLI 明确把 stdout/stderr 配置为 UTF-8；重跑中文可读。

## 6. 干净安装、升级与回滚演练

所有操作位于系统临时目录，结束后按已验证的 temp 根路径清理；未写真实 Vault。

### 6.1 发现并解释的安装失败

首次空 venv 安装使用本机全局清华 pip 镜像，在构建隔离阶段报告找不到
`setuptools>=75`。进一步检查发现该镜像对任意 setuptools 查询都返回无版本；
官方 PyPI 可见 `75.0.0` 到 `84.0.0` 等版本，因此不是项目约束写错。

显式使用官方索引后，当前工作树在空 Python 3.12 venv 中通过非 editable 安装。
随后一次旧基线安装因代理连接重置失败。最终演练把网络依赖限定在首次安装/
构建 wheel，升级与回滚改用本地 wheel 离线执行。

### 6.2 最终成功证据

- `pip install <workspace>`（显式可用索引）：成功；
- 必需依赖与 `researchmind 0.1.0` 导入：成功；
- `pip check`：`No broken requirements found.`；
- JSON 配置诊断：6 项 `ok`、`has_errors=false`；
- 1 个 Markdown 备份/恢复：成功，源与恢复 SHA-256 相同；
- Git `c46201e` 基线 wheel：安装后没有 T6-B maintenance 模块；
- 强制安装当前 wheel：maintenance 模块存在，`pip check` 通过；
- 再安装 `c46201e` wheel：maintenance 模块消失；
- 整个旧→新→旧周期后，包外 Markdown SHA-256 不变。

当前与基线的包版本字段均为 `0.1.0`，因此本证据验证的是 wheel 文件替换、
回滚可达性和数据不变性；最终版本号和正式版本迁移矩阵仍属于 T6-D。

## 7. 最终自动化验证

最终审阅补充了“候选 Vault 子目录解析到 Vault 外部”边界测试。首次单测已证明
生产实现会拒绝该路径，失败原因只是测试期待了不同错误文案；调整为现有项目
错误语义后通过，因此没有为这项审阅修改生产逻辑。

- Vault 真实路径越界与备份恢复聚焦测试：`6 passed in 0.23s`；
- 全量 pytest：`237 passed in 9.65s`；
- `python -m compileall -q src tests scripts experiments`：退出码 0；
- 当前环境 `python -m pip check`：`No broken requirements found.`；
- routine tests 使用临时 Vault，不读取真实 `.env`、不调用真实 API；
- 干净安装演练使用假凭据和临时 Vault。
- `skill-creator` 官方 `quick_validate.py`：六个 ResearchMind 项目 Skill 全部
  `Skill is valid!`；
- API 密钥模式扫描（排除 `.env` 与 `.git`）：无命中；
- T6-B 旧状态检索：仅命中 T6-A 历史验证文档中的历史状态；
- `git diff --check`：无空白错误，仅报告现有 Windows 换行转换提示。

## 8. 当时遗留与后续状态

T6-B 完成时的遗留如下：

- 当时真实浏览器中的配置面板视觉与窄窗口体验尚未人工验收；后续由用户在
  T6-C 明确人工确认通过，未伪报自动浏览器证据；
- 后续 T6-C 已完成更完整的隐私/安全检查、性能基准和错误恢复场景；
- 当前定向恢复不合并已有目录，用户需要在新目录中人工比较，这是有意的
  非覆盖策略；
- 尚无签名发布工件、正式升级矩阵或冻结版本号，它们属于 T6-D。

后续 T5-B1 也已按独立合同完成一个已选 Python 行范围的受控替换；代码执行、
Shell、测试和安装权限仍未授权。当前下一阶段是 T6-D。
