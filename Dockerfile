# FinAlly — Multi-stage Docker build
# Stage 1: Build the Next.js static export
# Stage 2: Python backend serving the static files + API

# ---------------------------------------------------------------------------
# Stage 1 — Frontend build
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-build

WORKDIR /build/frontend

# Install dependencies first (cache layer)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy source and build static export
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — Python backend + static frontend
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy backend project files and install dependencies (cache layer)
COPY backend/pyproject.toml backend/uv.lock ./backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev

# Copy backend source
COPY backend/ /app/backend/

# Copy frontend build output into static/ directory at project root
COPY --from=frontend-build /build/frontend/out /app/static

# Create db directory for volume mount
RUN mkdir -p /app/db

WORKDIR /app/backend

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
