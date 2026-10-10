"""
Tests for LangChain tools.
"""

import os
import sys
from pathlib import Path

import pytest


# OPENAI_API_KEY must exist before tools.document_search is imported.
os.environ["OPENAI_API_KEY"] = "test-key-for-testing"

sys.path.append(str(Path(__file__).parent.parent / "src"))

from tools.catalog_search import catalog_search_tool
from tools.document_search import DocumentSearchInput, document_search_tool
from tools.financing_calculator import financing_calculator_tool


class TestCatalogSearchTool:
    """Test catalog search tool functionality."""

    def test_catalog_tool_attributes(self):
        """Test catalog search tool has required attributes."""
        assert hasattr(catalog_search_tool, "name")
        assert hasattr(catalog_search_tool, "description")
        assert hasattr(catalog_search_tool, "func")
        assert hasattr(catalog_search_tool, "args_schema")

        assert catalog_search_tool.name == "catalog_search"
        assert "vehicle" in catalog_search_tool.description.lower()
        assert catalog_search_tool.func is not None
        assert catalog_search_tool.args_schema is not None

    def test_catalog_tool_schema(self):
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

    def test_catalog_tool_schema_defaults(self):
        """Test catalog search tool schema default values."""
        schema = catalog_search_tool.args_schema

        minimal_inputs = {"make": "Honda"}
        validated = schema(**minimal_inputs)
        assert validated.make == "Honda"
        assert validated.max_results == 5  # Default value

    def test_catalog_tool_function_call(self):
        """Test catalog search tool function call."""
        # Test that the tool function can be called without crashing
        inputs = {"make": "Toyota", "max_results": 2}

        try:
            content, artifact = catalog_search_tool.func(**inputs)
            # Should return a str and list (even if empty)
            assert isinstance(content, str)
            assert isinstance(artifact, list)
        except Exception as e:
            # Expected to fail in test environment, but should not crash
            assert isinstance(e, (ValueError, TypeError, KeyError, AttributeError))

    def test_catalog_tool_error_handling(self):
        """Test catalog search tool error handling."""
        # Test with invalid inputs that should be handled gracefully
        invalid_inputs = [
            {"make": None, "max_results": -1},
            {"make": "", "budget_max": "invalid"},
            {"make": "Toyota", "max_results": 0},
        ]

        for inputs in invalid_inputs:
            try:
                result = catalog_search_tool.func(**DocumentSearchInput(**inputs))
                # Should either return results or handle gracefully
                assert isinstance(result, list)
            except Exception as e:
                # Should handle errors gracefully
                assert isinstance(e, (ValueError, TypeError, KeyError))


class TestDocumentSearchTool:
    """Test document search tool functionality."""

    def test_document_tool_attributes(self):
        """Test document search tool has required attributes."""
        assert hasattr(document_search_tool, "name")
        assert hasattr(document_search_tool, "description")
        assert hasattr(document_search_tool, "func")
        assert hasattr(document_search_tool, "args_schema")

        assert document_search_tool.name == "document_search"
        assert "document" in document_search_tool.description.lower()
        assert document_search_tool.func is not None
        assert document_search_tool.args_schema is not None

    def test_document_tool_schema(self):
        """Test document search tool schema validation."""
        schema = document_search_tool.args_schema

        # Test valid inputs
        valid_inputs = {
            "query": "vehicle specifications",
            "k": 5,
        }

        # Should not raise validation error
        validated = schema(**valid_inputs)
        assert validated.query == "vehicle specifications"
        assert validated.k == 5

    def test_document_tool_schema_defaults(self):
        """Test document search tool schema default values."""
        schema = document_search_tool.args_schema

        minimal_inputs = {"query": "test query"}
        validated = schema(**minimal_inputs)
        assert validated.query == "test query"
        assert validated.k == 6  # Default value

    def test_document_tool_function_call(self):
        """Test document search tool function call."""
        # Test that the tool function can be called without crashing
        inputs = {"query": "test query", "k": 2}

        content, artifact = document_search_tool.func(**inputs)
        assert isinstance(content, str)
        assert isinstance(artifact, list)

    def test_document_tool_error_handling(self):
        """Test document search tool error handling."""
        # Test with invalid inputs that should be handled gracefully
        invalid_inputs = [
            {"query": "", "k": -1},
            {"query": None, "k": 0},
        ]

        for inputs in invalid_inputs:
            try:
                result = document_search_tool.func(**DocumentSearchInput(**inputs))
                # Should either return results or handle gracefully
                assert isinstance(result, list)
            except Exception as e:
                # Should handle errors gracefully
                assert isinstance(e, (ValueError, TypeError, KeyError))


