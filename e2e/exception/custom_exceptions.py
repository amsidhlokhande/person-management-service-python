"""Domain exceptions mapped to stable HTTP status codes and response codes."""


class NotFoundException(Exception):
    """Raised when a requested person does not exist."""

    code = "RESOURCE_NOT_FOUND"


class ConflictException(Exception):
    """Raised when a person mutation violates a uniqueness constraint."""

    code = "RESOURCE_CONFLICT"
