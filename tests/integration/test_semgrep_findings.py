import os
import json
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("SEMGREP_API_TOKEN"),
    reason="SEMGREP_API_TOKEN not set; skipping integration test."
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
            results = await session.call_tool(
                "semgrep_findings",
                {"issue_type": ["sca"]}
            )
            assert results is not None
            findings = json.loads(results.content[0].text)["findings"]
            assert isinstance(findings, list)