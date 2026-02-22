"""Tests for bsage.core.credential_store — CredentialStore."""

import json

import pytest

from bsage.core.credential_store import CredentialStore
from bsage.core.exceptions import CredentialNotFoundError


class TestCredentialStoreGet:
    """Test credential loading."""

    async def test_get_returns_stored_data(self, tmp_path) -> None:
        creds_dir = tmp_path / ".credentials"
        creds_dir.mkdir()
        (creds_dir / "google-calendar.json").write_text(
            json.dumps({"client_id": "abc", "client_secret": "xyz"})
        )
        store = CredentialStore(creds_dir)
        result = await store.get("google-calendar")
        assert result == {"client_id": "abc", "client_secret": "xyz"}

    async def test_get_missing_raises(self, tmp_path) -> None:
        store = CredentialStore(tmp_path / ".credentials")
        with pytest.raises(CredentialNotFoundError, match="No credentials for 'missing'"):
            await store.get("missing")


class TestCredentialStoreStore:
    """Test credential saving."""

    async def test_store_creates_file(self, tmp_path) -> None:
        creds_dir = tmp_path / ".credentials"
        store = CredentialStore(creds_dir)
        await store.store("notion", {"token": "secret-token"})

        path = creds_dir / "notion.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data == {"token": "secret-token"}

    async def test_store_overwrites_existing(self, tmp_path) -> None:
        creds_dir = tmp_path / ".credentials"
        creds_dir.mkdir()
        (creds_dir / "svc.json").write_text(json.dumps({"old": "data"}))

        store = CredentialStore(creds_dir)
        await store.store("svc", {"new": "data"})

        data = json.loads((creds_dir / "svc.json").read_text())
        assert data == {"new": "data"}

    async def test_store_creates_parent_dir(self, tmp_path) -> None:
        creds_dir = tmp_path / "nested" / ".credentials"
        store = CredentialStore(creds_dir)
        await store.store("test", {"key": "value"})
        assert (creds_dir / "test.json").exists()


class TestCredentialStoreDelete:
    """Test credential deletion."""

    async def test_delete_removes_file(self, tmp_path) -> None:
        creds_dir = tmp_path / ".credentials"
        creds_dir.mkdir()
        (creds_dir / "svc.json").write_text("{}")

        store = CredentialStore(creds_dir)
        await store.delete("svc")
        assert not (creds_dir / "svc.json").exists()

    async def test_delete_missing_raises(self, tmp_path) -> None:
        store = CredentialStore(tmp_path / ".credentials")
        with pytest.raises(CredentialNotFoundError):
            await store.delete("nonexistent")


class TestCredentialStoreListServices:
    """Test listing stored credentials."""

    async def test_list_services_empty(self, tmp_path) -> None:
        store = CredentialStore(tmp_path / "no-dir")
        assert store.list_services() == []

    async def test_list_services_returns_sorted_names(self, tmp_path) -> None:
        creds_dir = tmp_path / ".credentials"
        creds_dir.mkdir()
        (creds_dir / "notion.json").write_text("{}")
        (creds_dir / "google-calendar.json").write_text("{}")
        (creds_dir / "telegram.json").write_text("{}")

        store = CredentialStore(creds_dir)
        assert store.list_services() == ["google-calendar", "notion", "telegram"]
