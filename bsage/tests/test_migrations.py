"""Tests for ``bsage.garden.migrations`` (Step B3d).

The migration script flattens a legacy entity-type vault layout (``ideas/``,
``insights/``, ``garden/idea/`` ...) into the maturity-based layout
(``garden/seedling/`` etc.) and turns the legacy ``type:`` field into a
tag. Round-trip safety is enforced by stamping every migrated note with
``_pre_migration_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bsage.garden.migrations import (
    apply_flatten,
    plan_flatten,
    revert_flatten,
)


def _write_legacy_note(
    vault_root: Path,
    rel: str,
    *,
    note_type: str = "idea",
    body: str = "Hello",
    tags: list[str] | None = None,
    maturity: str | None = None,
) -> Path:
    path = vault_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = {
        "type": note_type,
        "status": "seed",
        "source": "test",
    }
    if tags:
        fm["tags"] = tags
    if maturity:
        fm["maturity"] = maturity
    path.write_text(
        f"---\n{yaml.dump(fm).strip()}\n---\n# Note\n{body}\n",
        encoding="utf-8",
    )
    return path


def _read_fm(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    closing = raw.find("\n---\n", 4)
    return yaml.safe_load(raw[4:closing])


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    (tmp_path / ".bsage").mkdir()
    return tmp_path


class TestPlanFlatten:
    def test_finds_top_level_legacy_folders(self, vault: Path) -> None:
        _write_legacy_note(vault, "ideas/a.md", note_type="idea")
        _write_legacy_note(vault, "insights/b.md", note_type="insight")
        _write_legacy_note(vault, "projects/c.md", note_type="project")

        plan = plan_flatten(vault)
        sources = sorted(str(m.src.relative_to(vault)) for m in plan.moves)
        assert sources == ["ideas/a.md", "insights/b.md", "projects/c.md"]
        # All headed for garden/seedling by default.
        assert all(str(m.dst).startswith(str(vault / "garden" / "seedling")) for m in plan.moves)

    def test_finds_garden_legacy_subfolders(self, vault: Path) -> None:
        _write_legacy_note(vault, "garden/idea/x.md", note_type="idea")
        _write_legacy_note(vault, "garden/insight/y.md", note_type="insight")

        plan = plan_flatten(vault)
        rels = {str(m.src.relative_to(vault)) for m in plan.moves}
        assert rels == {"garden/idea/x.md", "garden/insight/y.md"}

    def test_existing_maturity_preserved(self, vault: Path) -> None:
        # Note already self-declares maturity: budding → land in budding/.
        _write_legacy_note(vault, "ideas/mature.md", note_type="idea", maturity="budding")
        plan = plan_flatten(vault)
        assert len(plan.moves) == 1
        assert plan.moves[0].dst.parent == vault / "garden" / "budding"

    def test_unknown_maturity_falls_back_to_seedling(self, vault: Path) -> None:
        _write_legacy_note(vault, "ideas/typo.md", note_type="idea", maturity="banana")
        plan = plan_flatten(vault)
        assert plan.moves[0].dst.parent == vault / "garden" / "seedling"

    def test_skips_files_without_frontmatter(self, vault: Path) -> None:
        bad = vault / "ideas" / "broken.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("just a body, no frontmatter\n", encoding="utf-8")
        plan = plan_flatten(vault)
        assert plan.moves == []
        assert bad in plan.skipped

    def test_dry_run_does_not_touch_files(self, vault: Path) -> None:
        path = _write_legacy_note(vault, "ideas/a.md", note_type="idea")
        before = path.read_text()
        plan_flatten(vault)
        assert path.exists()
        assert path.read_text() == before


class TestApplyFlatten:
    def test_moves_files_and_demotes_type_to_tag(self, vault: Path) -> None:
        legacy = _write_legacy_note(
            vault, "insights/learning.md", note_type="insight", tags=["python"]
        )
        plan = apply_flatten(vault, backup=False)

        assert len(plan.moves) == 1
        assert not legacy.exists()
        new_path = vault / "garden" / "seedling" / "learning.md"
        assert new_path.exists()

        fm = _read_fm(new_path)
        assert "type" not in fm
        assert "insight" in fm["tags"]
        assert "python" in fm["tags"]
        assert fm["maturity"] == "seedling"
        assert fm["_pre_migration_path"] == "insights/learning.md"

    def test_collisions_get_dedup_suffix(self, vault: Path) -> None:
        # Two legacy notes with the same filename.
        _write_legacy_note(vault, "ideas/dup.md", note_type="idea", body="A")
        _write_legacy_note(vault, "insights/dup.md", note_type="insight", body="B")
        plan = apply_flatten(vault, backup=False)
        assert len(plan.moves) == 2
        seedling = vault / "garden" / "seedling"
        files = sorted(p.name for p in seedling.glob("*.md"))
        assert "dup.md" in files
        assert any(name.startswith("dup_") for name in files)

    def test_idempotent_against_already_migrated_vault(self, vault: Path) -> None:
        _write_legacy_note(vault, "ideas/a.md", note_type="idea")
        apply_flatten(vault, backup=False)
        # Second run finds nothing — legacy folder is already empty.
        plan2 = plan_flatten(vault)
        assert plan2.moves == []

    def test_creates_backup_directory(self, vault: Path) -> None:
        _write_legacy_note(vault, "ideas/a.md", note_type="idea")
        apply_flatten(vault, backup=True)
        backups = list((vault / ".bsage").glob("migration-backup-flatten-*"))
        assert backups, "expected a backup directory under .bsage/"
        # Original layout reachable inside the backup.
        assert (backups[0] / "ideas" / "a.md").exists()


class TestRevertFlatten:
    def test_round_trip_preserves_layout(self, vault: Path) -> None:
        original = _write_legacy_note(vault, "insights/x.md", note_type="insight")

        apply_flatten(vault, backup=False)
        revert_flatten(vault)

        # Original file is back at the original path.
        assert original.exists()
        # Type field restored, _pre_migration_path stripped.
        fm = _read_fm(original)
        assert fm.get("type") == "insight"
        assert "_pre_migration_path" not in fm
        # Body line preserved.
        assert "Hello" in original.read_text()
        # Migrated file gone.
        assert not (vault / "garden" / "seedling" / "x.md").exists()

    def test_revert_skips_non_migrated_notes(self, vault: Path) -> None:
        # A new-shape note that was never migrated (no _pre_migration_path).
        path = vault / "garden" / "seedling" / "fresh.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\nmaturity: seedling\nstatus: seed\n---\nbody\n", encoding="utf-8")
        plan = revert_flatten(vault)
        assert plan.moves == []
        assert path.exists()
