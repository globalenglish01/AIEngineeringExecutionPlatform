"""Jinja2-based prompt template with variable interpolation and inheritance."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    Template,
    TemplateNotFound,
    select_autoescape,
)


# Module-level Jinja2 environment (can be reconfigured by PromptStore)
_default_env = Environment(
    undefined=StrictUndefined,
    autoescape=select_autoescape([]),
    keep_trailing_newline=True,
)


def render_template(source: str, variables: dict[str, Any]) -> str:
    """Render a Jinja2 template string with the given variables."""
    tmpl: Template = _default_env.from_string(source)
    return tmpl.render(**variables)


@dataclass
class PromptTemplate:
    """A versioned, renderable prompt template."""

    name: str
    source: str
    version: int = 1
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def render(self, variables: dict[str, Any] | None = None) -> str:
        return render_template(self.source, variables or {})

    def with_source(self, new_source: str) -> PromptTemplate:
        """Return a new template with incremented version."""
        return PromptTemplate(
            name=self.name,
            source=new_source,
            version=self.version + 1,
            description=self.description,
            tags=self.tags,
        )