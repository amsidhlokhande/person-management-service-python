"""Map framework, validation, database, and domain errors to safe API envelopes."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from e2e.exception.custom_exceptions import ConflictException, NotFoundException
from e2e.logging.correlation_middleware import correlation_id_context
from e2e.logging.trace import log_event
from e2e.model.response_model import ErrorDetail, ErrorResponse

logger = logging.getLogger("person_management.errors")


def _error_response(
        request: Request,
        status_code: int,
        code: str,
        message: str,
        errors: list[ErrorDetail] | None = None,
        headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build one sanitized error body and preserve protocol/correlation headers."""
    # Echo the request ID so client-side failures can be correlated with server logs.
    correlation_id = getattr(request.state, "correlation_id", "unavailable")
    response_headers = dict(headers or {})
    response_headers["X-Correlation-ID"] = correlation_id
    body = ErrorResponse(
        status=status_code,
        code=code,
        message=message,
        path=request.url.path,
        correlationId=correlation_id,
        errors=errors,
    )
    log_event(
        logger,
        logging.WARNING if status_code < 500 else logging.ERROR,
        "http.error.response",
        status_code=status_code,
        error_code=code,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json", exclude_none=True),
        headers=response_headers,
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Register the centralized exception-to-HTTP response mappings."""

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        """Replace framework details with a safe, stable public message."""
        status_codes = {
            401: ("UNAUTHORIZED", "Authentication is required or invalid"),
            403: ("FORBIDDEN", "You are not allowed to perform this action"),
            404: ("RESOURCE_NOT_FOUND", "The requested resource was not found"),
            405: ("METHOD_NOT_ALLOWED", "The requested method is not allowed"),
        }
        code, message = status_codes.get(
            exc.status_code, ("HTTP_ERROR", "The request could not be completed")
        )
        return _error_response(
            request, exc.status_code, code, message, headers=exc.headers
        )

    @application.exception_handler(NotFoundException)
    async def not_found_handler(request: Request, exc: NotFoundException):
        """Convert missing domain resources to a standardized 404 response."""
        return _error_response(request, 404, exc.code, str(exc))

    @application.exception_handler(ConflictException)
    async def conflict_handler(request: Request, exc: ConflictException):
        """Convert domain conflicts to a standardized 409 response."""
        return _error_response(request, 409, exc.code, str(exc))

    @application.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        """Return safe field locations without echoing invalid input values."""
        # Exclude Pydantic's input/context fields because they may contain credentials or PII.
        errors = [
            ErrorDetail(
                location=list(error["loc"]),
                message=error["msg"],
                error_type=error["type"],
            )
            for error in exc.errors()
        ]
        return _error_response(
            request, 422, "REQUEST_VALIDATION_FAILED", "Request validation failed", errors
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError):
        """Log database failure details privately and return a generic 500."""
        context_token = correlation_id_context.set(
            getattr(request.state, "correlation_id", "unavailable")
        )
        try:
            log_event(
                logger,
                logging.ERROR,
                "database_operation_failed",
                error_type=type(exc).__name__,
                path=request.url.path,
            )
        finally:
            correlation_id_context.reset(context_token)
        return _error_response(
            request, 500, "DATABASE_ERROR", "A database operation failed"
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        """Prevent unexpected exception details from being exposed to clients."""
        context_token = correlation_id_context.set(
            getattr(request.state, "correlation_id", "unavailable")
        )
        try:
            log_event(
                logger,
                logging.ERROR,
                "unexpected_application_error",
                error_type=type(exc).__name__,
                path=request.url.path,
            )
        finally:
            correlation_id_context.reset(context_token)
        return _error_response(
            request, 500, "INTERNAL_SERVER_ERROR", "An unexpected error occurred"
        )
