"""CredentialStore — JSON file-backed credential storage for Skills."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from bsage.core.exceptions import CredentialNotFoundError

logger = structlog.get_logger(__name__)


class CredentialStore:
    """Stores and loads credentials from .credentials/{name}.json.

    Skills access credentials via context.credentials.get("service-name")
    to authenticate with external APIs. Each service's credentials are
    stored as a separate JSON file.
    """

    def __init__(self, credentials_dir: Path) -> None:
        self._dir = credentials_dir

    async def get(self, name: str) -> dict[str, Any]:
        """Load credentials for a named service.

        Args:
            name: Service identifier (e.g. "google-calendar").

        Returns:
            Dict of credential data.

        Raises:
            CredentialNotFoundError: If no credentials exist for the service.
        """
        path = self._dir / f"{name}.json"
        if not path.exists():
            logger.warning("credential_not_found", service=name)
            raise CredentialNotFoundError(f"No credentials for '{name}'")

        data = json.loads(path.read_text(encoding="utf-8"))
        logger.debug("credential_loaded", service=name)
        return data

    async def store(self, name: str, data: dict[str, Any]) -> None:
        """Save credentials for a named service.

        Args:
            name: Service identifier.
            data: Credential data to persist.
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{name}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("credential_stored", service=name)

    async def delete(self, name: str) -> None:
        """Remove credentials for a named service.

        Args:
            name: Service identifier.

        Raises:
            CredentialNotFoundError: If no credentials exist for the service.
        """
        path = self._dir / f"{name}.json"
        if not path.exists():
            raise CredentialNotFoundError(f"No credentials for '{name}'")
        path.unlink()
        logger.info("credential_deleted", service=name)

    def list_services(self) -> list[str]:
        """Return names of all services with stored credentials."""
        if not self._dir.is_dir():
            return []
        return sorted(p.stem for p in self._dir.glob("*.json"))
