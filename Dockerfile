# --- Builder stage: build wheels / compile native extensions ---
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build deps only in builder stage
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      g++ \
      git \
      curl \
      libpq-dev \
      libssl-dev \
      pkg-config \
      && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (better cache)
COPY requirements.txt .

# Build wheels for all requirements to avoid compiling in final image
RUN python -m pip install --upgrade pip setuptools wheel && \
    mkdir /wheels && \
    pip wheel --wheel-dir /wheels -r requirements.txt

# Copy app source (if your build needs the source for building some extras)
COPY . .

# --- Runtime stage: minimal image ---
FROM python:3.11-slim AS runtime

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install only runtime OS deps (keep minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      ca-certificates \
      && rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels from builder and install them
COPY --from=builder /wheels /wheels
RUN python -m pip install --upgrade pip setuptools && \
    pip install --no-deps --no-index --find-links=/wheels -r /app/requirements.txt || \
    pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]