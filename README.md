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

MCP Server for using Semgrep to scan code

[MCP](https://modelcontextprotocol.io/) is like LSP or unix pipes but for LLMs and AI Agents and coding tools such as Cursor.

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

### Docker

```bash
docker run -p 8000:8000 mcp-server
```

### CLI
```bash
uv run mcp run server.py
```

[Additional info](https://github.com/modelcontextprotocol/python-sdk) on the python mcp sdk

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



## Cursor Plugin

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

## Developlment

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
