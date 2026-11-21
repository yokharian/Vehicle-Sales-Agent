"""Application configuration via pydantic-settings.

Model selection is provider-agnostic: every LLM endpoint (chat and embeddings,
separately configured) is an OpenAI-compatible API addressed by three fields
- model, api_key and api_url - so swapping providers never touches tool code.
"""

from __future__ import annotations

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_POOLER_ONLY_QUERY_PARAMS = frozenset({"pgbouncer", "supa"})


def _normalize_postgres_scheme(uri: str | None) -> str | None:
    """Rewrite Postgres URLs onto the SQLAlchemy driver this project installs.

    Bare ``postgres://`` is not a SQLAlchemy dialect. Bare ``postgresql://``
    lets SQLAlchemy 2.1 import psycopg (v3), which is not a dependency;
    ``psycopg2-binary`` is. An explicit ``+driver`` suffix is preserved.
    Pooler-only query parameters are removed because libpq rejects them.
    """
    if uri is None:
        return None
    scheme, sep, rest = uri.partition("://")
    if not sep:
        return uri
    if scheme == "postgres" or scheme.startswith("postgres+"):
        scheme = "postgresql" + scheme[len("postgres") :]
    if scheme == "postgresql":
        scheme = "postgresql+psycopg2"
    if "?" in rest:
        base, _, query = rest.partition("?")
        kept = [
            pair
            for pair in query.split("&")
            if pair and pair.split("=", 1)[0].lower() not in _POOLER_ONLY_QUERY_PARAMS
        ]
        rest = f"{base}?{'&'.join(kept)}" if kept else base
    return f"{scheme}://{rest}"


class DatabaseSettings(BaseSettings):
    """Database connection settings (relational + pgvector vector store).

    DATABASE_URI is the relational connection (CRUD, tables); PGVECTOR_URI is
    the pgvector connection and defaults to DATABASE_URI, so a single-database
    setup needs one URL. An empty variable counts as unset, because the
    LangGraph runtime exports DATABASE_URI="" for its in-memory edition.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_uri: str | None = Field(
        default=None,
        validation_alias="DATABASE_URI",
        description="Relational PostgreSQL connection (CRUD, tables)",
    )
    pgvector_uri: str | None = Field(
        default=None,
        validation_alias="PGVECTOR_URI",
        description="pgvector connection; defaults to database_uri when unset",
    )
    db_echo: bool = Field(
        default=False,
        validation_alias="DB_ECHO",
        description="Echo SQL statements emitted by the database engines",
    )

    _normalize_schemes = field_validator("database_uri", "pgvector_uri")(_normalize_postgres_scheme)

    @model_validator(mode="after")
    def _resolve_uris(self) -> DatabaseSettings:
        """Blank URIs count as unset; the vector store defaults to the relational URI."""
        if self.database_uri is not None and not self.database_uri.strip():
            self.database_uri = None
        if self.pgvector_uri is not None and not self.pgvector_uri.strip():
            self.pgvector_uri = None
        self.pgvector_uri = self.pgvector_uri or self.database_uri
        return self


class DocumentSearchSettings(BaseSettings):
    """Configuration for the document search tool and indexing CLI."""

    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model name",
    )
    embedding_api_key: str | None = Field(
        default=None,
        description="API key for the embedding endpoint",
    )
    embedding_api_url: str | None = Field(
        default=None,
        description="OpenAI-compatible base URL; unset uses the OpenAI endpoint",
    )
    top_k: int = Field(default=6, ge=1, description="Final number of retrieved passages")
    bm25_candidates: int = Field(default=6, ge=1, description="BM25 candidate count")
    dense_candidates: int = Field(default=6, ge=1, description="Dense candidate count")
    bm25_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Ensemble weight for BM25; dense weight is its complement",
    )


class AgentSettings(BaseSettings):
    """Agent chat model configuration (OpenAI-compatible)."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = Field(
        default="gpt-5.6-luna",
        description="Chat model name",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for the chat model endpoint",
    )
    api_url: str | None = Field(
        default=None,
        description="OpenAI-compatible base URL; unset uses the OpenAI endpoint",
    )
    debug: bool = Field(
        default=False,
        validation_alias="VERBOSE",
        description="Enable agent debug output",
    )


class CognitoSettings(BaseSettings):
    """Cognito (Amplify Auth) settings used by the LangGraph middleware (src/auth.py).

    Optional: when both `region` and `user_pool_id` are set, requests must
    carry a Cognito access token as `Authorization: Bearer <jwt>`, validated
    against the user pool's JWKS endpoint plus issuer, expiry, token_use and
    the accepted client ids. When unset, the server runs open under a single
    anonymous identity (e.g. local pgvector-only setups).
    """

    model_config = SettingsConfigDict(
        env_prefix="COGNITO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    region: str | None = Field(
        default=None,
        description="AWS region hosting the user pool; unset disables JWT auth (server runs open)",
    )
    user_pool_id: str | None = Field(
        default=None,
        description="Cognito user pool ID; unset disables JWT auth (server runs open)",
    )
    app_client_ids: str | None = Field(
        default=None,
        validation_alias=AliasChoices("COGNITO_APP_CLIENT_IDS", "COGNITO_APP_CLIENT_ID"),
        description=(
            "Comma-separated `client_id` claims accepted in access tokens "
            "(for example the registered and guest app clients); unset skips the check"
        ),
    )

    @property
    def expected_app_client_ids(self) -> frozenset[str]:
        """Accepted `client_id` values; an empty set means accept any client."""
        if not self.app_client_ids:
            return frozenset()
        return frozenset(
            client_id.strip()
            for client_id in self.app_client_ids.split(",")
            if client_id.strip()
        )

    @property
    def enabled(self) -> bool:
        return bool(self.region and self.user_pool_id)

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_uri(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"


class TwilioSettings(BaseSettings):
    """Twilio WhatsApp credentials."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    account_sid: str | None = Field(default=None, validation_alias="TWILIO_ACCOUNT_SID")
    auth_token: str | None = Field(default=None, validation_alias="TWILIO_AUTH_TOKEN")
    whatsapp_number: str | None = Field(default=None, validation_alias="TWILIO_WHATSAPP_NUMBER")


class SentrySettings(BaseSettings):
    """Sentry SDK configuration (error monitoring, tracing, agent tracing).

    The DSN is the only value needed to switch Sentry on; without it the SDK
    stays disabled so local runs and tests never reach the network. Trace
    sampling follows the deployment environment unless overridden: every
    trace outside production, a tenth of them in production.
    """

    model_config = SettingsConfigDict(
        env_prefix="SENTRY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dsn: str | None = Field(
        default=None,
        description="Sentry project DSN; unset keeps the SDK disabled",
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("SENTRY_ENVIRONMENT", "VERCEL_ENV"),
        description="Environment tag attached to events (defaults to VERCEL_ENV)",
    )
    release: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SENTRY_RELEASE", "VERCEL_GIT_COMMIT_SHA"),
        description="Release tag attached to events (defaults to VERCEL_GIT_COMMIT_SHA)",
    )
    traces_sample_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Trace sample rate; None samples by environment",
    )

    @property
    def enabled(self) -> bool:
        return bool(self.dsn)

    @property
    def resolved_traces_sample_rate(self) -> float:
        if self.traces_sample_rate is not None:
            return self.traces_sample_rate
        return 0.1 if self.environment == "production" else 1.0
