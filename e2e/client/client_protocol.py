"""Contracts shared by external clients and their aggregate health reporting."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sqlalchemy import MetaData
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ClientHealth:
    """Dependency readiness result safe to return from the public health endpoint."""

    name: str
    client_type: str
    status: str
    message: str


@runtime_checkable
class ExternalClient(Protocol):
    """Common health and lifecycle contract for registered external clients."""

    name: str

    def initialize(self) -> None:
        """Initialize the external dependency."""

    def health_check(self) -> ClientHealth:
        """Probe the backend and return a safe readiness result."""

    def close(self) -> None:
        """Release resources owned by the client."""


@runtime_checkable
class DatabaseClient(ExternalClient, Protocol):
    """Database operations required by repositories and application startup."""

    def initialize(self, metadata: MetaData) -> None:
        """Initialize this database and its configured ORM schema."""

    def session(self) -> AbstractContextManager[Session]:
        """Create a session owned and closed by the repository operation."""
