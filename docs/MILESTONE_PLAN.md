# AI Engineering Execution Platform — 里程碑开发计划

> **版本**：v0.1（P1 阶段产出）  
> **角色**：CTO  
> **基于**：[ARCHITECTURE.md](ARCHITECTURE.md)  
> **约束**：本文档为纯规划文档，不包含任何代码实现  
> **日期**：2026-06-23

---

## 目录

1. [里程碑总览](#1-里程碑总览)
2. [各里程碑详细说明](#2-各里程碑详细说明)
3. [整体甘特图](#3-整体甘特图)
4. [关键路径分析](#4-关键路径分析)
5. [里程碑依赖关系图](#5-里程碑依赖关系图)
6. [跨里程碑特别约束](#6-跨里程碑特别约束)
7. [风险与缓冲](#7-风险与缓冲)

---

## 1. 里程碑总览

| 里程碑 | 名称 | 预估工期 | 依赖 | 关键产出 |
|--------|------|---------|------|---------|
| M0 | Vision & Principles | 1 天 | — | ARCHITECTURE.md ✅ |
| M1 | Architecture & Full Design | 3 天 | M0 | MILESTONE_PLAN / DOD / VALIDATION_FIRST / PROVIDER_FRAMEWORK |
| M2 | Core Engine | 3 天 | M1 | 项目骨架、核心接口、配置、日志、验证接口占位 |
| M3 | Workflow Engine | 4 天 | M2 | DAG执行、断点续跑、重试、并行、插件钩子 |
| M4 | Provider Framework | 5 天 | M2 | API/Local/Browser Provider、Fallback、费用追踪 |
| M5 | Agent Framework | 4 天 | M3, M4 | ReAct、Multi-Agent、工具系统、内置角色 |
| M6 | Memory & Prompt Management | 3 天 | M2, M5 | 短/长期记忆、向量检索、Prompt模板库 |
| M7 | Validation Engine | 4 天 | M2, M4 | 全类型验证器、质量门禁、验证报告 |
| M8 | Artifact Management | 2 天 | M2, M7 | 制品存储、版本管理、多格式导出 |
| M9 | Benchmark System | 3 天 | M7, M8 | 基准套件、回归检测、排行榜、CI集成 |
| M10 | Production Hardening | 4 天 | M5, M6, M7, M8, M9 | CLI、可观测性、安全、首个真实任务验证 |

**总预估工期**：36 天（含 M0 已完成）  
**实际关键路径工期**：见第 4 节

---

## 2. 各里程碑详细说明

---

### M0 — Vision & Principles（已完成 ✅）

**核心目标**：确认产品方向、核心设计原则、系统边界。

**产出**：`docs/ARCHITECTURE.md`（已提交）

**完成标准**：
- ✅ 包含 19 个架构章节
- ✅ Browser Provider 解耦设计明确
- ✅ 验证优先原则明确定义
- ✅ 提交到 Git

---

### M1 — Architecture & Full Design

**核心目标**：完成所有设计文档，为编码阶段建立清晰的合同（Contract）。在进入编码前，所有模块的接口、数据流、验证策略都必须在纸上确定。

**工期**：3 天

**依赖**：M0

**必须完成的文档**：

| 文档 | 内容 | 对应提示词 |
|------|------|-----------|
| `docs/MILESTONE_PLAN.md` | 本文档 | P1 |
| `docs/DEFINITION_OF_DONE.md` | 每个模块的可量化验收标准 | P2 |
| `docs/VALIDATION_FIRST_DESIGN.md` | Validation Engine + Benchmark + Quality Gate 详细设计 | P3 |
| `docs/PROVIDER_FRAMEWORK_DESIGN.md` | Provider 接口 + Browser Provider 状态机 + Fallback 设计 | P4 |

**特别要求**：
- 每份文档必须包含"为什么这样设计"和"未来如何扩展"
- Browser Provider 的 DOM 操作细节可以等到 M4 再确定，但接口必须在 M1 锁定
- Validation Engine 的接口必须在 M1 锁定（即使实现在 M7）

**完成标准**：
- [ ] 4 份设计文档均已提交到 Git
- [ ] 所有核心接口（Provider、Validator、Agent、Workflow Node）有明确的方法签名
- [ ] 质量门禁配置格式已确定（YAML Schema）
- [ ] Browser Provider 状态机图已完成
- [ ] CTO（本文档作者）对所有设计文档签字确认

---

### M2 — Core Engine

**核心目标**：建立项目骨架和所有核心抽象接口。M2 是所有后续里程碑的基础，任何一个后续模块都依赖 M2 定义的接口。

**工期**：3 天

**依赖**：M1

**必须完成的功能**：

| 功能 | 路径 | 说明 |
|------|------|------|
| 项目初始化 | `pyproject.toml`, `.github/` | uv 项目、ruff、mypy、pytest 配置 |
| 目录结构 | `platform/` 全部目录 | 含所有 `__init__.py` 和占位文件 |
| LLMProvider 接口 | `platform/core/interfaces/provider.py` | complete/stream/count_tokens/health_check |
| Validator 接口 | `platform/core/interfaces/validator.py` | validate(artifact, rules) → ValidationResult |
| Agent 接口 | `platform/core/interfaces/agent.py` | run(task, context) → AgentResult |
| WorkflowNode 接口 | `platform/core/interfaces/workflow.py` | execute(inputs, context) → NodeOutput |
| 核心数据模型 | `platform/core/models/` | Message、Artifact、ValidationResult、QualityGate |
| 异常体系 | `platform/core/exceptions/` | ProviderError、ValidationError、WorkflowError 等 |
| ProviderRegistry 骨架 | `platform/providers/registry.py` | 注册、发现（实现留到 M4） |
| 配置系统 | `platform/config/` | Pydantic Settings + YAML 加载 |
| 结构化日志 | `platform/observability/logging.py` | structlog 配置，trace_id 注入 |
| 基础单元测试 | `tests/unit/core/` | 覆盖所有核心数据模型 |

**验证接口植入（特别要求）**：
- `platform/core/interfaces/validator.py` 必须在 M2 完成，即使 M7 才实现
- `platform/workflow/` 目录结构必须在 M2 创建，含 `validation_node.py` 占位文件
- 这确保 M3（Workflow Engine）可以在节点中调用验证，而不需要等 M7

**完成标准**：
- [ ] `uv run pytest tests/unit/core/` 全部通过，覆盖率 ≥ 80%
- [ ] `mypy platform/core/` 零错误
- [ ] `ruff check platform/` 零警告
- [ ] `platform/core/interfaces/` 下 4 个接口文件齐全，方法签名完整
- [ ] 配置系统能从 `config.yaml` + 环境变量加载
- [ ] 日志能输出结构化 JSON，包含 `trace_id`

---

### M3 — Workflow Engine

**核心目标**：实现完整的工作流编排引擎，支持 DAG 执行、断点续跑、并行、重试、插件钩子。这是平台的"神经系统"，控制所有任务的调度和状态。

**工期**：4 天

**依赖**：M2

**必须完成的功能**：

| 功能 | 路径 | 优先级 |
|------|------|--------|
| DAG 定义与执行 | `platform/workflow/dag.py` | P0 |
| 拓扑排序 | `platform/workflow/dag.py` | P0 |
| 节点执行引擎 | `platform/workflow/executor.py` | P0 |
| 状态持久化 | `platform/workflow/state.py` | P0 |
| 断点续跑（Resume） | `platform/workflow/executor.py` | P0 |
| 并行节点执行 | `platform/workflow/nodes/parallel_node.py` | P0 |
| LLM 节点 | `platform/workflow/nodes/llm_node.py` | P0 |
| 验证节点（调用 Validator 接口） | `platform/workflow/nodes/validation_node.py` | P0 |
| 条件分支节点 | `platform/workflow/nodes/branch_node.py` | P1 |
| 循环节点（修复循环） | `platform/workflow/nodes/loop_node.py` | P1 |
| 代码执行节点 | `platform/workflow/nodes/code_exec_node.py` | P1 |
| 人工审核节点 | `platform/workflow/nodes/human_review_node.py` | P2 |
| 指数退避重试 | `platform/workflow/retry.py` | P0 |
| Plugin 钩子系统 | `platform/workflow/plugins.py` | P1 |
| 内置插件：LoggingPlugin | `platform/workflow/plugins/logging_plugin.py` | P1 |
| 内置插件：CostTrackingPlugin | `platform/workflow/plugins/cost_plugin.py` | P2 |
| YAML 工作流定义加载 | `platform/workflow/loader.py` | P0 |
| 工作流模板：write_book_chapter | `platform/workflow/templates/` | P1 |
| 工作流模板：develop_feature | `platform/workflow/templates/` | P2 |

**完成标准**：
- [ ] DAG 循环检测：有循环的 DAG 定义时抛出明确错误
- [ ] 并行执行：≥ 3 个无依赖节点并发执行，总时间 ≤ 最慢单节点时间 × 1.2
- [ ] 断点续跑：模拟节点3执行完成后崩溃，重启后从节点4开始执行
- [ ] 重试：节点失败后自动重试，指数退避间隔正确
- [ ] Plugin：LoggingPlugin 在每个节点前后输出结构化日志
- [ ] 端到端：`write_book_chapter` 模板能完整执行（LLM 节点用 mock）
- [ ] `uv run pytest tests/unit/workflow/ tests/integration/workflow/` 全部通过，覆盖率 ≥ 80%

---

### M4 — Provider Framework

**核心目标**：实现所有 LLM Provider，包括 API Provider、本地 Provider 和 Browser Provider。Browser Provider 是本里程碑的技术难点和重点。

**工期**：5 天（Browser Provider 复杂，额外 1 天缓冲）

**依赖**：M2

**注意**：M3 和 M4 可以并行执行（均只依赖 M2），但实际上 Claude Code 顺序执行，建议 M3 → M4。

**必须完成的功能**：

| 功能 | 路径 | 工期估算 |
|------|------|---------|
| BaseLLMProvider 基类 | `platform/providers/base.py` | 0.5 天 |
| OpenAI Provider | `platform/providers/api/openai_provider.py` | 0.5 天 |
| Anthropic Provider | `platform/providers/api/anthropic_provider.py` | 0.5 天 |
| DeepSeek Provider | `platform/providers/api/deepseek_provider.py` | 0.25 天 |
| Custom API Provider | `platform/providers/api/custom_provider.py` | 0.25 天 |
| Ollama Provider | `platform/providers/local/ollama_provider.py` | 0.5 天 |
| BrowserSession（Playwright封装） | `platform/providers/browser/session.py` | 1 天 |
| BaseBrowserProvider | `platform/providers/browser/base_browser_provider.py` | 0.5 天 |
| ChatGPT target | `platform/providers/browser/targets/chatgpt.py` | 0.5 天 |
| DeepSeek target | `platform/providers/browser/targets/deepseek.py` | 0.5 天 |
| Claude.ai target | `platform/providers/browser/targets/claude_ai.py` | 0.5 天 |
| BrowserProvider 入口 | `platform/providers/browser/browser_provider.py` | 0.25 天 |
| ProviderRegistry（完整实现） | `platform/providers/registry.py` | 0.5 天 |
| Fallback 链 | `platform/providers/fallback.py` | 0.5 天 |
| Circuit Breaker | `platform/providers/circuit_breaker.py` | 0.5 天 |
| CostTracker | `platform/providers/cost_tracker.py` | 0.25 天 |
| 集成测试 | `tests/integration/providers/` | 0.5 天 |

**Browser Provider 特别约束**（硬性规则）：
- `import playwright` 仅允许出现在 `platform/providers/browser/` 目录
- CI 中增加一个 lint 检查：扫描 `platform/` 目录（排除 `providers/browser/`），若发现 `playwright` 字符串则构建失败

**完成标准**：
- [ ] `grep -r "playwright" platform/ --exclude-dir=providers/browser` 输出为空
- [ ] OpenAI Provider：使用真实 API Key 调用 `gpt-4o-mini`，返回合法响应
- [ ] DeepSeek Provider：使用真实 API Key 调用 `deepseek-chat`，返回合法响应
- [ ] Ollama Provider：`health_check()` 在 Ollama 未运行时返回 `UNHEALTHY`
- [ ] Browser Provider：mock 测试通过（mock Playwright Page 对象）
- [ ] Fallback：主 Provider 抛出 `ProviderError` 时，自动切换到备用 Provider
- [ ] Circuit Breaker：连续失败 3 次后，Provider 状态变为 `OPEN`
- [ ] 每次调用后 `CostTracker` 有记录（可查询）
- [ ] `uv run pytest tests/unit/providers/ tests/integration/providers/ -m "not browser_live"` 全部通过

---

### M5 — Agent Framework

**核心目标**：实现单 Agent 和 Multi-Agent 协作框架，提供内置工具系统和 4 个专用 Agent 角色。Agent 是执行具体工程任务的"员工"。

**工期**：4 天

**依赖**：M3（Workflow Engine）、M4（Provider Framework）

**必须完成的功能**：

| 功能 | 路径 | 说明 |
|------|------|------|
| BaseAgent | `platform/agents/base_agent.py` | 含 run/step/use_tool |
| ReAct 推理循环 | `platform/agents/reasoning/react.py` | Thought→Action→Observation |
| Tool 接口 | `platform/agents/tools/base_tool.py` | name/description/input_schema/execute |
| ToolRegistry | `platform/agents/tool_registry.py` | 注册、发现、生成 schema |
| FileTool | `platform/agents/tools/file_tool.py` | read/write/list |
| SearchTool | `platform/agents/tools/search_tool.py` | grep/glob |
| ShellTool | `platform/agents/tools/shell_tool.py` | 白名单命令执行 |
| WebTool | `platform/agents/tools/web_tool.py` | 网页抓取 |
| MemoryTool | `platform/agents/tools/memory_tool.py` | 调用 Memory 接口（M6 实现前用 mock） |
| ValidationTool | `platform/agents/tools/validation_tool.py` | 调用 Validation Engine |
| Multi-Agent Supervisor | `platform/agents/multi_agent.py` | 任务分解 + Worker 调度 |
| ArchitectAgent | `platform/agents/builtin/architect_agent.py` | 角色：系统架构师 |
| EngineerAgent | `platform/agents/builtin/engineer_agent.py` | 角色：软件工程师 |
| WriterAgent | `platform/agents/builtin/writer_agent.py` | 角色：技术写作专家 |
| ValidatorAgent | `platform/agents/builtin/validator_agent.py` | 角色：质量验证专家 |
| 流式输出支持 | `platform/agents/base_agent.py` | stream=True 时流式返回 Thought |

**完成标准**：
- [ ] ReAct 循环：Agent 完成"读文件 → 分析内容 → 写结果"3 步任务（使用 mock Provider）
- [ ] 工具调用失败：自动重试 3 次，3 次均失败时 Agent 切换策略
- [ ] 陷入循环检测：相同 action 重复 3 次时，Agent 中止并报告
- [ ] Multi-Agent：Supervisor + 2 Worker 并行完成任务，结果正确聚合
- [ ] `uv run pytest tests/unit/agents/ tests/integration/agents/` 全部通过，覆盖率 ≥ 80%

---

### M6 — Memory & Prompt Management

**核心目标**：实现两层记忆系统和 Prompt 模板库，使 Agent 具备"记忆能力"和标准化的提示词管理。

**工期**：3 天

**依赖**：M2（核心接口）、M5（Agent Framework，MemoryTool 依赖此模块）

**必须完成的功能**：

| 功能 | 路径 | 说明 |
|------|------|------|
| ShortTermMemory | `platform/memory/short_term.py` | 对话历史 + 自动裁剪 + 摘要压缩 |
| LongTermMemory | `platform/memory/long_term.py` | ChromaDB 向量存储 + 语义检索 |
| MemoryStore 统一接口 | `platform/memory/memory_store.py` | save/search/forget/get_context_for_task |
| Jinja2 模板引擎封装 | `platform/prompts/template.py` | 变量/条件/循环/继承/宏 |
| PromptStore | `platform/prompts/store.py` | 文件系统加载 + 版本管理 |
| A/B 测试框架 | `platform/prompts/ab_test.py` | 多版本权重随机选择 + 得分记录 |
| PromptOptimizer | `platform/prompts/optimizer.py` | 基于历史得分建议改进方向 |
| 内置提示词库 | `platform/prompts/library/` | system/（4个角色）+ tasks/（8个任务） |

**完成标准**：
- [ ] ShortTermMemory：添加 20 条消息，context window 设为 10 条，自动裁剪正确
- [ ] LongTermMemory：save 5 条记忆，search("asyncio") 能找到相关记忆（embedding 相似度）
- [ ] MemoryStore：forget(id) 后 search 不再返回该记忆
- [ ] Prompt 模板：`write_chapter.j2` 含变量插值，渲染结果正确
- [ ] A/B 测试：配置 A(60%) / B(40%) 两个变体，1000 次选择后 A 被选中约 600 次（±50）
- [ ] `uv run pytest tests/unit/memory/ tests/unit/prompts/` 全部通过，覆盖率 ≥ 80%

---

### M7 — Validation Engine

**核心目标**：实现完整的验证引擎，包含所有验证器类型和质量门禁机制。这是平台质量保证的核心，必须在 M8、M9 之前完成。

**工期**：4 天

**依赖**：M2（Validator 接口已在 M2 定义）、M4（LLM Validator 需要 Provider 调用）

**注意**：M7 可以与 M5、M6 并行，均只依赖 M2 和 M4。

**必须完成的功能**：

| 功能 | 路径 | 优先级 |
|------|------|--------|
| ValidationEngine 主入口 | `platform/validation/engine.py` | P0 |
| SchemaValidator | `platform/validation/validators/schema_validator.py` | P0 |
| RuleValidator | `platform/validation/validators/rule_validator.py` | P0 |
| LLMValidator（多次调用防抖） | `platform/validation/validators/llm_validator.py` | P0 |
| CodeValidator | `platform/validation/validators/code_validator.py` | P1 |
| ConsistencyValidator | `platform/validation/validators/consistency_validator.py` | P2 |
| QualityGate（Hard/Soft） | `platform/validation/quality_gate.py` | P0 |
| ValidationReport 生成 | `platform/validation/report.py` | P1 |
| 内置规则库 | `platform/validation/rules/` | P1 |
| YAML 门禁配置加载 | `platform/validation/gates/` | P1 |

**验证在 M2 的植入说明**：
M2 已定义 `Validator` 接口，M3 的 `validation_node.py` 已通过接口调用验证逻辑。M7 补全所有验证器实现后，无需修改 Workflow Engine 代码，直接生效。这验证了"一切皆插件"原则的正确性。

**完成标准**：
- [ ] SchemaValidator：对不合法 JSON 格式 Artifact 返回具体错误位置
- [ ] RuleValidator：`min_words: 1000` 规则，800 字内容正确返回 FAIL
- [ ] LLMValidator：调用 3 次（mock），取中位数，最终得分正确
- [ ] LLMValidator 防抖：3 次得分方差 > 15 时自动增加到 5 次调用
- [ ] QualityGate Hard：总分 < 75 时返回 `GateDecision.BLOCK`
- [ ] QualityGate Soft：总分 75-89 时返回 `GateDecision.WARN`
- [ ] ValidationReport：生成包含总分、各维度得分、问题列表的 Markdown 报告
- [ ] `uv run pytest tests/unit/validation/ tests/integration/validation/` 全部通过，覆盖率 ≥ 80%

---

### M8 — Artifact Management

**核心目标**：实现制品的存储、版本管理和多格式导出。Artifact 是平台所有生成内容的统一容器。

**工期**：2 天

**依赖**：M2（Artifact 数据模型已定义）、M7（需要存储验证得分）

**必须完成的功能**：

| 功能 | 路径 | 说明 |
|------|------|------|
| ArtifactStore | `platform/artifacts/store.py` | CRUD + 版本管理 |
| 文件系统存储后端 | `platform/artifacts/backends/filesystem.py` | 大内容存文件系统 |
| SQLite 元数据存储 | `platform/artifacts/backends/sqlite.py` | 元数据 + 质量分历史 |
| 版本管理 | `platform/artifacts/versioning.py` | diff + 历史查询 |
| Markdown 导出 | `platform/artifacts/exporters/markdown.py` | 默认格式 |
| ZIP 导出 | `platform/artifacts/exporters/zip.py` | 整个项目打包 |
| 生命周期管理 | `platform/artifacts/lifecycle.py` | DRAFT/REVIEW/PUBLISHED/ARCHIVED |
| 全文搜索 | `platform/artifacts/search.py` | 基于 SQLite FTS5 |

**完成标准**：
- [ ] 保存一个 2000 字 Markdown Artifact，读取内容一致
- [ ] 修改后保存新版本，`list_versions(id)` 返回 2 个版本
- [ ] `diff(v1, v2)` 输出正确的差异
- [ ] ZIP 导出：包含所有相关 Artifact 文件
- [ ] 全文搜索：搜索关键词能找到包含该词的 Artifact
- [ ] `uv run pytest tests/unit/artifacts/` 全部通过，覆盖率 ≥ 80%

---

### M9 — Benchmark System

**核心目标**：实现基准测试套件、回归检测和排行榜系统。Benchmark 是平台质量持续改进的量化工具。

**工期**：3 天

**依赖**：M7（Validation Engine）、M8（Artifact Management）

**必须完成的功能**：

| 功能 | 路径 | 说明 |
|------|------|------|
| BenchmarkSuite 定义 | `platform/benchmark/suite.py` | YAML 加载标准任务集 |
| BenchmarkRunner | `platform/benchmark/runner.py` | 执行所有 Task，调用验证 |
| BenchmarkTracker | `platform/benchmark/tracker.py` | 持久化结果 + 趋势数据 |
| 回归检测 | `platform/benchmark/regression.py` | 与 Baseline 对比 |
| Leaderboard | `platform/benchmark/leaderboard.py` | Provider/Prompt/Workflow 横向对比 |
| 报告生成 | `platform/benchmark/reporter.py` | Markdown + JSON 报告 |
| 内置套件：book_chapter | `platform/benchmark/suites/book_chapter.yaml` | 书籍章节基准 |
| 内置套件：code_generation | `platform/benchmark/suites/code_generation.yaml` | 代码生成基准 |
| CI 集成脚本 | `scripts/ci_benchmark.py` | PR 自动触发 + 对比报告 |

**完成标准**：
- [ ] 运行 `book_chapter_suite`，每个 task 有验证得分记录
- [ ] 人工制造质量下降（mock 返回低分），回归检测正确触发告警
- [ ] Leaderboard：2 个 Provider 对比后，得分高的排名靠前
- [ ] 历史趋势：运行 3 次后，趋势数据能生成折线图数据（JSON）
- [ ] CI 脚本：`python scripts/ci_benchmark.py --compare main` 输出对比报告
- [ ] `uv run pytest tests/unit/benchmark/` 全部通过，覆盖率 ≥ 80%

---

### M10 — Production Hardening

**核心目标**：完成 CLI、完整可观测性、安全加固，并以真实任务验证整个平台端到端可用。M10 是平台 v1.0 的发布里程碑。

**工期**：4 天

**依赖**：M5、M6、M7、M8、M9（全部前置里程碑）

**必须完成的功能**：

| 功能 | 路径 | 说明 |
|------|------|------|
| CLI（Typer） | `cli/main.py` | run/status/resume/validate/benchmark/provider 等命令 |
| Prometheus 指标 | `platform/observability/metrics.py` | 5 项核心指标 |
| OpenTelemetry 追踪 | `platform/observability/tracing.py` | workflow → node → llm → tool 完整链路 |
| 告警系统 | `platform/observability/alerting.py` | 质量/费用/Provider 3 类告警 |
| API Key 加密存储 | `platform/config/secrets.py` | Fernet 加密，类似参考项目 APIKeyConfig |
| 代码执行沙箱 | `platform/agents/tools/shell_tool.py` | 白名单 + timeout + 路径限制 |
| 输入验证 | 全局 | 所有外部输入通过 Pydantic |
| 全套回归测试 | `tests/` | 所有已有测试全部通过 |
| README.md | `/` | 项目概述 + 快速开始 |
| docs/QUICKSTART.md | `docs/` | 5 分钟上手指南 |
| docs/PROVIDER_SETUP.md | `docs/` | 各 Provider 配置（含 Browser Provider 登录步骤） |
| **真实任务验证** | — | 见下方 |

**真实任务验证（M10 最重要的完成标准）**：

选择以下任意一个真实任务，使用平台完成（不是 mock）：

**选项 A（推荐）**：自动写一篇技术文章
- 主题：《Python asyncio 并发编程最佳实践》
- 要求：字数 1500-2500，质量得分 ≥ 80/100
- 工作流：`write_book_chapter.yaml`
- 使用真实 LLM Provider（至少一个 API 或 Browser Provider）
- 通过 Validation Engine 验证，输出验证报告

**完成标准**：
- [ ] CLI：`platform run write_book_chapter --input "Python asyncio 最佳实践"` 成功执行
- [ ] CLI：`platform status <run_id>` 正确显示状态
- [ ] CLI：模拟崩溃后 `platform resume <run_id>` 成功恢复
- [ ] 观测：执行过程中 Prometheus 指标正常，日志有完整 trace_id
- [ ] 安全：API Key 以加密形式存储在配置文件中
- [ ] 真实任务：选项 A 完成，生成 Artifact，质量得分 ≥ 80
- [ ] 全套测试：`uv run pytest tests/` 全部通过，整体覆盖率 ≥ 75%
- [ ] 文档：README、QUICKSTART、PROVIDER_SETUP 齐全

---

## 3. 整体甘特图

```
里程碑    │ W1    │ W2    │ W3    │ W4    │ W5    │ W6    │ W7    │ W8
          │1 2 3 4│5 6 7 8│9 ...  │       │       │       │       │
──────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼──────
M0 Vision │████   │       │       │       │       │       │       │
M1 Design │  ████████████ │       │       │       │       │       │
M2 Core   │       │    ████████   │       │       │       │       │
M3 Workfl │       │       │  █████████████│       │       │       │
M4 Provid │       │       │        ███████████████│       │       │
M5 Agent  │       │       │       │       │  █████████████│       │
M6 Memory │       │       │       │       │       │  █████████    │
M7 Valid  │       │       │       │  █████████████│       │       │
M8 Artifa │       │       │       │       │       │      ██████   │
M9 Benchm │       │       │       │       │       │          █████████
M10 Prod  │       │       │       │       │       │       │    ████████

注：W = 工作周（每周 5 个工作日）
    ██ = 里程碑执行期间（Claude Code 全力执行）
    总工期约 7-8 周
```

**说明**：
- M3 和 M4 均依赖 M2，可以同期开始（如有条件并行执行）
- M7 依赖 M2 和 M4，可以在 M4 完成后立即开始，与 M5/M6 并行
- M10 是汇聚点，必须所有前置完成

---

## 4. 关键路径分析

### 4.1 关键路径（Critical Path）

```
M0（1天）→ M1（3天）→ M2（3天）→ M4（5天）→ M7（4天）→ M9（3天）→ M10（4天）

关键路径总长：1 + 3 + 3 + 5 + 4 + 3 + 4 = 23 天
```

**关键路径说明**：

| 环节 | 为何在关键路径上 |
|------|----------------|
| M0 → M1 | 设计文档是所有编码的前提，无法并行 |
| M1 → M2 | 接口定义是骨架代码的前提 |
| M2 → M4 | Provider 是最复杂的实现，Browser Provider 有额外风险 |
| M4 → M7 | LLM Validator 依赖 Provider，验证是质量保证核心 |
| M7 → M9 | Benchmark 依赖验证引擎评分 |
| M9 → M10 | 生产加固是最终汇聚点 |

### 4.2 可并行的非关键路径

```
M2 → M3（Workflow Engine）：可与 M4 并行，不在关键路径
M2 → M3 → M5（Agent Framework）：在 M4 完成后启动，约影响 4 天
M5 → M6（Memory & Prompt）：在 M5 完成后启动，约影响 3 天
M7 → M8（Artifact Management）：可与 M9 并行开始
```

### 4.3 关键路径风险

**最大风险节点：M4（Browser Provider）**
- Browser Provider 是整个项目中不确定性最高的模块
- 目标网站的 DOM 结构随时可能变化
- 缓解方案：
  1. M4 第一天先完成 API Provider 和 Ollama Provider（确保核心路径畅通）
  2. Browser Provider 放在 M4 后半段，失败不影响关键路径
  3. Browser Provider 的 mock 测试先通过，真实集成测试可以延后到 M10 验证

---

## 5. 里程碑依赖关系图

```
M0
│
▼
M1
│
▼
M2 ─────────┬──────────────────────────┐
│           │                          │
▼           ▼                          ▼
M3 ──────► M5 ──────► M6           M4 ──────► M7 ──────► M8
           │                          │                   │
           └──────────────────────────┘                   │
                                      │                   ▼
                                      └─────────────► M9
                                                          │
                                                          ▼
                                              M10（汇聚所有前置）
```

**图例**：
- `→` 强依赖（前置里程碑完成才能开始）
- M5 依赖 M3 和 M4（同时）
- M7 依赖 M2 和 M4（同时）
- M10 依赖 M5、M6、M7、M8、M9（全部）

---

## 6. 跨里程碑特别约束

### 约束 1：Browser Provider 隔离（硬性约束）

```
规则：platform/ 目录下（排除 providers/browser/），不允许出现 "playwright" 字符串
检测：在 M4 完成时，运行以下命令，输出必须为空：
      grep -r "playwright" platform/ --include="*.py" \
           --exclude-path="platform/providers/browser/*"
后果：输出不为空则 M4 视为未完成
```

### 约束 2：Validator 接口在 M2 必须锁定

```
规则：platform/core/interfaces/validator.py 在 M2 完成后不允许破坏性变更
      （可以增加可选参数，不能删除已有方法）
原因：M3 的 validation_node.py 依赖此接口
检测：M7 完成后，M3 的代码不需要改动即可调用 M7 的实现
```

### 约束 3：每个里程碑完成必须通过回归测试

```
规则：进入下一个里程碑之前：
      uv run pytest tests/ -x（-x 表示第一个失败立即停止）必须通过
      mypy platform/ 零错误
      ruff check platform/ 零警告
原因：防止技术债积累，避免后期难以回溯的 Bug
```

### 约束 4：验证接口早于实现

```
规则：M7 Validation Engine 的所有验证器类必须继承 M2 定义的 Validator 接口
      不允许在 M7 中新增未在接口中声明的公开方法（私有方法不限）
原因：保证 Workflow Engine 的 validation_node.py 可以透明调用任何验证器
```

---

## 7. 风险与缓冲

### 7.1 预留缓冲时间

| 里程碑 | 估算工期 | 风险等级 | 建议缓冲 |
|--------|---------|---------|---------|
| M4 Browser Provider | 5 天 | 高 | +1 天（DOM 结构变化） |
| M7 LLM Validator | 4 天 | 中 | +0.5 天（LLM 输出解析不稳定） |
| M10 真实任务验证 | 4 天 | 中 | +1 天（首次端到端可能发现隐藏问题） |
| **总缓冲** | | | **+2.5 天** |

**含缓冲总工期**：36 天 + 2.5 天 = **约 38-39 天（约 8 周）**

### 7.2 里程碑降级策略

若某里程碑严重超期，允许以下降级：

| 里程碑 | 可降级内容 | 降级后果 |
|--------|-----------|---------|
| M4 | Claude.ai Browser target 延后到 M10 | 减少 1 个 Browser 目标网站 |
| M5 | Multi-Agent 降级为 P2，M10 前完成 | 首个真实任务只用单 Agent |
| M6 | A/B 测试框架降级为 P2 | 无 Prompt 版本对比 |
| M8 | PDF/DOCX 导出延后到 M10 后 | 只支持 Markdown + ZIP |

**不可降级的功能**（核心 DoD）：
- Browser Provider 基础功能（ChatGPT 和 DeepSeek 至少一个）
- Validation Engine 基础功能（SchemaValidator + RuleValidator + LLMValidator）
- 断点续跑（Resume）
- Quality Gate Hard Gate
- 真实任务完成（M10 验收必须）

---

*本文档由 CTO 在 P1 阶段产出。里程碑工期为 Claude Code 全力执行的估算，实际工期受 API 配额、网络环境、目标网站稳定性等因素影响。每个里程碑完成后更新实际工期记录。*
