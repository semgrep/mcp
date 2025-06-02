#!/usr/bin/env python3
import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
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

__version__ = "0.3.0"
DEFAULT_TIMEOUT = 300  # 5 mins in seconds

SEMGREP_URL = os.environ.get("SEMGREP_URL", "https://semgrep.dev")
SEMGREP_API_URL = f"{SEMGREP_URL}/api"

# Field definitions for function parameters
CODE_FILES_FIELD = Field(description="List of dictionaries with 'filename' and 'content' keys")
CONFIG_FIELD = Field(
    description="Optional Semgrep configuration string (e.g. 'p/docker', 'p/xss', 'auto')",
    default=None,
)

RULE_FIELD = Field(description="Semgrep YAML rule string")
RULE_ID_FIELD = Field(description="Semgrep rule ID")
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
    filename: str = Field(description="Relative path to the code file")
    content: str = Field(description="Content of the code file")


class CodeWithLanguage(BaseModel):
    content: str = Field(description="Content of the code file")
    language: str = Field(description="Programing language of the code file", default="python")


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
    if os.path.isabs(untrusted_path):
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
    if not Path(normalized_path).resolve() == Path(normalized_path):
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
    if config is None or config.startswith("p/") or config.startswith("r/") or config == "auto":
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

        # Create files in the temporary directory
        for file_info in code_files:
            filename = file_info.filename
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
    for file in code_files:
        if os.path.isabs(file.filename):
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS, message="code_files.filename must be a relative path"
                )
            )


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
    version=__version__,
    request_timeout=DEFAULT_TIMEOUT,
)

http_client = httpx.AsyncClient()

# ---------------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------------


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


@mcp.tool()
async def security_check(
    code_files: list[CodeFile] = CODE_FILES_FIELD,
) -> str:
    """
    Runs a fast security check on code and returns any issues found.

    Use this tool when you need to:
      - scan code for security vulnerabilities
      - verify that code is secure
      - double check that code is secure before committing
      - get a second opinion on code security

    If there are no issues, you can be reasonably confident that the code is secure.
    """
    # Validate code_files
    validate_code_files(code_files)

    no_findings_message = """No security issues found in the code!"""
    security_issues_found_message_template = """{num_issues} security issues found in the code.

Here are the details of the security issues found:

<security-issues>
    {details}
</security-issues>
"""
    try:
        # Create temporary files from code content
        temp_dir = create_temp_files_from_code_content(code_files)
        args = get_semgrep_scan_args(temp_dir)
        output = await run_semgrep(args)
        results: SemgrepScanResult = SemgrepScanResult.model_validate_json(output)
        remove_temp_dir_from_results(results, temp_dir)

        if len(results.results) > 0:
            return security_issues_found_message_template.format(
                num_issues=len(results.results),
                details=results.model_dump_json(indent=2),
            )
        else:
            return no_findings_message

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
async def get_abstract_syntax_tree(
    code: str = Field(description="The code to get the AST for"),
    language: str = Field(description="The programming language of the code"),
) -> str:
    """
    Returns the Abstract Syntax Tree (AST) for the provided code file in JSON format

    Use this tool when you need to:
      - get the Abstract Syntax Tree (AST) for the provided code file\
      - get the AST of a file
      - understand the structure of the code in a more granular way
      - see what a parser sees in the code
    """

    try:
        # Create temporary directory and file for AST generation
        temp_dir = tempfile.mkdtemp(prefix="semgrep_ast_")
        temp_file_path = os.path.join(temp_dir, "code.txt")  # safe

        # Write content to file
        with open(temp_file_path, "w") as f:
            f.write(code)

        args = [
            "--experimental",
            "--dump-ast",
            "-l",
            language,
            "--json",
            temp_file_path,
        ]
        return await run_semgrep(args)

    except McpError as e:
        raise e
    except ValidationError as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error parsing semgrep output: {e!s}")
        ) from e
    except OSError as e:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Failed to create or write to file {temp_file_path}: {e!s}",
            )
        ) from e
    except Exception as e:
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Error running semgrep scan: {e!s}")
        ) from e
    finally:
        if "temp_dir" in locals():
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------------
# MCP Prompts
# ---------------------------------------------------------------------------------


@mcp.prompt()
def write_custom_semgrep_rule(
    code: str = Field(description="The code to get the AST for"),
    language: str = Field(description="The programming language of the code"),
) -> str:
    """
    Write a custom Semgrep rule for the provided code and language

    Use this prompt when you need to:
      - write a custom Semgrep rule
      - write a Semgrep rule for a specific issue or pattern
    """

    prompt_template = """You are an expert at writing Semgrep rules.

Your task is to analyze a given piece of code and create a Semgrep rule
that can detect specific patterns or issues within that code.
Semgrep is a lightweight static analysis tool that uses pattern matching
to find bugs and enforce code standards.

Here is the code you need to analyze:

<code>
{code}
</code>

The code is written in the following programming language:

<language>
{language}
</language>

To write an effective Semgrep rule, follow these guidelines:
1. Identify a specific pattern, vulnerability, or
coding standard violation in the given code.
2. Create a rule that matches this pattern as precisely as possible.
3. Use Semgrep's pattern syntax, which is similar to the target language
but with metavariables and ellipsis operators where appropriate.
4. Consider the context and potential variations of the pattern you're trying to match.
5. Provide a clear and concise message that explains what the rule detects.
6. The value of the `severity` must be one of the following:
    - "ERROR"
    - "WARNING"
    - "INFO"
    - "INVENTORY"
    - "EXPERIMENT"
    - "CRITICAL"
    - "HIGH"
    - "MEDIUM"
    - "LOW"

7. The value of the `languages` must be a list of languages that the rule is applicable
to and include the language given in <language> tags.


Write your Semgrep rule in YAML format. The rule should include at least the following keys:
- rules
- id
- pattern
- message
- severity
- languages

Before providing the rule, briefly explain in a few sentences what specific issue or
pattern your rule is designed to detect and why it's important.

Then, output your Semgrep rule inside <semgrep_rule> tags.

Ensure that the rule is properly formatted in YAML.
Make sure to include all the required keys and values in the rule."""

    return prompt_template.format(code=code, language=language)


# ---------------------------------------------------------------------------------
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
def main(transport: str) -> None:
    """Entry point for the MCP server

    Supports stdio, streamable-http, and sse transports.
    For stdio, it will read from stdin and write to stdout.
    For streamable-http and sse, it will start an HTTP server on port 8000.
    """
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
