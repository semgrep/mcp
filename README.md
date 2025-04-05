<p align="center">
  <a href="https://semgrep.dev">
    <picture>
      <source media="(prefers-color-scheme: light)" srcset="images/semgrep-logo-light.svg">
      <source media="(prefers-color-scheme: dark)" srcset="images/semgrep-logo-dark.svg">
      <img src="https://raw.githubusercontent.com/semgrep/mcp/main/images/semgrep-logo-light.svg" height="100" alt="Semgrep logo"/>
    </picture>
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/semgrep-mcp/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/semgrep-mcp?style=flat-square&color=blue">
  </a>
  <a href="https://semgrep.dev/docs/">
      <img src="https://img.shields.io/badge/docs-semgrep.dev-purple?style=flat-square" alt="Documentation" />
  </a>
  <a href="https://go.semgrep.dev/slack">
    <img src="https://img.shields.io/badge/slack-3.5k%20members-green?style=flat-square" alt="Join Semgrep community Slack" />
  </a>
  <a href="https://github.com/semgrep/mcp/issues/new/choose">
    <img src="https://img.shields.io/badge/issues-welcome-green?style=flat-square" alt="Issues welcome!" />
  </a>
  <a href="https://x.com/intent/follow?screen_name=semgrep">
    <img src="https://img.shields.io/twitter/follow/semgrep" alt="Follow @semgrep on X" />
  </a>
</p>
</br>

# Semgrep MCP Server

