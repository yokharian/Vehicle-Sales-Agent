# 🚗 Vehicle Sales Agent

An AI-powered vehicle sales assistant that chats with customers over WhatsApp: it searches the vehicle catalog with fuzzy typo tolerance, answers company questions from a knowledge base with hybrid (BM25 + pgvector) retrieval, and calculates financing plans — built with LangGraph, PostgreSQL, and FastAPI, managed with `uv`.

## Diagram

![AI Sales Agent.svg](docs/diagrams/AI%20Sales%20Agent.svg)

## ✨ Features

- 🤖 **AI-Powered Agent**: LangGraph `create_agent` with structured tool calling
- 📱 **WhatsApp Integration**: Bidirectional messaging via Twilio (TwiML webhooks)
- 🔍 **Vehicle Catalog Search**: Fuzzy matching with typo tolerance (rapidfuzz) over SQLModel/PostgreSQL
- 📄 **Document Search**: Hybrid retrieval — BM25Plus sparse + pgvector dense, fused with `EnsembleRetriever`
- 💰 **Financing Calculator**: Decimal-precise monthly payments and amortization schedules
- 🌐 **FastAPI Server**: Production-ready webhook handling with health checks

![Features High Level Diagram.svg](docs/diagrams/Features%20High%20Level%20Diagram.svg)

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- **Docker** and **Docker Compose** for the app stack — and required to run the test suite (testcontainers)
- API keys: OpenAI or OpenRouter for chat/embeddings, Twilio for WhatsApp

### Installation

1. **Clone the repository and install dependencies:**
   ```bash
   git clone <repository-url>
   cd vehicle-sales-agent
   uv sync
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Start PostgreSQL with pgvector (or use Docker Compose, below):**
   ```bash
   docker compose up -d db
   ```

4. **Ingest the vehicle catalog and index the knowledge base:**
   ```bash
   uv run --env-file .env python scripts/ingest_csv.py data/sample_vehicles.csv --create-tables
   uv run --env-file .env python scripts/index_documents.py
   ```

5. **Run the WhatsApp server:**
   ```bash
   uv run --env-file .env python src/whatsapp_server.py --host 0.0.0.0 --port 5000
   ```

### Using Docker Compose

For a full deployment (app + database), see [docs/DOCKER.md](docs/DOCKER.md):

```bash
docker compose up --build
```

The container runs CSV ingestion on startup, then serves the WhatsApp server on port `5000`.

## 💬 Usage

The agent answers over WhatsApp. Example queries:

```
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

Configure the Twilio webhook URL: `http://your-server:5000/whatsapp/webhook`

## ⚙️ Configuration

All configuration is loaded with `pydantic-settings` from `.env` (see [`.env.example`](.env.example) for the full reference):

| Variable | Purpose |
|---|---|
| `MODEL_PROVIDER` | Chat provider: `openai` or `openrouter` (default `openrouter`) |
| `DEFAULT_MODEL` | Chat model (default `gpt-5.6-luna`) |
| `VERBOSE` | Agent debug output (optional, default `false`) |
| `OPENAI_API_KEY` / `OPENROUTER_API_KEY` | Provider API keys |
| `DOCUMENT_EMBEDDING_PROVIDER` | Embedding provider: `openai` or `openrouter` |
| `DOCUMENT_EMBEDDING_MODEL` | Embedding model (falls back to provider default) |
| `DATABASE_URL` | PostgreSQL connection string |
| `DB_ECHO` | Echo SQL statements (optional, default `false`) |
| `SUPABASE_URL` | Optional — set to enable Supabase JWT auth; omit to run open (anonymous) |
| `SUPABASE_AUDIENCE` | Expected token `aud` claim (optional, default `authenticated`) |
| `TWILIO_*` | Twilio account SID, auth token, WhatsApp number |

## 🔧 How It Works

### Vehicle Search Flow
1. User query received (WhatsApp)
2. The agent calls the `catalog_search` tool with the raw user input
3. Fuzzy matching normalizes make/model typos (rapidfuzz)
4. PostgreSQL query filters by price, features, mileage, make, and model
5. Results ranked and formatted back to the user

### Document Search Flow
1. Knowledge-base documents (`.md`) are chunked (500 chars, 100 overlap) at headings
2. Chunks embedded via OpenAI/OpenRouter and stored in PostgreSQL `pgvector`
3. Hybrid retrieval: BM25Plus sparse + dense vector search, fused by `EnsembleRetriever`
4. Relevant chunks ground the agent's response; no invented information

### Financing Flow
- Monthly payments and amortization schedules computed with `Decimal` arithmetic and `ROUND_HALF_UP`

## 🧪 Testing

```bash
uv run pytest
```

**Docker is required to run the tests.** The suite provisions real PostgreSQL + pgvector containers via [testcontainers](https://testcontainers-python.readthedocs.io/) instead of mocking the database; embedding calls are replaced with deterministic fakes, so no API keys are needed. See [docs/DOCKER.md](docs/DOCKER.md) for details and troubleshooting.

## 📊 API Endpoints

When running the WhatsApp server:

- `POST /whatsapp/webhook` - Handle incoming WhatsApp messages (Twilio)
- `GET /whatsapp/webhook` - Webhook verification
- `GET /health` - Health check endpoint
- `POST /send-message` - Send a WhatsApp message programmatically
- `GET /docs` - FastAPI auto-generated documentation (Swagger)
- `GET /redoc` - ReDoc API documentation

## 📁 Project Structure

```
vehicle-sales-agent/
│
├── src/
│   ├── agent.py                     # LangGraph agent (catalog + document search tools)
│   ├── config.py                    # pydantic-settings configuration
│   ├── whatsapp_server.py           # FastAPI WhatsApp webhook server
│   ├── db/                          # Database layer (engine, DAOs, document loader)
│   └── tools/                       # LangChain tools
│       ├── catalog_search.py        # Vehicle catalog search (fuzzy matching)
│       ├── document_search.py       # Hybrid document search (BM25 + pgvector)
│       └── financing_calculator.py  # Financing calculator
│
├── scripts/
│   ├── ingest_csv.py                # CSV vehicle data ingestion
│   ├── index_documents.py           # Knowledge-base indexing into pgvector
│   └── html2text_cli.py             # HTML → markdown conversion utility
│
├── data/
│   ├── documents/kavak.md           # Knowledge base (company information)
│   └── sample_vehicles.csv          # Sample vehicle data
│
├── docs/                            # Documentation (see below)
├── tests/                           # Test suite (testcontainers)
├── Dockerfile                       # uv-based container image
└── docker-compose.yml               # App + PostgreSQL/pgvector stack
```

## 📚 Documentation

- [Docker Setup Guide](docs/DOCKER.md) - Deployment and testing with Docker
- [WhatsApp Setup Guide](docs/WHATSAPP.md) - Twilio account, webhook, and server configuration
- [Product Requirement Documents](docs/Product%20Requirement%20Documents/) - `vehicle_catalog.md`, `knowledge_search.md`, `financing_calculator.md`
- [Architecture Decision Records](docs/Architecture%20Decision%20Records/) - ADR-001 through ADR-006 (technology stack, structured tool calling, PostgreSQL datastore, grounded responses, evaluation, hybrid retrieval)
- [Challenge description](docs/Challenge.en.md) / [Descripción del reto](docs/Challenge.es.md)

### External Resources
- [LangChain Documentation](https://python.langchain.com/docs/introduction/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)
- [pgvector](https://github.com/pgvector/pgvector)
