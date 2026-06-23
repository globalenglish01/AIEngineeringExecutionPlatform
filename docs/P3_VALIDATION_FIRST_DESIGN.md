# P3 — 验证优先设计提示词（Validation-First Design Prompt）

> **发送时机**：P2 完成定义文档获得确认后发送。
> **核心思路**：先设计验证平台，再设计执行平台。质量由 Validation 保证，不是由 Generator 保证。
> **禁止事项**：本阶段禁止写任何代码。

---

## 提示词正文

```
你是本项目的 Validation Architect（验证架构师）。

在本平台中，我们采用"验证优先（Validation-First）"的设计原则：

Validation Engine → Benchmark → Quality Gate → Execution Engine

这意味着：
- 在设计任何生成器（Generator）之前，必须先设计好验证器（Validator）
- 每一类输出（书籍章节、代码文件、测试用例、网站页面等）都必须有对应的验证规则
- 质量门禁（Quality Gate）必须在工作流中是强制的，不可绕过

现在请完成以下设计任务：

---

任务 1：Validation Engine 详细设计

请设计一个通用的 Validation Engine，要求：

1. 支持多种验证类型：
   - Schema Validation（JSON Schema、数据格式）
   - Rule-based Validation（可配置规则，如字数、结构、完整性）
   - LLM-based Validation（用 LLM 对输出打分，支持多个评判维度）
   - Code Execution Validation（运行代码，验证是否报错）
   - Human-in-the-loop Validation（人工审核节点）
   - Cross-reference Validation（对比参考资料，检查事实准确性）

2. 验证结果必须包含：
   - 总分（0-100）
   - 各维度得分
   - 具体问题列表（每个问题有：位置、严重程度、建议修复方式）
   - 是否通过质量门禁

3. 验证引擎必须是可插拔的（Plugin-based），方便添加新的验证类型

4. 验证引擎的接口设计（伪代码层面，不是实现）：
   - validate(artifact, rules, context) → ValidationResult
   - register_validator(type, validator_class)
   - get_validators_for(artifact_type) → list[Validator]

---

任务 2：Benchmark 系统设计

请设计一个 Benchmark 系统，要求：

1. 能够对以下对象进行基准测试：
   - LLM Provider（速度、成本、质量）
   - Prompt Template（同一任务不同提示词的质量对比）
   - Workflow（整体流程的质量和效率）
   - Agent（Agent 完成任务的成功率和质量）

2. Benchmark 数据结构：
   - 基准集（Benchmark Suite）：一组标准测试任务
   - 评分标准（Scoring Rubric）：每类任务的评分维度和权重
   - 历史数据（History）：每次运行的结果时序数据
   - 排行榜（Leaderboard）：不同配置的横向对比

3. 自动化要求：
   - 每次代码合并（PR）自动触发回归 Benchmark
   - 质量下降超过阈值时，自动阻断合并

---

任务 3：Quality Gate 设计

请设计质量门禁机制：

1. 门禁类型：
   - Hard Gate（必须通过，否则阻断流程）
   - Soft Gate（发出警告，但允许继续）
   - Progressive Gate（质量随迭代轮次逐步提高）

2. 门禁触发点：
   - 任务执行后
   - 工作流节点完成后
   - 里程碑完成后
   - 代码提交时

3. 门禁配置格式（YAML 示例）：
   ```yaml
   quality_gates:
     book_chapter:
       hard:
         min_score: 75
         dimensions:
           factual_accuracy: 80
           readability: 70
       soft:
         target_score: 90
     code_file:
       hard:
         tests_pass: true
         min_coverage: 80
   ```

---

任务 4：书写"验证优先开发宣言"

请输出一份简短的"Validation-First Manifesto"（验证优先宣言），说明：
- 为什么质量必须由验证保证，而不是由生成器保证
- 在本平台中，验证与执行的关系
- 开发者必须遵守的验证相关约定

---

输出格式：
1. 将上述四个任务合并输出为 docs/VALIDATION_FIRST_DESIGN.md
2. 包含 Mermaid 图表说明各组件关系
3. 每个设计决策说明"为什么"

不要开始写代码。
```

---

## 预期输出

Claude Code 应输出并保存 `docs/VALIDATION_FIRST_DESIGN.md`。

## 下一步

完成后发送 **P4_PROVIDER_FRAMEWORK_DESIGN.md** 中的提示词。
