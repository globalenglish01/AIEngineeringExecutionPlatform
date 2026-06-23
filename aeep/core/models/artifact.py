"""Artifact models 窶・outputs produced by the platform."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ArtifactType(str, Enum):
    TEXT = "text"
    CODE = "code"
    MARKDOWN = "markdown"
    JSON = "json"
    FILE = "file"
    DATASET = "dataset"
    REPORT = "report"


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    VALIDATING = "validating"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class Artifact:
    artifact_type: ArtifactType
    content: str
    title: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ArtifactStatus = ArtifactStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)
    # task and run context
    task_type: str | None = None
    run_id: str | None = None
    # quality
    quality_score: float | None = None
    validation_issues: list[str] = field(default_factory=list)
