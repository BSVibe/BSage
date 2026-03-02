"""Tests for bsage.core.runtime_config — mutable runtime settings."""

import json
from unittest.mock import MagicMock, patch

import pytest

from bsage.core.runtime_config import RuntimeConfig


def _cfg(**overrides: object) -> RuntimeConfig:
    """Create a RuntimeConfig with sensible defaults."""
    defaults: dict[str, object] = {
        "llm_model": "model-a",
        "llm_api_key": "",
        "llm_api_base": None,
        "safe_mode": True,
        "disabled_entries": [],
    }
    defaults.update(overrides)
    return RuntimeConfig(**defaults)


class TestRuntimeConfigInit:
    """Test RuntimeConfig initialization."""

    def test_init_stores_values(self) -> None:
        config = RuntimeConfig(
            llm_model="anthropic/claude-sonnet-4-20250514",
            llm_api_key="sk-test",
            llm_api_base=None,
            safe_mode=True,
        )
        assert config.llm_model == "anthropic/claude-sonnet-4-20250514"
        assert config.llm_api_key == "sk-test"
        assert config.llm_api_base is None
        assert config.safe_mode is True

    def test_init_with_api_base(self) -> None:
        config = RuntimeConfig(
            llm_model="ollama/llama3",
            llm_api_key="",
            llm_api_base="http://localhost:11434",
            safe_mode=False,
        )
        assert config.llm_api_base == "http://localhost:11434"
        assert config.safe_mode is False

    def test_unknown_attribute_raises(self) -> None:
        config = _cfg()
        with pytest.raises(AttributeError):
            _ = config.nonexistent_field


class TestRuntimeConfigUpdate:
    """Test RuntimeConfig.update() method."""

    def test_update_model(self) -> None:
        config = _cfg()
        config.update(llm_model="model-b")
        assert config.llm_model == "model-b"

    def test_update_api_key(self) -> None:
        config = _cfg(llm_api_key="old-key")
        config.update(llm_api_key="new-key")
        assert config.llm_api_key == "new-key"
        assert config.llm_model == "model-a"  # unchanged

    def test_update_api_base(self) -> None:
        config = _cfg()
        config.update(llm_api_base="http://localhost:11434")
        assert config.llm_api_base == "http://localhost:11434"

    def test_update_api_base_to_none(self) -> None:
        config = _cfg(llm_api_base="http://old")
        config.update(llm_api_base=None)
        assert config.llm_api_base is None

    def test_update_empty_model_raises(self) -> None:
        config = _cfg()
        with pytest.raises(ValueError, match="cannot be empty"):
            config.update(llm_model="")

    def test_update_whitespace_model_raises(self) -> None:
        config = _cfg()
        with pytest.raises(ValueError, match="cannot be empty"):
            config.update(llm_model="   ")

    def test_update_safe_mode_toggle(self) -> None:
        config = _cfg(safe_mode=True)
        assert config.safe_mode is True
        config.update(safe_mode=False)
        assert config.safe_mode is False
        config.update(safe_mode=True)
        assert config.safe_mode is True

    def test_update_multiple_fields_atomically(self) -> None:
        config = _cfg()
        config.update(llm_model="model-b", safe_mode=False)
        assert config.llm_model == "model-b"
        assert config.safe_mode is False

    def test_update_unknown_field_raises(self) -> None:
        config = _cfg()
        with pytest.raises(ValueError, match="Unknown config fields"):
            config.update(nonexistent="value")


class TestRuntimeConfigSnapshot:
    """Test snapshot() returns correct data."""

    def test_snapshot_excludes_api_key(self) -> None:
        config = _cfg(llm_api_key="secret-key")
        snap = config.snapshot()
        assert "llm_api_key" not in snap
        assert snap["llm_model"] == "model-a"
        assert snap["safe_mode"] is True

    def test_snapshot_includes_api_base(self) -> None:
        config = _cfg(llm_api_base="http://base", safe_mode=False)
        snap = config.snapshot()
        assert snap["llm_api_base"] == "http://base"
        assert snap["safe_mode"] is False


class TestRuntimeConfigPersistence:
    """Test JSON file persistence."""

    def test_persist_creates_file(self, tmp_path) -> None:
        persist_path = tmp_path / ".bsage" / "runtime_config.json"
        config = _cfg(llm_api_key="key", persist_path=persist_path)
        config.update(safe_mode=False)

        assert persist_path.exists()
        data = json.loads(persist_path.read_text())
        assert data["safe_mode"] is False
        assert data["llm_model"] == "model-a"
        assert data["llm_api_key"] == "key"

    def test_persist_updates_on_change(self, tmp_path) -> None:
        persist_path = tmp_path / "config.json"
        config = _cfg(persist_path=persist_path)
        config.update(llm_model="model-b")

        data = json.loads(persist_path.read_text())
        assert data["llm_model"] == "model-b"

    def test_no_persist_when_path_is_none(self) -> None:
        config = _cfg(persist_path=None)
        config.update(safe_mode=False)
        # Should not raise — just skip persistence
        assert config.safe_mode is False

    def test_persist_failure_does_not_raise(self, tmp_path) -> None:
        persist_path = tmp_path / "config.json"
        config = _cfg(persist_path=persist_path)

        with patch(
            "bsage.core.runtime_config.Path.write_text",
            side_effect=OSError("disk full"),
        ):
            # Should not raise — in-memory update succeeds
            config.update(safe_mode=False)

        assert config.safe_mode is False


