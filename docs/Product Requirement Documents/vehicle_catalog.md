# PRD: Vehicle Catalog

**Version:** 1.0
**Status:** Accepted
**Scope:** Vehicle catalog ingestion and search

---

## 1. Purpose

Provide a reliable vehicle catalog that can be populated from the
provided CSV and queried by the AI commercial agent to recommend
vehicles based on customer preferences.

The catalog is the authoritative source for vehicle availability,
price, mileage and vehicle attributes.

---

## 2. Requirements

### 2.1 Challenge Requirements

The challenge requires the agent to:

- Recommend available vehicles from the catalog.
- Consider customer preferences when selecting vehicles.
- Handle natural-language complexity and common spelling mistakes
  in vehicle makes and models.
- Provide accurate vehicle information rather than hallucinating
  catalog data.

The challenge also provides a vehicle catalog as input data.

### 2.2 Design Decisions

To satisfy these requirements, we will:

- Store the catalog in PostgreSQL.
- Normalize catalog data during ingestion.
- Expose catalog search through a deterministic application tool.
- Use fuzzy matching for make and model names.
- Keep vehicle data retrieval independent from the LLM.
- Return structured vehicle data to the agent.

These are implementation decisions, not requirements imposed by
the challenge.

---

## 3. Scope

### In scope

- CSV ingestion.
- Vehicle data normalization and validation.
- PostgreSQL persistence.
- Vehicle catalog search.
- Make and model typo tolerance.
- Filtering by customer preferences.
- Result sorting and limiting.
- Deterministic search behavior.
- Automated tests.

### Out of scope

- Natural-language interpretation.
- LLM-based recommendations.
- Financing calculations.
- Knowledge/document retrieval.
- WhatsApp integration.
- Conversation management.
- Image or semantic vehicle search.
- External vehicle inventory APIs.

---

## 4. Catalog Data

The catalog contains vehicle information such as:

| Field | Required | Description |
| --- | --- | --- |
| `stock_id` | Yes | Unique vehicle identifier |
| `make` | Yes | Vehicle manufacturer |
| `model` | Yes | Vehicle model |
| `year` | Yes | Vehicle year |
| `version` | No | Vehicle version |
| `km` | Yes | Mileage |
| `price` | Yes | Vehicle price |
| `features` | No | Vehicle features |

Additional source columns may be normalized into the `features`
field when appropriate.

The database schema should preserve the fields required by the
search use cases without unnecessarily duplicating source data.

---

## 5. CSV Ingestion

### 5.1 Purpose

Transform the provided CSV into validated catalog records that can
be safely stored and queried.

### 5.2 Processing Flow

```text
CSV
 ↓
Parse
 ↓
Normalize
 ↓
Validate
 ↓
Transform to Vehicle model
 ↓
Batch insert
 ↓
PostgreSQL
```

### 5.3 Normalization

The ingestion process should:

- Trim whitespace.
- Normalize text casing.
- Remove accents where appropriate for matching.
- Convert numeric fields to their expected types.
- Normalize boolean-like values.
- Represent missing optional values as `null`.

Invalid values should be reported with enough information to identify
the source row.

### 5.4 Validation

Required fields must be present and valid.

Examples:

- `stock_id` must be unique.
- `price` must be numeric.
- `km` must be numeric.
- `year` must be a valid integer.
- Required text fields must not be empty.

A malformed row should not silently become an invalid catalog record.

## 5.5 Idempotency

`stock_id` is the stable identifier for a vehicle.

The ingestion process must not silently create duplicate vehicles
when the same catalog is imported more than once.

The initial implementation may reject duplicates or explicitly
support an upsert/replace mode.

---

## 6. Catalog Search

### 6.1 Purpose

Provide a deterministic interface for retrieving vehicles that
match structured customer preferences.

The LLM is responsible for understanding the customer's request and
extracting preferences. The catalog tool is responsible for
retrieving actual vehicles.

```text
Customer
   ↓
LLM
   ↓
Structured preferences
   ↓
catalog_search
   ↓
PostgreSQL
   ↓
Vehicle results
   ↓
LLM
   ↓
Customer response
```

The LLM must not invent vehicle availability, prices or attributes.

