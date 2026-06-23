# Workflow Guide

## Running a Built-in Workflow

```bash
uv run python -m cli.main run write_book_chapter --input context.json
```

`context.json` example:
```json
{"topic": "Python asyncio", "target_length": "3000 words", "audience": "intermediate developers"}
```

## Workflow YAML Structure

```yaml
name: my_workflow
nodes:
  - id: generate
    type: llm
    config:
      provider_name: openai
      model: gpt-4o-mini
      prompt_template: "Write about: $topic"
      output_key: draft

  - id: validate
    type: validation
    depends_on: [generate]
    config:
      input_key: draft
      min_score: 70
      on_fail: warn

  - id: check
    type: branch
    depends_on: [validate]
    config:
      condition_key: validate_passed
      condition_op: truthy
      true_branch: done
      false_branch: revise
```

## Node Types

| Type | Purpose |
|------|---------|
| `llm` | Call an LLM provider |
| `validation` | Score content quality |
| `branch` | Conditional routing |
| `loop` | Iterate until condition met |
| `parallel` | Run sub-nodes concurrently |
| `human_review` | Pause for human input |
| `code_execution` | Run Python code |

## Resume a Failed Run

```bash
uv run python -m cli.main resume <run_id>
```

The workflow skips already-completed nodes and continues from the failure point.