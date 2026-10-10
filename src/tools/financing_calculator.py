"""
LangChain tool for deterministic vehicle financing calculations.

Implements the financing_calculator PRD: fixed 10% annual interest rate
defined by the application, 3-6 year terms, standard fixed-rate amortization,
and Decimal-based monetary arithmetic so the LLM never computes or alters
financial values.
"""

from __future__ import annotations

import logging
import math
from decimal import ROUND_HALF_UP, Decimal, localcontext

from langchain_core.tools import tool
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)

ANNUAL_INTEREST_RATE = Decimal("0.10")
MIN_TERM_YEARS = 3
MAX_TERM_YEARS = 6
PAYMENTS_PER_YEAR = 12
CALCULATION_PRECISION = 28
_CENT = Decimal("0.01")


class FinancingCalculationError(RuntimeError):
    """Raised when the financing calculation fails, without leaking internals."""


def _money(value: Decimal) -> Decimal:
    """Round a monetary amount to two decimals, half-up."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _as_decimal(value: float) -> Decimal:
    """Convert a monetary input deterministically via its shortest repr."""
    return Decimal(str(value))


class FinancingInput(BaseModel):
    """Input schema for the financing calculator."""

    vehicle_price: float = Field(description="Total vehicle price in USD", gt=0)
    down_payment: float = Field(description="Customer down payment in USD", ge=0)
    term_years: int = Field(
        description=f"Financing term in years ({MIN_TERM_YEARS}-{MAX_TERM_YEARS})",
        ge=MIN_TERM_YEARS,
        le=MAX_TERM_YEARS,
    )


class FinancingResult(BaseModel):
    """Structured financing plan returned to the agent."""

    vehicle_price: float = Field(description="Total vehicle price in USD")
    down_payment: float = Field(description="Customer down payment in USD")
    financed_amount: float = Field(
        description="Financed amount in USD (vehicle price minus down payment)"
    )
    annual_interest_rate: float = Field(
        description="Annual interest rate defined by the application"
    )
    term_years: int = Field(description="Financing term in years")
    monthly_payment: float = Field(description="Fixed monthly payment in USD")
    number_of_payments: int = Field(description="Total number of monthly payments")


@tool(
    "financing_calculator",
    description="""Calculate vehicle financing deterministically.

Computes the financed amount (vehicle_price - down_payment), applies the
fixed 10% annual interest rate, and returns the fixed monthly payment for
the requested term (3-6 years) using the standard amortization formula.""",
    args_schema=FinancingInput,
    error_on_invalid_docstring=False,
    return_direct=False,
    parse_docstring=True,
    response_format="content_and_artifact",
)
def financing_calculator_tool(
    vehicle_price: float,
    down_payment: float,
    term_years: int,
) -> tuple[str, FinancingResult]:
    """
    Calculate vehicle financing with the fixed application interest rate.

    Args:
        vehicle_price: Total vehicle price in USD (greater than zero)
        down_payment: Customer down payment in USD (zero or more, at most the price)
        term_years: Financing term in years (3-6)

    Returns:
        (summary_text, structured_result) with the financing plan.
    """
    if not math.isfinite(vehicle_price):
        raise ValueError("vehicle_price must be a finite number")
    if not math.isfinite(down_payment):
        raise ValueError("down_payment must be a finite number")
    if vehicle_price <= 0:
        raise ValueError("vehicle_price must be greater than zero")
    if down_payment < 0:
        raise ValueError("down_payment must be greater than or equal to zero")
    if down_payment > vehicle_price:
        raise ValueError("down_payment must not exceed vehicle_price")
    if (
        not isinstance(term_years, int)
        or term_years < MIN_TERM_YEARS
        or term_years > MAX_TERM_YEARS
    ):
        raise ValueError(
            f"term_years must be an integer between {MIN_TERM_YEARS} and {MAX_TERM_YEARS}"
        )

    price = _as_decimal(vehicle_price)
    down_payment_value = _as_decimal(down_payment)
    financed_amount = _money(price - down_payment_value)

    try:
        with localcontext() as context:
            context.prec = CALCULATION_PRECISION
            monthly_rate = ANNUAL_INTEREST_RATE / PAYMENTS_PER_YEAR
            growth = (Decimal(1) + monthly_rate) ** (term_years * PAYMENTS_PER_YEAR)
            payment = financed_amount * monthly_rate * growth / (growth - Decimal(1))
    except ArithmeticError as exc:
        logger.error("Financing calculation failed: %s", type(exc).__name__)
        raise FinancingCalculationError("Financing calculation failed.") from exc

    monthly_payment = _money(payment)
    result = FinancingResult(
        vehicle_price=float(price),
        down_payment=float(down_payment_value),
        financed_amount=float(financed_amount),
        annual_interest_rate=float(ANNUAL_INTEREST_RATE),
        term_years=term_years,
        monthly_payment=float(monthly_payment),
        number_of_payments=term_years * PAYMENTS_PER_YEAR,
    )
    summary = (
        f"{float(price):,.2f} USD price with {float(down_payment_value):,.2f} USD down "
        f"finances {float(financed_amount):,.2f} USD at "
        f"{float(ANNUAL_INTEREST_RATE):.0%} APR for {term_years} years: "
        f"{result.number_of_payments} payments of {float(monthly_payment):,.2f} USD."
    )
    return summary, result
