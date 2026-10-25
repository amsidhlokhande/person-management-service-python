"""Small helper for consistent structured events across service layers."""

import logging
from typing import Any


def log_event(
        logger: logging.Logger,
        level: int,
        event: str,
        **fields: Any,
) -> None:
    """Emit a named event with machine-readable fields for JSON formatting."""
    logger.log(level, event, extra={"trace_event": event, "trace_fields": fields})
