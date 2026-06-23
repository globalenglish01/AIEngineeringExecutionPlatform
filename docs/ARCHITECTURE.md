# AI Engineering Execution Platform — 系统架构设计文档

> **版本**：v0.1（P0 阶段产出）  
> **角色**：首席系统架构师  
> **约束**：本文档为纯设计文档，不包含任何代码实现  
> **日期**：2026-06-23

---

## 目录

1. [产品目标（Vision）](#1-产品目标vision)
2. [核心设计原则](#2-核心设计原则)
3. [系统边界](#3-系统边界)
4. [功能清单](#4-功能清单)
5. [非功能需求](#5-非功能需求)
6. [总体架构](#6-总体架构)
7. [核心模块列表与职责](#7-核心模块列表与职责)
8. [模块之间的数据流](#8-模块之间的数据流)
9. [插件机制设计](#9-插件机制设计)
10. [Workflow Engine 设计](#10-workflow-engine-设计)
11. [Agent Framework 设计](#11-agent-framework-设计)
12. [Provider Framework 设计](#12-provider-framework-设计)
13. [Validation Engine 设计](#13-validation-engine-设计)
14. [Memory 设计](#14-memory-设计)
15. [Prompt Management 设计](#15-prompt-management-设计)
16. [Artifact Management 设计](#16-artifact-management-设计)
17. [Benchmark 设计](#17-benchmark-设计)
18. [风险分析](#18-风险分析)
19. [后续开发阶段规划](#19-后续开发阶段规划)

---

## 1. 产品目标（Vision）

### 1.1 一句话定义

> **AI Engineering Execution Platform（AEEP）是一个通用的 AI 工程执行平台，能够将任意可拆分的工程项目自动化执行，并通过闭环验证保证输出质量。**

### 1.2 核心价值主张

当前 AI 工具的最大问题不是"生成能力不够"，而是"质量不可控、流程不闭环"。用户给 AI 一个需求，AI 一次性输出结果，人工验收，发现问题，重新提问——这是一个低效的人工闭环。

AEEP 的目标是：**用自动化闭环取代人工反复提问**。

平台核心循环：
```
需求 → 规划 → 设计 → 执行 → 验证 → 修复 → 再验证 → 输出
                              ↑__________________________|
                                    （不满足质量门禁时循环）
```

### 1.3 目标能力

平台应能自动完成以下类型的工程项目：

| 类型 | 示例 | 质量目标 |
|------|------|---------|
| 技术书籍写作 | 《Python 并发编程实战》全书 | 质量评分 ≥ 90/100 |
| 网站开发 | 企业官网、SaaS 产品前后端 | 功能完整 + 测试通过 |
| 桌面软件开发 | Electron / Tauri 应用 | 功能完整 + 用户体验达标 |
| 移动 App 开发 | React Native / Flutter App | 功能完整 + 平台规范达标 |
| 自动化测试 | API 测试、UI 测试、性能测试 | 覆盖率 ≥ 80% |
| 数据分析 | 数据清洗、建模、可视化报告 | 分析准确 + 报告清晰 |
| 课程生成 | 完整在线课程（视频脚本 + 练习题） | 内容准确 + 教学逻辑合理 |
| 任意可拆分项目 | 扩展到任何结构化工程任务 | 由具体任务定义 |

### 1.4 为什么这样设计

**问题根源**：AI 生成的内容质量不稳定，且没有自我纠错能力。单次提示词无法保证复杂项目的整体质量。

**解决思路**：把工程项目拆分为可验证的最小单元，每个单元都有明确的质量标准，通过自动化闭环迭代直到满足标准。这是工业工程（精益制造）思想在 AI 工程领域的应用。

**未来扩展**：平台应该能够通过学习历史任务数据，不断优化执行策略和质量标准，形成"越用越好"的正向飞轮。

---

## 2. 核心设计原则

### 原则 1：验证优先（Validation-First）

**规则**：任何模块如果没有自动验证机制，则该模块视为设计未完成。

**为什么**：执行是容易的，保证质量是困难的。先定义"什么是好的输出"，再去生成输出，比先生成再事后验证更可靠。

**如何扩展**：每新增一类任务（如视频脚本），必须先定义该类任务的验证规则，再开发执行能力。

### 原则 2：一切皆插件（Everything is a Plugin）

**规则**：所有可变组件（Provider、Validator、Node、Agent、Tool）都通过插件机制接入，核心引擎只依赖接口。

**为什么**：防止核心引擎被具体实现污染。Browser Provider 中的 Playwright 代码绝对不能出现在 Workflow Engine 中。

**如何扩展**：新增 Provider、新增验证规则、新增工作流节点类型，都通过注册插件实现，无需修改核心代码。

### 原则 3：闭环执行（Closed-Loop Execution）

**规则**：执行结果必须经过验证，验证不通过则触发修复，修复后再验证，直到通过或达到最大迭代次数。

**为什么**：一次性生成不可靠，迭代改进才是工程质量的保证。

**如何扩展**：可以设计"分级迭代"——先快速粗糙迭代（低质量门禁），再精细迭代（高质量门禁）。

### 原则 4：可观测性内置（Observability Built-in）

**规则**：每次 LLM 调用、每步工作流执行、每次验证，都必须记录结构化日志、指标和追踪 ID。

**为什么**：复杂系统的调试和优化依赖可观测性。"黑盒 AI"是不可维护的。

**如何扩展**：支持导出到 Prometheus、Jaeger、ELK 等标准可观测性平台。

### 原则 5：Provider 无关（Provider Agnostic）

**规则**：所有业务逻辑不依赖任何具体 LLM Provider。切换 Provider 不需要修改 Workflow 或 Agent 代码。

**为什么**：LLM 市场竞争激烈，模型能力快速迭代。系统必须能够快速切换到更好的模型。

**如何扩展**：Browser Provider 是最特殊的实现，它通过浏览器自动化访问网页版 AI，与 API Provider 接口完全一致。

### 原则 6：任何输出都是可迭代的制品（Artifact）

**规则**：所有生成的内容（文章、代码、测试用例、分析报告）都作为"制品（Artifact）"管理，有版本、有历史、有质量分。

**为什么**：防止"一次性生成丢弃"的模式。好的内容应该被版本化、复用、持续优化。

**如何扩展**：Artifact 可以作为新任务的输入（例如：已有的代码作为修改任务的上下文）。

---

## 3. 系统边界

### 3.1 In Scope（平台负责的）

- 工作流编排与执行
- LLM 调用（API、本地模型、浏览器自动化）
- 智能体（Agent）调度和协作
- 输出质量验证和评分
- 制品版本管理
- 提示词管理和优化
- 记忆管理（短期 + 长期）
- 基准测试和性能追踪
- 执行日志和可观测性
- 费用追踪

### 3.2 Out of Scope（平台不负责的）

- LLM 模型训练和微调（使用现有模型）
- 平台本身的 Web UI（初期为 CLI，Web UI 为后续扩展）
- 代码部署和 CI/CD 流水线（生成代码，不负责部署）
- 数据标注平台
- 用户权限和多租户管理（初期为单用户）

---

## 4. 功能清单

### 4.1 Workflow Engine

- [ ] DAG（有向无环图）定义和执行
- [ ] 节点类型：LLM 调用、验证、条件分支、循环、并行、代码执行、人工审核
- [ ] 工作流状态持久化（支持断点续跑）
- [ ] 失败重试（指数退避）
- [ ] 工作流版本管理
- [ ] 工作流模板库（书写、开发、测试、分析）
- [ ] 定时触发
- [ ] 事件驱动触发

### 4.2 Agent Framework

- [ ] 基础 Agent（单 Agent，工具调用）
- [ ] ReAct 推理循环（Thought → Action → Observation）
- [ ] Multi-Agent 协作（Supervisor + Worker 模式）
- [ ] 工具系统（文件操作、代码执行、网页搜索、记忆操作）
- [ ] 流式输出
- [ ] Agent 间通信协议
- [ ] Agent 角色库（架构师、工程师、写作者、验证者）

### 4.3 Provider Framework

- [ ] 统一 Provider 接口（complete / stream / count_tokens / health_check）
- [ ] API Provider：OpenAI、Anthropic、DeepSeek、自定义兼容接口
- [ ] Local Provider：Ollama
- [ ] Browser Provider：ChatGPT、DeepSeek Chat、Claude.ai（Playwright 驱动）
- [ ] Provider 注册表（动态注册、发现）
- [ ] Fallback 链（主 Provider 失败自动切换）
- [ ] Circuit Breaker（连续失败后临时禁用）
- [ ] 费用追踪（token 用量 + 费用记录）
- [ ] 负载均衡（多个同类 Provider 之间）

### 4.4 Validation Engine

- [ ] Schema 验证（JSON Schema、结构规则）
- [ ] Rule-based 验证（字数、段落、完整性）
- [ ] LLM-based 验证（多维度评分，防抖：3次取平均）
- [ ] 代码执行验证（语法检查、运行测试、代码质量）
- [ ] 一致性验证（跨章节/跨文件）
- [ ] 人工审核节点
- [ ] 质量门禁（Hard Gate / Soft Gate）
- [ ] 验证报告生成（Markdown + HTML）

### 4.5 Memory System

- [ ] 短期记忆（会话内对话历史，自动裁剪）
- [ ] 长期记忆（向量存储，跨会话持久化）
- [ ] 语义检索（相似度搜索）
- [ ] 摘要压缩（历史对话压缩为摘要）
- [ ] 主动遗忘（删除指定记忆）
- [ ] 任务上下文生成（为当前任务检索相关记忆）

### 4.6 Prompt Management

- [ ] 模板系统（Jinja2，支持变量、条件、继承）
- [ ] 版本控制（每次修改自动创建版本）
- [ ] A/B 测试（多版本对比）
- [ ] 历史得分追踪
- [ ] 内置提示词库（角色 + 任务类型）
- [ ] 提示词优化建议

### 4.7 Artifact Management

- [ ] 制品存储（文件系统 + 元数据数据库）
- [ ] 版本管理
- [ ] 质量分历史
- [ ] 多格式导出（Markdown、PDF、DOCX、ZIP）
- [ ] 生命周期管理（草稿/审核/发布/归档）
- [ ] 全文搜索

### 4.8 Benchmark System

- [ ] 基准测试套件（可配置标准任务集）
- [ ] 自动运行和结果记录
- [ ] 与 Baseline 对比（回归检测）
- [ ] Provider / Prompt / Workflow 横向对比排行榜
- [ ] 趋势图（质量随时间变化）
- [ ] CI 集成（PR 自动触发）

### 4.9 可观测性

- [ ] 结构化日志（structlog）
- [ ] 指标收集（Prometheus）
- [ ] 分布式追踪（OpenTelemetry）
- [ ] 告警（质量下降、费用超预算、Provider 失败）

### 4.10 CLI

- [ ] 运行工作流
- [ ] 查询/恢复运行状态
- [ ] Provider 管理（列表、健康检查）
- [ ] 验证制品
- [ ] 基准测试操作
- [ ] 配置管理

---

## 5. 非功能需求

### 5.1 性能

| 指标 | 目标 | 说明 |
|------|------|------|
| 工作流启动延迟 | < 500ms | 从触发到第一个节点开始执行 |
| 并行节点数 | ≥ 10 | 同时并行执行的 Agent/节点数 |
| 断点恢复时间 | < 5s | 从崩溃到恢复执行 |
| 验证引擎响应 | < 30s | 不含 LLM 评分（LLM 评分单独计时） |
| Benchmark 报告生成 | < 60s | 完整套件运行后生成报告 |

### 5.2 可靠性

| 指标 | 目标 | 说明 |
|------|------|------|
| 工作流成功恢复率 | ≥ 95% | 非致命错误后成功从断点恢复 |
| Provider Fallback 成功率 | ≥ 99% | 主 Provider 失败时备用 Provider 接管 |
| 任务完成率 | ≥ 90% | 所有启动的任务最终完成（含修复循环） |

### 5.3 安全性

| 要求 | 实现方式 |
|------|---------|
| API Key 加密存储 | Fernet 对称加密，永不明文存储 |
| 代码执行沙箱 | 白名单命令，限制文件访问路径，timeout 保护 |
| Prompt Injection 防护 | 对 LLM 输出中的特殊指令进行过滤 |
| 输入验证 | 所有外部输入通过 Pydantic 验证 |

### 5.4 可观测性

- 每次 LLM 调用：provider、model、input_tokens、output_tokens、cost、duration、trace_id
- 每步工作流执行：node_id、start_time、end_time、status、input_hash、output_hash
- 每次验证：artifact_id、validator_type、score、issues_count、gate_result
- 告警：质量下降 > 10%、费用超预算、Provider 连续失败 3 次

### 5.5 可维护性

- 代码覆盖率 ≥ 80%（核心模块）
- mypy 零错误
- 所有公开接口有文档字符串
- CHANGELOG 自动生成

---

## 6. 总体架构

### 6.1 分层架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI / API 入口层                         │
│                    (cli/main.py, api/routes/)                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                      编排层 (Orchestration)                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Workflow Engine                         │    │
│  │  DAG Executor │ State Manager │ Retry │ Event Bus       │    │
│  └─────────────┬──────────────────────────────────────────┘    │
│                │                                                 │
│  ┌─────────────▼──────────────────────────────────────────┐    │
│  │                  Agent Framework                        │    │
│  │  BaseAgent │ ReAct │ Multi-Agent │ Tool Registry        │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────┬────────────────────────────┬────────────────────┘
               │                            │
┌──────────────▼──────────┐  ┌─────────────▼──────────────────────┐
│    Provider 层           │  │         质量保证层                   │
│  ┌──────────────────┐   │  │  ┌────────────────────────────┐    │
│  │ ProviderRegistry │   │  │  │    Validation Engine        │    │
│  └────────┬─────────┘   │  │  │ Schema│Rule│LLM│Code│人工  │    │
│  ┌────────▼─────────┐   │  │  └───────────────┬────────────┘    │
│  │  API  │Local│    │   │  │  ┌───────────────▼────────────┐    │
│  │Provider│Provider│   │  │  │     Quality Gate             │    │
│  ├────────────────┤ │   │  │  │   Hard Gate │ Soft Gate     │    │
│  │ Browser        │ │   │  │  └───────────────┬────────────┘    │
│  │ Provider       │ │   │  │  ┌───────────────▼────────────┐    │
│  │(Playwright封装)│ │   │  │  │    Benchmark System         │    │
│  └────────────────┘ │   │  │  └────────────────────────────┘    │
└─────────────────────┘  └──────────────────────────────────────┘
               │
┌──────────────▼────────────────────────────────────────────────┐
│                      基础设施层                                  │
│  Memory│PromptMgr│ArtifactMgr│Config│Observability│CostTracker │
└────────────────────────────────────────────────────────────────┘
```

### 6.2 架构决策说明

**为什么分层**：分层使每一层只关心自己的职责。Workflow Engine 不需要知道 LLM 是 API 还是浏览器；Agent 不需要知道验证规则；Provider 不需要知道任务业务逻辑。

**为什么 Browser Provider 在 Provider 层**：Browser Provider 是 LLM 能力的一种获取方式，与从 API 获取 LLM 能力本质相同，只是实现手段不同。任何通过浏览器获取 LLM 响应的代码都封装在 Provider 层内部，对上层完全透明。

---

## 7. 核心模块列表与职责

| 模块 | 路径 | 职责 | 不负责 |
|------|------|------|--------|
| Workflow Engine | `platform/workflow/` | DAG 编排、状态管理、重试、并行 | 具体业务逻辑 |
| Agent Framework | `platform/agents/` | 推理循环、工具调用、多 Agent 协作 | LLM 调用细节 |
| Provider Framework | `platform/providers/` | LLM 能力获取、Fallback、费用追踪 | 任务业务逻辑 |
| Browser Provider | `platform/providers/browser/` | Playwright 驱动、会话管理、响应提取 | 工作流编排 |
| Validation Engine | `platform/validation/` | 质量验证、评分、质量门禁 | 内容生成 |
| Memory System | `platform/memory/` | 短期/长期记忆、向量检索 | 推理决策 |
| Prompt Management | `platform/prompts/` | 模板管理、版本控制、A/B 测试 | 业务流程 |
| Artifact Management | `platform/artifacts/` | 制品存储、版本、生命周期 | 内容生成 |
| Benchmark System | `platform/benchmark/` | 基准测试、回归检测、排行榜 | 验证逻辑 |
| Core Interfaces | `platform/core/interfaces/` | 定义所有抽象接口 | 任何实现 |
| Observability | `platform/observability/` | 日志、指标、追踪 | 业务逻辑 |
| Config | `platform/config/` | 配置加载（YAML + 环境变量） | 配置内容的业务含义 |

---

## 8. 模块之间的数据流

### 8.1 主流程数据流（书籍章节写作示例）

```
用户输入（需求）
    │
    ▼
CLI/API 接收需求
    │
    ▼
WorkflowEngine.start_run(workflow="write_book_chapter", input=需求)
    │
    ├─── 节点1: LLM Node（大纲生成）
    │         └─ ProviderRegistry.get_provider()
    │              └─ APIProvider.complete(messages) → 大纲 Artifact
    │
    ├─── 节点2: Validation Node（大纲验证）
    │         └─ ValidationEngine.validate(artifact=大纲, rules=outline_rules)
    │              ├─ RuleValidator.validate() → score_1
    │              └─ LLMValidator.validate() → score_2
    │              └─ QualityGate.evaluate() → PASS / RETRY
    │                        │ RETRY
    │                        ↓
    │              节点2重试 → 大纲重生成（带上验证问题作为上下文）
    │
    ├─── 节点3: LLM Node（章节撰写，并行）
    │         └─ 并行调用 Provider，写各章节
    │              └─ Memory.get_context_for_task() → 注入历史经验
    │
    ├─── 节点4: Validation Node（章节验证）
    │         └─ ValidationEngine.validate(artifact=章节, rules=chapter_rules)
    │              └─ QualityGate: score < 75 → BLOCK → 修复循环
    │
    └─── 节点5: Artifact Node（存储输出）
              └─ ArtifactManager.save(content, version, score)
```

### 8.2 关键数据结构流转

```
用户需求(str)
    → TaskInput(需求, 上下文, 配置)
    → WorkflowRun(id, 状态, 节点列表)
    → NodeRun(id, 输入, 输出, 状态)
    → Message(role, content, metadata)
    → CompletionResult(content, usage, cost)
    → Artifact(id, type, content, version, score)
    → ValidationResult(总分, 各维度分, 问题列表, 是否通过)
    → GateDecision(PASS/WARN/BLOCK, 原因)
```

### 8.3 Provider 调用序列图

```
Agent/WorkflowNode
    │ 1. get_provider(name="deepseek_api")
    ▼
ProviderRegistry
    │ 2. return DeepSeekProvider
    ▼
DeepSeekProvider (APIProvider 的子类)
    │ 3. complete(messages, model, temperature)
    │ 4. [失败] → Fallback 到 BrowserProvider
    ▼
BrowserProvider
    │ 5. get_session(target="deepseek")
    ▼
BrowserSession
    │ 6. page.goto("chat.deepseek.com")
    │ 7. page.fill(input, message)
    │ 8. wait_for_response()
    │ 9. extract_text()
    ▼
BrowserProvider
    │ 10. return CompletionResult(content, ...)
    ▼
CostTracker
    │ 11. record(provider, tokens, cost=0)
    ▼
Agent/WorkflowNode
    │ 12. 处理结果
```

---

## 9. 插件机制设计

### 9.1 设计思想

所有可扩展组件都通过**注册表（Registry）+ 接口（Interface）**模式实现。注册表是唯一的查找入口，核心引擎只与注册表交互，不直接依赖具体实现。

### 9.2 可插拔组件

| 组件类型 | 接口 | 注册表 |
|---------|------|--------|
| LLM Provider | `LLMProvider` | `ProviderRegistry` |
| Validator | `Validator` | `ValidatorRegistry` |
| Workflow Node | `WorkflowNode` | `NodeRegistry` |
| Agent Tool | `Tool` | `ToolRegistry` |
| Memory Backend | `MemoryBackend` | `MemoryRegistry` |
| Artifact Exporter | `ArtifactExporter` | `ExporterRegistry` |
| Benchmark Suite | `BenchmarkSuite` | `BenchmarkRegistry` |

### 9.3 插件注册流程

```
1. 定义插件类，实现对应接口
2. 在插件类上使用装饰器 @register_plugin(type="provider", name="my_provider")
3. 平台启动时自动扫描 plugins/ 目录，加载所有插件
4. 通过配置文件指定使用哪些插件
```

### 9.4 Workflow 节点插件钩子

```
[BeforeNode 钩子]
    → LoggingPlugin.before_node()
    → CostBudgetPlugin.check_budget()
    → TracePlugin.start_span()
    │
[NodeExecution]
    │
[AfterNode 钩子]
    → LoggingPlugin.after_node()
    → CostTrackingPlugin.record()
    → BenchmarkPlugin.record_metric()
    → TracePlugin.end_span()
    │
[OnError 钩子]（仅在失败时）
    → AlertPlugin.send_alert()
    → StatePlugin.save_checkpoint()
```

**为什么设计钩子系统**：让横切关注点（日志、费用、追踪、告警）与业务逻辑分离，任何节点都自动获得这些能力，不需要在业务代码中重复实现。

---

## 10. Workflow Engine 设计

### 10.1 核心概念

```
WorkflowDefinition（工作流定义，YAML 格式）
    ├── nodes: list[NodeDefinition]
    │       ├── id, type, config
    │       └── inputs: {key: "node_id.output_key"} （数据流声明）
    └── edges: list[Edge]（节点间依赖关系）

WorkflowRun（一次执行实例）
    ├── run_id（唯一标识，用于 Resume）
    ├── status（PENDING/RUNNING/PAUSED/COMPLETED/FAILED）
    ├── node_runs: dict[node_id, NodeRun]
    └── context: dict（全局共享数据）

NodeRun（节点执行记录）
    ├── node_id, status, start_time, end_time
    ├── input_snapshot（输入数据快照，用于调试）
    ├── output_snapshot（输出数据快照）
    └── retry_count
```

### 10.2 执行策略

**拓扑排序执行**：根据 DAG 的边关系，计算节点的执行顺序。无依赖关系的节点可以并行执行。

**断点续跑**：每个节点完成后，立即持久化状态。崩溃重启后，从最后一个已完成节点之后开始执行。

**修复循环**：验证节点失败时，可以配置"循环回到指定节点重新执行"，并将验证问题注入上下文。

### 10.3 节点类型

| 类型 | 职责 | 关键配置 |
|------|------|---------|
| `llm` | 调用 LLM | provider, prompt_template, output_key |
| `validate` | 验证制品 | artifact_key, rules, gate_config |
| `branch` | 条件分支 | condition_expr, true_branch, false_branch |
| `loop` | 修复循环 | max_iterations, exit_condition, target_node |
| `parallel` | 并行执行 | children, merge_strategy |
| `code_exec` | 代码执行 | command, timeout, allowed_paths |
| `human_review` | 人工审核 | timeout, default_decision |
| `artifact` | 保存制品 | artifact_type, content_key, metadata |

### 10.4 工作流定义示例（YAML）

```yaml
name: write_book_chapter
version: "1.0"
nodes:
  - id: generate_outline
    type: llm
    config:
      provider: "${default_provider}"
      prompt_template: tasks/generate_outline.j2
      output_key: outline

  - id: validate_outline
    type: validate
    config:
      artifact_key: outline
      rules: [outline_structure, min_sections_5, word_count_100_500]
      gate:
        hard: {min_score: 70}
      on_fail: {loop_to: generate_outline, max_iterations: 3}
    depends_on: [generate_outline]

  - id: write_chapters
    type: parallel
    config:
      foreach: "${outline.sections}"
      child_template: write_single_chapter
    depends_on: [validate_outline]
```

**为什么用 YAML 定义工作流**：工作流定义是配置，不是代码。使用 YAML 使非工程师也能理解和修改工作流，且易于版本控制。

---

## 11. Agent Framework 设计

### 11.1 Agent 层次结构

```
BaseAgent（基类）
    ├── SingleAgent（单 Agent，ReAct 推理）
    │       └── 内置角色：ArchitectAgent、EngineerAgent、WriterAgent、ValidatorAgent
    └── MultiAgent（多 Agent 协作）
            ├── SupervisorAgent（分配任务）
            └── WorkerAgent（执行子任务）
```

### 11.2 ReAct 推理循环

```
开始
  │
  ▼
[Thought] LLM 思考："我需要做什么？已知什么？下一步是？"
  │
  ▼
[Action] 选择工具并生成参数
  │
  ▼
[Tool Execution] 实际调用工具
  │
  ▼
[Observation] 将工具结果注入上下文
  │
  ▼
[Check] 任务是否完成？
  ├── 是 → 输出最终结果
  └── 否 → 回到 [Thought]（最多 max_iterations 次）
```

### 11.3 Tool 接口设计

```
Tool:
  name: str              # 工具名称（LLM 通过名称调用）
  description: str       # 工具描述（LLM 理解工具用途）
  input_schema: dict     # JSON Schema（LLM 按此格式传参）
  execute(args) → ToolResult  # 实际执行逻辑
```

### 11.4 Multi-Agent 协作协议

```
SupervisorAgent 接收任务
    │
    ├── 1. 分析任务，分解为子任务
    ├── 2. 为每个子任务选择合适的 WorkerAgent
    ├── 3. 并行分配子任务给 Workers
    ├── 4. 收集 Workers 的结果
    └── 5. 聚合结果，处理失败的子任务

Worker → Supervisor 通信格式：
{
  "worker_id": "engineer_1",
  "task_id": "write_auth_module",
  "status": "completed",
  "result": { ... },
  "quality_score": 85
}
```

**为什么选择 Supervisor 模式而不是 Peer-to-Peer**：Supervisor 模式有明确的控制点，易于追踪整体任务进度，便于处理 Worker 失败的情况。Peer-to-Peer 协作虽然更灵活，但在工程实践中更难调试。

---

## 12. Provider Framework 设计

### 12.1 统一接口

```
LLMProvider（接口）：
  name: str
  provider_type: ProviderType  # API / LOCAL / BROWSER

  complete(messages, model, temperature, max_tokens) → CompletionResult
  stream(messages, model, temperature, max_tokens) → AsyncIterator[StreamChunk]
  count_tokens(messages) → int
  health_check() → HealthStatus
  get_cost(input_tokens, output_tokens) → float
```

### 12.2 Browser Provider 解耦架构

**核心约束**：`import playwright` 只允许出现在 `platform/providers/browser/` 目录下。

```
platform/providers/
├── base.py                     # LLMProvider 接口定义
├── registry.py                 # ProviderRegistry
├── api/
│   ├── openai_provider.py      # import openai
│   ├── anthropic_provider.py   # import anthropic
│   └── deepseek_provider.py    # 复用 openai（兼容接口）
├── local/
│   └── ollama_provider.py      # import httpx（调用 Ollama REST API）
└── browser/
    ├── browser_provider.py     # BrowserProvider（入口，路由到 targets）
    ├── session.py              # BrowserSession（Playwright 封装）
    └── targets/
        ├── chatgpt.py          # ChatGPT 网页操作逻辑
        ├── deepseek.py         # DeepSeek Chat 网页操作逻辑
        └── claude_ai.py        # Claude.ai 网页操作逻辑
```

### 12.3 Browser Provider 状态机

```
初始状态
    │
    ▼ get_session()
[会话获取]
    ├── Cookie 文件存在 → 加载 Cookie
    └── Cookie 文件不存在 → 引导用户手动登录 → 保存 Cookie
    │
    ▼ 登录验证成功
[就绪状态]
    │
    ▼ complete(messages)
[发送消息]
    │ 页面操作：填入消息、点击发送
    ▼
[等待响应]
    │ 检测响应完成标志（"Stop generating" 按钮消失）
    ▼
[提取响应]
    │ 从 DOM 中提取纯文本 + 代码块
    ▼
[返回 CompletionResult]
    │
    ├── 失败（超时/页面错误）→ 记录错误 → 触发 Fallback
    └── 成功 → 返回结果
```

### 12.4 Fallback 链与 Circuit Breaker

```
请求到达
    │
    ▼
ProviderRegistry.complete() 调用 Fallback Chain：
    [Provider A] → 失败 → [Provider B] → 失败 → [Provider C]
                                                       │
                                                       ▼
                                                   全部失败 → 抛出异常

Circuit Breaker（断路器）：
    - Provider 连续失败 3 次 → 状态变为 OPEN（临时禁用）
    - OPEN 状态持续 60 秒后 → 状态变为 HALF_OPEN（尝试一次）
    - 尝试成功 → 状态变为 CLOSED（恢复正常）
    - 尝试失败 → 状态回到 OPEN
```

---

## 13. Validation Engine 设计

### 13.1 验证流水线

```
ValidationEngine.validate(artifact, rules, context)
    │
    ├── 1. 按规则类型分发到对应 Validator
    │       ├── SchemaValidator.validate()
    │       ├── RuleValidator.validate()
    │       ├── LLMValidator.validate()（可配置调用 N 次取平均）
    │       ├── CodeValidator.validate()（仅代码类 Artifact）
    │       └── ConsistencyValidator.validate()（跨文件验证）
    │
    ├── 2. 聚合所有验证结果
    │       └── 加权平均计算总分（各维度权重可配置）
    │
    ├── 3. 应用 Quality Gate
    │       ├── Hard Gate 失败 → GateDecision.BLOCK
    │       ├── Soft Gate 失败 → GateDecision.WARN
    │       └── 全部通过 → GateDecision.PASS
    │
    └── 4. 生成验证报告（Markdown + 结构化 JSON）
```

### 13.2 LLM Validator 设计细节

LLM Validator 是最重要的验证器，但 LLM 输出不稳定，因此需要防抖设计：

- 默认调用 3 次，取中位数（或平均值）
- 要求 LLM 以结构化 JSON 输出得分（通过 JSON Schema 约束响应格式）
- 分多个维度评分：准确性、完整性、清晰度、实用性、创新性
- 如果 3 次得分方差 > 15，增加调用次数（最多 5 次）

### 13.3 质量门禁配置

```yaml
# validation/gates/book_chapter.yaml
quality_gates:
  book_chapter:
    hard:
      min_total_score: 75
      required_dimensions:
        factual_accuracy: {min: 70}
        completeness: {min: 65}
    soft:
      target_total_score: 90
      recommended_dimensions:
        readability: {target: 85}
        innovation: {target: 80}
```

**为什么设计 Hard/Soft 双层门禁**：Hard Gate 防止低质量内容进入下一阶段；Soft Gate 指引内容朝更高质量迭代，但不强制阻断，避免系统过于僵化。

---

## 14. Memory 设计

### 14.1 两层记忆架构

```
Memory System
├── Short-term Memory（短期记忆）
│   - 范围：当前工作流 Run 内
│   - 存储：内存（dict）
│   - 内容：当前对话历史、中间结果
│   - 管理：超出 context window 时，旧消息压缩为摘要
│
└── Long-term Memory（长期记忆）
    - 范围：跨 Run 持久化
    - 存储：ChromaDB（向量数据库）+ SQLite（元数据）
    - 内容：重要事实、最佳实践、历史经验、用户偏好
    - 检索：语义相似度搜索（embedding 向量）
```

### 14.2 记忆检索流程

```
任务开始时：
    Memory.get_context_for_task(task_description)
        │
        ├── 1. 生成任务的 embedding 向量
        ├── 2. 在 ChromaDB 中检索 Top-K 相似记忆
        ├── 3. 按相关性排序，取最相关的 N 条
        └── 4. 格式化为 "Previous Experience:" 段落，注入 System Prompt
```

### 14.3 记忆写入策略

不是所有内容都值得写入长期记忆，只写入以下类型：
- 任务成功完成的经验摘要（含关键决策和结果）
- 验证失败的教训（包括"什么不该做"）
- 用户的明确指令和偏好
- 高质量输出的特征总结

---

## 15. Prompt Management 设计

### 15.1 模板系统

使用 Jinja2 作为模板引擎，支持：
- 变量插值：`{{ artifact.title }}`
- 条件：`{% if context.previous_errors %}...{% endif %}`
- 循环：`{% for section in outline.sections %}...{% endfor %}`
- 继承：`{% extends "base/engineer.j2" %}`
- 宏（Macro）：复用常见的提示词片段

### 15.2 内置提示词库结构

```
platform/prompts/library/
├── system/
│   ├── base.j2              # 基础系统提示（所有角色共享）
│   ├── architect.j2         # 系统架构师角色
│   ├── engineer.j2          # 软件工程师角色
│   ├── writer.j2            # 技术写作专家角色
│   └── validator.j2         # 质量验证专家角色
└── tasks/
    ├── analyze_requirement.j2
    ├── generate_outline.j2
    ├── write_chapter.j2
    ├── generate_code.j2
    ├── review_code.j2
    ├── write_tests.j2
    ├── validate_output.j2    # LLM 评判模板
    └── summarize_for_memory.j2  # 生成记忆摘要
```

### 15.3 版本控制与 A/B 测试

```
PromptStore:
    get(name, version=None)    # None 表示获取最新版本
    save(name, content)        # 自动生成新版本号
    list_versions(name)        # 列出所有版本及得分
    rollback(name, version)    # 回滚到指定版本

A/B 测试：
    - 为同一任务配置多个提示词变体（A, B, C...）
    - 按权重随机选择使用哪个变体
    - 记录每次执行使用的变体和最终质量得分
    - 定期统计各变体平均得分，推荐最优版本
```

---

## 16. Artifact Management 设计

### 16.1 Artifact 数据模型

```
Artifact:
  id: UUID
  type: ArtifactType  # BOOK_CHAPTER / CODE_FILE / TEST_SUITE / DATA_ANALYSIS / ...
  title: str
  content: str         # 实际内容
  format: str          # markdown / python / typescript / json / ...
  version: int         # 自动递增
  quality_score: float # 最新验证得分
  status: ArtifactStatus  # DRAFT / REVIEW / PUBLISHED / ARCHIVED
  metadata: dict       # 任意附加元数据（如：所属书籍、作者、关键词）
  created_at, updated_at
  parent_id: UUID | None  # 用于版本关联（修改后的制品指向上一版本）
```

### 16.2 生命周期

```
创建（DRAFT）
    │ 验证通过
    ▼
审核（REVIEW）←── 人工审核节点
    │ 审核通过
    ▼
发布（PUBLISHED）
    │ 有新版本
    ▼
归档（ARCHIVED）
```

### 16.3 存储策略

- **内容存储**：大内容（代码文件、书籍章节）存储在文件系统，数据库只存路径和元数据
- **小内容**（< 1MB）：直接存储在数据库
- **版本差异**：存储 diff 而不是全量内容（节省空间）
- **导出**：支持 Markdown、PDF（via Pandoc）、DOCX、ZIP（整个项目打包）

---

## 17. Benchmark 设计

### 17.1 基准测试套件结构

```yaml
# benchmark/suites/book_chapter.yaml
name: book_chapter_suite
description: 书籍章节写作质量基准
version: "1.0"
tasks:
  - id: python_async_intro
    type: book_chapter
    prompt: "写一篇关于 Python asyncio 基础的技术文章（1500-2000字）"
    expected:
      min_word_count: 1500
      max_word_count: 2000
      required_sections: ["概念介绍", "代码示例", "最佳实践"]
    scoring:
      factual_accuracy: {weight: 0.3}
      completeness: {weight: 0.3}
      readability: {weight: 0.2}
      code_quality: {weight: 0.2}
    baseline_score: 80  # 历史最佳得分作为基准
```

### 17.2 回归检测策略

- 每次 PR 合并自动触发基准测试
- 与 main 分支最新基准对比
- 任何维度得分下降 > 5 分 → WARN
- 总分下降 > 10 分 → BLOCK（阻断合并）
- 得分提升 → 自动更新 Baseline

### 17.3 排行榜设计

```
Provider Leaderboard（书籍章节写作任务）：
┌─────────────────────┬────────┬──────────┬─────────┬────────┐
│ Provider            │ 总分   │ 准确性   │ 可读性  │ 费用/千字│
├─────────────────────┼────────┼──────────┼─────────┼────────┤
│ Claude Opus (API)   │ 92.3   │ 94.1     │ 91.2    │ $0.045 │
│ GPT-4o (API)        │ 89.7   │ 91.3     │ 88.5    │ $0.030 │
│ DeepSeek (Browser)  │ 87.2   │ 88.9     │ 86.1    │ $0.000 │
│ Ollama/Llama3 (本地)│ 81.5   │ 82.0     │ 81.3    │ $0.000 │
└─────────────────────┴────────┴──────────┴─────────┴────────┘
```

**为什么设计排行榜**：使用者需要知道"哪个 Provider + 哪个提示词版本"在哪类任务上表现最好，从而做出性价比最优的选择。Browser Provider（免费）在得分接近 API Provider 的情况下有明显成本优势。

---

## 18. 风险分析

### 18.1 技术风险

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|---------|
| Browser Provider 被目标网站检测和封锁 | 高 | 中 | Playwright stealth 模式；随机 User-Agent；随机延迟；失败自动 Fallback 到 API |
| LLM 输出不稳定导致验证得分波动 | 高 | 中 | LLM Validator 多次调用取中位数；设置合理的得分容差区间 |
| 长任务（如写一本完整的书）上下文溢出 | 中 | 高 | Memory 摘要压缩；分章节独立执行；Artifact 作为上下文而不是完整对话历史 |
| 闭环修复陷入无限循环 | 中 | 中 | max_iterations 强制上限；检测"相同输出"（hash 比较）时提前终止 |
| 本地模型（Ollama）性能不足 | 低 | 中 | Benchmark 自动检测；低质量时自动升级到 API Provider |
| 向量数据库（ChromaDB）检索质量差 | 低 | 低 | 定期清理低质量记忆；支持替换为其他向量数据库（Qdrant、Weaviate） |

### 18.2 业务风险

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|---------|
| API 费用失控 | 中 | 高 | 每日/月费用上限配置；超预算自动切换到免费 Provider（Browser/本地） |
| 生成内容的版权和准确性 | 中 | 高 | 内置 Fact-checking Validator；输出加水印；明确告知用户人工复核必要性 |
| 网页版 AI 服务条款违规 | 中 | 中 | Browser Provider 设计为可选，用户自行评估合规性；默认推荐使用 API Provider |

### 18.3 架构风险

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|---------|
| 过早优化导致过度复杂 | 中 | 中 | 严格遵守"只实现当前里程碑需要的功能"原则 |
| Provider 接口设计不够抽象，后期难以扩展 | 低 | 高 | P0 阶段深入设计接口；接口变更必须经过 Breaking Change 审查 |
| 验证规则维护成本高 | 中 | 低 | 使用 YAML 配置规则，而不是硬编码；提供规则测试工具 |

---

## 19. 后续开发阶段规划

### 路线图总览

```
2026 Q3
├── M0: Vision & Principles     ← 当前（P0 文档）
├── M1: Architecture & Design   ← P1-P4 提示词阶段
└── M2: Core Engine             ← P5 编码阶段开始

2026 Q4
├── M3: Workflow Engine         ← P7
├── M4: Provider Framework      ← P6（含 Browser Provider）
└── M5: Agent Framework         ← P8（前半）

2027 Q1
├── M6: Memory & Prompt         ← P8（后半）
├── M7: Validation Engine       ← P9（前半）
└── M9: Benchmark System        ← P9（后半）

2027 Q2
├── M10: Production Hardening   ← P10
└── v1.0 发布                   ← 第一个真实任务验证
```

### 各里程碑简述

| 里程碑 | 目标 | 关键输出 |
|--------|------|---------|
| M0 Vision | 确认产品方向和设计原则 | 本文档（ARCHITECTURE.md） |
| M1 Architecture | 完整设计文档（DoD、验证优先、Provider设计） | MILESTONE_PLAN / DOD / VALIDATION_FIRST / PROVIDER_FRAMEWORK |
| M2 Core Engine | 项目骨架 + 所有核心接口定义 | `platform/core/`，Provider Registry，配置系统 |
| M3 Workflow Engine | DAG 执行引擎，含断点续跑 | `platform/workflow/`，3 个内置工作流模板 |
| M4 Provider Framework | 全部 Provider 实现（含 Browser Provider） | `platform/providers/`，4 类 Provider |
| M5 Agent Framework | ReAct Agent + Multi-Agent + 工具系统 | `platform/agents/`，4 个内置 Agent |
| M6 Memory & Prompt | 短/长期记忆 + Prompt 模板库 | `platform/memory/`，`platform/prompts/` |
| M7 Validation Engine | 全类型验证 + 质量门禁 | `platform/validation/`，内置验证报告 |
| M9 Benchmark System | 基准测试 + 回归检测 + 排行榜 | `platform/benchmark/`，CI 集成 |
| M10 Production Hardening | CLI、可观测性、安全、真实任务验证 | v1.0 可用状态 |

### 后 v1.0 演进方向

1. **Web UI**：提供图形化工作流编辑器和任务监控界面
2. **新工作流模板**：网站开发、App 开发、课程生成
3. **提示词自动优化**：基于 Benchmark 历史数据，自动搜索更优提示词
4. **多用户支持**：权限管理、团队协作
5. **云部署**：Docker/Kubernetes 部署方案
6. **Fine-tuning 集成**：基于高质量 Artifact 数据微调专用模型

---

*本文档由首席系统架构师在 P0 阶段产出。后续任何架构变更必须更新本文档，并注明变更原因和版本号。*
