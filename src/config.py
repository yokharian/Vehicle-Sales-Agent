"""Application configuration via pydantic-settings.

Provider and model selection is configuration-driven: OpenAI and OpenRouter
(OpenAI-compatible) embedding models are declared here alongside the agent's
default chat model, so swapping providers never touches tool code.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
VERCEL_AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"

# Pooler-only query parameters. libpq rejects unknown connection parameters,
# so they are dropped before the URL reaches SQLAlchemy.
_POOLER_ONLY_QUERY_PARAMS = frozenset({"pgbouncer", "supa"})

EmbeddingProvider = Literal["openai", "openrouter", "vercel"]
ChatModelProvider = Literal["openai", "openrouter", "vercel"]

DEFAULT_EMBEDDING_MODELS: dict[str, str] = {
    "openai": "text-embedding-3-small",
    "openrouter": "openai/text-embedding-3-small",
    "vercel": "openai/text-embedding-3-small",
}


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


def _compose_postgres_uri(
    host: str | None,
    user: str | None,
    password: str | None,
    database: str | None,
) -> str | None:
    """Assemble a Postgres URL from discrete Supabase connection fields."""
    if not host or not user or not password:
        return None
    name = database or "postgres"
    return (
        f"postgres://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}:5432/{name}?sslmode=require"
    )


def _first_configured(*values: str | None) -> str | None:
    """Return the first value that is set and not blank.

    An empty environment variable means "not configured": the LangGraph runtime
    exports DATABASE_URI="" for its in-memory edition, and that must not shadow
    the Supabase variables.
    """
    for value in values:
        if value and value.strip():
            return value
    return None


class DatabaseSettings(BaseSettings):
    """Database connection settings (relational + pgvector vector store).

    Supabase is the source of truth. The connection URL is taken from the first
    configured value among DATABASE_URI, POSTGRES_URL_NON_POOLING,
    POSTGRES_URL and POSTGRES_PRISMA_URL; the non-pooling URL comes before the
    pooled ones because a pooled session multiplexes connections behind
    PgBouncer, which breaks startup DDL (CREATE EXTENSION) and long-lived
    statements. When only the discrete POSTGRES_HOST / POSTGRES_USER /
    POSTGRES_PASSWORD / POSTGRES_DATABASE fields are present, the URL is
    assembled from them.

    An empty variable counts as unset, because the LangGraph runtime exports
    DATABASE_URI="" for its in-memory edition and that must not shadow the
    Supabase variables. DATABASE_URI and PGVECTOR_URI stay supported as
    explicit per-deployment overrides (the self-hosted compose stacks and the
    test harness set them). The vector database defaults to the relational
    URI, so a single-database setup needs one URL.
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
    postgres_url_non_pooling: str | None = Field(
        default=None,
        validation_alias="POSTGRES_URL_NON_POOLING",
        description="Supabase connection URL without transaction pooling",
    )
    postgres_url: str | None = Field(
        default=None,
        validation_alias="POSTGRES_URL",
        description="Supabase connection URL through the transaction pooler",
    )
    postgres_prisma_url: str | None = Field(
        default=None,
        validation_alias="POSTGRES_PRISMA_URL",
        description="Supabase connection URL through the transaction pooler (Prisma form)",
    )
    postgres_host: str | None = Field(
        default=None,
        validation_alias="POSTGRES_HOST",
        description="Supabase Postgres host, used when no connection URL is set",
    )
    postgres_user: str | None = Field(
        default=None,
        validation_alias="POSTGRES_USER",
        description="Supabase Postgres user, used when no connection URL is set",
    )
    postgres_password: str | None = Field(
        default=None,
        validation_alias="POSTGRES_PASSWORD",
        description="Supabase Postgres password, used when no connection URL is set",
    )
    postgres_database: str | None = Field(
        default=None,
        validation_alias="POSTGRES_DATABASE",
        description="Supabase Postgres database name, used when no connection URL is set",
    )
    db_echo: bool = Field(
        default=False,
        validation_alias="DB_ECHO",
        description="Echo SQL statements emitted by the database engines",
    )

    _normalize_schemes = field_validator("database_uri", "pgvector_uri")(_normalize_postgres_scheme)

    @model_validator(mode="after")
    def _apply_composed_uri(self) -> DatabaseSettings:
        resolved = _first_configured(
            self.database_uri,
            self.postgres_url_non_pooling,
            self.postgres_url,
            self.postgres_prisma_url,
        )
        if resolved is None:
            resolved = _compose_postgres_uri(
                self.postgres_host,
                self.postgres_user,
                self.postgres_password,
                self.postgres_database,
            )
        self.database_uri = _normalize_postgres_scheme(resolved)

        vector = _first_configured(self.pgvector_uri)
        self.pgvector_uri = _normalize_postgres_scheme(vector) or self.database_uri
        return self


