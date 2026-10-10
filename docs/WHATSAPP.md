# WhatsApp Setup Guide

This document explains how to connect the vehicle sales assistant to WhatsApp
through Twilio: account setup, environment configuration, server startup, and
webhook wiring.

## Overview

The assistant communicates over WhatsApp bidirectionally using Twilio:

- Incoming messages hit a **FastAPI webhook** (`src/whatsapp_server.py`)
- Each message is forwarded to the **LangGraph agent** (`src/agent.py`), which
  uses the catalog search, document search, and financing calculator tools
- The reply is returned as a **TwiML response**; outgoing messages are sent
  programmatically through the Twilio REST API

## Prerequisites

1. A **Twilio account** — https://www.twilio.com
2. API keys for the agent providers (OpenAI or OpenRouter)
3. PostgreSQL with pgvector, running and seeded (see the
   [README](../README.md) Quick Start or [docs/DOCKER.md](DOCKER.md))

## Twilio Setup

1. Get your **Account SID** and **Auth Token** from the Twilio Console
2. Set up the **WhatsApp Sandbox** for development, or request
   **WhatsApp Business API** access for production
3. Note your WhatsApp sender number (Twilio sandbox number for development)

## Environment Variables

Create a `.env` file in the project root (see [`.env.example`](../.env.example)):

The Twilio variables are loaded by `TwilioSettings` (pydantic-settings) and
the WhatsApp number must use the `whatsapp:+<number>` prefix format.

## Running the Server

```bash
uv run --env-file .env python src/whatsapp_server.py --host 0.0.0.0 --port 5000
```

Options: `--host` (default `0.0.0.0`), `--port` (default `5000`), and
`--debug` to run uvicorn with debug logging.

Or deploy everything with Docker Compose (container starts with CSV ingestion
and then serves the WhatsApp server) — see [docs/DOCKER.md](DOCKER.md).

## Webhook Configuration

1. Start the server and note the public webhook URL:
   `http://your-server:5000/whatsapp/webhook`
2. Configure this URL as the **"WHEN A MESSAGE COMES IN"** webhook in your
   Twilio WhatsApp sender or sandbox settings
3. Send a message to the connected number — the agent replies automatically

The `GET /whatsapp/webhook` route answers webhook verification challenges
(`hub.challenge`) for Meta-style verification flows.

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/whatsapp/webhook` | POST | Handle incoming WhatsApp messages (Twilio) |
| `/whatsapp/webhook` | GET | Webhook verification (`hub.challenge`) |
| `/health` | GET | Health check (`{"status": "healthy", ...}`) |
| `/send-message` | POST | Send a WhatsApp message programmatically |
| `/docs` | GET | Swagger API documentation |
| `/redoc` | GET | ReDoc API documentation |

The `POST /send-message` endpoint accepts:

```json
{"to_number": "+1234567890", "message": "Hello"}
```

The Twilio client is initialized lazily on the first webhook or send-message
request, so the server can start even with incomplete Twilio credentials.

## Message Handling

- Incoming messages are logged with sender and body, then answered by the AI
  agent; only catalog and knowledge-base information is used (grounded
  responses — the agent will not invent data)
- Replies are truncated at **1600 characters** (`...\n\n[Respuesta truncada]`)
  to respect WhatsApp message limits
- TwiML (`MessagingResponse`) formats the reply; errors return a polite
  Spanish apology message instead of crashing the webhook

## Troubleshooting

| Symptom | Fix |
|---|---|
| `"Twilio client not initialized"` / init error at first request | Check `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` |
| `"Twilio WhatsApp number not configured"` | Set `TWILIO_WHATSAPP_NUMBER` (with `whatsapp:` prefix) |
| Webhook not receiving messages | Verify the webhook URL in the Twilio console and that the server is publicly reachable |
| Message not sending | Check the destination number format and the sender number prefix |
| Agent errors on every message | Verify the model provider keys (`OPENROUTER_API_KEY` or `OPENAI_API_KEY`) and `DATABASE_URL` |

Enable debug logging with the `--debug` flag; application logs go to stdout.

## Testing Without Twilio

Exercise the agent directly without any WhatsApp wiring:

```bash
uv run --env-file .env python -c "
import sys; sys.path.insert(0, 'src')
from agent import chat
print(chat('Busco un Toyota 2020')['response'])
"
```

The test suite covers the server routes and agent wiring with testcontainers
(see the README Testing section); no Twilio credentials are needed.

## Security Notes

- Keep Twilio credentials out of version control (`.env` is git-ignored)
- Use HTTPS in production (terminate TLS at a reverse proxy)
- Validate incoming webhook requests (e.g., Twilio request signature
  validation) before trusting webhook payloads
- Apply rate limiting for production deployments

## Production Deployment

- Deploy with Docker Compose or a container platform — see
  [docs/DOCKER.md](DOCKER.md)
- Use environment-specific configuration and a secrets manager
- Set up logging, monitoring, and alerting on the `/health` endpoint
- Use a production PostgreSQL instance with backups (the Compose `db` service
  is for development)
