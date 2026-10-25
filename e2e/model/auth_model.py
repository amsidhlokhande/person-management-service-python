"""Request and response DTOs for token issuance and refresh operations."""

from pydantic import BaseModel, ConfigDict, Field


class TokenRequest(BaseModel):
    """Form credentials accepted by the public token endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "admin",
                    "password": "change-me",
                }
            ]
        }
    )

    username: str = Field(
        description="Username configured by the active profile.",
        examples=["admin"],
    )
    password: str = Field(
        description="Password configured by the active profile.",
        examples=["change-me"],
        json_schema_extra={"format": "password"},
    )


class TokenResponse(BaseModel):
    """OAuth2-compatible token pair returned by login and refresh."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                }
            ]
        }
    )

    access_token: str = Field(description="Short-lived token for protected API requests.")
    refresh_token: str = Field(description="Longer-lived token accepted only by refresh.")
    token_type: str = Field(default="bearer", description="Authorization scheme.")


class RefreshRequest(BaseModel):
    """Refresh-token exchange request body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                }
            ]
        }
    )

    refresh_token: str = Field(
        description="Unexpired refresh token returned by the token endpoint."
    )
