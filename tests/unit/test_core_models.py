"""Tests for core data models."""

import pytest

from aeep.core.models.artifact import Artifact, ArtifactStatus, ArtifactType
from aeep.core.models.message import CompletionResult, Message, Role, StreamChunk
from aeep.core.models.validation import (
    GateResult,
    QualityGate,
    Severity,
    ValidationIssue,
    ValidationResult,
)


class TestMessage:
    def test_to_dict_without_name(self):
        msg = Message(role=Role.USER, content="hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "hello"}

    def test_to_dict_with_name(self):
        msg = Message(role=Role.ASSISTANT, content="hi", name="AgentA")
        d = msg.to_dict()
        assert d["name"] == "AgentA"

    def test_role_values(self):
        assert Role.SYSTEM.value == "system"
        assert Role.USER.value == "user"
        assert Role.ASSISTANT.value == "assistant"


class TestCompletionResult:
    def test_total_tokens(self):
        result = CompletionResult(
            content="hi",
            model="gpt-4o",
            provider_name="openai",
            input_tokens=100,
            output_tokens=50,
            finish_reason="stop",
            duration_ms=300,
        )
        assert result.total_tokens == 150


class TestStreamChunk:
    def test_final_chunk(self):
        chunk = StreamChunk(delta="done", is_final=True, finish_reason="stop")
        assert chunk.is_final
        assert chunk.finish_reason == "stop"


class TestArtifact:
    def test_default_status(self):
        a = Artifact(artifact_type=ArtifactType.TEXT, content="hello")
        assert a.status == ArtifactStatus.PENDING

    def test_id_auto_generated(self):
        a1 = Artifact(artifact_type=ArtifactType.TEXT, content="a")
        a2 = Artifact(artifact_type=ArtifactType.TEXT, content="b")
        assert a1.id != a2.id


class TestValidationResult:
    def test_error_count(self):
        issues = [
            ValidationIssue(Severity.ERROR, "bad field", "schema"),
            ValidationIssue(Severity.WARNING, "minor issue", "rule"),
        ]
        result = ValidationResult("schema", passed=False, score=40.0, issues=issues)
        assert result.error_count == 1
        assert result.warning_count == 1


class TestQualityGate:
    def test_hard_gate_pass(self):
        gate = QualityGate(name="basic", min_score=70.0, gate_type="hard")
        result = ValidationResult("v", passed=True, score=80.0)
        assert gate.evaluate(result) == GateResult.PASS

    def test_hard_gate_fail_score(self):
        gate = QualityGate(name="basic", min_score=70.0, gate_type="hard")
        result = ValidationResult("v", passed=False, score=60.0)
        assert gate.evaluate(result) == GateResult.FAIL

    def test_hard_gate_fail_errors(self):
        gate = QualityGate(name="strict", min_score=70.0, max_error_count=0)
        issue = ValidationIssue(Severity.ERROR, "fatal", "rule")
        result = ValidationResult("v", passed=False, score=90.0, issues=[issue])
        assert gate.evaluate(result) == GateResult.FAIL

    def test_progressive_gate_iteration_1(self):
        gate = QualityGate(
            name="prog",
            min_score=85.0,
            gate_type="progressive",
            iteration=1,
            base_score=60.0,
            target_score=85.0,
            increment_per_iter=5.0,
        )
        assert gate.effective_min_score() == 60.0

    def test_progressive_gate_iteration_5(self):
        gate = QualityGate(
            name="prog",
            min_score=85.0,
            gate_type="progressive",
            iteration=5,
            base_score=60.0,
            target_score=85.0,
            increment_per_iter=5.0,
        )
        assert gate.effective_min_score() == 80.0

    def test_progressive_gate_capped(self):
        gate = QualityGate(
            name="prog",
            min_score=85.0,
            gate_type="progressive",
            iteration=100,
            base_score=60.0,
            target_score=85.0,
            increment_per_iter=5.0,
        )
        assert gate.effective_min_score() == 85.0
