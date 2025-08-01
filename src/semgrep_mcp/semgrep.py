import asyncio
import json
import os
import subprocess
from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from semgrep_mcp.models import CodeFile
from semgrep_mcp.semgrep_interfaces.semgrep_output_v1 import CliOutput

################################################################################
# Prelude #
################################################################################
# Communicating with the Semgrep binary.

################################################################################
# Constants #
################################################################################

_SEMGREP_LOCK = asyncio.Lock()

# Global variable to store the semgrep executable path
SEMGREP_EXECUTABLE: str | None = None

################################################################################
# Finding Semgrep #
################################################################################


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
    global SEMGREP_EXECUTABLE

    # Fast path - check if we already have the path
    if SEMGREP_EXECUTABLE:
        return SEMGREP_EXECUTABLE

    # Slow path - acquire lock and find semgrep
    async with _SEMGREP_LOCK:
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
        SEMGREP_EXECUTABLE = semgrep_path
        return semgrep_path


def set_semgrep_executable(semgrep_path: str) -> None:
    global SEMGREP_EXECUTABLE
    SEMGREP_EXECUTABLE = semgrep_path


################################################################################
# Communicating with Semgrep over RPC #
################################################################################


class SemgrepContext:
    process: asyncio.subprocess.Process
    stdin: asyncio.StreamWriter
    stdout: asyncio.StreamReader

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process

        if process.stdin is not None and process.stdout is not None:
            self.stdin = process.stdin
            self.stdout = process.stdout
        else:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="Semgrep process stdin/stdout not available",
                )
            )

    async def communicate(self, line: str) -> str:
        self.stdin.write(f"{line}\n".encode())
        await self.stdin.drain()

        stdout = await self.stdout.readline()
        return stdout.decode()

    async def send_request(self, request: str, **kwargs: Any) -> str:
        payload = {"method": request, **kwargs}

        return await self.communicate(json.dumps(payload))


################################################################################
# Running Semgrep #
################################################################################


async def run_semgrep_process(args: list[str]) -> asyncio.subprocess.Process:
    """
    Runs semgrep with the given arguments as a subprocess, without waiting for it to finish.
    """

    # Ensure semgrep is available
    semgrep_path = await ensure_semgrep_available()

    # Just so we get the debug logs for the MCP server
    env = os.environ.copy()
    env["SEMGREP_LOG_SRCS"] = "mcp"

    # Execute semgrep command
    process = await asyncio.create_subprocess_exec(
        semgrep_path,
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        # This ensures that stderr makes it through to
        # the server logs, for debugging purposes.
        stderr=None,
        env=env,
    )

    return process


async def run_semgrep(args: list[str]) -> str:
    """
    Runs semgrep with the given arguments

    Args:
        args: List of command arguments

    Returns:
        Output of semgrep command
    """

    process = await run_semgrep_process(args)

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Error running semgrep: ({process.returncode}) {stderr.decode()}",
            )
        )

    return stdout.decode()


async def run_semgrep_via_rpc(context: SemgrepContext, data: list[CodeFile]) -> CliOutput:
    """
    Runs semgrep with the given arguments via RPC

    Args:
        data: List of code files to scan

    Returns:
        List of CliMatch objects
    """

    files_json = [{"file": data.filename, "content": data.content} for data in data]

    # ATD serialized value
    resp = await context.send_request("scanFiles", files=files_json)

    # The JSON we get is double encoded, looks like
    # '"{"results": ..., ...}"'
    # so we have to load it twice
    resp_json = json.loads(resp)
    resp_json = json.loads(resp_json)
    assert isinstance(resp_json, dict)

    return CliOutput.from_json(resp_json)
