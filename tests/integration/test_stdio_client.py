import json

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["src/semgrep_mcp/server.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)

@pytest.mark.asyncio
async def test_stdio_client():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # List available prompts
            prompts = await session.list_prompts()

            print(prompts)
            # List available resources
            resources = await session.list_resources()

            # List available tools
            print(resources)

            tools = await session.list_tools()

            print(tools)

            # Read a resource
            print("Reading resource")
            content, mime_type = await session.read_resource("semgrep://rule/schema")

            # Call a tool
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
