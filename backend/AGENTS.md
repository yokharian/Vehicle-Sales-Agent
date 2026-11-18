# PROJECT KNOWLEDGE BASE

**Generated:** 2026-10-13
**Commit:** 1541d7f
**Branch:** master

## OVERVIEW

AI vehicle sales assistant for WhatsApp (Spanish-language): a LangGraph agent that searches a vehicle catalog with fuzzy matching, answers company questions from a knowledge base via hybrid BM25 + pgvector retrieval, and computes financing plans. Stack: Python 3.12 (uv), LangChain/LangGraph, FastAPI, SQLModel/PostgreSQL + pgvector, Twilio.

## STRUCTURE

```
vehicle-sales-agent/
├── src/            # app core — flat-module imports (config, agent, db.*, tools.*), never src.*
│   ├── agent.py            # LangGraph graph + SYSTEM_PROMPT + chat()
│   ├── whatsapp_server.py  # FastAPI webhook server (entry point)
│   ├── config.py           # all pydantic-settings classes
│   ├── auth.py             # optional Cognito JWT auth
│   ├── db/                 # engines, Vehicle model, DAO, pgvector chunk store
│   └── tools/              # three @tool functions the agent calls
├── scripts/        # ingest_csv.py, index_documents.py, html2text_cli.py (CLI entry points)
├── tests/          # pytest suite; Docker/testcontainers required
├── docs/           # binding ADRs + PRDs, DOCKER.md, WHATSAPP.md
├── data/           # sample_vehicles.csv + documents/kavak.md (the knowledge corpus)
├── docker/         # WhatsApp/minimal compose stacks
├── langgraph.json  # graph: src/agent.py:agent, auth: src/auth.py:auth
└── Dockerfile      # uv-based image
```

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Change agent behaviour/prompt | `src/agent.py` | `SYSTEM_PROMPT`, `chat()`; tools are commented out here |
| Add/change a tool | `src/tools/` | see `src/tools/AGENTS.md`; schema fields are the LLM contract |
| Catalog queries / fuzzy match | `src/db/vehicle_dao.py` | scoring runs in PostgreSQL, not Python |
| Knowledge retrieval | `src/tools/document_search.py` + `src/db/document_loader.py` | BM25Plus + dense ensemble |
| Config/env surface | `src/config.py`, `.env.example` | one `*Settings` class per concern |
| Webhook / endpoints | `src/whatsapp_server.py` | `/whatsapp/webhook`, `/health`, `/send-message` |
| Ingestion + indexing | `scripts/ingest_csv.py`, `scripts/index_documents.py` | both idempotent per key/source |
| Binding decisions | `docs/Architecture Decision Records/`, `docs/Product Requirement Documents/` | ADR-002 tool calling, ADR-004 grounded answers, per-tool PRDs |
| Test harness | `tests/conftest.py` | see `tests/AGENTS.md` |

## CODE MAP

Refs are textual references across tracked `.py` files (no LSP server is configured for this repo, so centrality is measured by search, not semantic analysis).

| Symbol | Type | Location | Refs | Role |
|---|---|---|---|---|
| `Vehicle` | SQLModel table | `src/db/database.py:59` | ~103 | catalog row, `stock_id` PK, JSON `features` |
| `catalog_search_tool` | `@tool` | `src/tools/catalog_search.py:142` | ~54 | vehicle search; structured + CSV output |
| `financing_calculator_tool` | `@tool` | `src/tools/financing_calculator.py:85` | ~30 | Decimal financing math |
| `document_search_tool` | `@tool` | `src/tools/document_search.py:158` | ~28 | grounded evidence retrieval |
| `DocumentChunk` | ORM table | `src/db/document_loader.py:96` | ~22 | chunk rows + `Vector` embedding |
| `DocumentSearchSettings` | settings | `src/config.py:58` | ~22 | retrieval + embedding config |
| `DocumentLoader` | class | `src/db/document_loader.py:48` | ~19 | discovers/chunks `.md`/`.txt` |
| `fuzzy_match_make` | function | `src/db/vehicle_dao.py:66` | ~17 | SQL levenshtein make resolution |
| `load_chunks` / `dense_search` | functions | `src/db/document_loader.py:181,192` | ~15 / ~6 | retrieval primitives |
| `get_session_sync` / `get_pgvector_session_sync` | functions | `src/db/database.py:49,54` | ~6 / ~5 | catalog / vector sessions |
| `chat` | function | `src/agent.py:91` | ~5 | the only agent entry used by the server |
| `create_fastapi_app` / `start_whatsapp_server` | functions | `src/whatsapp_server.py:120,187` | ~1 / ~1 | app factory and uvicorn runner |

