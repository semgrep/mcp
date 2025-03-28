# Base image with Python and uv
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

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

# Copy the entire application source code
COPY --chown=app:app . .

# Create a virtual environment and install dependencies **as non-root**
RUN python -m venv /app/.venv \
    && uv pip install --no-cache .

# Default command to run the application
CMD ["uv", "run", "--with", "fastmcp", "fastmcp", "run", "server.py", "-t", "sse"]