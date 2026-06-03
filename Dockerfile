# syntax=docker/dockerfile:1.6
#
# Production image: builds the React frontend, then drops it into the FastAPI
# image so the whole app ships as a single container.
#
#   docker build -t factory-mvp .
#   docker run --rm -p 8000:8000 -v $PWD/data:/app/data \
#       -e GEMINI_API_KEY=$GEMINI_API_KEY -e SECRET_KEY=local \
#       factory-mvp

# ============================================================================
# Stage 1 — build React app
# ============================================================================
FROM node:22-alpine AS frontend
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
# `npm install` (not `npm ci`) because the host-generated lockfile may miss
# Linux-specific optionalDependencies; npm install reconciles them on the fly.
RUN npm install --no-audit --no-fund

COPY frontend/ ./

# Relative API base — the same FastAPI process serves both, so the React app
# just hits "/api/v1/..." which resolves to whatever host the user opened.
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

# ============================================================================
# Stage 2 — Python backend + bundled frontend
# ============================================================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl for the container healthcheck, sqlite3 + b2 for in-container backups
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/app ./app
COPY backend/seed ./seed
COPY --from=frontend /build/dist ./static

# Persistent SQLite directory. In production this is overlaid by a Fly volume
# (or a docker bind mount) — the directory must exist before the mount.
RUN mkdir -p /app/data /app/generated_reports

# Run as non-root.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
