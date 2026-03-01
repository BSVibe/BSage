"""Tests for the unfinished-detector skill — metadata loading via SkillLoader."""

from pathlib import Path

from bsage.core.skill_loader import OutputTarget, SkillLoader


async def test_load_unfinished_detector() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    assert "unfinished-detector" in registry

    meta = registry["unfinished-detector"]
    assert meta.name == "unfinished-detector"
    assert meta.version == "1.0.0"
    assert meta.category == "process"
    assert meta.trigger == {"type": "cron", "schedule": "0 10 * * MON"}
    assert "garden/project" in meta.read_context
    assert "garden/idea" in meta.read_context
    assert "actions" in meta.read_context
    assert meta.output_target is OutputTarget.GARDEN
    assert meta.output_note_type == "insight"
    assert meta.output_format == "json"
    assert meta.system_prompt  # has LLM prompt


async def test_unfinished_detector_description_not_empty() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    meta = registry["unfinished-detector"]
    assert meta.description
    assert len(meta.description) > 10


async def test_unfinished_detector_system_prompt_mentions_stalled() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    meta = registry["unfinished-detector"]
    assert "stalled" in meta.system_prompt.lower()
