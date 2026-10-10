#!/usr/bin/env python3
"""CSV Ingestion Script for Vehicle Data.

Processes CSV files containing vehicle data and ingests them into the
PostgreSQL catalog (Parse -> Normalize -> Validate -> Batch upsert).
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sqlmodel import Session
from unidecode import unidecode


# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

import db.database as db_module
from db.database import Vehicle, create_db_and_tables


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ingestion_errors.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

FEATURE_COLUMNS = ["bluetooth", "car_play"]


def parse_boolean(value: Any) -> bool:
    """Parse Spanish/English truthy strings to bool."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    str_value = str(value).lower().strip()
    truthy_values = ["sí", "si", "yes", "true", "1", "verdadero", "v"]
    return str_value in truthy_values


def _to_int(value: Any, field: str, row_number: int) -> int:
    try:
        if pd.isna(value):
            raise ValueError("value is required")
        return int(str(value).strip())
    except (ValueError, TypeError) as exc:
        raise ValueError(f"row {row_number}: {field} must be an integer, got {value!r}") from exc


def _to_float(value: Any, field: str, row_number: int) -> float:
    try:
        if pd.isna(value):
            raise ValueError("value is required")
        return float(str(value).strip())
    except (ValueError, TypeError) as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric, got {value!r}") from exc


def _clean_text(value: Any, field: str, row_number: int, required: bool) -> str | None:
    text = "" if value is None or pd.isna(value) else str(value)
    text = unidecode(text).strip().lower()
    if not text:
        if required:
            raise ValueError(f"row {row_number}: {field} must not be empty")
        return None
    return text


def process_vehicle_row(row: pd.Series, row_number: int) -> dict[str, Any]:
    """Normalize and validate one CSV row into Vehicle-ready data."""
    stock_id = _to_int(row.get("stock_id"), "stock_id", row_number)
    year = _to_int(row.get("year"), "year", row_number)
    km = _to_int(row.get("km"), "km", row_number)
    price = _to_float(row.get("price"), "price", row_number)
    make = _clean_text(row.get("make"), "make", row_number, required=True)
    model = _clean_text(row.get("model"), "model", row_number, required=True)
    version = _clean_text(row.get("version"), "version", row_number, required=False)

    features = {
        feature: parse_boolean(row.get(feature)) for feature in FEATURE_COLUMNS if feature in row
    }

    largo_raw = row.get("largo")
    largo = _to_float(largo_raw, "largo", row_number) if not pd.isna(largo_raw) else None
    ancho_raw = row.get("ancho")
    ancho = _to_float(ancho_raw, "ancho", row_number) if not pd.isna(ancho_raw) else None
    altura_raw = row.get("altura")
    altura = _to_float(altura_raw, "altura", row_number) if not pd.isna(altura_raw) else None

    return {
        "stock_id": stock_id,
        "make": make,
        "model": model,
        "year": year,
        "version": version,
        "km": km,
        "price": price,
        "largo": largo,
        "ancho": ancho,
        "altura": altura,
        "features": features,
    }


def ingest_csv(filepath: str, batch_size: int = 500) -> None:
    """Ingest a CSV file into the PostgreSQL catalog. Idempotent via PK upsert."""
    filepath = Path(filepath)

    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        return

    logger.info(f"Starting ingestion of {filepath}")

    try:
        df = pd.read_csv(filepath)
        logger.info(f"Loaded {len(df)} rows from CSV")
        create_db_and_tables()

        processed_count = 0
        error_count = 0

        with Session(db_module.engine) as session:
            for i in range(0, len(df), batch_size):
                batch_df = df.iloc[i : i + batch_size]
                batch_vehicles = []

                for offset, (_, row) in enumerate(batch_df.iterrows(), start=i + 2):
                    try:
                        vehicle_data = process_vehicle_row(row, row_number=offset)
                        batch_vehicles.append(Vehicle(**vehicle_data))
                    except (ValueError, TypeError) as exc:
                        error_count += 1
                        logger.error(str(exc))
                        continue

                for vehicle in batch_vehicles:
                    session.merge(vehicle)

                session.commit()
                processed_count += len(batch_vehicles)

                logger.info(
                    f"Processed batch {i // batch_size + 1}: {len(batch_vehicles)} vehicles"
                )

        logger.info(f"Ingestion completed. Processed: {processed_count}, Errors: {error_count}")

    except Exception as exc:
        logger.error(f"Ingestion failed: {type(exc).__name__}")
        raise


def main():
    """Entrypoint for CLI usage."""
    parser = argparse.ArgumentParser(description="Ingest vehicle CSV data into database")
    parser.add_argument(
        "--file",
        dest="filepath",
        default="data/sample_vehicles.csv",
        help="Path to the vehicle catalog CSV",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for processing")
    parser.add_argument("--create-tables", action="store_true", help="Create database tables")

    args = parser.parse_args()

    if args.create_tables:
        create_db_and_tables()
        logger.info("Database tables created")

    ingest_csv(args.filepath, args.batch_size)


if __name__ == "__main__":
    main()
