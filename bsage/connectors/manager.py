"""ConnectorManager — registry for connected external service connectors."""

from __future__ import annotations

import structlog

from bsage.connectors.base import BaseConnector
from bsage.core.exceptions import ConnectorNotFoundError

logger = structlog.get_logger(__name__)


class ConnectorManager:
    """Manages the lifecycle of connectors: connect, get, disconnect, list."""

    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}

    async def get(self, name: str) -> BaseConnector:
        """Return a connected connector by name.

        Raises ConnectorNotFoundError if the connector is not connected.
        """
        if name not in self._connectors:
            logger.warning("connector_not_found", connector=name)
            raise ConnectorNotFoundError(f"Connector '{name}' is not connected")
        return self._connectors[name]

    async def connect(self, name: str, connector: BaseConnector) -> None:
        """Register a connector under the given name.

        If a connector with the same name already exists, it is replaced.
        """
        if name in self._connectors:
            logger.info("connector_replaced", connector=name)
        else:
            logger.info("connector_connected", connector=name)
        self._connectors[name] = connector

    async def disconnect(self, name: str) -> None:
        """Remove a connector by name.

        Raises ConnectorNotFoundError if the connector is not connected.
        """
        if name not in self._connectors:
            logger.warning("connector_disconnect_not_found", connector=name)
            raise ConnectorNotFoundError(f"Cannot disconnect '{name}': connector is not connected")
        del self._connectors[name]
        logger.info("connector_disconnected", connector=name)

    def list_connected(self) -> list[str]:
        """Return the names of all currently connected connectors."""
        return list(self._connectors.keys())
