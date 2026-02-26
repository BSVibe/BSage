"""Tests for bsage.core.skill_loader — MD scanning and SkillMeta registry."""

import pytest

from bsage.core.exceptions import SkillLoadError
from bsage.core.skill_loader import OutputTarget, SkillLoader, SkillMeta, _split_frontmatter


class TestSplitFrontmatter:
    """Test the frontmatter splitting helper."""

    def test_splits_frontmatter_from_body(self) -> None:
        text = "---\nname: test\n---\n\nBody content here."
        fm, body = _split_frontmatter(text)
        assert "name: test" in fm
        assert "Body content here." in body

    def test_no_frontmatter_returns_empty_string(self) -> None:
        text = "Just body text."
        fm, body = _split_frontmatter(text)
        assert fm == ""
        assert body == "Just body text."

    def test_empty_body_ok(self) -> None:
        text = "---\nname: test\n---\n"
        fm, body = _split_frontmatter(text)
        assert "name: test" in fm
        assert body == ""

    def test_no_closing_delimiter_returns_empty(self) -> None:
        text = "---\nname: test\n"
        fm, body = _split_frontmatter(text)
        assert fm == ""


class TestSkillMeta:
    """Test SkillMeta dataclass."""

    def test_required_fields(self) -> None:
        meta = SkillMeta(
            name="test",
            version="1.0.0",
            category="process",
            description="A test skill",
        )
        assert meta.name == "test"
        assert meta.version == "1.0.0"
        assert meta.category == "process"
        assert meta.description == "A test skill"

    def test_optional_fields_defaults(self) -> None:
        meta = SkillMeta(
            name="test",
            version="1.0.0",
            category="process",
            description="A test skill",
        )
        assert meta.author == ""
        assert meta.trigger is None
        assert meta.credentials is None
        assert meta.read_context == []
        assert meta.output_target is None
        assert meta.output_note_type == "idea"
        assert meta.system_prompt is None
        assert meta.output_format is None

    def test_yaml_only_fields(self) -> None:
        meta = SkillMeta(
            name="weekly-digest",
            version="1.0.0",
            category="process",
            description="Weekly digest",
            read_context=["garden/idea", "garden/insight"],
            output_target=OutputTarget.GARDEN,
            output_note_type="insight",
            system_prompt="You are a digest generator.",
            output_format="json",
        )
        assert meta.read_context == ["garden/idea", "garden/insight"]
        assert meta.output_target is OutputTarget.GARDEN
        assert meta.output_note_type == "insight"
        assert meta.system_prompt == "You are a digest generator."
        assert meta.output_format == "json"


