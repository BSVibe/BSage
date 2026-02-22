"""Tests for bsage.garden.sync — SyncManager and WriteEvent."""

from pathlib import Path
from unittest.mock import AsyncMock, PropertyMock

import pytest

from bsage.garden.sync import SyncBackend, SyncManager, WriteEvent, WriteEventType


def _make_event(
    event_type: WriteEventType = WriteEventType.SEED,
    path: str = "/vault/seeds/test/2026-02-22.md",
    source: str = "test-skill",
) -> WriteEvent:
    return WriteEvent(event_type=event_type, path=Path(path), source=source)


def _make_backend(
    name: str = "test-backend",
    sync_side_effect: Exception | None = None,
) -> AsyncMock:
    backend = AsyncMock(spec=SyncBackend)
    type(backend).name = PropertyMock(return_value=name)
    if sync_side_effect:
        backend.sync.side_effect = sync_side_effect
    return backend


class TestWriteEvent:
    """Test WriteEvent dataclass."""

    def test_write_event_fields(self) -> None:
        event = _make_event()
        assert event.event_type == WriteEventType.SEED
        assert event.path == Path("/vault/seeds/test/2026-02-22.md")
        assert event.source == "test-skill"

    def test_write_event_types(self) -> None:
        assert WriteEventType.SEED.value == "seed"
        assert WriteEventType.GARDEN.value == "garden"
        assert WriteEventType.ACTION.value == "action"


class TestSyncManagerRegistration:
    """Test register/unregister/list_backends."""

    def test_register_adds_backend(self) -> None:
        mgr = SyncManager()
        backend = _make_backend("s3")
        mgr.register(backend)
        assert mgr.list_backends() == ["s3"]

    def test_register_multiple_backends(self) -> None:
        mgr = SyncManager()
        mgr.register(_make_backend("s3"))
        mgr.register(_make_backend("git"))
        assert set(mgr.list_backends()) == {"s3", "git"}

    def test_unregister_removes_backend(self) -> None:
        mgr = SyncManager()
        mgr.register(_make_backend("s3"))
        mgr.unregister("s3")
        assert mgr.list_backends() == []

    def test_unregister_unknown_raises(self) -> None:
        mgr = SyncManager()
        with pytest.raises(KeyError):
            mgr.unregister("nonexistent")

    def test_list_backends_empty(self) -> None:
        mgr = SyncManager()
        assert mgr.list_backends() == []

    def test_register_replaces_existing(self) -> None:
        mgr = SyncManager()
        mgr.register(_make_backend("s3"))
        new_backend = _make_backend("s3")
        mgr.register(new_backend)
        assert mgr.list_backends() == ["s3"]


class TestSyncManagerNotify:
    """Test notify dispatches to backends."""

    async def test_notify_calls_sync(self) -> None:
        mgr = SyncManager()
        backend = _make_backend("s3")
        mgr.register(backend)

        event = _make_event()
        await mgr.notify(event)
        backend.sync.assert_called_once_with(event)

    async def test_notify_calls_all_backends(self) -> None:
        mgr = SyncManager()
        b1 = _make_backend("s3")
        b2 = _make_backend("git")
        mgr.register(b1)
        mgr.register(b2)

        event = _make_event()
        await mgr.notify(event)
        b1.sync.assert_called_once_with(event)
        b2.sync.assert_called_once_with(event)

    async def test_notify_no_backends(self) -> None:
        mgr = SyncManager()
        event = _make_event()
        # Should not raise
        await mgr.notify(event)

    async def test_notify_failure_does_not_propagate(self) -> None:
        mgr = SyncManager()
        failing = _make_backend("broken", sync_side_effect=RuntimeError("network error"))
        mgr.register(failing)

        event = _make_event()
        # Should not raise
        await mgr.notify(event)
        failing.sync.assert_called_once()

    async def test_notify_one_failure_does_not_block_others(self) -> None:
        mgr = SyncManager()
        failing = _make_backend("broken", sync_side_effect=RuntimeError("fail"))
        healthy = _make_backend("healthy")
        mgr.register(failing)
        mgr.register(healthy)

        event = _make_event()
        await mgr.notify(event)
        # Both should be called
        failing.sync.assert_called_once()
        healthy.sync.assert_called_once()


class TestSyncBackendProtocol:
    """Test that SyncBackend is a runtime-checkable protocol."""

    def test_mock_implements_protocol(self) -> None:
        backend = _make_backend("test")
        assert isinstance(backend, SyncBackend)
