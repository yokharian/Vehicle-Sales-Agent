"""
LangChain tool for deterministic vehicle catalog search over PostgreSQL.

structured filters with
fuzzy make/model matching, sorting, result limiting, and controlled errors
that never leak database credentials.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from db.database import Vehicle, get_session_sync
from db.vehicle_dao import fuzzy_match_make, fuzzy_match_model, search_vehicles


logger = logging.getLogger(__name__)

DEFAULT_MAX_RESULTS = 5
MAX_RESULTS_CAP = 20

_SORT_KEYS = {
    "price_asc": lambda vehicle: vehicle.price,
    "price_desc": lambda vehicle: vehicle.price,
    "year_desc": lambda vehicle: vehicle.year,
    "km_asc": lambda vehicle: vehicle.km,
    "model_asc": lambda vehicle: vehicle.model,
}
_REVERSE_SORT = {"price_desc", "year_desc"}


class CatalogSearchDatabaseError(RuntimeError):
    """Raised when the catalog database fails, without leaking DSNs."""


def fuzzy_search_make(make_input: str) -> str | None:
    """Resolve a user-provided make against known catalog values."""
    try:
        return fuzzy_match_make(make_input)
    except SQLAlchemyError as exc:
        logger.error("Fuzzy match failed: %s", type(exc).__name__)
        raise CatalogSearchDatabaseError("Vehicle catalog is temporarily unavailable.") from exc


def fuzzy_search_model(model_input: str, make: str | None = None) -> str | None:
    """Resolve a user-provided model within a make (or across the catalog)."""
    try:
        return fuzzy_match_model(model_input, make)
    except SQLAlchemyError as exc:
        logger.error("Fuzzy match failed: %s", type(exc).__name__)
        raise CatalogSearchDatabaseError("Vehicle catalog is temporarily unavailable.") from exc


def _features_as_names(vehicle: Vehicle) -> list[str]:
    features = vehicle.features if isinstance(vehicle.features, dict) else {}
    return sorted(name for name, enabled in features.items() if enabled)


def _filter_by_features(candidates: list[Vehicle], features: list[str] | None) -> list[Vehicle]:
    """Keep vehicles that have every requested feature enabled."""
    if not features:
        return candidates
    return [
        vehicle
        for vehicle in candidates
        if isinstance(vehicle.features, dict)
        and all(vehicle.features.get(feature, False) for feature in features)
    ]


class VehiclePreferences(BaseModel):
    """Input schema for vehicle search preferences."""

    budget_min: float | None = Field(default=None, description="Minimum budget in USD", ge=0)
    budget_max: float | None = Field(default=None, description="Maximum budget in USD", ge=0)
    make: str | None = Field(
        default=None,
        description="Preferred vehicle make (supports typos and fuzzy matching)",
    )
    model: str | None = Field(
        default=None,
        description="Preferred vehicle model (supports typos and fuzzy matching)",
    )
    km_max: int | None = Field(default=None, description="Maximum kilometers/mileage", ge=0)
    features: list[str] | None = Field(
        default=None,
        description="Required features (e.g., ['bluetooth', 'car_play'])",
    )
    sort_by: str | None = Field(
        default=None,
        description=(
            "Sort results by: 'price_asc', 'price_desc', 'year_desc', 'km_asc', 'model_asc'"
        ),
    )
    max_results: int | None = Field(
        default=DEFAULT_MAX_RESULTS,
        description=f"Maximum number of results to return (1-{MAX_RESULTS_CAP})",
        ge=1,
        le=MAX_RESULTS_CAP,
    )


class VehicleResult(BaseModel):
    """Structured vehicle data returned to the agent."""

    stock_id: int = Field(description="Unique vehicle stock ID")
    make: str = Field(description="Vehicle make")
    model: str = Field(description="Vehicle model")
    year: int = Field(description="Model year")
    version: str | None = Field(description="Vehicle version/trim")
    price: float = Field(description="Price in USD")
    km: int = Field(description="Mileage in kilometers")
    features: list[str] = Field(description="Names of available features")


@tool(
    "catalog_search",
    description="""Search the vehicle catalog with structured filters and fuzzy matching.

