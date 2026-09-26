# Docker Setup

This document explains how to run the Commercial Agent with Docker: the
application stack for development and deployment, and the Docker requirement
for running the test suite.

## Prerequisites

1. **Docker** and **Docker Compose** installed
2. **Environment variables** configured (see below)

> **Docker is also required to run the tests.** The test suite spins up real
> PostgreSQL + pgvector containers with
> [testcontainers](https://testcontainers-python.readthedocs.io/) instead of
> mocking the database, so `uv run pytest` needs a working Docker daemon.

## Environment Variables

Configuration is loaded with `pydantic-settings`, which reads a `.env` file in
the project root (see `.env.example` for the full reference)

The `db` service uses the `pgvector/pgvector:pg16` image because the document
search index requires the PostgreSQL `pgvector` extension.

## Quick Start

### Option 1: Using Docker directly

1. **Build the image:**
   ```bash
   docker build -t commercial-agent .
   ```

2. **Run with environment variables:**
   ```bash
   docker run -p 5000:5000 --env-file .env commercial-agent
   ```

### Option 2: Using Docker Compose

1. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

2. **Build and start the services:**
   ```bash
   docker compose up --build
   ```

3. **Access the application:**
   - WhatsApp webhook: `http://localhost:5000/whatsapp/webhook`
   - Health check: `http://localhost:5000/health`
   - API docs: `http://localhost:5000/docs`

## What Happens During Startup

1. **CSV Ingestion**: The container first runs the CSV ingestion script to populate the database with vehicle data
2. **Database Setup**: Creates the vehicle catalog tables
3. **WhatsApp Server**: Starts the FastAPI server with WhatsApp webhook endpoints

## Container Features

- **uv-managed dependencies**: `uv sync --frozen` against `uv.lock` during the image build
- **Automatic CSV Ingestion**: Runs `scripts/ingest_csv.py --create-tables` on startup
- **Health Checks**: Built-in health monitoring
- **Error Handling**: Fails fast if CSV ingestion fails
- **Logging**: Comprehensive logging to stdout
- **Database Integration**: PostgreSQL with pgvector and persistent volumes

## Running the Tests

The test suite requires Docker because it provisions throwaway PostgreSQL
containers (pgvector/pgvector:pg16) via testcontainers:

```bash
uv run pytest
```

- Catalog, document search, and combined-workflow tests run against a real
  PostgreSQL + pgvector instance inside a container.
- Embedding calls are replaced with deterministic fake embeddings, so no API
  keys or network access to providers are needed for tests.
- The container is started once per test session and stopped automatically.

## Local Development (without Docker deployment)

Run the server against a local PostgreSQL instance:

```bash
uv run --env-file .env python src/whatsapp_server.py --host 0.0.0.0 --port 5000
```

`--env-file` loads `.env` into the process environment (uv native support);
`pydantic-settings` also reads `.env` from the working directory for the
application settings.

## Troubleshooting

### CSV Ingestion Fails
- Check that `data/sample_vehicles.csv` exists
- Verify database connection
- Check logs: `docker compose logs commercial-agent`

### WhatsApp Webhook Issues
- Ensure Twilio webhook URL points to: `http://your-domain:5000/whatsapp/webhook`
- Verify Twilio credentials are correct
- Check that the server is accessible from the internet

### Database Connection Issues
- Ensure PostgreSQL container is running: `docker compose ps`
- Check database logs: `docker compose logs db`
- Verify environment variables

### Tests Fail to Start Containers
- Verify the Docker daemon is running: `docker info`
- Ensure your user can run containers without errors: `docker run --rm hello-world`

## Development

### Accessing the Database
```bash
# Connect to PostgreSQL
docker compose exec db psql -U postgres -d commercial_agent

# Or use a GUI tool with:
# Host: localhost
# Port: 5432
# Database: commercial_agent
# Username: postgres
# Password: password
```

## Production Deployment

For production deployment:

1. **Use environment-specific configuration**
2. **Set up proper secrets management**
3. **Configure reverse proxy (nginx)**
4. **Set up SSL/TLS certificates**
5. **Configure monitoring and alerting**
6. **Use production database with proper backup strategy**

## API Endpoints

- `GET /health` - Health check
- `POST /whatsapp/webhook` - WhatsApp webhook (Twilio)
- `GET /whatsapp/webhook` - WhatsApp webhook verification
- `POST /send-message` - Send WhatsApp message via API
- `GET /docs` - API documentation (Swagger)
- `GET /redoc` - Alternative API documentation
