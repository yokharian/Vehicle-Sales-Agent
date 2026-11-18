# PROJECT KNOWLEDGE BASE

**Scope:** the repository root of the Vehicle Sales Agent monorepo.

Two independent deployables live here: the Python agent in `backend/` and the Next.js chat front end in `web/`. This file covers the layout and the rules that span both. The backend has its own deep knowledge base at `backend/AGENTS.md`, with more in `backend/src/AGENTS.md`, `backend/src/db/AGENTS.md`, `backend/src/tools/AGENTS.md` and `backend/tests/AGENTS.md`. Read those before touching backend code; this file does not repeat them.

## OVERVIEW

The agent searches the vehicle catalog, answers company questions from a knowledge base and computes financing plans. It is reached over WhatsApp (Twilio webhook) and over the web chat (LangGraph API). The web app authenticates with Amazon Cognito and sends the access token as a bearer on every HTTP and SSE request.

## STRUCTURE

```
vehicle-sales-agent/
├── backend/                 # Python agent, all backend knowledge lives here
│   ├── src/                 # app core, flat imports (config, agent, db.*, tools.*)
│   ├── scripts/             # ingest_csv.py, index_documents.py, html2text_cli.py
│   ├── tests/               # pytest suite, Docker and testcontainers required
│   ├── docs/                # ADRs, PRDs, DOCKER.md, WHATSAPP.md
│   ├── data/                # sample_vehicles.csv, documents/kavak.md
│   ├── docker/              # WhatsApp and minimal Compose stacks
│   ├── Dockerfile           # uv based image, build context is backend/
│   ├── langgraph.json       # graph src/agent.py:agent, auth src/auth.py:auth
│   ├── pyproject.toml       # Python project, owns uv.lock
│   └── README.md            # backend README
├── web/                     # Next.js chat front end (static export)
├── .github/workflows/       # CI, backend image pipeline, web publish pipeline
├── .gitignore               # shared ignore rules for both stacks
├── LICENSE
├── README.md                # repo overview, quickstarts, CI and deploy
└── AGENTS.md                # this file
```

## WHERE TO LOOK

| Task | Location | Notes |
|---|---|---|
| Agent behaviour, prompt, tools | `backend/src/agent.py`, `backend/src/tools/` | see `backend/AGENTS.md` |
| Catalog, knowledge base, financing | `backend/src/db/`, `backend/src/tools/` | scoring happens in Postgres, not Python |
| Backend configuration surface | `backend/src/config.py`, `backend/.env.example` | one pydantic-settings class per concern |
| WhatsApp webhook and endpoints | `backend/src/whatsapp_server.py` | `/whatsapp/webhook`, `/health`, `/send-message` |
| Binding backend decisions | `backend/docs/Architecture Decision Records/`, `backend/docs/Product Requirement Documents/` | ADR and PRD per tool |
| Front end chat surface | `web/src/` | assistant-ui primitives, LangGraph runtime |
| Front end auth | `web/src/providers/Auth.tsx`, `web/src/lib/guest-session.ts` | Cognito plus the guest token store |
| Repository layout, CI, deploy | `README.md`, `.github/workflows/` | |

## CONVENTIONS

- One project per directory, no workspace manifests at the root. `uv` commands run from `backend/`, `pnpm` commands run from `web/`. There is no root `package.json` and no root `pyproject.toml`.
- Docs live next to what they describe: `backend/README.md` and `backend/docs/` for the agent, root `README.md` and `AGENTS.md` for the repo.
- Secrets never enter the repo. `.env`, `.env.local` and generated `amplify_outputs.json` are gitignored.
- Backend money is `Decimal`; the model never computes figures. Backend user-facing strings are Spanish, code and logs are English. The front end ships English and Spanish copy as the product needs.
- The web app is a static export (`output: "export"` in `web/next.config.mjs`). No server runtime, no API routes, no middleware.

## ANTI-PATTERNS (THIS PROJECT)

- Do not run uv, pnpm, Next.js or Docker commands from the repo root and expect them to work.
- Do not reintroduce a Python or npm workspace root to "simplify" installs; the two stacks are deployed independently.
- Do not commit `.env`, `.env.local`, `web/amplify_outputs.json` or any generated build output.
- Do not merge backend knowledge into this file; extend `backend/AGENTS.md` instead.
- Do not add a Vercel or Amplify git integration. GitHub Actions is the only builder and publisher.

## COMMANDS

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
docker build -f backend/Dockerfile -t vsa-backend:local backend
```

Front end, from `web/`:

```bash
pnpm install
pnpm dev
pnpm build                         # static export into web/out
pnpm lint
pnpm format:check
```

## NOTES

- The backend moved into `backend/` in this branch. Every backend path in this file is relative to `backend/`, and the Docker build context is `backend/`, not the repo root.
- `.github/workflows/ci.yml` runs the backend steps with `working-directory: backend`. The repo root holds no Python project, so a root-scoped `uv sync --locked` fails there (exit 2).
- `.github/workflows/deploy.yml` builds with `context: ./backend` and `file: ./backend/Dockerfile`.
- The Amplify app for the front end has no connected repository and auto-build disabled. The publish workflow creates a deployment through the Amplify manual deployment API.
- Backend CI does not run the web build, and the web workflow does not run the backend suite.
