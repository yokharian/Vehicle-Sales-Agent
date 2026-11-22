import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError


sys.path.append(str(Path(__file__).parent.parent / "src"))

from db.vehicle_dao import fuzzy_match_make, fuzzy_match_model
from tools.catalog_search import (
    CatalogSearchDatabaseError,
    catalog_search_tool,
    fuzzy_search_make,
    fuzzy_search_model,
)


class TestFuzzySearch:
    @patch("tools.catalog_search.search_vehicles")
    @patch("tools.catalog_search.fuzzy_match_make")
    def test_catalog_search_with_fuzzy_make(self, mock_fuzzy_match_make, mock_search_vehicles):
        mock_fuzzy_match_make.return_value = "Toyota"

        mock_vehicle = Mock()
        mock_vehicle.stock_id = 1
        mock_vehicle.make = "Toyota"
        mock_vehicle.model = "Camry"
        mock_vehicle.year = 2020
        mock_vehicle.version = "LE"
        mock_vehicle.price = 25000.0
        mock_vehicle.km = 50000
        mock_vehicle.features = {"bluetooth": True}

        mock_search_vehicles.return_value = [mock_vehicle]

        preferences = {
            "make": "Toyta",  # Typo in Toyota
            "budget_max": 30000,
            "max_results": 5,
        }

        content, artifact = catalog_search_tool.func(**preferences)

        assert len(artifact) == 1
        assert artifact[0].make == "Toyota"
        assert artifact[0].model == "Camry"

    @patch("tools.catalog_search.fuzzy_match_make")
    def test_catalog_search_no_fuzzy_match(self, mock_fuzzy_match_make):
        mock_fuzzy_match_make.return_value = None

        preferences = {"make": "Xyz", "budget_max": 30000, "max_results": 5}  # No match

        content, artifact = catalog_search_tool.func(**preferences)

        assert len(artifact) == 0

    @patch("tools.catalog_search.fuzzy_match_make")
    def test_fuzzy_db_error_is_wrapped_without_dsn(self, mock_fuzzy_match_make):
        mock_fuzzy_match_make.side_effect = SQLAlchemyError("postgresql://user:secret@host/db")
        with pytest.raises(CatalogSearchDatabaseError) as excinfo:
            fuzzy_search_make("toyota")
        assert str(excinfo.value) == "Vehicle catalog is temporarily unavailable."
        assert "postgresql://" not in str(excinfo.value)
        assert "secret" not in str(excinfo.value)

    def test_fuzzy_search_comprehensive_scenarios(self):
        resolution_scenarios = [
            ({"make": "Toyta", "budget_max": 500000, "max_results": 3}, "toyota"),
            ({"make": "Hnda", "budget_max": 500000, "max_results": 3}, "honda"),
            (
                {"make": "Toyota", "model": "Camri", "budget_max": 500000, "max_results": 3},
                "toyota",
            ),
            (
                {"make": "Toyta", "model": "Camri", "budget_max": 500000, "max_results": 3},
                "toyota",
            ),
        ]

        for preferences, expected_make in resolution_scenarios:
            _, artifact = catalog_search_tool.func(**preferences)

            assert artifact, f"Expected results for {preferences}"
            assert all(vehicle.make == expected_make for vehicle in artifact)

        _, artifact = catalog_search_tool.func(
            make="XyzBrand", budget_max=500000, max_results=3
        )

        assert artifact == []

    def test_dao_integration_functionality(self):
        from db.vehicle_dao import get_makes, get_models, get_models_by_make

        makes = get_makes(limit=10)
        assert isinstance(makes, list), "get_makes should return a list"
        assert len(makes) > 0, "Should have at least one make"
        for make in makes:
            assert isinstance(make, str), "Each make should be a string"
            assert len(make) > 0, "Make should not be empty"

        models = get_models(limit=10)
        assert isinstance(models, list), "get_models should return a list"
        assert len(models) > 0, "Should have at least one model"
        for model in models:
            assert isinstance(model, str), "Each model should be a string"
            assert len(model) > 0, "Model should not be empty"

        if makes:
            first_make = makes[0]
            models_for_make = get_models_by_make(first_make, limit=5)
            assert isinstance(models_for_make, list), "get_models_by_make should return a list"
            for model in models_for_make:
                assert isinstance(model, str), "Each model should be a string"
                assert len(model) > 0, "Model should not be empty"

    def test_langchain_tool_integration(self):
        from tools.catalog_search import catalog_search_tool

        assert catalog_search_tool.name == "catalog_search"
        assert isinstance(catalog_search_tool.description, str)
        assert len(catalog_search_tool.description) > 0
        assert catalog_search_tool.args_schema is not None
        assert callable(catalog_search_tool.func)

        content, artifact = catalog_search_tool.func(
            make="Toyta",
            budget_max=50000,
            max_results=3,
        )

        assert isinstance(artifact, list)
        assert artifact
        assert all(vehicle.make == "toyota" for vehicle in artifact)
        assert "stock_id" in content

    def test_fuzzy_matching_accuracy(self):
        from tools.catalog_search import fuzzy_search_make

        resolution = {
            "Toyta": "toyota",
            "Hnda": "honda",
            "BM": "bmw",
        }

        for typo, expected in resolution.items():
            assert fuzzy_search_make(typo) == expected

        assert fuzzy_search_make("Mercdes") is None
        assert fuzzy_search_make("VW") is None



