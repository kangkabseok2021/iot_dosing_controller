# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy root pyproject.toml and uv.lock (build context is root of monorepo)
COPY pyproject.toml uv.lock ./

# Install dependencies (only production)
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root user
RUN groupadd -r app && useradd -r -g app app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY slm_sensor_analytics/app /app/app
COPY slm_sensor_analytics/migrations /app/migrations
COPY slm_sensor_analytics/alembic.ini /app/alembic.ini

# Ensure correct permissions
RUN mkdir -p /app/models && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV MODEL_DIR="/app/models"
ENV DATABASE_URL="postgresql+asyncpg://slm:slm@db:5432/slmdb"

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
