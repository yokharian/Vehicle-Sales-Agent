# PRD: Financing Calculator Tool

**Version:** 1.0
**Status:** Accepted
**Tool:** `financing_calculator`

## 1. Purpose

Provide deterministic financing calculations based on the vehicle price, customer's down payment, the challenge-defined interest rate, and the selected financing term.

The tool returns the calculated financing amount and payment information so the AI sales agent can communicate financing options to the customer.

The LLM must not perform the financial calculation itself.

---

## 2. Goals

* Calculate financing plans deterministically.
* Use the vehicle price and customer's down payment as inputs.
* Apply the challenge-defined 10% interest rate.
* Support financing terms from 3 to 6 years.
* Return structured calculation results.
* Make calculations reproducible and independently testable.
* Prevent the LLM from inventing or approximating financial values.

---

## 3. Non-Goals

* Vehicle catalog search.
* Vehicle availability.
* Credit approval.
* Customer eligibility assessment.
* Credit scoring.
* External lender integration.
* Real-time financial product information.
* Personalized financial advice.
* Negotiation of interest rates or financing terms.

---

## 4. Tool Interface

### Input

```json
{
  "vehicle_price": 450000,
  "down_payment": 100000,
  "term_years": 5
}
```

Parameters:

```text
vehicle_price: float
down_payment: float
term_years: int
```

Constraints:

* `vehicle_price` must be greater than zero.
* `down_payment` must be greater than or equal to zero.
* `down_payment` must not exceed `vehicle_price`.
* `term_years` must be between 3 and 6.
* Monetary values must use a consistent currency and precision.

The interest rate is not provided by the LLM. It is defined by the application according to the challenge requirements.

---

## 5. Financing Rules

The financing amount is:

```text
financed_amount = vehicle_price - down_payment
```

The challenge defines an annual interest rate of:

```text
annual_interest_rate = 10%
```

Supported terms are:

```text
3 years
4 years
5 years
6 years
```

The implementation must use a documented amortization formula to calculate the periodic payment.

For a standard fixed-rate monthly payment:

```text
r = annual_interest_rate / 12

n = term_years × 12

payment =
    financed_amount × r × (1 + r)^n
    --------------------------------
           (1 + r)^n - 1
```

If the financed amount is zero, the periodic payment is zero.

The implementation should keep the calculation logic isolated from the LLM and agent orchestration.

---

## 6. Output

The tool returns structured financing information.

Example:

```json
{
  "vehicle_price": 450000,
  "down_payment": 100000,
  "financed_amount": 350000,
  "annual_interest_rate": 0.10,
  "term_years": 5,
  "monthly_payment": 7436.47,
  "number_of_payments": 60
}
```

The exact monetary rounding policy must be consistent across all calculations.

The tool output should contain only values produced by the calculation.

---

## 7. Multiple Financing Options

The agent may call the tool for different financing terms to present multiple options to the customer.

For example:

```text
3 years
4 years
5 years
6 years
```

The tool remains responsible only for calculating each requested option.

The LLM is responsible for presenting the options conversationally.

The LLM must not modify the calculated values.

---

## 8. Validation

The tool must reject invalid inputs before performing the calculation.

Examples:

### Invalid vehicle price

```text
vehicle_price <= 0
```

### Invalid down payment

```text
down_payment < 0
```

### Down payment greater than vehicle price

```text
down_payment > vehicle_price
```

### Invalid term

```text
term_years < 3
term_years > 6
```

Validation errors should identify the invalid parameter without exposing internal implementation details.

---

## 9. Error Handling

### Invalid Input

Return a controlled validation error.

### Calculation Failure

Return a controlled application error and log the technical failure.

The tool must not return an approximate or LLM-generated value when the calculation fails.

---

## 10. Precision and Rounding

Financial calculations must use a deterministic monetary representation.

Intermediate calculations should preserve sufficient precision.

The final monetary values presented to the user should be rounded consistently to two decimal places.

The rounding policy should be implemented in the calculator rather than delegated to the LLM.

---

## 11. Performance

The calculation is expected to be computationally inexpensive.

Initial POC target:

```text
Calculation: <10 ms
```

This is an engineering target rather than a challenge acceptance criterion.

No caching or additional infrastructure is required.

---

## 12. Testing

### Unit Tests

Cover:

* Exact calculation with a known example.
* Zero down payment.
* Down payment equal to vehicle price.
* Minimum term: 3 years.
* Maximum term: 6 years.
* Invalid vehicle price.
* Negative down payment.
* Down payment greater than vehicle price.
* Invalid financing term.
* Monetary rounding.

### Regression Tests

Representative financing scenarios should be included in the agent evaluation dataset.

Example:

```text
Vehicle price: 450,000
Down payment: 100,000
Term: 5 years
Interest rate: 10%
```

The expected result should be calculated independently and used as a regression fixture.

---

## 13. Acceptance Criteria

The financing calculator is ready for integration when:

* It calculates the financed amount from vehicle price and down payment.
* It applies the challenge-defined 10% annual interest rate.
* It supports terms from 3 to 6 years.
* Calculations are deterministic and reproducible.
* Invalid inputs are rejected explicitly.
* Results are returned through a structured tool interface.
* Monetary rounding is consistent.
* The tool has no dependency on the LLM.
* Core calculation and validation behavior is covered by automated tests.

---

## 14. Current Limitations

The POC intentionally does not support:

* Credit approval.
* Customer eligibility rules.
* Credit scoring.
* Variable interest rates.
* External financing providers.
* Taxes, fees, insurance, or other charges not specified by the challenge.
* Early repayment calculations.
* Amortization schedules beyond the required payment calculation.

These capabilities should only be introduced if explicitly required by the business or financing provider.

---

## 15. Dependencies

* Python
* Pydantic
* Pytest

The calculator does not require an LLM, database, external API, or retrieval system.

**Implementation:** `src/tools/financing_calculator.py`
**Tests:** `tests/test_financing_calculator.py`