class TestRuntimeConfigFromSettings:
    """Test from_settings class method."""

    def test_from_settings_uses_defaults(self) -> None:
        settings = MagicMock()
        settings.llm_model = "anthropic/claude-sonnet-4-20250514"
        settings.llm_api_key = "sk-test"
        settings.llm_api_base = None
        settings.safe_mode = True
        settings.disabled_entries = []

        config = RuntimeConfig.from_settings(settings, persist_path=None)
        assert config.llm_model == "anthropic/claude-sonnet-4-20250514"
        assert config.llm_api_key == "sk-test"
        assert config.safe_mode is True

    def test_from_settings_overrides_from_json(self, tmp_path) -> None:
        persist_path = tmp_path / "config.json"
        persist_path.write_text(
            json.dumps(
                {
                    "llm_model": "ollama/llama3",
                    "llm_api_key": "overridden-key",
                    "llm_api_base": "http://localhost:11434",
                    "safe_mode": False,
                }
            )
        )

        settings = MagicMock()
        settings.llm_model = "anthropic/claude-sonnet-4-20250514"
        settings.llm_api_key = "sk-test"
        settings.llm_api_base = None
        settings.safe_mode = True
        settings.disabled_entries = []

        config = RuntimeConfig.from_settings(settings, persist_path=persist_path)
        assert config.llm_model == "ollama/llama3"
        assert config.llm_api_key == "overridden-key"
        assert config.llm_api_base == "http://localhost:11434"
        assert config.safe_mode is False

    def test_from_settings_ignores_missing_json(self, tmp_path) -> None:
        persist_path = tmp_path / "nonexistent.json"

        settings = MagicMock()
        settings.llm_model = "model-a"
        settings.llm_api_key = "key"
        settings.llm_api_base = None
        settings.safe_mode = True
        settings.disabled_entries = []

        config = RuntimeConfig.from_settings(settings, persist_path=persist_path)
        assert config.llm_model == "model-a"

    def test_from_settings_ignores_invalid_json(self, tmp_path) -> None:
        persist_path = tmp_path / "bad.json"
        persist_path.write_text("not valid json{{{")

        settings = MagicMock()
        settings.llm_model = "model-a"
        settings.llm_api_key = "key"
        settings.llm_api_base = None
        settings.safe_mode = True
        settings.disabled_entries = []

        config = RuntimeConfig.from_settings(settings, persist_path=persist_path)
        assert config.llm_model == "model-a"  # falls back to Settings

    def test_from_settings_partial_json_override(self, tmp_path) -> None:
        persist_path = tmp_path / "config.json"
        persist_path.write_text(json.dumps({"llm_model": "new-model"}))

        settings = MagicMock()
        settings.llm_model = "default-model"
        settings.llm_api_key = "key"
        settings.llm_api_base = None
        settings.safe_mode = True
        settings.disabled_entries = []

        config = RuntimeConfig.from_settings(settings, persist_path=persist_path)
        assert config.llm_model == "new-model"
        assert config.llm_api_key == "key"  # from Settings
        assert config.safe_mode is True  # from Settings


class TestDisabledEntries:
    """Test disabled_entries field in RuntimeConfig."""

    def test_init_default_empty_list(self) -> None:
        config = _cfg()
        assert config.disabled_entries == []

    def test_init_with_disabled_entries(self) -> None:
        config = _cfg(disabled_entries=["plugin-a", "skill-b"])
        assert config.disabled_entries == ["plugin-a", "skill-b"]

    def test_update_disabled_entries(self) -> None:
        config = _cfg()
        config.update(disabled_entries=["plugin-a"])
        assert config.disabled_entries == ["plugin-a"]

    def test_update_disabled_entries_to_empty(self) -> None:
        config = _cfg(disabled_entries=["plugin-a"])
        config.update(disabled_entries=[])
        assert config.disabled_entries == []

    def test_snapshot_includes_disabled_entries(self) -> None:
        config = _cfg(disabled_entries=["skill-x"])
        snap = config.snapshot()
        assert snap["disabled_entries"] == ["skill-x"]

    def test_persist_includes_disabled_entries(self, tmp_path) -> None:
        persist_path = tmp_path / "config.json"
        config = _cfg(persist_path=persist_path, disabled_entries=["a"])
        config.update(disabled_entries=["a", "b"])

        data = json.loads(persist_path.read_text())
        assert data["disabled_entries"] == ["a", "b"]
