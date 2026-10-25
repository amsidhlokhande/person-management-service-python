"""Profile-scoped registry that initializes and probes every configured client."""

import logging
from collections.abc import Callable

from sqlalchemy import MetaData
from sqlalchemy.engine import make_url

from constants import DatabaseClientSettings
from e2e.client.client_protocol import ClientHealth, DatabaseClient, ExternalClient
from e2e.client.sqlite_database_client import SQLiteDatabaseClient
from e2e.logging.trace import log_event

logger = logging.getLogger("person_management.client.registry")
DatabaseClientFactory = Callable[[str, str], DatabaseClient]
_DATABASE_CLIENT_FACTORIES: dict[str, DatabaseClientFactory] = {
    "sqlite": SQLiteDatabaseClient,
}


def register_database_backend(
        backend: str, factory: DatabaseClientFactory
) -> None:
    """Register an adapter factory once its backend driver is installed."""
    normalized_backend = backend.strip().lower()
    if not normalized_backend:
        raise ValueError("Database backend name must not be empty")
    if normalized_backend in _DATABASE_CLIENT_FACTORIES:
        raise ValueError(f"Database backend '{normalized_backend}' is already registered")
    _DATABASE_CLIENT_FACTORIES[normalized_backend] = factory


class ClientRegistry:
    """Own all external clients enabled for one active application profile."""

    def __init__(self, clients: dict[str, ExternalClient]):
        """Register instantiated clients by their profile-configured names."""
        self._clients = clients

    @classmethod
    def from_settings(
            cls, database_settings: tuple[DatabaseClientSettings, ...]
    ) -> "ClientRegistry":
        """Build all named clients only after validating supported backend adapters."""
        configured_backends = [
            (configured, make_url(configured.url).get_backend_name())
            for configured in database_settings
        ]
        unsupported = [
            f"{configured.name} ({backend})"
            for configured, backend in configured_backends
            if backend not in _DATABASE_CLIENT_FACTORIES
        ]
        if unsupported:
            raise ValueError(
                "No database adapter is registered for: "
                + ", ".join(unsupported)
                + ". Register an adapter and install its SQLAlchemy driver."
            )

        clients: dict[str, ExternalClient] = {}
        for configured, backend in configured_backends:
            clients[configured.name] = _DATABASE_CLIENT_FACTORIES[backend](
                configured.name, configured.url
            )
        return cls(clients)

    def initialize(self, metadata: MetaData) -> None:
        """Initialize every client; database adapters retain failures for readiness."""
        for client in self._clients.values():
            if isinstance(client, DatabaseClient):
                client.initialize(metadata)
            else:
                client.initialize()

    def database(self, name: str) -> DatabaseClient:
        """Return a named database client required by a persistence adapter."""
        client = self._clients[name]
        if not isinstance(client, DatabaseClient):
            raise TypeError(f"Configured client '{name}' is not a database client")
        return client

    def health_checks(self) -> list[ClientHealth]:
        """Probe every client so one unavailable backend does not mask the others."""
        results = [client.health_check() for client in self._clients.values()]
        for result in results:
            log_event(
                logger,
                logging.INFO if result.status == "UP" else logging.ERROR,
                "client.health.completed",
                client_name=result.name,
                client_type=result.client_type,
                status=result.status,
            )
        return results

    def close(self) -> None:
        """Release every configured external client during application shutdown."""
        for client in self._clients.values():
            client.close()
