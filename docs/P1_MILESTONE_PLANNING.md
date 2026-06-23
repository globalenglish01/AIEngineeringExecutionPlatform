# P1 — 里程碑规划提示词（Milestone Planning Prompt）

> **发送时机**：P0 架构文档获得确认后发送。
> **禁止事项**：本阶段禁止写任何代码。

---

## 提示词正文

```
你是本项目的 CTO。

请基于你刚才完成的系统架构文档，制定完整的里程碑开发计划（Milestone Plan）。

要求：
1. 将整个项目拆分为若干个里程碑（Milestone），建议参考以下结构但可以根据架构调整：

   M0  Vision & Principles（视角与原则确认）
   M1  Architecture & Design（架构完整设计）
   M2  Core Engine（核心引擎骨架）
   M3  Workflow Engine（工作流引擎）
   M4  Provider Framework（含 Browser Provider）
   M5  Agent Framework（智能体框架）
   M6  Memory & Prompt Management（记忆与提示管理）
   M7  Validation Engine（验证引擎）
   M8  Artifact Management（制品管理）
   M9  Benchmark System（基准测试系统）
   M10 Production Hardening（生产加固）

2. 对每个里程碑，说明：
   - 核心目标（1-2 句）
   - 必须完成的功能列表
   - 与其他里程碑的依赖关系
   - 预估工作量（以"天"为单位，Claude Code 全力执行）
   - 完成标准（可量化的验收条件）

3. 特别要求：
   - Validation Engine（M7）的基础设计必须在 M2 阶段就植入，不能等到 M7 才考虑
   - Browser Provider 必须作为 M4 Provider Framework 的一个子模块，不允许在核心引擎中出现任何 Playwright 引用
   - 每个里程碑完成后，必须有自动化的回归测试通过，才能进入下一个里程碑

4. 输出格式：
   - Markdown 表格 + 详细说明
   - 包含整体甘特图（文字版）
   - 包含关键路径分析

5. 将此文档保存为 docs/MILESTONE_PLAN.md

不要开始写代码。
```

---

## 预期输出

Claude Code 应输出并保存 `docs/MILESTONE_PLAN.md`，包含完整里程碑计划。

## 下一步

完成后发送 **P2_DEFINITION_OF_DONE.md** 中的提示词。
