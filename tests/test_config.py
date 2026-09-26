"""
Tests for application configuration.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


sys.path.append(str(Path(__file__).parent.parent / "src"))

from config import AgentSettings, DocumentSearchSettings, TwilioSettings


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
        monkeypatch.setenv("DOCUMENT_EMBEDDING_PROVIDER", "openrouter")
        monkeypatch.setenv("DOCUMENT_EMBEDDING_MODEL", "openai/text-embedding-3-large")
        monkeypatch.setenv("DOCUMENT_TOP_K", "10")
        monkeypatch.setenv("DOCUMENT_BM25_CANDIDATES", "8")
        monkeypatch.setenv("DOCUMENT_DENSE_CANDIDATES", "12")
        monkeypatch.setenv("DOCUMENT_BM25_WEIGHT", "0.7")

        settings = DocumentSearchSettings()

        assert settings.embedding_provider == "openrouter"
        assert settings.embedding_model == "openai/text-embedding-3-large"
        assert settings.top_k == 10
        assert settings.bm25_candidates == 8
        assert settings.dense_candidates == 12
        assert settings.bm25_weight == 0.7

    def test_resolved_embedding_model_falls_back_to_provider_default(self, monkeypatch):
        monkeypatch.delenv("DOCUMENT_EMBEDDING_MODEL", raising=False)
        settings = DocumentSearchSettings(embedding_provider="openai")
        assert settings.resolved_embedding_model == "text-embedding-3-small"

        openrouter_settings = DocumentSearchSettings(embedding_provider="openrouter")
        assert openrouter_settings.resolved_embedding_model == "openai/text-embedding-3-small"

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

    def test_rejects_unknown_model_provider(self):
        with pytest.raises(ValidationError):
            AgentSettings(model_provider="cohere")

    def test_debug_read_from_verbose_environment(self, monkeypatch):
        monkeypatch.setenv("VERBOSE", "true")

        assert AgentSettings().debug is True


class TestTwilioSettings:
    """Test Twilio settings loading."""

    def test_reads_twilio_environment_variables(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
        monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+1234567890")

        settings = TwilioSettings()

        assert settings.account_sid == "AC123"
        assert settings.auth_token == "token"
        assert settings.whatsapp_number == "whatsapp:+1234567890"

    def test_defaults_to_none_without_environment(self, monkeypatch):
        for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_NUMBER"):
            monkeypatch.delenv(name, raising=False)

        settings = TwilioSettings()

        assert settings.account_sid is None
        assert settings.auth_token is None
        assert settings.whatsapp_number is None

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
