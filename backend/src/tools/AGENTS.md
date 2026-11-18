# src/tools — LANGCHAIN TOOLS

Three `@tool` functions the agent can call, each with pydantic input/output schemas. Their argument schemas ARE the model's interface (ADR-002), so field names, descriptions and constraints are contract — not documentation. Earned this file as a distinct domain (score 8: high reference centrality, `catalog_search_tool` ~54 refs, plus a binding PRD per tool).

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Vehicle search | `catalog_search.py` | `catalog_search_tool`, `VehiclePreferences` → `VehicleResult`; dual output (structured + CSV/JSON string) |
| Knowledge retrieval | `document_search.py` | `document_search_tool`, hybrid BM25Plus + dense `EnsembleRetriever` |
| Financing math | `financing_calculator.py` | `financing_calculator_tool`, `FinancingInput` → `FinancingResult` |
| Provider/key resolution | `document_search.resolve_embeddings` | openai vs openrouter, key from `DocumentSearchSettings` |

## CONVENTIONS

- One error class per tool, all `RuntimeError` subclasses: `CatalogSearchDatabaseError`, `DocumentSearchError`, `FinancingCalculationError`. Raise `X from exc`, log the exception TYPE (never the DSN), and keep the message generic ("temporarily unavailable").
- Validate inside the tool body before doing work, even where pydantic already constrains the field; invalid input raises `ValueError` naming the parameter.
- Money is `Decimal` only: `Decimal(str(value))` at the boundary, `localcontext()` precision 28, `ROUND_HALF_UP`, `_money()` helper. The LLM never computes or adjusts a figure.
- Fixed business rules live in code, not prompts: `ANNUAL_INTEREST_RATE = Decimal("0.10")`, terms limited to 3–6 years.
- Retrieval returns evidence only — passages with source metadata — and reports empty retrieval as empty. No generated text, no fallback to model knowledge (ADR-004).
- `document_search.build_bm25_retriever` uses `BM25Plus`, not `BM25Okapi` (Okapi IDF collapses on the small corpus).
- Docstrings follow "one-line contract + typed Args + Returns"; the `@tool` `description` is what the model routes on, so update docstring and description together.

## ANTI-PATTERNS (THIS PROJECT)

- Do not let a tool's external contract expose PostgreSQL specifics (PRD `knowledge_search.md`).
- Do not return `[]` for a database failure: empty means "no match", an error means "unavailable". Silently emptying results makes the agent answer as if there were no stock.
- Do not move business rules into prompts or the LLM's reasoning path (ADR-002).

## HOTSPOTS

- `catalog_search_tool` (~100 lines) does validation, fuzzy resolution, DB read, feature post-filter, sorting and dual serialization in one body.
- `document_search_tool` reloads chunks and rebuilds the BM25 index per query — the retrieval hotspot.
- `DenseRetriever._get_relevant_documents` carries `# noqa: ARG002` on `run_manager` for interface compatibility; keep the signature.
