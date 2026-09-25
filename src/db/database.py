import os
from collections.abc import Generator
from typing import Any

from sqlalchemy import JSON, Column, Engine
from sqlmodel import Field, Session, SQLModel, create_engine


DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Vehicle catalog stores data in PostgreSQL; "
        "provide e.g. postgresql+psycopg2://user:password@localhost:5432/vehicle_sales"
    )


engine: Engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    pool_recycle=300,
)


def create_db_and_tables() -> None:
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Get database session."""
    with Session(engine) as session:
        yield session


def get_session_sync() -> Session:
    """Get synchronous database session."""
    return Session(engine)


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
