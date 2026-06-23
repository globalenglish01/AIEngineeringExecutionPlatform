# P6 — Provider 实现提示词（Provider Implementation Prompt）

> **发送时机**：P5 核心引擎骨架实现完成并通过 DoD 后发送。
> **本阶段目标**：实现 M4（Provider Framework），重点是 Browser Provider。

---

## 提示词正文

```
现在实现 M4（Provider Framework）。

请基于 core/interfaces/provider.py 中定义的 LLMProvider 接口，
实现以下所有 Provider：

---

【任务 1】API Provider 实现

1. providers/api/openai_provider.py
   - 实现 complete 和 stream 方法
   - 支持所有 OpenAI 兼容的模型（GPT-4o、GPT-4 等）
   - 使用 openai Python SDK
   - 实现 count_tokens（tiktoken）
   - 实现 get_cost（基于官方定价）

2. providers/api/anthropic_provider.py
   - 实现 complete 和 stream 方法
   - 使用 anthropic Python SDK
   - 实现 count_tokens
   - 实现 get_cost

3. providers/api/deepseek_provider.py
   - DeepSeek 兼容 OpenAI 接口，可复用 OpenAI Provider
   - base_url 设置为 https://api.deepseek.com/v1
   - 支持 deepseek-chat 和 deepseek-coder 模型

4. providers/api/custom_provider.py
   - 支持任意 OpenAI 兼容接口（自定义 base_url + api_key）

---

【任务 2】Local Provider 实现

1. providers/local/ollama_provider.py
   - 通过 Ollama REST API 调用本地模型
   - 支持流式输出
   - health_check 检查 Ollama 服务是否运行
   - get_cost 返回 0.0（本地模型无费用）

---

【任务 3】Browser Provider 实现（重点）

重要约束：
- providers/browser/ 目录下的代码是唯一可以 import playwright 的地方
- core/ 和 workflow/ 等目录中不能出现任何 playwright 引用
- Browser Provider 对外表现与 API Provider 完全一致

实现以下文件：

1. providers/browser/session.py — 浏览器会话管理
   - 管理 Playwright 浏览器实例的生命周期
   - Cookie 持久化（保存/加载登录状态）
   - 支持 headless 和有头模式
   - 会话池（复用已有会话，避免频繁创建）

2. providers/browser/base_browser_provider.py — Browser Provider 基类
   - 实现 LLMProvider 接口
   - 封装通用的：发送消息、等待响应、提取文本的逻辑
   - 实现 Fallback（当浏览器操作失败时抛出 ProviderError）
   - count_tokens 使用 tiktoken 估算（因为无法从网页获取精确值）
   - get_cost 返回 0.0（网页版免费）

3. providers/browser/targets/chatgpt.py — ChatGPT 网页版
   - 登录状态检测
   - 新建对话
   - 发送消息（支持长文本分段发送）
   - 等待并提取 AI 响应（流式提取，直到响应完成）
   - 处理：rate limit 提示、网络错误、页面刷新
   - 参考实现思路：与 D:\TestAgentPythonProject 中 UI Agent 的 Playwright 使用方式类似

4. providers/browser/targets/deepseek.py — DeepSeek Chat 网页版
   - 与 chatgpt.py 结构相同，但针对 DeepSeek 网页的 DOM 结构实现

5. providers/browser/targets/claude_ai.py — Claude.ai 网页版
   - 与 chatgpt.py 结构相同，但针对 Claude.ai 的 DOM 结构实现

6. providers/browser/browser_provider.py — 统一入口
   - 根据配置的 target 名称，路由到对应的 target 实现
   - 支持热切换目标网站（不重启服务）

---

【任务 4】Provider 集成测试

为每个 Provider 编写集成测试：
- tests/integration/providers/test_openai_provider.py
- tests/integration/providers/test_deepseek_provider.py
- tests/integration/providers/test_ollama_provider.py
- tests/integration/providers/test_browser_provider.py

Browser Provider 测试注意：
- 使用 pytest.mark.browser 标记，默认跳过（需要真实浏览器环境）
- 提供 mock 测试（mock Playwright，测试消息解析逻辑）

---

【任务 5】Fallback 和 Cost Tracking 实现

1. providers/fallback.py — Fallback 链
   - 按优先级尝试多个 Provider
   - 失败时记录日志并切换
   - 临时禁用连续失败的 Provider（Circuit Breaker 模式）

2. providers/cost_tracker.py — 费用追踪
   - 每次调用后记录：provider、model、input_tokens、output_tokens、cost、duration
   - 持久化到 SQLite（开发环境）或 PostgreSQL（生产环境）
   - 提供费用汇总查询接口

---

完成标准（对照 DoD）：
✓ 所有 Provider 实现 LLMProvider 接口的全部方法
✓ Browser Provider 中没有任何代码出现在 providers/browser/ 目录之外
✓ API Provider 的集成测试通过（使用真实 API Key，从环境变量读取）
✓ Browser Provider 的 mock 测试通过
✓ Fallback 机制在主 Provider 失败时正确切换
✓ 每次调用都有 Cost 记录
✓ 单元测试覆盖率 ≥ 80%

每完成一个 Provider，立即运行测试并 git commit。
```

---

## 预期输出

- 完整的 Provider 实现代码
- 测试通过证明

## 下一步

完成后发送 **P7_WORKFLOW_ENGINE_IMPL.md** 中的提示词。
