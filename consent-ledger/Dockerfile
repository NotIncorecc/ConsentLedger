# ─── Build stage: compile gnark prover binary ─────────────────────────────────
# Build context is consent-ledger/ so circuits/ is directly accessible.
FROM golang:1.22-alpine AS go_builder

WORKDIR /build
COPY circuits/ .
RUN go mod download && go build -o prover cmd/main.go

# ─── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="ConsentLedger Backend"
LABEL org.opencontainers.image.description="Phase 3 FastAPI backend for ConsentLedger ZKP dApp"

WORKDIR /app

# Install system dependencies required by py-algorand-sdk
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy gnark prover binary and keys from build stage
COPY --from=go_builder /build/prover /app/prover
COPY --from=go_builder /build/keys/ /app/keys/

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source
COPY backend/ .

# Override config.py defaults so the prover is found inside the container.
# Local dev still uses ../circuits/prover via the .env file.
ENV PROVER_BINARY=/app/prover
ENV PROVER_KEYS_DIR=/app/keys

EXPOSE 8000

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
