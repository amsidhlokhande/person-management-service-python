"""Typed, privacy-conscious request and response metadata for interceptor logs."""

from pydantic import BaseModel, ConfigDict, Field


class HttpRequestLog(BaseModel):
    """Safe request metadata emitted by the HTTP interceptor."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    method: str
    path: str
    route_template: str | None = None
    query_parameters: list[str] = Field(
        description="Query parameter names only; values are deliberately excluded."
    )
    headers: dict[str, str] = Field(
        description="Allow-listed headers that do not contain credentials."
    )
    content_type: str | None = None
    body_size_bytes: int | None = None
    body_fields: list[str] = Field(
        description="Payload field paths only; submitted values are never logged."
    )
    body_truncated: bool
    body_parse_status: str


class HttpResponseLog(BaseModel):
    """Safe response metadata emitted by the HTTP interceptor."""

    model_config = ConfigDict(extra="forbid")

    status_code: int
    headers: dict[str, str] = Field(
        description="Allow-listed response headers without response content."
    )
    content_type: str | None = None
    body_size_bytes: int
    body_fields: list[str] = Field(
        description="Response field paths only; response values are never logged."
    )
    body_truncated: bool
    body_parse_status: str
    duration_ms: float
