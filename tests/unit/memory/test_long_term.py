"""Tests for LongTermMemory (SQLite fallback mode)."""

from __future__ import annotations

import pytest
from pathlib import Path

from aeep.memory.long_term import LongTermMemory


class TestLongTermMemory:
    def test_save_and_count(self):
        mem = LongTermMemory()  # in-memory SQLite
        mem.save("Python is a programming language")
        mem.save("asyncio enables concurrent code")
        assert mem.count() == 2

    def test_save_returns_id(self):
        mem = LongTermMemory()
        mid = mem.save("some fact")
        assert isinstance(mid, str)
        assert len(mid) > 0

    def test_search_finds_relevant(self):
        mem = LongTermMemory()
        mem.save("Python is great for machine learning")
        mem.save("JavaScript runs in the browser")
        mem.save("Docker containers are portable")
        results = mem.search("machine learning Python", k=3)
        assert len(results) >= 1
        assert "Python" in results[0].content

    def test_search_empty_store(self):
        mem = LongTermMemory()
        results = mem.search("anything", k=5)
        assert results == []

    def test_forget(self):
        mem = LongTermMemory()
        mid = mem.save("to be deleted")
        assert mem.count() == 1
        mem.forget(mid)
        assert mem.count() == 0

    def test_persist_to_disk(self, tmp_path: Path):
        mem = LongTermMemory(persist_directory=tmp_path)
        mem.save("persisted fact")
        assert mem.count() == 1
        # Reload from same path
        mem2 = LongTermMemory(persist_directory=tmp_path)
        assert mem2.count() == 1

    def test_metadata_stored(self):
        mem = LongTermMemory()
        mid = mem.save("tagged fact", metadata={"tag": "important"})
        results = mem.search("tagged fact")
        assert len(results) >= 1
