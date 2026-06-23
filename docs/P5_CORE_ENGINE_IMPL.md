# P5 — 核心引擎实现提示词（Core Engine Implementation Prompt）

> **发送时机**：所有设计文档（P0-P4）获得确认后发送。这是第一个编码阶段。
> **前提条件**：docs/ARCHITECTURE.md、docs/MILESTONE_PLAN.md、docs/DEFINITION_OF_DONE.md、docs/VALIDATION_FIRST_DESIGN.md、docs/PROVIDER_FRAMEWORK_DESIGN.md 均已完成并确认。

---

## 提示词正文

```
现在进入编码阶段。

你是本项目的首席工程师。请基于之前确认的所有设计文档，开始实现 M2（Core Engine）里程碑。

本阶段的目标是建立核心骨架，包括：
1. 项目目录结构
2. 核心抽象接口（不是实现）
3. Provider Framework 骨架（包含 Browser Provider 的接口定义）
4. Validation Engine 骨架
5. 基础配置系统
6. 基础日志和可观测性

开发约束：
1. 技术栈：Python 3.11+，使用 asyncio 实现所有异步操作
2. 包管理：使用 uv（不是 pip，不是 poetry）
3. 代码质量：ruff 格式化，mypy 类型检查
4. 测试框架：pytest + pytest-asyncio
5. 配置：YAML + Pydantic Settings
6. 日志：structlog（结构化日志）

项目目录结构要求：
```
platform/
├── core/                    # 核心抽象（接口、基类）
│   ├── interfaces/          # 所有接口定义（Provider、Validator、Agent 等）
│   ├── models/              # 核心数据模型（Message、Artifact、ValidationResult 等）
│   └── exceptions/          # 异常体系
├── providers/               # LLM Provider 实现
│   ├── base.py              # 基类
│   ├── api/                 # API Provider（OpenAI、Anthropic、DeepSeek）
│   ├── local/               # 本地 Provider（Ollama）
│   └── browser/             # Browser Provider（Playwright，与核心解耦）
│       ├── base.py
│       ├── targets/         # 各网站实现（chatgpt.py、deepseek.py、claude_ai.py）
│       └── session.py       # 浏览器会话管理
├── workflow/                # Workflow Engine
├── agents/                  # Agent Framework
├── validation/              # Validation Engine
├── memory/                  # Memory System
├── prompts/                 # Prompt Management
├── artifacts/               # Artifact Management
├── benchmark/               # Benchmark System
├── config/                  # 配置系统
├── observability/           # 日志、追踪、指标
└── tests/                   # 测试（镜像 platform/ 目录结构）
```

本阶段具体实现任务：

【任务 1】创建项目骨架
- 初始化 uv 项目
- 配置 pyproject.toml（依赖、ruff、mypy）
- 创建上述目录结构（含 __init__.py 和占位文件）

【任务 2】实现核心接口
- core/interfaces/provider.py：LLMProvider 接口
- core/interfaces/validator.py：Validator 接口
- core/interfaces/agent.py：Agent 接口
- core/interfaces/workflow.py：Workflow 接口
- core/models/message.py：Message、CompletionResult、StreamChunk
- core/models/artifact.py：Artifact、ArtifactType、ArtifactStatus
- core/models/validation.py：ValidationResult、ValidationIssue、QualityGate
- core/exceptions/__init__.py：异常体系

【任务 3】实现 Provider Registry
- providers/registry.py：ProviderRegistry（注册、发现、健康检查、Fallback）
- providers/base.py：BaseLLMProvider（实现接口的通用逻辑）

【任务 4】实现配置系统
- config/settings.py：全局配置（Pydantic BaseSettings）
- config/provider_config.py：Provider 配置（含 Browser Provider 配置）
- 支持从 YAML 文件 + 环境变量加载

【任务 5】实现基础日志
- observability/logging.py：structlog 配置
- 每次 LLM 调用自动记录：provider、model、tokens、cost、duration

【任务 6】编写基础测试
- tests/unit/test_provider_registry.py
- tests/unit/test_core_models.py
- tests/unit/test_config.py

完成标准（对照 DoD）：
✓ 所有接口定义完整，类型注解完整
✓ ProviderRegistry 可以注册和发现 Provider
✓ 配置系统可以从 YAML 和环境变量加载
✓ 单元测试覆盖率 ≥ 80%
✓ mypy 检查零错误
✓ ruff 格式化通过

每完成一个任务，立即运行测试并确认通过，然后 git commit。
不要一次写完所有代码再提交。
```

---

## 预期输出

- 完整的项目骨架代码
- 所有核心接口实现
- 测试通过的证明（pytest 输出）

## 下一步

完成后发送 **P6_PROVIDER_IMPL.md** 中的提示词。
