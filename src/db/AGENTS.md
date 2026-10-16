# src/db — DATA LAYER

Two stores behind one package: the SQLModel vehicle catalog (relational) and the pgvector document index. `database.py` holds both engines as module globals; every DAO/loader call resolves them at call time. Earned this file as a distinct domain (score 10: own module boundary, high reference centrality — `Vehicle` alone is referenced ~100 times).

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Vehicle table, engines, sessions | `database.py` | `Vehicle` (stock_id PK, `features` JSON column, `extend_existing=True`) |
| Catalog queries, fuzzy make/model | `vehicle_dao.py` | scoring runs in SQL, `FUZZY_MATCH_THRESHOLD = 60` |
| Document discovery/chunking | `document_loader.py` | `DocumentLoader` class |
| Chunk persistence and retrieval | `document_loader.py` | module-level primitives: `reindex`, `upsert_document_chunks`, `purge_removed_sources`, `load_chunks`, `dense_search`, `stored_chunk_hashes` |
| DDL | `database.create_db_and_tables()` (fuzzystrmatch), `document_loader.ensure_tables()` (vector) | both idempotent |

## CONVENTIONS

- Two engines, two session helpers: `get_session_sync()` (catalog) and `get_pgvector_session_sync()` (chunks). Everything is sync SQLAlchemy/SQLModel — do not introduce async sessions even though the sample URIs say `asyncpg`.
- Reach engines through the MODULE: `import db.database as db_module`, then `db_module.pgvector_engine`. The one-argument form (`from .database import get_session_sync`) works because those functions build a `Session` from the global at call time. This is deliberate: the test harness swaps `db_module.engine` at runtime.
- Fuzzy matching is computed in PostgreSQL (`levenshtein` + `strpos` containment bonus of 90, alphabetical tie-break), never in Python. Inputs over 255 bytes return `None` — PostgreSQL's levenshtein limit — rather than raising.
- Import-time failure is intentional: `database.py` raises `MissingDatabaseURIError` when `DATABASE_URI` is not set.
- Indexed sources are `.md`/`.txt` only (`SUPPORTED_SUFFIXES`), chunked 500/100. `content_hash` is embedding-model-qualified, so switching models invalidates stored rows.
- DDL is additive and idempotent: `ensure_tables()` also runs `ALTER TABLE ... ADD COLUMN IF NOT EXISTS content_hash`.

## ANTI-PATTERNS (THIS PROJECT)

- Never append duplicate catalog rows on re-ingest (PRD `vehicle_catalog.md`): the catalog is keyed on `stock_id` — upsert or reject, never a blind insert.
- Never let a connection string or DSN reach an error message or log line; tool-layer errors wrap as `*Error(RuntimeError)` with generic text.
- Never run two ingests of the same source concurrently (`scripts/index_documents.py` states the single-writer-per-source constraint).
- `Vehicle.price` is a `float` column while financing math is `Decimal`; convert at the boundary with `Decimal(str(value))`, never `Decimal(float)`. `select(...)` statements in `_replace_rows` delete-then-insert must stay in one transaction.

## HOTSPOTS

- `vehicle_dao.fuzzy_match_make` / `fuzzy_match_model` express scoring as SQLAlchemy `case`/`func.levenshtein` expressions; read the docstring before editing.
- `document_loader` is split by role: `DocumentLoader` only discovers and chunks, all persistence lives in the module-level functions.
