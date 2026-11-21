# src — APPLICATION CORE

The running service: one LangGraph agent, one FastAPI webhook server, one settings module, plus the `db/` and `tools/` packages. Everything here is imported as a FLAT top-level module (`config`, `agent`, `db.database`), not as `src.*`.

Entry points: `langgraph.json` maps the graph to `./src/agent.py:agent` and auth to `./src/auth.py:auth`; Docker runs `src/whatsapp_server.py`.

## KNOWN STATE / GOTCHAS

- `langgraph.json` sets `disable_studio_auth: false`, so leaving `COGNITO_REGION`/`COGNITO_USER_POOL_ID` unset runs the graph server open under a single anonymous identity — fine locally, not for deployment.
- `auth._decode_token` is synchronous on purpose: `PyJWKClient` fetches the JWKS over HTTP with `urllib`, which blocks the event loop (LangGraph dev aborts on it via blockbuster), so callers run it in a worker thread.
- `auth.add_owner` stamps `metadata.owner` on thread creation and returns the `{"owner": <identity>}` filter for every other thread/run event; that filter is what keeps conversations private per user.
- `config._normalize_postgres_scheme` rewrites bare `postgresql://` to `+psycopg2` (psycopg v3 is not a dependency) and drops pooler-only query params (`pgbouncer`, `supa`) because libpq rejects them.
- `DATABASE_URI=""` counts as unset: the LangGraph runtime exports it empty for the in-memory edition.
