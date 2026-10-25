"""Pydantic DTOs for person creation, updates, and API responses."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class PersonCreate(BaseModel):
    """Validated input for creating a person."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "email": "ada@example.com",
                    "phone": "+1-555-0100",
                }
            ]
        }
    )

    first_name: str = Field(
        min_length=1,
        max_length=100,
        description="Person's given name (1-100 characters).",
        examples=["Ada"],
    )
    last_name: str = Field(
        min_length=1,
        max_length=100,
        description="Person's family name (1-100 characters).",
        examples=["Lovelace"],
    )
    email: EmailStr = Field(
        description="Valid, unique email address. Duplicate values return HTTP 409.",
        examples=["ada@example.com"],
    )
    phone: str | None = Field(
        default=None,
        max_length=30,
        description="Optional phone number, up to 30 characters.",
        examples=["+1-555-0100"],
    )


class PersonUpdate(BaseModel):
    """Partial update body; omitted fields remain unchanged."""

    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Person's given name (1-100 characters). Omit to keep unchanged.",
        examples=["Ada"],
    )
    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Person's family name (1-100 characters). Omit to keep unchanged.",
        examples=["Lovelace"],
    )
    email: EmailStr | None = Field(
        default=None,
        description="Valid, unique email address. Omit to keep unchanged.",
        examples=["ada@example.com"],
    )
    phone: str | None = Field(
        default=None,
        max_length=30,
        description="Optional phone number, up to 30 characters. Omit to keep unchanged; null clears it.",
        examples=["+1-555-0100"],
    )

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        """Allow null only for phone; required person fields cannot be cleared."""
        for field in ("first_name", "last_name", "email"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PersonResponse(PersonCreate):
    """Person fields returned by the API, including the assigned ID."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "email": "ada@example.com",
                    "phone": "+1-555-0100",
                }
            ]
        },
    )

    id: int = Field(
        description="Stable database identifier used in person resource URLs.",
        examples=[1],
    )
