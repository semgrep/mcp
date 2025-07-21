import os

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from semgrep_mcp.models import Finding


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("SEMGREP_API_TOKEN"),
    reason="SEMGREP_API_TOKEN not set; skipping integration test.",
)
async def test_semgrep_findings_sca():
    server_params = StdioServerParameters(
        command="python",
        args=["src/semgrep_mcp/server.py"],
        env={**os.environ},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            results = await session.call_tool("semgrep_findings", {"issue_type": ["sca"]})
            assert results is not None

            # Validate findings against the model
            for content in results.content:
                Finding.model_validate_json(content.text)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("SEMGREP_API_TOKEN"),
    reason="SEMGREP_API_TOKEN not set; skipping integration test.",
)
async def test_semgrep_findings_sast():
    server_params = StdioServerParameters(
        command="python",
        args=["src/semgrep_mcp/server.py"],
        env={**os.environ},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            results = await session.call_tool("semgrep_findings", {"issue_type": ["sast", "sca"]})
            assert results is not None

            # Validate findings against the model
            for content in results.content:
                finding = Finding.model_validate_json(content.text)
                print(finding)
