from collections.abc import Generator
from typing import Any

from sqlalchemy import JSON, Column, Engine, text
from sqlmodel import Field, Session, SQLModel, create_engine

from config import DatabaseSettings


DB_SETTINGS = DatabaseSettings()


class MissingDatabaseURIError(RuntimeError):
    """Raised when neither POSTGRES_URI nor DATABASE_URI is configured."""


if DB_SETTINGS.postgres_uri is None:
    raise MissingDatabaseURIError()

engine: Engine = create_engine(
    DB_SETTINGS.postgres_uri,
    echo=DB_SETTINGS.db_echo,
    pool_pre_ping=True,
    pool_recycle=300,
)

pgvector_engine: Engine = create_engine(
    DB_SETTINGS.pgvector_uri or DB_SETTINGS.postgres_uri,
    echo=DB_SETTINGS.db_echo,
    pool_pre_ping=True,
    pool_recycle=300,
)


def create_db_and_tables() -> None:
    """Create database tables."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;"))
        conn.commit()
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Get database session."""
    with Session(engine) as session:
        yield session


def get_session_sync() -> Session:
    """Get synchronous database session."""
    return Session(engine)


def get_pgvector_session_sync() -> Session:
    """Get synchronous session bound to the vector-database engine."""
    return Session(pgvector_engine)


class Vehicle(SQLModel, table=True, extend_existing=True):
    """Vehicle model for storing car inventory data."""

    stock_id: int = Field(primary_key=True, description="Unique stock identifier")
    km: int = Field(description="Kilometers/mileage")
    price: float = Field(description="Vehicle price")
    make: str = Field(description="Vehicle manufacturer")
    model: str = Field(description="Vehicle model")
    year: int = Field(description="Model year")
    version: str | None = Field(default=None, description="Vehicle version/trim")
    largo: float | None = Field(default=None, description="Vehicle length")
    ancho: float | None = Field(default=None, description="Vehicle width")
    altura: float | None = Field(default=None, description="Vehicle height")
    features: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Vehicle features (bluetooth, car_play, etc.)",
    )
