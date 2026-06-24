"""Live integration test: real DeepSeek browser + real CSV + Agent ReAct loop.

Run:
    uv run python tests/test_agent_live.py

What it tests:
  - DeepSeek account logs in / is reachable
  - Agent sends task, DeepSeek responds in ReAct format
  - file_tool.read_csv is called with correct args
  - Final answer is produced and saved to Downloads/memory_test_output.md
  - Any parse/loop failures are printed with the raw LLM text for diagnosis
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CSV     = r"C:\Users\Tigersoft\Downloads\n1_verbs_cards.csv"
OUTFILE = r"C:\Users\Tigersoft\Downloads\memory_test_output.md"
TASK    = f'为"{CSV}"中的word，kana，meaning列的日语单词生成最快最好的记忆方法（只处理前10行，输出结果）'

ACCOUNTS_FILE = Path(".browser_cookies/accounts.json")
COOKIE_DIR    = Path(".browser_cookies")


# ── Instrumented ReAct loop (logs every LLM reply) ───────────────────

class LoggingReActAgent:
    """Thin wrapper: runs agent.run() but prints every raw LLM reply."""

    def __init__(self, agent):
        self._agent = agent
        self._raw_replies: list[str] = []

    async def run(self, task: str):
        from aeep.core.models.message import Message, Role
        from aeep.agents.models import AgentResult, AgentStatus, AgentStep

        system_msg = Message(role=Role.SYSTEM,
                             content=self._agent._system_prompt())
        user_msg   = Message(role=Role.USER, content=f"Task: {task}")
        messages   = [system_msg, user_msg]
        steps: list[AgentStep] = []

        for iteration in range(self._agent._max_iterations):
            print(f"\n{'─'*60}")
            print(f"[ITER {iteration+1}] sending {len(messages)} messages to DeepSeek…")
            t0 = time.time()

            result = await self._agent._provider.complete(
                messages=messages, model="", temperature=0.7, max_tokens=2048,
            )
            elapsed = time.time() - t0
            raw = result.content
            self._raw_replies.append(raw)

            print(f"[ITER {iteration+1}] reply in {elapsed:.1f}s ({len(raw)} chars):")
            print("  " + raw[:600].replace("\n", "\n  "))

            step = self._agent._parse_step(raw)
            steps.append(step)

            print(f"[ITER {iteration+1}] parsed → action={step.action!r}  "
                  f"is_final={step.is_final}  thought={step.thought[:60]!r}")

            if step.is_final:
                print(f"\n[DONE] final answer ({len(step.thought)} chars)")
                # save
                Path(OUTFILE).write_text(step.thought, encoding="utf-8")
                print(f"[SAVED] {OUTFILE}")
                return AgentResult(
                    status=AgentStatus.COMPLETED,
                    output=step.thought,
                    steps=steps,
                    iterations=iteration + 1,
                )

            # Execute tool
            obs = await self._execute_tool(step)
            step.observation = obs
            print(f"[TOOL] {step.action} → {obs[:200]!r}")

            from aeep.agents.reasoning.react import ReActLoop
            messages.append(Message(role=Role.ASSISTANT,
                                    content=ReActLoop._format_step(step)))
            messages.append(Message(role=Role.USER, content=f"工具结果：{obs}"))

        return AgentResult(
            status=AgentStatus.FAILED,
            output="",
            steps=steps,
            error=f"max_iterations={self._agent._max_iterations} exceeded",
            iterations=self._agent._max_iterations,
        )

    async def _execute_tool(self, step) -> str:
        try:
            res = await self._agent._registry.execute(step.action, step.action_input)
            return str(res)
        except Exception as e:
            return f"Tool error: {e}"


# ── main ─────────────────────────────────────────────────────────────

async def _debug_deepseek_response(pool):
    """Send a trivial message, dump raw HTML + text from every candidate selector."""
    from aeep.providers.browser.account_pool import AccountPool
    slot = pool.slots()[0]
    await pool._ensure_provider(slot)
    provider = slot.provider
    session  = provider._session
    page = await session.get_page("debug")
    base_url = provider._target.base_url
    await page.goto(base_url, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    # Type a very short message
    import asyncio as _a
    INPUT_BOX = "textarea[placeholder], div[contenteditable='true']"
    SEND_BTN  = "button[class*='sendButton'], button[aria-label*='send'], button[aria-label*='Send']"
    await page.wait_for_selector(INPUT_BOX, timeout=10_000)
    el = await page.query_selector(INPUT_BOX)
    await el.click()
    await el.fill("")
    await page.keyboard.type("请用一句话介绍自己", delay=20)
    btns = await page.query_selector_all(SEND_BTN)
    if btns:
        await btns[-1].click()
    else:
        await page.keyboard.press("Enter")

    await asyncio.sleep(8)  # wait for response

    # Dump all candidate selectors
    selectors = [
        "[class*='markdown']",
        "[class*='ds-markdown']",
        "[class*='chat-message']",
        "[class*='message-content']",
        "[class*='assistant']",
        "div[class*='md']",
    ]
    print("\nPage title:", await page.title())
    for sel in selectors:
        els = await page.query_selector_all(sel)
        if els:
            txt = await els[-1].inner_text()
            html = await els[-1].inner_html()
            print(f"\n  selector={sel!r}  count={len(els)}")
            print(f"  text={txt[:150]!r}")
            print(f"  html={html[:200]!r}")


async def main():
    from aeep.providers.browser.account_pool import AccountPool
    from aeep.agents.base_agent import BaseAgent
    from aeep.agents.tools.file_tool import FileTool

    print("=== Live Agent Test: DeepSeek + real CSV ===")
    print(f"Task: {TASK}\n")

    # Load pool
    pool = AccountPool(target="deepseek", cookie_dir=COOKIE_DIR,
                       accounts_file=ACCOUNTS_FILE)
    print(f"Accounts loaded: {pool.slot_count()}")
    if pool.slot_count() == 0:
        print("ERROR: no deepseek accounts in accounts.json")
        return False

    class PoolProvider:
        async def complete(self, messages, model="", **kw):
            return await pool.complete(messages, model=model, **kw)

    agent = BaseAgent(
        name="assistant",
        role="你是一位专业的 AI 助手，请用中文详细回答问题。",
        provider=PoolProvider(),
        tools=[FileTool()],
        max_iterations=6,
    )

    # First: debug what DeepSeek actually returns for a simple message
    print("\n--- DEBUG: raw DeepSeek response for simple prompt ---")
    await _debug_deepseek_response(pool)

    wrapper = LoggingReActAgent(agent)
    result = await wrapper.run(task=TASK)

    print(f"\n{'='*60}")
    print(f"STATUS : {result.status.value}")
    print(f"ITERS  : {result.iterations}")
    print(f"OUTPUT : {(result.output or '')[:400]}")
    if result.error:
        print(f"ERROR  : {result.error}")
    return result.status.value == "completed"


if __name__ == "__main__":
    # Windows requires ProactorEventLoop for Playwright subprocess
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
