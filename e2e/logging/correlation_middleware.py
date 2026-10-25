"""Structured logging setup and ASGI correlation-ID propagation."""

import contextvars
import json
import logging
import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
correlation_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="system"
)
_original_record_factory = logging.getLogRecordFactory()


def _correlation_record_factory(*args, **kwargs):
    """Attach the active request ID to every LogRecord before formatting."""
    record = _original_record_factory(*args, **kwargs)
    record.correlationId = correlation_id_context.get()
    return record


logging.setLogRecordFactory(_correlation_record_factory)


class JsonLogFormatter(logging.Formatter):
    """Format application and server records as JSON with a correlation ID."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize standard fields and optional safe trace-event attributes."""
        entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlationId": record.correlationId,
        }
        event = getattr(record, "trace_event", None)
        if event:
            entry["event"] = event
            entry.update(record.trace_fields)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=True)


def configure_logging() -> None:
    """Route application/server logs through a common JSON formatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not any(
            getattr(handler, "_person_management_handler", False)
            for handler in root_logger.handlers
    ):
        handler = logging.StreamHandler()
        handler._person_management_handler = True
        root_logger.addHandler(handler)
    for handler in root_logger.handlers:
        handler.setFormatter(JsonLogFormatter())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        configured_logger = logging.getLogger(name)
        configured_logger.handlers.clear()
        configured_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


configure_logging()


class CorrelationIdMiddleware:
    """Attach a validated correlation ID to request state, logs, and responses."""

    def __init__(self, app: ASGIApp):
        """Wrap the downstream ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Keep the correlation context active until the response is sent."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        supplied_id = headers.get(b"x-correlation-id", b"").decode("latin-1")
        correlation_id = (
            supplied_id
            if _VALID_CORRELATION_ID.fullmatch(supplied_id)
            else str(uuid.uuid4())
        )
        # The generated ID replaces malformed or untrusted header values.
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        context_token = correlation_id_context.set(correlation_id)

        async def send_with_correlation(message: Message) -> None:
            """Add the request ID to the first ASGI response message."""
            if message["type"] == "http.response.start":
                response_headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-correlation-id"
                ]
                response_headers.append(
                    (b"x-correlation-id", correlation_id.encode("ascii"))
                )
                message = {**message, "headers": response_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            # Reset context after the response to prevent ID leakage across async requests.
            correlation_id_context.reset(context_token)
