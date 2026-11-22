import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


# Set test environment variables before any imports
os.environ["DOCUMENT_EMBEDDING_API_KEY"] = "test-key-for-testing"

sys.path.append(str(Path(__file__).parent.parent / "src"))

from tools.catalog_search import (
    VehiclePreferences,
    VehicleResult,
)


class TestVehiclePreferences:
    def test_valid_preferences(self):
        prefs = VehiclePreferences(
            budget_min=10000,
            budget_max=25000,
            make="toyota",
            model="corolla",
            km_max=50000,
            features=["bluetooth", "air_conditioning"],
        )

        assert prefs.budget_min == 10000
        assert prefs.budget_max == 25000
        assert prefs.make == "toyota"
        assert prefs.model == "corolla"
        assert prefs.km_max == 50000
        assert prefs.features == ["bluetooth", "air_conditioning"]
        assert prefs.sort_by is None
        assert prefs.max_results == 5

    def test_minimal_preferences(self):
        prefs = VehiclePreferences()

        assert prefs.budget_min is None
        assert prefs.budget_max is None
        assert prefs.make is None
        assert prefs.model is None
        assert prefs.km_max is None
        assert prefs.features is None
        assert prefs.sort_by is None
        assert prefs.max_results == 5

    def test_invalid_budget(self):
        with pytest.raises((ValueError, ValidationError)):
            VehiclePreferences(budget_min=-1000)

        with pytest.raises((ValueError, ValidationError)):
            VehiclePreferences(budget_max=-5000)

    def test_invalid_max_results(self):
        with pytest.raises((ValueError, ValidationError)):
            VehiclePreferences(max_results=0)

        with pytest.raises((ValueError, ValidationError)):
            VehiclePreferences(max_results=25)


class TestVehicleResult:
    def test_valid_result(self):
        result = VehicleResult(
            stock_id=1001,
            make="toyota",
            model="corolla",
            year=2020,
            version="le",
            price=18500.00,
            km=25000,
            features=["bluetooth", "air_conditioning"],
        )

        assert result.stock_id == 1001
        assert result.make == "toyota"
        assert result.model == "corolla"
        assert result.year == 2020
        assert result.version == "le"
        assert result.price == 18500.00
        assert result.km == 25000
        assert result.features == ["bluetooth", "air_conditioning"]

    def test_result_with_none_version(self):
        result = VehicleResult(
            stock_id=1002,
            make="honda",
            model="civic",
            year=2019,
            version=None,
            price=20000.00,
            km=30000,
            features=["bluetooth"],
        )

        assert result.version is None


class TestCatalogSearchTool:
    def test_catalog_search_tool_creation(self):
        from tools.catalog_search import catalog_search_tool

        assert catalog_search_tool.name == "catalog_search"
        assert "Search the vehicle catalog" in catalog_search_tool.description
        assert catalog_search_tool.args_schema is not None

    def test_vehicle_preferences_validation(self):
        from tools.catalog_search import VehiclePreferences

        prefs = VehiclePreferences(make="Toyota", budget_max=50000, max_results=5)
        assert prefs.make == "Toyota"
        assert prefs.budget_max == 50000
        assert prefs.max_results == 5

        prefs_none = VehiclePreferences()
        assert prefs_none.make is None
        assert prefs_none.budget_max is None
        assert prefs_none.max_results == 5  # Default value

    def test_catalog_search_comprehensive_scenarios(self):
        from tools.catalog_search import catalog_search_tool

        _, artifact = catalog_search_tool.func(
            make="toyota", budget_max=20000, max_results=3
        )
        assert [vehicle.stock_id for vehicle in artifact] == [1001]

        _, artifact = catalog_search_tool.func(
            make="hond", model="civic", max_results=2
        )
        assert [vehicle.stock_id for vehicle in artifact] == [1002]

        _, artifact = catalog_search_tool.func(
            features=["bluetooth", "air_conditioning"], max_results=2
        )
        assert sorted(vehicle.stock_id for vehicle in artifact) == [1001, 1002]

        _, artifact = catalog_search_tool.func(
            make="Toyta", budget_max=50000, km_max=50000, max_results=3
        )
        assert sorted(vehicle.stock_id for vehicle in artifact) == [1001, 1003]

        _, artifact = catalog_search_tool.func(
            budget_min=200000, budget_max=400000, max_results=5
        )
        assert artifact == []

    def test_catalog_search_tool_integration(self):
        from tools.catalog_search import catalog_search_tool

        content, artifact = catalog_search_tool.func(
            make="Toyta",
            budget_max=50000,
            max_results=3,
        )

        assert isinstance(artifact, list)
        assert artifact
        assert all(vehicle.make == "toyota" for vehicle in artifact)
        assert "stock_id" in content

    def test_catalog_search_edge_cases(self):
        from tools.catalog_search import catalog_search_tool

        with pytest.raises(ValueError, match="budget_min"):
            catalog_search_tool.func(budget_min=50000, budget_max=20000, max_results=3)

        _, artifact = catalog_search_tool.func(make="Toy@ta", max_results=3)

        assert artifact
        assert all(vehicle.make == "toyota" for vehicle in artifact)

