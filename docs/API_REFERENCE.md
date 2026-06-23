# API Reference

## Core Interfaces

### LLMProvider

```python
class LLMProvider(Protocol):
    name: str
    async def complete(messages, model, temperature=0.7, max_tokens=4096) -> CompletionResult
    async def stream(messages, model, ...) -> AsyncIterator[StreamChunk]
    async def count_tokens(messages) -> int
    async def health_check() -> HealthCheckResult
    def get_cost(input_tokens, output_tokens, model) -> float
```

### ValidationEngine

```python
engine = ValidationEngine(llm_provider=optional_provider)
result: ValidationResult = await engine.validate(artifact, rules, context)
```

### QualityGate

```python
gate = QualityGate(
    hard_gates=[GateRule("hard", min_score=75.0)],
    soft_gates=[GateRule("soft", min_score=90.0)],
)
decision: GateDecision = gate.evaluate(result)  # PASS | WARN | BLOCK
```

### WorkflowRunner

```python
runner = WorkflowRunner("my_workflow", dag, state_store=store)
run = await runner.run(initial_context)
run = await runner.run(resume_run_id="abc123")  # resume
```

### BaseAgent

```python
agent = BaseAgent(
    name="MyAgent", role="...",
    provider=provider,
    tools=[FileTool(), ShellTool()],
    memory=MemoryStore(),
    max_iterations=10,
)
result: AgentResult = await agent.run(task="...", context={})
```

### MemoryStore

```python
store = MemoryStore(persist_directory="./data")
store.add_message(message)
memory_id = store.save("Important fact", metadata={"tag": "key"})
memories = store.search("query", k=5)
context_str = store.get_context_for_task("current task")
```

### BenchmarkRunner

```python
suite = BenchmarkSuite.from_yaml("path/to/suite.yaml")
runner = BenchmarkRunner()
report = await runner.run(suite, generator=async_generator_fn)
tracker = BenchmarkTracker("history.db")
tracker.save(report)
alert = tracker.check_regression(report, threshold=5.0)
```

### Security

```python
from aeep.security import APIKeyManager, InputValidator, sanitize_llm_output

# Key management
mgr = APIKeyManager()
mgr.set_key("openai", "sk-...")
key = mgr.get_key("openai")

# Input validation
result = InputValidator.validate_workflow_input({"topic": "Python", "max_words": 2000})

# Prompt injection filter
clean = sanitize_llm_output(llm_output)
```