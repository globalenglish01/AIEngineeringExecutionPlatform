"""AEEP Web UI — Gradio interface backed by Browser LLM (free, no API key needed).

Run:
    uv run python app.py
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# xxhash DLL is blocked by security policy on this machine — mock it before
# any LangChain/LangSmith import chain tries to load the broken native extension.
if "xxhash" not in sys.modules:
    sys.modules["xxhash"] = MagicMock()

import asyncio
import json
import threading
import warnings
from pathlib import Path
from typing import Any

# Suppress Gradio 6 / Starlette internal deprecation noise
warnings.filterwarnings("ignore", category=DeprecationWarning, module="gradio")
warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")

import gradio as gr

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Async bridge: one persistent background event loop for all browser calls
# ---------------------------------------------------------------------------
_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _bg_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            # ProactorEventLoop required on Windows for Playwright subprocess windows
            if sys.platform == "win32":
                loop: asyncio.AbstractEventLoop = asyncio.ProactorEventLoop()
            else:
                loop = asyncio.new_event_loop()
            _loop = loop
            t = threading.Thread(target=_loop.run_forever, daemon=True)
            t.start()
    return _loop


def run_async(coro: Any, timeout: int = 300) -> Any:
    future = asyncio.run_coroutine_threadsafe(coro, _bg_loop())
    return future.result(timeout=timeout)


# ---------------------------------------------------------------------------
# Global AccountPool registry (one pool per target)
# ---------------------------------------------------------------------------
_COOKIE_DIR = Path(".browser_cookies")
_pools: dict[str, Any] = {}   # target → AccountPool


_ACCOUNTS_FILE = _COOKIE_DIR / "accounts.json"


def _get_pool(target: str) -> Any:
    from aeep.providers.browser.account_pool import AccountPool

    if target not in _pools:
        _COOKIE_DIR.mkdir(exist_ok=True)
        _pools[target] = AccountPool(
            target=target,
            cookie_dir=_COOKIE_DIR,
            accounts_file=_ACCOUNTS_FILE,
        )
    return _pools[target]


# ---------------------------------------------------------------------------
# UI action handlers
# ---------------------------------------------------------------------------

def do_add_account(target: str, label: str) -> tuple[str, Any]:
    """Add a new account slot — opens a browser window for login."""
    try:
        pool = _get_pool(target)
        lbl = label.strip() or None
        slot = run_async(pool.add_slot(lbl), timeout=60)
        target_names = {"chatgpt": "ChatGPT", "claude_ai": "Claude.ai", "deepseek": "DeepSeek"}
        name = target_names.get(target, target)
        msg = (
            f"浏览器已为「{slot.label}」打开。\n"
            f"请在弹出窗口中登录 {name}（支持 Google 账号）。\n"
            f"登录后点击「💾 保存登录状态」。"
        )
        return msg, _render_account_table(target)
    except Exception as exc:
        return f"❌ 添加失败: {exc}", _render_account_table(target)


def do_import(target: str, source_path: str) -> tuple[str, Any, Any]:
    try:
        pool = _get_pool(target)
        imported, skipped = pool.import_from_file(source_path.strip())
        msg = f"Imported {imported} account(s), skipped {skipped} duplicate(s)."
        choices = _slot_labels(target)
        return msg, _render_account_table(target), gr.update(choices=choices, value=choices[-1] if choices else None)
    except Exception as exc:
        return f"Import failed: {exc}", _render_account_table(target), gr.update()


def do_rename_from_table(target: str, data: Any) -> str:
    """Handle inline edits to the Account column. Returns status string (not table)
    to avoid triggering another change event and causing an infinite loop."""
    import pandas as pd
    pool = _get_pool(target)
    slots = pool.slots()
    if data is None or not slots:
        return ""
    rows = data.values.tolist() if isinstance(data, pd.DataFrame) else data
    renamed = []
    for i, row in enumerate(rows):
        if i >= len(slots):
            break
        new_label = str(row[1]).strip()
        if new_label and new_label != slots[i].label:
            slots[i].label = new_label
            renamed.append(new_label)
    if renamed:
        pool._save()
        return f"Renamed: {', '.join(renamed)}"
    return ""


def do_reconnect(target: str, slot_label: str) -> tuple[str, Any]:
    """Reopen the browser for an existing account and navigate to the target site."""
    try:
        pool = _get_pool(target)
        for slot in pool.slots():
            if slot.label == slot_label:
                slot.provider = None   # force re-init
                run_async(pool._ensure_provider(slot), timeout=60)
                page = run_async(slot.provider._session.get_page("login"))
                base_url = slot.provider._target.base_url
                run_async(
                    page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
                )
                run_async(page.bring_to_front())
                return f"Opened '{slot_label}' → {base_url}", _render_account_table(target)
        return "Account not found.", _render_account_table(target)
    except Exception as exc:
        return f"Reconnect failed: {exc}", _render_account_table(target)


def do_test_all(target: str) -> tuple[str, Any]:
    """Open every account, check login status, update table."""
    pool = _get_pool(target)
    if not pool.slots():
        return "No accounts to test.", _render_account_table(target)

    results = []
    for slot in pool.slots():
        try:
            slot.provider = None
            run_async(pool._ensure_provider(slot), timeout=60)
            page = run_async(slot.provider._session.get_page("test"))
            base_url = slot.provider._target.base_url
            run_async(page.goto(base_url, wait_until="domcontentloaded", timeout=30_000))
            logged_in = run_async(slot.provider._target.is_logged_in(page))
            slot.logged_in = logged_in
            slot.status = "ready" if logged_in else "ready"
            icon = "OK" if logged_in else "NOT LOGGED IN"
            results.append(f"{slot.label}: {icon}")
        except Exception as exc:
            results.append(f"{slot.label}: ERROR - {exc}")

    pool._save()
    summary = "\n".join(results)
    return summary, _render_account_table(target)


def do_remove_account(target: str, slot_label: str) -> tuple[str, Any]:
    try:
        pool = _get_pool(target)
        for slot in pool.slots():
            if slot.label == slot_label:
                run_async(pool.remove_slot(slot.index))
                return f"✅ 已删除账号「{slot_label}」", _render_account_table(target)
        return "❌ 未找到该账号", _render_account_table(target)
    except Exception as exc:
        return f"❌ 删除失败: {exc}", _render_account_table(target)


def do_refresh_status(target: str) -> Any:
    return _render_account_table(target)


def _render_account_table(target: str):
    import pandas as pd
    pool = _get_pool(target)
    rows = pool.status_table()
    if not rows:
        return pd.DataFrame(columns=["No.", "Account", "Status", "Cookie"])
    return pd.DataFrame(
        [[r["no"], r["account"], r["status"], r["cookie"]] for r in rows],
        columns=["No.", "Account", "Status", "Cookie"],
    )


def _slot_labels(target: str) -> list[str]:
    return [s.label for s in _get_pool(target).slots()]


_BROWSER_TARGETS = {"chatgpt", "claude_ai", "deepseek"}


def _is_browser(target: str) -> bool:
    return target in _BROWSER_TARGETS


def _make_api_provider(target: str, api_key: str, model: str):
    """Instantiate the correct API provider from target name."""
    key = api_key.strip()
    if not key:
        raise ValueError("请填写 API Key")
    if target == "api_openai":
        from aeep.providers.api.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=key), model or "gpt-4o-mini"
    if target == "api_anthropic":
        from aeep.providers.api.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=key), model or "claude-haiku-4-5-20251001"
    if target == "api_deepseek":
        from aeep.providers.api.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(api_key=key), model or "deepseek-chat"
    raise ValueError(f"Unknown API target: {target}")


def _make_lc_api_model(target: str, api_key: str, model: str) -> Any:
    """Wrap an AEEP API provider as a LangChain BaseChatModel."""
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from aeep.core.models.message import Message, Role as ARole

    provider, mdl = _make_api_provider(target, api_key, model)

    _role_map = {"human": ARole.USER, "ai": ARole.ASSISTANT, "system": ARole.SYSTEM}

    class _ApiChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return f"aeep-api-{target}"

        def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kw) -> ChatResult:
            msgs = [Message(role=_role_map.get(m.type, ARole.USER), content=m.content if isinstance(m.content, str) else str(m.content)) for m in messages]
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(provider.complete(msgs, model=mdl))
            finally:
                loop.close()
            text = result.content or ""
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

        async def _agenerate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kw) -> ChatResult:
            msgs = [Message(role=_role_map.get(m.type, ARole.USER), content=m.content if isinstance(m.content, str) else str(m.content)) for m in messages]
            result = await provider.complete(msgs, model=mdl)
            text = result.content or ""
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    return _ApiChatModel()


def do_chat(
    user_msg: str,
    history: list[list[str]],
    target: str,
    api_key: str = "",
    model: str = "",
) -> tuple[list[list[str]], str]:
    if not user_msg.strip():
        return history, ""
    try:
        from aeep.core.models.message import Message, Role

        messages: list[Message] = []
        for pair in history:
            messages.append(Message(role=Role.USER, content=pair[0]))
            messages.append(Message(role=Role.ASSISTANT, content=pair[1]))
        messages.append(Message(role=Role.USER, content=user_msg))

        if _is_browser(target):
            from aeep.providers.browser.account_pool import AllAccountsCoolingError
            pool = _get_pool(target)
            if pool.slot_count() == 0:
                history = history + [[user_msg, "⚠️ 请先在「账号管理」Tab 添加至少一个账号"]]
                return history, ""
            result = run_async(pool.complete(messages), timeout=300)
        else:
            provider, mdl = _make_api_provider(target, api_key, model)
            result = run_async(provider.complete(messages, model=mdl), timeout=300)

        history = history + [[user_msg, result.content]]
        return history, ""
    except Exception as exc:
        history = history + [[user_msg, f"❌ {exc}"]]
        return history, ""


def _extract_file_paths(text: str) -> list[str]:
    """Extract quoted file paths from task description."""
    import re
    return re.findall(r'["“”]((?:[A-Za-z]:\\|/)[^""“”\n]+)["“”]', text)


def _read_file_for_prompt(path: str, offset: int = 0, batch_size: int = 30) -> tuple[str, int, int]:
    """Read a file slice suitable for injection into a prompt.

    Returns (content_str, offset_after_batch, total_rows_or_chars).
    For CSV: returns all columns as-is (the AI decides what to do with them).
    For other files: returns a plain text slice.
    """
    import csv as _csv, io as _io
    p = Path(path)
    if not p.exists():
        return f"[文件不存在: {path}]", 0, 0
    if p.suffix.lower() == ".csv":
        text = p.read_text(encoding="utf-8-sig")
        all_rows = list(_csv.DictReader(_io.StringIO(text)))
        total = len(all_rows)
        batch = all_rows[offset: offset + batch_size]
        if not batch:
            return "", offset, total
        out = _io.StringIO()
        writer = _csv.DictWriter(out, fieldnames=list(batch[0].keys()))
        writer.writeheader()
        writer.writerows(batch)
        end = offset + len(batch)
        header = f"# 行 {offset+1}–{end}（共 {total} 行）\n"
        return header + out.getvalue(), end, total
    # Plain text: slice by characters
    raw = p.read_text(encoding="utf-8-sig", errors="replace")
    total = len(raw)
    chunk = raw[offset: offset + batch_size * 200]  # ~200 chars per "row" for plain text
    end = offset + len(chunk)
    return chunk, end, total


def do_agent(
    task: str,
    target: str,
    use_file: bool,
    use_search: bool,
    use_shell: bool,
    api_key: str = "",
    model: str = "",
    save_path: str = "",
    batch_size: int = 30,
) -> tuple[str, str]:
    if not task.strip():
        return "请先输入任务描述", ""
    try:
        return run_async(
            _agent_lc(
                task=task,
                target=target,
                use_file=use_file,
                use_search=use_search,
                use_shell=use_shell,
                api_key=api_key,
                model=model,
                save_path=save_path,
            ),
            timeout=600,
        )
    except Exception as exc:
        import traceback
        return f"❌ 错误: {exc}\n{traceback.format_exc()}", ""


async def _agent_lc(
    task: str,
    target: str,
    use_file: bool,
    use_search: bool,
    use_shell: bool,
    api_key: str,
    model: str,
    save_path: str,
) -> tuple[str, str]:
    """LangGraph create_react_agent — works for both browser and API providers."""
    import re as _re

    from langchain.agents import create_agent as create_react_agent
    from langchain_core.tools import tool as lc_tool
    from langchain_core.messages import HumanMessage

    from aeep.agents.tools import FileTool, SearchTool, ShellTool

    # ── 1. Build LangChain model ──────────────────────────────────────────────
    if _is_browser(target):
        pool = _get_pool(target)
        if pool.slot_count() == 0:
            return "⚠️ 请先在「账号管理」Tab 添加至少一个账号", ""
        from aeep.providers.browser.langchain_adapter import BrowserChatModel
        lc_model = BrowserChatModel(pool=pool, model_name="")
    else:
        lc_model = _make_lc_api_model(target, api_key, model)

    # ── 2. Build AEEP tools ───────────────────────────────────────────────────
    aeep_tools_list = []
    if use_file:
        aeep_tools_list.append(FileTool())
    if use_search:
        aeep_tools_list.append(SearchTool("."))
    if use_shell:
        aeep_tools_list.append(ShellTool())

    # ── 3. Wrap as LangChain @tool functions (JSON string input) ─────────────
    def _make_lc_tool(t: Any):
        schema_props = getattr(t, "input_schema", {}).get("properties", {})
        prop_hint = ", ".join(schema_props) or "action, path, ..."
        tool_desc = f"{t.description} Input must be a JSON string with keys: {prop_hint}"
        tool_name = t.name

        @lc_tool(tool_name)
        async def _tool_fn(input_json: str) -> str:
            """Executes a tool with a JSON-encoded arguments string."""
            try:
                args = json.loads(input_json)
            except json.JSONDecodeError:
                fixed = _re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', input_json)
                try:
                    args = json.loads(fixed)
                except json.JSONDecodeError:
                    args = {"input": input_json}
            if "path" in args and isinstance(args["path"], str):
                args["path"] = (args["path"]
                                .replace("\n", "\\n").replace("\t", "\\t")
                                .replace("\r", "\\r").replace("\b", "\\b"))
            result = await t.execute(args)
            return str(result.output) if result.success else f"Error: {result.error}"

        _tool_fn.description = tool_desc
        return _tool_fn

    lc_tools = [_make_lc_tool(t) for t in aeep_tools_list]

    # ── 4. System prompt ──────────────────────────────────────────────────────
    system_prompt = (
        "你是一位专业AI助手，利用工具完成用户任务，最终用中文回答。\n\n"
        "【工具调用格式】工具的 input_json 参数必须是合法JSON字符串，例如：\n"
        '  读CSV: {"action":"read_csv","path":"C:\\\\Users\\\\name\\\\file.csv","columns":["col1","col2"],"limit":10}\n'
        '  读文本/MD文件: {"action":"read_file","path":"D:\\\\My\\\\docs\\\\spec.md"}\n'
        '  写文件: {"action":"write_file","path":"output.txt","content":"结果内容"}\n\n'
        "Windows路径中的反斜杠必须写成双反斜杠：C:\\\\Users\\\\xxx"
    )

    # ── 5. Run create_agent (langchain 1.x / langgraph) ──────────────────────
    agent = create_react_agent(lc_model, lc_tools, system_prompt=system_prompt)
    result = await agent.ainvoke({"messages": [HumanMessage(content=task)]})

    # ── 6. Extract output and steps ───────────────────────────────────────────
    messages = result.get("messages", [])
    output = "(无输出)"
    steps_md = ""

    for msg in messages:
        msg_type = getattr(msg, "type", "")
        if msg_type == "tool":
            tool_name = getattr(msg, "name", "tool")
            obs_str = str(msg.content)
            steps_md += f"**👁 [{tool_name}] 结果**\n{obs_str[:500]}{'...' if len(obs_str) > 500 else ''}\n\n---\n\n"
        elif msg_type == "ai":
            content = msg.content or ""
            tool_calls = getattr(msg, "tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    tc_name = tc.get("name", "")
                    tc_args = tc.get("args", {})
                    steps_md += f"**⚡ 行动** `{tc_name}`\n```json\n{json.dumps(tc_args, ensure_ascii=False, indent=2)}\n```\n\n"
            elif content:
                output = content  # last AI content = final answer

    # ── 7. Save output ────────────────────────────────────────────────────────
    out_path = save_path.strip()
    if out_path and output and output != "(无输出)":
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(output, encoding="utf-8")
        steps_md += f"\n\n**💾 已保存到** `{out_path}`"

    return output, steps_md


# ---------------------------------------------------------------------------
# 批量记忆生成（Memory Generation Batch）
# ---------------------------------------------------------------------------

_MEMORY_RULES = """\
【谐音记忆生成规则】
类型判断：词条(word字段)若为片假名外来语（kana全为片假名字符）→ 输出空对象 {}，不生成x/l。
否则（汉字/平假名词）必须生成 x + l 两个字段。

