"""End-to-end agent diagnostic.

Tests:
  1. FileTool.read_csv  — can read actual CSV with column selection
  2. _parse_step        — Chinese and English ReAct keyword parsing
  3. system→user merge  — no [System] header in browser prompt
  4. Full ReAct loop    — mock provider, tool called, result returned
"""
from __future__ import annotations
import asyncio
import sys
sys.path.insert(0, ".")

from aeep.agents.base_agent import BaseAgent
from aeep.agents.tools.file_tool import FileTool
from aeep.core.models.message import CompletionResult, Message, Role

CSV = r"C:\Users\Tigersoft\Downloads\n1_verbs_cards.csv"
TASK = f'为"{CSV}"中的word，kana，meaning列的日语单词生成最快最好的记忆方法'
PASS = "[OK]"
FAIL = "[FAIL]"


# ── helper ───────────────────────────────────────────────────────────

def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  {PASS if ok else FAIL}  {label}" + (f"  → {detail}" if detail else ""))
    return ok


# ── 1. FileTool.read_csv ─────────────────────────────────────────────

async def test_file_tool() -> bool:
    ft = FileTool()
    r = await ft.execute({
        "action": "read_csv",
        "path": CSV,
        "columns": ["word", "kana", "meaning"],
        "limit": 5,
    })
    if not check("FileTool.read_csv success", r.success, r.error or ""):
        return False
    output = r.output if isinstance(r.output, str) else str(r.output)
    has_header = "word" in output and "kana" in output
    check("CSV header present", has_header, output[:80])
    rows = [l for l in output.splitlines() if l.strip() and not l.startswith("#")]
    check("5 data rows + header returned", len(rows) == 6, f"rows={len(rows)}")
    return r.success


# ── 2. _parse_step ───────────────────────────────────────────────────

def test_parse_step() -> bool:
    fa = object.__new__(BaseAgent)
    all_ok = True

    def p(label: str, text: str, exp_action=None, exp_final=False):
        nonlocal all_ok
        step = fa._parse_step(text)
        ok_a = (step.action == exp_action) if exp_action is not None else True
        ok_f = step.is_final == exp_final
        ok = ok_a and ok_f
        all_ok = all_ok and ok
        detail = f"action={step.action!r} is_final={step.is_final}"
        check(f"parse({label})", ok, detail)

    p("CN tool call",
      "思考：需要读文件\n行动：file_tool\n输入：{\"action\": \"read_csv\", \"path\": \"x\"}",
      exp_action="file_tool")
    p("CN final",
      "思考：完成\n最终答案：结果在此",
      exp_final=True)
    p("EN tool call",
      "Thought: need file\nAction: file_tool\nAction Input: {\"action\": \"read_file\", \"path\": \"x\"}",
      exp_action="file_tool")
    p("no structure → final",
      "直接回答，没有格式",
      exp_final=True)
    p("multiline JSON input",
      '行动：file_tool\n输入：{\n  "action": "read_csv",\n  "path": "foo.csv"\n}',
      exp_action="file_tool")
    return all_ok


# ── 3. system prompt merge ────────────────────────────────────────────

def test_system_merge() -> bool:
    from aeep.providers.browser.base_browser_provider import BaseBrowserProvider
    fp = object.__new__(BaseBrowserProvider)
    msgs = [
        Message(role=Role.SYSTEM, content="You are an assistant."),
        Message(role=Role.USER,   content="Hello"),
    ]
    merged = fp._messages_to_prompt(msgs)
    no_header = not merged.startswith("[System]")
    system_included = "You are an assistant" in merged
    user_included = "Hello" in merged
    ok = no_header and system_included and user_included
    check("no [System] header", no_header, merged[:60])
    check("system content present", system_included)
    check("user content present", user_included)
    return ok


# ── 4. Full ReAct loop with mock provider ────────────────────────────

async def test_full_react() -> bool:
    csv_escaped = CSV.replace("\\", "\\\\")
    turns = iter([
        # Turn 1: AI reads CSV
        (
            "思考：我需要先读取CSV文件中指定的列。\n"
            "行动：file_tool\n"
            f'输入：{{"action": "read_csv", "path": "{csv_escaped}", "columns": ["word","kana","meaning"], "limit": 5}}'
        ),
        # Turn 2: AI produces final answer
        (
            "思考：已获得数据，现在输出记忆方法。\n"
            "最终答案：**相次ぐ** 谐音「爱追狗」→ 事情一件追一件。\n"
            "**喘ぐ** 谐音「啊诶古」→ 跑步后喘气声。"
        ),
    ])

    class MockProvider:
        async def complete(self, messages, **kw):
            return CompletionResult(
                content=next(turns, "最终答案：无更多输出"),
                model="mock", provider_name="mock",
                input_tokens=0, output_tokens=0,
                finish_reason="stop", duration_ms=0,
            )

    agent = BaseAgent(
        name="assistant",
        role="你是一位专业的 AI 助手，请用中文详细回答问题。",
        provider=MockProvider(),
        tools=[FileTool()],
        max_iterations=5,
    )
    result = await agent.run(task=TASK)

    completed = result.status.value == "completed"
    has_output = bool(result.output)
    tool_called = any(s.action == "file_tool" for s in result.steps)
    tool_got_data = any(s.observation and "word" in s.observation for s in result.steps)

    check("loop completed", completed, f"status={result.status.value} iter={result.iterations}")
    check("has output", has_output, (result.output or "")[:80])
    check("file_tool was called", tool_called)
    check("tool returned CSV data", tool_got_data,
          next((s.observation[:80] for s in result.steps if s.observation), "no obs"))
    if result.error:
        check("no error", False, result.error)
    return completed and has_output and tool_called


# ── main ─────────────────────────────────────────────────────────────

async def main():
    results = {}
    print("\n=== [1] FileTool.read_csv ===")
    results["file_tool"] = await test_file_tool()

    print("\n=== [2] _parse_step ===")
    results["parse"] = test_parse_step()

    print("\n=== [3] system→user merge ===")
    results["merge"] = test_system_merge()

    print("\n=== [4] Full ReAct loop ===")
    results["react"] = await test_full_react()

    print("\n=== SUMMARY ===")
    all_pass = True
    for name, ok in results.items():
        print(f"  {PASS if ok else FAIL}  {name}")
        all_pass = all_pass and ok
    print("\n" + ("ALL PASS" if all_pass else "SOME FAILURES — see above"))
    return all_pass

if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
