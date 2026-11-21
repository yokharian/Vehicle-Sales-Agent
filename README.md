# Vehicle Sales Agent

A vehicle sales assistant with two deployables in one repo:

- `backend/` is the Python agent. It searches the vehicle catalog with typo-tolerant fuzzy matching, answers company questions from a knowledge base with hybrid BM25 + pgvector retrieval, and computes financing plans. It serves WhatsApp through a Twilio webhook and the LangGraph API that the web app talks to.
- `web/` is the Next.js chat front end. It streams answers from the same LangGraph API and authenticates every HTTP and SSE request with a Cognito bearer token.

There is no Python manifest or npm workspace at the repo root. Every command runs from the directory that owns it: setup and commands live in [backend/README.md](backend/README.md) and [web/README.md](web/README.md); setup guides in [docs/DOCKER.md](docs/DOCKER.md) and [docs/WHATSAPP.md](docs/WHATSAPP.md).

## Architecture

How the vehicle sales assistant is put together: the two deployables, the request paths, and the three agent tools. All backend commands referenced here run from `backend/`.

### System overview

![AI Sales Agent](docs/diagrams/AI%20Sales%20Agent.svg)

- `web/` streams answers from the LangGraph API (`src/agent.py`), sending a Cognito access token as a bearer on every HTTP and SSE request.
- WhatsApp messages reach the FastAPI webhook server (`src/whatsapp_server.py`) through Twilio and are answered by the same agent over `chat()`.

### Feature map

![Features High Level Diagram](docs/diagrams/Features%20High%20Level%20Diagram.svg)

Excalidraw sources sit next to the SVGs in `docs/diagrams/`.

### Vehicle search flow

1. A user query arrives (WhatsApp or web chat).
2. The agent calls the `catalog_search` tool with the raw user input.
3. Fuzzy matching normalizes make/model typos (PostgreSQL `fuzzystrmatch`); scoring runs in SQL, not Python.
4. PostgreSQL filters by price, features, mileage, make and model.
5. Results are ranked and formatted back to the user.

### Document search flow

1. Knowledge-base documents (`.md`/`.txt`) are chunked (500 chars, 100 overlap) at headings.
2. Chunks are embedded and stored in PostgreSQL with `pgvector`.
3. Hybrid retrieval — BM25Plus sparse + dense vector search — is fused by `EnsembleRetriever`.
4. Relevant chunks ground the agent's response; empty retrieval is reported as empty, never filled from model knowledge (ADR-004).

### Financing flow

- Monthly payments and amortization schedules are computed with `Decimal` arithmetic and `ROUND_HALF_UP`; the LLM never computes figures.

Binding decisions live in the [Architecture Decision Records](docs/Architecture%20Decision%20Records/) (ADR-001 through ADR-006) and the [Product Requirement Documents](docs/Product%20Requirement%20Documents/).

## CI and deploy

- **`ci.yml`** gates two independent jobs behind a paths filter: the backend job (`backend/**`) runs `uv sync --locked`, the ruff lint and format checks, and pytest; the web job (`web/**`) runs the pnpm format, lint and build checks with dummy public values.
- **`deploy.yml`** builds the backend image from `backend/Dockerfile` with the `./backend` build context, pushes it to GitHub Container Registry and signs it with cosign.
- **`web-deploy.yml`** publishes the static export to Amplify Hosting through the manual deployment API. It is the only web publisher and never runs on pull requests.
- Dependabot groups minor and patch updates; non-major pull requests auto-merge after CI.

CI provisions nothing. The Cognito user pool and app clients, the Amplify app, the OIDC deploy role and the GitHub secrets must exist first — see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Further reading

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — deployment pipelines and AWS provisioning
- [docs/DOCKER.md](docs/DOCKER.md) and [docs/WHATSAPP.md](docs/WHATSAPP.md) — setup guides
- [Architecture Decision Records](docs/Architecture%20Decision%20Records/) and [Product Requirement Documents](docs/Product%20Requirement%20Documents/) — binding decisions
- [backend/README.md](backend/README.md) — features, commands, API endpoints, testing
- [web/README.md](web/README.md) — front end commands
