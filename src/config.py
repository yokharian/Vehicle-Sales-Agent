"""Application configuration via pydantic-settings.

Provider and model selection is configuration-driven: OpenAI, Gemini, and
OpenRouter (OpenAI-compatible) embedding models are declared here alongside
the agent's default chat model, so swapping providers never touches tool code.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

EmbeddingProvider = Literal["openai", "gemini", "openrouter"]

DEFAULT_EMBEDDING_MODELS: dict[str, str] = {
    "openai": "text-embedding-3-small",
    "gemini": "models/text-embedding-004",
    "openrouter": "openai/text-embedding-3-small",
}


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
        description="Embedding provider: 'openai', 'gemini', or 'openrouter'",
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

    default_model: str = Field(
        default="gpt-5.6-luna",
        description="Default chat model used by the agent",
    )
