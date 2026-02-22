"""AgentLoop — orchestrates Skill execution chains."""

from __future__ import annotations

import json
from typing import Any

import structlog

from bsage.connectors.manager import ConnectorManager
from bsage.core.safe_mode import SafeModeGuard
from bsage.core.skill_context import ConnectorAccessor, LLMClient, SkillContext
from bsage.core.skill_loader import SkillMeta
from bsage.core.skill_runner import SkillRunner
from bsage.garden.writer import GardenWriter

logger = structlog.get_logger(__name__)


class AgentLoop:
    """Orchestrates the full Skill execution pipeline.

    Flow:
    1. Write raw input to seeds
    2. Determine next skills (rules or LLM fallback)
    3. SafeMode check → SkillRunner.run → write action
    """

    def __init__(
        self,
        registry: dict[str, SkillMeta],
        skill_runner: SkillRunner,
        safe_mode_guard: SafeModeGuard,
        garden_writer: GardenWriter,
        llm_client: LLMClient,
        connector_manager: ConnectorManager,
    ) -> None:
        self._registry = registry
        self._skill_runner = skill_runner
        self._safe_mode_guard = safe_mode_guard
        self._garden_writer = garden_writer
        self._llm_client = llm_client
        self._connector_manager = connector_manager

    async def on_input(self, skill_name: str, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Process input from an InputSkill and run the chain.

        Args:
            skill_name: Name of the InputSkill that produced the data.
            raw_data: Raw data collected by the InputSkill.

        Returns:
            List of result dicts from each executed ProcessSkill.
        """
        logger.info("agent_loop_input", skill_name=skill_name)

        # 1. Write raw data to seeds
        await self._garden_writer.write_seed(skill_name, raw_data)

        # 2. Determine next skills to run
        input_meta = self._registry.get(skill_name)
        if input_meta and input_meta.rules:
            next_skills = input_meta.rules
        else:
            next_skills = await self._decide_with_llm(skill_name, raw_data)

        # 3. Execute each skill in the chain
        results: list[dict] = []
        for next_name in next_skills:
            try:
                meta = self._registry[next_name]
            except KeyError:
                logger.warning("skill_not_in_registry", name=next_name)
                continue

            # SafeMode check
            approved = await self._safe_mode_guard.check(meta)
            if not approved:
                logger.warning("skill_rejected_by_safe_mode", name=next_name)
                continue

            # Run the skill
            context = self._build_context(input_data=raw_data)
            result = await self._skill_runner.run(meta, context)
            results.append(result)

            # Log action
            await self._garden_writer.write_action(
                next_name, f"Executed with result keys: {list(result.keys())}"
            )

        logger.info(
            "agent_loop_complete",
            skill_name=skill_name,
            skills_run=len(results),
        )
        return results

    async def _decide_with_llm(self, skill_name: str, raw_data: dict[str, Any]) -> list[str]:
        """Use LLM to decide which ProcessSkills to run."""
        available = [name for name, meta in self._registry.items() if meta.category == "process"]

        if not available:
            return []

        system = (
            "You are BSage's skill router. Given input from a skill, "
            "decide which ProcessSkill(s) to run next.\n"
            f"Available ProcessSkills: {', '.join(available)}\n"
            "Respond with ONLY the skill name(s), one per line. "
            "If none are appropriate, respond with 'none'."
        )
        messages = [
            {
                "role": "user",
                "content": (
                    f"Input from '{skill_name}':\n"
                    f"```json\n{json.dumps(raw_data, default=str)}\n```\n\n"
                    "Which ProcessSkill(s) should handle this?"
                ),
            }
        ]

        response = await self._llm_client.chat(system=system, messages=messages)

        # Parse response: each line is a skill name
        selected = []
        for line in response.strip().splitlines():
            name = line.strip().lower()
            if name and name != "none" and name in self._registry:
                selected.append(name)

        logger.info("llm_decision", selected=selected)
        return selected

    def _build_context(self, input_data: dict[str, Any] | None = None) -> SkillContext:
        """Create a SkillContext with all dependencies injected."""
        return SkillContext(
            connector=ConnectorAccessor(self._connector_manager),
            garden=self._garden_writer,
            llm=self._llm_client,
            config={},
            logger=structlog.get_logger("skill"),
            input_data=input_data,
        )
