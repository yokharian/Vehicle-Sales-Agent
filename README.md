# Vehicle Sales Agent

A vehicle sales assistant with two deployables in one repo:

- `backend/` is the Python agent. It searches the vehicle catalog with typo-tolerant fuzzy matching, answers company questions from a knowledge base with hybrid BM25 + pgvector retrieval, and computes financing plans. It serves WhatsApp through a Twilio webhook and the LangGraph API that the web app talks to.
- `web/` is the Next.js chat front end. It streams answers from the same LangGraph API and authenticates every HTTP and SSE request with a Cognito bearer token.

## Layout

| Path | What lives there | Stack | Docs |
|---|---|---|---|
| `backend/` | Agent, tools, WhatsApp server, tests, Docker image, Compose stacks | Python 3.12, LangGraph, FastAPI, SQLModel/PostgreSQL + pgvector, uv | [backend/README.md](backend/README.md) |
| `backend/src/` | The application core, flat imports (`from config import ...`) | Python | [backend/src/AGENTS.md](backend/src/AGENTS.md) |
| `backend/tests/` | pytest suite, real Postgres through testcontainers | pytest | [backend/tests/AGENTS.md](backend/tests/AGENTS.md) |
| `backend/docs/` | ADRs, PRDs, Docker and WhatsApp setup | Markdown | [backend/docs/](backend/docs/) |
| `web/` | Chat front end, statically exported | Next.js 16, React 19, assistant-ui, Tailwind v4, pnpm | |
| `.github/workflows/` | CI for both stacks, container image and hosting pipelines | GitHub Actions | |
| `AGENTS.md` | Repo level knowledge for agents | Markdown | [AGENTS.md](AGENTS.md) |

There is no Python manifest or npm workspace at the repo root. Every command runs from the directory that owns it: `backend/` for uv and Docker, `web/` for pnpm and Next.js.

## Prerequisites

- Python 3.12 and [`uv`](https://docs.astral.sh/uv/)
- Node.js and pnpm 10.5.1 (through `corepack enable`)
- Docker and Docker Compose, for the backend stack and for the test suite
- A model provider key (OpenAI or OpenRouter) for chat and embeddings
- Twilio credentials for the WhatsApp path
- A Supabase Postgres project with the `pgvector` extension for the catalog and the knowledge base

## Backend quickstart

```bash
cd backend
uv sync --locked
cp .env.example .env      # then fill in the keys
docker compose up -d db
uv run --env-file .env scripts/ingest_csv.py data/sample_vehicles.csv --create-tables
uv run --env-file .env scripts/index_documents.py
```

Run the LangGraph API that the web app connects to:

```bash
cd backend
uv run langgraph dev
```

Run the WhatsApp webhook server instead:

```bash
cd backend
uv run --env-file .env src/whatsapp_server.py --host 0.0.0.0 --port 5000
```

Backend tests need a running Docker daemon, because the suite provisions real Postgres containers:

```bash
cd backend
uv run pytest
```

## Web quickstart

```bash
cd web
pnpm install
pnpm dev
```

The build needs these values, read from `web/.env.local` locally and from GitHub secrets in CI:

| Variable | Meaning |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the LangGraph API, for example `https://api.yokharian.dev/vsagent` |
| `NEXT_PUBLIC_ASSISTANT_ID` | Graph id to talk to, `agent` |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Cloudflare Turnstile site key for the guest flow |
| `AMPLIFY_OUTPUTS_JSON` | Cognito config for the web app, written to `web/amplify_outputs.json` during the build |

```bash
cd web
pnpm build            # static export into web/out
pnpm lint
pnpm format:check
```

## CI and deploy

- **`.github/workflows/ci.yml`** runs on pushes to `master` and on pull requests. It installs uv, syncs the locked dependencies, checks the code with ruff and runs the pytest suite. The job sets `working-directory: backend`, so every step runs inside `backend/`.
- **`.github/workflows/deploy.yml`** builds the backend image from `backend/Dockerfile` with the `./backend` build context, pushes it to GitHub Container Registry on `master`, on `v*.*.*` tags and on manual dispatch, and signs the digest with cosign.
- **`.github/workflows/web-deploy.yml`** builds the static export and publishes it to Amplify Hosting through the manual deployment API. It runs on pushes that touch `web/` and on manual dispatch. The Amplify app has no connected repository and auto-build disabled, so GitHub Actions is the only builder and publisher.

## AWS provisioning precondition

The web app talks to AWS hosted resources, and CI creates none of them.

- **Amazon Cognito user pool** (us-east-1) with a registered app client and a guest app client. The registered client backs sign-in and sign-up, the guest client backs the "Continue as guest" flow. The backend validates access tokens against the pool JWKS once `COGNITO_REGION` and `COGNITO_USER_POOL_ID` are set, and runs open while they are unset.
- **Amplify app** for hosting the static export, created with no connected repository, no auto branch creation and `enableAutoBuild: false` on its branch.
- **GitHub secrets and variables**: secrets `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_ASSISTANT_ID`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, `AMPLIFY_OUTPUTS_JSON` and `AWS_DEPLOY_ROLE_ARN`; variables `AMPLIFY_APP_ID`, `AMPLIFY_BRANCH` and `AWS_REGION`.

The Postgres database is Supabase rather than AWS, but the `pgvector` extension has to be enabled there before the document search works.

## Further reading

- [Backend README](backend/README.md): features, configuration, API endpoints, project structure
- [Docker setup](backend/docs/DOCKER.md)
- [WhatsApp setup](backend/docs/WHATSAPP.md)
- [Architecture Decision Records](backend/docs/Architecture%20Decision%20Records/)
- [Product Requirement Documents](backend/docs/Product%20Requirement%20Documents/)
