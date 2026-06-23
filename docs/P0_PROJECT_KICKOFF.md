# P0 — 项目启动提示词（Project Kickoff Prompt）

> **发送时机**：第一次打开 Claude Code，项目目录为空时发送。
> **禁止事项**：本阶段禁止写任何代码。

---

## 提示词正文

```
你将作为本项目唯一的首席系统架构师（Chief System Architect）。

我们要开发的是一个通用 AI Engineering Execution Platform（AI 工程执行平台）。

这个平台最终应该能够完成包括但不限于：
- 自动写高质量技术书（目标评分 ≥ 90 分）
- 自动开发网站
- 自动开发桌面软件
- 自动开发移动 App
- 自动完成自动化测试
- 自动完成数据分析
- 自动生成课程
- 自动完成任何可以拆分成任务的工程项目

平台必须采用"需求 → 规划 → 设计 → 执行 → 验证 → 修复 → 再验证"的闭环，而不是一次性生成结果。

平台必须支持多种 LLM Provider，包括：
- 官方 API（OpenAI、Anthropic、DeepSeek 等）
- 本地模型（Ollama 等）
- Browser Provider（通过 Playwright 操作 ChatGPT、DeepSeek 等网页版，并封装成统一 LLM 接口）

关于 Browser Provider，有以下设计要求：
- 它必须只是 LLM Provider 的一种实现，与系统核心完全解耦
- 通过 Playwright 控制浏览器访问网页版 AI（如 ChatGPT、DeepSeek Chat 等）
- 对外暴露与其他 Provider 完全相同的接口（如 complete / stream）
- 支持会话保持、登录状态管理、响应提取
- 失败时可自动切换到其他 Provider（Fallback 机制）

核心约束：
1. 第一阶段禁止写任何代码
2. 第一阶段唯一目标是完成系统架构设计文档
3. 任何架构、Prompt、Workflow 都视为可验证、可评分、可迭代优化的对象
4. 任何模块如果没有自动验证机制，则该模块视为设计未完成

请输出完整的系统架构设计文档，必须包含以下所有章节：

1. 产品目标（Vision）
2. 核心设计原则（含为什么这样设计、未来如何扩展）
3. 系统边界（In Scope / Out of Scope）
4. 功能清单（按模块分类）
5. 非功能需求（性能、可靠性、安全性、可观测性）
6. 总体架构图（文字版 ASCII 或 Mermaid）
7. 核心模块列表与职责
8. 模块之间的数据流（含序列图）
9. 插件机制设计
10. Workflow Engine 设计
11. Agent Framework 设计
12. Provider Framework 设计（重点：Browser Provider 如何与核心解耦）
13. Validation Engine 设计
14. Memory 设计
15. Prompt Management 设计
16. Artifact Management 设计
17. Benchmark 设计
18. 风险分析
19. 后续开发阶段规划（路线图）

每个章节都必须说明：为什么这样设计，以及未来如何扩展。

不要开始写代码。
```

---

## 预期输出

Claude Code 应输出一份完整的架构设计文档（Markdown 格式），保存在 `docs/ARCHITECTURE.md`。

## 下一步

完成后发送 **P1_MILESTONE_PLANNING.md** 中的提示词。
