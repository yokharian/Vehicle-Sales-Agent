"""Application configuration via pydantic-settings.

Provider and model selection is configuration-driven: OpenAI and OpenRouter
(OpenAI-compatible) embedding models are declared here alongside the agent's
default chat model, so swapping providers never touches tool code.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

EmbeddingProvider = Literal["openai", "openrouter"]
ChatModelProvider = Literal["openai", "openrouter"]

DEFAULT_EMBEDDING_MODELS: dict[str, str] = {
    "openai": "text-embedding-3-small",
    "openrouter": "openai/text-embedding-3-small",
}


def _normalize_postgres_scheme(uri: str | None) -> str | None:
    """Rewrite the bare `postgres` URL scheme to `postgresql`.

    Providers and platform tooling (Prisma, LangGraph CLI defaults) emit
    `postgres://...` URLs, but SQLAlchemy's dialect is named `postgresql`,
    so passing one through raises `NoSuchModuleError: Can't load plugin:
    sqlalchemy.dialects:postgres`. An explicit `+driver` suffix is preserved.
    """
    if uri is None:
        return None
    scheme, sep, rest = uri.partition("://")
    if not sep:
        return uri
    if scheme == "postgres" or scheme.startswith("postgres+"):
        return "postgresql" + scheme[len("postgres") :] + "://" + rest
    return uri


class DatabaseSettings(BaseSettings):
    """Database connection settings (relational + pgvector vector store).

    Relational reads DATABASE_URI. The vector database reads PGVECTOR_URI
    and defaults to the relational URI when unset (single-database setups).
    Bare `postgres://` schemes are normalized to `postgresql://`.
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
        description="Embedding provider: 'openai' or 'openrouter'",
    )
    embedding_model: str | None = Field(
        default="openai/text-embedding-3-small",
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
        description="Chat model provider: 'openai' or 'openrouter'",
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
