import json
import os
import subprocess
import time

import pytest
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

base_url = os.getenv("MCP_BASE_URL", "http://127.0.0.1:8000")

print(f"MCP_BASE_URL: {base_url}")


@pytest.fixture(scope="module")
def sse_server():
    # Start the SSE server
    proc = subprocess.Popen(["python", "src/semgrep_mcp/server.py", "-t", "sse"])
    # Wait briefly to ensure the server starts
    time.sleep(2)
    yield
    # Teardown: terminate the server
    proc.terminate()
    proc.wait()


@pytest.mark.asyncio
async def test_sse_client_smoke(sse_server):
    async with sse_client(f"{base_url}/sse") as (read_stream, write_stream):
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
