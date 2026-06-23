"""Tests for alerting system."""

from __future__ import annotations

import pytest

from aeep.observability.alerting import (
    Alert,
    AlertManager,
    AlertSeverity,
    ConsoleAlertChannel,
    FileAlertChannel,
    get_alert_manager,
    reset_alert_manager,
)


@pytest.fixture(autouse=True)
def reset():
    reset_alert_manager()
    yield
    reset_alert_manager()


class TestAlertManager:
    @pytest.mark.asyncio
    async def test_alert_recorded_in_history(self):
        mgr = AlertManager(channels=[])
        await mgr.alert("Test", "Something happened", AlertSeverity.WARNING)
        assert len(mgr.history) == 1
        assert mgr.history[0].title == "Test"

    @pytest.mark.asyncio
    async def test_quality_gate_alert(self):
        mgr = AlertManager(channels=[])
        await mgr.quality_gate_failed("art-1", 55.0, 70.0)
        assert len(mgr.history) == 1
        assert "55.0" in mgr.history[0].message

    @pytest.mark.asyncio
    async def test_provider_failure_critical_at_3(self):
        mgr = AlertManager(channels=[])
        await mgr.provider_failure("openai", 3)
        assert mgr.history[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_provider_failure_warning_at_2(self):
        mgr = AlertManager(channels=[])
        await mgr.provider_failure("openai", 2)
        assert mgr.history[0].severity == AlertSeverity.WARNING

    @pytest.mark.asyncio
    async def test_budget_exceeded_alert(self):
        mgr = AlertManager(channels=[])
        await mgr.budget_exceeded(12.50, 10.00)
        assert mgr.history[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_file_channel(self, tmp_path):
        log_file = tmp_path / "alerts.jsonl"
        ch = FileAlertChannel(log_file)
        mgr = AlertManager(channels=[ch])
        await mgr.alert("File Test", "Written to disk", AlertSeverity.INFO)
        assert log_file.exists()
        content = log_file.read_text()
        assert "File Test" in content

    @pytest.mark.asyncio
    async def test_channel_failure_does_not_propagate(self):
        class FailChannel(ConsoleAlertChannel):
            async def send(self, alert: Alert) -> None:
                raise RuntimeError("channel broken")

        mgr = AlertManager(channels=[FailChannel()])
        # Should not raise
        await mgr.alert("Safe", "No crash", AlertSeverity.INFO)

    def test_singleton(self):
        m1 = get_alert_manager()
        m2 = get_alert_manager()
        assert m1 is m2
