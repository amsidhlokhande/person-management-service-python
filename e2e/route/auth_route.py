"""Public token issuance and refresh endpoints."""

from datetime import timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Form, HTTPException, status

from constants import settings
from e2e.config.security import create_token, credentials_match, decode_token
from e2e.model.auth_model import RefreshRequest, TokenRequest, TokenResponse
from e2e.model.response_model import ErrorResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


def _tokens(subject: str) -> TokenResponse:
    """Issue a new access/refresh token pair for the authenticated subject."""
    return TokenResponse(
        access_token=create_token(
            subject, "access", timedelta(minutes=settings.access_token_minutes)
        ),
        refresh_token=create_token(
            subject, "refresh", timedelta(days=settings.refresh_token_days)
        ),
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtain access and refresh tokens",
    description=(
            "Submit the active profile's configured username and password as form fields. "
            "Never include credentials in URLs or logs."
    ),
    responses={
        401: {
            "model": ErrorResponse,
            "description": "The supplied credentials are invalid.",
        },
        422: {"model": ErrorResponse, "description": "Credential form validation failed."},
    },
)
def issue_token(
        credentials: Annotated[TokenRequest, Form()],
):
    """Validate form credentials and return a signed token pair."""
    if not credentials_match(credentials.username, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    response = _tokens(credentials.username)
    return response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access and refresh tokens",
    description="Exchange a valid, unexpired refresh token for a new token pair.",
    responses={
        401: {
            "model": ErrorResponse,
            "description": "The token is invalid, expired, or not a refresh token.",
        },
        422: {"model": ErrorResponse, "description": "Refresh request validation failed."},
    },
)
def refresh_token(request: RefreshRequest):
    """Validate refresh-token claims and issue a replacement token pair."""
    try:
        payload = decode_token(request.refresh_token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from exc
    # A correctly signed token is still rejected unless it has refresh-only purpose.
    if payload.get("type") != "refresh" or payload.get("sub") != settings.auth_username:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    response = _tokens(payload["sub"])
    return response
