"""Authentication checks for identities verified by the trusted mTLS gateway."""

import logging

from fastapi import HTTPException, Request, status

from e2e.logging.trace import log_event

logger = logging.getLogger("person_management.security")


def require_client_certificate(request: Request) -> str:
    """Require identity headers that the private-network mTLS gateway overwrites."""
    verified = request.headers.get("x-client-verify")
    subject = request.headers.get("x-client-subject")
    if verified != "SUCCESS" or not subject:
        log_event(logger, logging.WARNING, "security.client_certificate.rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid client certificate is required",
        )

    log_event(logger, logging.INFO, "security.client_certificate.accepted")
    return subject
