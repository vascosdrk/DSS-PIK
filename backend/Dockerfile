# ==============================================================================
# DSS-PIK Backend — Production API Dockerfile (Python 3.12 Slim, Non-Root)
# Build context: project root (.)
# ==============================================================================

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CEWS_SERVE_FRONTEND=false \
    CEWS_PORT=8000 \
    PYTHONPATH=/app:/app/SPEI/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libexpat1 \
    libfreetype6 \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-lock.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=180 --retries=10 -r requirements-lock.txt

RUN groupadd --gid 1000 dsspik \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home dsspik

COPY backend/ ./backend/
COPY config/ ./config/
COPY SPEI/src/ ./SPEI/src/
COPY pipeline/ ./pipeline/
COPY scripts/ ./scripts/
COPY database/ ./database/
COPY pytest.ini ./

RUN mkdir -p /app/data/raw /app/data/reference /app/data/processed /app/data/operational/maps /app/data/historical /app/data/output /app/logs/runtime /app/outputs /app/reports \
    && chown -R dsspik:dsspik /app

USER dsspik

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

STOPSIGNAL SIGTERM

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
