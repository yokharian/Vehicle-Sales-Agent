# src — APPLICATION CORE

The running service: one LangGraph agent, one FastAPI webhook server, one settings module, plus the `db/` and `tools/` packages. Everything here is imported as a FLAT top-level module (`config`, `agent`, `db.database`), not as `src.*`. Earned this file as the app core (score 9: module boundary, ~20 public symbols, high reference centrality).

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Agent graph + system prompt | `agent.py` | `agent` (LangGraph `create_agent`), `chat()`, `build_chat_model()`, `SYSTEM_PROMPT` |
| WhatsApp webhook server | `whatsapp_server.py` | `create_fastapi_app()`, `start_whatsapp_server()`, CLI `--host/--port/--debug` |
| All configuration | `config.py` | one `*Settings(BaseSettings)` class per concern; `.env`-backed |
| JWT auth for the server | `auth.py` | LangGraph `Auth`; Cognito JWKS validation |

Entry points: `langgraph.json` maps the graph to `./src/agent.py:agent` and auth to `./src/auth.py:auth`; Docker runs `src/whatsapp_server.py`.

## CONVENTIONS

- Flat sibling imports are the norm: `from config import ...`, `from agent import chat`, `import db.database as db_module`. Each entry point prepends its own directory to `sys.path` (`sys.path.append(str(Path(__file__).parent))` in `agent.py` and `whatsapp_server.py`; `sys.path.insert(0, .../src)` in tests and scripts). Note this contradicts ruff's `known-first-party = ["src", "tests"]`.
- Configuration is pydantic-settings, one class per concern, `extra="ignore"`, with explicit `validation_alias` env names. The database reads `DATABASE_URI` (with `PGVECTOR_URI` defaulting to it; blank counts as unset), and the chat model and embeddings each read an OpenAI-compatible endpoint via three fields: model, api_key and api_url (`LLM_*` and `DOCUMENT_EMBEDDING_*`). Read settings through a class instance; never `os.environ` directly in application code.
- Import-time side effects are deliberate and load-bearing: `config.py` classes are instantiated, `agent.py` builds `standard_model`, the `agent` graph and `langfuse_handler` at import, and `db/database.py` opens its engines. Importing `agent` without `LLM_API_KEY` raises `ValueError` at import.
- User-facing strings are Spanish; code, logs and docstrings are English. Keep the agent's fallback line verbatim: "Lo siento, no tengo esa información disponible en este momento."
- Tool output sent over WhatsApp is truncated at 1600 chars with the suffix `...\n\n[Respuesta truncada]`.
- `whatsapp_server.py` keeps one lazy module-global `assistant` singleton (`global assistant`) so Twilio is constructed on first message, not at import.

## ANTI-PATTERNS (THIS PROJECT)

- Do not wire a second agent or bypass `chat()`: the webhook, and anything else answering a user, goes through it.
- Do not put business rules in `SYSTEM_PROMPT` (ADR-002); it routes tools and sets tone only.
- Do not read `.env` values directly or add config outside a `*Settings` class.
- Do not import `src.`-prefixed paths or rely on the repo root being on `sys.path`; run entry points as files or with `src/` on the path.

## KNOWN STATE / GOTCHAS

- `langgraph.json` sets `disable_studio_auth: false`, so leaving `COGNITO_REGION`/`COGNITO_USER_POOL_ID` unset runs the graph server open under a single anonymous identity — fine locally, not for deployment.
