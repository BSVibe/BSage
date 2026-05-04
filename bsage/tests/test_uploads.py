"""Tests for POST /api/uploads — generic file upload endpoint.

Used by Phase 2b (memory imports) and Phase 3 (Obsidian ZIP) so plugins
can read uploaded files from a known temp path via input_data.upload_id.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def upload_app(tmp_path: Path):
    """Build a minimal FastAPI app with the upload route mounted."""
    from fastapi import FastAPI

    from bsage.gateway.dependencies import AppState
    from bsage.gateway.routes import create_routes

    state = MagicMock(spec=AppState)

    async def _mock_get_current_user():
        principal = MagicMock()
        principal.active_tenant_id = "tenant-1"
        principal.id = "user-1"
        return principal

    state.get_current_user = _mock_get_current_user

    # Vault root inside tmp_path; uploads dir sits as a sibling
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    state.vault = MagicMock()
    state.vault.root = vault_root

    # Stubs the rest of the create_routes deps would need
    state.plugin_loader = MagicMock()
    state.skill_loader = MagicMock()
    state.plugin_loader.load_all = AsyncMock(return_value={})
    state.skill_loader.load_all = AsyncMock(return_value={})
    state.runtime_config = MagicMock()
    state.runtime_config.disabled_entries = []
    state.credential_store = MagicMock()
    state.credential_store.list_services = MagicMock(return_value=[])
    state.danger_analyzer = MagicMock()
    state.danger_analyzer.analyze = AsyncMock(return_value=(False, ""))

    app = FastAPI()
    app.include_router(create_routes(state))

    client = TestClient(app)
    return client, state, tmp_path


class TestUploadEndpoint:
    def test_upload_returns_id_and_path(self, upload_app) -> None:
        client, _, tmp_path = upload_app
        resp = client.post(
            "/api/uploads",
            files={"file": ("note.md", io.BytesIO(b"# Hello"), "text/markdown")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "upload_id" in body
        assert "path" in body
        assert "expires_at" in body
        # Default endpoint stores under <vault.root.parent>/uploads/<id>/<filename>
        stored = Path(body["path"])
        assert stored.exists()
        assert stored.read_bytes() == b"# Hello"

    def test_upload_id_is_unique(self, upload_app) -> None:
        client, *_ = upload_app
        r1 = client.post(
            "/api/uploads",
            files={"file": ("a.md", io.BytesIO(b"a"), "text/markdown")},
        )
        r2 = client.post(
            "/api/uploads",
            files={"file": ("a.md", io.BytesIO(b"b"), "text/markdown")},
        )
        assert r1.json()["upload_id"] != r2.json()["upload_id"]

    def test_upload_isolates_by_tenant(self, upload_app) -> None:
        client, _, tmp_path = upload_app
        resp = client.post(
            "/api/uploads",
            files={"file": ("x.md", io.BytesIO(b"hi"), "text/markdown")},
        )
        assert resp.status_code == 200
        # Path should contain the tenant id segment so cross-tenant access
        # via raw filesystem paths can be vetted by callers.
        assert "tenant-1" in resp.json()["path"]

    def test_upload_rejects_path_traversal_filename(self, upload_app) -> None:
        client, *_ = upload_app
        resp = client.post(
            "/api/uploads",
            files={"file": ("../escape.md", io.BytesIO(b"x"), "text/markdown")},
        )
        # Endpoint must sanitize and not write outside the upload dir.
        assert resp.status_code == 200
        stored = Path(resp.json()["path"])
        # Filename component should NOT contain ".."
        assert ".." not in stored.name
        assert stored.exists()

    def test_upload_rejects_oversized_file(self, upload_app) -> None:
        client, *_ = upload_app
        # 51 MB blob — over the configured 50 MB cap
        big = b"x" * (51 * 1024 * 1024)
        resp = client.post(
            "/api/uploads",
            files={"file": ("big.bin", io.BytesIO(big), "application/octet-stream")},
        )
        assert resp.status_code == 413

    def test_response_carries_filename(self, upload_app) -> None:
        client, *_ = upload_app
        resp = client.post(
            "/api/uploads",
            files={"file": ("conversations.json", io.BytesIO(b"{}"), "application/json")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "conversations.json"
