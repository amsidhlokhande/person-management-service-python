"""SQLAlchemy-backed SQLite client used for development and local execution."""

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from e2e.client.client_protocol import ClientHealth
from e2e.logging.trace import log_event

logger = logging.getLogger("person_management.client.database")


class SQLiteDatabaseClient:
    """Own one SQLite engine, schema initialization, health probe, and sessions."""

    def __init__(self, name: str, url: str):
        """Create the engine lazily with SQLite-specific thread and memory options."""
        database_url = make_url(url)
        if database_url.get_backend_name() != "sqlite":
            raise ValueError("SQLiteDatabaseClient requires a sqlite:// database URL")
        options: dict[str, object] = {
            "connect_args": {"check_same_thread": False},
        }
        if database_url.database in {None, "", ":memory:"}:
            options["poolclass"] = StaticPool
        self.name = name
        self._engine = create_engine(database_url, **options)
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self._initialization_error: str | None = None

    def initialize(self, metadata: MetaData) -> None:
        """Create this client's schema, retaining failure state for readiness checks."""
        try:
            metadata.create_all(bind=self._engine)
            self._initialization_error = None
            log_event(
                logger,
                logging.INFO,
                "client.database.initialized",
                client_name=self.name,
                backend="sqlite",
            )
        except SQLAlchemyError as exc:
            self._initialization_error = type(exc).__name__
            log_event(
                logger,
                logging.ERROR,
                "client.database.initialization_failed",
                client_name=self.name,
                error_type=self._initialization_error,
            )

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield an operation-scoped ORM session and roll back failed operations."""
        database = self._session_factory()
        try:
            yield database
        except Exception:
            database.rollback()
            raise
        finally:
            database.close()

    def health_check(self) -> ClientHealth:
        """Probe with a lightweight query and expose no connection details."""
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            return ClientHealth(
                name=self.name,
                client_type="database",
                status="DOWN",
                message=f"Database probe failed ({type(exc).__name__}).",
            )
        if self._initialization_error:
            return ClientHealth(
                name=self.name,
                client_type="database",
                status="DOWN",
                message=f"Database schema initialization failed ({self._initialization_error}).",
            )
        return ClientHealth(
            name=self.name,
            client_type="database",
            status="UP",
            message="Database connection is available.",
        )

    def close(self) -> None:
        """Dispose of the connection pool when application lifespan ends."""
        self._engine.dispose()
