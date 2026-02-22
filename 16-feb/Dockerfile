# ---------------------------------------------------------------------------
# Stage 1: Install Python dependencies in an isolated prefix
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Minimal production runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Security: run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy pre-built dependencies from builder stage
COPY --from=builder /install /usr/local

# Copy application code (no tests, no dev files)
COPY app/ ./app/

# Set ownership and drop privileges
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Health check using the /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8080}/api/health')" || exit 1

# Cloud Run sets PORT env var; --workers=1 is optimal for single-container
# Cloud Run instances (concurrency is handled at the container level).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --log-level warning --no-access-log"]
