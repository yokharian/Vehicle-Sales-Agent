# uv-managed Python 3.12 image (uv + Python bundled)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set working directory
WORKDIR /app

# Install curl for the container health check
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better Docker layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy the entire project
COPY . .

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Startup script: CSV ingestion first, then the WhatsApp server
RUN set -e; \
    cat > /app/start.sh <<'EOF' && chmod +x /app/start.sh
#!/usr/bin/env sh
set -e

echo "🚀 Starting Commercial Agent Setup..."
echo "📊 Step 1: Running CSV ingestion..."
cd /app
uv run python scripts/ingest_csv.py data/sample_vehicles.csv --create-tables

echo "✅ CSV ingestion completed successfully"
echo "📱 Step 2: Starting WhatsApp server..."
exec uv run python src/whatsapp_server.py --host 0.0.0.0 --port 5000
EOF

# Expose the port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the startup script
CMD ["/app/start.sh"]
