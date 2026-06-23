"""Tests for built-in agent tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeep.agents.tools.file_tool import FileTool
from aeep.agents.tools.memory_tool import MemoryTool
from aeep.agents.tools.search_tool import SearchTool
from aeep.agents.tools.shell_tool import ShellTool
from aeep.agents.tools.validation_tool import ValidationTool
from aeep.memory.memory_store import MemoryStore


class TestFileTool:
    @pytest.mark.asyncio
    async def test_write_and_read(self, tmp_path: Path):
        tool = FileTool(base_dir=tmp_path)
        write_result = await tool.execute({"action": "write_file", "path": "hello.txt", "content": "world"})
        assert write_result.success
        read_result = await tool.execute({"action": "read_file", "path": "hello.txt"})
        assert read_result.success
        assert read_result.output == "world"

    @pytest.mark.asyncio
    async def test_list_files(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        tool = FileTool(base_dir=tmp_path)
        result = await tool.execute({"action": "list_files", "path": "."})
        assert result.success
        assert "a.txt" in result.output

    @pytest.mark.asyncio
    async def test_read_nonexistent(self, tmp_path: Path):
        tool = FileTool(base_dir=tmp_path)
        result = await tool.execute({"action": "read_file", "path": "missing.txt"})
        assert not result.success

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path: Path):
        tool = FileTool(base_dir=tmp_path)
        result = await tool.execute({"action": "read_file", "path": "../../etc/passwd"})
        assert not result.success

    @pytest.mark.asyncio
    async def test_unknown_action(self, tmp_path: Path):
        tool = FileTool(base_dir=tmp_path)
        result = await tool.execute({"action": "delete", "path": "x.txt"})
        assert not result.success


class TestSearchTool:
    @pytest.mark.asyncio
    async def test_glob(self, tmp_path: Path):
        (tmp_path / "foo.py").write_text("def foo(): pass")
        tool = SearchTool(base_dir=tmp_path)
        result = await tool.execute({"action": "glob", "pattern": "*.py"})
        assert result.success
        assert any("foo.py" in f for f in result.output)

    @pytest.mark.asyncio
    async def test_grep(self, tmp_path: Path):
        (tmp_path / "code.py").write_text("def my_function():\n    return 42\n")
        tool = SearchTool(base_dir=tmp_path)
        result = await tool.execute({"action": "grep", "pattern": "my_function"})
        assert result.success
        assert len(result.output) >= 1
        assert result.output[0]["line"] == 1

    @pytest.mark.asyncio
    async def test_invalid_regex(self, tmp_path: Path):
        tool = SearchTool(base_dir=tmp_path)
        result = await tool.execute({"action": "grep", "pattern": "["})
        assert not result.success


class TestShellTool:
    @pytest.mark.asyncio
    async def test_echo_command(self):
        tool = ShellTool(timeout=10)
        result = await tool.execute({"command": "echo hello"})
        assert result.success
        assert "hello" in result.output["stdout"]

    @pytest.mark.asyncio
    async def test_blocked_command(self):
        tool = ShellTool()
        # "rm" is in the blocked list
        result = await tool.execute({"command": "rm somefile"})
        assert not result.success
        assert "blocked" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_command(self):
        tool = ShellTool()
        result = await tool.execute({"command": ""})
        assert not result.success


class TestValidationTool:
    @pytest.mark.asyncio
    async def test_pass_long_content(self):
        tool = ValidationTool()
        result = await tool.execute({"content": "word " * 300, "min_score": 60})
        assert result.success
        assert result.output["passed"] is True

    @pytest.mark.asyncio
    async def test_fail_empty(self):
        tool = ValidationTool()
        result = await tool.execute({"content": ""})
        assert not result.success

    @pytest.mark.asyncio
    async def test_fail_short(self):
        tool = ValidationTool()
        result = await tool.execute({"content": "hi", "min_score": 80})
        assert result.output["passed"] is False


class TestMemoryTool:
    @pytest.mark.asyncio
    async def test_save_and_search(self):
        store = MemoryStore()
        tool = MemoryTool(memory_store=store)
        save_result = await tool.execute({"action": "save_memory", "content": "Python is great for AI"})
        assert save_result.success
        search_result = await tool.execute({"action": "search_memory", "query": "Python AI"})
        assert search_result.success
        assert len(search_result.output) >= 1

    @pytest.mark.asyncio
    async def test_missing_content(self):
        store = MemoryStore()
        tool = MemoryTool(memory_store=store)
        result = await tool.execute({"action": "save_memory"})
        assert not result.success
