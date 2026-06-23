# AI Engineering Execution Platform (AEEP)

A production-grade platform for orchestrating LLM-powered engineering workflows — writing, coding, analysis — with built-in validation, benchmarking, and observability.

## Features

| Module | What it does |
|--------|-------------|
| **Provider Framework** | OpenAI, Anthropic, DeepSeek, Ollama, Browser (ChatGPT/Claude.ai) with circuit breaker + fallback |
| **Workflow Engine** | YAML-defined DAGs with 7 node types, checkpoint resume, retry |
| **Agent Framework** | ReAct loop, 6 built-in tools, Supervisor/Worker multi-agent |
| **Memory System** | Short-term sliding window + long-term ChromaDB vector search |
| **Prompt Management** | Jinja2 templates, versioning, A/B optimizer |
| **Validation Engine** | Schema, rule, LLM-judge, code (syntax+lint+security), consistency validators |
| **Benchmark System** | Suite runner, regression tracker, leaderboard |
| **CLI** | `platform run / validate / benchmark / provider` commands |
| **Observability** | Structured logging, in-process metrics, span tracing, alerting |
| **Security** | Fernet-encrypted API keys, prompt-injection filter, sandbox shell |

## Quick Start

```bash
# Install
git clone <repo>
cd AIEngineeringExecutionPlatform
uv sync

# Run demo validation task (no LLM required)
uv run python scripts/demo_task.py

# CLI: validate an artifact
uv run python -m cli.main validate my_chapter.md --min-words 1000

# CLI: run benchmark
uv run python -m cli.main benchmark run book_chapter

# Run all tests
uv run pytest tests/ -q
```

## Project Structure

```
aeep/
├── agents/          # BaseAgent, ReAct loop, tools, multi-agent
├── benchmark/       # Suite, runner, tracker, leaderboard
├── config/          # PlatformSettings, provider config loader
├── core/            # Interfaces, models, exceptions, error handler
├── memory/          # Short-term + long-term + unified MemoryStore
├── observability/   # Logging, metrics, tracing, alerting
├── prompts/         # Jinja2 templates, store, A/B optimizer
├── providers/       # API (OpenAI/Anthropic/DeepSeek), Local (Ollama), Browser
├── security/        # APIKeyManager, InputValidator, injection filter
├── validation/      # Engine, 5 validators, QualityGate, report
└── workflow/        # DAG, 7 node types, state, retry, plugins, runner
cli/                 # Typer CLI entry point
scripts/             # CI benchmark, demo task
tests/               # Unit + integration tests (250+)
workflows/templates/ # YAML workflow templates
```

## Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
AEEP_OPENAI_API_KEY=sk-...
AEEP_ANTHROPIC_API_KEY=sk-ant-...
```

Or use the encrypted key manager:

```python
from aeep.security import APIKeyManager
mgr = APIKeyManager()
mgr.set_key("openai", "sk-...")
```

## License

MIT
