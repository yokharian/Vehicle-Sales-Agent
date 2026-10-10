"""
Tests for application configuration.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


sys.path.append(str(Path(__file__).parent.parent / "src"))

from config import AgentSettings, DocumentSearchSettings


class TestDocumentSearchSettings:
    """Test document search settings loading and validation."""

    def test_poc_defaults(self, monkeypatch):
        for name in (
            "DOCUMENT_EMBEDDING_PROVIDER",
            "DOCUMENT_EMBEDDING_MODEL",
            "DOCUMENT_TOP_K",
            "DOCUMENT_BM25_CANDIDATES",
            "DOCUMENT_DENSE_CANDIDATES",
            "DOCUMENT_BM25_WEIGHT",
        ):
            monkeypatch.delenv(name, raising=False)

        settings = DocumentSearchSettings()

        assert settings.embedding_provider == "openai"
        assert settings.embedding_model is None
        assert settings.top_k == 6
        assert settings.bm25_candidates == 6
        assert settings.dense_candidates == 6
        assert settings.bm25_weight == 0.5

    def test_environment_overrides(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_EMBEDDING_PROVIDER", "gemini")
        monkeypatch.setenv("DOCUMENT_EMBEDDING_MODEL", "models/text-embedding-004")
        monkeypatch.setenv("DOCUMENT_TOP_K", "10")
        monkeypatch.setenv("DOCUMENT_BM25_CANDIDATES", "8")
        monkeypatch.setenv("DOCUMENT_DENSE_CANDIDATES", "12")
        monkeypatch.setenv("DOCUMENT_BM25_WEIGHT", "0.7")

        settings = DocumentSearchSettings()

        assert settings.embedding_provider == "gemini"
        assert settings.embedding_model == "models/text-embedding-004"
        assert settings.top_k == 10
        assert settings.bm25_candidates == 8
        assert settings.dense_candidates == 12
        assert settings.bm25_weight == 0.7

    def test_resolved_embedding_model_falls_back_to_provider_default(self, monkeypatch):
        monkeypatch.delenv("DOCUMENT_EMBEDDING_MODEL", raising=False)
        settings = DocumentSearchSettings(embedding_provider="openai")
        assert settings.resolved_embedding_model == "text-embedding-3-small"

        gemini_settings = DocumentSearchSettings(embedding_provider="gemini")
        assert gemini_settings.resolved_embedding_model == "models/text-embedding-004"

    def test_openrouter_provider_uses_openrouter_style_model_default(self, monkeypatch):
        monkeypatch.delenv("DOCUMENT_EMBEDDING_MODEL", raising=False)

        settings = DocumentSearchSettings(embedding_provider="openrouter")

        assert settings.embedding_provider == "openrouter"
        assert settings.resolved_embedding_model == "openai/text-embedding-3-small"

    def test_openrouter_provider_honors_explicit_model_override(self):
        settings = DocumentSearchSettings(
            embedding_provider="openrouter",
            embedding_model="openai/text-embedding-3-large",
        )
        assert settings.resolved_embedding_model == "openai/text-embedding-3-large"

    def test_rejects_unknown_provider(self):
        with pytest.raises(ValidationError):
            DocumentSearchSettings(embedding_provider="cohere")

    def test_openrouter_api_key_read_from_environment(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")

        settings = DocumentSearchSettings()

        assert settings.openrouter_api_key == "or-key"

    def test_openrouter_api_key_defaults_to_none(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        assert DocumentSearchSettings().openrouter_api_key is None


class TestAgentSettings:
    """Test agent chat model settings."""

    def test_prod_default_model(self, monkeypatch):
        monkeypatch.delenv("DEFAULT_MODEL", raising=False)

        settings = AgentSettings()

        assert settings.default_model == "gpt-5.6-luna"

    def test_environment_override(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_MODEL", "openai/gpt-5.6-luna")

        settings = AgentSettings()

        assert settings.default_model == "openai/gpt-5.6-luna"

    def test_resolved_embedding_model_honors_explicit_override(self):
        settings = DocumentSearchSettings(embedding_model="custom-model")
        assert settings.resolved_embedding_model == "custom-model"

    def test_rejects_out_of_range_values(self):
        with pytest.raises(ValidationError):
            DocumentSearchSettings(top_k=0)

        with pytest.raises(ValidationError):
            DocumentSearchSettings(bm25_candidates=-2)

        with pytest.raises(ValidationError):
            DocumentSearchSettings(bm25_weight=1.5)

        with pytest.raises(ValidationError):
            DocumentSearchSettings(bm25_weight=-0.1)

    def test_unrelated_environment_variables_are_ignored(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_UNRELATED", "value")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-testing")

        settings = DocumentSearchSettings()

        assert settings.embedding_provider == "openai"
