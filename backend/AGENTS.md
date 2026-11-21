# backend — PYTHON AGENT

Spanish-language AI vehicle sales assistant: a LangGraph agent that searches the vehicle catalog with fuzzy matching, answers company questions from a knowledge base via hybrid BM25 + pgvector retrieval, and computes financing plans. Stack: Python 3.12 (uv), LangChain/LangGraph, FastAPI, SQLModel/PostgreSQL + pgvector, Twilio.

Everything below is relative to `backend/`. The service is one LangGraph agent, one FastAPI webhook server, one settings module, plus the `db/` and `tools/` packages, imported as FLAT top-level modules (`config`, `agent`, `db.database`), not as `src.*`. Entry points: `langgraph.json` maps the graph to `./src/agent.py:agent` and auth to `./src/auth.py:auth`; Docker runs `src/whatsapp_server.py`.

Deeper knowledge lives in `src/db/AGENTS.md`, `src/tools/AGENTS.md` and `tests/AGENTS.md`; binding decisions and setup guides live in the repo-root `docs/` folder. Commands live in this directory's `README.md`.
