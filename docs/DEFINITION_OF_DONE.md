# AI Engineering Execution Platform — 完成定义（Definition of Done）

> **版本**：v0.1（P2 阶段产出）  
> **角色**：质量负责人（Quality Gatekeeper）  
> **基于**：[ARCHITECTURE.md](ARCHITECTURE.md) · [MILESTONE_PLAN.md](MILESTONE_PLAN.md)  
> **核心原则**：没有自动验证机制的模块视为设计未完成；DoD 必须可量化、可自动验证；进入下一里程碑前当前里程碑所有 DoD 必须 100% 通过  
> **日期**：2026-06-23

---

## 目录

1. [全局 DoD（所有模块共用）](#1-全局-dod所有模块共用)
2. [Workflow Engine DoD](#2-workflow-engine-dod)
3. [Agent Framework DoD](#3-agent-framework-dod)
4. [Provider Framework DoD](#4-provider-framework-dod)
5. [Validation Engine DoD](#5-validation-engine-dod)
6. [Memory System DoD](#6-memory-system-dod)
7. [Prompt Management DoD](#7-prompt-management-dod)
8. [Artifact Management DoD](#8-artifact-management-dod)
9. [Benchmark System DoD](#9-benchmark-system-dod)
10. [里程碑通关检查清单](#10-里程碑通关检查清单)
11. [自动化验证工具说明](#11-自动化验证工具说明)

---

## 1. 全局 DoD（所有模块共用）

每个里程碑完成时，以下条件必须 **全部通过**，无一例外：

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| 单元测试通过 | `uv run pytest tests/ -x --tb=short` | 0 个失败，0 个错误 |
| 类型检查通过 | `uv run mypy platform/` | 输出 `Success: no issues found` |
| 代码格式通过 | `uv run ruff check platform/ tests/` | 输出 `All checks passed.` |
| 新增代码覆盖率 | `uv run pytest --cov=platform --cov-report=term-missing` | 新增模块覆盖率 ≥ 80% |
| 无硬编码密钥 | `grep -rE "(api_key|password|secret)\s*=\s*['\"][^'\"]{8,}" platform/` | 输出为空 |
| 无 Playwright 泄漏 | `grep -r "playwright" platform/ --include="*.py" --exclude-path="platform/providers/browser/*"` | 输出为空 |
| Git 提交规范 | `git log --oneline -5` | 每个功能点独立 commit，消息格式：`type: description` |
| CHANGELOG 更新 | `grep "M[0-9]" CHANGELOG.md` | 当前里程碑条目存在 |

**自动化检验脚本**：
```bash
# scripts/check_dod.sh（在每个里程碑结束时运行）
uv run pytest tests/ -x --tb=short --cov=platform --cov-fail-under=80
uv run mypy platform/
uv run ruff check platform/ tests/
grep -rE "(api_key|password|secret)\s*=\s*['\"][^'\"]{8,}" platform/ && exit 1
grep -r "playwright" platform/ --include="*.py" \
  $(find platform/providers/browser -name "*.py" | sed 's/^/--exclude=/') && exit 1
echo "✅ 全局 DoD 通过"
```

---

## 2. Workflow Engine DoD

> **对应里程碑**：M3  
> **对应提示词**：P7_WORKFLOW_ENGINE_IMPL.md

### 2.1 DoD 明细表

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| **DAG — 基础执行** | `pytest tests/unit/workflow/test_dag.py::test_linear_execution` | 3 节点线性 DAG 按顺序执行完成 |
| **DAG — 循环检测** | `pytest tests/unit/workflow/test_dag.py::test_cycle_detection` | 含环 DAG 抛出 `CyclicDependencyError` |
| **DAG — 拓扑排序** | `pytest tests/unit/workflow/test_dag.py::test_topological_sort` | 输出节点顺序满足所有依赖关系 |
| **Retry — 次数上限** | `pytest tests/unit/workflow/test_retry.py::test_max_attempts` | 失败 3 次后抛出 `MaxRetriesExceededError` |
| **Retry — 指数退避** | `pytest tests/unit/workflow/test_retry.py::test_exponential_backoff` | 重试间隔序列为 [1s, 2s, 4s]（±10%） |
| **Retry — 可重试分类** | `pytest tests/unit/workflow/test_retry.py::test_non_retryable` | `ConfigurationError` 不触发重试，立即失败 |
| **Resume — 断点保存** | `pytest tests/integration/workflow/test_resume.py::test_checkpoint_saved` | 每个节点完成后，状态持久化到 SQLite |
| **Resume — 断点恢复** | `pytest tests/integration/workflow/test_resume.py::test_resume_from_checkpoint` | 模拟节点 3 完成后进程崩溃，重启后从节点 4 继续，节点 1-3 不重复执行 |
| **Event — 下游触发** | `pytest tests/unit/workflow/test_events.py::test_downstream_triggered` | 节点 A 完成后，事件总线触发节点 B、C 开始执行 |
| **Plugin — Before 钩子** | `pytest tests/unit/workflow/test_plugins.py::test_before_hook_called` | BeforeNode 钩子在节点执行前被调用，调用顺序正确 |
| **Plugin — After 钩子** | `pytest tests/unit/workflow/test_plugins.py::test_after_hook_called` | AfterNode 钩子接收到节点输出，可读取结果 |
| **Plugin — OnError 钩子** | `pytest tests/unit/workflow/test_plugins.py::test_error_hook_called` | 节点抛出异常时 OnError 钩子被调用，正常节点不触发 |
| **Log — 结构化日志** | `pytest tests/unit/workflow/test_logging.py` | 每步日志含 `trace_id`、`node_id`、`status`、`duration_ms` 字段 |
| **Log — 可追溯** | 手动验证：执行一个 3 节点工作流，查看日志 | 可通过 `trace_id` 过滤出完整执行链路 |
| **Parallel — 并发执行** | `pytest tests/unit/workflow/test_parallel.py::test_concurrent_execution` | 3 个无依赖节点，各耗时 1s，总耗时 ≤ 1.5s（串行则 ≥ 3s） |
| **Parallel — 结果聚合** | `pytest tests/unit/workflow/test_parallel.py::test_result_merge` | 3 个并行节点的输出均被正确聚合到下游节点的输入 |
| **Schedule — 定时触发** | `pytest tests/unit/workflow/test_schedule.py::test_cron_trigger` | cron 表达式 `*/1 * * * *` 在 mock 时钟下每分钟触发一次 |
| **Benchmark — 耗时记录** | `pytest tests/unit/workflow/test_benchmark.py::test_duration_recorded` | 每个节点执行后，`NodeRun.duration_ms` 有值且 > 0 |
| **Benchmark — 得分记录** | `pytest tests/unit/workflow/test_benchmark.py::test_score_recorded` | 验证节点完成后，`WorkflowRun.quality_score` 被更新 |
| **Test — 覆盖率** | `pytest --cov=platform/workflow --cov-report=term` | `platform/workflow/` 覆盖率 ≥ 80% |

### 2.2 端到端验收测试

```
测试名称：test_write_book_chapter_workflow_e2e
测试内容：使用 write_book_chapter.yaml 模板，mock LLM 节点，
          验证节点返回分数 72（低于 Hard Gate 75），触发修复循环，
          第二次验证节点返回分数 82（通过），工作流成功结束
期望结果：WorkflowRun.status == "COMPLETED"
          WorkflowRun.loop_iterations == 2
          最终 Artifact 的 quality_score == 82
```

---

## 3. Agent Framework DoD

> **对应里程碑**：M5  
> **对应提示词**：P8_AGENT_AND_MEMORY_IMPL.md（前半）

### 3.1 DoD 明细表

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| **Tool Use — 注册** | `pytest tests/unit/agents/test_tool_registry.py::test_register_and_get` | 注册工具后可按名称取出，schema 完整 |
| **Tool Use — 调用** | `pytest tests/unit/agents/test_tools.py::test_file_tool_read` | `FileTool.execute({"action":"read","path":"x.txt"})` 返回文件内容 |
| **Tool Use — 错误处理** | `pytest tests/unit/agents/test_tools.py::test_tool_error_wrapped` | 工具执行失败时返回 `ToolResult(success=False, error=...)` 而非抛出异常 |
| **Tool Use — Schema 生成** | `pytest tests/unit/agents/test_tool_registry.py::test_openai_schema_format` | 生成的 tool schema 符合 OpenAI Function Calling 格式，可被 JSON Schema 验证 |
| **Memory — 短期接入** | `pytest tests/unit/agents/test_base_agent.py::test_short_term_memory_used` | Agent 第 2 轮对话时，消息列表包含第 1 轮历史 |
| **Memory — 长期接入** | `pytest tests/unit/agents/test_base_agent.py::test_long_term_memory_injected` | Agent 启动时，`get_context_for_task()` 返回的记忆被注入 System Prompt |
| **Planning — ReAct 循环** | `pytest tests/unit/agents/test_react.py::test_three_step_task` | Agent 完成「读文件→分析→写结果」3 步任务，Thought/Action/Observation 各出现 ≥ 1 次 |
| **Planning — 循环检测** | `pytest tests/unit/agents/test_react.py::test_loop_detection` | 相同 action+args 出现 3 次时，Agent 中止并返回 `AgentResult(status="loop_detected")` |
| **Planning — max_iterations** | `pytest tests/unit/agents/test_react.py::test_max_iterations_respected` | 设置 `max_iterations=5`，迭代 5 次未完成时强制返回，不无限循环 |
| **Multi-Agent — 任务分解** | `pytest tests/integration/agents/test_multi_agent.py::test_supervisor_decomposes_task` | SupervisorAgent 将任务拆成 ≥ 2 个子任务，分配给不同 Worker |
| **Multi-Agent — 并行执行** | `pytest tests/integration/agents/test_multi_agent.py::test_workers_run_parallel` | 2 个 Worker 并行执行，总时间 ≤ 最慢 Worker × 1.3 |
| **Multi-Agent — Worker 失败** | `pytest tests/integration/agents/test_multi_agent.py::test_worker_failure_handled` | Worker 失败时 Supervisor 重新分配或标记子任务失败，整体任务不崩溃 |
| **Streaming — 流式输出** | `pytest tests/unit/agents/test_base_agent.py::test_streaming_output` | `agent.run(stream=True)` 返回 `AsyncIterator`，第一个 chunk 在 LLM 完全响应前到达 |
| **Error Recovery — 工具重试** | `pytest tests/unit/agents/test_react.py::test_tool_retry_on_failure` | 工具调用失败时自动重试最多 3 次，3 次均失败后 Agent 换策略 |
| **Provider Agnostic — 切换** | `pytest tests/unit/agents/test_base_agent.py::test_provider_switch` | 将 Agent 的 provider 从 `openai` 换为 `deepseek`，Agent 代码无需修改，行为一致 |
| **Test — 覆盖率** | `pytest --cov=platform/agents --cov-report=term` | `platform/agents/` 覆盖率 ≥ 80% |

### 3.2 内置 Agent 验收

| Agent | 验收命令 | 通过标准 |
|-------|---------|---------|
| ArchitectAgent | `pytest tests/integration/agents/test_builtin_agents.py::test_architect` | 给定需求描述，输出含「模块」「接口」「数据流」关键词的分析结果 |
| EngineerAgent | `pytest tests/integration/agents/test_builtin_agents.py::test_engineer` | 给定功能描述，调用 FileTool 写出可运行的 Python 函数（mock Provider） |
| WriterAgent | `pytest tests/integration/agents/test_builtin_agents.py::test_writer` | 给定主题，输出字数 ≥ 200 的结构化技术说明（mock Provider） |
| ValidatorAgent | `pytest tests/integration/agents/test_builtin_agents.py::test_validator` | 给定 Artifact，调用 ValidationTool 返回含评分的验证报告 |

---

## 4. Provider Framework DoD

> **对应里程碑**：M4  
> **对应提示词**：P6_PROVIDER_IMPL.md

### 4.1 DoD 明细表

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| **Unified Interface — 接口完整** | `pytest tests/unit/providers/test_interface_compliance.py` | 所有已注册 Provider 类通过接口合规检查（`isinstance(p, LLMProvider)` + 5 个方法均存在） |
| **Unified Interface — 返回格式一致** | `pytest tests/unit/providers/test_interface_compliance.py::test_return_type_consistent` | 所有 Provider 的 `complete()` 返回 `CompletionResult`，字段齐全 |
| **API Provider — OpenAI** | `pytest tests/integration/providers/test_openai.py -m "not slow"` | 使用真实 API Key（从环境变量读取），调用 `gpt-4o-mini`，返回非空文本 |
| **API Provider — Anthropic** | `pytest tests/integration/providers/test_anthropic.py -m "not slow"` | 使用真实 API Key，调用 `claude-haiku-4-5-20251001`，返回非空文本 |
| **API Provider — DeepSeek** | `pytest tests/integration/providers/test_deepseek.py -m "not slow"` | 使用真实 API Key，调用 `deepseek-chat`，返回非空文本 |
| **Local Provider — Ollama 健康检查** | `pytest tests/unit/providers/test_ollama.py::test_health_check_unhealthy` | Ollama 服务未启动时，`health_check()` 返回 `HealthStatus.UNHEALTHY`（不抛出异常） |
| **Local Provider — Ollama 调用** | `pytest tests/integration/providers/test_ollama.py -m "requires_ollama"` | Ollama 运行时（标记跳过），调用本地模型返回非空文本 |
| **Browser Provider — Playwright 隔离** | `grep -r "playwright" platform/ --include="*.py" --exclude-path="platform/providers/browser/*"` | 输出为空（零泄漏） |
| **Browser Provider — 登录状态管理** | `pytest tests/unit/providers/browser/test_session.py::test_cookie_save_and_load` | Cookie 保存到文件后，新 Session 加载 Cookie，`is_logged_in()` 返回 True（mock） |
| **Browser Provider — 会话保持** | `pytest tests/unit/providers/browser/test_session.py::test_session_reuse` | 同一 Session 对象第 2 次调用不重新创建页面，`page_creation_count == 1` |
| **Browser Provider — 响应提取** | `pytest tests/unit/providers/browser/test_response_extraction.py` | mock DOM 含代码块时，提取结果包含纯文本和代码块分离的结构 |
| **Browser Provider — 自动重试** | `pytest tests/unit/providers/browser/test_browser_provider.py::test_auto_retry` | 操作失败时自动重试 3 次，3 次均失败后抛出 `ProviderError` |
| **Browser Provider — mock 测试** | `pytest tests/unit/providers/browser/ -m "not browser_live"` | 所有 mock 测试通过（不需要真实浏览器） |
| **Fallback — 自动切换** | `pytest tests/unit/providers/test_fallback.py::test_fallback_on_error` | 主 Provider 抛出 `ProviderError` 时，自动切换到备用 Provider，返回成功结果 |
| **Fallback — 全部失败** | `pytest tests/unit/providers/test_fallback.py::test_all_providers_fail` | Fallback 链全部失败时，抛出 `AllProvidersFailedError`，包含每个 Provider 的失败原因 |
| **Circuit Breaker — OPEN 状态** | `pytest tests/unit/providers/test_circuit_breaker.py::test_opens_after_failures` | 连续失败 3 次后，`provider.circuit_state == "OPEN"`，后续调用直接失败（不重试） |
| **Circuit Breaker — 半开恢复** | `pytest tests/unit/providers/test_circuit_breaker.py::test_half_open_recovery` | OPEN 状态 60 秒后（mock 时钟）变为 HALF_OPEN，下次调用成功后变为 CLOSED |
| **Cost Tracking — 记录** | `pytest tests/unit/providers/test_cost_tracker.py::test_call_recorded` | 每次 `complete()` 后，`CostTracker.get_last_record()` 含 provider/model/tokens/cost/duration |
| **Cost Tracking — 查询** | `pytest tests/unit/providers/test_cost_tracker.py::test_total_cost_query` | 调用 3 次后，`CostTracker.total_cost()` 等于 3 次费用之和（精度误差 < 0.0001） |
| **Test — 每个 Provider 独立测试** | `pytest tests/unit/providers/ tests/integration/providers/ -m "not browser_live and not requires_ollama"` | 全部通过，覆盖率 ≥ 80% |

---

## 5. Validation Engine DoD

> **对应里程碑**：M7  
> **接口植入于**：M2（`platform/core/interfaces/validator.py`）  
> **对应提示词**：P9_VALIDATION_BENCHMARK_IMPL.md（前半）

### 5.1 DoD 明细表

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| **Score — 输出范围** | `pytest tests/unit/validation/test_engine.py::test_score_range` | `ValidationResult.total_score` 始终在 [0, 100]，不超出边界 |
| **Score — 加权计算** | `pytest tests/unit/validation/test_engine.py::test_weighted_score` | 2 个验证器权重 [0.6, 0.4]，得分 [80, 70]，总分 = 76.0（± 0.01） |
| **Rule — JSON Schema** | `pytest tests/unit/validation/test_schema_validator.py::test_invalid_json_detected` | 缺少必填字段的 JSON 返回含字段名的错误信息 |
| **Rule — 字数规则** | `pytest tests/unit/validation/test_rule_validator.py::test_min_words` | 800 字内容对 `min_words: 1000` 规则返回 `ValidationIssue(severity="error")` |
| **Rule — 结构规则** | `pytest tests/unit/validation/test_rule_validator.py::test_required_sections` | 缺少「最佳实践」章节时返回具体缺失章节名称 |
| **Rule — 自定义函数** | `pytest tests/unit/validation/test_rule_validator.py::test_custom_function_rule` | YAML 中定义的 Python 表达式规则正确执行 |
| **LLM Judge — 多次调用** | `pytest tests/unit/validation/test_llm_validator.py::test_multiple_calls` | mock LLM 被调用 3 次，取中位数作为最终分 |
| **LLM Judge — 防抖** | `pytest tests/unit/validation/test_llm_validator.py::test_high_variance_triggers_more_calls` | 3 次得分方差 > 15 时，自动增加到 5 次调用 |
| **LLM Judge — 维度评分** | `pytest tests/unit/validation/test_llm_validator.py::test_dimension_scores` | `ValidationResult.dimension_scores` 含 `factual_accuracy`/`completeness`/`readability` ≥ 3 个维度 |
| **LLM Judge — JSON 强制输出** | `pytest tests/unit/validation/test_llm_validator.py::test_json_output_enforced` | 即使 LLM 返回文本夹杂分数，也能正确解析出 `{"total_score": X}` 格式 |
| **Human Review — 暂停等待** | `pytest tests/unit/validation/test_human_review.py::test_workflow_paused` | 遇到 HumanReview 节点时，WorkflowRun.status 变为 `PAUSED` |
| **Human Review — 超时默认** | `pytest tests/unit/validation/test_human_review.py::test_timeout_default_decision` | 超过 timeout 时，按配置的 `default_decision`（pass/fail）继续 |
| **Diff — 版本对比** | `pytest tests/unit/validation/test_diff.py::test_quality_diff` | 版本 1 得分 72，版本 2 得分 85，diff 输出 `+13` 且列出改进维度 |
| **Gate — Hard Block** | `pytest tests/unit/validation/test_quality_gate.py::test_hard_gate_blocks` | 总分 70 < Hard Gate 75，返回 `GateDecision.BLOCK`，含阻断原因 |
| **Gate — Soft Warn** | `pytest tests/unit/validation/test_quality_gate.py::test_soft_gate_warns` | 总分 78 < Soft Target 90，返回 `GateDecision.WARN`，不阻断 |
| **Gate — Pass** | `pytest tests/unit/validation/test_quality_gate.py::test_gate_pass` | 总分 92 ≥ Hard 75，返回 `GateDecision.PASS` |
| **Gate — YAML 配置加载** | `pytest tests/unit/validation/test_quality_gate.py::test_yaml_config_loaded` | 从 `gates/book_chapter.yaml` 加载门禁配置，阈值与文件一致 |
| **Report — Markdown 输出** | `pytest tests/unit/validation/test_report.py::test_markdown_report` | 输出含「总分」「各维度得分」「问题列表」「建议」四个 H2 章节 |
| **Report — 结构化 JSON** | `pytest tests/unit/validation/test_report.py::test_json_report` | JSON 报告可被 ValidationReport JSON Schema 验证通过 |
| **Test — 覆盖率** | `pytest --cov=platform/validation --cov-report=term` | `platform/validation/` 覆盖率 ≥ 80% |

---

## 6. Memory System DoD

> **对应里程碑**：M6  
> **对应提示词**：P8_AGENT_AND_MEMORY_IMPL.md（后半）

### 6.1 DoD 明细表

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| **Short-term — 存储** | `pytest tests/unit/memory/test_short_term.py::test_add_and_get` | 添加 5 条消息，`get_messages()` 返回 5 条，顺序一致 |
| **Short-term — 自动裁剪** | `pytest tests/unit/memory/test_short_term.py::test_auto_trim` | 设置 `max_messages=10`，添加 15 条后，`get_messages()` 返回最新 10 条 |
| **Short-term — 摘要压缩** | `pytest tests/unit/memory/test_short_term.py::test_summarize_on_overflow` | 设置 `summarize=True`，溢出时旧消息被压缩为一条摘要消息（mock LLM） |
| **Long-term — 保存** | `pytest tests/unit/memory/test_long_term.py::test_save_and_persist` | 保存记忆后，重启 MemoryStore（重新加载 ChromaDB），记忆仍可检索 |
| **Long-term — 语义检索** | `pytest tests/unit/memory/test_long_term.py::test_semantic_search` | 保存「asyncio 最佳实践」记忆，搜索「Python 并发」返回该记忆（相似度 > 0.7） |
| **Long-term — 关键词检索** | `pytest tests/unit/memory/test_long_term.py::test_keyword_search` | 搜索精确关键词「ChromaDB」返回包含该词的记忆，不含该词的不返回 |
| **Context Window — 自动管理** | `pytest tests/unit/memory/test_memory_store.py::test_context_window_management` | `get_context_for_task()` 返回内容总 token 数 ≤ 配置的 `max_context_tokens` |
| **Forget — 主动遗忘** | `pytest tests/unit/memory/test_memory_store.py::test_forget` | `forget(memory_id)` 后，`search()` 不再返回该记忆（即使语义高度相关） |
| **Forget — 不影响其他** | `pytest tests/unit/memory/test_memory_store.py::test_forget_only_target` | 遗忘 A 后，与 A 相似的 B 仍可正常检索 |
| **Test — 覆盖率** | `pytest --cov=platform/memory --cov-report=term` | `platform/memory/` 覆盖率 ≥ 80% |

---

## 7. Prompt Management DoD

> **对应里程碑**：M6  
> **对应提示词**：P8_AGENT_AND_MEMORY_IMPL.md（后半）

### 7.1 DoD 明细表

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| **Version Control — 自动版本** | `pytest tests/unit/prompts/test_store.py::test_auto_version_on_save` | 第 1 次保存版本号为 1，第 2 次修改后版本号为 2 |
| **Version Control — 历史列表** | `pytest tests/unit/prompts/test_store.py::test_list_versions` | `list_versions("write_chapter")` 返回所有版本及各版本的历史得分 |
| **Template — 变量插值** | `pytest tests/unit/prompts/test_template.py::test_variable_interpolation` | `{{ artifact.title }}` 被正确替换为传入值 |
| **Template — 条件渲染** | `pytest tests/unit/prompts/test_template.py::test_conditional_rendering` | `{% if context.previous_errors %}` 在有错误时渲染，无错误时不渲染 |
| **Template — 循环渲染** | `pytest tests/unit/prompts/test_template.py::test_loop_rendering` | `{% for section in outline %}` 正确渲染 3 个章节 |
| **Template — 继承** | `pytest tests/unit/prompts/test_template.py::test_template_inheritance` | 子模板继承父模板后，父模板的 system_prefix 出现在渲染结果中 |
| **A/B Test — 权重分配** | `pytest tests/unit/prompts/test_ab_test.py::test_weight_distribution` | 配置 A(60%)/B(40%)，模拟 1000 次选择，A 被选 560-640 次（95% 置信区间） |
| **A/B Test — 得分记录** | `pytest tests/unit/prompts/test_ab_test.py::test_score_recorded_per_variant` | 使用变体 A 完成任务后，`get_variant_scores("A")` 包含该次得分 |
| **Score Tracking — 历史得分** | `pytest tests/unit/prompts/test_store.py::test_score_history` | 为版本 2 记录 3 次得分，`get_version_score("write_chapter", 2)` 返回平均值 |
| **Rollback — 回滚** | `pytest tests/unit/prompts/test_store.py::test_rollback` | `rollback("write_chapter", version=1)` 后，`get("write_chapter")` 返回版本 1 的内容 |
| **内置库 — 文件完整** | `pytest tests/unit/prompts/test_library.py::test_all_templates_loadable` | `platform/prompts/library/` 下所有 `.j2` 文件可被 Jinja2 加载，无语法错误 |
| **内置库 — 渲染无错误** | `pytest tests/unit/prompts/test_library.py::test_all_templates_render` | 所有模板使用样例数据渲染，无 UndefinedError |
| **Test — 覆盖率** | `pytest --cov=platform/prompts --cov-report=term` | `platform/prompts/` 覆盖率 ≥ 80% |

---

## 8. Artifact Management DoD

> **对应里程碑**：M8  
> **对应提示词**：P9_VALIDATION_BENCHMARK_IMPL.md 中的 Artifact 部分

### 8.1 DoD 明细表

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| **Storage — 保存与读取** | `pytest tests/unit/artifacts/test_store.py::test_save_and_load` | 保存 2000 字 Artifact，`load(id)` 返回内容 sha256 与原文一致 |
| **Storage — 大文件** | `pytest tests/unit/artifacts/test_store.py::test_large_artifact` | 1MB 内容保存到文件系统（不进数据库），元数据含文件路径 |
| **Storage — 小内容** | `pytest tests/unit/artifacts/test_store.py::test_small_artifact_in_db` | < 10KB 内容直接存入 SQLite，无文件系统文件生成 |
| **Version — 新版本** | `pytest tests/unit/artifacts/test_versioning.py::test_new_version_created` | 修改内容后保存，`list_versions(id)` 返回 2 个版本记录 |
| **Version — 历史质量分** | `pytest tests/unit/artifacts/test_versioning.py::test_quality_score_history` | 版本 1 得分 72，版本 2 得分 85，历史记录包含两次得分 |
| **Diff — 文本差异** | `pytest tests/unit/artifacts/test_versioning.py::test_diff_output` | `diff(v1_id, v2_id)` 输出包含增加行（+）和删除行（-）的 unified diff 格式 |
| **Export — Markdown** | `pytest tests/unit/artifacts/test_exporters.py::test_markdown_export` | 导出文件扩展名为 `.md`，内容与 Artifact.content 一致 |
| **Export — ZIP** | `pytest tests/unit/artifacts/test_exporters.py::test_zip_export` | ZIP 文件包含所有相关 Artifact 文件，解压后目录结构正确 |
| **Lifecycle — 状态流转** | `pytest tests/unit/artifacts/test_lifecycle.py::test_status_transitions` | DRAFT → REVIEW → PUBLISHED 状态流转正常；PUBLISHED → DRAFT 被拒绝 |
| **Lifecycle — 归档** | `pytest tests/unit/artifacts/test_lifecycle.py::test_archive` | PUBLISHED Artifact 可归档，归档后内容只读（修改操作被拒绝） |
| **Search — 关键词** | `pytest tests/unit/artifacts/test_search.py::test_full_text_search` | 搜索「asyncio」返回含该词的 Artifact，不含该词的 Artifact 不出现 |
| **Search — 元数据过滤** | `pytest tests/unit/artifacts/test_search.py::test_metadata_filter` | 按 `type=BOOK_CHAPTER` 过滤，返回结果全部为书籍章节类型 |
| **Test — 覆盖率** | `pytest --cov=platform/artifacts --cov-report=term` | `platform/artifacts/` 覆盖率 ≥ 80% |

---

## 9. Benchmark System DoD

> **对应里程碑**：M9  
> **对应提示词**：P9_VALIDATION_BENCHMARK_IMPL.md（后半）

### 9.1 DoD 明细表

| 项目 | 验证方式 | 通过标准 |
|------|---------|---------|
| **Baseline — 建立** | `pytest tests/unit/benchmark/test_tracker.py::test_baseline_set` | 首次运行 Suite 后，`get_baseline("book_chapter_suite")` 返回得分记录 |
| **Baseline — 更新策略** | `pytest tests/unit/benchmark/test_tracker.py::test_baseline_update` | 得分提升时自动更新 Baseline；得分下降时保持原 Baseline |
| **Regression — 检测告警** | `pytest tests/unit/benchmark/test_regression.py::test_regression_detected` | mock 返回低于 Baseline 10+ 分时，`check_regression()` 返回 `RegressionAlert` |
| **Regression — 无误报** | `pytest tests/unit/benchmark/test_regression.py::test_no_false_positive` | 得分比 Baseline 低 3 分（在容差内），不触发告警 |
| **Regression — 阻断 CI** | `pytest tests/unit/benchmark/test_ci.py::test_ci_blocks_on_regression` | `ci_benchmark.py --compare main` 在检测到回归时退出码为非 0 |
| **Leaderboard — 排序** | `pytest tests/unit/benchmark/test_leaderboard.py::test_ranking_by_score` | 2 个 Provider，得分 85 的排在得分 79 的前面 |
| **Leaderboard — 多维度** | `pytest tests/unit/benchmark/test_leaderboard.py::test_multi_dimension_display` | 排行榜包含「总分/准确性/可读性/费用」4 列数据 |
| **Time Series — 数据积累** | `pytest tests/unit/benchmark/test_tracker.py::test_time_series_data` | 运行 3 次后，`get_trend("book_chapter_suite")` 返回含 3 个时间点的列表 |
| **Time Series — 趋势方向** | `pytest tests/unit/benchmark/test_tracker.py::test_trend_direction` | 3 次得分 [75, 80, 85]，`trend.direction == "improving"` |
| **Report — Markdown 生成** | `pytest tests/unit/benchmark/test_reporter.py::test_markdown_report` | 报告含「总览」「各 Task 得分」「与 Baseline 对比」「排行榜」4 个章节 |
| **Report — JSON 生成** | `pytest tests/unit/benchmark/test_reporter.py::test_json_report` | JSON 报告可被 BenchmarkReport JSON Schema 验证通过 |
| **Alert — 质量下降告警** | `pytest tests/unit/benchmark/test_alerting.py::test_quality_alert_fired` | 回归检测触发后，`AlertManager.get_alerts()` 包含 `type="quality_regression"` 的告警 |
| **Alert — 费用告警** | `pytest tests/unit/benchmark/test_alerting.py::test_budget_alert` | 累计费用超过配置 `max_cost_usd: 10` 时，触发 `type="budget_exceeded"` 告警 |
| **内置套件 — 可加载** | `pytest tests/unit/benchmark/test_suites.py::test_builtin_suites_loadable` | `book_chapter.yaml` 和 `code_generation.yaml` 均可被 BenchmarkSuite 加载，无 Schema 错误 |
| **Test — 覆盖率** | `pytest --cov=platform/benchmark --cov-report=term` | `platform/benchmark/` 覆盖率 ≥ 80% |

---

## 10. 里程碑通关检查清单

在进入下一个里程碑之前，运行以下清单，**所有项目必须打勾**：

### M2 Core Engine 通关清单

```
[ ] uv run pytest tests/unit/core/ -x                         通过，0 失败
[ ] uv run mypy platform/core/                                 零错误
[ ] uv run ruff check platform/core/                           零警告
[ ] platform/core/interfaces/ 下 4 个接口文件存在              ls 确认
[ ] LLMProvider 接口含 5 个方法（complete/stream/count_tokens/health_check/get_cost）
[ ] Validator 接口含 validate() 方法，签名与 ARCHITECTURE.md 一致
[ ] 配置系统从 config.yaml 加载成功（pytest 集成测试验证）
[ ] 结构化日志输出含 trace_id 字段（pytest 验证）
[ ] pytest --cov=platform/core --cov-fail-under=80             覆盖率 ≥ 80%
[ ] 全局 DoD 检查脚本通过（scripts/check_dod.sh）
```

### M3 Workflow Engine 通关清单

```
[ ] M2 通关清单全部通过（前提）
[ ] DAG 循环检测测试通过
[ ] 并行节点执行时间测试通过（3节点并行，总时间 ≤ 1.5s）
[ ] Resume 断点恢复测试通过（模拟崩溃后从断点继续）
[ ] 重试指数退避间隔测试通过
[ ] Plugin 钩子（Before/After/OnError）测试通过
[ ] LoggingPlugin 输出含 trace_id 字段
[ ] write_book_chapter 工作流模板端到端测试通过（mock LLM）
[ ] pytest --cov=platform/workflow --cov-fail-under=80         通过
[ ] 全局 DoD 检查脚本通过
```

### M4 Provider Framework 通关清单

```
[ ] M2 通关清单全部通过（前提）
[ ] Playwright 泄漏检测：grep 输出为空
[ ] OpenAI Provider 集成测试通过（真实 API Key）
[ ] Anthropic Provider 集成测试通过（真实 API Key）
[ ] DeepSeek Provider 集成测试通过（真实 API Key）
[ ] Ollama Provider health_check UNHEALTHY 测试通过（不需要 Ollama 运行）
[ ] Browser Provider mock 测试全部通过（不需要真实浏览器）
[ ] Cookie 保存/加载测试通过
[ ] Fallback 链切换测试通过
[ ] Circuit Breaker 状态机测试通过（CLOSED→OPEN→HALF_OPEN→CLOSED）
[ ] CostTracker 每次调用记录测试通过
[ ] pytest --cov=platform/providers --cov-fail-under=80        通过
[ ] 全局 DoD 检查脚本通过
```

### M5 Agent Framework 通关清单

```
[ ] M3 + M4 通关清单全部通过（前提）
[ ] ReAct 3 步任务测试通过
[ ] 循环检测（相同 action 3 次）测试通过
[ ] max_iterations 强制中止测试通过
[ ] Multi-Agent 并行执行时间测试通过
[ ] Worker 失败不崩溃整体任务测试通过
[ ] 流式输出 AsyncIterator 测试通过
[ ] Provider 切换无需改 Agent 代码测试通过
[ ] 4 个内置 Agent 集成测试通过（mock Provider）
[ ] pytest --cov=platform/agents --cov-fail-under=80           通过
[ ] 全局 DoD 检查脚本通过
```

### M6 Memory & Prompt 通关清单

```
[ ] M2 + M5 通关清单全部通过（前提）
[ ] 短期记忆自动裁剪测试通过
[ ] 长期记忆持久化（重启后仍可检索）测试通过
[ ] 语义搜索相似度 > 0.7 测试通过
[ ] Forget 后 search 不返回该记忆测试通过
[ ] Prompt 模板变量/条件/循环/继承渲染测试通过
[ ] A/B 测试权重分配（1000次，A 在 560-640 范围）测试通过
[ ] 版本回滚测试通过
[ ] 所有内置 .j2 模板语法无错误
[ ] pytest --cov=platform/memory platform/prompts --cov-fail-under=80  通过
[ ] 全局 DoD 检查脚本通过
```

### M7 Validation Engine 通关清单

```
[ ] M2 + M4 通关清单全部通过（前提）
[ ] 得分范围 [0,100] 边界测试通过
[ ] 加权得分计算精度测试通过
[ ] LLM Validator 3 次调用防抖测试通过
[ ] LLM Validator 高方差触发 5 次调用测试通过
[ ] Hard Gate BLOCK 测试通过（总分 70 < 阈值 75）
[ ] Soft Gate WARN 测试通过（总分 78 < 目标 90）
[ ] Markdown 报告含 4 个章节测试通过
[ ] YAML 门禁配置加载测试通过
[ ] M3 的 validation_node.py 无需修改即可调用 M7 实现（集成测试）
[ ] pytest --cov=platform/validation --cov-fail-under=80       通过
[ ] 全局 DoD 检查脚本通过
```

### M8 Artifact Management 通关清单

```
[ ] M2 + M7 通关清单全部通过（前提）
[ ] 2000 字 Artifact 保存/读取 sha256 一致
[ ] 大文件（1MB）存文件系统，小文件（<10KB）存 SQLite
[ ] 版本历史列表测试通过
[ ] Diff 输出 unified diff 格式测试通过
[ ] Lifecycle 非法状态流转被拒绝测试通过
[ ] 全文搜索关键词返回正确结果
[ ] ZIP 导出解压后目录结构正确
[ ] pytest --cov=platform/artifacts --cov-fail-under=80        通过
[ ] 全局 DoD 检查脚本通过
```

### M9 Benchmark System 通关清单

```
[ ] M7 + M8 通关清单全部通过（前提）
[ ] Baseline 首次建立并持久化
[ ] 回归检测（-10分）触发 RegressionAlert
[ ] 无误报（-3分，容差内，不告警）
[ ] CI 脚本回归时退出码非 0
[ ] Leaderboard 排序正确（得分高的排前面）
[ ] Time Series 方向判断正确（3次递增→improving）
[ ] 内置套件（book_chapter + code_generation）可加载
[ ] pytest --cov=platform/benchmark --cov-fail-under=80        通过
[ ] 全局 DoD 检查脚本通过
```

### M10 Production Hardening 通关清单（v1.0 发布）

```
[ ] M5 + M6 + M7 + M8 + M9 通关清单全部通过（前提）
[ ] CLI: platform run <workflow> 成功执行
[ ] CLI: platform status <run_id> 显示正确状态
[ ] CLI: platform resume <run_id> 断点恢复成功
[ ] CLI: platform validate <path> 输出验证报告
[ ] CLI: platform benchmark run <suite> 执行并输出报告
[ ] Prometheus 指标端点可访问，5 项指标均有值
[ ] OpenTelemetry trace 完整链路（workflow→node→llm→tool）
[ ] API Key Fernet 加密存储，明文不出现在配置文件
[ ] ShellTool 白名单外命令被拒绝（测试 rm -rf 被阻断）
[ ] uv run pytest tests/ -x                                    整体通过
[ ] pytest --cov=platform --cov-fail-under=75                  整体覆盖率 ≥ 75%
[ ] 真实任务：选项 A（Python asyncio 文章），质量得分 ≥ 80/100
[ ] README / QUICKSTART / PROVIDER_SETUP 文档存在且内容完整
[ ] 全局 DoD 检查脚本通过
```

---

## 11. 自动化验证工具说明

### 11.1 工具栈

| 工具 | 用途 | 安装命令 |
|------|------|---------|
| pytest | 单元测试 + 集成测试 | `uv add --dev pytest pytest-asyncio pytest-cov` |
| mypy | 静态类型检查 | `uv add --dev mypy` |
| ruff | 代码格式 + Lint | `uv add --dev ruff` |
| pytest-cov | 覆盖率报告 | 含在 pytest 扩展中 |
| jsonschema | JSON Schema 验证 | `uv add jsonschema` |
| chromadb | 向量数据库测试 | `uv add chromadb` |

### 11.2 标准测试标记（pytest marks）

```ini
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m not slow')",
    "browser_live: requires real browser (deselect with '-m not browser_live')",
    "requires_ollama: requires Ollama running locally",
    "integration: integration tests (requires real APIs or services)",
    "unit: pure unit tests with no external dependencies",
]
```

### 11.3 CI 执行策略

```yaml
# .github/workflows/ci.yml 执行策略
on_pr:
  - uv run pytest tests/ -m "unit" -x                  # 所有单元测试，快速
  - uv run mypy platform/
  - uv run ruff check platform/ tests/
  - python scripts/ci_benchmark.py --compare main       # Benchmark 回归检测

on_merge_to_main:
  - uv run pytest tests/ -m "unit or integration" -x    # 含集成测试
  - pytest --cov=platform --cov-fail-under=75
  - python scripts/ci_benchmark.py --update-baseline    # 更新 Baseline

nightly:
  - uv run pytest tests/ -m "slow or requires_ollama"   # 慢速测试
  - uv run pytest tests/ -m "browser_live"              # Browser Provider 真实测试
```

### 11.4 DoD 自动检验脚本

```bash
# scripts/check_dod.sh
#!/usr/bin/env bash
set -e

MILESTONE=${1:-"all"}
echo "🔍 检查 DoD: 里程碑 $MILESTONE"

# 全局检查（所有里程碑）
echo "--- 全局检查 ---"
uv run ruff check platform/ tests/ || { echo "❌ ruff 失败"; exit 1; }
uv run mypy platform/ || { echo "❌ mypy 失败"; exit 1; }
grep -rE "(api_key|password|secret)\s*=\s*['\"][^'\"]{8,}" platform/ \
  && { echo "❌ 发现硬编码密钥"; exit 1; }
grep -r "playwright" platform/ --include="*.py" \
  --exclude-path="platform/providers/browser/*" \
  && { echo "❌ Playwright 泄漏"; exit 1; }
uv run pytest tests/ -x --tb=short \
  -m "not browser_live and not requires_ollama and not slow" \
  || { echo "❌ 测试失败"; exit 1; }
uv run pytest --cov=platform --cov-fail-under=75 -q \
  || { echo "❌ 覆盖率不足"; exit 1; }

echo "✅ 全局 DoD 全部通过！可以进入下一里程碑。"
```

---

*本文档由质量负责人在 P2 阶段产出。每个里程碑实际完成时，将在对应通关检查清单中打勾并记录完成日期。DoD 不满足时，必须在当前里程碑内修复，不得带病进入下一里程碑。*
