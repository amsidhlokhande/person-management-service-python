"""Database access operations for person records, isolated from HTTP and services."""

import logging
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from e2e.client.client_protocol import DatabaseClient
from e2e.entity.person_entity import Person
from e2e.exception.custom_exceptions import ConflictException
from e2e.logging.trace import log_event
from e2e.model.person_model import PersonCreate, PersonUpdate

logger = logging.getLogger("person_management.repository.people")


class PersonRepository:
    """Encapsulate persistence queries and transaction boundaries for people."""

    def __init__(self, database: DatabaseClient):
        """Bind the repository to its configured database client."""
        self.database = database

    def list(self, offset: int = 0, limit: int = 50) -> list[Person]:
        """Return a bounded page of people from the configured database."""
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "repository.people.list.started",
            offset=offset,
            limit=limit,
            client_name=self.database.name,
        )
        try:
            with self.database.session() as db:
                results = list(db.scalars(select(Person).offset(offset).limit(limit)).all())
        except SQLAlchemyError as exc:
            log_event(
                logger,
                logging.ERROR,
                "repository.people.list.failed",
                client_name=self.database.name,
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        log_event(
            logger,
            logging.INFO,
            "repository.people.list.completed",
            client_name=self.database.name,
            result_count=len(results),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return results

    def get(self, person_id: int) -> Person | None:
        """Return a person by primary key, or None when it does not exist."""
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "repository.people.get.started",
            person_id=person_id,
            client_name=self.database.name,
        )
        try:
            with self.database.session() as db:
                result = db.get(Person, person_id)
        except SQLAlchemyError as exc:
            log_event(
                logger,
                logging.ERROR,
                "repository.people.get.failed",
                person_id=person_id,
                client_name=self.database.name,
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        log_event(
            logger,
            logging.INFO,
            "repository.people.get.completed",
            person_id=person_id,
            found=result is not None,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return result

    def find_by_email(self, email: str) -> Person | None:
        """Find one person by the unique email key for idempotent seeding."""
        try:
            with self.database.session() as db:
                return db.scalar(select(Person).where(Person.email == email))
        except SQLAlchemyError as exc:
            log_event(
                logger,
                logging.ERROR,
                "repository.people.find_by_email.failed",
                client_name=self.database.name,
                error_type=type(exc).__name__,
            )
            raise

    def create(self, person: PersonCreate) -> Person:
        """Insert a validated person, committing inside this data-access boundary."""
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "repository.people.create.started",
            client_name=self.database.name,
        )
        try:
            with self.database.session() as db:
                entity = Person(**person.model_dump())
                db.add(entity)
                db.commit()
                db.refresh(entity)
        except IntegrityError as exc:
            log_event(
                logger,
                logging.WARNING,
                "repository.people.create.conflict",
                client_name=self.database.name,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise ConflictException("A person with this email already exists") from exc
        except SQLAlchemyError as exc:
            log_event(
                logger,
                logging.ERROR,
                "repository.people.create.failed",
                client_name=self.database.name,
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        log_event(
            logger,
            logging.INFO,
            "repository.people.create.committed",
            person_id=entity.id,
            client_name=self.database.name,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return entity

    def update(self, person_id: int, person: PersonUpdate) -> Person | None:
        """Update only supplied fields and commit the transaction."""
        started = time.perf_counter()
        try:
            with self.database.session() as db:
                entity = db.get(Person, person_id)
                if entity is None:
                    return None
                for field, value in person.model_dump(exclude_unset=True).items():
                    setattr(entity, field, value)
                db.commit()
                db.refresh(entity)
        except IntegrityError as exc:
            log_event(
                logger,
                logging.WARNING,
                "repository.people.update.conflict",
                person_id=person_id,
                client_name=self.database.name,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise ConflictException("A person with this email already exists") from exc
        except SQLAlchemyError as exc:
            log_event(
                logger,
                logging.ERROR,
                "repository.people.update.failed",
                person_id=person_id,
                client_name=self.database.name,
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        log_event(
            logger,
            logging.INFO,
            "repository.people.update.committed",
            person_id=entity.id,
            client_name=self.database.name,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return entity

    def delete(self, person_id: int) -> bool:
        """Delete one record and report whether the database contained that ID."""
        started = time.perf_counter()
        try:
            with self.database.session() as db:
                entity = db.get(Person, person_id)
                if entity is None:
                    return False
                db.delete(entity)
                db.commit()
        except SQLAlchemyError as exc:
            log_event(
                logger,
                logging.ERROR,
                "repository.people.delete.failed",
                person_id=person_id,
                client_name=self.database.name,
                error_type=type(exc).__name__,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise
        log_event(
            logger,
            logging.INFO,
            "repository.people.delete.committed",
            person_id=person_id,
            client_name=self.database.name,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return True
