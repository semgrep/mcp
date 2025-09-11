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
from semgrep_mcp.utilities.tracing import get_trace_endpoint, tracing_disabled
from semgrep_mcp.utilities.utils import ensure_semgrep_available, is_hosted

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
# Communicating with Semgrep over RPC #
################################################################################


class SemgrepContext:
    process: asyncio.subprocess.Process | None
    stdin: asyncio.StreamWriter | None
    stdout: asyncio.StreamReader | None
    top_level_span: trace.Span | None

    is_hosted: bool
    pro_engine_available: bool
    use_rpc: bool

    def __init__(
        self,
        top_level_span: trace.Span | None,
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
    if top_level_span and not tracing_disabled:
        env["SEMGREP_TRACE_PARENT_SPAN_ID"] = trace.format_span_id(
            top_level_span.get_span_context().span_id
        )
        env["SEMGREP_TRACE_PARENT_TRACE_ID"] = trace.format_trace_id(
            top_level_span.get_span_context().trace_id
        )

    return env


async def create_args(args: list[str]) -> list[str]:
    semgrep_path = await ensure_semgrep_available()
    _, env_alias = get_trace_endpoint()
    return [
        semgrep_path,
        *args
        + (["--no-trace"] if tracing_disabled else ["--trace", "--trace-endpoint", env_alias]),
    ]


async def run_semgrep_process_async(
    top_level_span: trace.Span | None,
    args: list[str],
) -> asyncio.subprocess.Process:
    env = get_semgrep_env(top_level_span)

    # Execute semgrep command
    process = await asyncio.create_subprocess_exec(
        *await create_args(args),
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
    env = get_semgrep_env(top_level_span)

    # Execute semgrep command
    process = subprocess.run(
        await create_args(args),
        stdin=subprocess.PIPE,
        capture_output=True,
        env=env,
    )
    return process


async def mk_context(top_level_span: trace.Span | None) -> SemgrepContext:
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
        process = await run_semgrep_process_async(top_level_span, ["mcp", "--pro"])

    return SemgrepContext(
        top_level_span=top_level_span,
        is_hosted=is_hosted(),
        pro_engine_available=pro_engine_available,
        process=process,
        use_rpc=use_rpc,
    )


async def run_semgrep_output(context: SemgrepContext, args: list[str]) -> str:
    """
    Runs `semgrep` with the given arguments and returns the stdout.
    """
    process = await run_semgrep_process_sync(context.top_level_span, args)

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