---

## 6.2 Search Inputs

The tool accepts structured filters such as:

```json
{
  "budget_min": 300000,
  "budget_max": 500000,
  "make": "toyota",
  "model": "corolla",
  "km_max": 80000,
  "features": ["bluetooth"],
  "sort_by": "price_asc",
  "max_results": 5
}
```

All parameters are optional except where required by the specific
query.

`max_results` defaults to 5 and must not exceed 20.

---

## 6.3 Search Behavior

The search process is:

```text
Validate input
    ↓
Resolve make/model
    ↓
Apply catalog filters
    ↓
Apply feature filters
    ↓
Sort
    ↓
Limit results
```

Supported filters include:

- Price range.
- Make.
- Model.
- Maximum mileage.
- Vehicle features.
- Sorting.
- Maximum number of results.

---

## 7. Make and Model Matching

Users may provide misspellings such as:

```text
toyata → toyota
volkswagn → volkswagen
```

The search should tolerate common spelling variations.

The initial implementation uses fuzzy matching against known catalog
values.

A match below the configured confidence threshold must not be
silently guessed.

The threshold is an implementation parameter and should be covered
by tests using representative catalog queries.

---

## 8. Search Output

The tool returns structured vehicle information:

```json
[
  {
    "stock_id": 12345,
    "make": "toyota",
    "model": "corolla",
    "year": 2020,
    "version": "LE",
    "price": 450000,
    "km": 50000,
    "features": ["bluetooth", "car_play"]
  }
]
```

The response should contain only data retrieved from the catalog.

If no vehicle matches the requested criteria, the tool returns an
empty result set.

---

## 9. Error Handling

### Invalid input

Return a validation error describing the invalid parameter.

### No matches

Return an empty result set.

### Fuzzy match below threshold

Do not guess the make or model. Return no matching catalog result.

### Database failure

Return a controlled application error and log the failure.

Errors must not expose credentials, connection strings or other
sensitive information.

---

## 10. Performance

For the POC, the target is:

- Fuzzy matching: <100 ms.
- Database query: <500 ms.
- End-to-end catalog search: <1 second.

These are engineering targets for the POC, not challenge acceptance
criteria.

If the catalog grows substantially, search performance should be
re-evaluated before introducing additional infrastructure.

---

## 11. Testing

Tests should cover at least:

### Ingestion

- Valid CSV.
- Missing required fields.
- Invalid numeric values.
- Invalid boolean values.
- Duplicate `stock_id`.
- Missing optional values.
- Repeated ingestion.

### Search

- Exact make/model match.
- Common make/model typo.
- Price filtering.
- Mileage filtering.
- Feature filtering.
- Sorting.
- Result limits.
- No results.
- Invalid parameters.
- Fuzzy match below threshold.

Challenge examples should be represented as regression tests where
applicable.

---

## 12. Acceptance Criteria

The catalog is considered ready for integration with the agent when:

- The supplied CSV can be ingested into PostgreSQL.
- Invalid records are detected and reported.
- Repeated ingestion does not silently duplicate vehicles.
- Vehicle searches return only catalog records.
- Common make/model spelling mistakes are tolerated.
- Price, mileage and feature filters work correctly.
- Empty results are handled explicitly.
- Search behavior is covered by automated tests.
- The catalog tool has no dependency on an LLM.

---

## 13. Implementation Notes

The initial implementation uses:

- Python.
- PostgreSQL.
- SQLModel/Pydantic.
- RapidFuzz for fuzzy matching.
- Pytest for automated tests.

These technologies are implementation choices and may be replaced
without changing the catalog's functional contract.

The ingestion process should be exposed through a repeatable CLI
rather than being coupled to application startup.

Example:

```bash
python scripts/ingest_csv.py \
  --file data/vehicles.csv \
  --batch-size 500
```

---

## 14. Future Considerations

The following are intentionally deferred for the POC:

- Incremental catalog synchronization.
- External inventory APIs.
- Advanced ranking/recommendation models.
- Semantic vehicle search.
- Distributed search infrastructure.
- High-volume ingestion pipelines.
- Real-time inventory synchronization.

These should only be introduced if production requirements justify
the additional complexity.
