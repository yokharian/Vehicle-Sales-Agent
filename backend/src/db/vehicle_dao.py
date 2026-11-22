from typing import List, Optional

from sqlalchemy import case, distinct, func, or_
from sqlmodel import Session
from sqlmodel import select

from .database import Vehicle, get_session_sync


FUZZY_MATCH_THRESHOLD = 60


def get_makes(limit: int = 5) -> List[str]:
    with get_session_sync() as session:
        stmt = select(distinct(Vehicle.make)).limit(limit)
        results = session.exec(stmt).all()
        return list(results)


def get_models(limit: int = 5) -> List[str]:
    with get_session_sync() as session:
        stmt = select(distinct(Vehicle.model)).limit(limit)
        results = session.exec(stmt).all()
        return list(results)


def get_models_by_make(make: str, limit: int = 5) -> List[str]:
    with get_session_sync() as session:
        stmt = select(distinct(Vehicle.model)).where(Vehicle.make == make).limit(limit)
        results = session.exec(stmt).all()
        return list(results)


def fuzzy_match_make(make_input: str) -> str | None:
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
    statement = select(Vehicle).where(Vehicle.stock_id == stock_id)
    vehicle = db.exec(statement).first()
    return vehicle


def get_vehicles_by_make_model(db: Session, make: str, model: str) -> List[Vehicle]:
    statement = select(Vehicle).where(Vehicle.make == make.lower(), Vehicle.model == model.lower())
    return list(db.exec(statement))


def get_vehicles_by_price_range(db: Session, min_price: float, max_price: float) -> List[Vehicle]:
    statement = select(Vehicle).where(Vehicle.price >= min_price, Vehicle.price <= max_price)
    return list(db.exec(statement))


def get_vehicles_by_year_range(db: Session, min_year: int, max_year: int) -> List[Vehicle]:
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
    statement = select(Vehicle)

    if make is not None:
        statement = statement.where(Vehicle.make == make)

    if model is not None:
        statement = statement.where(Vehicle.model == model)

    if min_year is not None:
        statement = statement.where(Vehicle.year >= min_year)

    if max_year is not None:
        statement = statement.where(Vehicle.year <= max_year)

    if min_price is not None:
        statement = statement.where(Vehicle.price >= min_price)

    if max_price is not None:
        statement = statement.where(Vehicle.price <= max_price)

    if km_max is not None:
        statement = statement.where(Vehicle.km <= km_max)

    return list(db.exec(statement))
