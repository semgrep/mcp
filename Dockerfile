# Use the latest as a default, but allow it to be overriden in case we
# want to publish images with different versions of Semgrep.
ARG BASE_IMAGE=semgrep/semgrep:latest

# Use the Semgrep image, so that we can select which version of
# Semgrep we want to distribute with.
FROM ${BASE_IMAGE}

# Add `uv` to the image
RUN apk update && apk add py3-uv

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install .

# Uninstall, because we want to use the base image's version of Semgrep.
RUN uv pip uninstall semgrep

# need this for `useradd` right after
RUN apk add shadow

# Create non-root user
RUN useradd -m app

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Switch to non-root user
USER app

EXPOSE 8000

# expose the server to the outside world otherwise it will only be accessible from inside the container
ENV FASTMCP_HOST=0.0.0.0

ENTRYPOINT ["semgrep-mcp"]
CMD ["-t", "streamable-http"]