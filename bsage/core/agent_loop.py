"""AgentLoop — orchestrates Skill execution via trigger matching and tool use."""

from __future__ import annotations

import json
from typing import Any

import structlog

from bsage.core.notification import NotificationInterface
from bsage.core.prompt_registry import PromptRegistry
from bsage.core.safe_mode import SafeModeGuard
from bsage.core.skill_context import LLMClient, SkillContext
from bsage.core.skill_loader import SkillMeta
from bsage.core.skill_runner import SkillRunner
from bsage.garden.writer import GardenWriter

logger = structlog.get_logger(__name__)


class AgentLoop:
    """Orchestrates Skill execution via trigger matching and tool use.

    Skills with ``input_schema`` are exposed as LLM tools so the model
    can invoke them directly — both during interactive chat and when
    routing on-demand skills for automated input processing.
    """

    def __init__(
        self,
        registry: dict[str, SkillMeta],
        skill_runner: SkillRunner,
        safe_mode_guard: SafeModeGuard,
        garden_writer: GardenWriter,
        llm_client: LLMClient,
        notification: NotificationInterface | None = None,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self._registry = registry
        self._skill_runner = skill_runner
        self._safe_mode_guard = safe_mode_guard
        self._garden_writer = garden_writer
        self._llm_client = llm_client
        self._notification = notification
        self._prompt_registry = prompt_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(self, system: str, messages: list[dict]) -> str:
        """Interactive chat with tool-use skill execution.

        The LLM sees available skills as tools and can call them during
        the conversation.  Falls back to plain chat when no tools exist.
        """
        tools = self._build_skill_tools() or None
        return await self._llm_client.chat(
            system=system,
            messages=messages,
            tools=tools,
            tool_handler=self._handle_tool_call if tools else None,
        )

    async def on_input(self, skill_name: str, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Process input from an InputSkill and run triggered skills.

        1. Write raw data to seeds.
        2. Run deterministic on_input-triggered skills.
        3. Let LLM decide and execute on-demand skills via tool use.
        """
        logger.info("agent_loop_input", skill_name=skill_name)

        # 1. Write raw data to seeds
        await self._garden_writer.write_seed(skill_name, raw_data)

        # 2. Run deterministic on_input-triggered skills
        triggered = self._find_triggered_skills(skill_name)
        results: list[dict] = []
        for meta in triggered:
            approved = await self._safe_mode_guard.check(meta)
            if not approved:
                logger.warning("skill_rejected_by_safe_mode", name=meta.name)
                continue
            context = self.build_context(input_data=raw_data)
            result = await self._skill_runner.run(meta, context)
            results.append(result)
            summary = json.dumps(result, default=str)
            await self._garden_writer.write_action(meta.name, summary)

        # 3. Let LLM decide and execute on-demand skills via tool use
        on_demand_results = await self._decide_on_demand_skills(skill_name, raw_data)
        results.extend(on_demand_results)

        logger.info(
            "agent_loop_complete",
            skill_name=skill_name,
            skills_run=len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Trigger matching
    # ------------------------------------------------------------------

    def _find_triggered_skills(self, source_name: str) -> list[SkillMeta]:
        """Find process skills with trigger.type == on_input matching source."""
        result = []
        for meta in self._registry.values():
            if meta.category != "process" or not meta.trigger:
                continue
            if meta.trigger.get("type") != "on_input":
                continue
            sources = meta.trigger.get("sources")
            if sources is None or source_name in sources:
                result.append(meta)
        return result

    # ------------------------------------------------------------------
    # Tool use infrastructure (shared by chat and on_input)
    # ------------------------------------------------------------------

    def _build_skill_tools(self) -> list[dict]:
        """Build OpenAI-format tool definitions from skills with input_schema."""
        tools = []
        for meta in self._registry.values():
            if meta.category == "process" and meta.input_schema:
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": meta.name,
                            "description": meta.description,
                            "parameters": meta.input_schema,
                        },
                    }
                )
        return tools

    async def _handle_tool_call(self, tool_call_id: str, name: str, args: dict[str, Any]) -> str:
        """Execute a skill triggered by an LLM tool call.

        SafeMode → SkillRunner.run() → action log → result JSON.
        """
        meta = self._registry.get(name)
        if meta is None:
            return json.dumps({"error": f"Unknown skill: {name}"})

        approved = await self._safe_mode_guard.check(meta)
        if not approved:
            logger.warning("skill_rejected_by_safe_mode", name=name)
            return json.dumps({"error": f"Skill '{name}' rejected by safe mode"})

        try:
            context = self.build_context(input_data=args)
            result = await self._skill_runner.run(meta, context)
            summary = json.dumps(result, default=str)[:200]
            await self._garden_writer.write_action(name, summary)
            return json.dumps(result, default=str)
        except Exception as exc:
            logger.exception("tool_call_failed", skill=name)
            return json.dumps({"error": str(exc)})

    # ------------------------------------------------------------------
    # On-demand skill routing via tool use
    # ------------------------------------------------------------------

    async def _decide_on_demand_skills(
        self, source_name: str, raw_data: dict[str, Any]
    ) -> list[dict]:
        """Let LLM decide and execute on-demand skills via tool use.

        If on-demand skills have input_schema, uses tool use so the LLM
        both decides AND executes in a single pass.  Falls back to the
        text-based routing for skills without input_schema.
        """
        on_demand = [
            m
            for m in self._registry.values()
            if m.category == "process" and (not m.trigger or m.trigger.get("type") == "on_demand")
        ]
        if not on_demand:
            return []

        # Build tool definitions for on-demand skills with input_schema
        tools = []
        for m in on_demand:
            if m.input_schema:
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": m.name,
                            "description": m.description,
                            "parameters": m.input_schema,
                        },
                    }
                )

        system = self._build_router_prompt(on_demand)
        messages = [
            {
                "role": "user",
                "content": (
                    f"Input from '{source_name}':\n"
                    f"```json\n{json.dumps(raw_data, default=str)}\n```\n\n"
                    "Decide which skill(s) should handle this and call them."
                ),
            }
        ]

        # Collect results from tool calls
        results: list[dict] = []

        if tools:
            # Tool use path: LLM decides and executes via tool calls
            async def _collecting_handler(
                tool_call_id: str, name: str, args: dict[str, Any]
            ) -> str:
                result_str = await self._handle_tool_call(tool_call_id, name, args)
                try:
                    results.append(json.loads(result_str))
                except json.JSONDecodeError:
                    results.append({"raw": result_str})
                return result_str

            await self._llm_client.chat(
                system=system,
                messages=messages,
                tools=tools,
                tool_handler=_collecting_handler,
            )
        else:
            # Fallback: text-based routing for skills without input_schema
            selected = await self._route_by_text(on_demand, system, messages)
            for meta in selected:
                approved = await self._safe_mode_guard.check(meta)
                if not approved:
                    continue
                context = self.build_context(input_data=raw_data)
                result = await self._skill_runner.run(meta, context)
                results.append(result)
                summary = json.dumps(result, default=str)
                await self._garden_writer.write_action(meta.name, summary)

        return results

    async def _route_by_text(
        self,
        on_demand: list[SkillMeta],
        system: str,
        messages: list[dict],
    ) -> list[SkillMeta]:
        """Fallback: text-based routing when no tools are available."""
        response = await self._llm_client.chat(system=system, messages=messages)
        on_demand_names = {m.name for m in on_demand}
        selected = []
        for line in response.strip().splitlines():
            name = line.strip().lower()
            if name and name != "none" and name in on_demand_names:
                selected.append(self._registry[name])
        logger.info("llm_on_demand_decision", selected=[m.name for m in selected])
        return selected

    def _build_router_prompt(self, on_demand: list[SkillMeta]) -> str:
        """Build system prompt for on-demand skill routing."""
        skill_descriptions = "\n".join(
            f"- {m.name}: {m.description}"
            + (f" (hint: {m.trigger['hint']})" if m.trigger and m.trigger.get("hint") else "")
            for m in on_demand
        )
        if self._prompt_registry:
            try:
                return self._prompt_registry.render("router", skill_descriptions=skill_descriptions)
            except KeyError:
                pass
        return self._build_router_prompt_fallback(skill_descriptions)

    @staticmethod
    def _build_router_prompt_fallback(skill_descriptions: str) -> str:
        """Build router system prompt when PromptRegistry is unavailable."""
        return (
            "You are BSage's skill router. Given input from a skill, "
            "decide which on-demand ProcessSkill(s) should run.\n"
            f"Available on-demand skills:\n{skill_descriptions}\n\n"
            "Respond with ONLY the skill name(s), one per line. "
            "If none are appropriate, respond with 'none'."
        )

    # ------------------------------------------------------------------
    # Framework API
    # ------------------------------------------------------------------

    def get_skill(self, name: str) -> SkillMeta:
        """Look up a skill by name from the registry.

        Raises:
            KeyError: If the skill is not registered.
        """
        return self._registry[name]

    def build_context(self, input_data: dict[str, Any] | None = None) -> SkillContext:
        """Create a SkillContext with all dependencies injected."""
        return SkillContext(
            garden=self._garden_writer,
            llm=self._llm_client,
            config={},
            logger=structlog.get_logger("skill"),
            input_data=input_data,
            notify=self._notification,
        )

    async def write_action(self, skill_name: str, summary: str) -> None:
        """Write an action log entry for a skill execution."""
        await self._garden_writer.write_action(skill_name, summary)
