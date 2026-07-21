"""Application configuration.

All runtime configuration is loaded from environment variables and validated on
startup via ``pydantic-settings``. Importing :data:`settings` (or calling
:func:`get_settings`) will raise a :class:`pydantic.ValidationError` if a required
variable is missing or malformed, which fails the application fast rather than at
first use.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
    TypeAdapter,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_POSTGRES_DSN = TypeAdapter(PostgresDsn)
_REDIS_DSN = TypeAdapter(RedisDsn)


class Environment(StrEnum):
    """Deployment environment names."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    """Validated application settings.

    Values are read from the process environment and, when present, a local
    ``.env`` file. Unknown environment variables are ignored so that variables
    intended for sibling services (frontend, worker) do not break the backend.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Core -------------------------------------------------------------
    app_name: str = Field(default="AI YouTube Factory API")
    environment: Environment = Field(default=Environment.LOCAL)
    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_json: bool = Field(
        default=True,
        description="Emit structured JSON logs. Disable for human-readable local logs.",
    )

    # -- HTTP / API -------------------------------------------------------
    api_v1_prefix: str = Field(default="/api/v1")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # -- Datastores -------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_youtube_factory",
        description="Async SQLAlchemy DSN (asyncpg driver).",
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672//")

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        """Ensure the database DSN is a well-formed PostgreSQL URL."""
        _POSTGRES_DSN.validate_python(value)
        return value

    @field_validator("redis_url")
    @classmethod
    def _validate_redis_url(cls, value: str) -> str:
        """Ensure the Redis DSN is well-formed."""
        _REDIS_DSN.validate_python(value)
        return value

    # -- External providers (placeholders — implemented in later phases) --
    anthropic_api_key: str | None = Field(default=None, repr=False)
    youtube_api_key: str | None = Field(default=None, repr=False)
    google_client_id: str | None = Field(default=None, repr=False)
    google_client_secret: str | None = Field(default=None, repr=False)

    # -- Security ---------------------------------------------------------
    secret_key: str = Field(
        default="change-me-in-production",
        min_length=8,
        repr=False,
        description="Base secret for signing. MUST be overridden outside local dev.",
    )

    # -- JWT --------------------------------------------------------------
    jwt_secret_key: str = Field(
        default="change-me-jwt-secret",
        min_length=8,
        repr=False,
        description="Signing key for JWT access tokens.",
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15, ge=1)
    refresh_token_expire_days: int = Field(default=30, ge=1)
    jwt_issuer: str = Field(default="ai-youtube-factory")

    # -- Verification / reset token lifetimes -----------------------------
    email_verification_expire_hours: int = Field(default=24, ge=1)
    password_reset_expire_hours: int = Field(default=2, ge=1)
    invitation_expire_days: int = Field(default=7, ge=1)

    # -- Brute-force / rate limiting --------------------------------------
    login_max_attempts: int = Field(default=5, ge=1)
    login_lockout_seconds: int = Field(default=900, ge=1)
    rate_limit_enabled: bool = Field(default=True)

    # -- Storage ----------------------------------------------------------
    storage_backend: Literal["local", "s3", "minio", "r2", "gcs", "azure"] = Field(
        default="local"
    )
    storage_local_path: str = Field(default="./var/storage")
    storage_public_base_url: str = Field(default="http://localhost:8000/files")

    # -- Web / links ------------------------------------------------------
    frontend_url: str = Field(default="http://localhost:3000")
    cookie_secure: bool = Field(default=False)
    cookie_domain: str | None = Field(default=None)

    # -- Email (SMTP) -----------------------------------------------------
    email_enabled: bool = Field(
        default=False,
        description="When false, emails are logged instead of sent (dev default).",
    )
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)
    smtp_user: str | None = Field(default=None, repr=False)
    smtp_password: str | None = Field(default=None, repr=False)
    smtp_use_tls: bool = Field(default=False)
    email_from: str = Field(default="no-reply@ai-youtube-factory.local")
    email_from_name: str = Field(default="AI YouTube Factory")

    # -- OAuth: Google ----------------------------------------------------
    google_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/google/callback"
    )
    # -- OAuth: GitHub ----------------------------------------------------
    github_client_id: str | None = Field(default=None, repr=False)
    github_client_secret: str | None = Field(default=None, repr=False)
    github_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/github/callback"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow ``CORS_ORIGINS`` to be a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        """True when running in the production environment."""
        return self.environment is Environment.PRODUCTION

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Synchronous DSN (psycopg) for Alembic migrations."""
        return str(self.database_url).replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    """Return the cached, validated settings singleton."""
    return Settings()


settings = get_settings()