class SupabaseSettings(BaseSettings):
    """Supabase project credentials.

    Holds the project URL and the API keys Supabase issues for the project.
    The anon/publishable keys are safe to expose to clients; the secret and
    service-role keys are server-only.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_URL"),
        description="Supabase project URL",
    )
    anon_key: str | None = Field(
        default=None,
        validation_alias="SUPABASE_ANON_KEY",
        description="Supabase anon (public) API key",
    )
    publishable_key: str | None = Field(
        default=None,
        validation_alias="SUPABASE_PUBLISHABLE_KEY",
        description="Supabase publishable API key",
    )
    secret_key: str | None = Field(
        default=None,
        validation_alias="SUPABASE_SECRET_KEY",
        description="Supabase secret API key (server-only)",
    )
    service_role_key: str | None = Field(
        default=None,
        validation_alias="SUPABASE_SERVICE_ROLE_KEY",
        description="Supabase service-role API key (server-only, bypasses RLS)",
    )
    jwt_secret: str | None = Field(
        default=None,
        validation_alias="SUPABASE_JWT_SECRET",
        description="Supabase JWT signing secret, used to verify project JWTs",
    )


class DocumentSearchSettings(BaseSettings):
    """Configuration for the document search tool and indexing CLI."""

    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    embedding_provider: EmbeddingProvider = Field(
        default="openai",
        description="Embedding provider: 'openai', 'openrouter' or 'vercel'",
    )
    embedding_model: str | None = Field(
        default=None,
        description="Embedding model override; None uses the provider default",
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias="OPENROUTER_API_KEY",
        description="API key used when embedding_provider is 'openrouter'",
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        description="API key used when embedding_provider is 'openai'",
    )
    vercel_api_key: str | None = Field(
        default=None,
        validation_alias="AI_GATEWAY_API_KEY",
        description="API key used when embedding_provider is 'vercel'",
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

    @property
    def resolved_embedding_model(self) -> str:
        if self.embedding_model is not None:
            return self.embedding_model
        return DEFAULT_EMBEDDING_MODELS[self.embedding_provider]


class AgentSettings(BaseSettings):
    """Agent-layer chat model configuration (OpenRouter-compatible)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_provider: ChatModelProvider = Field(
        default="openrouter",
        description="Chat model provider: 'openai', 'openrouter' or 'vercel'",
    )
    default_model: str = Field(
        default="gpt-5.6-luna",
        description="Default chat model used by the agent",
    )
    debug: bool = Field(
        default=False,
        validation_alias="VERBOSE",
        description="Enable agent debug output",
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
        description="API key used when model_provider is 'openai'",
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias="OPENROUTER_API_KEY",
        description="API key used when model_provider is 'openrouter'",
    )
    vercel_api_key: str | None = Field(
        default=None,
        validation_alias="AI_GATEWAY_API_KEY",
        description="API key used when model_provider is 'vercel'",
    )


class CognitoSettings(BaseSettings):
    """Cognito (Amplify Auth) settings used by the LangGraph middleware (src/auth.py).

    Optional: when both `region` and `user_pool_id` are set, requests must
    carry a Cognito access token as `Authorization: Bearer <jwt>`, validated
    against the user pool's JWKS endpoint plus issuer, expiry, token_use and
    client identity. When unset, the server runs open under a single
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
    app_client_id: str | None = Field(
        default=None,
        description="Expected `client_id` claim of access tokens; unset skips the check",
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
