"""
Data access layer for vehicle operations.
"""

from typing import List, Optional

from sqlalchemy import case, distinct, func, or_
from sqlmodel import Session
from sqlmodel import select

from .database import Vehicle, get_session_sync


FUZZY_MATCH_THRESHOLD = 60


def get_makes(limit: int = 5) -> List[str]:
    """
    Get distinct vehicle makes from the database.

    Args:
        limit: Maximum number of makes to return

    Returns:
        List of unique vehicle makes
    """
    with get_session_sync() as session:
        stmt = select(distinct(Vehicle.make)).limit(limit)
        results = session.exec(stmt).all()
        return list(results)


def get_models(limit: int = 5) -> List[str]:
    """
    Get distinct vehicle models from the database.

    Args:
        limit: Maximum number of models to return

    Returns:
        List of unique vehicle models
    """
    with get_session_sync() as session:
        stmt = select(distinct(Vehicle.model)).limit(limit)
        results = session.exec(stmt).all()
        return list(results)


def get_models_by_make(make: str, limit: int = 5) -> List[str]:
    """
    Get distinct vehicle models for a specific make.

    Args:
        make: Vehicle make to filter by
        limit: Maximum number of models to return

    Returns:
        List of unique vehicle models for the specified make
    """
    with get_session_sync() as session:
        stmt = select(distinct(Vehicle.model)).where(Vehicle.make == make).limit(limit)
        results = session.exec(stmt).all()
        return list(results)


def fuzzy_match_make(make_input: str) -> str | None:
    """
    Find the catalog make fuzzy-matching the user input.

    Scoring runs entirely in PostgreSQL (fuzzystrmatch): candidates are the
    distinct catalog makes; containment between candidate and input scores
    90, otherwise the score is the normalized Levenshtein similarity
    percentage. The best candidate at or above FUZZY_MATCH_THRESHOLD wins,
    with alphabetical tie-break.

    Args:
        make_input: User input for the vehicle make

    Returns:
        Canonical catalog make, or None when the input is empty, exceeds
        PostgreSQL's 255-byte levenshtein limit, or no candidate reaches
        FUZZY_MATCH_THRESHOLD
    """
    query = make_input.strip().lower()
    if not query or len(query.encode("utf-8")) > 255:
        return None

    inner = select(distinct(Vehicle.make).label("make")).subquery()
    cand = func.lower(inner.c.make)
    max_len = func.greatest(func.length(cand), len(query))
    dist = func.levenshtein(cand, query)
    contained = or_(func.strpos(cand, query) > 0, func.strpos(query, cand) > 0)
    score = case((contained, 90), else_=(max_len - dist) * 100 / max_len)

    with get_session_sync() as session:
        stmt = (
            select(inner.c.make)
            .where(score >= FUZZY_MATCH_THRESHOLD)
            .order_by(score.desc(), cand.asc())
            .limit(1)
        )
        return session.exec(stmt).first()


def fuzzy_match_model(model_input: str, make: str | None = None) -> str | None:
    """
    Find the catalog model fuzzy-matching the user input.

    Scoring runs entirely in PostgreSQL (fuzzystrmatch), as in
    fuzzy_match_make(). When make is given, candidates are restricted to
    models of that make (scoping is case-insensitive).

    Args:
        model_input: User input for the vehicle model
        make: Optional make to scope the candidate models (case-insensitive)

    Returns:
        Canonical catalog model, or None when the input is empty, exceeds
        PostgreSQL's 255-byte levenshtein limit, or no candidate reaches
        FUZZY_MATCH_THRESHOLD
    """
    query = model_input.strip().lower()
    if not query or len(query.encode("utf-8")) > 255:
        return None

    inner_stmt = select(distinct(Vehicle.model).label("model"))
    if make is not None:
        inner_stmt = inner_stmt.where(func.lower(Vehicle.make) == make.strip().lower())
    inner = inner_stmt.subquery()
    cand = func.lower(inner.c.model)
    max_len = func.greatest(func.length(cand), len(query))
    dist = func.levenshtein(cand, query)
    contained = or_(func.strpos(cand, query) > 0, func.strpos(query, cand) > 0)
    score = case((contained, 90), else_=(max_len - dist) * 100 / max_len)

    with get_session_sync() as session:
        stmt = (
            select(inner.c.model)
            .where(score >= FUZZY_MATCH_THRESHOLD)
            .order_by(score.desc(), cand.asc())
            .limit(1)
        )
        return session.exec(stmt).first()


def get_vehicle_by_id(db: Session, stock_id: int) -> Optional[Vehicle]:
    """
    Get vehicle by stock_id.

    Args:
        db: Database session
        stock_id: Vehicle stock ID

    Returns:
        Vehicle object or None if not found
    """
    statement = select(Vehicle).where(Vehicle.stock_id == stock_id)
    vehicle = db.exec(statement).first()
    return vehicle


def get_vehicles_by_make_model(db: Session, make: str, model: str) -> List[Vehicle]:
    """
    Get vehicles by make and model.

    Args:
        db: Database session
        make: Vehicle make
        model: Vehicle model

    Returns:
        List of Vehicle objects
    """
    statement = select(Vehicle).where(Vehicle.make == make.lower(), Vehicle.model == model.lower())
    return list(db.exec(statement))


def get_vehicles_by_price_range(db: Session, min_price: float, max_price: float) -> List[Vehicle]:
    """
    Get vehicles within a price range.

    Args:
        db: Database session
        min_price: Minimum price
        max_price: Maximum price

    Returns:
        List of Vehicle objects
    """
    statement = select(Vehicle).where(Vehicle.price >= min_price, Vehicle.price <= max_price)
    return list(db.exec(statement))


def get_vehicles_by_year_range(db: Session, min_year: int, max_year: int) -> List[Vehicle]:
    """
    Get vehicles within a year range.

    Args:
        db: Database session
        min_year: Minimum year
        max_year: Maximum year

    Returns:
        List of Vehicle objects
    """
    statement = select(Vehicle).where(Vehicle.year >= min_year, Vehicle.year <= max_year)
    return list(db.exec(statement))


def search_vehicles(
    db: Session,
    make: Optional[str] = None,
    model: Optional[str] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    km_max: Optional[int] = None,
    features: Optional[dict] = None,
) -> List[Vehicle]:
    """
    Search vehicles with multiple criteria.

    Args:
        db: Database session
        make: Vehicle make filter
        model: Vehicle model filter
        min_year: Minimum year filter
        max_year: Maximum year filter
        min_price: Minimum price filter
        max_price: Maximum price filter
        km_max: Maximum km filter
        features: Features filter dictionary

    Returns:
        List of Vehicle objects matching criteria
    """
    statement = select(Vehicle)

    if make:
        statement = statement.where(Vehicle.make == make)

    if model:
        statement = statement.where(Vehicle.model == model)

    if min_year:
        statement = statement.where(Vehicle.year >= min_year)

    if max_year:
        statement = statement.where(Vehicle.year <= max_year)

    if min_price:
        statement = statement.where(Vehicle.price >= min_price)

    if max_price:
        statement = statement.where(Vehicle.price <= max_price)

    if km_max:
        statement = statement.where(Vehicle.km <= km_max)

    # Note: Feature filtering would require more complex JSON queries
    # This is a simplified version

    return list(db.exec(statement))
