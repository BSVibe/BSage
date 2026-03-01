"""Tests for the skill-builder skill (Markdown-based)."""

from pathlib import Path

from bsage.core.skill_loader import SkillLoader


async def test_load_skill_builder() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    assert "skill-builder" in registry

    meta = registry["skill-builder"]
    assert meta.category == "process"
    assert meta.version == "1.0.0"
    assert meta.trigger == {
        "type": "on_demand",
        "hint": "When a new capability is needed that doesn't exist yet",
    }
    assert meta.output_format == "json"
    assert meta.system_prompt is not None
    assert len(meta.system_prompt) > 0


async def test_skill_builder_description_not_empty() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    meta = registry["skill-builder"]
    assert meta.description
    assert len(meta.description) > 10


async def test_skill_builder_system_prompt_covers_both_types() -> None:
    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    meta = registry["skill-builder"]
    prompt = meta.system_prompt.lower()
    assert "skill" in prompt
    assert "plugin" in prompt
    assert "@plugin" in meta.system_prompt
    assert "frontmatter" in prompt


async def test_skill_builder_output_target_is_seeds() -> None:
    """Generated code should go to seeds for user review, not garden."""
    from bsage.core.skill_loader import OutputTarget

    loader = SkillLoader(Path("skills"))
    registry = await loader.load_all()
    meta = registry["skill-builder"]
    assert meta.output_target == OutputTarget.SEEDS