class TestSkillLoader:
    """Test SkillLoader MD scanning and registry."""

    @pytest.fixture()
    def skills_dir(self, tmp_path):
        """Create a temporary skills directory with sample .md skill files."""
        (tmp_path / "weekly-digest.md").write_text(
            "---\n"
            "name: weekly-digest\n"
            "version: 1.0.0\n"
            "category: process\n"
            "description: Generate weekly digest\n"
            "trigger:\n"
            "  type: cron\n"
            "  schedule: '0 9 * * MON'\n"
            "---\n"
            "\n"
            "You are a weekly digest generator.\n"
        )
        (tmp_path / "insight-linker.md").write_text(
            "---\n"
            "name: insight-linker\n"
            "version: 1.0.0\n"
            "category: process\n"
            "description: Link insights across notes\n"
            "---\n"
            "\n"
            "You are an insight linker.\n"
        )
        return tmp_path

    async def test_load_all_discovers_md_skills(self, skills_dir) -> None:
        loader = SkillLoader(skills_dir)
        registry = await loader.load_all()
        assert "weekly-digest" in registry
        assert "insight-linker" in registry
        assert len(registry) == 2

    async def test_load_all_returns_skill_meta(self, skills_dir) -> None:
        loader = SkillLoader(skills_dir)
        registry = await loader.load_all()
        meta = registry["weekly-digest"]
        assert isinstance(meta, SkillMeta)
        assert meta.category == "process"

    async def test_md_body_becomes_system_prompt(self, skills_dir) -> None:
        loader = SkillLoader(skills_dir)
        registry = await loader.load_all()
        meta = registry["weekly-digest"]
        assert meta.system_prompt == "You are a weekly digest generator."

    async def test_load_all_parses_trigger(self, skills_dir) -> None:
        loader = SkillLoader(skills_dir)
        registry = await loader.load_all()
        meta = registry["weekly-digest"]
        assert meta.trigger == {"type": "cron", "schedule": "0 9 * * MON"}

    async def test_load_all_skips_non_md_files(self, tmp_path) -> None:
        (tmp_path / "not-a-skill.txt").write_text("hello")
        (tmp_path / "notes.yaml").write_text("name: something\n")
        loader = SkillLoader(tmp_path)
        registry = await loader.load_all()
        assert len(registry) == 0

    async def test_get_returns_skill(self, skills_dir) -> None:
        loader = SkillLoader(skills_dir)
        await loader.load_all()
        meta = loader.get("weekly-digest")
        assert meta.name == "weekly-digest"

    async def test_get_raises_on_unknown_skill(self, skills_dir) -> None:
        loader = SkillLoader(skills_dir)
        await loader.load_all()
        with pytest.raises(SkillLoadError, match="not found"):
            loader.get("nonexistent")

    async def test_load_all_handles_invalid_yaml_frontmatter(self, tmp_path) -> None:
        (tmp_path / "broken.md").write_text("---\nname: broken\n[invalid yaml\n---\n\nbody\n")
        loader = SkillLoader(tmp_path)
        registry = await loader.load_all()
        assert "broken" not in registry

    async def test_load_all_handles_missing_required_fields(self, tmp_path) -> None:
        (tmp_path / "incomplete.md").write_text(
            "---\nname: incomplete\nversion: 1.0.0\n---\n\nbody\n"
        )
        loader = SkillLoader(tmp_path)
        registry = await loader.load_all()
        assert "incomplete" not in registry

    async def test_load_all_rejects_invalid_skill_name(self, tmp_path) -> None:
        (tmp_path / "bad-name.md").write_text(
            "---\n"
            "name: Bad_Name!\n"
            "version: 1.0.0\n"
            "category: process\n"
            ""
            "description: Invalid name\n"
            "---\n"
        )
        loader = SkillLoader(tmp_path)
        registry = await loader.load_all()
        assert "Bad_Name!" not in registry

    async def test_load_all_rejects_invalid_category(self, tmp_path) -> None:
        (tmp_path / "meta-skill.md").write_text(
            "---\n"
            "name: meta-skill\n"
            "version: 1.0.0\n"
            "category: meta\n"
            ""
            "description: Old meta category\n"
            "---\n"
        )
        loader = SkillLoader(tmp_path)
        registry = await loader.load_all()
        assert "meta-skill" not in registry

    async def test_load_all_parses_yaml_only_fields(self, tmp_path) -> None:
        (tmp_path / "weekly-digest.md").write_text(
            "---\n"
            "name: weekly-digest\n"
            "version: 1.0.0\n"
            "category: process\n"
            ""
            "description: Weekly digest\n"
            "read_context:\n"
            "  - garden/idea\n"
            "  - garden/insight\n"
            "output_target: garden\n"
            "output_note_type: insight\n"
            "output_format: json\n"
            "---\n"
            "\n"
            "You are a digest generator.\n"
        )
        loader = SkillLoader(tmp_path)
        registry = await loader.load_all()
        meta = registry["weekly-digest"]
        assert meta.read_context == ["garden/idea", "garden/insight"]
        assert meta.output_target is OutputTarget.GARDEN
        assert meta.output_note_type == "insight"
        assert meta.output_format == "json"
        assert meta.system_prompt == "You are a digest generator."

    async def test_load_all_rejects_invalid_output_target(self, tmp_path) -> None:
        (tmp_path / "bad-target.md").write_text(
            "---\n"
            "name: bad-target\n"
            "version: 1.0.0\n"
            "category: process\n"
            ""
            "description: Invalid output target\n"
            "output_target: invalid\n"
            "---\n"
        )
        loader = SkillLoader(tmp_path)
        registry = await loader.load_all()
        assert "bad-target" not in registry

    async def test_load_all_nonexistent_dir(self, tmp_path) -> None:
        loader = SkillLoader(tmp_path / "does-not-exist")
        registry = await loader.load_all()
        assert len(registry) == 0

    async def test_load_all_handles_missing_frontmatter(self, tmp_path) -> None:
        (tmp_path / "no-frontmatter.md").write_text("# Just a markdown file\nNo frontmatter.\n")
        loader = SkillLoader(tmp_path)
        registry = await loader.load_all()
        assert len(registry) == 0
