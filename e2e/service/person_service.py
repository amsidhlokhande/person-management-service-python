"""Person use cases, domain rules, and service-to-repository orchestration."""

import logging
import time

from e2e.exception.custom_exceptions import NotFoundException
from e2e.logging.trace import log_event
from e2e.model.person_model import PersonCreate, PersonUpdate
from e2e.repo.person_repo import PersonRepository

logger = logging.getLogger("person_management.service.people")


class PersonService:
    """Apply person-domain rules without depending on HTTP or database sessions."""

    def __init__(self, repository: PersonRepository):
        """Receive the persistence abstraction from the application composition root."""
        self.repository = repository

    def list_people(self, offset: int, limit: int):
        """Request one bounded result page from the repository."""
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "service.people.list.started",
            offset=offset,
            limit=limit,
        )
        results = self.repository.list(offset, limit)
        log_event(
            logger,
            logging.INFO,
            "service.people.list.completed",
            result_count=len(results),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return results

    def get_person(self, person_id: int):
        """Load a person or raise a domain-level not-found exception."""
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "service.people.get.started",
            person_id=person_id,
        )
        person = self.repository.get(person_id)
        if person is None:
            log_event(
                logger,
                logging.WARNING,
                "service.people.get.not_found",
                person_id=person_id,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise NotFoundException(f"Person {person_id} was not found")
        log_event(
            logger,
            logging.INFO,
            "service.people.get.completed",
            person_id=person_id,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return person

    def create_person(self, person: PersonCreate):
        """Delegate persistence and preserve the repository's domain conflict."""
        started = time.perf_counter()
        log_event(logger, logging.INFO, "service.people.create.started")
        result = self.repository.create(person)
        log_event(
            logger,
            logging.INFO,
            "service.people.create.completed",
            person_id=result.id,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return result

    def update_person(self, person_id: int, person: PersonUpdate):
        """Update supplied fields on a person or raise not-found."""
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "service.people.update.started",
            person_id=person_id,
        )
        result = self.repository.update(person_id, person)
        if result is None:
            raise NotFoundException(f"Person {person_id} was not found")
        log_event(
            logger,
            logging.INFO,
            "service.people.update.completed",
            person_id=result.id,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return result

    def delete_person(self, person_id: int) -> None:
        """Delete an existing person or raise the domain-level not-found error."""
        started = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "service.people.delete.started",
            person_id=person_id,
        )
        if not self.repository.delete(person_id):
            raise NotFoundException(f"Person {person_id} was not found")
        log_event(
            logger,
            logging.INFO,
            "service.people.delete.completed",
            person_id=person_id,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
