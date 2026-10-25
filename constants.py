"""Profile-based application settings loaded from the environment and .env file."""

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DatabaseClientSettings:
    """Connection settings for one named database client in the active profile."""

    name: str
    url: str


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings resolved from the selected profile.

    Environment variables use the ``<PROFILE>_<PROPERTY>`` convention. A profile
    lists named database clients and selects its person-store client, while
    ``SPRING_PROFILES_ACTIVE`` selects the active profile.
    """

    # Normalized active environment; only DEV, UAT, and PROD are supported.
    profile: str
    # All databases enabled for this profile; the person store is selected separately.
    database_clients: tuple[DatabaseClientSettings, ...]
    # Named client used by the person repository for CRUD operations.
    primary_database_client: str
    # Private signing key used for access and refresh JWTs.
    jwt_secret: str
    # Supported HMAC algorithm used to sign and verify JWTs.
    jwt_algorithm: str
    # Access-token expiry, expressed in minutes.
    access_token_minutes: int
    # Refresh-token expiry, expressed in days.
    refresh_token_days: int
    # Single configured account allowed to request tokens.
    auth_username: str
    # Password for that account; never log or return this value.
    auth_password: str
    # Whether the startup lifecycle inserts the development sample record.
    seed_data: bool


def load_settings() -> Settings:
    """Load active-profile properties and validate them before app startup.

    ``SPRING_PROFILES_ACTIVE`` selects the prefix used for all settings. Required
    credentials and every configured database URL must exist for that prefix.
    Production has stricter secret checks, and seeding must be explicitly enabled.
    """
    profile = os.getenv("SPRING_PROFILES_ACTIVE", "DEV").strip().upper()
    if profile not in {"DEV", "UAT", "PROD"}:
        raise ValueError("SPRING_PROFILES_ACTIVE must be one of DEV, UAT, or PROD")

    def required(name: str) -> str:
        """Return a non-empty value for the active profile or fail at startup."""
        value = os.getenv(f"{profile}_{name}")
        if not value:
            raise ValueError(f"Missing required environment variable: {profile}_{name}")
        return value

    # Keep development defaults convenient while rejecting unsupported algorithms.
    secret = required("JWT_SECRET")
    algorithm = os.getenv(f"{profile}_JWT_ALGORITHM", "HS256")
    if algorithm not in {"HS256", "HS384", "HS512"}:
        raise ValueError("JWT algorithm must be one of HS256, HS384, or HS512")

    access_token_minutes = int(os.getenv(f"{profile}_ACCESS_TOKEN_MINUTES", "30"))
    refresh_token_days = int(os.getenv(f"{profile}_REFRESH_TOKEN_DAYS", "7"))
    if access_token_minutes <= 0 or refresh_token_days <= 0:
        raise ValueError("JWT expiration settings must be positive integers")

    auth_password = required("AUTH_PASSWORD")
    client_names = [
        name.strip().lower()
        for name in required("DATABASE_CLIENTS").split(",")
        if name.strip()
    ]
    if not client_names:
        raise ValueError(f"{profile}_DATABASE_CLIENTS must contain at least one client name")
    if len(client_names) != len(set(client_names)):
        raise ValueError(f"{profile}_DATABASE_CLIENTS must not contain duplicate names")
    if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,30}", name) for name in client_names):
        raise ValueError(
            f"{profile}_DATABASE_CLIENTS names must start with a letter and contain "
            "only lowercase letters, digits, and underscores"
        )
    database_clients = tuple(
        DatabaseClientSettings(
            name=name,
            url=required(f"{name.upper()}_DATABASE_URL"),
        )
        for name in client_names
    )
    primary_database_client = os.getenv(
        f"{profile}_PRIMARY_DATABASE_CLIENT", client_names[0]
    ).strip().lower()
    if primary_database_client not in client_names:
        raise ValueError(
            f"{profile}_PRIMARY_DATABASE_CLIENT must name one of "
            f"{profile}_DATABASE_CLIENTS"
        )
    if profile == "PROD":
        # Do not let the sample credentials accidentally become production secrets.
        if secret.startswith("replace-") or len(secret) < 32:
            raise ValueError("Configure a unique production JWT secret of at least 32 characters")
        if auth_password.startswith("change-") or len(auth_password) < 12:
            raise ValueError("Configure a non-placeholder production password of at least 12 characters")

    # Seeding is opt-in except where the DEV .env explicitly enables it.
    seed_value = os.getenv(f"{profile}_SEED_DATA", "false").lower()
    if seed_value not in {"true", "false"}:
        raise ValueError(f"{profile}_SEED_DATA must be true or false")

    # Keep the resolved values in one immutable object for application-wide use.
    return Settings(
        # Store the normalized active profile, not its original casing.
        profile=profile,
        # Resolve a named set so one profile can initialize and monitor several stores.
        database_clients=database_clients,
        primary_database_client=primary_database_client,
        jwt_secret=secret,
        jwt_algorithm=algorithm,
        # Keep expiry values as integers in their documented time units.
        access_token_minutes=access_token_minutes,
        refresh_token_days=refresh_token_days,
        auth_username=required("AUTH_USERNAME"),
        auth_password=auth_password,
        # Convert the validated textual flag into a boolean setting.
        seed_data=seed_value == "true",
    )


settings = load_settings()
