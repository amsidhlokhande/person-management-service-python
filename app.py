"""FastAPI application factory, middleware assembly, and lifecycle management."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from constants import settings
from e2e.client.client_registry import ClientRegistry
from e2e.config.seed import seed_initial_data
from e2e.entity.base import Base
from e2e.exception.global_handler import register_exception_handlers
from e2e.interceptor.request_response_interceptor import RequestResponseInterceptor
from e2e.logging.correlation_middleware import CorrelationIdMiddleware
from e2e.logging.trace import log_event
from e2e.repo.person_repo import PersonRepository
from e2e.route.auth_route import router as auth_router
from e2e.route.health_route import router as health_router
from e2e.route.person_route import router as person_router
from e2e.service.health_service import HealthService
from e2e.service.person_service import PersonService

logger = logging.getLogger("person_management.lifecycle")


class CorrelatedFastAPI(FastAPI):
    """FastAPI variant that wraps every response in correlation-ID middleware."""

    def build_middleware_stack(self):
        """Place correlation middleware outside FastAPI's error middleware.

        This ensures even framework-generated error responses receive the same
        correlation header and request context as successful responses.
        """
        application = super().build_middleware_stack()
        return CorrelationIdMiddleware(RequestResponseInterceptor(application))


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize profile clients and release their resources with app lifespan."""
    log_event(logger, logging.INFO, "application.startup.started")
    clients = ClientRegistry.from_settings(settings.database_clients)
    application.state.client_registry = clients
    try:
        # Import above registers the Person mapping before initializing every client.
        clients.initialize(Base.metadata)
        primary_database = clients.database(settings.primary_database_client)
        repository = PersonRepository(primary_database)
        application.state.person_service = PersonService(repository)
        application.state.health_service = HealthService(clients, settings.profile)

        primary_health = primary_database.health_check()
        if primary_health.status == "UP":
            seed_initial_data(repository)
        else:
            log_event(
                logger,
                logging.ERROR,
                "application.startup.seed_skipped",
                client_name=primary_health.name,
                reason=primary_health.message,
            )
        log_event(logger, logging.INFO, "application.startup.completed")
        yield
    finally:
        # Dispose pools for every configured client, not only the person repository's client.
        clients.close()
        log_event(logger, logging.INFO, "application.shutdown.completed")


def create_app() -> FastAPI:
    """Build the application and register exception handling and API routers."""
    application = CorrelatedFastAPI(
        title="Person Management Service",
        description=(
            "A layered REST API for managing people. Use the authentication endpoints "
            "to obtain a Bearer token before calling protected people operations. "
            "Query, path, form, and JSON body fields include descriptions and examples."
        ),
        version="1.0.0",
        docs_url="/swagger",
        openapi_tags=[
            {"name": "health", "description": "Public health and architecture pages."},
            {
                "name": "authentication",
                "description": "Issue and refresh JWT access credentials.",
            },
            {
                "name": "people",
                "description": "Bearer-token-protected person directory operations.",
            },
        ],
        lifespan=lifespan,
    )
    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(person_router, prefix="/api/v1")
    return application


app = create_app()
