"""Tests for bsage.core.agent_loop — AgentLoop orchestration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bsage.core.agent_loop import AgentLoop
from bsage.core.skill_loader import SkillMeta


def _make_meta(**overrides) -> SkillMeta:
    defaults = {
        "name": "test-skill",
        "version": "1.0.0",
        "category": "process",
        "is_dangerous": False,
        "description": "Test skill",
    }
    defaults.update(overrides)
    return SkillMeta(**defaults)


@pytest.fixture()
def mock_deps():
    """Create all mocked dependencies for AgentLoop."""
    registry = {
        "calendar-input": _make_meta(
            name="calendar-input",
            category="input",
            rules=["garden-writer"],
        ),
        "garden-writer": _make_meta(
            name="garden-writer",
            category="process",
        ),
        "dangerous-skill": _make_meta(
            name="dangerous-skill",
            category="process",
            is_dangerous=True,
        ),
    }
    skill_runner = MagicMock()
    skill_runner.run = AsyncMock(return_value={"status": "ok"})
    safe_mode_guard = MagicMock()
    safe_mode_guard.check = AsyncMock(return_value=True)
    garden_writer = MagicMock()
    garden_writer.write_seed = AsyncMock()
    garden_writer.write_action = AsyncMock()
    llm_client = MagicMock()
    llm_client.chat = AsyncMock(return_value="garden-writer")
    credential_store = MagicMock()

    return {
        "registry": registry,
        "skill_runner": skill_runner,
        "safe_mode_guard": safe_mode_guard,
        "garden_writer": garden_writer,
        "llm_client": llm_client,
        "credential_store": credential_store,
    }


def _make_loop(deps: dict) -> AgentLoop:
    return AgentLoop(
        registry=deps["registry"],
        skill_runner=deps["skill_runner"],
        safe_mode_guard=deps["safe_mode_guard"],
        garden_writer=deps["garden_writer"],
        llm_client=deps["llm_client"],
        credential_store=deps["credential_store"],
    )


class TestAgentLoopOnInput:
    """Test on_input orchestration."""

    async def test_writes_seed_on_input(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        await loop.on_input("calendar-input", {"events": [1, 2]})
        mock_deps["garden_writer"].write_seed.assert_called_once_with(
            "calendar-input", {"events": [1, 2]}
        )

    async def test_rule_based_chain_runs_process_skill(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        results = await loop.on_input("calendar-input", {"events": [1]})
        assert len(results) == 1
        assert results[0]["status"] == "ok"
        # SkillRunner should have been called with garden-writer meta
        call_args = mock_deps["skill_runner"].run.call_args
        assert call_args.args[0].name == "garden-writer"

    async def test_writes_action_after_skill_run(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        await loop.on_input("calendar-input", {"events": [1]})
        mock_deps["garden_writer"].write_action.assert_called_once()
        call_args = mock_deps["garden_writer"].write_action.call_args
        assert call_args.args[0] == "garden-writer"

    async def test_safe_mode_blocks_dangerous_skill(self, mock_deps) -> None:
        mock_deps["safe_mode_guard"].check = AsyncMock(return_value=False)
        # Set calendar-input rules to chain into dangerous-skill
        mock_deps["registry"]["calendar-input"] = _make_meta(
            name="calendar-input",
            category="input",
            rules=["dangerous-skill"],
        )
        loop = _make_loop(mock_deps)
        results = await loop.on_input("calendar-input", {"events": []})
        # dangerous skill should be blocked, no results
        assert len(results) == 0
        mock_deps["skill_runner"].run.assert_not_called()

    async def test_unknown_skill_in_chain_is_skipped(self, mock_deps) -> None:
        mock_deps["registry"]["calendar-input"] = _make_meta(
            name="calendar-input",
            category="input",
            rules=["nonexistent-skill"],
        )
        loop = _make_loop(mock_deps)
        results = await loop.on_input("calendar-input", {"events": []})
        assert len(results) == 0


class TestAgentLoopLLMFallback:
    """Test LLM-based decision when no rules defined."""

    async def test_llm_fallback_when_no_rules(self, mock_deps) -> None:
        mock_deps["registry"]["no-rules-input"] = _make_meta(
            name="no-rules-input",
            category="input",
            rules=[],
        )
        mock_deps["llm_client"].chat = AsyncMock(return_value="garden-writer")
        loop = _make_loop(mock_deps)
        results = await loop.on_input("no-rules-input", {"data": "test"})
        assert len(results) == 1
        mock_deps["llm_client"].chat.assert_called_once()

    async def test_llm_fallback_unknown_skill_ignored(self, mock_deps) -> None:
        mock_deps["registry"]["no-rules-input"] = _make_meta(
            name="no-rules-input",
            category="input",
            rules=[],
        )
        mock_deps["llm_client"].chat = AsyncMock(return_value="nonexistent-skill")
        loop = _make_loop(mock_deps)
        results = await loop.on_input("no-rules-input", {"data": "test"})
        assert len(results) == 0


class TestAgentLoopBuildContext:
    """Test _build_context creates proper SkillContext."""

    async def test_build_context_has_required_fields(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        context = loop._build_context(input_data={"key": "value"})
        assert context.input_data == {"key": "value"}
        assert context.llm is mock_deps["llm_client"]
        assert context.garden is mock_deps["garden_writer"]

    async def test_build_context_none_input_data(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        context = loop._build_context(input_data=None)
        assert context.input_data is None
