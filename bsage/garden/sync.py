"""SyncManager — extensible vault sync after writes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)


class WriteEventType(Enum):
    """Type of vault write operation."""

    SEED = "seed"
    GARDEN = "garden"
    ACTION = "action"


@dataclass
class WriteEvent:
    """Describes a vault write that just occurred."""

    event_type: WriteEventType
    path: Path
    source: str


@runtime_checkable
class SyncBackend(Protocol):
    """Protocol for vault synchronization backends.

    Implementations (e.g. S3SyncBackend, GitSyncBackend) are registered
    with SyncManager and notified after every vault write.
    """

    @property
    def name(self) -> str: ...

    async def sync(self, event: WriteEvent) -> None: ...


class SyncManager:
    """Manages registered sync backends and dispatches write events.

    Sync failures are logged but never propagated — local writes always
    succeed regardless of sync backend status.
    """

    def __init__(self) -> None:
        self._backends: dict[str, SyncBackend] = {}

    def register(self, backend: SyncBackend) -> None:
        """Register a sync backend."""
        self._backends[backend.name] = backend
        logger.info("sync_backend_registered", name=backend.name)

    def unregister(self, name: str) -> None:
        """Remove a sync backend by name.

        Raises:
            KeyError: If the backend is not registered.
        """
        del self._backends[name]
        logger.info("sync_backend_unregistered", name=name)

    def list_backends(self) -> list[str]:
        """Return names of all registered backends."""
        return list(self._backends.keys())

    async def notify(self, event: WriteEvent) -> None:
        """Notify all registered backends of a write event.

        Each backend is called independently. Failures are logged
        but never propagated — the local write has already succeeded.
        """
        for name, backend in self._backends.items():
            try:
                await backend.sync(event)
                logger.debug("sync_backend_notified", backend=name, path=str(event.path))
            except Exception:
                logger.warning(
                    "sync_backend_failed",
                    backend=name,
                    path=str(event.path),
                    exc_info=True,
                )
