"""ReAct (Reasoning + Acting) loop implementation."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from aeep.agents.models import AgentResult, AgentStatus, AgentStep
from aeep.core.models.message import Message, Role

if TYPE_CHECKING:
    from aeep.agents.base_agent import BaseAgent

_MAX_LOOP_DETECTS = 3   # same action repeated this many times → break out


class ReActLoop:
    """Orchestrates the Thought → Action → Observation cycle."""

    def __init__(self, agent: BaseAgent) -> None:
        self._agent = agent

    async def run(self, task: str, context: dict[str, Any]) -> AgentResult:
        system_msg = Message(role=Role.SYSTEM, content=self._agent._system_prompt())
        user_msg = Message(
            role=Role.USER,
            content=self._build_user_message(task, context),
        )

        messages: list[Message] = [system_msg, user_msg]
        steps: list[AgentStep] = []
        action_counter: Counter[str] = Counter()

        for iteration in range(self._agent._max_iterations):
            step = await self._agent.step(messages)
            steps.append(step)

            if step.is_final:
                if self._agent.memory:
                    self._agent.memory.save(
                        f"Task: {task}\nResult: {step.thought}",
                        {"agent": self._agent.name},
                    )
                return AgentResult(
                    status=AgentStatus.COMPLETED,
                    output=step.thought,
                    steps=steps,
                    iterations=iteration + 1,
                )

            # Execute tool with up to 3 retries
            observation = await self._execute_with_retry(step)
            step.observation = observation

            # Loop detection
            action_counter[step.action] += 1
            if action_counter[step.action] >= _MAX_LOOP_DETECTS:
                # Switch strategy: add a hint message
                messages.append(Message(
                    role=Role.USER,
                    content=(
                        f"You have called {step.action!r} {_MAX_LOOP_DETECTS} times in a row "
                        "without making progress. Try a different approach or provide your Final Answer."
                    ),
                ))
                action_counter.clear()

            # Append assistant turn + observation
            messages.append(Message(role=Role.ASSISTANT, content=self._format_step(step)))
            messages.append(Message(role=Role.USER, content=f"Observation: {observation}"))

        return AgentResult(
            status=AgentStatus.FAILED,
            output="",
            steps=steps,
            error=f"Exceeded max_iterations ({self._agent._max_iterations})",
            iterations=self._agent._max_iterations,
        )

    async def _execute_with_retry(self, step: AgentStep, max_retries: int = 3) -> str:
        last_error = ""
        for attempt in range(max_retries):
            try:
                result = await self._agent.use_tool(step.action, step.action_input)
                return result
            except Exception as e:
                last_error = str(e)
        return f"Tool failed after {max_retries} retries: {last_error}"

    @staticmethod
    def _format_step(step: AgentStep) -> str:
        parts = []
        if step.thought:
            parts.append(f"Thought: {step.thought}")
        if step.action:
            import json
            parts.append(f"Action: {step.action}")
            parts.append(f"Action Input: {json.dumps(step.action_input)}")
        return "\n".join(parts)

    @staticmethod
    def _build_user_message(task: str, context: dict[str, Any]) -> str:
        if context:
            ctx_str = "\n".join(f"  {k}: {v}" for k, v in context.items())
            return f"Task: {task}\n\nContext:\n{ctx_str}"
        return f"Task: {task}"