"""CodeExecutionNode — runs code in a subprocess sandbox."""

from __future__ import annotations

import asyncio
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any

from aeep.workflow.nodes.base import BaseNode

logger = logging.getLogger(__name__)


class CodeExecutionNode(BaseNode):
    """Execute Python code from context in a sandboxed subprocess.

    Config keys:
        code_key       str   context key with code string (default: "code")
        timeout        int   seconds before killing the process (default: 30)
        output_key     str   where to store execution result (default: node_id)
        language       str   "python" only for now (default: "python")
    """

    node_type = "code_execution"

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        code_key: str = self.config.get("code_key", "code")
        timeout: int = int(self.config.get("timeout", 30))
        output_key: str = self.config.get("output_key", self.node_id)
        code: str = context.get(code_key, "")

        if not code.strip():
            return {output_key: {"stdout": "", "stderr": "no code provided", "exit_code": 1}}

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                exit_code = proc.returncode or 0
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                logger.warning("CodeExecutionNode '%s': timeout after %ds", self.node_id, timeout)
                return {
                    output_key: {
                        "stdout": "",
                        "stderr": f"Execution timed out after {timeout}s",
                        "exit_code": -1,
                    }
                }
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")

        logger.info(
            "CodeExecutionNode '%s': exit_code=%d stdout=%d chars",
            self.node_id,
            exit_code,
            len(stdout),
        )

        return {output_key: {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}}
