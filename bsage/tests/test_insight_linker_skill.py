"""Tests for the insight-linker skill — metadata loading via SkillLoader."""

from pathlib import Path

from bsage.core.skill_loader import OutputTarget, SkillLoader


async def test_load_insight_linker() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    assert "insight-linker" in registry

    meta = registry["insight-linker"]
    assert meta.name == "insight-linker"
    assert meta.version == "1.0.0"
    assert meta.category == "process"
    assert meta.trigger == {"type": "cron", "schedule": "0 21 * * *"}
    assert "garden/idea" in meta.read_context
    assert "garden/insight" in meta.read_context
    assert "garden/project" in meta.read_context
    assert meta.output_target is OutputTarget.GARDEN
    assert meta.output_note_type == "insight"
    assert meta.output_format == "json"
    assert meta.system_prompt  # has LLM prompt


async def test_insight_linker_description_not_empty() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    meta = registry["insight-linker"]
    assert meta.description
    assert len(meta.description) > 10


async def test_insight_linker_system_prompt_mentions_connections() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    meta = registry["insight-linker"]
    assert "connection" in meta.system_prompt.lower()
