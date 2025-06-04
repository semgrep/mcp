import json
import os
import subprocess
import time

import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

base_url = os.getenv("MCP_BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="module")
def streamable_server():
    # Start the streamable-http server
    proc = subprocess.Popen(["python", "src/semgrep_mcp/server.py", "-t", "streamable-http"])
    # Wait briefly to ensure the server starts
    time.sleep(2)
    yield
    # Teardown: terminate the server
    proc.terminate()
    proc.wait()


@pytest.mark.asyncio
async def test_streamable_client_smoke(streamable_server):
    async with streamablehttp_client(f"{base_url}/mcp") as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            # Initializing session...
            await session.initialize()
            # Session initialized

            # Scan code for security issues
            results = await session.call_tool(
                "semgrep_scan",
                {
                    "code_files": [
                        {
                            "filename": "hello_world.py",
                            "content": "def hello(): print('Hello, World!')",
                        }
                    ]
                },
            )
            # We have results!
            assert results is not None
            content = json.loads(results.content[0].text)
            assert isinstance(content, dict)
            assert content["paths"]["scanned"] == ["hello_world.py"]
            print(json.dumps(content, indent=2))
