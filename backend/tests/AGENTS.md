# tests — PYTEST SUITE

12 test modules over the app, with the whole harness living in `conftest.py` (there is no pytest config section in `pyproject.toml` — default discovery only). Earned this file as a distinct domain (score 9: 14 files, 3.3k LOC, a non-obvious container + engine-swap harness).

## WHERE TO LOOK

| Test file | Covers | Needs Docker |
|---|---|---|
| `conftest.py` | sys.path, env seeding, container, catalog seed, fake embeddings | yes (fixtures) |
| `test_auth.py` | Cognito JWT path (throwaway RSA key + stubbed JWKS) | no |
| `test_config.py` | settings classes and env overrides | no |
| `test_csv_ingestion.py` | `scripts/ingest_csv.py` parse/normalize/validate/upsert | yes |
| `test_document_loader.py` | `DocumentLoader` discovery/chunking on `tmp_path` | inherited only |
| `test_document_search.py` | hybrid retrieval + document tool (largest file, 566 lines) | yes |
| `test_fuzzy_search.py` | `fuzzy_match_make/_model` and fuzzy DAO paths | yes |
| `test_catalog_search_tool.py` | `VehiclePreferences`/`VehicleResult` + tool behaviour | yes |
| `test_financing_calculator.py` | Decimal math, validation, rounding, error contract | no |
| `test_tools_schema.py` | all three tool schemas | no |
| `test_vehicle_dao.py` | DAO queries — own in-memory `sqlite:///:memory:` engine | inherited only |
| `test_vehicle_model.py` | `Vehicle` model + DB ops — own sqlite engine | inherited only |
| `test_combined_workflow.py` | catalog + documents + financing together | yes |

## CONVENTIONS

- Every module prepends `src/` to `sys.path` BEFORE importing app code (`sys.path.append(str(Path(__file__).parent.parent / "src"))`). Imports are flat (`from config import ...`, `import db.database as db_module`) — never `from src.x import ...`.
- `conftest.py` seeds placeholder env vars at import (`DATABASE_URI`/`PGVECTOR_URI` at localhost:59999, `OPENAI_API_KEY`, `COGNITO_*`) because `db.database` and `src.auth` build settings and engines at import time.
- Three session-scoped autouse fixtures, chained in order: `_postgres_with_pgvector` (testcontainers `pgvector/pgvector:pg16`, enables `vector` + `fuzzystrmatch`, then REPLACES `db_module.engine` and `db_module.pgvector_engine` by assignment) → `_seed_catalog_db` (7 vehicles, stock_id 1001-1007) → `_fake_embeddings_for_document_search` (monkeypatches `document_search.resolve_embeddings` to `DeterministicFakeEmbedding(size=768)`).
- Because those fixtures are autouse and session-scoped, the container starts for the entire run — including the "pure" tests. Only the fixtures can be bypassed with `-p no:cacheprovider`-style tricks, not by choosing a file.
- Embeddings are always faked, so no provider API key or network access is needed.
- `document_index` is a per-FILE fixture, defined separately in `test_document_search.py` and `test_combined_workflow.py`, applied via `@pytest.mark.usefixtures("document_index")`.
- `test_vehicle_dao.py` and `test_vehicle_model.py` build their own function-scoped `test_engine` (`sqlite:///:memory:`) and assert against that, not the container data.

## ANTI-PATTERNS (THIS PROJECT)

- Never import an app module above the `sys.path` line in a test file.
- Never `from db.database import engine`: the harness swaps engines on the module, so bindings taken at import time go stale. Use `db_module.engine` or the `get_*_session_*()` helpers.
- Never assert settings defaults after only `monkeypatch.delenv`: `monkeypatch` clears process env, not the `.env` file pydantic-settings reads from the CWD.
- Do not add a Docker-dependent test without expecting the session fixture cost; do not add a test that hits a real provider API.

## CAVEATS (verified 2026-10-12)

- **Docker is required and is running in this checkout (verified 2026-10-13).** `docker info` succeeds, so the session fixtures can start the container.
- **The root `.env` leaks into settings assertions.** Verified with a clean environment: from the repo root `DocumentSearchSettings()` resolves `embedding_provider=openrouter` (the `.env` value), while the same command from `/tmp` resolves `openai` (the code default). Tests that assert defaults therefore depend on your local `.env` — run from a clean worktree or unset `DOCUMENT_*`.
- `ruff` is configured in `pyproject.toml` but is NOT in the `dev` dependency group (only `pytest` and `testcontainers`), and `.venv/bin/ruff` does not exist — invoke it as `uvx ruff`.
