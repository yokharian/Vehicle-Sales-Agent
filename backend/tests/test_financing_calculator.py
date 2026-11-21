import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError


sys.path.append(str(Path(__file__).parent.parent / "src"))

from tools.financing_calculator import (
    FinancingCalculationError,
    FinancingInput,
    FinancingResult,
    financing_calculator_tool,
)


class TestFinancingInputSchema:
    def test_valid_input(self):
        params = FinancingInput(vehicle_price=450000, down_payment=100000, term_years=5)

        assert params.vehicle_price == 450000
        assert params.down_payment == 100000
        assert params.term_years == 5

    def test_zero_down_payment_is_allowed(self):
        params = FinancingInput(vehicle_price=450000, down_payment=0, term_years=3)

        assert params.down_payment == 0

    def test_rejects_non_positive_vehicle_price(self):
        with pytest.raises(ValidationError):
            FinancingInput(vehicle_price=0, down_payment=0, term_years=5)

        with pytest.raises(ValidationError):
            FinancingInput(vehicle_price=-1000, down_payment=0, term_years=5)

    def test_rejects_negative_down_payment(self):
        with pytest.raises(ValidationError):
            FinancingInput(vehicle_price=450000, down_payment=-1, term_years=5)

    def test_rejects_out_of_range_term(self):
        with pytest.raises(ValidationError):
            FinancingInput(vehicle_price=450000, down_payment=0, term_years=2)

        with pytest.raises(ValidationError):
            FinancingInput(vehicle_price=450000, down_payment=0, term_years=7)


class TestFinancingResultSchema:
    def test_valid_result(self):
        result = FinancingResult(
            vehicle_price=450000.0,
            down_payment=100000.0,
            financed_amount=350000.0,
            annual_interest_rate=0.10,
            term_years=5,
            monthly_payment=7436.47,
            number_of_payments=60,
        )

        assert result.vehicle_price == 450000.0
        assert result.down_payment == 100000.0
        assert result.financed_amount == 350000.0
        assert result.annual_interest_rate == 0.10
        assert result.term_years == 5
        assert result.monthly_payment == 7436.47
        assert result.number_of_payments == 60


class TestFinancingCalculations:
    def test_known_example_regression(self):
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
        assert "350,000.00" in summary
        assert "7,436.47" in summary

    def test_zero_down_payment(self):
        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=0.0,
            term_years=5,
        )

        assert result.financed_amount == 450000.0
        assert result.monthly_payment == 9561.17
        assert result.number_of_payments == 60

    def test_down_payment_equal_to_vehicle_price(self):
        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=450000.0,
            term_years=5,
        )

        assert result.financed_amount == 0.0
        assert result.monthly_payment == 0.0
        assert result.number_of_payments == 60

    def test_minimum_term_three_years(self):
        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=0.0,
            term_years=3,
        )

        assert result.term_years == 3
        assert result.number_of_payments == 36
        assert result.monthly_payment == 14520.23

    def test_maximum_term_six_years(self):
        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=0.0,
            term_years=6,
        )

        assert result.term_years == 6
        assert result.number_of_payments == 72
        assert result.monthly_payment == 8336.63


class TestFinancingValidation:
    def test_rejects_invalid_vehicle_price(self):
        for price in (0.0, -1.0, float("nan"), float("inf")):
            with pytest.raises(ValueError, match="vehicle_price"):
                financing_calculator_tool.func(
                    vehicle_price=price,
                    down_payment=0.0,
                    term_years=5,
                )

    def test_rejects_negative_down_payment(self):
        with pytest.raises(ValueError, match="down_payment"):
            financing_calculator_tool.func(
                vehicle_price=450000.0,
                down_payment=-1.0,
                term_years=5,
            )

    def test_rejects_down_payment_greater_than_vehicle_price(self):
        with pytest.raises(ValueError, match="down_payment"):
            financing_calculator_tool.func(
                vehicle_price=450000.0,
                down_payment=450001.0,
                term_years=5,
            )

    def test_rejects_invalid_term_years(self):
        for term_years in (2, 7):
            with pytest.raises(ValueError, match="term_years"):
                financing_calculator_tool.func(
                    vehicle_price=450000.0,
                    down_payment=0.0,
                    term_years=term_years,
                )

    def test_rejects_non_integer_term_years(self):
        with pytest.raises(ValueError, match="term_years"):
            financing_calculator_tool.func(
                vehicle_price=450000.0,
                down_payment=0.0,
                term_years=4.5,
            )


class TestMonetaryRounding:
    def test_monthly_payment_rounded_to_two_decimals(self):
        raw_payment = 350000.0 * (0.10 / 12) * (1 + 0.10 / 12) ** 60 / ((1 + 0.10 / 12) ** 60 - 1)
        assert raw_payment != 7436.47

        _, result = financing_calculator_tool.func(
            vehicle_price=450000.0,
            down_payment=100000.0,
            term_years=5,
        )
        assert result.monthly_payment == 7436.47


class TestErrorHandling:
    def test_calculation_failure_is_controlled(self, monkeypatch):
        monkeypatch.setattr("tools.financing_calculator.ANNUAL_INTEREST_RATE", Decimal("0.00"))

        with pytest.raises(FinancingCalculationError, match="Financing calculation failed"):
            financing_calculator_tool.func(
                vehicle_price=450000.0,
                down_payment=100000.0,
                term_years=5,
            )


class TestToolInterface:
    def test_tool_creation(self):
        assert financing_calculator_tool.name == "financing_calculator"
        assert "financing" in financing_calculator_tool.description.lower()
        assert financing_calculator_tool.args_schema is not None
        assert callable(financing_calculator_tool.func)
