"""Tests for ShortTermMemory."""

from __future__ import annotations

import pytest

from aeep.core.models.message import Message, Role
from aeep.memory.short_term import ShortTermMemory


def _msg(role: Role, content: str) -> Message:
    return Message(role=role, content=content)


class TestShortTermMemory:
    def test_add_and_retrieve(self):
        mem = ShortTermMemory(max_messages=10)
        mem.add(_msg(Role.USER, "hello"))
        mem.add(_msg(Role.ASSISTANT, "hi there"))
        assert len(mem) == 2
        msgs = mem.get_messages()
        assert msgs[0].content == "hello"
        assert msgs[1].content == "hi there"

    def test_trim_when_full(self):
        mem = ShortTermMemory(max_messages=4)
        for i in range(6):
            mem.add(_msg(Role.USER, f"msg {i}"))
        # After overflow trimming, we never exceed max_messages
        assert len(mem) <= mem.max_messages

    def test_summary_created_on_trim(self):
        mem = ShortTermMemory(max_messages=4)
        for i in range(6):
            mem.add(_msg(Role.USER, f"message {i}"))
        assert mem.get_summary() != ""

    def test_clear(self):
        mem = ShortTermMemory()
        mem.add(_msg(Role.USER, "test"))
        mem.clear()
        assert len(mem) == 0
        assert mem.get_summary() == ""

    def test_to_context_string_includes_messages(self):
        mem = ShortTermMemory()
        mem.add(_msg(Role.USER, "what is Python?"))
        ctx = mem.to_context_string()
        assert "what is Python?" in ctx

    def test_to_context_string_includes_summary(self):
        mem = ShortTermMemory(max_messages=2)
        for i in range(4):
            mem.add(_msg(Role.USER, f"m{i}"))
        ctx = mem.to_context_string()
        assert "Earlier conversation summary" in ctx