## CONVENTIONS

- Flat imports inside the app: `from config import ...`, `import db.database as db_module`, `from tools.document_search import ...`. `src` is NOT a package name at runtime — entry points prepend their own directory to `sys.path`. (This contradicts ruff's `known-first-party = ["src", "tests"]`.)
- Settings are always pydantic-settings classes in `src/config.py`; never read `os.environ` directly elsewhere.
- Import-time side effects are deliberate: `db/database.py` opens both engines, `agent.py` builds the model and graph, `auth.py` builds the JWKS client. Expect imports to need env configured.
- Money is `Decimal` (`Decimal(str(value))`, `ROUND_HALF_UP`, `localcontext()`); the LLM never computes or adjusts figures.
- Errors: one `*Error(RuntimeError)` class per tool, raised `from exc`, logging the exception type and never the DSN.
- User-facing strings are Spanish; code, docstrings and logs are English.

## ANTI-PATTERNS (THIS PROJECT)

- No `src.`-prefixed imports inside the app; no reliance on the repo root being importable.
- No business rules in prompts (ADR-002) and no invented business facts (ADR-004) — empty retrieval is reported as empty, never filled from model knowledge.
- Never append duplicate catalog rows on re-ingest; the catalog is keyed on `stock_id`.
- Never let a connection string, token or DSN reach an error message or log line.
- Never make the tool contract expose PostgreSQL specifics (PRD `knowledge_search.md`).
- Tests must not import app modules before their `sys.path` line, and must not bind `db.database.engine` at import time (the harness swaps engines on the module).

## UNIQUE STYLES

- `agent.py` builds the model, the Langfuse `CallbackHandler` and the graph at module scope; there is no factory function for the graph.
- `whatsapp_server.py` holds one lazy module-global `assistant` singleton and truncates replies at 1600 chars with `...\n\n[Respuesta truncada]`.
- Retrieval deliberately uses `BM25Plus`, not `BM25Okapi` (Okapi IDF collapses on this small corpus).
- `document_loader.py` splits ingest (`DocumentLoader` class) from persistence (module-level functions); the persistence functions reach the engine through the module so the test harness can swap it.

## COMMANDS

```bash
uv sync                                                      # install deps (Python 3.12 from .python-version)
uv run pytest                                                # full suite — REQUIRES a running Docker daemon
uv run pytest tests/test_document_loader.py                   # single module
uvx ruff check . && uvx ruff format .                         # ruff is configured but NOT installed in .venv
uv run --env-file .env python src/whatsapp_server.py --host 0.0.0.0 --port 5000
uv run --env-file .env python scripts/ingest_csv.py data/sample_vehicles.csv --create-tables
uv run --env-file .env python scripts/index_documents.py       # --file <path> for one doc, --force to rebuild
docker compose up --build                                     # app + pgvector; ingests on startup
vercel deploy --prod                                          # builds the root Dockerfile, serves it with Fluid Compute
```

CI (`.github/workflows/deploy.yml`) builds, pushes and cosign-signs the image on `master`, `v*.*.*` tags and manual dispatch — it never runs the test suite.

## NOTES

- **`src/agent.py` currently runs without tools.** Lines 21-23 (tool imports), 80 (`tools = [...]`) and 85 (`tools=tools,`) are commented out, so the live agent has no catalog/document/financing capability although README, ADR-002 and the PRDs describe tool calling. Confirm intent before restoring.
- **Docker is running in this checkout (verified 2026-10-13)**, so the test suite can start here again.
- `.env` is read from the CWD by pydantic-settings, so tests and CLIs behave differently when run from another directory; the local `.env` also shadows settings defaults in `tests/test_config.py`.
- `.aiignore` excludes `.env` and `.venv/`; `.env` exists locally and is gitignored.
- ADR-006 is a Draft; ADR-001 to ADR-005 are Accepted and binding. Each tool has a PRD that defines its contract.
- `docs/diagrams/` holds SVG/Excalidraw sources; `ingestion_errors.log` is a runtime artifact.