class TestFuzzyMatchDao:
    def test_exact_match(self):
        assert fuzzy_match_make("toyota") == "toyota"

    @pytest.mark.parametrize("make_input", ["Toyota", "TOYOTA"])
    def test_case_insensitive_match(self, make_input):
        assert fuzzy_match_make(make_input) == "toyota"

    @pytest.mark.parametrize(
        "make_input, expected",
        [
            ("toyta", "toyota"),
            ("hnda", "honda"),
            ("hond", "honda"),
        ],
    )
    def test_make_typo_match(self, make_input, expected):
        assert fuzzy_match_make(make_input) == expected

    @pytest.mark.parametrize(
        "model_input, make, expected",
        [
            ("camri", "toyota", "camry"),
            ("cvic", None, "civic"),
        ],
    )
    def test_model_typo_match(self, model_input, make, expected):
        assert fuzzy_match_model(model_input, make=make) == expected

    @pytest.mark.parametrize(
        "make_input, expected",
        [
            ("mercedes", "mercedes benz"),
            ("bm", "bmw"),
            ("onda", "honda"),
            ("benz", "mercedes benz"),
        ],
    )
    def test_containment_match(self, make_input, expected):
        assert fuzzy_match_make(make_input) == expected

    def test_sixty_percent_band_match(self):
        # "bmd" -> "bmw" scores 66 (2/3 of the max length): inside the
        # intended 60-69.9 band, accepted only by the new threshold.
        assert fuzzy_match_make("bmd") == "bmw"

    @pytest.mark.parametrize("make_input", ["mercdes", "vw", "xyz"])
    def test_rejected_flip(self, make_input):
        assert fuzzy_match_make(make_input) is None

    @pytest.mark.parametrize("make_input", ["", "   "])
    def test_empty_input(self, make_input):
        assert fuzzy_match_make(make_input) is None

    def test_oversize_ascii_input(self):
        # 256 bytes > PostgreSQL's 255-byte levenshtein argument cap.
        assert fuzzy_match_make("a" * 256) is None

    def test_oversize_unicode_input(self):
        # 100 CJK chars = 300 UTF-8 bytes > the 255-byte cap.
        assert fuzzy_match_make("\u4e00" * 100) is None

    def test_model_scoped_to_make(self):
        assert fuzzy_match_model("corolla", make="honda") is None
