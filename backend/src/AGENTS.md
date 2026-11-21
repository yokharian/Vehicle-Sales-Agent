# src — APPLICATION CORE

The running service: one LangGraph agent, one FastAPI webhook server, one settings module, plus the `db/` and `tools/` packages. Everything here is imported as a FLAT top-level module (`config`, `agent`, `db.database`), not as `src.*`.

Entry points: `langgraph.json` maps the graph to `./src/agent.py:agent` and auth to `./src/auth.py:auth`; Docker runs `src/whatsapp_server.py`.

## KNOWN STATE / GOTCHAS

- `langgraph.json` sets `disable_studio_auth: false`, so leaving `COGNITO_REGION`/`COGNITO_USER_POOL_ID` unset runs the graph server open under a single anonymous identity — fine locally, not for deployment.
