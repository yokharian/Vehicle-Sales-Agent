# AGENTS.md

Two independent deployables live in this repo: the Python agent in `backend/` and the Next.js chat front end in `web/`. The agent searches the vehicle catalog, answers company questions from a knowledge base and computes financing plans; it is reached over WhatsApp (Twilio webhook) and over the web chat (LangGraph API). The web app authenticates with Amazon Cognito and sends the access token as a bearer on every HTTP and SSE request.

Backend knowledge is layered: read `backend/AGENTS.md` first, then `backend/src/AGENTS.md`, `backend/src/db/AGENTS.md`, `backend/src/tools/AGENTS.md` and `backend/tests/AGENTS.md` when working in those areas. `web/AGENTS.md` covers the front end. Setup guides and binding decisions live in the root `docs/` folder; architecture lives in the root `README.md`.

## Commands

Backend, from `backend/`:

```bash
uv sync --locked                   # install dependencies
uv run pytest                      # full suite, needs a running Docker daemon
uvx ruff@0.9.10 check .            # lint
uvx ruff@0.9.10 format --check .   # format check
uv run --env-file .env scripts/ingest_csv.py data/sample_vehicles.csv --create-tables
uv run --env-file .env scripts/index_documents.py
uv run --env-file .env src/whatsapp_server.py --host 0.0.0.0 --port 5000
uv run langgraph dev               # LangGraph API used by the web app
docker compose up --build          # app plus pgvector
```

The backend image can be built locally from the repo root:
`docker build -f backend/Dockerfile -t vsa-backend:local backend`.

Front end, from `web/`:

```bash
corepack pnpm install              # pnpm 10.5.1 is pinned; no global pnpm needed
corepack pnpm dev
corepack pnpm build                # static export into web/out
corepack pnpm lint
corepack pnpm format:check
```

## CI and deploy

- `ci.yml` runs on pushes to `master` and pull requests, gated by `dorny/paths-filter@v3`: the backend job (`backend/**`) runs `uv sync --locked`, both ruff checks and `uv run pytest -q` from `backend/`; the web job (`web/**`) runs the pnpm format, lint and build checks from `web/` with dummy `NEXT_PUBLIC_*` values and `AMPLIFY_OUTPUTS_JSON='{"auth":{}}'`.
- `deploy.yml` builds the backend image with `context: ./backend`, pushes it to GitHub Container Registry and signs the digest with cosign.
- `web-deploy.yml` is the only web publisher: it deploys the static export through the Amplify manual deployment API and never runs on pull requests.
- Dependabot groups minor and patch updates; non-major pull requests auto-merge after CI.

CI provisions nothing: the Cognito user pool and app clients, the Amplify app and the OIDC deploy role must exist first — see `docs/DEPLOYMENT.md`.
