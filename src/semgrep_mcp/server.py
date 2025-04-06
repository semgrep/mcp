#!/usr/bin/env python3
import asyncio
import os
import shutil
import subprocess
import tempfile
from typing import Any

import click
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    ErrorData,
)
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------------

VERSION = "0.1.9"
DEFAULT_TIMEOUT = 300  # 5 mins in seconds

SEMGREP_URL = os.environ.get("SEMGREP_URL", "https://semgrep.dev")
SEMGREP_API_URL = f"{SEMGREP_URL}/api"

# Field definitions for function parameters
CODE_FILES_FIELD = Field(description="List of dictionaries with 'filename' and 'content' keys")
CONFIG_FIELD = Field(
    description="Optional Semgrep configuration string (e.g. 'auto', 'p/ci', 'p/security')",
    default=None,
)

RULE_FIELD = Field(description="Semgrep YAML rule string")

# ---------------------------------------------------------------------------------
# Global Variables
# ---------------------------------------------------------------------------------

# Global variable to store the semgrep executable path
semgrep_executable: str | None = None
_semgrep_lock = asyncio.Lock()

# ---------------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------------


class CodeFile(BaseModel):
    filename: str = Field(description="Relative path to the file")
    content: str = Field(description="Content of the file")


class SemgrepScanResult(BaseModel):
    version: str = Field(description="Version of Semgrep used for the scan")
    results: list[dict[str, Any]] = Field(description="List of semgrep scan results")
    errors: list[dict[str, Any]] = Field(
        description="List of errors encountered during scan", default_factory=list
    )
    paths: dict[str, Any] = Field(description="Paths of the scanned files")
    skipped_rules: list[str] = Field(
        description="List of rules that were skipped during scan", default_factory=list
    )


# ---------------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------------


def safe_join(base_dir: str, untrusted_path: str) -> str:
    # Absolute, normalized path to the base directory
    base_dir = os.path.abspath(base_dir)

    # Join and normalize the untrusted path
    full_path = os.path.abspath(os.path.join(base_dir, untrusted_path))

    # Ensure the final path is still within the base directory
    if not full_path.startswith(base_dir + os.sep):
        raise ValueError(f"Untrusted path escapes the base directory!: {untrusted_path}")

    return full_path


def common_base_dir(file_paths: list[str]) -> str:
    dirs = [os.path.dirname(p) for p in file_paths]
    return os.path.commonpath(dirs)


# Path validation
def validate_absolute_path(path_to_validate: str, param_name: str) -> str:
    """Validates an absolute path to ensure it's safe to use"""
    if not os.path.isabs(path_to_validate):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"{param_name} must be an absolute path. Received: {path_to_validate}",
            )
        )

    # Normalize path and ensure no path traversal is possible
    normalized_path = os.path.normpath(path_to_validate)

    # Check if normalized path is still absolute
    if not os.path.isabs(normalized_path):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"{param_name} contains invalid path traversal sequences",
            )
        )

    return normalized_path


def validate_config(config: str | None = None) -> str | None:
    """Validates semgrep configuration parameter"""
    # Allow registry references (p/ci, p/security, etc.)
    if config is None or config.startswith("p/") or config == "auto":
        return config

    # Otherwise, treat as path and validate
    return validate_absolute_path(config, "config")


# Semgrep utilities
def find_semgrep_path() -> str | None:
    """
    Dynamically find semgrep in PATH or common installation directories
    Returns: Path to semgrep executable or None if not found
    """
    # Common paths where semgrep might be installed
    common_paths = [
        "semgrep",  # Default PATH
        "/usr/local/bin/semgrep",
        "/usr/bin/semgrep",
        "/opt/homebrew/bin/semgrep",  # Homebrew on macOS
        "/opt/semgrep/bin/semgrep",
        "/home/linuxbrew/.linuxbrew/bin/semgrep",  # Homebrew on Linux
        "/snap/bin/semgrep",  # Snap on Linux
    ]

    # Add Windows paths if on Windows
    if os.name == "nt":
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            common_paths.extend(
                [
                    os.path.join(app_data, "Python", "Scripts", "semgrep.exe"),
                    os.path.join(app_data, "npm", "semgrep.cmd"),
                ]
            )

    # Try each path
    for semgrep_path in common_paths:
        # For 'semgrep' (without path), check if it's in PATH
        if semgrep_path == "semgrep":
            try:
                subprocess.run(
                    [semgrep_path, "--version"], check=True, capture_output=True, text=True
                )
                return semgrep_path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        # For absolute paths, check if the file exists before testing
        if os.path.isabs(semgrep_path):
            if not os.path.exists(semgrep_path):
                continue

            # Try executing semgrep at this path
            try:
                subprocess.run(
                    [semgrep_path, "--version"], check=True, capture_output=True, text=True
                )
                return semgrep_path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

    return None


async def ensure_semgrep_available() -> str:
    """
    Ensures semgrep is available and sets the global path in a thread-safe manner

    Returns:
        Path to semgrep executable

    Raises:
        McpError: If semgrep is not installed or not found
    """
    global semgrep_executable

    # Fast path - check if we already have the path
    if semgrep_executable:
        return semgrep_executable

    # Slow path - acquire lock and find semgrep
    async with _semgrep_lock:
        # Try to find semgrep
        semgrep_path = find_semgrep_path()

        if not semgrep_path:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="Semgrep is not installed or not in your PATH. "
                    "Please install Semgrep manually before using this tool. "
                    "Installation options: "
                    "pip install semgrep, "
                    "macOS: brew install semgrep, "
                    "Or refer to https://semgrep.dev/docs/getting-started/",
                )
            )

        # Store the path for future use
        semgrep_executable = semgrep_path
        return semgrep_path


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
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")

        # if given a list of files, with absolute paths, find the common base dir
        paths = [file_info.filename for file_info in code_files]
        base_dir = common_base_dir(paths)

        # Create files in the temporary directory
        for file_info in code_files:
            filename = file_info.filename
            if not filename:
                continue

            if base_dir:
                relative_path = os.path.relpath(filename, base_dir)
                temp_file_path = safe_join(temp_dir, relative_path)
            else:
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
        if "temp_dir" in locals():
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


