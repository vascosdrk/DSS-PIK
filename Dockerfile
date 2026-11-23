# ==============================================================================
# DSS-PIK BMKG Kepulauan Riau — Multi-Stage Production Dockerfile
# Stage 1: Build React/Vite SPA production assets
# Stage 2: Python 3.12 slim runtime serving FastAPI API + SPA on port 8000
# ==============================================================================

# --- Stage 1: Frontend Builder ---
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# --- Stage 2: Python Application Runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CEWS_SERVE_FRONTEND=true \
    CEWS_PORT=8000 \
    PYTHONPATH=/app:/app/SPEI/src

WORKDIR /app

# Install minimal runtime OS libraries required by geopandas/pyogrio/matplotlib/curl healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libexpat1 \
    libfreetype6 \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Install locked Python dependencies reproducibly (BuildKit cache mount avoids re-downloads on retry without bloating image)
COPY requirements-lock.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=180 --retries=10 -r requirements-lock.txt

# Create non-root application user
RUN groupadd --gid 1000 dsspik \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home dsspik

# Copy application source code (no secrets, no dumps, no large operational datasets)
COPY backend/ ./backend/
COPY config/ ./config/
COPY SPEI/src/ ./SPEI/src/
COPY pipeline/ ./pipeline/
COPY scripts/ ./scripts/
COPY database/ ./database/
COPY pytest.ini ./

# Copy built frontend SPA from Stage 1
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Prepare writable mount points for operational outputs & runtime logs
RUN mkdir -p /app/data/raw /app/data/reference /app/data/processed /app/data/operational/maps /app/data/historical /app/data/output /app/logs/runtime /app/outputs /app/reports \
    && chown -R dsspik:dsspik /app

USER dsspik

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

STOPSIGNAL SIGTERM

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
