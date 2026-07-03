# AERO-SHIELD X — Backend Dockerfile
# Python 3.12 slim image for production deployment

FROM python:3.12-slim

# Build args
ARG APP_ENV=production

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r aeroshield && useradd -r -g aeroshield aeroshield

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Set ownership
RUN chown -R aeroshield:aeroshield /app

USER aeroshield

# Expose API port
EXPOSE 8000

# Health check — uses the liveness probe endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/system/health/live || exit 1

# Production entrypoint
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
