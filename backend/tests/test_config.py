import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine


sys.path.append(str(Path(__file__).parent.parent / "src"))

from config import (
    AgentSettings,
    DatabaseSettings,
    DocumentSearchSettings,
    TwilioSettings,
)


class TestDocumentSearchSettings:
    def test_poc_defaults(self, monkeypatch):
        for name in (
            "DOCUMENT_EMBEDDING_MODEL",
            "DOCUMENT_EMBEDDING_API_KEY",
            "DOCUMENT_EMBEDDING_API_URL",
            "DOCUMENT_TOP_K",
            "DOCUMENT_BM25_CANDIDATES",
            "DOCUMENT_DENSE_CANDIDATES",
            "DOCUMENT_BM25_WEIGHT",
        ):
            monkeypatch.delenv(name, raising=False)

        settings = DocumentSearchSettings()

        assert settings.embedding_model == "text-embedding-3-small"
        assert settings.embedding_api_key is None
        assert settings.embedding_api_url is None
        assert settings.top_k == 6
        assert settings.bm25_candidates == 6
        assert settings.dense_candidates == 6
        assert settings.bm25_weight == 0.5

    def test_environment_overrides(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_EMBEDDING_MODEL", "custom-embedding-model")
        monkeypatch.setenv("DOCUMENT_EMBEDDING_API_KEY", "embedding-key")
        monkeypatch.setenv("DOCUMENT_EMBEDDING_API_URL", "https://gateway.example.com/v1")
        monkeypatch.setenv("DOCUMENT_TOP_K", "10")
        monkeypatch.setenv("DOCUMENT_BM25_CANDIDATES", "8")
        monkeypatch.setenv("DOCUMENT_DENSE_CANDIDATES", "12")
        monkeypatch.setenv("DOCUMENT_BM25_WEIGHT", "0.7")

        settings = DocumentSearchSettings()

        assert settings.embedding_model == "custom-embedding-model"
        assert settings.embedding_api_key == "embedding-key"
        assert settings.embedding_api_url == "https://gateway.example.com/v1"
        assert settings.top_k == 10
        assert settings.bm25_candidates == 8
        assert settings.dense_candidates == 12
        assert settings.bm25_weight == 0.7

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

        settings = DocumentSearchSettings()

        assert settings.embedding_model == "text-embedding-3-small"


class TestDatabaseSettings:
    def test_normalizes_postgres_scheme(self):
        settings = DatabaseSettings(**{"DATABASE_URI": "postgres://u:p@host:5432/db"})

        assert settings.database_uri == "postgresql+psycopg2://u:p@host:5432/db"

    def test_preserves_explicit_driver_suffix(self):
        settings = DatabaseSettings(**{"DATABASE_URI": "postgres+asyncpg://u:p@host:5432/db"})

        assert settings.database_uri == "postgresql+asyncpg://u:p@host:5432/db"

    def test_bare_postgresql_uses_psycopg2(self):
        settings = DatabaseSettings(**{"DATABASE_URI": "postgresql://u:p@host:5432/db"})

        assert settings.database_uri == "postgresql+psycopg2://u:p@host:5432/db"

    def test_normalizes_pgvector_uri(self):
        settings = DatabaseSettings(
            **{
                "DATABASE_URI": "postgres://u:p@host:5432/db",
                "PGVECTOR_URI": "postgres://u:p@host:5432/db",
            }
        )

        assert settings.pgvector_uri == "postgresql+psycopg2://u:p@host:5432/db"

    def test_normalized_uri_loads_sqlalchemy_dialect(self):
        settings = DatabaseSettings(**{"DATABASE_URI": "postgres://u:p@host:5432/db"})

        # Raises NoSuchModuleError for the un-normalized `postgres` scheme;
        # building the engine opens no connection.
        assert create_engine(settings.database_uri) is not None

    def test_vector_uri_defaults_to_the_relational_uri(self, monkeypatch):
        monkeypatch.delenv("PGVECTOR_URI", raising=False)
        settings = DatabaseSettings(**{"DATABASE_URI": "postgres://u:p@direct:5432/db"})

        assert settings.pgvector_uri == settings.database_uri

    def test_vector_uri_can_point_at_another_database(self):
        settings = DatabaseSettings(
            **{
                "DATABASE_URI": "postgres://u:p@direct:5432/db",
                "PGVECTOR_URI": "postgres://u:p@vectors:5432/other",
            }
        )

        assert settings.pgvector_uri == "postgresql+psycopg2://u:p@vectors:5432/other"

    def test_blank_uris_count_as_unset(self):
        settings = DatabaseSettings(**{"DATABASE_URI": "", "PGVECTOR_URI": ""})

        assert settings.database_uri is None
        assert settings.pgvector_uri is None

    def test_missing_uri_is_none(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URI", raising=False)

        assert DatabaseSettings().database_uri is None


class TestAgentSettings:
    def test_prod_default_model(self, monkeypatch):
        monkeypatch.delenv("LLM_MODEL", raising=False)

        settings = AgentSettings()

        assert settings.model == "gpt-5.6-luna"

    def test_environment_overrides(self, monkeypatch):
        monkeypatch.setenv("LLM_MODEL", "openai/gpt-5.6-luna")
        monkeypatch.setenv("LLM_API_KEY", "llm-key")
        monkeypatch.setenv("LLM_API_URL", "https://gateway.example.com/v1")

        settings = AgentSettings()

        assert settings.model == "openai/gpt-5.6-luna"
        assert settings.api_key == "llm-key"
        assert settings.api_url == "https://gateway.example.com/v1"

    def test_api_key_and_url_default_to_none(self, monkeypatch):
        for name in ("LLM_API_KEY", "LLM_API_URL"):
            monkeypatch.delenv(name, raising=False)

        settings = AgentSettings()

        assert settings.api_key is None
        assert settings.api_url is None

    def test_debug_read_from_verbose_environment(self, monkeypatch):
        monkeypatch.setenv("VERBOSE", "true")

        assert AgentSettings().debug is True


class TestTwilioSettings:
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
