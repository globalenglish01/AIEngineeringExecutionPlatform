# P9 — 验证引擎与基准系统实现提示词（Validation Engine & Benchmark Implementation Prompt）

> **发送时机**：P8 Agent 和记忆系统实现完成并通过 DoD 后发送。
> **本阶段目标**：实现 M7（Validation Engine）+ M9（Benchmark System）。

---

## 提示词正文

```
现在实现 M7（Validation Engine）和 M9（Benchmark System）。

这是整个平台质量保证的核心，必须在进入生产加固阶段之前完成。

---

【任务 1】Validation Engine 核心实现

实现 validation/ 目录：

1. validation/engine.py — 验证引擎入口
   async def validate(
       artifact: Artifact,
       rules: list[ValidationRule],
       context: dict
   ) -> ValidationResult

   - 按规则类型路由到对应的 Validator
   - 聚合所有 Validator 的结果
   - 计算最终总分（加权平均）
   - 应用 Quality Gate（判断是否通过）

2. validation/validators/schema_validator.py
   - 使用 jsonschema 验证 JSON 格式
   - 使用自定义规则验证文本结构（如：章节数量、字数范围）

3. validation/validators/rule_validator.py
   - 基于 Python 表达式的规则引擎
   - 内置规则：min_words、max_words、contains_sections、no_placeholder
   - 支持从 YAML 加载自定义规则

4. validation/validators/llm_validator.py
   - 使用 LLM 对 Artifact 评分
   - 多维度评分：准确性、完整性、清晰度、实用性、创新性
   - 使用 validation/prompts/llm_judge.j2 模板
   - 防止 LLM 输出不稳定：多次调用取平均分（默认 3 次）

5. validation/validators/code_validator.py
   - 语法检查（Python: py_compile, JS: esprima）
   - 运行测试（pytest / jest）
   - 代码质量检查（ruff / eslint）
   - 安全扫描（bandit）

6. validation/validators/consistency_validator.py
   - 检查跨章节、跨文件的一致性
   - 术语一致性（同一概念使用相同词汇）
   - 引用一致性（引用的章节/文件确实存在）

---

【任务 2】Quality Gate 实现

实现 validation/quality_gate.py：

class QualityGate:
    - hard_gates: list[GateRule]（必须通过，否则阻断）
    - soft_gates: list[GateRule]（发出警告，但允许继续）

    def evaluate(result: ValidationResult) -> GateDecision
    # GateDecision: PASS / WARN / BLOCK

支持从 YAML 加载质量门禁配置：
```yaml
quality_gates:
  book_chapter:
    hard:
      min_score: 75
      required_dimensions:
        factual_accuracy: 70
        completeness: 70
    soft:
      target_score: 90
      recommended_dimensions:
        readability: 85
```

---

【任务 3】Benchmark System 实现

实现 benchmark/ 目录：

1. benchmark/suite.py — 基准测试套件
   - BenchmarkSuite：包含一组标准测试任务
   - BenchmarkTask：单个测试任务（输入 + 期望输出 + 评分标准）
   - 从 YAML 文件加载基准套件

2. benchmark/runner.py — 基准测试运行器
   - 执行所有 BenchmarkTask
   - 对每个 Task 调用 Validation Engine 评分
   - 记录运行时间和资源消耗
   - 输出结构化报告（JSON + Markdown）

3. benchmark/tracker.py — 结果追踪
   - 持久化每次 Benchmark 运行结果
   - 计算相对于 Baseline 的变化（+/- 分）
   - 检测回归（得分下降超过阈值）
   - 生成趋势图数据（时序数据）

4. benchmark/leaderboard.py — 排行榜
   - 对比不同 Provider / Prompt / Workflow 配置的得分
   - 支持按维度排序
   - 导出 Markdown 格式的排行榜

5. benchmark/suites/ — 内置基准套件
   - book_chapter_suite.yaml：书籍章节写作基准
   - code_generation_suite.yaml：代码生成基准
   - data_analysis_suite.yaml：数据分析基准

---

【任务 4】CI 集成

实现 .github/workflows/benchmark.yml（如果使用 GitHub Actions）
或 scripts/ci_benchmark.py（通用 CI 脚本）：

- 每次 PR 自动运行基准测试
- 与 main 分支的基准结果对比
- 质量下降时输出警告，严重下降时阻断 PR

---

【任务 5】验证报告生成

实现 validation/report.py：
- 输出 Markdown 格式的验证报告
- 包含：总分、各维度得分、问题列表、改进建议
- 支持导出 HTML 格式（方便在浏览器查看）

---

【任务 6】端到端验证测试

编写一个完整的端到端测试：
1. 生成一段示例书籍章节（可以是固定内容，不需要真实 LLM 调用）
2. 通过 Validation Engine 验证
3. 确认质量门禁正确判断
4. 输出验证报告
5. 运行 Benchmark Suite，确认得分正确记录

---

完成标准（对照 DoD）：
✓ Schema Validator：正确验证 JSON 格式
✓ Rule Validator：字数、结构等规则正确执行
✓ LLM Validator：调用 LLM 并解析多维度得分（mock 测试）
✓ Code Validator：Python 代码语法检查正确
✓ Quality Gate：Hard Gate 阻断、Soft Gate 警告均正确
✓ Benchmark：运行基准套件，结果正确记录
✓ Regression Detection：人工制造质量下降，检测到回归
✓ 单元测试覆盖率 ≥ 80%

每完成一个任务，立即运行测试并 git commit。
```

---

## 预期输出

- Validation Engine 完整实现
- Quality Gate 完整实现
- Benchmark System 完整实现
- 端到端验证测试通过

## 下一步

完成后发送 **P10_PRODUCTION_HARDENING.md** 中的提示词。
