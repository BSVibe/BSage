"""Tests for bsage.connectors.manager — ConnectorManager."""

from unittest.mock import AsyncMock, PropertyMock

import pytest

from bsage.connectors.base import BaseConnector
from bsage.connectors.manager import ConnectorManager
from bsage.core.exceptions import ConnectorNotFoundError


def _make_mock_connector(name: str) -> BaseConnector:
    """Create a mock connector that satisfies the BaseConnector interface."""
    mock = AsyncMock(spec=BaseConnector)
    type(mock).name = PropertyMock(return_value=name)
    type(mock).is_authenticated = PropertyMock(return_value=True)
    return mock


class TestConnectorManager:
    """Tests for ConnectorManager connect / get / disconnect / list."""

    async def test_get_raises_on_missing_connector(self) -> None:
        """Getting a connector that was never connected raises ConnectorNotFoundError."""
        manager = ConnectorManager()
        with pytest.raises(ConnectorNotFoundError):
            await manager.get("nonexistent")

    async def test_connect_and_get(self) -> None:
        """After connecting a connector, get() returns it."""
        manager = ConnectorManager()
        mock_conn = _make_mock_connector("google-calendar")

        await manager.connect("google-calendar", mock_conn)
        result = await manager.get("google-calendar")

        assert result is mock_conn

    async def test_disconnect_removes_connector(self) -> None:
        """After disconnecting, get() raises ConnectorNotFoundError."""
        manager = ConnectorManager()
        mock_conn = _make_mock_connector("google-calendar")

        await manager.connect("google-calendar", mock_conn)
        await manager.disconnect("google-calendar")

        with pytest.raises(ConnectorNotFoundError):
            await manager.get("google-calendar")

    async def test_list_connected_empty(self) -> None:
        """A fresh ConnectorManager has no connected connectors."""
        manager = ConnectorManager()
        assert manager.list_connected() == []

    async def test_list_connected_returns_names(self) -> None:
        """list_connected returns the names of all connected connectors."""
        manager = ConnectorManager()
        await manager.connect("google-calendar", _make_mock_connector("google-calendar"))
        await manager.connect("notion", _make_mock_connector("notion"))

        names = manager.list_connected()

        assert sorted(names) == ["google-calendar", "notion"]

    async def test_connect_overwrites_existing(self) -> None:
        """Connecting with the same name replaces the old connector."""
        manager = ConnectorManager()
        old_conn = _make_mock_connector("google-calendar")
        new_conn = _make_mock_connector("google-calendar")

        await manager.connect("google-calendar", old_conn)
        await manager.connect("google-calendar", new_conn)

        result = await manager.get("google-calendar")
        assert result is new_conn
        assert result is not old_conn

    async def test_disconnect_nonexistent_raises(self) -> None:
        """Disconnecting a connector that is not connected raises ConnectorNotFoundError."""
        manager = ConnectorManager()
        with pytest.raises(ConnectorNotFoundError):
            await manager.disconnect("nonexistent")
