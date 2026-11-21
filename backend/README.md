# Vehicle Sales Agent — Backend

An AI-powered vehicle sales assistant that chats with customers over WhatsApp: it searches the vehicle catalog with fuzzy typo tolerance (PostgreSQL fuzzystrmatch), answers company questions from a knowledge base with hybrid BM25 + pgvector retrieval, and calculates financing plans with Decimal-precise math — built with LangGraph, PostgreSQL and FastAPI, managed with `uv`.

Architecture diagrams and request flows: [../README.md#architecture](../README.md#architecture).

## Features

- **AI agent**: LangGraph `create_agent` with structured tool calling
- **WhatsApp integration**: bidirectional messaging via Twilio (TwiML webhooks)
- **Vehicle catalog search**: fuzzy matching with typo tolerance over SQLModel/PostgreSQL
- **Document search**: hybrid retrieval — BM25Plus sparse + pgvector dense, fused with `EnsembleRetriever`; grounded responses only
- **Financing calculator**: Decimal-precise monthly payments and amortization schedules
- **FastAPI server**: production-ready webhook handling with health checks

## Commands

All from this directory, which owns `pyproject.toml`, `uv.lock` and the Docker image. Configure the environment first: `cp .env.example .env`, then edit `.env` with your credentials (full reference in [`.env.example`](.env.example)).

```bash
uv sync --locked                                             # install deps (Python 3.12 from .python-version)
docker compose up -d db                                      # PostgreSQL with pgvector for development
uv run --env-file .env scripts/ingest_csv.py data/sample_vehicles.csv --create-tables
uv run --env-file .env scripts/index_documents.py            # --file <path> for one doc, --force to rebuild
uv run --env-file .env src/whatsapp_server.py --host 0.0.0.0 --port 5000
uv run langgraph dev                                         # LangGraph API used by the web app in web/
docker compose up --build                                    # app + pgvector; ingests on startup
vercel deploy --prod                                         # builds backend/Dockerfile, serves it with Fluid Compute
uv run pytest                                                # full suite — REQUIRES a running Docker daemon
uvx ruff check . && uvx ruff format .                        # ruff is configured but NOT installed in .venv
```

The `docker compose up --build` container runs CSV ingestion on startup, then serves the WhatsApp server on port 5000. The LangGraph API reads `langgraph.json` in this directory.

## Usage

Configure the Twilio webhook URL — `http://your-server:5000/whatsapp/webhook`
— as described in [../docs/WHATSAPP.md](../docs/WHATSAPP.md). Example queries:

```text
You: ¿Qué documentos necesito para comprar un auto?
You: Quiero comprar un coche BMW
You: ¿Hay devolución?
You: Busco onda o bolbo baratos
You: ¿Dónde están las sedes de kavak?
You: wolksvagen del año
You: nasda y nisan con el menor km
You: ¿Cómo funciona el plan de pago a meses?

# invalid query (grounded responses only):
You: ¿En qué año se fundó kavak?
```

## API endpoints

When running the WhatsApp server:

- `POST /whatsapp/webhook` — handle incoming WhatsApp messages (Twilio)
- `GET /whatsapp/webhook` — webhook verification
- `GET /health` — health check
- `POST /send-message` — send a WhatsApp message programmatically
- `GET /docs`, `GET /redoc` — auto-generated API documentation

## Testing

`uv run pytest` requires a running Docker daemon: the suite provisions real
PostgreSQL + pgvector containers via
[testcontainers](https://testcontainers-python.readthedocs.io/) instead of
mocking the database, and embedding calls are replaced with deterministic
fakes, so no API keys are needed. Details and troubleshooting:
[../docs/DOCKER.md](../docs/DOCKER.md).

## Deployment

The image pipeline (GHCR + cosign) and the Vercel Fluid Compute deployment
behind Kong are documented in [../docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).

## Documentation

- [Docker setup](../docs/DOCKER.md) — deployment and testing with Docker
- [WhatsApp setup](../docs/WHATSAPP.md) — Twilio account, webhook and server configuration
- [Deployment](../docs/DEPLOYMENT.md) — image pipeline, Vercel Fluid Compute, Amplify
- [Product Requirement Documents](../docs/Product%20Requirement%20Documents/) — `vehicle_catalog.md`, `knowledge_search.md`, `financing_calculator.md`
- [Architecture Decision Records](../docs/Architecture%20Decision%20Records/) — ADR-001 through ADR-006
- [Challenge description](../docs/Challenge.en.md) / [Challenge description (Spanish)](../docs/Challenge.es.md)
