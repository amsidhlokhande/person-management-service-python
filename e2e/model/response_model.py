"""Shared Pydantic response envelopes for pagination, health, and API errors."""

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    """Page of results with the applied offset and limit."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "id": 1,
                            "first_name": "Ada",
                            "last_name": "Lovelace",
                            "email": "ada@example.com",
                            "phone": None,
                        }
                    ],
                    "offset": 0,
                    "limit": 50,
                }
            ]
        }
    )

    items: list[T] = Field(description="Records returned for this page.")
    offset: int = Field(ge=0, description="Number of records skipped.")
    limit: int = Field(ge=1, le=100, description="Maximum records requested.")


class HealthClientStatus(BaseModel):
    """Sanitized readiness information for one external dependency."""

    name: str = Field(description="Configured client name.")
    client_type: str = Field(description="External client category.")
    status: str = Field(description="UP when this dependency can be reached.")
    message: str = Field(description="Safe status summary; excludes connection secrets.")


class HealthResponse(BaseModel):
    """Readiness result for the API and all configured external clients."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "UP",
                    "profile": "DEV",
                    "clients": [
                        {
                            "name": "primary",
                            "client_type": "database",
                            "status": "UP",
                            "message": "Database connection is available.",
                        }
                    ],
                }
            ]
        }
    )

    status: str = Field(description="UP when every configured client is ready; otherwise DOWN.")
    profile: str = Field(description="Active application profile.")
    clients: list[HealthClientStatus] = Field(
        description="Readiness result for every registered external client."
    )


class ErrorDetail(BaseModel):
    """Safe, field-level validation detail without raw input values."""

    location: list[str | int] = Field(
        default_factory=list,
        description="Request location of the invalid field, such as body.email.",
    )
    message: str = Field(description="Human-readable validation message.")
    error_type: str = Field(description="Stable Pydantic validation error type.")


class ErrorResponse(BaseModel):
    """Standard error format shared by API and framework exceptions."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "timestamp": "2026-10-25T00:00:00Z",
                    "status": 404,
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "The requested resource was not found",
                    "path": "/api/v1/people/99",
                    "correlationId": "7b3f94c2-75d8-4e2b-bf17-3f08f013c295",
                }
            ]
        }
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC time when the error response was created.",
    )
    status: int = Field(description="HTTP status code.")
    code: str = Field(description="Stable machine-readable application error code.")
    message: str = Field(description="Safe summary suitable for API clients.")
    path: str = Field(description="Request path that produced the error.")
    correlationId: str = Field(description="Request ID for matching server-side logs.")
    errors: list[ErrorDetail] | None = Field(
        default=None,
        description="Optional field-level validation errors.",
    )
