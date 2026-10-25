"""JWT creation, credential comparison, and access-token authentication."""

import hmac
import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from constants import settings
from e2e.logging.trace import log_event

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    description=(
        "For this service, enter the active profile's configured AUTH_USERNAME and "
        "AUTH_PASSWORD. The OAuth2 client_id and client_secret fields are not used; "
        "leave them blank. PyCharm/local values are configured in .env as "
        "<PROFILE>_AUTH_USERNAME and <PROFILE>_AUTH_PASSWORD. After authorizing, "
        "Swagger sends the returned access token with protected requests."
    ),
)
logger = logging.getLogger("person_management.security")


def create_token(subject: str, token_type: str, lifetime: timedelta) -> str:
    """Sign a token with explicit type and expiry claims."""
    now = datetime.now(timezone.utc)
    # The type claim prevents a refresh token from being accepted as an API credential.
    return jwt.encode(
        {
            "sub": subject,
            "type": token_type,
            "iat": now,
            "exp": now + lifetime,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """Verify token signature and expiry using the active profile settings."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def credentials_match(username: str, password: str) -> bool:
    """Compare configured credentials without ordinary string timing leaks."""
    username_matches = hmac.compare_digest(
        username.encode("utf-8"), settings.auth_username.encode("utf-8")
    )
    password_matches = hmac.compare_digest(
        password.encode("utf-8"), settings.auth_password.encode("utf-8")
    )
    return username_matches and password_matches


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Require a valid access token belonging to the configured service user."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError as exc:
        log_event(logger, logging.WARNING, "security.access_token.invalid")
        raise credentials_error from exc

    subject = payload.get("sub")
    if payload.get("type") != "access" or subject != settings.auth_username:
        log_event(logger, logging.WARNING, "security.access_token.rejected")
        raise credentials_error
    # Return only the verified subject; callers do not need the raw token claims.
    log_event(logger, logging.INFO, "security.access_token.accepted")
    return subject
