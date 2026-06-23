"""Shell tool — run commands in a sandboxed subprocess."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from aeep.agents.tools.base_tool import BaseTool, ToolResult

# Commands that are always blocked
_BLOCKED = frozenset({"rm", "del", "rmdir", "mkfs", "dd", "shutdown", "reboot", "format"})


class ShellTool(BaseTool):
    name = "shell_tool"
    description = "Execute shell commands. Dangerous commands (rm, format, shutdown) are blocked."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)."},
            "cwd": {"type": "string", "description": "Working directory (optional)."},
        },
        "required": ["command"],
    }

    def __init__(self, allowed_commands: list[str] | None = None, timeout: int = 30) -> None:
        self._allowed = set(allowed_commands) if allowed_commands is not None else None
        self._default_timeout = timeout

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        command = args.get("command", "").strip()
        timeout = int(args.get("timeout", self._default_timeout))
        cwd = args.get("cwd")

        if not command:
            return ToolResult(success=False, error="No command provided")

        base_cmd = command.split()[0].lower()
        if base_cmd in _BLOCKED:
            return ToolResult(success=False, error=f"Command blocked for safety: {base_cmd!r}")

        if self._allowed is not None and base_cmd not in self._allowed:
            return ToolResult(success=False, error=f"Command not in allowlist: {base_cmd!r}")

        try:
            if sys.platform == "win32":
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    "bash", "-c", command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return ToolResult(
                success=(proc.returncode == 0),
                output={
                    "stdout": stdout.decode(errors="replace").strip(),
                    "stderr": stderr.decode(errors="replace").strip(),
                    "exit_code": proc.returncode,
                },
                error=stderr.decode(errors="replace").strip() if proc.returncode != 0 else "",
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ToolResult(success=False, error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))