> This beta Semgrep mcp server is under active development, we would love your feedback, bug reports, feature requests. For more support, join our [community slack](https://go.semgrep.dev/slack) > `#mcp` channel.

 A MCP server for using [Semgrep](https://semgrep.dev) to scan code for security vulnerabilies.

```bash
uvx semgrep-mcp -t sse
```

example Cursor `mcp.json` config:

```json
{
  "mcpServers": {
    "semgrep": {
      "command": "uvx",
      "args": ["semgrep-mcp"]
    }
  }
}

```

## Demo
<a href="https://www.loom.com/share/8535d72e4cfc4e1eb1e03ea223a702df"> <img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/8535d72e4cfc4e1eb1e03ea223a702df-1047fabea7261abb-full-play.gif"> </a>

[Model Context Protocul (MCP)](https://modelcontextprotocol.io/) is like Unix pipes or an API for LLMs, agents, and coding tools like Cursor, VS Code, Windsurf, Claude, or any other tool that support MCP, to get specialized help doing a task by using a tool.


## MCP Tools

> To optionally connect to Semgrep AppSec Platform:
>
> 1. [Login](https://semgrep.dev/login/) or sign up
> 2. Generate a token from [Settings](https://semgrep.dev/orgs/-/settings/tokens/api) page
> 3. Add it to your environment variables
>    - CLI (`export SEMGREP_APP_TOKEN=<token>`)
>    - Docker (`docker run -e SEMGREP_APP_TOKEN=<token>`)
>    - MCP Config JSON 
>        
>      ```json
>      "env": {
>        "SEMGREP_APP_TOKEN": "<token>"
>      }
>      ```
>
> Semgrep will automatically use the API token to connect and use the remote configuration. Please reach out to [support@semgrep.com](mailto:support@semgrep.com) if you have any problems.

**Scanning Code**
- `semgrep_scan`: Scan code snippets for security vulnerabilities

**Meta**
- `supported_languages`: Return the list of langauges Semgrep supports


## Usage

This package is published to PyPI as [semgrep-mcp](https://pypi.org/p/semgrep-mcp)

You can install it and run with [pip](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#install-a-package), [pipx](https://pipx.pypa.io/), [uv](https://docs.astral.sh/uv/), [poetry](https://python-poetry.org/), or any other way to install python packages.

For example:
```bash
pipx install semgrep-mcp
semgrep-mcp --help
```

## Run From Source

### Setup

#### CLI Environment

1. Install `uv` using their [installation instructions](https://docs.astral.sh/uv/getting-started/installation/)
1. Ensure you have Python 3.13+ installed
2. Clone this repository
3. Install Semgrep ([additional methods](https://semgrep.dev/docs/getting-started/quickstart)):

   ```bash
   pip install semgrep
   ```

#### Docker

1. Install `docker` using their [installation instructions](https://docs.docker.com/get-started/get-docker/)
2. Clone this repository
3. Build the server

  ```bash
  docker build -t semgrep-mcp .
  ```

### Running

#### CLI Environment

##### SSE Mode<a name="sse-mode"></a>

```bash
uv run mcp run server.py -t sse
```
Or as a script
```bash
chmod +x server.py
./server.py -t sse
```

##### STDIO Mode<a name="stdio-mode"></a>
```bash
uv run mcp run server.py -t stdio
```

See the official [python mcp sdk](https://github.com/modelcontextprotocol/python-sdk) for more details and configuration options.

#### Docker

```bash
docker run -p 8000:8000 semgrep-mcp
```

Also published to [ghcr.io/semgrep/mcp](http://ghcr.io/semgrep/mcp)

```bash
docker run -p 8000:8000 ghcr.io/semgrep/mcp:latest
```

### Creating your own client

```python
from mcp.client import Client

client = Client()
client.connect("localhost:8000")

# Scan code for security issues
results = client.call_tool("semgrep_scan", 
  {
  "code_files": [
    {
      "filename": "hello_world.py",
      "content": "def hello(): ..."
    }
  ]
})
```

## VS Code Integration


[![Install with UV in VS Code](https://img.shields.io/badge/VS_Code-UV-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22uv%22%2C%22args%22%3A%5B%22run%22%2C%22mcp%22%2C%22run%22%2C%22server.py%22%2C%22-t%22%2C%22sse%22%5D%7D) [![Install with UV in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-UV-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22uv%22%2C%22args%22%3A%5B%22run%22%2C%22mcp%22%2C%22run%22%2C%22server.py%22%2C%22-t%22%2C%22sse%22%5D%7D&quality=insiders)

[![Install with Docker in VS Code](https://img.shields.io/badge/VS_Code-Docker-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%22-p%22%2C%228000%3A8000%22%2C%22ghcr.io%2Fsemgrep%2Fmcp%3Alatest%22%5D%7D) [![Install with Docker in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Docker-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%22-p%22%2C%228000%3A8000%22%2C%22ghcr.io%2Fsemgrep%2Fmcp%3Alatest%22%5D%7D&quality=insiders)

### Manual Installation into VS Code

Click the install buttons at the top of this section for the quickest installation method. Alternatively, you can manually configure the server using one of the methods below.

#### Using UV

Add the following JSON block to your User Settings (JSON) file in VS Code. You can do this by pressing `Ctrl + Shift + P` and typing `Preferences: Open User Settings (JSON)`.

```json
{
  "mcp": {
    "servers": {
      "semgrep": {
        "command": "uv",
        "args": ["run", "mcp", "run", "server.py", "-t", "sse"]
      }
    }
  }
}
```

Optionally, you can add it to a file called `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "semgrep": {
      "command": "uv",
        "args": ["run", "mcp", "run", "server.py", "-t", "sse"]
    }
  }
}
```

#### Using Docker

Add the following JSON block to your User Settings (JSON) file in VS Code:

```json
{
  "mcp": {
    "servers": {
      "semgrep": {
        "command": "docker",
        "args": ["run", "-p", "8000:8000", "ghcr.io/semgrep/mcp:latest"]
      }
    }
  }
}
```

Optionally, you can add it to a file called `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "semgrep": {
      "command": "docker",
      "args": ["run", "-p", "8000:8000", "ghcr.io/semgrep/mcp:latest"]
    }
  }
}
```


## Cursor in SSE Mode

1. Ensure your Semgrep MCP is [running in SSE mode](#sse-mode) in the terminal
1. Go to Cursor > Settings > Cursor Settings
2. Choose the `MCP` tab
3. Click "Add new MCP server"
4. Name: `Semgrep`, Type: `sse`, Server URL: `http://127.0.0.1:8000/sse`
5. Ensure the MCP server is enabled

![cursor MCP settings](/images/cursor.png)

You can also set it up by adding this to `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "Semgrep": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

## Development

> Your contributions to this project are most welcome. Please see the ["good first issue"](https://github.com/semgrep/mcp/labels/good%20first%20issue) label for easy tasks.

### Running the Development Server

Start the MCP server in development mode:
```bash
uv run mcp dev server.py
```

By default, the MCP server runs on `http://localhost:8000` with the inspector server on `http://localhost:6274`.

**Note:** When opening the inspector sever, add query parameters to the url to increase the default timeout of the server from 10s

[http://localhost:6274/?timeout=300000](http://localhost:6274/?timeout=300000)


## Community & Related Projects

This project builds upon and is inspired by several awesome community projects:

### Core Technologies 🛠️
- [Semgrep](https://github.com/semgrep/semgrep) - The underlying static analysis engine that powers this project
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) - The protocol that enables AI agent communication

### Similar Tools 🔍
- [semgrep-vscode](https://github.com/semgrep/semgrep-vscode) - Official VSCode extension for Semgrep
- [semgrep-intellij](https://github.com/semgrep/semgrep-intellij) - IntelliJ plugin for Semgrep

### Community Projects 🌟
- [semgrep-rules](https://github.com/semgrep/semgrep-rules) - The official collection of Semgrep rules
- [mcp-server-semgrep](https://github.com/Szowesgad/mcp-server-semgrep) - Original inspiration written by [Szowesgad](https://github.com/Szowesgad) and [stefanskiasan](https://github.com/stefanskiasan)

### MCP Server Registries

- [Glama](https://glama.ai/mcp/servers/@semgrep/mcp)
<a href="https://glama.ai/mcp/servers/4iqti5mgde">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/4iqti5mgde/badge" alt="Semgrep Server MCP server" />
</a>

- [MCP.so](https://mcp.so/server/mcp/semgrep)
