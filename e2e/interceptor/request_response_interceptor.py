"""Centralized, privacy-conscious HTTP exchange logging middleware."""

import json
import logging
import time
from urllib.parse import parse_qsl

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from e2e.logging.trace import log_event
from e2e.model.interceptor_model import HttpRequestLog, HttpResponseLog

logger = logging.getLogger("person_management.interceptor.http")
_MAX_LOGGED_BODY_BYTES = 64 * 1024
_REQUEST_HEADER_ALLOWLIST = {
    b"accept",
    b"content-length",
    b"content-type",
    b"user-agent",
    b"x-correlation-id",
}
_RESPONSE_HEADER_ALLOWLIST = {
    b"cache-control",
    b"content-length",
    b"content-type",
    b"x-correlation-id",
}


def _selected_headers(
        headers: list[tuple[bytes, bytes]], allowed: set[bytes]
) -> dict[str, str]:
    """Return only explicitly safe headers, excluding authorization and cookies."""
    return {
        name.decode("latin-1").lower(): value.decode("latin-1")[:256]
        for name, value in headers
        if name.lower() in allowed
    }


def _query_parameter_names(query: bytes) -> list[str]:
    """Return bounded query keys without retaining parameter values."""
    if len(query) > _MAX_LOGGED_BODY_BYTES:
        return ["<query_too_large>"]
    try:
        names = parse_qsl(
            query.decode("latin-1"),
            keep_blank_values=True,
            max_num_fields=1000,
        )
    except ValueError:
        return ["<too_many_query_parameters>"]
    return list(dict.fromkeys(key[:128] for key, _ in names))[:100]


def _payload_fields(
        payload: bytes,
        content_type: str | None,
        truncated: bool,
) -> tuple[list[str], str]:
    """Extract payload key paths without retaining or logging any submitted values."""
    if not payload:
        return [], "empty"
    if truncated:
        return [], "truncated"

    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    try:
        if media_type == "application/json" or media_type.endswith("+json"):
            document = json.loads(payload)
            fields: list[str] = []
            pending: list[tuple[object, str, int]] = [(document, "", 0)]
            while pending and len(fields) < 100:
                value, prefix, depth = pending.pop()
                if depth >= 10:
                    continue
                if isinstance(value, dict):
                    for key, child in value.items():
                        field_path = f"{prefix}.{key}" if prefix else str(key)
                        fields.append(field_path[:256])
                        pending.append((child, field_path[:256], depth + 1))
                        if len(fields) >= 100:
                            break
                elif isinstance(value, list):
                    pending.extend((child, prefix, depth + 1) for child in value[:100])
            return fields, "parsed"
        if media_type == "application/x-www-form-urlencoded":
            decoded = payload.decode("utf-8")
            return list(dict.fromkeys(key for key, _ in parse_qsl(decoded)))[:100], "parsed"
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        return [], "invalid"

    return [], "not_inspected"


class RequestResponseInterceptor:
    """Log request/response metadata once centrally without exposing body values."""

    def __init__(self, app: ASGIApp):
        """Wrap the downstream ASGI application."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Measure the complete HTTP exchange while transparently forwarding messages."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = list(scope.get("headers", []))
        request_content_type = _selected_headers(
            request_headers, {b"content-type"}
        ).get("content-type")
        query_names = _query_parameter_names(scope.get("query_string", b""))
        request_body = bytearray()
        request_body_size = 0
        request_truncated = False
        response_body = bytearray()
        response_body_size = 0
        response_truncated = False
        response_status = 500
        response_headers: list[tuple[bytes, bytes]] = []
        started = time.perf_counter()

        async def receive_with_capture() -> Message:
            """Observe incoming body bytes without changing ASGI receive behavior."""
            nonlocal request_body_size, request_truncated
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                request_body_size += len(body)
                remaining = _MAX_LOGGED_BODY_BYTES - len(request_body)
                if remaining > 0:
                    request_body.extend(body[:remaining])
                if len(body) > remaining:
                    request_truncated = True
            return message

        async def send_with_capture(message: Message) -> None:
            """Observe response metadata/body while forwarding the original message."""
            nonlocal response_status, response_headers, response_body_size, response_truncated
            if message["type"] == "http.response.start":
                response_status = message["status"]
                response_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                response_body_size += len(body)
                remaining = _MAX_LOGGED_BODY_BYTES - len(response_body)
                if remaining > 0:
                    response_body.extend(body[:remaining])
                if len(body) > remaining:
                    response_truncated = True
            await send(message)

        correlation_id = scope.get("state", {}).get("correlation_id", "unavailable")
        initial_request = HttpRequestLog(
            correlation_id=correlation_id,
            method=scope.get("method", ""),
            path=scope.get("path", ""),
            query_parameters=query_names,
            headers=_selected_headers(request_headers, _REQUEST_HEADER_ALLOWLIST),
            content_type=request_content_type,
            body_fields=[],
            body_truncated=False,
            body_parse_status="pending",
        )
        log_event(
            logger,
            logging.INFO,
            "http.request.received",
            request=initial_request.model_dump(exclude_none=True),
        )

        try:
            await self.app(scope, receive_with_capture, send_with_capture)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "http.exchange.failed",
                method=scope.get("method", ""),
                path=scope.get("path", ""),
                error_type=type(exc).__name__,
            )
            raise
        finally:
            request_fields, request_parse_status = _payload_fields(
                bytes(request_body), request_content_type, request_truncated
            )
            response_header_map = _selected_headers(
                response_headers, _RESPONSE_HEADER_ALLOWLIST
            )
            response_content_type = response_header_map.get("content-type")
            response_fields, response_parse_status = _payload_fields(
                bytes(response_body), response_content_type, response_truncated
            )
            route = scope.get("route")
            request_log = initial_request.model_copy(
                update={
                    "route_template": getattr(route, "path", None),
                    "body_size_bytes": request_body_size,
                    "body_fields": request_fields,
                    "body_truncated": request_truncated,
                    "body_parse_status": request_parse_status,
                }
            )
            response_log = HttpResponseLog(
                status_code=response_status,
                headers=response_header_map,
                content_type=response_content_type,
                body_size_bytes=response_body_size,
                body_fields=response_fields,
                body_truncated=response_truncated,
                body_parse_status=response_parse_status,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            log_event(
                logger,
                (
                    logging.ERROR
                    if response_status >= 500
                    else logging.WARNING
                    if response_status >= 400
                    else logging.INFO
                ),
                "http.response.sent",
                request=request_log.model_dump(exclude_none=True),
                response=response_log.model_dump(exclude_none=True),
            )
