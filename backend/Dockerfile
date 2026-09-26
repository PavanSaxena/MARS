FROM python:3.12-slim

# torch / sentence-transformers / scikit-learn need a C build toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pull the static uv/uvx binaries instead of pip-installing uv itself
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Compile bytecode at build time (slower build, faster cold start) and keep
# the cache off the final layer size
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Install deps first so this layer is cached unless the lockfile changes.
# --no-install-project skips installing the app itself, so this layer
# only invalidates when dependencies actually change, not on every code edit.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now the app code, then install the project itself
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

# main.py's __main__ block is an interactive CLI (input()), which will hang
# in a container. Run the actual FastAPI app with uvicorn instead.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
