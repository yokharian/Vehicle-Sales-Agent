"""
Tests for CSV ingestion functionality.
"""

import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from sqlmodel import func, select


sys.path.append(str(Path(__file__).parent.parent / "src"))
sys.path.append(str(Path(__file__).parent.parent))

import db.database as db_module
from scripts.ingest_csv import ingest_csv, parse_boolean, process_vehicle_row


class TestParseBoolean:
    """Test cases for parse_boolean function."""

    def test_truthy_values(self):
        """Test truthy string values."""
        assert parse_boolean("Sí") == True
        assert parse_boolean("si") == True
        assert parse_boolean("yes") == True
        assert parse_boolean("true") == True
        assert parse_boolean("1") == True
        assert parse_boolean("verdadero") == True
        assert parse_boolean("v") == True

    def test_falsy_values(self):
        """Test falsy string values."""
        assert parse_boolean("No") == False
        assert parse_boolean("no") == False
        assert parse_boolean("false") == False
        assert parse_boolean("0") == False
        assert parse_boolean("") == False
        assert parse_boolean("   ") == False

    def test_boolean_input(self):
        """Test boolean input."""
        assert parse_boolean(True) == True
        assert parse_boolean(False) == False

    def test_none_input(self):
        """Test None input."""
        assert parse_boolean(None) == False


