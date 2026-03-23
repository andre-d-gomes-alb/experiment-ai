# ===========================
# 1) BUILDER: Install deps
# ===========================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.7.1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential git postgresql-client && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock* /app/

# Install dependencies without creating venv
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY . /app

# ======================================
# 2) FINAL IMAGE  minimal + secure
# ======================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser || true

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy application
COPY --from=builder /app /app

# Fix permissions
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Default command (override in compose/k8s as needed)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
