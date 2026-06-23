"""LLMNode — calls an LLM provider and writes the response into context."""

from __future__ import annotations

import logging
from string import Template
from typing import Any

from aeep.core.models.message import Message, Role
from aeep.workflow.nodes.base import BaseNode

logger = logging.getLogger(__name__)


class LLMNode(BaseNode):
    """Calls a provider via ProviderRegistry and stores the output.

    Config keys:
        provider_name   str   which provider to use (default: reads from context['default_provider'])
        model           str   model name
        prompt_template str   Python string.Template; $variables interpolated from context
        system_prompt   str   optional system message
        output_key      str   context key where the response is stored (default: node_id)
        temperature     float default 0.7
        max_tokens      int   default 4096
    """

    node_type = "llm"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from aeep.providers.registry import get_registry

        registry = get_registry()

        provider_name: str = self._get(context, "provider_name", "")
        model: str = self.config.get("model", context.get("default_model", ""))
        template_str: str = self.config.get("prompt_template", "")
        system_prompt: str = self.config.get("system_prompt", "")
        output_key: str = self.config.get("output_key", self.node_id)
        temperature: float = float(self.config.get("temperature", 0.7))
        max_tokens: int = int(self.config.get("max_tokens", 4096))

        # Interpolate template
        prompt = Template(template_str).safe_substitute(context)

        messages: list[Message] = []
        if system_prompt:
            messages.append(Message(role=Role.SYSTEM, content=system_prompt))
        messages.append(Message(role=Role.USER, content=prompt))

        logger.info("LLMNode '%s': calling provider '%s'", self.node_id, provider_name)

        provider = registry.get(provider_name)
        result = await provider.complete(messages, model=model, temperature=temperature, max_tokens=max_tokens)

        logger.info(
            "LLMNode '%s': received %d tokens in %dms",
            self.node_id,
            result.total_tokens,
            result.duration_ms,
        )

        return {output_key: result.content, f"{self.node_id}_result": result}
