# P8 — Agent 框架与记忆系统实现提示词（Agent & Memory Implementation Prompt）

> **发送时机**：P7 Workflow Engine 实现完成并通过 DoD 后发送。
> **本阶段目标**：实现 M5（Agent Framework）+ M6（Memory & Prompt Management）。

---

## 提示词正文

```
现在实现 M5（Agent Framework）和 M6（Memory & Prompt Management）。

这两个模块紧密相关，放在同一阶段实现。

---

【任务 1】Agent 基类实现

实现 agents/base_agent.py：

class BaseAgent:
    - name: str
    - role: str（角色描述，注入 System Prompt）
    - provider: LLMProvider（通过 ProviderRegistry 获取）
    - tools: list[Tool]（可使用的工具列表）
    - memory: MemoryStore（长短期记忆）
    - max_iterations: int（防止死循环）

    async def run(task: str, context: dict) -> AgentResult
    async def step(messages: list[Message]) -> AgentStep（单步执行）
    async def use_tool(tool_name: str, args: dict) -> ToolResult

---

【任务 2】Tool 系统

实现 agents/tools/ 目录：

1. base_tool.py — Tool 接口
   - name、description（供 LLM 理解的描述）
   - input_schema（JSON Schema，LLM 按此格式调用）
   - async execute(args: dict) → ToolResult

2. 内置工具：
   - file_tool.py：读写文件（read_file、write_file、list_files）
   - search_tool.py：代码搜索（grep、glob）
   - shell_tool.py：执行 shell 命令（带沙箱保护）
   - web_tool.py：网页抓取（使用 httpx + BeautifulSoup）
   - memory_tool.py：操作记忆（save_memory、search_memory）
   - validation_tool.py：调用 Validation Engine 验证当前输出

3. Tool 注册表（agents/tool_registry.py）：
   - 按名称注册和发现工具
   - 支持动态加载（从 YAML 配置文件加载工具定义）
   - 生成 LLM 可理解的 tool schema（OpenAI Function Calling 格式）

---

【任务 3】ReAct 推理循环

实现 agents/reasoning/react.py：

ReAct 循环（Reasoning + Acting）：
1. Thought：LLM 思考下一步做什么
2. Action：选择并调用工具
3. Observation：获取工具返回结果
4. 重复直到任务完成或达到 max_iterations

支持：
- 流式输出 Thought 过程
- 工具调用失败时自动重试（3次）
- 陷入循环时（相同 action 重复3次）自动切换策略

---

【任务 4】Multi-Agent 协作

实现 agents/multi_agent.py：

Supervisor 模式：
- SupervisorAgent：负责任务分解，分配给 WorkerAgent
- WorkerAgent：执行具体子任务，报告结果给 Supervisor
- 通信协议：结构化消息（JSON）

支持：
- 并行执行多个 WorkerAgent
- Worker 失败时 Supervisor 重新分配任务
- 最终聚合所有 Worker 结果

---

【任务 5】Memory System

实现 memory/ 目录：

1. memory/short_term.py — 短期记忆
   - 存储当前会话的对话历史
   - 自动裁剪超出 context window 的旧消息（保留最近 N 轮）
   - 支持摘要压缩（将旧对话压缩为摘要后继续）

2. memory/long_term.py — 长期记忆
   - 向量存储（使用 ChromaDB，本地持久化）
   - 保存重要事实、偏好、历史经验
   - 基于语义相似度检索相关记忆

3. memory/memory_store.py — 统一接口
   - save(content, metadata) → memory_id
   - search(query, k=5) → list[Memory]
   - forget(memory_id)
   - get_context_for_task(task) → str（为当前任务检索相关记忆，拼接成上下文）

---

【任务 6】Prompt Management

实现 prompts/ 目录：

1. prompts/template.py — Prompt 模板
   - 基于 Jinja2 的模板系统
   - 支持变量插值、条件、循环
   - 模板继承（Base Template + 专用 Template）

2. prompts/store.py — 模板存储
   - 从文件系统加载模板（.j2 文件）
   - 版本控制（每次修改自动创建版本）
   - 按名称和版本获取模板

3. prompts/optimizer.py — 提示词优化器
   - 基于历史得分，建议改进方向
   - A/B 测试：同一任务使用不同版本提示词，比较输出质量

4. prompts/library/ — 内置提示词库
   - system/architect.j2：系统架构师角色
   - system/engineer.j2：工程师角色
   - system/validator.j2：验证者角色
   - system/writer.j2：技术写作角色
   - tasks/analyze_requirement.j2：需求分析
   - tasks/write_chapter.j2：写书章节
   - tasks/generate_code.j2：代码生成
   - tasks/review_code.j2：代码审查
   - tasks/validate_output.j2：输出验证

---

【任务 7】内置 Agent 实现

基于上述基础设施，实现以下专用 Agent：

1. agents/builtin/architect_agent.py
   - 角色：系统架构师
   - 专长：需求分析、架构设计、技术选型
   - 工具：search_tool、web_tool、file_tool

2. agents/builtin/engineer_agent.py
   - 角色：软件工程师
   - 专长：代码生成、重构、测试编写
   - 工具：file_tool、shell_tool、validation_tool

3. agents/builtin/writer_agent.py
   - 角色：技术写作专家
   - 专长：文档撰写、章节创作、内容优化
   - 工具：file_tool、web_tool、validation_tool

4. agents/builtin/validator_agent.py
   - 角色：质量验证专家
   - 专长：代码审查、内容评分、问题定位
   - 工具：validation_tool、shell_tool、file_tool

---

【任务 8】测试

tests/unit/agents/test_base_agent.py
tests/unit/agents/test_tools.py
tests/unit/agents/test_react.py
tests/unit/memory/test_short_term.py
tests/unit/memory/test_long_term.py
tests/unit/prompts/test_template.py
tests/integration/agents/test_multi_agent.py

---

完成标准（对照 DoD）：
✓ ReAct 循环：Agent 可以完成一个简单的多步任务（如：读文件 → 分析 → 写结果）
✓ Tool 调用：至少 file_tool 和 shell_tool 工作正常
✓ Short-term Memory：对话历史正确管理，超出时自动裁剪
✓ Long-term Memory：save 和 search 功能正常，ChromaDB 持久化
✓ Prompt Template：Jinja2 模板渲染正确，变量插值正常
✓ Multi-Agent：Supervisor + 2个 Worker 完成并行任务
✓ 单元测试覆盖率 ≥ 80%

每完成一个任务，立即运行测试并 git commit。
```

---

## 预期输出

- Agent Framework 完整实现
- Memory System 完整实现
- Prompt Management 完整实现
- 内置 Agent 可以执行实际任务

## 下一步

完成后发送 **P9_VALIDATION_BENCHMARK_IMPL.md** 中的提示词。