class TestCSVIngestion:
    """Test cases for CSV ingestion functionality."""

    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data for testing."""
        return {
            "stock_id": [1001, 1002, 1003],
            "make": ["Toyota", "Honda", "Ford"],
            "model": ["Corolla", "Civic", "Focus"],
            "year": [2020, 2019, 2021],
            "version": ["LE", "LX", "SE"],
            "km": [25000, 32000, 18000],
            "price": [18500.00, 16800.00, 19500.00],
            "bluetooth": ["Sí", "Sí", "No"],
            "car_play": ["Sí", "No", "Sí"],
            "largo": [4.6, 4.5, 4.4],
            "ancho": [1.8, 1.8, 1.8],
            "altura": [1.5, 1.5, 1.4],
        }

    def test_process_vehicle_row(self, sample_csv_data):
        """Test processing a single CSV row."""
        df = pd.DataFrame(sample_csv_data)
        row = df.iloc[0]

        result = process_vehicle_row(row, row_number=2)

        assert result["stock_id"] == 1001
        assert result["make"] == "toyota"
        assert result["model"] == "corolla"
        assert result["year"] == 2020
        assert result["version"] == "le"
        assert result["km"] == 25000
        assert result["price"] == 18500.00
        assert result["features"]["bluetooth"] == True
        assert result["features"]["car_play"] == True
        assert result["largo"] == 4.6
        assert result["ancho"] == 1.8
        assert result["altura"] == 1.5

    def test_process_vehicle_row_with_missing_data(self):
        """Test processing row with missing optional data."""
        row_data = {
            "stock_id": 1004,
            "make": "Chevrolet",
            "model": "Cruze",
            "year": 2018,
            "km": 45000,
            "price": 14200.00,
            "bluetooth": "No",
        }

        row = pd.Series(row_data)
        result = process_vehicle_row(row, row_number=2)

        assert result["stock_id"] == 1004
        assert result["make"] == "chevrolet"
        assert result["model"] == "cruze"
        assert result["version"] is None
        assert result["features"]["bluetooth"] == False
        assert result["largo"] is None
        assert result["ancho"] is None
        assert result["altura"] is None

    def test_process_vehicle_row_with_invalid_data(self):
        """Test that malformed rows are rejected with a descriptive error."""
        row_data = {
            "stock_id": "invalid",
            "make": "Toyota",
            "model": "Corolla",
            "year": "not_a_year",
            "km": "not_a_number",
            "price": "not_a_price",
            "bluetooth": "Sí",
        }

        row = pd.Series(row_data)

        with pytest.raises(ValueError, match="stock_id must be an integer"):
            process_vehicle_row(row, row_number=3)

    def test_process_vehicle_row_with_missing_required_fields(self):
        """Test that missing required text fields are rejected."""
        row = pd.Series(
            {"stock_id": 1001, "make": "", "model": "   ", "year": 2020, "km": 10, "price": 10}
        )

        with pytest.raises(ValueError, match="make must not be empty"):
            process_vehicle_row(row, row_number=2)

    def test_process_vehicle_row_removes_accents(self):
        """Test accent removal for matching."""
        row = pd.Series(
            {
                "stock_id": 1002,
                "make": "  Sáburu  ",
                "model": "Impréza",
                "year": 2020,
                "km": 1,
                "price": 1,
            }
        )
        result = process_vehicle_row(row, row_number=2)

        assert result["make"] == "saburu"
        assert result["model"] == "impreza"

    def test_process_vehicle_row_rejects_non_numeric_price(self):
        """Test that non-numeric prices are rejected."""
        row = pd.Series(
            {
                "stock_id": 1003,
                "make": "Toyota",
                "model": "Corolla",
                "year": 2020,
                "km": 10,
                "price": "free",
            }
        )
        with pytest.raises(ValueError, match="price must be numeric"):
            process_vehicle_row(row, row_number=2)

    def test_process_vehicle_row_rejects_invalid_year(self):
        """Test that invalid years are rejected."""
        row = pd.Series(
            {
                "stock_id": 1004,
                "make": "Toyota",
                "model": "Corolla",
                "year": "very old",
                "km": 10,
                "price": 10,
            }
        )
        with pytest.raises(ValueError, match="year must be an integer"):
            process_vehicle_row(row, row_number=2)

    def test_create_sample_csv_file(self):
        """Test creating a sample CSV file for testing."""
        sample_data = {
            "stock_id": [1001, 1002],
            "make": ["Toyota", "Honda"],
            "model": ["Corolla", "Civic"],
            "year": [2020, 2019],
            "km": [25000, 32000],
            "price": [18500.00, 16800.00],
            "bluetooth": ["Sí", "No"],
            "car_play": ["Sí", "Sí"],
            "largo": [4.6, 4.5],
            "ancho": [1.8, 1.8],
            "altura": [1.5, 1.5],
        }

        df = pd.DataFrame(sample_data)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)

            # Verify CSV was created correctly
            loaded_df = pd.read_csv(f.name)
            assert len(loaded_df) == 2
            assert loaded_df["stock_id"].iloc[0] == 1001
            assert loaded_df["make"].iloc[0] == "Toyota"

            # Clean up
            Path(f.name).unlink()

    def test_csv_ingestion_workflow(self):
        """Test complete CSV ingestion workflow."""
        # Create sample data that matches the real CSV structure
        sample_data = {
            "stock_id": [1001, 1002, 1003, 1004],
            "make": ["Toyota", "Honda", "Ford", "Chevrolet"],
            "model": ["Corolla", "Civic", "Focus", "Cruze"],
            "year": [2020, 2019, 2021, 2018],
            "version": ["LE", "LX", "SE", None],
            "km": [25000, 32000, 18000, 45000],
            "price": [18500.00, 16800.00, 19500.00, 14200.00],
            "bluetooth": ["Sí", "Sí", "No", "No"],
            "car_play": ["Sí", "No", "Sí", "No"],
            "largo": [4.6, 4.5, 4.4, 4.3],
            "ancho": [1.8, 1.8, 1.8, 1.7],
            "altura": [1.5, 1.5, 1.4, 1.4],
        }

        df = pd.DataFrame(sample_data)
        assert len(df) == 4

        # Test processing each row
        for i, (_, row) in enumerate(df.iterrows(), 1):
            result = process_vehicle_row(row, row_number=i + 1)

            # Verify basic structure
            assert isinstance(result, dict)
            assert "stock_id" in result
            assert "make" in result
            assert "model" in result
            assert "features" in result
            assert isinstance(result["features"], dict)

    def test_boolean_parsing_comprehensive(self):
        """Test boolean parsing with comprehensive test cases."""
        test_values = [
            ("Sí", True),
            ("si", True),
            ("No", False),
            ("no", False),
            ("yes", True),
            ("true", True),
            ("false", False),
            ("1", True),
            ("0", False),
            ("", False),
            (None, False),
            (True, True),
            (False, False),
        ]

        for value, expected in test_values:
            result = parse_boolean(value)
            assert result == expected, (
                f"parse_boolean({value!r}) = {result}, expected {expected}"
            )

    def test_data_validation_comprehensive(self):
        """Test data validation with various data quality scenarios."""
        test_cases = [
            {
                "name": "Valid data",
                "data": {
                    "stock_id": 1001,
                    "make": "Toyota",
                    "model": "Corolla",
                    "year": 2020,
                    "km": 25000,
                    "price": 18500.00,
                    "bluetooth": "Sí",
                    "car_play": "No",
                },
                "should_succeed": True,
            },
            {
                "name": "Missing optional fields",
                "data": {
                    "stock_id": 1002,
                    "make": "Honda",
                    "model": "Civic",
                    "year": 2019,
                    "km": 32000,
                    "price": 16800.00,
                    "bluetooth": "No",
                },
                "should_succeed": True,
            },
            {
                "name": "Invalid data types",
                "data": {
                    "stock_id": "invalid",
                    "make": "Ford",
                    "model": "Focus",
                    "year": "not_a_year",
                    "km": "not_a_number",
                    "price": "not_a_price",
                    "bluetooth": "Sí",
                },
                "should_succeed": False,
            },
            {
                "name": "Edge case values",
                "data": {
                    "stock_id": 0,
                    "make": "",
                    "model": "   ",
                    "year": 1900,
                    "km": -1000,
                    "price": 0.01,
                    "bluetooth": "maybe",
                },
                "should_succeed": False,
            },
        ]

        for test_case in test_cases:
            row = pd.Series(test_case["data"])

            if test_case["should_succeed"]:
                result = process_vehicle_row(row, row_number=2)
                assert isinstance(result, dict)
                assert "stock_id" in result
                assert "make" in result
                assert "model" in result
                assert "features" in result
            else:
                with pytest.raises(ValueError):
                    process_vehicle_row(row, row_number=2)

    def test_csv_ingestion_edge_cases(self):
        """Test CSV ingestion with edge cases."""
        edge_cases = [
            {"name": "Empty DataFrame", "data": pd.DataFrame(), "expected_count": 0},
            {
                "name": "Single row",
                "data": pd.DataFrame(
                    {
                        "stock_id": [1001],
                        "make": ["Toyota"],
                        "model": ["Corolla"],
                        "year": [2020],
                        "km": [25000],
                        "price": [18500.00],
                        "bluetooth": ["Sí"],
                    }
                ),
                "expected_count": 1,
            },
            {
                "name": "All None values",
                "data": pd.DataFrame(
                    {
                        "stock_id": [None],
                        "make": [None],
                        "model": [None],
                        "year": [None],
                        "km": [None],
                        "price": [None],
                        "bluetooth": [None],
                    }
                ),
                "expected_count": 1,
                "expected_error": "stock_id",
            },
        ]

        for case in edge_cases:
            df = case["data"]
            assert len(df) == case["expected_count"]

            if len(df) > 0:
                for row_number, (_, row) in enumerate(df.iterrows(), start=2):
                    if "expected_error" in case:
                        with pytest.raises(ValueError, match=case["expected_error"]):
                            process_vehicle_row(row, row_number=row_number)
                    else:
                        result = process_vehicle_row(row, row_number=row_number)
                        assert isinstance(result, dict)

    def test_csv_ingestion_performance(self):
        """Test CSV ingestion performance with larger datasets."""
        import time

        # Create a larger dataset
        large_data = {
            "stock_id": list(range(1001, 1101)),  # 100 rows
            "make": ["Toyota", "Honda", "Ford", "Chevrolet"] * 25,
            "model": [f"Model{i}" for i in range(100)],
            "year": [2020 + (i % 5) for i in range(100)],
            "km": [10000 + (i * 1000) for i in range(100)],
            "price": [15000 + (i * 100) for i in range(100)],
            "bluetooth": ["Sí" if i % 2 == 0 else "No" for i in range(100)],
        }

        df = pd.DataFrame(large_data)

        start_time = time.time()

        # Process all rows
        results = []
        for row_number, (_, row) in enumerate(df.iterrows(), start=2):
            result = process_vehicle_row(row, row_number=row_number)
            results.append(result)

        end_time = time.time()

        # Should complete within reasonable time (2 seconds for 100 rows)
        assert end_time - start_time < 2.0
        assert len(results) == 100

        # Verify all results have correct structure
        for result in results:
            assert isinstance(result, dict)
            assert "stock_id" in result
            assert "features" in result


class TestCSVIngestionPostgreSQL:
    """PostgreSQL-backed ingestion tests."""

    @pytest.fixture
    def catalog_csv(self, tmp_path):
        """Write a small catalog CSV and return its path."""
        csv_path = tmp_path / "catalog.csv"
        csv_path.write_text(
            "stock_id,make,model,year,version,km,price,bluetooth,car_play\n"
            "2001,Toyota,Corolla,2020,LE,25000,18500.0,Sí,No\n"
            "2002,Honda,Civic,2019,LX,32000,16800.0,Sí,Sí\n"
            "2002,Ford,Focus,2018,SE,45000,14200.0,No,No\n"
        )
        return str(csv_path)

    def _count_vehicles(self, stock_ids: tuple[int, ...] | None = None) -> int:
        statement = select(func.count()).select_from(db_module.Vehicle)
        if stock_ids is not None:
            statement = statement.where(db_module.Vehicle.stock_id.in_(stock_ids))
        with db_module.Session(db_module.engine) as session:
            return session.exec(statement).one()

    def test_ingest_csv_populates_postgresql(self, catalog_csv):
        """The supplied CSV can be ingested into PostgreSQL."""
        ingest_csv(catalog_csv)

        # 3 data rows, 2 unique stock_ids (2002 appears twice → PK upsert).
        assert self._count_vehicles((2001, 2002)) == 2

    def test_repeated_ingestion_does_not_duplicate(self, catalog_csv):
        """Re-ingesting the same catalog must not create duplicates."""
        ingest_csv(catalog_csv)
        count_after_first = self._count_vehicles((2001, 2002))

        ingest_csv(catalog_csv)
        count_after_second = self._count_vehicles((2001, 2002))

        assert count_after_first == count_after_second == 2

    def test_ingestion_skips_malformed_rows_and_reports_them(self, tmp_path, caplog):
        """Malformed rows are reported with source-row information."""
        import logging

        csv_path = tmp_path / "malformed.csv"
        csv_path.write_text(
            "stock_id,make,model,year,km,price\n"
            "2001,Toyota,Corolla,2020,25000,18500.0\n"
            "free,Toyota,Corolla,2020,25000,18500.0\n"
        )

        with caplog.at_level(logging.ERROR, logger="scripts.ingest_csv"):
            ingest_csv(str(csv_path))

        error_messages = [
            record.getMessage() for record in caplog.records if record.levelno == logging.ERROR
        ]
        assert any("row 3" in message and "stock_id" in message for message in error_messages)
        assert self._count_vehicles((2001,)) == 1
