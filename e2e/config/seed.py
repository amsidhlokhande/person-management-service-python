"""Idempotent startup seed for local development data."""

import logging
import time

from constants import settings
from e2e.logging.trace import log_event
from e2e.model.person_model import PersonCreate
from e2e.repo.person_repo import PersonRepository

logger = logging.getLogger("person_management.database.seed")


def seed_initial_data(repository: PersonRepository) -> None:
    """Insert the sample person only when seeding is enabled and absent."""
    if not settings.seed_data:
        log_event(logger, logging.INFO, "database.seed.skipped", profile=settings.profile)
        return

    started = time.perf_counter()
    log_event(logger, logging.INFO, "database.seed.started", profile=settings.profile)
    # The unique email makes repeated startup seeding safe and idempotent.
    existing = repository.find_by_email("ada@example.com")
    if existing is None:
        repository.create(
            PersonCreate(
                first_name="Ada",
                last_name="Lovelace",
                email="ada@example.com",
                phone=None,
            )
        )
        seeded = True
    else:
        seeded = False
    log_event(
        logger,
        logging.INFO,
        "database.seed.completed",
        profile=settings.profile,
        record_seeded=seeded,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
