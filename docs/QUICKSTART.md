# AEEP Quick Start (5 Minutes)

## 1. Install

```bash
git clone <repo> && cd AIEngineeringExecutionPlatform
uv sync
```

## 2. Run Demo (no API key needed)

```bash
uv run python scripts/demo_task.py
```

Output: validates a pre-written Python asyncio chapter. Should score ≥ 80/100.

## 3. Set Up an API Provider

```bash
# Option A: environment variable
export AEEP_OPENAI_API_KEY=sk-...

# Option B: encrypted key store
uv run python -c "
from aeep.security import APIKeyManager
mgr = APIKeyManager()
mgr.set_key('openai', 'sk-...')
print('Key stored')
"
```

## 4. Validate Your Own Content

```bash
echo "Your article text here..." > my_article.md
uv run python -m cli.main validate my_article.md --min-words 500
```

## 5. Run a Benchmark Suite

```bash
uv run python -m cli.main benchmark run book_chapter
```

## 6. Run Tests

```bash
uv run pytest tests/ -q   # ~250 tests, ~15 seconds
```