x（谐音）规则：
1. 以kana读音为准，选与读音最接近的中文词/短语
2. 最长匹配优先：优先将多个音节合并为一个有意义的中文词，禁止逐音节强行拼音
   正例：あいつぐ(ai-tsu-gu)→爱吃苦  かたづけ→靠它止咳  うんめい→纹眉
   错例：あいつぐ→阿卡（无关）、阿+一+吃+苦（逐音节）
3. 允许使用专有名词、口语词、方言词，音近即可

l（联想例句）规则：
1. 必须包含x谐音词，句子含义要暗示日语单词的意思
2. ≤20字，用中文口语，要自然
   例：x=爱吃苦 meaning=相继发生 → l="妈妈爱吃苦，麻烦事一件接一件。"

输出格式（纯JSON，不加任何说明文字）：
{"单词1": {"x": "谐音词", "l": "联想例句"}, "单词2": {}, ...}
"""


def _extract_json_obj(text: str) -> dict | None:
    """从LLM输出中提取第一个JSON对象。"""
    import re
    # Try to find a JSON object in the text
    # Remove markdown code fences first
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Find first { ... } block
    start = text.find("{")
    if start == -1:
        return None
    # Try increasingly large slices from the end
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
    return None


def do_memory_gen(
    csv_path: str,
    output_path: str,
    batch_size: int,
    target: str,
    api_key: str,
    model: str,
) -> tuple[str, str]:
    """批量为CSV里的日语单词生成谐音记忆，结果保存到 output_path。"""
    csv_path = csv_path.strip()
    output_path = output_path.strip()
    if not csv_path:
        return "请填写 CSV 文件路径", ""
    try:
        return run_async(
            _memory_gen_async(csv_path, output_path, int(batch_size), target, api_key, model),
            timeout=3600,
        )
    except Exception as exc:
        import traceback
        return f"❌ 错误: {exc}\n{traceback.format_exc()}", ""


async def _memory_gen_async(
    csv_path: str,
    output_path: str,
    batch_size: int,
    target: str,
    api_key: str,
    model: str,
) -> tuple[str, str]:
    import csv as _csv
    import io as _io
    from langchain_core.messages import HumanMessage

    # ── 1. 读 CSV ─────────────────────────────────────────────────────────────
    text = Path(csv_path).read_text(encoding="utf-8-sig")
    reader = _csv.DictReader(_io.StringIO(text))
    all_rows = list(reader)
    total = len(all_rows)
    if total == 0:
        return "CSV 文件为空", ""

    # ── 2. 构建 LLM ───────────────────────────────────────────────────────────
    if _is_browser(target):
        pool = _get_pool(target)
        if pool.slot_count() == 0:
            return "⚠️ 请先在「账号管理」Tab 添加至少一个账号", ""
        from aeep.providers.browser.langchain_adapter import BrowserChatModel
        lc_model = BrowserChatModel(pool=pool, model_name="")
    else:
        lc_model = _make_lc_api_model(target, api_key, model)

    # ── 3. 逐批处理 ────────────────────────────────────────────────────────────
    all_results: dict = {}
    out_path = Path(output_path) if output_path else None
    progress_lines: list[str] = []
    failed_batches: list[str] = []

    for batch_start in range(0, total, batch_size):
        batch = all_rows[batch_start : batch_start + batch_size]
        # 构建单词列表（只取需要的列）
        words_text = "\n".join(
            f"{r.get('word', r.get('单词', ''))} "
            f"[{r.get('kana', r.get('假名', ''))}] "
            f"{r.get('meaning', r.get('含义', r.get('意思', '')))}"
            for r in batch
        )
        prompt = (
            f"{_MEMORY_RULES}\n\n"
            f"为以下 {len(batch)} 个日语单词生成记忆方法（第{batch_start+1}~{batch_start+len(batch)}个，共{total}个）：\n\n"
            f"{words_text}"
        )
        try:
            response = await lc_model.ainvoke([HumanMessage(content=prompt)])
            raw = response.content if hasattr(response, "content") else str(response)
            obj = _extract_json_obj(raw)
            if obj:
                all_results.update(obj)
                progress_lines.append(
                    f"✅ 第{batch_start+1}~{batch_start+len(batch)}个（{len(obj)}个成功）"
                )
            else:
                failed_batches.append(f"第{batch_start+1}~{batch_start+len(batch)}个（JSON解析失败）")
                progress_lines.append(f"⚠️ 第{batch_start+1}~{batch_start+len(batch)}个 JSON解析失败")
        except Exception as exc:
            progress_lines.append(f"❌ 第{batch_start+1}~{batch_start+len(batch)}个 错误: {exc}")

        # 每批完成后立即保存（追加写入以防崩溃丢数据）
        if out_path and all_results:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(all_results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    # ── 4. 返回结果 ────────────────────────────────────────────────────────────
    summary = f"**共处理 {total} 个单词，成功生成 {len(all_results)} 条记忆**\n\n"
    if out_path:
        summary += f"**已保存到** `{out_path}`\n\n"
    if failed_batches:
        summary += "**失败批次：**\n" + "\n".join(failed_batches) + "\n\n"

    preview = json.dumps(dict(list(all_results.items())[:5]), ensure_ascii=False, indent=2)
    return preview, summary + "\n".join(progress_lines)


def do_validate(text: str, min_words: int, min_sections: int) -> tuple[str, str]:
    if not text.strip():
        return "请输入待验证的文本", ""
    try:
        from aeep.core.models.artifact import Artifact, ArtifactType
        from aeep.validation.engine import ValidationEngine
        from aeep.validation.models import RuleType, ValidationRule
        from aeep.validation.quality_gate import GateRule, QualityGate
        from aeep.validation.report import ValidationReport

        rules = []
        if min_words > 0:
            rules.append(
                ValidationRule("word_count", RuleType.RULE, config={"min_words": min_words})
            )
        if min_sections > 0:
            rules.append(
                ValidationRule("structure", RuleType.SCHEMA, config={"min_sections": min_sections})
            )
        rules.append(ValidationRule("consistency", RuleType.CONSISTENCY, config={}))

        artifact = Artifact(artifact_type=ArtifactType.MARKDOWN, content=text)
        engine = ValidationEngine()
        result = run_async(engine.validate(artifact, rules))
        report = ValidationReport(result)

        gate = QualityGate(
            name="default",
            hard_gates=[GateRule("hard", min_score=60.0)],
            soft_gates=[GateRule("soft", min_score=80.0)],
        )
        decision = gate.evaluate(result)

        badge = {"PASS": "🟢 通过", "WARN": "🟡 警告", "BLOCK": "🔴 阻断"}.get(
            decision.value.upper(), decision.value
        )
        summary = (
            f"## {badge}\n\n"
            f"| 指标 | 值 |\n|---|---|\n"
            f"| 总分 | **{result.score:.1f} / 100** |\n"
            f"| 字数 | {len(text.split())} |\n"
            f"| 错误 | {result.error_count} |\n"
            f"| 警告 | {result.warning_count} |\n"
        )
        return summary, report.to_markdown()
    except Exception as exc:
        return f"❌ 错误: {exc}", ""


# ---------------------------------------------------------------------------
# Workflow Execution
# ---------------------------------------------------------------------------

def _load_workflow_yaml(yaml_path: str) -> dict:
    """Load a workflow YAML file and return the raw dict."""
    import yaml
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_dag_from_yaml(wf_dict: dict) -> Any:
    """Build a DAG from a workflow YAML dict, registering all node types."""
    from aeep.workflow.dag import DAG
    from aeep.workflow.nodes.llm_node import LLMNode
    from aeep.workflow.nodes.validation_node import ValidationNode
    from aeep.workflow.nodes.code_execution_node import CodeExecutionNode
    from aeep.workflow.nodes.branch_node import BranchNode
    from aeep.workflow.nodes.loop_node import LoopNode

    defaults = wf_dict.get("defaults", {})
    nodes_cfg = wf_dict.get("nodes", [])

    dag = DAG()

    _NODE_CLASSES = {
        "llm": LLMNode,
        "validation": ValidationNode,
        "code_execution": CodeExecutionNode,
        "branch": BranchNode,
    }

    built: dict[str, Any] = {}
    for n in nodes_cfg:
        node_id = n["id"]
        node_type = n["type"]
        depends_on = n.get("depends_on", [])
        # Merge defaults into config (node-level overrides defaults)
        cfg = dict(defaults)
        cfg.update(n.get("config", {}))

        if node_type == "loop":
            # LoopNode has no inner_nodes wired from YAML in this simple loader
            node = LoopNode(node_id=node_id, inner_nodes=[], depends_on=depends_on, config=cfg)
        elif node_type in _NODE_CLASSES:
            node = _NODE_CLASSES[node_type](node_id=node_id, depends_on=depends_on, config=cfg)
        else:
            # Unknown type — fall through as a no-op LLM node
            node = LLMNode(node_id=node_id, depends_on=depends_on, config=cfg)

        built[node_id] = node
        dag.add_node(node)

    return dag


async def _run_workflow_async(
    yaml_path: str,
    initial_context: dict,
    pool: Any,
    progress_cb: Any = None,
) -> tuple[dict, list[str]]:
    """Load YAML, build DAG, inject Browser LLM pool, run, return (context, log_lines)."""
    from aeep.workflow.runner import WorkflowRunner

    wf_dict = _load_workflow_yaml(yaml_path)
    dag = _build_dag_from_yaml(wf_dict)

    # Inject pool as direct provider so LLMNode skips ProviderRegistry
    ctx = dict(initial_context)
    ctx["_provider"] = pool

    log_lines: list[str] = []

    async def _on_start(node_id: str) -> None:
        msg = f"▶ 运行节点: {node_id}"
        log_lines.append(msg)
        if progress_cb:
            progress_cb(msg)

    async def _on_done(node_id: str, output: dict | None) -> None:
        keys = list((output or {}).keys())
        msg = f"✅ 完成: {node_id}  输出键: {keys}"
        log_lines.append(msg)
        if progress_cb:
            progress_cb(msg)

    async def _on_error(node_id: str, exc: Exception) -> None:
        msg = f"❌ 失败: {node_id}  错误: {exc}"
        log_lines.append(msg)
        if progress_cb:
            progress_cb(msg)

    runner = WorkflowRunner(
        workflow_name=wf_dict.get("name", "workflow"),
        dag=dag,
    )
    run = await runner.run(
        initial_context=ctx,
    )
    # Attach callbacks manually (runner doesn't support per-node cb without plugins)
    # We re-implement a lightweight version above via DAG callbacks
    return run.final_context, log_lines


async def _run_workflow_with_log(
    yaml_path: str,
    initial_context: dict,
    pool: Any,
) -> tuple[dict, list[str]]:
    """Run workflow and capture per-node progress via DAG._run_node monkey-patching."""
    from aeep.workflow.dag import DAG
    from aeep.workflow.runner import WorkflowRunner

    wf_dict = _load_workflow_yaml(yaml_path)
    dag = _build_dag_from_yaml(wf_dict)

    ctx = dict(initial_context)
    ctx["_provider"] = pool
    log_lines: list[str] = []

    async def _on_start(node_id: str) -> None:
        log_lines.append(f"▶ [{node_id}] 开始执行…")

    async def _on_done(node_id: str, output: dict | None) -> None:
        keys = list((output or {}).keys())
        log_lines.append(f"✅ [{node_id}] 完成  → {keys}")

    async def _on_error(node_id: str, exc: Exception) -> None:
        log_lines.append(f"❌ [{node_id}] 失败: {exc}")

    runner = WorkflowRunner(workflow_name=wf_dict.get("name", "workflow"), dag=dag)
    run = await runner.run(
        initial_context=ctx,
    )
    # runner doesn't expose per-node callbacks directly; extract from node_runs
    for node_id, nr in run.node_runs.items():
        status = nr.status.value if hasattr(nr.status, "value") else str(nr.status)
        dur = f"{nr.duration_ms}ms" if nr.duration_ms else "?"
        log_lines.append(f"  {status.upper()} [{node_id}] {dur}")

    return run.final_context, log_lines


def _run_chapter_workflow(
    chapter_title: str,
    requirements: str,
    target: str,
    api_key: str,
    model: str,
    min_words: int,
    min_score: float,
) -> tuple[str, str, str]:
    """Run write_book_chapter.yaml and validate output. Returns (content, validation_report, log)."""
    if not chapter_title.strip():
        return "", "请输入章节标题", ""
    try:
        # Build provider
        if _is_browser(target):
            pool = _get_pool(target)
            if pool.slot_count() == 0:
                return "", "⚠️ 请先在「账号管理」Tab 添加至少一个账号", ""
        else:
            provider, mdl = _make_api_provider(target, api_key, model)
            # Wrap API provider as a duck-typed pool with .complete()
            class _ApiPool:
                async def complete(self, messages, model=""):
                    return await provider.complete(messages, model=mdl)
            pool = _ApiPool()

        yaml_path = str(Path(__file__).parent / "workflows" / "templates" / "write_book_chapter.yaml")
        initial_ctx = {
            "chapter_title": chapter_title,
            "requirements": requirements or f"为技术读者撰写关于 {chapter_title} 的完整章节，字数不少于 {min_words} 字，包含代码示例和最佳实践。",
        }

        final_ctx, log_lines = run_async(
            _run_workflow_with_log(yaml_path, initial_ctx, pool),
            timeout=600,
        )

        chapter_content = final_ctx.get("chapter_content", "")
        log_text = "\n".join(log_lines)

        # Validate with ValidationEngine
        from aeep.core.models.artifact import Artifact, ArtifactType
        from aeep.validation.engine import ValidationEngine
        from aeep.validation.models import RuleType, ValidationRule
        from aeep.validation.report import ValidationReport

        rules = [
            ValidationRule("word_count", RuleType.RULE, config={"min_words": min_words}, weight=3.0),
            ValidationRule("structure", RuleType.RULE, config={"min_sections": 4}, weight=2.0),
            ValidationRule("no_placeholder", RuleType.RULE, config={"no_placeholder": True}, weight=1.0),
            ValidationRule("consistency", RuleType.CONSISTENCY, config={}, weight=1.0),
        ]
        artifact = Artifact(artifact_type=ArtifactType.MARKDOWN, content=chapter_content, title=chapter_title)
        engine = ValidationEngine()
        val_result = run_async(engine.validate(artifact, rules))
        report_md = ValidationReport(val_result).to_markdown()

        score_line = f"**总得分**: {val_result.score:.1f}/100  决策: {val_result.gate_decision.value.upper()}"
        report_md = score_line + "\n\n" + report_md

        return chapter_content, report_md, log_text

    except Exception as exc:
        import traceback
        return "", f"❌ 错误: {exc}\n{traceback.format_exc()}", ""


def _run_feature_workflow(
    feature_name: str,
    feature_request: str,
    tech_stack: str,
    target: str,
    api_key: str,
    model: str,
) -> tuple[str, str, str, str]:
    """Run develop_feature.yaml and validate code. Returns (impl_code, test_code, test_results, log)."""
    if not feature_name.strip():
        return "", "", "请输入功能名称", ""
    try:
        if _is_browser(target):
            pool = _get_pool(target)
            if pool.slot_count() == 0:
                return "", "", "⚠️ 请先在「账号管理」Tab 添加至少一个账号", ""
        else:
            provider, mdl = _make_api_provider(target, api_key, model)
            class _ApiPool:
                async def complete(self, messages, model=""):
                    return await provider.complete(messages, model=mdl)
            pool = _ApiPool()

        yaml_path = str(Path(__file__).parent / "workflows" / "templates" / "develop_feature.yaml")
        initial_ctx = {
            "feature_name": feature_name,
            "feature_request": feature_request or f"实现一个 Python 模块：{feature_name}",
            "tech_stack": tech_stack or "Python 3.11",
        }

        final_ctx, log_lines = run_async(
            _run_workflow_with_log(yaml_path, initial_ctx, pool),
            timeout=600,
        )

        impl_code = final_ctx.get("implementation_code", "")
        test_code = final_ctx.get("test_code", "")
        test_results_raw = final_ctx.get("test_results", {})
        code_review_raw = final_ctx.get("code_review", "")
        log_text = "\n".join(log_lines)

        # Format test results
        if isinstance(test_results_raw, dict):
            stdout = test_results_raw.get("stdout", "")
            stderr = test_results_raw.get("stderr", "")
            exit_code = test_results_raw.get("exit_code", -1)
            test_summary = f"Exit code: {exit_code}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        else:
            test_summary = str(test_results_raw)

        # Validate code with CodeValidator
        from aeep.validation.engine import ValidationEngine
        from aeep.validation.models import RuleType, ValidationRule
        from aeep.core.models.artifact import Artifact, ArtifactType
        from aeep.validation.report import ValidationReport

        code_rules = [
            ValidationRule("syntax", RuleType.CODE, config={"language": "python", "checks": ["syntax"]}, weight=3.0),
            ValidationRule("style", RuleType.CODE, config={"language": "python", "checks": ["ruff"]}, weight=1.0),
        ]
        code_artifact = Artifact(artifact_type=ArtifactType.CODE, content=impl_code, title=feature_name)
        engine = ValidationEngine()
        val_result = run_async(engine.validate(code_artifact, code_rules))
        val_report = ValidationReport(val_result).to_markdown()

        combined_result = (
            f"**代码验证得分**: {val_result.score:.1f}/100  决策: {val_result.gate_decision.value.upper()}\n\n"
            + val_report
            + ("\n\n---\n\n**Code Review:**\n\n" + str(code_review_raw) if code_review_raw else "")
            + f"\n\n---\n\n**测试运行结果:**\n```\n{test_summary}\n```"
        )

        return impl_code, test_code, combined_result, log_text

    except Exception as exc:
        import traceback
        return "", "", f"❌ 错误: {exc}\n{traceback.format_exc()}", ""


# ---------------------------------------------------------------------------
# Build Gradio UI
# ---------------------------------------------------------------------------

CSS = """
.status-bar { font-size: 0.9em; color: #666; }
footer { display: none !important; }
"""

TARGET_CHOICES = [
    ("🌐 ChatGPT (浏览器·免费)", "chatgpt"),
    ("🌐 Claude.ai (浏览器·免费)", "claude_ai"),
    ("🌐 DeepSeek (浏览器·免费)", "deepseek"),
    ("🔑 OpenAI API", "api_openai"),
    ("🔑 Anthropic API", "api_anthropic"),
    ("🔑 DeepSeek API", "api_deepseek"),
]

with gr.Blocks(title="AEEP · AI 工程执行平台") as demo:

    gr.Markdown(
        """
# 🤖 AEEP · AI 工程执行平台
**免费使用** ChatGPT / Claude.ai / DeepSeek — 无需 API Key，通过浏览器自动化驱动
"""
    )

    # ---------- 顶部连接栏 ----------
    with gr.Row(equal_height=True):
        target_dd = gr.Dropdown(
            choices=TARGET_CHOICES,
            value="chatgpt",
            label="选择 AI 目标",
            scale=2,
        )
        status_txt = gr.Textbox(
            value="请在「账号管理」Tab 添加账号后开始使用",
            label="状态",
            interactive=False,
            scale=5,
            elem_classes=["status-bar"],
        )

    # API Key row (only visible when an API target is selected)
    with gr.Row(visible=False) as api_key_row:
        api_key_box = gr.Textbox(
            label="API Key",
            placeholder="sk-... 或 sk-ant-...",
            type="password",
            scale=3,
        )
        api_model_box = gr.Textbox(
            label="模型（可留空用默认）",
            placeholder="gpt-4o-mini / claude-haiku-4-5-20251001 / deepseek-chat",
            scale=3,
        )

    def _on_target_change(tgt):
        is_api = not _is_browser(tgt)
        return gr.update(visible=is_api)

    target_dd.change(_on_target_change, inputs=[target_dd], outputs=[api_key_row])

    # ---------- 功能标签页 ----------
    with gr.Tabs():

        # ── Tab 0: 账号管理 ────────────────────────────────────────────
        with gr.Tab("👥 账号管理"):
            gr.Markdown(
                "每个账号对应一个独立的浏览器会话。"
                "当某账号达到使用限制时，系统**自动切换**到下一个可用账号。"
            )
            with gr.Row():
                acct_label_box = gr.Textbox(
                    label="账号备注名（可选）",
                    placeholder="例：Google账号1、工作账号…",
                    scale=3,
                )
                add_acct_btn = gr.Button("➕ 添加账号", variant="primary", scale=1)

            acct_status_txt = gr.Textbox(
                label="操作状态",
                interactive=False,
                value="",
            )
            acct_table = gr.Dataframe(
                headers=["No.", "Account", "Status", "Cookie"],
                label="Account Pool (Account column is editable)",
                interactive=True,
                row_count=(1, "dynamic"),
            )

            # Import from other project
            with gr.Row():
                import_path_box = gr.Textbox(
                    label="Import from accounts.json (paste full path)",
                    placeholder=r"D:\My\AIEducationOS\engine\llm\accounts.json",
                    scale=4,
                )
                import_btn = gr.Button("📥 Import", variant="secondary", scale=1)

            test_all_btn = gr.Button("🧪 Test All Accounts", variant="primary")

            with gr.Row():
                acct_select = gr.Dropdown(label="Select account", choices=[], scale=3)
                reconnect_btn = gr.Button("🔌 Reconnect", variant="secondary", scale=1)
                del_acct_btn = gr.Button("🗑 Remove", variant="stop", scale=1)
                refresh_btn = gr.Button("🔄 Refresh", scale=1)

            def _add(target, label):
                msg, _ = do_add_account(target, label)
                choices = _slot_labels(target)
                return msg, _render_account_table(target), gr.update(choices=choices, value=choices[-1] if choices else None)

            def _reconnect(target, lbl):
                msg, _ = do_reconnect(target, lbl)
                return msg, _render_account_table(target)

            def _del(target, lbl):
                msg, _ = do_remove_account(target, lbl)
                choices = _slot_labels(target)
                return msg, _render_account_table(target), gr.update(choices=choices, value=choices[0] if choices else None)

            def _refresh(target):
                choices = _slot_labels(target)
                return _render_account_table(target), gr.update(choices=choices)

            import_btn.click(
                do_import,
                inputs=[target_dd, import_path_box],
                outputs=[acct_status_txt, acct_table, acct_select],
            )
            test_all_btn.click(
                do_test_all,
                inputs=[target_dd],
                outputs=[acct_status_txt, acct_table],
            )
            add_acct_btn.click(
                _add,
                inputs=[target_dd, acct_label_box],
                outputs=[acct_status_txt, acct_table, acct_select],
            )
            reconnect_btn.click(
                _reconnect,
                inputs=[target_dd, acct_select],
                outputs=[acct_status_txt, acct_table],
            )
            del_acct_btn.click(
                _del,
                inputs=[target_dd, acct_select],
                outputs=[acct_status_txt, acct_table, acct_select],
            )
            refresh_btn.click(
                _refresh,
                inputs=[target_dd],
                outputs=[acct_table, acct_select],
            )
            # Reload table when switching target
            target_dd.change(
                _refresh,
                inputs=[target_dd],
                outputs=[acct_table, acct_select],
            )
            # Auto-populate table on page load / refresh
            demo.load(
                _refresh,
                inputs=[target_dd],
                outputs=[acct_table, acct_select],
            )
            # Inline rename: outputs to status text only (not back to table) to avoid loop
            acct_table.change(
                do_rename_from_table,
                inputs=[target_dd, acct_table],
                outputs=[acct_status_txt],
            )

        # ── Tab 1: 对话 ──────────────────────────────────────────────
        with gr.Tab("💬 对话"):
            chatbot = gr.Chatbot(height=480, label="对话记录")
            with gr.Row():
                chat_input = gr.Textbox(
                    placeholder="输入消息，按 Enter 发送…",
                    label="",
                    scale=5,
                    autofocus=True,
                )
                send_btn = gr.Button("发送", variant="primary", scale=1)
                clear_btn = gr.Button("清空", scale=1)

            def _send(msg, hist, tgt, key, mdl):
                return do_chat(msg, hist, tgt, api_key=key, model=mdl)

            send_btn.click(
                _send,
                inputs=[chat_input, chatbot, target_dd, api_key_box, api_model_box],
                outputs=[chatbot, chat_input],
            )
            chat_input.submit(
                _send,
                inputs=[chat_input, chatbot, target_dd, api_key_box, api_model_box],
                outputs=[chatbot, chat_input],
            )
            clear_btn.click(lambda: ([], ""), outputs=[chatbot, chat_input])

        # ── Tab 2: Agent 模式 ─────────────────────────────────────────
        with gr.Tab("🤖 Agent 模式"):
            gr.Markdown(
                "**浏览器模式**：自动分批读取文件，逐批发给 AI，结果合并保存\n\n"
                "**API 模式**：AI 自主调用工具循环推理直到完成任务"
            )
            task_box = gr.Textbox(
                label="任务描述",
                placeholder='例：为 "C:\\Users\\xxx\\Downloads\\n1_verbs_cards.csv" 中的所有单词生成记忆方法',
                lines=4,
            )
            with gr.Row():
                chk_file = gr.Checkbox(label="📁 文件读写", value=True)
                chk_search = gr.Checkbox(label="🔍 代码搜索", value=True)
                chk_shell = gr.Checkbox(label="🖥 Shell 命令", value=False)
            with gr.Row():
                save_path_box = gr.Textbox(
                    label="💾 保存结果到（路径，留空则不保存）",
                    placeholder=r"C:\Users\xxx\Downloads\memory_output.md",
                    scale=4,
                )
                batch_size_sl = gr.Slider(
                    minimum=10, maximum=100, value=30, step=10,
                    label="每批行数（浏览器模式）",
                    scale=2,
                )
            run_agent_btn = gr.Button("▶ 运行 Agent", variant="primary")
            with gr.Row():
                agent_out = gr.Textbox(label="最终答案（最后一批预览）", lines=12, scale=3)
                agent_steps = gr.Markdown(label="处理进度", scale=2)

            run_agent_btn.click(
                do_agent,
                inputs=[task_box, target_dd, chk_file, chk_search, chk_shell,
                        api_key_box, api_model_box, save_path_box, batch_size_sl],
                outputs=[agent_out, agent_steps],
            )

            # ── 批量记忆生成 ─────────────────────────────────────────────
            with gr.Accordion("📚 批量记忆生成（谐音/联想）", open=False):
                gr.Markdown(
                    "自动为 CSV 里的所有日语单词批量生成谐音(x)和联想例句(l)，"
                    "按批次发给 AI 处理，结果累积保存到 JSON 文件。"
                )
                with gr.Row():
                    mem_csv_box = gr.Textbox(
                        label="CSV 文件路径（需含 word, kana, meaning 列）",
                        placeholder=r"D:\My\StudyAthena\n1_verbs_cards_v2.csv",
                        scale=3,
                    )
                    mem_out_box = gr.Textbox(
                        label="输出 JSON 路径",
                        placeholder=r"D:\My\StudyAthena\memory_output.json",
                        scale=3,
                    )
                    mem_batch_sl = gr.Slider(
                        minimum=5, maximum=50, value=10, step=5,
                        label="每批单词数",
                        scale=1,
                    )
                mem_run_btn = gr.Button("▶ 开始批量生成", variant="primary")
                with gr.Row():
                    mem_preview = gr.Textbox(label="结果预览（前5条）", lines=10, scale=3)
                    mem_progress = gr.Markdown(label="进度", scale=2)

            mem_run_btn.click(
                do_memory_gen,
                inputs=[mem_csv_box, mem_out_box, mem_batch_sl,
                        target_dd, api_key_box, api_model_box],
                outputs=[mem_preview, mem_progress],
            )

        # ── Tab 3: 质量验证 ───────────────────────────────────────────
        with gr.Tab("✅ 质量验证"):
            gr.Markdown("粘贴文本，自动检验字数、章节结构、术语一致性，输出评分报告。")
            with gr.Row():
                with gr.Column(scale=3):
                    val_text = gr.Textbox(
                        label="待验证文本（Markdown）",
                        lines=18,
                        placeholder="粘贴文章、章节或说明文档…",
                    )
                with gr.Column(scale=2):
                    min_words_sl = gr.Slider(0, 5000, value=200, step=50, label="最少字数要求")
                    min_sec_sl = gr.Slider(0, 20, value=3, step=1, label="最少章节数要求")
                    val_btn = gr.Button("🔍 开始验证", variant="primary")
                    val_summary = gr.Markdown(label="验证摘要")

            val_report = gr.Markdown(label="完整报告")

            val_btn.click(
                do_validate,
                inputs=[val_text, min_words_sl, min_sec_sl],
                outputs=[val_summary, val_report],
            )

        # ── Tab 4: Workflow 自动化 ────────────────────────────────────
        with gr.Tab("⚙️ Workflow 自动化"):
            gr.Markdown(
                "使用 YAML Workflow 全自动完成复杂任务：技术写作、代码生成。"
                "由 Browser LLM 驱动，无需 API Key。"
            )

            with gr.Tabs():

                # Sub-Tab A: 技术文档写作
                with gr.Tab("📝 A. 技术文档写作"):
                    gr.Markdown("**使用 `write_book_chapter.yaml`** — 自动分析需求 → 生成提纲 → 写作章节 → Validation Engine 验证")
                    with gr.Row():
                        wf_chapter_title = gr.Textbox(
                            label="章节标题",
                            value="Python asyncio 最佳实践",
                            scale=3,
                        )
                        wf_chapter_minwords = gr.Slider(500, 5000, value=2000, step=100, label="最少字数", scale=2)
                        wf_chapter_minscore = gr.Slider(50, 100, value=80, step=5, label="质量得分门限", scale=2)
                    wf_chapter_req = gr.Textbox(
                        label="补充要求（可留空）",
                        placeholder="例：面向有 Python 基础的读者，包含事件循环、协程、任务管理、错误处理等核心内容，至少 5 个代码示例",
                        lines=3,
                    )
                    wf_chapter_btn = gr.Button("▶ 运行 Workflow", variant="primary")
                    with gr.Row():
                        wf_chapter_content = gr.Textbox(label="生成的章节内容", lines=20, scale=3)
                        with gr.Column(scale=2):
                            wf_chapter_report = gr.Markdown(label="Validation 报告")
                    wf_chapter_log = gr.Textbox(label="执行日志", lines=6, interactive=False)

                    wf_chapter_btn.click(
                        _run_chapter_workflow,
                        inputs=[wf_chapter_title, wf_chapter_req, target_dd,
                                api_key_box, api_model_box, wf_chapter_minwords, wf_chapter_minscore],
                        outputs=[wf_chapter_content, wf_chapter_report, wf_chapter_log],
                    )

                # Sub-Tab B: 代码生成
                with gr.Tab("💻 B. 代码自动生成"):
                    gr.Markdown("**使用 `develop_feature.yaml`** — 自动分析需求 → 设计方案 → 生成代码 → 生成测试 → Code Validator 验证")
                    with gr.Row():
                        wf_feat_name = gr.Textbox(
                            label="功能名称",
                            value="simple_calculator",
                            scale=2,
                        )
                        wf_feat_stack = gr.Textbox(
                            label="技术栈",
                            value="Python 3.11",
                            scale=2,
                        )
                    wf_feat_req = gr.Textbox(
                        label="功能需求描述",
                        value="实现一个简单计算器 Python 模块，支持加减乘除四则运算，包含输入验证和除零保护，提供完整的 pytest 测试套件，测试覆盖率 ≥ 70%",
                        lines=3,
                    )
                    wf_feat_btn = gr.Button("▶ 运行 Workflow", variant="primary")
                    with gr.Row():
                        wf_feat_impl = gr.Textbox(label="实现代码", lines=20, scale=3)
                        wf_feat_test = gr.Textbox(label="测试代码", lines=20, scale=3)
                    wf_feat_result = gr.Markdown(label="验证报告 & 测试结果")
                    wf_feat_log = gr.Textbox(label="执行日志", lines=6, interactive=False)

                    wf_feat_btn.click(
                        _run_feature_workflow,
                        inputs=[wf_feat_name, wf_feat_req, wf_feat_stack,
                                target_dd, api_key_box, api_model_box],
                        outputs=[wf_feat_impl, wf_feat_test, wf_feat_result, wf_feat_log],
                    )

        # ── Tab 5: 帮助 ───────────────────────────────────────────────
        with gr.Tab("📖 使用说明"):
            gr.Markdown("""
## 快速开始（首次）

1. **选择 AI 目标**（顶部下拉）：ChatGPT / Claude.ai / DeepSeek
2. 进入 **「👥 账号管理」Tab**，点 **「➕ 添加账号」**
3. 在弹出的浏览器窗口中，**用 Google 账号登录**对应网站
4. 回到管理 Tab，点 **「💾 保存登录状态」** — 下次无需重新登录
5. 重复 2-4 步骤可**添加多个账号**，达到限额时自动轮转

## 多账号轮转机制

- 系统按**轮询**顺序使用账号
- 某账号触发限额时，**自动标为冷却**并切换到下一个
- 冷却结束后自动恢复为可用状态
- 账号池里所有账号都冷却时，会返回等待时间提示

## 再次启动（已保存 Cookie）

直接添加账号（Cookie 自动加载），无需重新登录。

---

## 各标签页说明

| 标签 | 功能 |
|------|------|
| 💬 对话 | 与 AI 自由对话，保持多轮上下文 |
| 🤖 Agent | 给出复杂任务，AI 自主调用工具完成 |
| ✅ 质量验证 | 检验文章/代码质量，输出评分报告 |

## Agent 工具说明

| 工具 | 用途 |
|------|------|
| 📁 文件读写 | 读取/写入项目文件 |
| 🔍 代码搜索 | 在项目中搜索关键词或文件 |
| 🖥 Shell 命令 | 执行安全命令（rm/del 等危险命令已屏蔽） |

## 注意事项

- 浏览器窗口**不要关闭**，它是与 AI 通信的通道
- 如果 AI 网站要求人机验证，在浏览器窗口中手动完成即可
- 每个 AI 目标对应一个独立的浏览器会话
""")

if __name__ == "__main__":
    print("=" * 60)
    print("  AEEP Web UI starting...")
    print("  Open in browser: http://localhost:7860")
    print("=" * 60)
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        show_error=True,
        theme=gr.themes.Soft(),
    )
