<p align="center">
  <a href="https://semgrep.dev">
    <picture>
      <source media="(prefers-color-scheme: light)" srcset="images/semgrep-logo-light.svg">
      <source media="(prefers-color-scheme: dark)" srcset="images/semgrep-logo-dark.svg">
      <img src="https://raw.githubusercontent.com/semgrep/mcp-server/main/images/semgrep-logo-light.svg" height="100" alt="Semgrep logo"/>
    </picture>
  </a>
</p>
<p align="center">
  <a href="https://semgrep.dev/docs/">
      <img src="https://img.shields.io/badge/docs-semgrep.dev-purple?style=flat-square" alt="Documentation" />
  </a>
  <a href="https://go.semgrep.dev/slack">
    <img src="https://img.shields.io/badge/slack-3.5k%20members-green?style=flat-square" alt="Join Semgrep community Slack" />
  </a>
  <a href="https://github.com/semgrep/mcp-server/issues/new/choose">
    <img src="https://img.shields.io/badge/issues-welcome-green?style=flat-square" alt="Issues welcome!" />
  </a>

  <a href="https://x.com/intent/follow?screen_name=semgrep">
    <img src="https://img.shields.io/twitter/follow/semgrep" alt="Follow @semgrep on X" />
  </a>
</p>
</br>

# [beta] Semgrep MCP Server

MCP Server for using Semgrep to scan code.

## Demo
<a href="https://www.loom.com/share/8535d72e4cfc4e1eb1e03ea223a702df"> <img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/8535d72e4cfc4e1eb1e03ea223a702df-1047fabea7261abb-full-play.gif"> </a>

[MCP](https://modelcontextprotocol.io/) is like LSP or Unix pipes for LLMs, AI Agents, and coding tools such as Cursor.

## Features

This MCP Server provides a comprehensive interface to Semgrep through the Model Context Protocol, offering the following tools:

**Scanning Code**
- `semgrep_scan`: Scan code snippets for security vulnerabilities
- `scan_directory`: Perform Semgrep scan on a directory

**Customization**
- `list_rules`: List available Semgrep rules with optional language filtering
- `create_rule`: Create custom Semgrep rules

**Results**
- `analyze_results`: Analyze scan results including severity counts and top affected files
- `filter_results`: Filter scan results by severity, rule ID, file path, etc.
- `export_results`: Export scan results in various formats (JSON, SARIF, text)
- `compare_results`: Compare two scan results to identify new and fixed issues

## Installation

### CLI

1. Install `uv` using their [installation instructions](https://docs.astral.sh/uv/getting-started/installation/)
1. Ensure you have Python 3.13+ installed
2. Clone this repository
3. Install Semgrep ([additional methods](https://semgrep.dev/docs/getting-started/quickstart)):

   ```bash
   pip install semgrep
   ```

### Docker

```bash
docker build -t mcp-server .
```

## Usage

### CLI

#### SSE<a name="sse-mode"></a>
Run by invoking uv directly
```bash
uv run mcp run server.py -t sse
```
Or as a uv script
```bash
chmod +x server.py
./server.py
```

#### stdio
```bash
uv run mcp run server.py -t stdio
```

[Additional info](https://github.com/modelcontextprotocol/python-sdk) on the python mcp sdk

### Docker

```bash
docker run -p 8000:8000 mcp-server
```

Also published to [ghcr.io/semgrep/mcp](http://ghcr.io/semgrep/mcp).

```bash
docker run -p 8000:8000 ghcr.io/semgrep/mcp:latest
```

### Creating your own client

```python
from mcp.client import Client

client = Client()
client.connect("localhost:8000")

# Scan code for security issues
results = client.call_tool("semgrep_scan", {
    "code": "def get_user(user_id):\n    return User.objects.get(id=user_id)",
    "language": "python"
})
```

## VS Code Integration

For one-click installation, click one of the install buttons below:

[![Install with UV in VS Code](https://img.shields.io/badge/VS_Code-UV-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22uv%22%2C%22args%22%3A%5B%22run%22%2C%22mcp%22%2C%22run%22%2C%22server.py%22%2C%22-t%22%2C%22sse%22%5D%7D) [![Install with UV in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-UV-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22uv%22%2C%22args%22%3A%5B%22run%22%2C%22mcp%22%2C%22run%22%2C%22server.py%22%2C%22-t%22%2C%22sse%22%5D%7D&quality=insiders)

[![Install with Docker in VS Code](https://img.shields.io/badge/VS_Code-Docker-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%22-p%22%2C%228000%3A8000%22%2C%22ghcr.io%2Fsemgrep%2Fmcp%3Alatest%22%5D%7D) [![Install with Docker in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Docker-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%22-p%22%2C%228000%3A8000%22%2C%22ghcr.io%2Fsemgrep%2Fmcp%3Alatest%22%5D%7D&quality=insiders)

### Manual Installation

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


## Cursor Plugin

1. Ensure your Semgrep MCP is [running in SSE mode](#sse-mode)
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


## Advanced Usage

The server supports advanced Semgrep functionality:

```python
# Scan an entire directory
results = client.call_tool("scan_directory", {
    "path": "/path/to/code",
    "config": "p/security-audit"
})

# Filter results by severity
filtered = client.call_tool("filter_results", {
    "results_file": "/path/to/results.json",
    "severity": "ERROR"
})
```

## Development

### Running the Development Server

Start the MCP server in development mode:
```bash
uv run mcp dev server.py
```

By default, the server runs on `http://localhost:3000` with the inspector server on `http://localhost:5173`.

**Note:** When opening the inspector sever, add query parameters to the url to increase the default timeout of the server from 10s
```
http://localhost:5173/?timeout=300000
```

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
