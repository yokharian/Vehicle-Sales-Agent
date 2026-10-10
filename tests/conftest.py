"""Session-scoped fixtures for the vehicle sales agent test suite."""

import os
import sys
from pathlib import Path


# Make the application source importable from tests.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# db.database yields its global engine from DATABASE_URL at import time; the
# URL must point somewhere valid until the testcontainer replaces it below.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg2://invalid:invalid@localhost:59999/invalid"
)

# document_search resolves embedding providers lazily; tests still install a
# deterministic fake before any tool call touches the network.
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-testing")

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from sqlalchemy import text as sql_text
from testcontainers.community.postgres import PostgresContainer

import db.database as db_module
from tools import document_search


@pytest.fixture(scope="session", autouse=True)
def _postgres_with_pgvector():
    """Spin up a PostgreSQL container with pgvector for the whole test run."""
    container = PostgresContainer(
        image="pgvector/pgvector:pg16",
        driver="psycopg2",
    )
    container.start()

    url = container.get_connection_url()
    os.environ["DATABASE_URL"] = url

    # Swap the global engine so DAO / tool code talks to the container.
    db_module.engine.dispose()
    db_module.engine = db_module.create_engine(
        url, echo=False, pool_pre_ping=True, pool_recycle=300
    )

    with db_module.engine.connect() as conn:
        conn.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    yield container

    container.stop()


@pytest.fixture(scope="session", autouse=True)
def _seed_catalog_db(_postgres_with_pgvector):
    """Create the vehicle catalog tables and seed test data."""
    db_module.create_db_and_tables()

    vehicles = [
        db_module.Vehicle(
            stock_id=1001,
            make="toyota",
            model="corolla",
            year=2020,
            version="le",
            km=25000,
            price=18500.00,
            features={"bluetooth": True, "car_play": True, "air_conditioning": True},
        ),
        db_module.Vehicle(
            stock_id=1002,
            make="honda",
            model="civic",
            year=2019,
            version="lx",
            km=32000,
            price=16800.00,
            features={"bluetooth": True, "air_conditioning": True},
        ),
        db_module.Vehicle(
            stock_id=1003,
            make="toyota",
            model="camry",
            year=2021,
            version="se",
            km=18000,
            price=22000.00,
            features={"bluetooth": True, "car_play": True},
        ),
        db_module.Vehicle(
            stock_id=1004,
            make="ford",
            model="focus",
            year=2018,
            version="base",
            km=45000,
            price=14200.00,
            features={"bluetooth": False, "car_play": False},
        ),
        db_module.Vehicle(
            stock_id=1005,
            make="bmw",
            model="x5",
            year=2020,
            version="xdrive",
            km=30000,
            price=50000.00,
            features={"bluetooth": True},
        ),
        db_module.Vehicle(
            stock_id=1006,
            make="mercedes benz",
            model="c-class",
            year=2021,
            version="base",
            km=25000,
            price=55000.00,
            features={"bluetooth": True},
        ),
        db_module.Vehicle(
            stock_id=1007,
            make="volkswagen",
            model="jetta",
            year=2019,
            version="se",
            km=40000,
            price=20000.00,
            features={"bluetooth": True},
        ),
    ]

    with db_module.Session(db_module.engine) as session:
        for vehicle in vehicles:
            session.merge(vehicle)
        session.commit()

    yield


@pytest.fixture(scope="session", autouse=True)
def _fake_embeddings_for_document_search(_postgres_with_pgvector):
    """Replace provider-resolved embeddings with deterministic fake embeddings.

    This lets the knowledge-search pipeline exercise pgvector end-to-end
    without calling the OpenAI or Gemini APIs. Tests that monkeypatch
    document_search.resolve_embeddings themselves are unaffected.
    """
    fake_embeddings = DeterministicFakeEmbedding(size=768)
    original_resolver = document_search.resolve_embeddings
    document_search.resolve_embeddings = lambda: fake_embeddings

    yield

    document_search.resolve_embeddings = original_resolver
