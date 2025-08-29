import asyncio
import json
import logging
import os
import subprocess
from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, INVALID_REQUEST, ErrorData
from opentelemetry import trace

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

SEMGREP_PATH = os.getenv("SEMGREP_PATH", None)

################################################################################
# Helpers #
################################################################################


def is_hosted() -> bool:
    """
    Check if the user is using the hosted version of the MCP server.
    """
    return os.environ.get("SEMGREP_IS_HOSTED", "false").lower() == "true"


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

    if SEMGREP_PATH:
        common_paths.append(SEMGREP_PATH)

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
    process: asyncio.subprocess.Process | None
    stdin: asyncio.StreamWriter | None
    stdout: asyncio.StreamReader | None
    top_level_span: trace.Span

    is_hosted: bool
    pro_engine_available: bool
    use_rpc: bool

    def __init__(
        self,
        top_level_span: trace.Span,
        is_hosted: bool,
        pro_engine_available: bool,
        use_rpc: bool,
        process: asyncio.subprocess.Process | None = None,
    ) -> None:
        self.process = process
        self.top_level_span = top_level_span
        self.is_hosted = is_hosted
        self.pro_engine_available = pro_engine_available
        self.use_rpc = use_rpc

        if process is None:
            self.stdin = None
            self.stdout = None
        elif process.stdin is not None and process.stdout is not None:
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
        if self.stdin is None or self.stdout is None:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="Semgrep process stdin/stdout not available",
                )
            )

        self.stdin.write(f"{line}\n".encode())
        await self.stdin.drain()

        stdout = await self.stdout.readline()
        return stdout.decode()

    async def send_request(self, request: str, **kwargs: Any) -> str:
        if self.is_hosted:
            error_string = """
                Cannot run semgrep scan via RPC because the MCP server is hosted.
                RPC is only available when the MCP server is running locally.
                Use the `semgrep_scan` tool instead.
                """
            raise McpError(ErrorData(code=INVALID_REQUEST, message=error_string))

        if not self.pro_engine_available:
            error_string = """
                Cannot run semgrep scan via RPC because the Pro Engine is not installed.
                Try running `semgrep install-semgrep-pro` to install it.
                """
            raise McpError(ErrorData(code=INVALID_REQUEST, message=error_string))

        payload = {"method": request, **kwargs}

        try:
            return await self.communicate(json.dumps(payload))
        except Exception as e:
            # TODO: move this code out of send_request, make a proper result
            # type and interpret at the call site
            # this is not specific to semgrep_scan_rpc, but it is for now!!!
            msg = f"""
              Error sending request to semgrep (RPC server may not be running): {e}.
              Try using `semgrep_scan` instead.
            """
            logging.error(msg)

            raise McpError(ErrorData(code=INTERNAL_ERROR, message=msg)) from e

    def shutdown(self) -> None:
        if self.process is not None:
            self.process.terminate()


################################################################################
# Running Semgrep #
################################################################################


def get_semgrep_env(top_level_span: trace.Span | None) -> dict[str, str]:
    # Just so we get the debug logs for the MCP server
    env = os.environ.copy()
    env["SEMGREP_LOG_SRCS"] = "mcp"
    if top_level_span:
        env["SEMGREP_TRACE_PARENT_SPAN_ID"] = trace.format_span_id(
            top_level_span.get_span_context().span_id
        )
        env["SEMGREP_TRACE_PARENT_TRACE_ID"] = trace.format_trace_id(
            top_level_span.get_span_context().trace_id
        )

    return env


async def run_semgrep_process_async(
    top_level_span: trace.Span | None,
    args: list[str],
) -> asyncio.subprocess.Process:
    # Ensure semgrep is available
    semgrep_path = await ensure_semgrep_available()

    env = get_semgrep_env(top_level_span)

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


async def run_semgrep_process_sync(
    top_level_span: trace.Span | None,
    args: list[str],
) -> subprocess.CompletedProcess[bytes]:
    # Ensure semgrep is available
    semgrep_path = await ensure_semgrep_available()

    env = get_semgrep_env(top_level_span)

    # Execute semgrep command
    process = subprocess.run(
        [semgrep_path, *args],
        stdin=subprocess.PIPE,
        capture_output=True,
        env=env,
    )
    return process


async def mk_context(top_level_span: trace.Span) -> SemgrepContext:
    """
    Runs the semgrep daemon (`semgrep mcp`) if:
    - the user has the Pro Engine installed
    - is running the MCP server locally
    - the USE_SEMGREP_RPC env var is set to true

    TODO: remove the "running locally" check once we have a way to
    obtain per-user app tokens in the hosted environment
    """
    process = None
    pro_engine_available = True

    use_rpc = os.environ.get("USE_SEMGREP_RPC", "true").lower() == "true"

    resp = await run_semgrep_process_sync(top_level_span, ["--pro", "--version"])

    # The user doesn't seem to have the Pro Engine installed.
    # That's fine, let's just run the free engine, without the
    # `semgrep mcp` backend.
    if resp.returncode != 0:
        logging.warning(
            "User doesn't have the Pro Engine installed, not running `semgrep mcp` daemon..."
        )
        pro_engine_available = False
    elif not use_rpc:
        logging.info("USE_SEMGREP_RPC env var is false, not running `semgrep mcp` daemon...")
    elif is_hosted():
        logging.warning(
            """
            The `semgrep mcp` daemon is only available when the MCP server is ran locally.
            User is using the hosted version of the MCP server, not running `semgrep mcp` daemon...
            """
        )
    else:
        logging.info("Spawning `semgrep mcp` daemon...")
        process = await run_semgrep_process_async(top_level_span, ["mcp", "--pro", "--trace"])

    return SemgrepContext(
        top_level_span=top_level_span,
        is_hosted=is_hosted(),
        pro_engine_available=pro_engine_available,
        process=process,
        use_rpc=use_rpc,
    )


async def run_semgrep_output(top_level_span: trace.Span | None, args: list[str]) -> str:
    """
    Runs `semgrep` with the given arguments and returns the stdout.
    """
    process = await run_semgrep_process_sync(top_level_span, args)

    if process.stdout is None or process.stderr is None:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message="Error running semgrep: stdout or stderr is None",
            )
        )

    if process.returncode != 0:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Error running semgrep: ({process.returncode}) {process.stderr.decode()}",
            )
        )

    return process.stdout.decode()


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
