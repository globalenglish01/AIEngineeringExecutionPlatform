"""AEEP Web UI — Gradio interface backed by Browser LLM (free, no API key needed).

Run:
    uv run python app.py
"""

from __future__ import annotations

import asyncio
import sys
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
    """Reopen the browser for an existing account (e.g. after page refresh)."""
    try:
        pool = _get_pool(target)
        for slot in pool.slots():
            if slot.label == slot_label:
                slot.provider = None   # force re-init
                run_async(pool._ensure_provider(slot), timeout=60)
                page = run_async(slot.provider._session.get_page("login"))
                try:
                    run_async(page.bring_to_front())
                except Exception:
                    pass
                return f"Browser reopened for '{slot_label}'. If not logged in, sign in now.", _render_account_table(target)
        return "Account not found.", _render_account_table(target)
    except Exception as exc:
        return f"Reconnect failed: {exc}", _render_account_table(target)


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


def do_chat(
    user_msg: str,
    history: list[list[str]],
    target: str,
) -> tuple[list[list[str]], str]:
    if not user_msg.strip():
        return history, ""
    try:
        from aeep.core.models.message import Message, Role
        from aeep.providers.browser.account_pool import AllAccountsCoolingError

        pool = _get_pool(target)
        if pool.slot_count() == 0:
            history = history + [[user_msg, "⚠️ 请先在「账号管理」Tab 添加至少一个账号"]]
            return history, ""

        messages: list[Message] = []
        for pair in history:
            messages.append(Message(role=Role.USER, content=pair[0]))
            messages.append(Message(role=Role.ASSISTANT, content=pair[1]))
        messages.append(Message(role=Role.USER, content=user_msg))

        result = run_async(pool.complete(messages), timeout=300)
        history = history + [[user_msg, result.content]]
        return history, ""
    except Exception as exc:
        history = history + [[user_msg, f"❌ {exc}"]]
        return history, ""


def do_agent(
    task: str,
    target: str,
    use_file: bool,
    use_search: bool,
    use_shell: bool,
) -> tuple[str, str]:
    if not task.strip():
        return "请先输入任务描述", ""
    try:
        from aeep.agents.base_agent import BaseAgent
        from aeep.agents.tools import FileTool, SearchTool, ShellTool

        pool = _get_pool(target)
        if pool.slot_count() == 0:
            return "⚠️ 请先在「账号管理」Tab 添加至少一个账号", ""

        # Wrap pool as a provider-like object for BaseAgent
        class _PoolAdapter:
            async def complete(self, messages, model="", **kw):
                return await pool.complete(messages, model=model, **kw)

        provider = _PoolAdapter()
        tools = []
        if use_file:
            tools.append(FileTool("."))
        if use_search:
            tools.append(SearchTool("."))
        if use_shell:
            tools.append(ShellTool())

        agent = BaseAgent(
            name="assistant",
            role="你是一位专业的 AI 助手，请用中文详细回答问题。",
            provider=provider,
            tools=tools,
            max_iterations=10,
        )
        result = run_async(agent.run(task=task, context={}), timeout=600)

        steps_md = ""
        for step in result.steps:
            if step.thought:
                steps_md += f"**💭 思考**\n{step.thought}\n\n"
            if step.action and step.action != "Final Answer":
                steps_md += f"**⚡ 行动** `{step.action}`\n```\n{step.action_input}\n```\n\n"
            if step.observation:
                steps_md += f"**👁 观察**\n{step.observation}\n\n---\n\n"

        return result.output or "(无输出)", steps_md
    except Exception as exc:
        return f"❌ 错误: {exc}", ""


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
# Build Gradio UI
# ---------------------------------------------------------------------------

CSS = """
.status-bar { font-size: 0.9em; color: #666; }
footer { display: none !important; }
"""

TARGET_CHOICES = [
    ("ChatGPT (chat.openai.com)", "chatgpt"),
    ("Claude.ai (claude.ai)", "claude_ai"),
    ("DeepSeek (chat.deepseek.com)", "deepseek"),
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

            with gr.Row():
                acct_select = gr.Dropdown(label="Select account", choices=[], scale=3)
                reconnect_btn = gr.Button("🔌 Reconnect", variant="primary", scale=1)
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

            def _send(msg, hist, tgt):
                return do_chat(msg, hist, tgt)

            send_btn.click(
                _send,
                inputs=[chat_input, chatbot, target_dd],
                outputs=[chatbot, chat_input],
            )
            chat_input.submit(
                _send,
                inputs=[chat_input, chatbot, target_dd],
                outputs=[chatbot, chat_input],
            )
            clear_btn.click(lambda: ([], ""), outputs=[chatbot, chat_input])

        # ── Tab 2: Agent 模式 ─────────────────────────────────────────
        with gr.Tab("🤖 Agent 模式"):
            gr.Markdown(
                "Agent 会自主分析任务、调用工具（文件读写、代码搜索、Shell）、"
                "循环推理直到得出答案。"
            )
            task_box = gr.Textbox(
                label="任务描述",
                placeholder="例：分析 aeep/validation/ 目录的代码架构，输出设计摘要",
                lines=4,
            )
            with gr.Row():
                chk_file = gr.Checkbox(label="📁 文件读写", value=True)
                chk_search = gr.Checkbox(label="🔍 代码搜索", value=True)
                chk_shell = gr.Checkbox(label="🖥 Shell 命令", value=False)
            run_agent_btn = gr.Button("▶ 运行 Agent", variant="primary")
            with gr.Row():
                agent_out = gr.Textbox(label="最终答案", lines=12, scale=3)
                agent_steps = gr.Markdown(label="推理过程", scale=2)

            run_agent_btn.click(
                do_agent,
                inputs=[task_box, target_dd, chk_file, chk_search, chk_shell],
                outputs=[agent_out, agent_steps],
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

        # ── Tab 4: 帮助 ───────────────────────────────────────────────
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
