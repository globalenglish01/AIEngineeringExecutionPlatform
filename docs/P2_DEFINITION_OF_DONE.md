# P2 — 完成定义提示词（Definition of Done Prompt）

> **发送时机**：P1 里程碑计划获得确认后发送。
> **禁止事项**：本阶段禁止写任何代码。

---

## 提示词正文

```
你是本项目的质量负责人（Quality Gatekeeper）。

请为每个里程碑和每个核心模块制定严格的"完成定义（Definition of Done, DoD）"。

DoD 的核心原则：
- 没有自动验证机制的模块，视为设计未完成
- DoD 必须是可量化、可自动验证的，不能是主观判断
- 进入下一个里程碑之前，当前里程碑的所有 DoD 必须 100% 通过

请为以下每个模块分别输出 DoD 清单：

---

【Workflow Engine】
必须满足：
- DAG（有向无环图）执行
- Retry（失败重试，可配置次数和间隔）
- Resume（断点续跑，任务中断后可从断点恢复）
- Event（事件驱动，节点完成时触发下游）
- Plugin（插件钩子，可在节点前后注入逻辑）
- Log（结构化日志，每步可追溯）
- Parallel（并行执行多个节点）
- Schedule（定时触发工作流）
- Benchmark（每次执行记录耗时和质量得分）
- Test（自动化测试覆盖率 ≥ 80%）

【Agent Framework】
必须满足：
- Tool Use（工具调用，标准接口）
- Memory（短期 + 长期记忆接入）
- Planning（任务分解，支持 ReAct / CoT）
- Multi-Agent（多 Agent 协作，支持 Supervisor 模式）
- Streaming（流式输出）
- Error Recovery（失败时自动修复策略）
- Provider Agnostic（切换 LLM Provider 不需要改 Agent 代码）
- Test（自动化测试覆盖率 ≥ 80%）

【Provider Framework】
必须满足：
- Unified Interface（所有 Provider 实现相同接口：complete / stream / count_tokens）
- API Provider（至少支持 OpenAI、Anthropic、DeepSeek）
- Local Provider（至少支持 Ollama）
- Browser Provider（通过 Playwright 操作网页版 AI，封装成统一接口）
  - 登录状态管理
  - 会话保持
  - 响应提取（文本、代码块）
  - 自动重试
  - Fallback 到其他 Provider
- Fallback 机制（主 Provider 失败时自动切换）
- Cost Tracking（每次调用记录 token 用量和费用）
- Test（每个 Provider 有独立的集成测试）

【Validation Engine】
必须满足：
- Score（对任意 Artifact 给出 0-100 的质量得分）
- Rule（可配置的验证规则，支持 JSON Schema / 自定义函数）
- LLM Judge（用 LLM 对输出进行评分）
- Human Review（支持人工审核工作流）
- Diff（对比前后版本的质量变化）
- Gate（质量门禁，得分低于阈值时阻断流程）
- Report（输出结构化验证报告）
- Test（自动化测试覆盖率 ≥ 80%）

【Memory System】
必须满足：
- Short-term（会话内记忆）
- Long-term（跨会话持久化记忆）
- Retrieval（向量检索 + 关键词检索）
- Context Window Management（自动裁剪超长上下文）
- Forget（支持主动遗忘特定记忆）
- Test（自动化测试覆盖率 ≥ 80%）

【Prompt Management】
必须满足：
- Version Control（提示词版本管理）
- Template（支持变量插值）
- A/B Test（多版本提示词对比实验）
- Score Tracking（每个提示词版本的历史得分）
- Rollback（回滚到历史版本）
- Test（每个模板有自动化测试）

【Artifact Management】
必须满足：
- Storage（文件/数据库/对象存储）
- Version（制品版本管理）
- Diff（版本间差异对比）
- Export（支持多种格式导出）
- Lifecycle（制品生命周期管理：草稿/审核/发布/归档）
- Search（全文检索）
- Test（自动化测试覆盖率 ≥ 80%）

【Benchmark System】
必须满足：
- Baseline（建立基准质量分）
- Regression（检测质量退步）
- Leaderboard（不同模型/提示词的得分排行）
- Time Series（质量随时间的变化趋势）
- Report（自动生成基准测试报告）
- Alert（质量下降时发出告警）

---

输出格式要求：
1. 每个模块输出一个 Markdown 表格，列为：项目 / 验证方式 / 通过标准
2. 汇总所有模块，输出"里程碑通关检查清单"
3. 说明每个 DoD 项应该如何自动化验证（工具、脚本、测试框架）
4. 将此文档保存为 docs/DEFINITION_OF_DONE.md

不要开始写代码。
```

---

## 预期输出

Claude Code 应输出并保存 `docs/DEFINITION_OF_DONE.md`。

## 下一步

完成后发送 **P3_VALIDATION_FIRST_DESIGN.md** 中的提示词。
