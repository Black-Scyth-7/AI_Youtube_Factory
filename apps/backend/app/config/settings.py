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
from typing import Annotated, ClassVar, Literal

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
    TypeAdapter,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.__version__ import __version__

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

    # -- LLM framework ----------------------------------------------------
    llm_default_provider: str = Field(
        default="anthropic",
        description="Provider slug used when a request does not specify one.",
    )
    llm_default_model: str = Field(
        default="claude-opus-4-8",
        description="Default Claude model. Never hardcode model names in code.",
    )
    llm_max_tokens: int = Field(default=4096, ge=1)
    # Sampling params: applied only to models that accept them. Opus 4.7/4.8,
    # Sonnet 5, and Fable 5 reject temperature/top_p/top_k (the provider omits
    # them for those models). None means "let the model default".
    llm_temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    llm_top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    llm_top_k: int | None = Field(default=None, ge=0)
    llm_thinking: Literal["adaptive", "off"] = Field(default="adaptive")
    llm_timeout_seconds: float = Field(default=120.0, gt=0)
    llm_max_retries: int = Field(default=3, ge=0)
    llm_streaming_default: bool = Field(default=False)
    llm_system_prompt: str | None = Field(default=None)
    llm_cache_enabled: bool = Field(default=True)
    llm_cache_ttl_seconds: int = Field(default=3600, ge=1)
    llm_rate_limit_rpm: int = Field(default=60, ge=1)
    llm_rate_limit_concurrent: int = Field(default=10, ge=1)
    llm_fallback_model: str | None = Field(default=None)

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

    # S3-compatible (AWS S3, MinIO, Cloudflare R2)
    storage_bucket: str = Field(default="ai-youtube-factory")
    storage_region: str = Field(default="us-east-1")
    storage_endpoint_url: str | None = Field(
        default=None,
        description="Override for non-AWS S3 services (MinIO, R2). None uses AWS.",
    )
    storage_access_key: str = Field(default="", repr=False)
    storage_secret_key: str = Field(default="", repr=False)
    storage_use_ssl: bool = Field(default=True)
    storage_force_path_style: bool = Field(
        default=False,
        description="MinIO needs path-style addressing; AWS and R2 use virtual-host.",
    )

    # Google Cloud Storage
    storage_gcs_project: str | None = Field(default=None)
    storage_gcs_credentials_path: str | None = Field(default=None, repr=False)

    # Azure Blob Storage
    storage_azure_account_url: str | None = Field(default=None)
    storage_azure_container: str = Field(default="ai-youtube-factory")
    storage_azure_connection_string: str | None = Field(default=None, repr=False)

    # -- Video pipeline ---------------------------------------------------
    # Each external capability resolves to a registered provider slug. "mock" is
    # always available and deterministic, so the pipeline runs without keys.
    pipeline_speech_provider: str = Field(default="mock")
    pipeline_render_provider: str = Field(default="mock")
    pipeline_publish_provider: str = Field(default="mock")
    pipeline_analytics_provider: str = Field(default="mock")
    pipeline_default_voice: str = Field(default="default")

    # -- Payments ---------------------------------------------------------
    # "mock" settles every charge in process, so billing runs without an
    # account. A real provider also needs PAYMENT_WEBHOOK_SECRET: callbacks
    # move money, and an unverified one is an unauthenticated request to do so.
    payment_provider: str = Field(default="mock")
    payment_webhook_secret: str = Field(default="")
    payment_currency: str = Field(default="USD", min_length=3, max_length=3)

    # -- Observability ----------------------------------------------------
    # /metrics serves internal counters, which describe traffic shape and
    # failure rates. Reachable from the public internet it is reconnaissance,
    # so a deployment that cannot restrict it at the network layer should set
    # METRICS_TOKEN and scrape with `Authorization: Bearer <token>`.
    metrics_enabled: bool = Field(default=True)
    metrics_path: str = Field(default="/metrics")
    metrics_token: str = Field(default="")

    # Tracing works without any of this; these only control OTLP export, which
    # needs the optional extra: pip install -e ".[otel]"
    otel_enabled: bool = Field(default=False)
    otel_service_name: str = Field(default="ai-youtube-factory-api")
    otel_service_version: str = Field(default=__version__)
    otel_exporter_endpoint: str = Field(default="")
    otel_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)

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

    #: Values shipped in the repository as placeholders. Anyone can read them,
    #: so a deployment still using one can have its tokens forged by anyone.
    PLACEHOLDER_SECRETS: ClassVar[frozenset[str]] = frozenset(
        {"change-me-in-production", "change-me-jwt-secret", "changeme", "secret"}
    )
    #: HS256 keys shorter than the hash output weaken the signature (RFC 7518 3.2).
    MIN_SECRET_LENGTH: ClassVar[int] = 32

    @model_validator(mode="after")
    def _reject_insecure_production_secrets(self) -> Settings:
        """Refuse to start in production with a placeholder or short secret.

        There is an is_production flag but nothing used it, so a deployment that
        forgot to set JWT_SECRET_KEY started happily and signed every token with
        a value published in this repository. Failing to boot is noisy; silently
        accepting forged tokens is not.
        """
        if self.environment is not Environment.PRODUCTION:
            return self

        problems: list[str] = []
        for name in ("secret_key", "jwt_secret_key"):
            value = getattr(self, name)
            env_name = name.upper()
            if value in self.PLACEHOLDER_SECRETS:
                problems.append(f"{env_name} is still the placeholder value")
            elif len(value) < self.MIN_SECRET_LENGTH:
                problems.append(
                    f"{env_name} is {len(value)} characters; "
                    f"at least {self.MIN_SECRET_LENGTH} are required"
                )

        if problems:
            raise ValueError(
                "Insecure configuration for ENVIRONMENT=production: "
                + "; ".join(problems)
                + '. Generate one with: python -c "import secrets; '
                'print(secrets.token_urlsafe(48))"'
            )
        return self

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
