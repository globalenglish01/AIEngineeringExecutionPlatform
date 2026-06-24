"""AEEP Web UI — Gradio interface backed by Browser LLM (free, no API key needed).

Run:
    uv run python app.py
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Any

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
            _loop = asyncio.new_event_loop()
            t = threading.Thread(target=_loop.run_forever, daemon=True)
            t.start()
    return _loop


def run_async(coro: Any, timeout: int = 300) -> Any:
    future = asyncio.run_coroutine_threadsafe(coro, _bg_loop())
    return future.result(timeout=timeout)


# ---------------------------------------------------------------------------
# Global browser provider registry (one per target, kept alive)
# ---------------------------------------------------------------------------
_providers: dict[str, Any] = {}


async def _get_provider(target: str) -> Any:
    from aeep.providers.browser.browser_provider import BrowserProvider

    if target not in _providers:
        _providers[target] = BrowserProvider(target=target)
    return _providers[target]


# ---------------------------------------------------------------------------
# UI action handlers
# ---------------------------------------------------------------------------

def do_connect(target: str) -> tuple[str, dict]:
    try:
        provider = run_async(_get_provider(target))
        run_async(provider._ensure_initialized(), timeout=60)
        msg = (
            f"浏览器已启动！请在弹出的浏览器窗口中登录 {target}，"
            "登录完成后回到此页面即可使用。"
        )
        return msg, gr.update(variant="secondary", value="已连接 ✓")
    except Exception as exc:
        return f"启动失败: {exc}", gr.update(variant="primary", value="启动浏览器")


def do_chat(
    user_msg: str,
    history: list[list[str]],
    target: str,
) -> tuple[list[list[str]], str]:
    if not user_msg.strip():
        return history, ""
    try:
        from aeep.core.models.message import Message, Role

        provider = run_async(_get_provider(target))
        messages: list[Message] = []
        for pair in history:
            messages.append(Message(role=Role.USER, content=pair[0]))
            messages.append(Message(role=Role.ASSISTANT, content=pair[1]))
        messages.append(Message(role=Role.USER, content=user_msg))

        result = run_async(provider.complete(messages), timeout=300)
        history = history + [[user_msg, result.content]]
        return history, ""
    except Exception as exc:
        history = history + [[user_msg, f"❌ 错误: {exc}"]]
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

        provider = run_async(_get_provider(target))
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
        connect_btn = gr.Button("🚀 启动浏览器", variant="primary", scale=1)
        status_txt = gr.Textbox(
            value="尚未连接 — 点击「启动浏览器」",
            label="状态",
            interactive=False,
            scale=3,
            elem_classes=["status-bar"],
        )

    connect_btn.click(
        do_connect,
        inputs=[target_dd],
        outputs=[status_txt, connect_btn],
    )

    # ---------- 功能标签页 ----------
    with gr.Tabs():

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
## 快速开始

1. **选择 AI 目标**（顶部下拉菜单）
2. **点击「启动浏览器」** — 会弹出一个 Chromium 窗口
3. **在弹出窗口中登录**对应网站（ChatGPT / Claude.ai / DeepSeek）
4. 登录成功后回到此页面，**开始对话或使用 Agent**

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
    print("  AEEP Web UI 启动中...")
    print("  浏览器将自动打开: http://localhost:7860")
    print("=" * 60)
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        show_error=True,
        theme=gr.themes.Soft(),
    )
