"""Tests for bsage.core.scheduler — trigger registration and cron scheduling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from bsage.core.scheduler import Scheduler
from bsage.core.skill_loader import SkillMeta


def _make_meta(**overrides) -> SkillMeta:
    defaults = {
        "name": "test-skill",
        "version": "1.0.0",
        "category": "input",
        "is_dangerous": False,
        "description": "Test skill",
    }
    defaults.update(overrides)
    return SkillMeta(**defaults)


@pytest.fixture()
def mock_agent_loop():
    loop = MagicMock()
    loop.on_input = AsyncMock(return_value=[{"status": "ok"}])
    loop._registry = {
        "calendar-input": _make_meta(
            name="calendar-input",
            trigger={"type": "cron", "schedule": "*/15 * * * *"},
        ),
    }
    loop._build_context = MagicMock(return_value=MagicMock())
    return loop


@pytest.fixture()
def mock_skill_runner():
    runner = MagicMock()
    runner.run = AsyncMock(return_value={"events": [1, 2]})
    return runner


class TestParseCron:
    """Test cron expression parsing."""

    def test_parse_standard_cron(self) -> None:
        result = Scheduler._parse_cron("*/15 * * * *")
        assert result == {
            "minute": "*/15",
            "hour": "*",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_parse_specific_time(self) -> None:
        result = Scheduler._parse_cron("30 9 * * 1-5")
        assert result == {
            "minute": "30",
            "hour": "9",
            "day": "*",
            "month": "*",
            "day_of_week": "1-5",
        }

    def test_parse_invalid_cron_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cron"):
            Scheduler._parse_cron("*/15 *")

    def test_parse_daily_midnight(self) -> None:
        result = Scheduler._parse_cron("0 0 * * *")
        assert result["minute"] == "0"
        assert result["hour"] == "0"


class TestSchedulerRegisterTriggers:
    """Test trigger registration from skill registry."""

    def test_register_cron_triggers(self, mock_agent_loop, mock_skill_runner) -> None:
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        registry = {
            "calendar-input": _make_meta(
                name="calendar-input",
                trigger={"type": "cron", "schedule": "*/15 * * * *"},
            ),
        }
        scheduler.register_triggers(registry)
        assert "calendar-input" in scheduler._jobs

    def test_register_skips_non_cron_trigger(self, mock_agent_loop, mock_skill_runner) -> None:
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        registry = {
            "webhook-skill": _make_meta(
                name="webhook-skill",
                trigger={"type": "webhook"},
            ),
        }
        scheduler.register_triggers(registry)
        assert "webhook-skill" not in scheduler._jobs

    def test_register_skips_no_trigger(self, mock_agent_loop, mock_skill_runner) -> None:
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        registry = {
            "process-skill": _make_meta(
                name="process-skill",
                category="process",
                trigger=None,
            ),
        }
        scheduler.register_triggers(registry)
        assert len(scheduler._jobs) == 0


class TestSchedulerStartStop:
    """Test scheduler start and stop."""

    async def test_start_starts_apscheduler(self, mock_agent_loop, mock_skill_runner) -> None:
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        scheduler.start()
        assert scheduler._scheduler.running is True
        scheduler.stop()

    async def test_stop_stops_apscheduler(self, mock_agent_loop, mock_skill_runner) -> None:
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        scheduler.start()
        scheduler.stop()
        # AsyncIOScheduler defers state change to event loop
        await asyncio.sleep(0)
        assert scheduler._scheduler.running is False

    def test_stop_without_start_is_safe(self, mock_agent_loop, mock_skill_runner) -> None:
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        # Should not raise
        scheduler.stop()


class TestSchedulerOnTrigger:
    """Test trigger execution paths."""

    async def test_on_trigger_runs_skill_and_feeds_agent_loop(
        self, mock_agent_loop, mock_skill_runner
    ) -> None:
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        await scheduler._on_trigger("calendar-input")

        mock_skill_runner.run.assert_called_once()
        mock_agent_loop.on_input.assert_called_once_with("calendar-input", {"events": [1, 2]})

    async def test_on_trigger_handles_skill_error(self, mock_agent_loop, mock_skill_runner) -> None:
        mock_skill_runner.run = AsyncMock(side_effect=RuntimeError("skill failed"))
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        # Should not raise — error is logged internally
        await scheduler._on_trigger("calendar-input")
        mock_agent_loop.on_input.assert_not_called()

    async def test_on_trigger_missing_skill_raises(
        self, mock_agent_loop, mock_skill_runner
    ) -> None:
        scheduler = Scheduler(
            agent_loop=mock_agent_loop,
            skill_runner=mock_skill_runner,
        )
        # Should not raise — KeyError is caught by exception handler
        await scheduler._on_trigger("nonexistent")
        mock_skill_runner.run.assert_not_called()
