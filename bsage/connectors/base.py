"""Base connector interfaces and authentication data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConnectorAuth:
    """Authentication metadata for a connector."""

    connector_name: str
    auth_type: str  # oauth2 / api_key / token
    credentials_path: Path
    is_authenticated: bool = False


class BaseConnector(ABC):
    """Abstract base class that every connector must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this connector (e.g. 'google-calendar')."""
        ...

    @abstractmethod
    async def authenticate(self) -> None:
        """Perform authentication using stored credentials."""
        ...

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Return True if the connector has valid authentication."""
        ...
