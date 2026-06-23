# P4 — Provider 框架设计提示词（Provider Framework Design Prompt）

> **发送时机**：P3 验证优先设计文档获得确认后发送。
> **核心重点**：Browser Provider 的解耦设计，参照 D:\TestAgentPythonProject 中的实现思路。
> **禁止事项**：本阶段禁止写任何代码。

---

## 提示词正文

```
你是本项目的 Provider Architect（Provider 架构师）。

请完成 Provider Framework 的详细设计文档。

背景说明：
在本平台的参考项目（TestAgentPythonProject）中，已有一套 LLM 配置模型
（LLMSetting / APIKeyConfig），支持 deepseek / openai / anthropic / custom 等 provider，
并使用 Fernet 加密存储 API Key。本平台的 Provider Framework 需要在此基础上扩展，
重点是增加 Browser Provider 这一特殊实现。

---

任务 1：统一 Provider 接口设计

所有 Provider 必须实现相同的接口，包括：

```
interface LLMProvider:
    name: str                          # provider 唯一名称
    provider_type: ProviderType        # API / LOCAL / BROWSER

    async complete(
        messages: list[Message],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> CompletionResult

    async stream(
        messages: list[Message],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> AsyncIterator[StreamChunk]

    async count_tokens(messages: list[Message]) -> int

    async health_check() -> HealthStatus

    def get_cost(input_tokens: int, output_tokens: int) -> float
```

---

任务 2：Browser Provider 设计（重点）

Browser Provider 通过 Playwright 操作网页版 AI，封装成与 API Provider 完全相同的接口。

请设计以下内容：

1. 支持的目标网站（初期）：
   - ChatGPT（chat.openai.com）
   - DeepSeek Chat（chat.deepseek.com）
   - Claude.ai（claude.ai）
   - 其他：可通过配置扩展

2. Browser Provider 必须处理的场景：
   - 登录状态管理（Cookie 持久化，避免每次重新登录）
   - 会话管理（创建新会话、复用会话、清理历史）
   - 消息发送（文本、代码块）
   - 响应提取（流式提取、等待完成、提取纯文本 + 代码块）
   - 网络超时和重试
   - 反检测措施（stealth 模式、随机 delay）
   - 异常处理（页面崩溃、登录失效、请求频率限制）

3. 架构层次（不允许任何 Playwright 代码出现在核心引擎中）：
   ```
   Core Engine
       ↓ 调用统一接口
   ProviderRegistry
       ↓ 路由到具体实现
   BrowserProvider（实现 LLMProvider 接口）
       ↓ 使用
   BrowserSession（Playwright 封装层）
       ↓ 控制
   Playwright → 浏览器 → 网页版 AI
   ```

4. 配置格式（YAML 示例）：
   ```yaml
   providers:
     chatgpt_browser:
       type: browser
       target: chatgpt
       browser: chromium
       headless: true
       auth:
         method: cookie_file
         cookie_path: .secrets/chatgpt_cookies.json
       retry:
         max_attempts: 3
         delay_seconds: 5
       fallback: deepseek_api
   ```

5. Fallback 机制：
   - 当 Browser Provider 失败时，自动切换到配置的备用 Provider
   - 失败次数超过阈值时，临时禁用该 Provider 并告警
   - 支持手动和自动恢复

---

任务 3：ProviderRegistry 设计

设计一个 Provider 注册表，实现：
- 动态注册和发现 Provider
- 按 name / type / capability 查询 Provider
- Provider 健康状态监控
- 负载均衡（多个同类 Provider 之间的请求分发）
- 成本控制（设置每日/每月费用上限）

---

任务 4：Cost Tracking 设计

每次 LLM 调用必须记录：
- Provider 名称
- 模型名称
- Input tokens / Output tokens
- 费用（USD）
- 响应时间（ms）
- 成功/失败状态

支持按时间范围、Provider、任务类型汇总费用报告。

---

任务 5：与参考项目的对比分析

参考项目（D:\TestAgentPythonProject）中已有：
- LLMSetting 模型（存储 default_model、max_tokens、temperature）
- APIKeyConfig 模型（Fernet 加密存储 API Key，支持 deepseek/openai/anthropic/custom）

请说明本平台的 Provider Framework 如何在此基础上扩展，以及哪些设计需要改进。

---

输出格式：
1. 将上述任务合并输出为 docs/PROVIDER_FRAMEWORK_DESIGN.md
2. 包含 Mermaid 架构图
3. 包含 Browser Provider 的完整状态机图（登录 → 会话 → 发送 → 接收 → 完成）
4. 每个设计决策说明"为什么"和"如何扩展"

不要开始写代码。
```

---

## 预期输出

Claude Code 应输出并保存 `docs/PROVIDER_FRAMEWORK_DESIGN.md`。

## 下一步

完成后发送 **P5_CORE_ENGINE_IMPL.md** 中的提示词（第一个编码阶段）。
