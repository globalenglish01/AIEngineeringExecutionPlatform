# P7 — Workflow Engine 实现提示词（Workflow Engine Implementation Prompt）

> **发送时机**：P6 Provider 实现完成并通过 DoD 后发送。
> **本阶段目标**：实现 M3（Workflow Engine）。

---

## 提示词正文

```
现在实现 M3（Workflow Engine）。

Workflow Engine 是整个平台的核心调度系统。
它负责把"需求 → 规划 → 设计 → 执行 → 验证 → 修复 → 再验证"这个闭环自动化。

---

【任务 1】DAG（有向无环图）引擎

实现 workflow/dag.py：
- Node（节点）：包含 id、类型、输入、输出、执行函数
- Edge（边）：有向边，连接两个节点
- DAG：有向无环图，支持拓扑排序、循环检测
- 执行引擎：按拓扑顺序执行节点，支持并行执行无依赖节点
- 数据流：节点输出自动成为下游节点的输入

---

【任务 2】节点类型实现

实现 workflow/nodes/ 目录下的各种节点类型：

1. llm_node.py — LLM 调用节点
   - 通过 ProviderRegistry 调用 LLM
   - 支持 Prompt Template 插值
   - 记录调用日志

2. validation_node.py — 验证节点
   - 调用 Validation Engine 对上游输出进行验证
   - 验证失败时：根据配置决定是重试、修复还是中断

3. human_review_node.py — 人工审核节点
   - 暂停工作流，等待人工输入
   - 支持超时自动通过或自动拒绝

4. code_execution_node.py — 代码执行节点
   - 在沙箱中执行代码（subprocess + timeout）
   - 捕获输出和错误
   - 返回执行结果作为下游输入

5. branch_node.py — 条件分支节点
   - 根据上游输出的条件，选择不同的下游路径

6. loop_node.py — 循环节点
   - 支持"执行 → 验证 → 修复 → 再验证"的内循环
   - 配置最大循环次数和退出条件

7. parallel_node.py — 并行节点
   - 将任务分发给多个子节点并行执行
   - 等待所有子节点完成后聚合结果

---

【任务 3】Workflow 状态管理

实现 workflow/state.py：
- WorkflowRun：一次工作流执行的完整状态
- NodeRun：单个节点的执行状态
- 状态持久化：将执行状态保存到数据库（SQLite/PostgreSQL）
- 断点续跑：从最后一个成功节点继续执行（Resume）
- 历史查询：查询历史执行记录和每步输出

---

【任务 4】Retry 和错误处理

实现 workflow/retry.py：
- 指数退避重试（configurable：max_attempts、initial_delay、backoff_factor）
- 区分可重试错误（网络超时、API 限流）和不可重试错误（配置错误、权限问题）
- 重试日志记录

---

【任务 5】Plugin 钩子系统

实现 workflow/plugins.py：
- BeforeNodePlugin：在节点执行前调用
- AfterNodePlugin：在节点执行后调用
- OnErrorPlugin：在节点失败时调用
- 内置插件：LoggingPlugin、CostTrackingPlugin、BenchmarkPlugin

---

【任务 6】内置 Workflow 模板

实现以下常用 Workflow 模板（YAML 格式定义）：

1. workflows/templates/write_book_chapter.yaml
   - 需求分析 → 大纲生成 → 章节撰写 → 质量验证 → 修复循环 → 最终输出

2. workflows/templates/develop_feature.yaml
   - 需求分析 → 设计 → 代码生成 → 测试生成 → 执行测试 → 修复 → 再测试 → 代码审查

3. workflows/templates/data_analysis.yaml
   - 数据理解 → 分析方案设计 → 代码生成 → 执行 → 结果验证 → 报告生成

---

【任务 7】Workflow 测试

tests/unit/workflow/test_dag.py — DAG 基础测试
tests/unit/workflow/test_nodes.py — 各节点类型测试
tests/unit/workflow/test_state.py — 状态管理测试
tests/unit/workflow/test_retry.py — 重试机制测试
tests/integration/workflow/test_end_to_end.py — 端到端工作流测试

---

完成标准（对照 DoD）：
✓ DAG 能正确执行，拓扑排序正确
✓ 并行节点能并发执行
✓ 断点续跑：模拟中断后从断点恢复
✓ 重试机制：模拟失败后自动重试
✓ Plugin 钩子：日志和费用追踪插件正常工作
✓ 端到端测试：至少一个完整 Workflow 模板执行成功
✓ 单元测试覆盖率 ≥ 80%

每完成一个任务，立即运行测试并 git commit。
```

---

## 预期输出

- 完整的 Workflow Engine 实现代码
- 测试通过证明
- 至少一个端到端 Workflow 示例运行成功

## 下一步

完成后发送 **P8_AGENT_AND_MEMORY_IMPL.md** 中的提示词。
