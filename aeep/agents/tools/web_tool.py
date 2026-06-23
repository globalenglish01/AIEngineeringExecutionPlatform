"""Web tool — fetch and parse web pages via httpx + BeautifulSoup."""

from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup

from aeep.agents.tools.base_tool import BaseTool, ToolResult


class WebTool(BaseTool):
    name = "web_tool"
    description = "Fetch and extract text content from a URL."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch."},
            "extract": {
                "type": "string",
                "enum": ["text", "links", "title"],
                "description": "What to extract from the page (default: text).",
            },
            "timeout": {"type": "integer", "description": "Request timeout in seconds (default 15)."},
        },
        "required": ["url"],
    }

    def __init__(self, timeout: int = 15) -> None:
        self._timeout = timeout

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        url = args.get("url", "")
        extract = args.get("extract", "text")
        timeout = int(args.get("timeout", self._timeout))

        if not url:
            return ToolResult(success=False, error="No URL provided")

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "AEEP/1.0"})
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            if extract == "title":
                title = soup.title.string if soup.title else ""
                return ToolResult(success=True, output=title)

            elif extract == "links":
                links = [a.get("href", "") for a in soup.find_all("a", href=True)]
                return ToolResult(success=True, output=links[:100])

            else:  # text
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                # Truncate to 5000 chars
                return ToolResult(success=True, output=text[:5000])

        except httpx.HTTPStatusError as e:
            return ToolResult(success=False, error=f"HTTP {e.response.status_code}: {url}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))