def validate_code_files(code_files: list[CodeFile]) -> None:
    """
    Validates the code_files parameter for semgrep scan using Pydantic validation

    Args:
        code_files: List of CodeFile objects

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
        [CodeFile.model_validate(file) for file in code_files]
    except Exception as e:
        raise McpError(
            ErrorData(code=INVALID_PARAMS, message=f"Invalid code files format: {e!s}")
        ) from e


async def run_semgrep(args: list[str]) -> str:
    """
    Runs semgrep with the given arguments

    Args:
        args: List of command arguments

    Returns:
        Output of semgrep command
    """

    # Ensure semgrep is available
    semgrep_path = await ensure_semgrep_available()

    # Execute semgrep command
    process = await asyncio.create_subprocess_exec(
        semgrep_path, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Error running semgrep: ({process.returncode}) {stderr.decode()}",
            )
        )

    return stdout.decode()


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

# Create a fast MCP server
mcp = FastMCP(
    "Semgrep",
    version=VERSION,
    request_timeout=DEFAULT_TIMEOUT,
)

http_client = httpx.AsyncClient()


@mcp.tool()
async def semgrep_rule_schema() -> str:
    """
    Get the schema for a Semgrep rule

    Use this tool when you need to:
      - get the schema required to write a Semgrep rule
      - need to see what fields are available for a Semgrep rule
      - verify what fields are available for a Semgrep rule
      - verify the syntax for a Semgrep rule is correct
    """

    try:
        response = await http_client.get(f"{SEMGREP_API_URL}/schema_url")
        response.raise_for_status()
        data: dict[str, str] = response.json()
        schema_url: str = data["schema_url"]
        response = await http_client.get(schema_url)
        response.raise_for_status()
        return str(response.text)
    except Exception as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error getting schema for Semgrep rule: {e!s}")
        ) from e


@mcp.tool()
async def get_supported_languages() -> list[str]:
    """
    Returns a list of supported languages by Semgrep

    Only use this tool if you are not sure what languages Semgrep supports.
    """

    args = ["show", "supported-languages", "--experimental"]

    # Parse output and return list of languages
    languages = await run_semgrep(args)
    return [lang.strip() for lang in languages.strip().split("\n") if lang.strip()]


@mcp.tool()
async def semgrep_scan_with_custom_rule(
    code_files: list[CodeFile] = CODE_FILES_FIELD,
    rule: str = RULE_FIELD,
) -> SemgrepScanResult:
    """
    Runs a Semgrep scan with a custom rule on provided code content
    and returns the findings in JSON format

    Use this tool when you need to:
      - scan code files for specific security vulnerability not covered by the default Semgrep rules
      - scan code files for specific issue not covered by the default Semgrep rules
    """
    # Validate code_files
    validate_code_files(code_files)
    try:
        # Create temporary files from code content
        temp_dir = create_temp_files_from_code_content(code_files)
        # Write rule to file
        rule_file_path = os.path.join(temp_dir, "rule.yaml")
        with open(rule_file_path, "w") as f:
            f.write(rule)

        # Run semgrep scan with custom rule
        args = get_semgrep_scan_args(temp_dir, rule_file_path)
        output = await run_semgrep(args)
        results: SemgrepScanResult = SemgrepScanResult.model_validate_json(output)
        remove_temp_dir_from_results(results, temp_dir)
        return results

    except McpError as e:
        raise e
    except ValidationError as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error parsing semgrep output: {e!s}")
        ) from e
    except Exception as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error running semgrep scan: {e!s}")
        ) from e

    finally:
        if "temp_dir" in locals():
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)


@mcp.tool()
async def semgrep_scan(
    code_files: list[CodeFile] = CODE_FILES_FIELD,
    config: str | None = CONFIG_FIELD,
) -> SemgrepScanResult:
    """
    Runs a Semgrep scan on provided code content and returns the findings in JSON format

    Use this tool when you need to:
      - scan code files for security vulnerabilities
      - scan code files for other issues
    """
    # Validate config
    config = validate_config(config)

    # Validate code_files
    validate_code_files(code_files)

    try:
        # Create temporary files from code content
        temp_dir = create_temp_files_from_code_content(code_files)
        args = get_semgrep_scan_args(temp_dir, config)
        output = await run_semgrep(args)
        results: SemgrepScanResult = SemgrepScanResult.model_validate_json(output)
        remove_temp_dir_from_results(results, temp_dir)
        return results

    except McpError as e:
        raise e
    except ValidationError as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error parsing semgrep output: {e!s}")
        ) from e
    except Exception as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error running semgrep scan: {e!s}")
        ) from e

    finally:
        if "temp_dir" in locals():
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)


@click.command()
@click.version_option(version=VERSION, prog_name="Semgrep MCP Server")
@click.option(
    "-t",
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    envvar="MCP_TRANSPORT",
    help="Transport protocol to use (stdio or sse)",
)
def main(transport: str) -> None:
    """Entry point for the MCP server

    Supports both stdio and sse transports. For stdio, it will read from stdin and write to stdout.
    For sse, it will start an HTTP server on port 8000.
    """
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:  # sse
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
