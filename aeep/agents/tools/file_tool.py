"""File tool — read, write, list files, and read CSV with column selection."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from aeep.agents.tools.base_tool import BaseTool, ToolResult


class FileTool(BaseTool):
    name = "file_tool"
    description = (
        "Read, write, and list files. "
        "Use action='read_csv' for CSV files to select specific columns and limit rows."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read_file", "write_file", "list_files", "read_csv"],
                "description": "The file operation to perform.",
            },
            "path": {"type": "string", "description": "File or directory path."},
            "content": {
                "type": "string",
                "description": "Content to write (only for write_file).",
            },
            "columns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Column names to include (read_csv only). Omit to get all columns.",
            },
            "limit": {
                "type": "integer",
                "description": "Max rows to return (read_csv only). Default 50.",
            },
            "offset": {
                "type": "integer",
                "description": "Row offset to start from (read_csv only). Default 0.",
            },
        },
        "required": ["action", "path"],
    }

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            # Absolute paths provided explicitly by the user are allowed as-is.
            return p.resolve()
        # Relative paths are resolved inside base_dir (sandbox).
        p = (self._base_dir / p).resolve()
        try:
            p.relative_to(self._base_dir.resolve())
        except ValueError:
            raise PermissionError(f"Access denied: {path!r} is outside the sandbox")
        return p

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        # Accept common LLM aliases for parameter names
        path_str = args.get("path") or args.get("file_path") or args.get("filename") or ""
        if "limit_rows" in args and "limit" not in args:
            args = dict(args, limit=args["limit_rows"])
        if "offset_rows" in args and "offset" not in args:
            args = dict(args, offset=args["offset_rows"])

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

            elif action == "read_csv":
                columns = args.get("columns") or []
                limit = int(args.get("limit") or 50)
                offset = int(args.get("offset") or 0)
                text = resolved.read_text(encoding="utf-8-sig")
                reader = csv.DictReader(io.StringIO(text))
                all_rows = list(reader)
                total = len(all_rows)
                rows = all_rows[offset : offset + limit]
                if columns:
                    rows = [{c: r.get(c, "") for c in columns} for r in rows]
                out = io.StringIO()
                if rows:
                    writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
                summary = f"# {total} rows total, showing {offset+1}–{offset+len(rows)}\n"
                return ToolResult(success=True, output=summary + out.getvalue())

            else:
                return ToolResult(success=False, error=f"Unknown action: {action!r}")

        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except FileNotFoundError:
            return ToolResult(success=False, error=f"File not found: {path_str}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))