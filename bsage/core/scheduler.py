"""Scheduler — registers cron triggers for InputSkills via APScheduler."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from bsage.core.agent_loop import AgentLoop
    from bsage.core.skill_loader import SkillMeta
    from bsage.core.skill_runner import SkillRunner

logger = structlog.get_logger(__name__)

_CRON_FIELDS = ("minute", "hour", "day", "month", "day_of_week")


class Scheduler:
    """Registers and manages cron triggers for InputSkills."""

    def __init__(
        self,
        agent_loop: AgentLoop,
        skill_runner: SkillRunner,
    ) -> None:
        self._agent_loop = agent_loop
        self._skill_runner = skill_runner
        self._scheduler = AsyncIOScheduler()
        self._jobs: dict[str, str] = {}  # skill_name -> job_id

    def register_triggers(self, registry: dict[str, SkillMeta]) -> None:
        """Register cron triggers for all InputSkills with cron triggers."""
        for name, meta in registry.items():
            if not meta.trigger:
                continue

            trigger_type = meta.trigger.get("type")
            if trigger_type != "cron":
                logger.warning(
                    "unsupported_trigger_type",
                    skill=name,
                    trigger_type=trigger_type,
                )
                continue

            schedule = meta.trigger.get("schedule", "")
            try:
                cron_kwargs = self._parse_cron(schedule)
            except ValueError:
                logger.warning(
                    "invalid_cron_schedule",
                    skill=name,
                    schedule=schedule,
                )
                continue

            trigger = CronTrigger(**cron_kwargs)
            job = self._scheduler.add_job(
                self._on_trigger,
                trigger=trigger,
                args=[name],
                id=f"bsage-{name}",
                name=f"BSage: {name}",
            )
            self._jobs[name] = job.id
            logger.info("trigger_registered", skill=name, schedule=schedule)

    def start(self) -> None:
        """Start the AsyncIO scheduler."""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("scheduler_started")

    def stop(self) -> None:
        """Stop the AsyncIO scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("scheduler_stopped")

    @staticmethod
    def _parse_cron(schedule: str) -> dict[str, str]:
        """Parse a 5-field cron expression into APScheduler kwargs.

        Args:
            schedule: Cron expression like "*/15 * * * *".

        Returns:
            Dict with keys: minute, hour, day, month, day_of_week.

        Raises:
            ValueError: If the expression doesn't have exactly 5 fields.
        """
        parts = schedule.strip().split()
        if len(parts) != len(_CRON_FIELDS):
            raise ValueError(f"Invalid cron expression: '{schedule}'. Expected 5 fields.")
        return dict(zip(_CRON_FIELDS, parts, strict=True))

    async def _on_trigger(self, skill_name: str) -> None:
        """Handle a cron trigger firing for an InputSkill.

        Runs the InputSkill and feeds results into AgentLoop via on_input.
        """
        logger.info("trigger_fired", skill=skill_name)
        try:
            await self._run_triggered_skill(skill_name)
        except Exception:
            logger.exception("trigger_execution_failed", skill=skill_name)

    async def _run_triggered_skill(self, skill_name: str) -> None:
        """Execute a triggered InputSkill and feed results to AgentLoop."""
        context = self._agent_loop._build_context()
        result = await self._skill_runner.run(self._agent_loop._registry[skill_name], context)
        await self._agent_loop.on_input(skill_name, result)
