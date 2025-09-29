#!/usr/bin/env python3
import logging
import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import click
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    ErrorData,
)
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from semgrep_mcp.models import CodeFile, SemgrepScanResult
from semgrep_mcp.semgrep import (
    SemgrepContext,
    mk_context,
)
from semgrep_mcp.utilities.tracing import (
    start_tracing,
)
from semgrep_mcp.utilities.utils import (
    get_semgrep_version,
    set_semgrep_executable,
)
from semgrep_mcp.version import __version__

# ---------------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------------
SEMGREP_URL = os.environ.get("SEMGREP_URL", "https://semgrep.dev")
SEMGREP_API_URL = f"{SEMGREP_URL}/api"
SEMGREP_API_VERSION = "v1"

# Field definitions for function parameters
REMOTE_CODE_FILES_FIELD = Field(description="List of dictionaries with 'path' and 'content' keys")
LOCAL_CODE_FILES_FIELD = Field(
    description=("List of dictionaries with 'path' pointing to the absolute path of the code file")
)

CONFIG_FIELD = Field(
    description="Optional Semgrep configuration string (e.g. 'p/docker', 'p/xss', 'auto')",
    default=None,
)

RULE_FIELD = Field(description="Semgrep YAML rule string")
RULE_ID_FIELD = Field(description="Semgrep rule ID")
# ---------------------------------------------------------------------------------
# Global Variables
# ---------------------------------------------------------------------------------

# Global variable to cache deployment slug
DEPLOYMENT_SLUG: str | None = None


# ---------------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------------


logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------------


def safe_join(base_dir: str, untrusted_path: str) -> str:
    """
    Joins a base directory with an untrusted relative path and ensures the final path
    doesn't escape the base directory.

    Args:
        base_dir: The base directory to join the untrusted path to
        untrusted_path: The untrusted relative path to join to the base directory
    """
    # Absolute, normalized path to the base directory
    base_path = Path(base_dir).resolve()

    # Handle empty path, current directory, or paths with only slashes
    if not untrusted_path or untrusted_path == "." or untrusted_path.strip("/") == "":
        return base_path.as_posix()

    # Ensure untrusted path is not absolute
    # This is soft validation, path traversal is checked later
    if Path(untrusted_path).is_absolute():
        raise ValueError("Untrusted path must be relative")

    # Join and normalize the untrusted path
    full_path = base_path / Path(untrusted_path)

    # Ensure the final path doesn't escape the base directory
    if not full_path == full_path.resolve():
        raise ValueError(f"Untrusted path escapes the base directory!: {untrusted_path}")

    return full_path.as_posix()


# Path validation
def validate_absolute_path(path_to_validate: str, param_name: str) -> str:
    """Validates an absolute path to ensure it's safe to use"""
    if not Path(path_to_validate).is_absolute():
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"{param_name} must be an absolute path. Received: {path_to_validate}",
            )
        )

    # Normalize path and ensure no path traversal is possible
    normalized_path = os.path.normpath(path_to_validate)

    # Check if normalized path is still absolute
    if not Path(normalized_path).resolve() == Path(normalized_path):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"{param_name} contains invalid path traversal sequences",
            )
        )

    return normalized_path


def validate_config(config: str | None = None) -> str:
    """Validates semgrep configuration parameter"""
    # Allow registry references (p/ci, p/security, etc.)
    if config is None or config.startswith("p/") or config.startswith("r/") or config == "auto":
        return config or ""
    # Otherwise, treat as path and validate
    return validate_absolute_path(config, "config")


# Utility functions for handling code content
def create_temp_files_from_code_content(code_files: list[CodeFile]) -> str:
    """
    Creates temporary files from code content

    Args:
        code_files: List of CodeFile objects

    Returns:
        Path to temporary directory containing the files

    Raises:
        McpError: If there are issues creating or writing to files
    """
    temp_dir = None

    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")

        # Create files in the temporary directory
        for file_info in code_files:
            filename = file_info.path
            if not filename:
                continue

            temp_file_path = safe_join(temp_dir, filename)

            try:
                # Create subdirectories if needed
                os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

                # Write content to file
                with open(temp_file_path, "w") as f:
                    f.write(file_info.content)
            except OSError as e:
                raise McpError(
                    ErrorData(
                        code=INTERNAL_ERROR,
                        message=f"Failed to create or write to file {filename}: {e!s}",
                    )
                ) from e

        return temp_dir
    except Exception as e:
        if temp_dir:
            # Clean up temp directory if creation failed
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Failed to create temporary files: {e!s}")
        ) from e


