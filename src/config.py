"""Application configuration via pydantic-settings.

Every tunable of the document search stack (embedding provider selection,
retrieval parameters) is declared here so behavior is configuration-driven
and validated at read time instead of scattered across os.getenv calls.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_EMBEDDING_MODELS = {
    "openai": "text-embedding-3-small",
    "gemini": "models/text-embedding-004",
}


class DocumentSearchSettings(BaseSettings):
    """Configuration for the document search tool and indexing CLI."""

    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    embedding_provider: str = Field(
        default="openai", description="Embedding provider: 'openai' or 'gemini'"
    )
    embedding_model: str | None = Field(
        default=None,
        description="Embedding model override; None uses the provider default",
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
