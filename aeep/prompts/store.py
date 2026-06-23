"""Prompt template store — loads from filesystem, supports versioning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aeep.prompts.template import PromptTemplate


class PromptStore:
    """Loads and manages prompt templates from the filesystem.

    Directory layout::

        library/
            system/architect.j2
            tasks/analyze_requirement.j2
            ...

    A ``versions.json`` file in the root tracks version history.
    """

    def __init__(self, library_path: str | Path | None = None) -> None:
        if library_path is None:
            library_path = Path(__file__).parent / "library"
        self._root = Path(library_path)
        self._templates: dict[str, list[PromptTemplate]] = {}
        self._load_library()

    def _load_library(self) -> None:
        if not self._root.exists():
            return
        for j2_path in self._root.rglob("*.j2"):
            rel = j2_path.relative_to(self._root)
            name = str(rel.with_suffix("")).replace("\\", "/").replace("/", ".")
            source = j2_path.read_text(encoding="utf-8")
            tmpl = PromptTemplate(name=name, source=source)
            self._templates.setdefault(name, []).append(tmpl)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get(self, name: str, version: int | None = None) -> PromptTemplate:
        versions = self._templates.get(name)
        if not versions:
            raise KeyError(f"Template not found: {name!r}")
        if version is None:
            return versions[-1]
        for t in versions:
            if t.version == version:
                return t
        raise KeyError(f"Template {name!r} version {version} not found")

    def put(self, template: PromptTemplate) -> None:
        """Register or update a template (adds new version if content changed)."""
        existing = self._templates.get(template.name, [])
        if existing and existing[-1].source == template.source:
            return  # no change
        self._templates.setdefault(template.name, []).append(template)

    def list_names(self) -> list[str]:
        return sorted(self._templates.keys())

    def render(self, name: str, variables: dict[str, Any] | None = None) -> str:
        return self.get(name).render(variables)