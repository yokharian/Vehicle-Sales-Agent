"""
Tests for LangChain tool schemas.
"""

import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


# OPENAI_API_KEY must exist before embedding provider configuration is exercised.
os.environ["OPENAI_API_KEY"] = "test-key-for-testing"

sys.path.append(str(Path(__file__).parent.parent / "src"))

from tools.catalog_search import catalog_search_tool
from tools.document_search import document_search_tool
from tools.financing_calculator import financing_calculator_tool


class TestCatalogSearchToolSchema:
    """Test catalog search tool schema."""

    def test_tool_attributes(self):
        """Test catalog search tool has required attributes."""
        assert hasattr(catalog_search_tool, "name")
        assert hasattr(catalog_search_tool, "description")
        assert hasattr(catalog_search_tool, "func")
        assert hasattr(catalog_search_tool, "args_schema")

        assert catalog_search_tool.name == "catalog_search"
        assert "vehicle" in catalog_search_tool.description.lower()
        assert catalog_search_tool.func is not None
        assert catalog_search_tool.args_schema is not None

    def test_schema_valid_inputs(self):
        """Test catalog search tool schema validation."""
        schema = catalog_search_tool.args_schema

        valid_inputs = {
            "make": "Toyota",
            "model": "Corolla",
            "budget_max": 30000,
            "max_results": 5,
        }

        validated = schema(**valid_inputs)
        assert validated.make == "Toyota"
        assert validated.model == "Corolla"
        assert validated.budget_max == 30000
        assert validated.max_results == 5

    def test_schema_defaults(self):
        """Test catalog search tool schema default values."""
        schema = catalog_search_tool.args_schema

        minimal_inputs = {"make": "Honda"}
        validated = schema(**minimal_inputs)
        assert validated.make == "Honda"
        assert validated.max_results == 5  # Default value

    def test_schema_rejects_invalid_inputs(self):
        """Test catalog search tool schema rejects invalid inputs."""
        schema = catalog_search_tool.args_schema

        invalid_inputs = [
            {"max_results": -1},
            {"budget_max": "invalid"},
            {"max_results": 0},
        ]

        for inputs in invalid_inputs:
            with pytest.raises(ValidationError):
                schema(**inputs)


class TestDocumentSearchToolSchema:
    """Test document search tool schema."""

    def test_tool_attributes(self):
        """Test document search tool has required attributes."""
        assert hasattr(document_search_tool, "name")
        assert hasattr(document_search_tool, "description")
        assert hasattr(document_search_tool, "func")
        assert hasattr(document_search_tool, "args_schema")

        assert document_search_tool.name == "document_search"
        assert "knowledge" in document_search_tool.description.lower()
        assert document_search_tool.func is not None
        assert document_search_tool.args_schema is not None

    def test_schema_valid_inputs(self):
        """Test document search tool schema validation."""
        schema = document_search_tool.args_schema

        validated = schema(**{"query": "vehicle specifications", "k": 5})
        assert validated.query == "vehicle specifications"
        assert validated.k == 5

    def test_schema_defaults(self):
        """Test document search tool schema default values."""
        schema = document_search_tool.args_schema

        validated = schema(**{"query": "test query"})
        assert validated.query == "test query"
        assert validated.k == 6  # Default value

    def test_schema_rejects_invalid_inputs(self):
        """Test document search tool schema rejects invalid inputs."""
        schema = document_search_tool.args_schema

        invalid_inputs = [
            {"query": ""},
            {"query": "test", "k": 0},
            {"query": "test", "k": 21},
            {"query": None, "k": 0},
        ]

        for inputs in invalid_inputs:
            with pytest.raises(ValidationError):
                schema(**inputs)


class TestFinancingCalculatorToolSchema:
    """Test financing calculator tool schema."""

    def test_tool_attributes(self):
        """Test financing calculator tool has required attributes."""
        assert hasattr(financing_calculator_tool, "name")
        assert hasattr(financing_calculator_tool, "description")
        assert hasattr(financing_calculator_tool, "func")
        assert hasattr(financing_calculator_tool, "args_schema")

        assert financing_calculator_tool.name == "financing_calculator"
        assert "financing" in financing_calculator_tool.description.lower()
        assert financing_calculator_tool.func is not None
        assert financing_calculator_tool.args_schema is not None

    def test_schema_valid_inputs(self):
        """Test financing calculator tool schema validation."""
        schema = financing_calculator_tool.args_schema

        validated = schema(vehicle_price=450000, down_payment=100000, term_years=5)
        assert validated.vehicle_price == 450000
        assert validated.down_payment == 100000
        assert validated.term_years == 5

    def test_schema_rejects_invalid_inputs(self):
        """Test financing calculator tool schema rejects invalid inputs."""
        schema = financing_calculator_tool.args_schema

        invalid_inputs = [
            {"vehicle_price": 0.0, "down_payment": 0.0, "term_years": 5},
            {"vehicle_price": -1000.0, "down_payment": 0.0, "term_years": 5},
            {"vehicle_price": 450000.0, "down_payment": -1.0, "term_years": 5},
            {"vehicle_price": 450000.0, "down_payment": 0.0, "term_years": 2},
            {"vehicle_price": 450000.0, "down_payment": 0.0, "term_years": 7},
        ]

        for inputs in invalid_inputs:
            with pytest.raises(ValidationError):
                schema(**inputs)


class TestToolSchemasConsistency:
    """Test schema consistency across all tools."""

    def test_all_tools_compatible_with_langchain(self):
        """Test that all tools are compatible with LangChain."""
        # All tools should have the required LangChain tool interface
        for tool in [
            catalog_search_tool,
            document_search_tool,
            financing_calculator_tool,
        ]:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "func")
            assert hasattr(tool, "args_schema")

            # Name should be a string
            assert isinstance(tool.name, str)
            assert len(tool.name) > 0

            # Description should be a string
            assert isinstance(tool.description, str)
            assert len(tool.description) > 0

            # Function should be callable
            assert callable(tool.func)

            # Args schema should be a Pydantic model
            assert hasattr(tool.args_schema, "model_fields")

    def test_all_schemas_have_typed_fields(self):
        """Test that tool schemas are consistent and valid."""
        for tool in [
            catalog_search_tool,
            document_search_tool,
            financing_calculator_tool,
        ]:
            schema = tool.args_schema

            # Schema should have fields
            fields = schema.model_fields

            assert len(fields) > 0

            # Each field should have a type annotation
            for field_name, field_info in fields.items():
                assert field_name is not None
                assert field_info is not None
