# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS uv

RUN useradd -m -u 10001 app
USER app
# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

ENV PATH="/app/.venv/bin:${PATH}"

# Copy just these files and install dependencies to improve caching
COPY --chown=app pyproject.toml .
COPY --chown=app uv.lock .

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY --chown=app . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install .

RUN --mount=type=secret,id=semgrep_app_token,required=true,env=SEMGREP_APP_TOKEN,uid=10001,gid=10001,mode=0440 \
    uv run semgrep install-semgrep-pro

# Clear out any detritus from the pro install (especially credentials)
RUN rm -rf /home/app/.semgrep

EXPOSE 8000

# expose the server to the outside world otherwise it will only be accessible from inside the container
ENV FASTMCP_HOST=0.0.0.0

ENTRYPOINT ["semgrep-mcp"]
CMD ["-t", "streamable-http"]
