# P10 — 生产加固提示词（Production Hardening Prompt）

> **发送时机**：P9 验证引擎和基准系统实现完成并通过 DoD 后发送。
> **本阶段目标**：实现 M10（Production Hardening），使平台达到可用于实际任务的生产水准。

---

## 提示词正文

```
现在进入 M10（Production Hardening）——生产加固阶段。

目标：确保平台在真实任务中稳定运行，能够完成第一个端到端的实际工程项目。

---

【任务 1】CLI 入口

实现 cli/main.py：

使用 Typer 框架，提供以下命令：

platform run <workflow_name> --input <file>    # 运行工作流
platform status <run_id>                        # 查询运行状态
platform resume <run_id>                        # 断点续跑
platform validate <artifact_path>               # 验证制品
platform benchmark run <suite_name>             # 运行基准测试
platform benchmark report                       # 查看基准报告
platform provider list                          # 列出所有可用 Provider
platform provider health                        # 检查 Provider 健康状态

---

【任务 2】可观测性完善

1. observability/metrics.py — 指标收集
   - 使用 Prometheus client（或 OpenTelemetry）
   - 核心指标：
     * workflow_run_duration_seconds（工作流执行时长）
     * llm_call_total（LLM 调用次数，按 provider/model 分维度）
     * llm_cost_usd_total（累计费用）
     * validation_score（验证得分分布）
     * task_success_rate（任务成功率）

2. observability/tracing.py — 分布式追踪
   - OpenTelemetry 集成
   - 追踪：workflow_run → node_run → llm_call → tool_call
   - 支持导出到 Jaeger / Tempo

3. observability/alerting.py — 告警
   - Quality Gate 失败时发送告警
   - Provider 连续失败时发送告警
   - 费用超出预算时发送告警
   - 告警渠道：控制台 / 文件（初期），后续扩展到 Slack / 邮件

---

【任务 3】错误处理与恢复

实现统一的错误处理策略：

1. 错误分类：
   - TransientError（瞬时错误，可重试）：网络超时、API 限流
   - PermanentError（永久错误，不重试）：配置错误、权限错误
   - QualityError（质量不达标）：触发修复循环
   - BudgetError（费用超出）：暂停并告警

2. 全局错误处理器：
   - 捕获所有未处理异常
   - 记录完整堆栈到结构化日志
   - 保存当前状态（用于 Resume）
   - 发送告警

---

【任务 4】安全加固

1. API Key 管理：
   - 所有 API Key 通过 Fernet 加密存储（参考 TestAgentPythonProject 的 APIKeyConfig 实现）
   - 支持从环境变量和加密存储两种方式获取 Key
   - Key 轮换：定期提醒用户更新即将过期的 Key

2. 代码执行沙箱：
   - shell_tool 执行命令前，检查命令白名单
   - 限制执行时间（timeout）
   - 限制文件访问范围（只允许在工作目录内操作）

3. 输入验证：
   - 所有外部输入（CLI 参数、YAML 配置、LLM 输出）都经过 Pydantic 验证
   - 防止 Prompt Injection：对 LLM 输出中的特殊指令进行过滤

---

【任务 5】第一个真实任务验证

使用本平台完成第一个真实工程任务，证明平台可用：

任务选项（选择其中一个）：
A. 自动写一个技术文档章节（例如：Python asyncio 最佳实践）
   - 要求：字数 ≥ 2000，质量得分 ≥ 80 分
   - 使用 write_book_chapter.yaml Workflow
   - 通过 Validation Engine 验证并输出报告

B. 自动生成一个简单 Python 模块的完整代码和测试
   - 要求：代码运行无错误，测试覆盖率 ≥ 70%
   - 使用 develop_feature.yaml Workflow
   - 通过 Code Validator 验证

执行步骤：
1. 配置好至少一个 LLM Provider（可以是 Browser Provider）
2. 运行选定的 Workflow
3. 输出：
   - 生成的 Artifact 文件
   - 验证报告（包含得分和问题列表）
   - 完整的执行日志（含费用统计）
4. 如果得分 < 80，触发修复循环，再次生成并验证

---

【任务 6】文档完善

1. README.md — 项目概述和快速开始指南
2. docs/QUICKSTART.md — 5 分钟快速上手
3. docs/PROVIDER_SETUP.md — 各 Provider 配置指南（含 Browser Provider 配置步骤）
4. docs/WORKFLOW_GUIDE.md — 如何创建和运行 Workflow
5. docs/API_REFERENCE.md — 核心接口参考文档

---

完成标准（最终 DoD）：
✓ CLI 可用：所有命令正确执行
✓ 可观测性：日志、指标、追踪均正常输出
✓ 错误恢复：模拟崩溃后成功 Resume
✓ 安全：API Key 加密存储，代码执行有沙箱保护
✓ 真实任务：至少一个真实任务以质量得分 ≥ 80 完成
✓ 全套回归测试通过
✓ 整体测试覆盖率 ≥ 75%
✓ README 和快速开始文档完整

每完成一个任务，立即运行测试并 git commit。
恭喜！完成所有 10 个 Milestone 后，平台正式进入 v1.0 可用状态。
```

---

## 预期输出

- 完整可用的 CLI 工具
- 完整的可观测性体系
- 至少一个真实任务成功完成，质量得分 ≥ 80
- 完整的项目文档

## 后续演进

M10 完成后，可以开始：
- 添加新的 Workflow 模板（网站开发、App 开发、课程生成等）
- 优化 Prompt Library（提高各类任务的默认质量）
- 扩展 Browser Provider 支持的网站
- 构建 Web UI（管理界面）
- 接入更多本地模型
