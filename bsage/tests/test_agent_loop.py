"""Tests for bsage.core.agent_loop — AgentLoop orchestration via trigger matching."""

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
            trigger={"type": "cron", "schedule": "*/15 * * * *"},
        ),
        "garden-writer": _make_meta(
            name="garden-writer",
            category="process",
            trigger={"type": "on_input"},
            input_schema={"type": "object", "properties": {"items": {"type": "array"}}},
        ),
        "insight-linker": _make_meta(
            name="insight-linker",
            category="process",
            trigger={"type": "on_input", "sources": ["calendar-input"]},
        ),
        "dangerous-skill": _make_meta(
            name="dangerous-skill",
            category="process",
            is_dangerous=True,
            trigger={"type": "on_input"},
        ),
        "skill-builder": _make_meta(
            name="skill-builder",
            category="process",
            trigger={"type": "on_demand", "hint": "When a new skill is needed"},
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
    llm_client.chat = AsyncMock(return_value="none")
    return {
        "registry": registry,
        "skill_runner": skill_runner,
        "safe_mode_guard": safe_mode_guard,
        "garden_writer": garden_writer,
        "llm_client": llm_client,
    }


def _make_loop(deps: dict) -> AgentLoop:
    return AgentLoop(
        registry=deps["registry"],
        skill_runner=deps["skill_runner"],
        safe_mode_guard=deps["safe_mode_guard"],
        garden_writer=deps["garden_writer"],
        llm_client=deps["llm_client"],
    )


class TestAgentLoopOnInput:
    """Test on_input orchestration."""

    async def test_writes_seed_on_input(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        await loop.on_input("calendar-input", {"events": [1, 2]})
        mock_deps["garden_writer"].write_seed.assert_called_once_with(
            "calendar-input", {"events": [1, 2]}
        )

    async def test_on_input_triggers_matching_process_skills(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        await loop.on_input("calendar-input", {"events": [1]})
        # garden-writer (on_input) + insight-linker (sources: [calendar-input])
        # + dangerous-skill (on_input) = 3 deterministic triggers
        run_calls = mock_deps["skill_runner"].run.call_args_list
        run_names = [call.args[0].name for call in run_calls]
        assert "garden-writer" in run_names
        assert "insight-linker" in run_names
        assert "dangerous-skill" in run_names

    async def test_on_input_respects_sources_filter(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        mock_deps["registry"]["unknown-input"] = _make_meta(name="unknown-input", category="input")
        await loop.on_input("unknown-input", {"data": "test"})
        run_calls = mock_deps["skill_runner"].run.call_args_list
        run_names = [call.args[0].name for call in run_calls]
        assert "garden-writer" in run_names
        assert "insight-linker" not in run_names

    async def test_writes_action_after_skill_run(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        await loop.on_input("calendar-input", {"events": [1]})
        assert mock_deps["garden_writer"].write_action.call_count > 0

    async def test_safe_mode_blocks_dangerous_skill(self, mock_deps) -> None:
        mock_deps["safe_mode_guard"].check = AsyncMock(side_effect=lambda m: not m.is_dangerous)
        loop = _make_loop(mock_deps)
        await loop.on_input("calendar-input", {"events": []})
        run_calls = mock_deps["skill_runner"].run.call_args_list
        run_names = [call.args[0].name for call in run_calls]
        assert "dangerous-skill" not in run_names


class TestAgentLoopFindTriggered:
    """Test _find_triggered_skills logic."""

    async def test_finds_on_input_skills(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        triggered = loop._find_triggered_skills("calendar-input")
        names = [m.name for m in triggered]
        assert "garden-writer" in names
        assert "insight-linker" in names

    async def test_excludes_non_process_skills(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        triggered = loop._find_triggered_skills("calendar-input")
        names = [m.name for m in triggered]
        assert "calendar-input" not in names

    async def test_excludes_cron_and_on_demand_skills(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        triggered = loop._find_triggered_skills("calendar-input")
        names = [m.name for m in triggered]
        assert "skill-builder" not in names

    async def test_sources_filter_excludes_unmatched(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        triggered = loop._find_triggered_skills("unknown-source")
        names = [m.name for m in triggered]
        assert "insight-linker" not in names
        assert "garden-writer" in names


class TestAgentLoopOnDemand:
    """Test LLM-based on_demand skill routing."""

    async def test_text_routing_selects_and_runs_skill(self, mock_deps) -> None:
        """On-demand skill without input_schema uses text-based routing."""
        mock_deps["llm_client"].chat = AsyncMock(return_value="skill-builder")
        loop = _make_loop(mock_deps)
        results = await loop._decide_on_demand_skills("calendar-input", {"data": "test"})
        assert len(results) == 1
        assert results[0]["status"] == "ok"
        # skill-builder should have been run via SkillRunner
        run_calls = mock_deps["skill_runner"].run.call_args_list
        run_names = [call.args[0].name for call in run_calls]
        assert "skill-builder" in run_names

    async def test_text_routing_none_returns_empty(self, mock_deps) -> None:
        mock_deps["llm_client"].chat = AsyncMock(return_value="none")
        loop = _make_loop(mock_deps)
        results = await loop._decide_on_demand_skills("calendar-input", {"data": "test"})
        assert len(results) == 0

    async def test_text_routing_ignores_unknown_names(self, mock_deps) -> None:
        mock_deps["llm_client"].chat = AsyncMock(return_value="nonexistent-skill")
        loop = _make_loop(mock_deps)
        results = await loop._decide_on_demand_skills("calendar-input", {"data": "test"})
        assert len(results) == 0

    async def test_no_on_demand_skills_skips_llm(self, mock_deps) -> None:
        del mock_deps["registry"]["skill-builder"]
        loop = _make_loop(mock_deps)
        results = await loop._decide_on_demand_skills("calendar-input", {"data": "test"})
        assert len(results) == 0
        mock_deps["llm_client"].chat.assert_not_called()

    async def test_triggerless_process_treated_as_on_demand(self, mock_deps) -> None:
        mock_deps["registry"]["auto-tagger"] = _make_meta(
            name="auto-tagger",
            category="process",
            trigger=None,
        )
        mock_deps["llm_client"].chat = AsyncMock(return_value="auto-tagger")
        loop = _make_loop(mock_deps)
        results = await loop._decide_on_demand_skills("calendar-input", {"data": "test"})
        assert len(results) >= 1

    async def test_tool_use_path_when_input_schema_exists(self, mock_deps) -> None:
        """On-demand skill with input_schema uses tool use routing."""
        mock_deps["registry"]["schema-skill"] = _make_meta(
            name="schema-skill",
            category="process",
            trigger={"type": "on_demand"},
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        )
        mock_deps["llm_client"].chat = AsyncMock(return_value="Done")
        loop = _make_loop(mock_deps)
        await loop._decide_on_demand_skills("test-input", {"data": "test"})
        call_kwargs = mock_deps["llm_client"].chat.call_args.kwargs
        assert call_kwargs["tools"] is not None


class TestAgentLoopChat:
    """Test interactive chat with tool use."""

    async def test_chat_uses_tools_when_available(self, mock_deps) -> None:
        mock_deps["llm_client"].chat = AsyncMock(return_value="Chat response")
        loop = _make_loop(mock_deps)
        result = await loop.chat(
            system="You are BSage",
            messages=[{"role": "user", "content": "Save a note"}],
        )
        assert result == "Chat response"
        call_kwargs = mock_deps["llm_client"].chat.call_args.kwargs
        assert call_kwargs["tools"] is not None

    async def test_chat_falls_back_to_plain_when_no_tools(self, mock_deps) -> None:
        # Remove all input_schema from registry
        for meta in mock_deps["registry"].values():
            meta.input_schema = None
        mock_deps["llm_client"].chat = AsyncMock(return_value="Plain response")
        loop = _make_loop(mock_deps)
        result = await loop.chat(
            system="You are BSage",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert result == "Plain response"
        call_kwargs = mock_deps["llm_client"].chat.call_args.kwargs
        assert call_kwargs["tools"] is None
        assert call_kwargs["tool_handler"] is None

    async def test_chat_passes_system_and_messages(self, mock_deps) -> None:
        mock_deps["llm_client"].chat = AsyncMock(return_value="ok")
        loop = _make_loop(mock_deps)
        msgs = [{"role": "user", "content": "hi"}]
        await loop.chat(system="sys prompt", messages=msgs)
        call_kwargs = mock_deps["llm_client"].chat.call_args.kwargs
        assert call_kwargs["system"] == "sys prompt"
        assert call_kwargs["messages"] == msgs


class TestBuildSkillTools:
    """Test _build_skill_tools tool definition generation."""

    async def test_includes_skills_with_input_schema(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        tools = loop._build_skill_tools()
        tool_names = [t["function"]["name"] for t in tools]
        assert "garden-writer" in tool_names

    async def test_excludes_skills_without_input_schema(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        tools = loop._build_skill_tools()
        tool_names = [t["function"]["name"] for t in tools]
        assert "insight-linker" not in tool_names
        assert "skill-builder" not in tool_names

    async def test_excludes_non_process_skills(self, mock_deps) -> None:
        mock_deps["registry"]["input-with-schema"] = _make_meta(
            name="input-with-schema",
            category="input",
            input_schema={"type": "object"},
        )
        loop = _make_loop(mock_deps)
        tools = loop._build_skill_tools()
        tool_names = [t["function"]["name"] for t in tools]
        assert "input-with-schema" not in tool_names

    async def test_tool_format_is_openai_compatible(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        tools = loop._build_skill_tools()
        for tool in tools:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]


class TestHandleToolCall:
    """Test _handle_tool_call skill execution."""

    async def test_runs_skill_via_runner(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        result = await loop._handle_tool_call("tc1", "garden-writer", {"items": []})
        mock_deps["skill_runner"].run.assert_called_once()
        assert "ok" in result

    async def test_unknown_skill_returns_error(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        result = await loop._handle_tool_call("tc1", "nonexistent", {})
        assert "error" in result
        assert "Unknown skill" in result

    async def test_safe_mode_rejection(self, mock_deps) -> None:
        mock_deps["safe_mode_guard"].check = AsyncMock(return_value=False)
        loop = _make_loop(mock_deps)
        result = await loop._handle_tool_call("tc1", "garden-writer", {})
        assert "rejected" in result
        mock_deps["skill_runner"].run.assert_not_called()

    async def test_writes_action_on_success(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        await loop._handle_tool_call("tc1", "garden-writer", {"items": []})
        mock_deps["garden_writer"].write_action.assert_called_once()

    async def test_passes_args_as_input_data(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        await loop._handle_tool_call("tc1", "garden-writer", {"items": [{"title": "Test"}]})
        context = mock_deps["skill_runner"].run.call_args.args[1]
        assert context.input_data == {"items": [{"title": "Test"}]}


class TestAgentLoopBuildContext:
    """Test build_context creates proper SkillContext."""

    async def test_build_context_has_required_fields(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        context = loop.build_context(input_data={"key": "value"})
        assert context.input_data == {"key": "value"}
        assert context.llm is mock_deps["llm_client"]
        assert context.garden is mock_deps["garden_writer"]

    async def test_build_context_none_input_data(self, mock_deps) -> None:
        loop = _make_loop(mock_deps)
        context = loop.build_context(input_data=None)
        assert context.input_data is None
