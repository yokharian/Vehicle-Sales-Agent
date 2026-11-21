# backend — PYTHON AGENT

Spanish-language AI vehicle sales assistant: a LangGraph agent that searches the vehicle catalog with fuzzy matching, answers company questions from a knowledge base via hybrid BM25 + pgvector retrieval, and computes financing plans. Stack: Python 3.12 (uv), LangChain/LangGraph, FastAPI, SQLModel/PostgreSQL + pgvector, Twilio.

Everything below is relative to `backend/`. Deeper knowledge lives in `src/AGENTS.md`, `src/db/AGENTS.md`, `src/tools/AGENTS.md` and `tests/AGENTS.md`; binding decisions and setup guides live in the repo-root `docs/` folder. Commands live in this directory's `README.md`.

## Notes

- `.env` is read from the CWD by pydantic-settings, so tests and CLIs behave differently when run from another directory; the local `.env` also shadows settings defaults in `tests/test_config.py`.
- ADR-006 is a Draft; ADR-001 to ADR-005 are Accepted and binding. Each tool has a PRD that defines its contract.
- `../docs/diagrams/` holds the SVG/Excalidraw architecture sources; `ingestion_errors.log` is a runtime artifact.
- The Docker build context is `backend/`, not the repo root.
