# Provider Setup Guide

## OpenAI

```bash
export AEEP_OPENAI_API_KEY=sk-...
```

Supported models: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`

## Anthropic

```bash
export AEEP_ANTHROPIC_API_KEY=sk-ant-...
```

Supported models: `claude-sonnet-4-6`, `claude-opus-4-8`, `claude-haiku-4-5`

## DeepSeek

```bash
export AEEP_DEEPSEEK_API_KEY=...
```

Supported models: `deepseek-chat`, `deepseek-reasoner`

## Ollama (Local)

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3`
3. No API key needed — runs at `http://localhost:11434`

```python
from aeep.providers.local.ollama_provider import OllamaProvider
provider = OllamaProvider(default_model="llama3")
```

## Browser Provider (ChatGPT / Claude.ai)

Requires Playwright:

```bash
uv pip install playwright
playwright install chromium
```

Configure a session in `config/providers.yaml`:

```yaml
providers:
  - name: chatgpt_browser
    type: browser
    target: chatgpt
    session:
      headless: false
      cookies_file: .cookies/chatgpt.json
```

On first run, log in manually. Cookies are saved for future sessions.

## Custom API (OpenAI-compatible)

```python
from aeep.providers.api.custom_provider import CustomAPIProvider
provider = CustomAPIProvider(
    name="my_llm",
    base_url="https://api.my-llm.com/v1",
    api_key="...",
    default_model="my-model",
)
```