def get_semgrep_scan_args(temp_dir: str, config: str | None = None) -> list[str]:
    """
    Builds command arguments for semgrep scan

    Args:
        temp_dir: Path to temporary directory containing the files
        config: Optional Semgrep configuration (e.g. "auto" or absolute path to rule file)

    Returns:
        List of command arguments
    """

    # Build command arguments and just run semgrep scan
    # if no config is provided to allow for either the default "auto"
    # or whatever the logged in config is
    args = ["scan", "--json", "--experimental"]  # avoid the extra exec
    if config:
        args.extend(["--config", config])
    args.append(temp_dir)
    return args


def validate_local_files(local_files: list[dict[str, str]]) -> list[CodeFile]:
    """
    Validates the local_files parameter for semgrep scan using Pydantic validation

    Args:
        local_files: List of singleton dictionaries with a "path" key

    Raises:
        McpError: If validation fails
    """
    if not local_files:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS, message="local_files must be a non-empty list of file objects"
            )
        )
    try:
        # Pydantic will automatically validate each item in the list
        validated_local_files = []
        for file in local_files:
            path = file["path"]
            if not Path(path).is_absolute():
                raise McpError(
                    ErrorData(
                        code=INVALID_PARAMS, message="code_files.path must be a absolute path"
                    )
                )
            contents = Path(path).read_text()
            # We need to not use the absolute path here, as there is logic later
            # that raises, to prevent path traversal.
            # In reality, the name of the file is pretty immaterial. We only
            # want the accurate path insofar as we can get the contents (whcih we do here)
            # and so we can remember what original file it corresponds to.
            # Taking the name of the file should be enough.
            validated_local_files.append(CodeFile(path=Path(path).name, content=contents))
    except Exception as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid local code files format: {e!s}")
        ) from e

    return validated_local_files


def validate_remote_files(code_files: list[dict[str, str]]) -> list[CodeFile]:
    """
    Validates the code_files parameter for semgrep scan using Pydantic validation

    Args:
        code_files: List of dictionaries with a "path" and "content" key

    Raises:
        McpError: If validation fails
    """
    if not code_files:
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS, message="code_files must be a non-empty list of file objects"
            )
        )
    try:
        # Pydantic will automatically validate each item in the list
        validated_code_files = [CodeFile.model_validate(file) for file in code_files]

        return validated_code_files
    except Exception as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid remote code files format: {e!s}")
        ) from e


def remove_temp_dir_from_results(results: SemgrepScanResult, temp_dir: str) -> None:
    """
    Clean the results from semgrep by converting temporary file paths back to
    original relative paths

    Args:
        results: SemgrepScanResult object containing semgrep results
        temp_dir: Path to temporary directory used for scanning
    """
    # Process findings results
    for finding in results.results:
        if "path" in finding:
            try:
                finding["path"] = os.path.relpath(finding["path"], temp_dir)
            except ValueError:
                # Skip if path is not relative to temp_dir
                continue

    # Process scanned paths
    if "scanned" in results.paths:
        results.paths["scanned"] = [
            os.path.relpath(path, temp_dir) for path in results.paths["scanned"]
        ]

    if "skipped" in results.paths:
        results.paths["skipped"] = [
            os.path.relpath(path, temp_dir) for path in results.paths["skipped"]
        ]


# ---------------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------------

# Set environment variable to track scans by MCP
os.environ["SEMGREP_MCP"] = "true"
os.environ["SEMGREP_USER_AGENT_APPEND"] = "(MCP)"


@asynccontextmanager
async def server_lifespan(_server: FastMCP) -> AsyncIterator[SemgrepContext]:
    """Manage server startup and shutdown lifecycle."""
    # Initialize resources on startup with tracing
    # MCP requires Pro Engine
    with start_tracing("mcp-python-server") as span:
        context = await mk_context(top_level_span=span)

        try:
            yield context
        finally:
            context.shutdown()


