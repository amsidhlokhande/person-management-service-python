"""Aggregate readiness of all clients enabled for the active profile."""

from e2e.client.client_registry import ClientRegistry
from e2e.model.response_model import HealthClientStatus, HealthResponse


class HealthService:
    """Provide a service-level readiness result without exposing HTTP concerns."""

    def __init__(self, clients: ClientRegistry, profile: str):
        """Receive initialized clients and the active deployment profile."""
        self.clients = clients
        self.profile = profile

    def readiness(self) -> HealthResponse:
        """Report UP only when every registered external client is ready."""
        checks = self.clients.health_checks()
        status = "UP" if all(check.status == "UP" for check in checks) else "DOWN"
        return HealthResponse(
            status=status,
            profile=self.profile,
            clients=[
                HealthClientStatus(
                    name=check.name,
                    client_type=check.client_type,
                    status=check.status,
                    message=check.message,
                )
                for check in checks
            ],
        )
