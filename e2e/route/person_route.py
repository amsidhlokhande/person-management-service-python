"""Protected HTTP endpoints for listing and managing people."""

from fastapi import APIRouter, Depends, Path, Query, Response, status

from e2e.config.security import get_current_user
from e2e.model.person_model import PersonCreate, PersonResponse, PersonUpdate
from e2e.model.response_model import ErrorResponse, PageResponse
from e2e.route.dependencies import get_person_service
from e2e.service.person_service import PersonService

router = APIRouter(
    prefix="/people",
    tags=["people"],
    responses={
        401: {"model": ErrorResponse, "description": "Missing, invalid, or expired access token."},
        404: {"model": ErrorResponse, "description": "The requested person does not exist."},
        409: {"model": ErrorResponse, "description": "A person already uses the supplied email address."},
        422: {"model": ErrorResponse, "description": "Query or request body failed validation."},
    },
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=PageResponse[PersonResponse],
    summary="List people",
    description="Return a page of people. Requires a valid Bearer access token.",
)
def list_people(
        offset: int = Query(
            default=0,
            ge=0,
            description="Number of records to skip before returning results.",
            examples=[0, 20],
        ),
        limit: int = Query(
            default=50,
            ge=1,
            le=100,
            description="Maximum number of records to return (1-100).",
            examples=[10, 50],
        ),
        service: PersonService = Depends(get_person_service),
):
    """Return a bounded, offset-based page of people."""
    results = service.list_people(offset, limit)
    return PageResponse(items=results, offset=offset, limit=limit)


@router.post(
    "",
    response_model=PersonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a person",
    description="Create a person using a valid, unique email address.",
    responses={
        201: {"description": "Person created successfully."},
        409: {
            "model": ErrorResponse,
            "description": "Another person already uses this email address.",
        },
    },
)
def create_person(
        person: PersonCreate,
        service: PersonService = Depends(get_person_service),
):
    """Validate and create a person, returning the persisted representation."""
    return service.create_person(person)


@router.get(
    "/{person_id}",
    response_model=PersonResponse,
    summary="Get a person",
    description="Return one person identified by its database ID.",
)
def get_person(
        person_id: int = Path(
            description="Positive integer ID assigned to a person.",
            examples=[1],
            gt=0,
        ),
        service: PersonService = Depends(get_person_service),
):
    """Return the requested person or a standardized 404 response."""
    return service.get_person(person_id)


@router.put(
    "/{person_id}",
    response_model=PersonResponse,
    summary="Update a person",
    description=(
            "Update only the supplied fields for the person ID. Omitted fields remain unchanged. "
            "Use null for phone to clear it; first_name, last_name, and email cannot be null."
    ),
    responses={
        200: {"description": "Person updated successfully."},
        404: {"model": ErrorResponse, "description": "The person ID does not exist."},
        409: {
            "model": ErrorResponse,
            "description": "Another person already uses the supplied email.",
        },
    },
)
def update_person(
        person_id: int = Path(
            description="Positive integer ID assigned to a person.",
            examples=[1],
            gt=0,
        ),
        person: PersonUpdate = ...,
        service: PersonService = Depends(get_person_service),
):
    """Update the supplied fields and return the updated record."""
    return service.update_person(person_id, person)


@router.delete(
    "/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a person",
    description="Permanently delete the person identified by this ID.",
    responses={
        204: {"description": "Person deleted; response has no body."},
        404: {"model": ErrorResponse, "description": "The person ID does not exist."},
    },
)
def delete_person(
        person_id: int = Path(
            description="Positive integer ID assigned to a person.",
            examples=[1],
            gt=0,
        ),
        service: PersonService = Depends(get_person_service),
):
    """Delete the person and return an empty 204 response."""
    service.delete_person(person_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
