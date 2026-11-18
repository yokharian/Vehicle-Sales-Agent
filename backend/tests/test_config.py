"""
Tests for application configuration.
"""

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
    SupabaseSettings,
    TwilioSettings,
)


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

        vercel_settings = DocumentSearchSettings(embedding_provider="vercel")
        assert vercel_settings.resolved_embedding_model == "openai/text-embedding-3-small"

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

    def test_vercel_api_key_read_from_environment(self, monkeypatch):
        monkeypatch.setenv("AI_GATEWAY_API_KEY", "vg-key")

        settings = DocumentSearchSettings()

        assert settings.vercel_api_key == "vg-key"


class TestDatabaseSettings:
    """Bare Postgres schemes are normalized onto the installed psycopg2 driver."""

    def test_normalizes_postgres_scheme(self):
        settings = DatabaseSettings(**{"DATABASE_URI": "postgres://u:p@host:5432/db"})

        assert settings.database_uri == "postgresql+psycopg2://u:p@host:5432/db"

    def test_postgres_uri_env_name_is_retired(self):
        settings = DatabaseSettings(
            **{
                "POSTGRES_URI": "postgres://ignored:ignored@localhost:1/ignored",
                "DATABASE_URI": "postgresql://u:p@host:5432/db",
            }
        )

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
                "DATABASE_URI": "postgresql://u:p@host:5432/db",
                "PGVECTOR_URI": "postgres://u:p@host:5432/db",
            }
        )

        assert settings.pgvector_uri == "postgresql+psycopg2://u:p@host:5432/db"

    def test_normalized_uri_loads_sqlalchemy_dialect(self):
        settings = DatabaseSettings(**{"DATABASE_URI": "postgres://u:p@host:5432/db"})

        # Raises NoSuchModuleError for the un-normalized `postgres` scheme;
        # building the engine opens no connection.
        assert create_engine(settings.database_uri) is not None


class TestSupabaseDatabaseSettings:
    """Supabase connection variables are the default source of the database URL."""

    @pytest.fixture(autouse=True)
    def _without_legacy_db_env(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URI", raising=False)
        monkeypatch.delenv("PGVECTOR_URI", raising=False)

    def test_non_pooling_url_is_preferred(self):
        settings = DatabaseSettings(
            **{
                "POSTGRES_URL_NON_POOLING": "postgres://u:p@direct:5432/db",
                "POSTGRES_URL": "postgres://u:p@pooler:6543/db",
                "POSTGRES_PRISMA_URL": "postgres://u:p@pooler:6543/db",
            }
        )

        assert settings.database_uri == "postgresql+psycopg2://u:p@direct:5432/db"

    def test_pooled_url_is_used_when_non_pooling_is_absent(self):
        settings = DatabaseSettings(
            **{
                "POSTGRES_URL": "postgres://u:p@pooler:6543/db",
                "POSTGRES_PRISMA_URL": "postgres://u:p@pooler:6543/db",
            }
        )

        assert settings.database_uri == "postgresql+psycopg2://u:p@pooler:6543/db"

    def test_prisma_url_is_the_last_resort(self):
        settings = DatabaseSettings(**{"POSTGRES_PRISMA_URL": "postgres://u:p@pooler:6543/db"})

        assert settings.database_uri == "postgresql+psycopg2://u:p@pooler:6543/db"

    def test_pooler_query_parameters_are_dropped(self):
        settings = DatabaseSettings(
            **{
                "POSTGRES_URL": "postgres://u:p@pooler:6543/db?sslmode=require&pgbouncer=true",
                "POSTGRES_PRISMA_URL": "postgres://u:p@pooler:6543/db?sslmode=require&supa=base-pooler.x",
            }
        )

        assert settings.database_uri == "postgresql+psycopg2://u:p@pooler:6543/db?sslmode=require"

    def test_database_uri_overrides_supabase_variables(self):
        settings = DatabaseSettings(
            **{
                "DATABASE_URI": "postgres://u:p@override:5432/db",
                "POSTGRES_URL_NON_POOLING": "postgres://u:p@direct:5432/db",
            }
        )

        assert settings.database_uri == "postgresql+psycopg2://u:p@override:5432/db"

    def test_blank_database_uri_does_not_shadow_supabase(self):
        settings = DatabaseSettings(
            **{
                "DATABASE_URI": "",
                "POSTGRES_URL_NON_POOLING": "postgres://u:p@direct:5432/db",
            }
        )

        assert settings.database_uri == "postgresql+psycopg2://u:p@direct:5432/db"

    def test_vector_uri_defaults_to_the_relational_uri(self):
        settings = DatabaseSettings(**{"POSTGRES_URL_NON_POOLING": "postgres://u:p@direct:5432/db"})

        assert settings.pgvector_uri == settings.database_uri

    def test_vector_uri_can_point_at_another_database(self):
        settings = DatabaseSettings(
            **{
                "POSTGRES_URL_NON_POOLING": "postgres://u:p@direct:5432/db",
                "PGVECTOR_URI": "postgres://u:p@vectors:5432/other",
            }
        )

        assert settings.pgvector_uri == "postgresql+psycopg2://u:p@vectors:5432/other"

    def test_discrete_fields_are_assembled_into_a_url(self):
        settings = DatabaseSettings(
            **{
                "POSTGRES_HOST": "db.project.supabase.co",
                "POSTGRES_USER": "postgres",
                "POSTGRES_PASSWORD": "p@ss word",
                "POSTGRES_DATABASE": "postgres",
            }
        )

        assert settings.database_uri == (
            "postgresql+psycopg2://postgres:p%40ss%20word@db.project.supabase.co:5432/postgres?sslmode=require"
        )

    def test_discrete_fields_need_a_password(self):
        settings = DatabaseSettings(
            **{"POSTGRES_HOST": "db.project.supabase.co", "POSTGRES_USER": "postgres"}
        )

        assert settings.database_uri is None

    def test_supabase_url_loads_sqlalchemy_dialect(self):
        settings = DatabaseSettings(**{"POSTGRES_URL_NON_POOLING": "postgres://u:p@direct:5432/db"})

        assert create_engine(settings.database_uri) is not None


class TestSupabaseSettings:
    """Supabase project credentials are read from their environment names."""

    def test_reads_project_url_and_keys(self):
        settings = SupabaseSettings(
            **{
                "NEXT_PUBLIC_SUPABASE_URL": "https://project.supabase.co",
                "SUPABASE_ANON_KEY": "anon",
                "SUPABASE_PUBLISHABLE_KEY": "publishable",
                "SUPABASE_SECRET_KEY": "secret",
                "SUPABASE_SERVICE_ROLE_KEY": "service-role",
                "SUPABASE_JWT_SECRET": "jwt",
            }
        )

        assert settings.url == "https://project.supabase.co"
        assert settings.anon_key == "anon"
        assert settings.publishable_key == "publishable"
        assert settings.secret_key == "secret"
        assert settings.service_role_key == "service-role"
        assert settings.jwt_secret == "jwt"

    def test_missing_keys_default_to_none(self, monkeypatch):
        for name in (
            "SUPABASE_ANON_KEY",
            "SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_SECRET_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_JWT_SECRET",
            "NEXT_PUBLIC_SUPABASE_URL",
            "SUPABASE_URL",
        ):
            monkeypatch.delenv(name, raising=False)

        settings = SupabaseSettings()

        assert settings.url is None
        assert settings.anon_key is None
        assert settings.service_role_key is None
        assert settings.jwt_secret is None


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
