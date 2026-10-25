"""Public dependency-readiness and interactive architecture endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse

from e2e.model.response_model import HealthResponse
from e2e.route.dependencies import get_health_service
from e2e.service.health_service import HealthService

router = APIRouter(tags=["health"])
_ARCHITECTURE_PAGE = (
        Path(__file__).resolve().parents[2] / "docs" / "architecture.html"
)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Readiness endpoint that probes the service and all configured external clients.",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "One or more configured external clients are unavailable.",
        }
    },
)
def health(
        response: Response,
        service: HealthService = Depends(get_health_service),
):
    """Report API readiness and the status of every registered client."""
    report = service.readiness()
    if report.status != "UP":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report


@router.get("/architecture", include_in_schema=False)
def architecture():
    """Serve the interactive HLD, LLD, and request-sequence diagrams."""
    return FileResponse(_ARCHITECTURE_PAGE, media_type="text/html")
