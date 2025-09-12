import json
import os
import subprocess
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

base_url = os.getenv("MCP_BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="module")
def streamable_server():
    # Start the streamable-http server
    proc = subprocess.Popen(
        ["python", "src/semgrep_mcp/server.py", "-t", "streamable-http"],
    )
    # Wait briefly to ensure the server starts
    time.sleep(5)
    yield
    # Teardown: terminate the server
    proc.terminate()
    proc.wait()


@pytest.mark.asyncio
async def test_local_scan(streamable_server):
    async with streamablehttp_client(f"{base_url}/mcp") as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            # Initializing session...
            await session.initialize()
            # Session initialized

            with NamedTemporaryFile(
                "w", prefix="hello_world", suffix=".py", encoding="utf-8"
            ) as tmp:
                tmp.write("def hello(): print('Hello, World!')")
                tmp.flush()

                path = tmp.name

                # Scan code for security issues using local semgrep_scan
                results = await session.call_tool(
                    "semgrep_scan",
                    {
                        "code_files": [
                            {
                                "path": str(Path(path).absolute()),
                            }
                        ]
                    },
                )
                # We have results!
                assert results is not None
                content = json.loads(results.content[0].text)  # type: ignore
                assert isinstance(content, dict)
                assert len(content["paths"]["scanned"]) == 1
                assert content["paths"]["scanned"][0].startswith("hello_world")
                print(json.dumps(content, indent=2))
