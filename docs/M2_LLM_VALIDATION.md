# M2 LLM 模块验证记录

日期：2026-08-27

## 实现范围

- `LlmProvider` 协议与 provider-neutral `ChatMessage`。
- 四种解释 Prompt：concept、math、algorithm、contextual。
- 一种追问 Prompt：followup。
- OpenAI 兼容 Provider、统一响应解析、超时/API/坏响应错误映射与配置工厂。
- 支持标准 `Authorization` 和 Dots Studio `api-key` 两种受限鉴权头配置。
- V1 请求只允许文本生成参数，拒绝 tools、function calling、web search 和 streaming。

`DEVELOPMENT_PLAN.md` 总览中的“五个解释 prompt + 追问 prompt”与任务明细及 `architecture.md` 不一致；本实现以架构源文件为准，实现四种解释模式和一种 follow-up，共五个 builder。

## 自动化验证

- M2/Dots 专项测试：42 passed。
- 全量回归：71 passed。
- 测试通过注入的假 completion 函数运行，不读取用户 `.env`，不访问网络，不产生 API 费用。
- 覆盖 Prompt 注入隔离、历史消息降权、最小上下文字段、SDK 请求转换、安全参数白名单、超时/API 错误映射、空响应、畸形响应、工厂配置和密钥错误信息脱敏。

## 手动验证状态

没有执行真实 LLM API 调用。真实调用可能发送论文上下文并产生费用，当前任务没有包含对外发送数据或消费 API 额度的明确授权；待用户配置端点、模型和 Key 并明确同意后再执行一次手动验收。