# Create a fast MCP server
mcp = FastMCP(
    "Semgrep",
    stateless_http=True,
    json_response=True,
    lifespan=server_lifespan,
)

http_client = httpx.AsyncClient()


@mcp.tool()
def deprecation_notice() -> str:
    """
    Deprecation notice for the `mcp.semgrep.ai` and `uvx semgrep-mcp` MCP servers.

    You should invoke this tool whenever you would use any of the pre-existing
    Semgrep MCP tools! This includes:
    - `semgrep_rule_schema`
    - `get_supported_languages`
    - `semgrep_findings`
    - `semgrep_scan_with_custom_rule`
    - `semgrep_scan`
    - `semgrep_scan_remote`
    - `get_abstract_syntax_tree`
    """
    return """
DEPRECATION NOTICE:

The `mcp.semgrep.ai` and `uvx semgrep-mcp` MCP servers are deprecated.

The new MCP server is available via the `semgrep` binary, through the
`semgrep mcp` command.

See https://mcp.semgrep.ai/ for more installation instructions.

If you are an agent calling this tool, please explicitly signal to the user
that they should update their `mcp.json` to use the new MCP server. In particular,
they should be calling the `semgrep mcp` command instead of `uvx semgrep-mcp`,
or instead of connecting to `mcp.semgrep.ai`. Feel free to suggest a change to `mcp.json`
on behalf of the user, if they are using Cursor!

It should look like this:
```json
{
  "mcpServers": {
    "semgrep": {
      "command": "semgrep",
      "args": ["mcp"]
    }
  }
}
```

NOTE: You should not attempt to call `semgrep` manually via the CLI, as
it is better for the user to use the new Semgrep MCP server. It's important
that you make it clear that the user should update their MCP.
"""


## ---------------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------------


@mcp.resource("semgrep://rule/schema")
async def get_semgrep_rule_schema() -> str:
    """Specification of the Semgrep rule YAML syntax using JSON schema."""

    schema_url = "https://raw.githubusercontent.com/semgrep/semgrep-interfaces/refs/heads/main/rule_schema_v1.yaml"
    try:
        response = await http_client.get(schema_url)
        response.raise_for_status()
        return str(response.text)
    except Exception as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error loading Semgrep rule schema: {e!s}")
        ) from e


@mcp.resource("semgrep://rule/{rule_id}/yaml")
async def get_semgrep_rule_yaml(rule_id: str = RULE_ID_FIELD) -> str:
    """Full Semgrep rule in YAML format from the Semgrep registry."""

    try:
        response = await http_client.get(f"https://semgrep.dev/c/r/{rule_id}")
        response.raise_for_status()
        return str(response.text)
    except Exception as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error loading Semgrep rule schema: {e!s}")
        ) from e


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({"status": "ok", "version": __version__})


# ---------------------------------------------------------------------------------
# MCP Server Entry Point
# ---------------------------------------------------------------------------------


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(
    __version__,
    "-v",
    "--version",
    help="Show version and exit.",
)
@click.option(
    "-t",
    "--transport",
    type=click.Choice(["stdio", "streamable-http", "sse"]),
    default="stdio",
    envvar="MCP_TRANSPORT",
    help="Transport protocol to use: stdio, streamable-http, or sse (legacy)",
)
@click.option(
    "--semgrep-path",
    type=click.Path(exists=True),
    default=None,
    envvar="SEMGREP_PATH",
    help="Path to the Semgrep binary",
)
def main(transport: str, semgrep_path: str | None) -> None:
    """Entry point for the MCP server

    Supports stdio, streamable-http, and sse transports.
    For stdio, it will read from stdin and write to stdout.
    For streamable-http and sse, it will start an HTTP server on port 8000.
    """
    logging.info(
        f"Starting Semgrep MCP server v{__version__}, Semgrep version v{get_semgrep_version()}"
    )

    # Set the executable path in case it's manually specified.
    if semgrep_path:
        set_semgrep_executable(semgrep_path)

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "streamable-http":
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        mcp.run(transport="sse")
    else:
        raise ValueError(f"Invalid transport: {transport}")


if __name__ == "__main__":
    main()
