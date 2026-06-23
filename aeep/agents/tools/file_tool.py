"""File tool — read, write, and list files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aeep.agents.tools.base_tool import BaseTool, ToolResult


class FileTool(BaseTool):
    name = "file_tool"
    description = "Read, write, and list files on the filesystem."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read_file", "write_file", "list_files"],
                "description": "The file operation to perform.",
            },
            "path": {"type": "string", "description": "File or directory path."},
            "content": {
                "type": "string",
                "description": "Content to write (only for write_file).",
            },
        },
        "required": ["action", "path"],
    }

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self._base_dir / p
        # Prevent path traversal outside base_dir
        p = p.resolve()
        try:
            p.relative_to(self._base_dir.resolve())
        except ValueError:
            raise PermissionError(f"Access denied: {path!r} is outside the sandbox")
        return p

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        path_str = args.get("path", "")

        try:
            resolved = self._resolve(path_str)
            if action == "read_file":
                text = resolved.read_text(encoding="utf-8")
                return ToolResult(success=True, output=text)

            elif action == "write_file":
                content = args.get("content", "")
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(content, encoding="utf-8")
                return ToolResult(success=True, output=f"Written {len(content)} chars to {path_str}")

            elif action == "list_files":
                if not resolved.is_dir():
                    return ToolResult(success=False, error=f"Not a directory: {path_str}")
                entries = [e.name for e in sorted(resolved.iterdir())]
                return ToolResult(success=True, output=entries)

            else:
                return ToolResult(success=False, error=f"Unknown action: {action!r}")

        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except FileNotFoundError:
            return ToolResult(success=False, error=f"File not found: {path_str}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))