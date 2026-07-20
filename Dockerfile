# syntax=docker/dockerfile:1

# ---------- Stage 1: build della PWA ----------
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: runtime backend + PWA ----------
FROM python:3.12-slim-bookworm AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    APP_ENV=prod \
    SESSION_COOKIE_SECURE=true \
    FRONTEND_DIST=/app/frontend_dist \
    PORT=8000

WORKDIR /app/backend

# 1) Dipendenze (layer cache separato dal codice)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Codice backend + installazione del progetto
COPY backend/ ./
RUN uv sync --frozen --no-dev

# 3) PWA buildata, servita dal backend (single origin)
COPY --from=frontend /fe/dist /app/frontend_dist

EXPOSE 8000
# All'avvio applica le migrazioni, poi serve API + PWA.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn whisper.main:app --host 0.0.0.0 --port ${PORT}"]
