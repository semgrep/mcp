import asyncio
import json

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client


async def main():
    async with sse_client("http://localhost:8000/sse") as (read_stream, write_stream):
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
            print(json.dumps(json.loads(results.content[0].text), indent=2))
            print("\n\n")
            print("Hope that was helpful!")


if __name__ == "__main__":
    # you can run the client with:
    # uv run python examples/sse_client.py

    print("Hello!")
    print("First, make sure the SSE MCP server is listening on port 8000.")
    print("One way you can run it is with:\n")
    print("\tdocker run -p 8000:8000 ghcr.io/semgrep/mcp:latest\n")
    print("in another tab in the terminal.")
    print("Now try running the SSE client:")
    print("=" * 80)
    asyncio.run(main())
