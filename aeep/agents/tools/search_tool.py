"""Search tool — grep and glob over the filesystem."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from aeep.agents.tools.base_tool import BaseTool, ToolResult


class SearchTool(BaseTool):
    name = "search_tool"
    description = "Search files using grep (regex) or glob patterns."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["grep", "glob"],
                "description": "grep: regex search in files. glob: find files by pattern.",
            },
            "pattern": {"type": "string", "description": "Regex (grep) or glob pattern."},
            "path": {"type": "string", "description": "Root directory to search (default: cwd)."},
            "max_results": {"type": "integer", "description": "Max results to return (default 50)."},
        },
        "required": ["action", "pattern"],
    }

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        pattern = args.get("pattern", "")
        path_str = args.get("path", ".")
        max_results = int(args.get("max_results", 50))

        root = self._base_dir / path_str
        if not root.exists():
            return ToolResult(success=False, error=f"Path not found: {path_str}")

        try:
            if action == "glob":
                matches = [str(p.relative_to(self._base_dir)) for p in root.rglob(pattern)][:max_results]
                return ToolResult(success=True, output=matches)

            elif action == "grep":
                regex = re.compile(pattern)
                results: list[dict[str, Any]] = []
                for file in root.rglob("*"):
                    if not file.is_file():
                        continue
                    try:
                        text = file.read_text(encoding="utf-8", errors="ignore")
                        for lineno, line in enumerate(text.splitlines(), 1):
                            if regex.search(line):
                                results.append({
                                    "file": str(file.relative_to(self._base_dir)),
                                    "line": lineno,
                                    "text": line.strip(),
                                })
                                if len(results) >= max_results:
                                    break
                    except Exception:
                        continue
                    if len(results) >= max_results:
                        break
                return ToolResult(success=True, output=results)

            else:
                return ToolResult(success=False, error=f"Unknown action: {action!r}")
        except re.error as e:
            return ToolResult(success=False, error=f"Invalid regex: {e}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))