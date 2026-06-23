# AI Engineering Execution Platform — 提示词发送顺序指南

本目录包含开发本平台所需的全部阶段性提示词，按顺序发送给 Claude Code。

---

## 提示词发送顺序

| 顺序 | 文件 | 阶段 | 是否可写代码 | 触发条件 |
|------|------|------|-------------|----------|
| 1 | [P0_PROJECT_KICKOFF.md](P0_PROJECT_KICKOFF.md) | 项目启动 / 架构设计 | ❌ 禁止 | 项目开始时 |
| 2 | [P1_MILESTONE_PLANNING.md](P1_MILESTONE_PLANNING.md) | 里程碑规划 | ❌ 禁止 | P0 架构文档确认后 |
| 3 | [P2_DEFINITION_OF_DONE.md](P2_DEFINITION_OF_DONE.md) | 完成定义 | ❌ 禁止 | P1 里程碑计划确认后 |
| 4 | [P3_VALIDATION_FIRST_DESIGN.md](P3_VALIDATION_FIRST_DESIGN.md) | 验证优先设计 | ❌ 禁止 | P2 DoD 确认后 |
| 5 | [P4_PROVIDER_FRAMEWORK_DESIGN.md](P4_PROVIDER_FRAMEWORK_DESIGN.md) | Provider 框架设计 | ❌ 禁止 | P3 验证设计确认后 |
| 6 | [P5_CORE_ENGINE_IMPL.md](P5_CORE_ENGINE_IMPL.md) | 核心引擎实现 | ✅ **开始编码** | 所有设计文档确认后 |
| 7 | [P6_PROVIDER_IMPL.md](P6_PROVIDER_IMPL.md) | Provider 实现（含 Browser Provider） | ✅ | P5 通过 DoD 后 |
| 8 | [P7_WORKFLOW_ENGINE_IMPL.md](P7_WORKFLOW_ENGINE_IMPL.md) | Workflow Engine 实现 | ✅ | P6 通过 DoD 后 |
| 9 | [P8_AGENT_AND_MEMORY_IMPL.md](P8_AGENT_AND_MEMORY_IMPL.md) | Agent 框架 + 记忆系统 | ✅ | P7 通过 DoD 后 |
| 10 | [P9_VALIDATION_BENCHMARK_IMPL.md](P9_VALIDATION_BENCHMARK_IMPL.md) | 验证引擎 + 基准系统 | ✅ | P8 通过 DoD 后 |
| 11 | [P10_PRODUCTION_HARDENING.md](P10_PRODUCTION_HARDENING.md) | 生产加固 | ✅ | P9 通过 DoD 后 |

---

## 关键原则

1. **每个阶段完成前不进入下一阶段** — 所有 DoD 必须 100% 通过
2. **设计阶段（P0-P4）禁止写任何代码** — Claude Code 必须只输出设计文档
3. **验证优先** — Validation Engine 的基础设计在 P3 完成，早于执行引擎
4. **Browser Provider 解耦** — 任何 Playwright 代码只允许出现在 `providers/browser/` 目录
5. **每个功能完成立即 commit** — 不要积累再统一提交

---

## 里程碑对应关系

```
P0-P4（设计阶段）
├── M0 Vision
├── M1 Architecture
└── 为 M2-M10 的实现做铺垫

P5 → M2 Core Engine
P6 → M4 Provider Framework（含 Browser Provider）
P7 → M3 Workflow Engine
P8 → M5 Agent Framework + M6 Memory & Prompt
P9 → M7 Validation Engine + M9 Benchmark System
P10 → M10 Production Hardening
```

---

## Browser Provider 说明

Browser Provider 通过 Playwright 操作 ChatGPT、DeepSeek、Claude.ai 等网页版，
将其封装成与 API Provider 完全相同的统一接口。

实现参考：`D:\TestAgentPythonProject`（该项目中有 LLM 配置和 Playwright 的使用先例）

关键约束：
- `providers/browser/` 是唯一可以 `import playwright` 的目录
- Browser Provider 对外暴露 `complete` / `stream` / `count_tokens` / `health_check`
- 支持 Fallback 到 API Provider（当浏览器操作失败时）