This tool can find vehicles based on:
- Budget range (budget_min, budget_max)
- Make and model with typo tolerance (make, model)
- Maximum mileage (km_max)
- Required features (features)
- Sorting preferences (sort_by)

Returns up to 20 vehicles.""",
    args_schema=VehiclePreferences,
    error_on_invalid_docstring=False,
    return_direct=False,
    parse_docstring=True,
    response_format="content_and_artifact",
)
def catalog_search_tool(
    budget_min: float | None = None,
    budget_max: float | None = None,
    make: str | None = None,
    model: str | None = None,
    km_max: int | None = None,
    features: list[str] | None = None,
    sort_by: str | None = None,
    max_results: int | None = None,
) -> tuple[str, list[VehicleResult]]:
    """
    Search the vehicle catalog with structured filters and fuzzy matching.

    Args:
        budget_min: Minimum budget in USD
        budget_max: Maximum budget in USD
        make: Preferred vehicle make (typo-tolerant)
        model: Preferred vehicle model (typo-tolerant, scoped to make)
        km_max: Maximum mileage in kilometers
        features: Required feature names
        sort_by: One of 'price_asc', 'price_desc', 'year_desc', 'km_asc', 'model_asc'
        max_results: Maximum number of results (1-20, default 5)

    Returns:
        (csv_text, structured_results) — records retrieved from the catalog.
    """
    if sort_by is not None and sort_by not in _SORT_KEYS:
        raise ValueError(f"Invalid sort_by {sort_by!r}; expected one of {sorted(_SORT_KEYS)}")
    if budget_min is not None and budget_max is not None and budget_min > budget_max:
        raise ValueError("budget_min must not be greater than budget_max")
    if km_max is not None and km_max < 0:
        raise ValueError("km_max must not be negative")
    limit = (
        DEFAULT_MAX_RESULTS if max_results is None else max(1, min(max_results, MAX_RESULTS_CAP))
    )
    if any(feature is None or not str(feature).strip() for feature in (features or [])):
        raise ValueError("features must contain non-empty feature names")

    matched_make = fuzzy_search_make(make) if make else None
    if make and not matched_make:
        return "", []
    matched_model = fuzzy_search_model(model, matched_make) if model else None
    if model and not matched_model:
        return "", []

    search_params: dict[str, Any] = {}
    if matched_make:
        search_params["make"] = matched_make
    if matched_model:
        search_params["model"] = matched_model
    if budget_min is not None:
        search_params["min_price"] = budget_min
    if budget_max is not None:
        search_params["max_price"] = budget_max
    if km_max is not None:
        search_params["km_max"] = km_max

    with get_session_sync() as session:
        try:
            candidates: list[Vehicle] = search_vehicles(session, **search_params)
        except SQLAlchemyError as exc:
            logger.error("Catalog search failed: %s", type(exc).__name__)
            raise CatalogSearchDatabaseError("Vehicle catalog is temporarily unavailable.") from exc

    if not candidates:
        return "", []

    filtered_candidates = _filter_by_features(candidates, features)

    if not filtered_candidates:
        return "", []

    sort_key = _SORT_KEYS.get(sort_by or "model_asc")
    filtered_candidates.sort(key=sort_key, reverse=(sort_by or "model_asc") in _REVERSE_SORT)

    results: list[VehicleResult] = [
        VehicleResult(
            stock_id=vehicle.stock_id,
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            version=vehicle.version,
            price=vehicle.price,
            km=vehicle.km,
            features=_features_as_names(vehicle),
        )
        for vehicle in filtered_candidates[:limit]
    ]

    results_in_text = _parse_vehicle_results(results)

    return results_in_text, results


def _parse_vehicle_results(
    vehicles: list[VehicleResult], exclude: tuple[str, ...] = ("metadata",)
) -> str:
    """Serialize results as CSV text with schema-key headers."""
    headers = list(VehicleResult.model_fields.keys() - list(exclude))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)

    for vehicle_result in vehicles:
        row_dict = vehicle_result.model_dump(exclude=exclude)
        row = []
        for key in headers:
            value = row_dict.get(key)
            if value is None:
                row.append("")
            elif isinstance(value, (dict, list)):
                row.append(json.dumps(value, ensure_ascii=False))
            else:
                row.append(value)
        writer.writerow(row)

    return buffer.getvalue().strip()