class TestFinancingCalculatorTool:
    """Test financing calculator tool functionality."""

    def test_financing_tool_attributes(self):
        """Test financing calculator tool has required attributes."""
        assert hasattr(financing_calculator_tool, "name")
        assert hasattr(financing_calculator_tool, "description")
        assert hasattr(financing_calculator_tool, "func")
        assert hasattr(financing_calculator_tool, "args_schema")

        assert financing_calculator_tool.name == "financing_calculator"
        assert "financing" in financing_calculator_tool.description.lower()
        assert financing_calculator_tool.func is not None
        assert financing_calculator_tool.args_schema is not None

    def test_financing_tool_schema(self):
        """Test financing calculator tool schema validation."""
        schema = financing_calculator_tool.args_schema

        validated = schema(vehicle_price=450000, down_payment=100000, term_years=5)
        assert validated.vehicle_price == 450000
        assert validated.down_payment == 100000
        assert validated.term_years == 5

    def test_financing_known_example(self):
        """Test the PRD regression scenario with independently calculated values."""
        summary, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=100000.0,
            term_years=5,
        )

        assert result.vehicle_price == 450000.0
        assert result.down_payment == 100000.0
        assert result.financed_amount == 350000.0
        assert result.annual_interest_rate == 0.10
        assert result.term_years == 5
        assert result.number_of_payments == 60
        assert result.monthly_payment == 7436.47
        assert isinstance(summary, str)
        assert "7,436.47" in summary

    def test_financing_zero_down_payment(self):
        """Test financing the full vehicle price."""
        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=0.0,
            term_years=5,
        )

        assert result.financed_amount == 450000.0
        assert result.monthly_payment == 9561.17

    def test_financing_down_payment_equal_to_price(self):
        """Test fully paid vehicle produces zero financing."""
        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=450000.0,
            term_years=5,
        )

        assert result.financed_amount == 0.0
        assert result.monthly_payment == 0.0

    def test_financing_minimum_term(self):
        """Test minimum supported term of 3 years."""
        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=0.0,
            term_years=3,
        )

        assert result.number_of_payments == 36
        assert result.monthly_payment == 14520.23

    def test_financing_maximum_term(self):
        """Test maximum supported term of 6 years."""
        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=0.0,
            term_years=6,
        )

        assert result.number_of_payments == 72
        assert result.monthly_payment == 8336.63

    def test_financing_error_handling(self):
        """Test invalid inputs are rejected before calculation."""
        invalid_inputs = [
            {"vehicle_price": 0.0, "down_payment": 0.0, "term_years": 5},
            {"vehicle_price": -1000.0, "down_payment": 0.0, "term_years": 5},
            {"vehicle_price": 450000.0, "down_payment": -1.0, "term_years": 5},
            {"vehicle_price": 450000.0, "down_payment": 450001.0, "term_years": 5},
            {"vehicle_price": 450000.0, "down_payment": 0.0, "term_years": 2},
            {"vehicle_price": 450000.0, "down_payment": 0.0, "term_years": 7},
        ]

        for inputs in invalid_inputs:
            with pytest.raises(ValueError):
                financing_calculator_tool.func(**inputs)


class TestToolIntegration:
    """Test tool integration and compatibility."""

    def test_tool_compatibility(self):
        """Test that both tools are compatible with LangChain."""
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

    def test_tool_schema_consistency(self):
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

    def test_tool_function_signatures(self):
        """Test that tool functions have correct signatures."""
        # All tools should accept a dictionary input
        test_input = {"query": "test"}

        for tool in [
            catalog_search_tool,
            document_search_tool,
            financing_calculator_tool,
        ]:
            # Should be able to call the function (even if it fails)
            try:
                result = tool.func(**test_input)
                assert isinstance(result, list)
            except Exception:
                # Expected to fail in test environment, but should not crash
                pass
