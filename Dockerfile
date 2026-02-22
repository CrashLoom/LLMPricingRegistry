FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (no dev deps)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code and data
COPY app/ app/
COPY pricing/ pricing/
COPY schema/ schema/

EXPOSE 8080

# (2 * CPUs) + 1 is the recommended worker count; Cloud Run provides 1 vCPU by default
CMD ["uv", "run", "gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "3", \
     "--bind", "0.0.0.0:8080", \
     "--timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
