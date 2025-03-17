# Base image with Python and uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

# Create a non-root user and set proper permissions
RUN groupadd -r app && useradd --no-log-init -r -g app app \
    && mkdir -p /home/app/.cache/uv /app \
    && chown -R app:app /home/app /app

# Switch to non-root user before doing anything
USER app

# Set working directory
WORKDIR /app

# Enable bytecode compilation and optimize caching
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

# Copy dependency files first for better caching
COPY --chown=app:app uv.lock pyproject.toml ./

# Create a virtual environment and install dependencies **as non-root**
RUN python -m venv /app/.venv \
    && uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application source code
COPY --chown=app:app . .

# Default command to run the application
CMD ["uv", "run", "--with", "fastmcp", "fastmcp", "run", "server.py", "-t", "sse"]