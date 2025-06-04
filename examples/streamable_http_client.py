import asyncio
import json

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent


async def main():
    async with streamablehttp_client("http://localhost:8000/mcp") as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            print("Initializing session...")
            await session.initialize()
            print("Session initialized")

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
            print("\n\nWe have results!\n")
            print("Raw result object:")
            print("=" * 80)
            print(results)
            print("\n\nPretty-printed result from semgrep_scan:")
            print("=" * 80)
            if isinstance(results.content[0], TextContent):
                print(json.dumps(json.loads(results.content[0].text), indent=2))
            else:
                print(f"First content is not TextContent: {type(results.content[0])}")
            print("\n\n")
            print("Hope that was helpful!")


if __name__ == "__main__":
    # you can run the client with:
    # uv run python examples/http_streamable_client.py

    print("Hello!")
    print("First, make sure the HTTP Streamable MCP server is listening on port 8000.")
    print("One way you can run it is with:\n")
    print("\tdocker run -p 8000:8000 ghcr.io/semgrep/mcp:latest -t streamable-http\n")
    print("in another tab in the terminal.")
    print("Now try running the HTTP Streamable client:")
    print("=" * 80)
    asyncio.run(main())
