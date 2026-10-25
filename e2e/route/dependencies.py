"""Resolve application-scoped services for HTTP route dependency injection."""

from fastapi import Request

from e2e.service.health_service import HealthService
from e2e.service.person_service import PersonService


def get_person_service(request: Request) -> PersonService:
    """Resolve the person use-case service without exposing persistence to routes."""
    return request.app.state.person_service


def get_health_service(request: Request) -> HealthService:
    """Resolve readiness aggregation from the application composition root."""
    return request.app.state.health_service
