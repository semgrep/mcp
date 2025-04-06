<p align="center">
  <a href="https://semgrep.dev">
    <picture>
      <source media="(prefers-color-scheme: light)" srcset="images/semgrep-logo-light.svg">
      <source media="(prefers-color-scheme: dark)" srcset="images/semgrep-logo-dark.svg">
      <img src="https://raw.githubusercontent.com/semgrep/mcp/main/images/semgrep-logo-light.svg" height="60" alt="Semgrep logo"/>
    </picture>
  </a>
</p>
<p align="center">
  <a href="https://semgrep.dev/docs/">
      <img src="https://img.shields.io/badge/Semgrep-docs-2acfa6?style=flat-square" alt="Documentation" />
  </a>
  <a href="https://go.semgrep.dev/slack">
    <img src="https://img.shields.io/badge/Slack-4.5k%20-4A154B?style=flat-square&logo=slack&logoColor=white" alt="Join Semgrep community Slack" />
  </a>
  <a href="https://www.linkedin.com/company/semgrep/">
    <img src="https://img.shields.io/badge/LinkedIn-follow-0a66c2?style=flat-square" alt="Follow on LinkedIn" />
  </a>
  <a href="https://x.com/intent/follow?screen_name=semgrep">
    <img src="https://img.shields.io/badge/semgrep-000000?style=flat-square&logo=x&logoColor=white?style=flat-square" alt="Follow @semgrep on X" />
  </a>
</p>

# Semgrep MCP Server

[![Install in VS Code UV](https://img.shields.io/badge/VS_Code-uv-0098FF?style=flat-square&logo=githubcopilot&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22semgrep-mcp%22%5D%7D)
[![Install in VS Code Docker](https://img.shields.io/badge/VS_Code-docker-0098FF?style=flat-square&logo=githubcopilot&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%20%22-i%22%2C%20%22--rm%22%2C%20%22ghcr.io%2Fsemgrep%2Fmcp%22%2C%20%22-t%22%2C%20%22stdio%22%5D%7D)
[![Install in VS Code semgrep.ai](https://img.shields.io/badge/VS_Code-semgrep.ai-0098FF?style=flat-square&logo=githubcopilot&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22server%22%3A%22https%3A%2F%2Fmcp.semgrep.ai%2Fsse%22%7D)
[![PyPI](https://img.shields.io/pypi/v/semgrep-mcp?style=flat-square&color=blue&logo=python&logoColor=white)](https://pypi.org/project/semgrep-mcp/)
[![Docker](https://img.shields.io/badge/docker-ghcr.io%2Fsemgrep%2Fmcp-0098FF?style=flat-square&logo=docker&logoColor=white)](https://ghcr.io/semgrep/mcp)
[![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-uv-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22semgrep-mcp%22%5D%7D&quality=insiders)
[![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-docker-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=semgrep&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%20%22-i%22%2C%20%22--rm%22%2C%20%22ghcr.io%2Fsemgrep%2Fmcp%22%2C%20%22-t%22%2C%20%22stdio%22%5D%7D&quality=insiders)

A MCP server for using [Semgrep](https://semgrep.dev) to scan code for security vulnerabilies. Secure your [vibe coding](https://www.linkedin.com/posts/daghanaltas_vibecoding-activity-7311434119924588545-EqvZ/) 😅

> This beta project is under active development, we would love your feedback, bug reports, and feature requests. Join the `#mcp` [community slack](https://go.semgrep.dev/slack) channel!

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) is a standardized API for LLMs, Agents, and IDEs like Cursor, VS Code, Windsurf, or anything that supports MCP, to get specialized help, context, and harness the power of tools. Semgrep is a fast, deterministic static analysis semantically understands many [languages](https://semgrep.dev/docs/supported-languages) and comes with with over [5,000 rules](https://semgrep.dev/registry). 🛠️

## Contents

- [Getting Started](#getting-started)
  - [Cursor](#cursor)
  - [Hosted Server](#hosted-server)
- [Demo](#demo)
- [Tools](#mcp-tools)
- [Semgrep AppSec Platform](#semgrep-appsec-platform)
- [Usage](#usage)

## Getting started

Install the [python package](https://pypi.org/p/semgrep-mcp) and run as a command ([stdio mode](https://modelcontextprotocol.io/docs/concepts/transports#built-in-transport-types))

```bash
uvx semgrep-mcp # see --help for more options
```

or as a [docker container](https://ghcr.io/semgrep/mcp)

```bash
docker run -i --rm ghcr.io/semgrep/mcp -t stdio 
```

### Cursor

example [`mcp.json`](https://docs.cursor.com/context/model-context-protocol)

```json
{
  "mcpServers": {
    "semgrep": {
      "command": "uvx",
      "args": ["semgrep-mcp"],
      "env": {
        "SEMGREP_APP_TOKEN": "<token>"
      }
    }
  }
}

```

Add an instruction to your [`.cursor/rules`](https://docs.cursor.com/context/rules-for-ai) to use automatically

```text
Always scan code generated using Semgrep for security vulnerabilities
```

### Hosted Server

> An experimental server that may break. Once the MCP spec gains support for HTTP Streaming and OAuth in the near future, it will gain new functionality.

`mcp.json`

```json
{
  "mcpServers": {
    "semgrep": {
      "url": "https://mcp.semgrep.ai/sse"
    }
  }
}
```

## Demo

<a href="https://www.loom.com/share/8535d72e4cfc4e1eb1e03ea223a702df"> <img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/8535d72e4cfc4e1eb1e03ea223a702df-1047fabea7261abb-full-play.gif"> </a>

## MCP Tools

**Scanning Code**

- `security_check`: Scan code for security vulnerabilities
- `semgrep_scan`: Scan code files for security vulnerabilities with a given config string
- `semgrep_scan_with_custom_rule`: Scan code files using a custom Semgrep rule

**Understanding Code**

- `get_abstract_syntax_tree`: Output the Abstract Syntax Tree (AST) of code

**Meta**

- `supported_languages`: Return the list of langauges Semgrep supports
- `semgrep_rule_schema`: Fetches the latest semgrep rule JSON Schema

## Semgrep AppSec Platform

> Please reach out to [support@semgrep.com](mailto:support@semgrep.com) if needed

To optionally connect to Semgrep AppSec Platform:

1. [Login](https://semgrep.dev/login/) or sign up
1. Generate a token from [Settings](https://semgrep.dev/orgs/-/settings/tokens/api) page
1. Add it to your environment variables
   - CLI (`export SEMGREP_APP_TOKEN=<token>`)

   - Docker (`docker run -e SEMGREP_APP_TOKEN=<token>`)

   - MCP Config JSON

     ```json
     "env": {
       "SEMGREP_APP_TOKEN": "<token>"
     }
     ```

## Usage

This package is published to PyPI as [semgrep-mcp](https://pypi.org/p/semgrep-mcp) and can be installed and run with [pip](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#install-a-package), [pipx](https://pipx.pypa.io/), [uv](https://docs.astral.sh/uv/), [poetry](https://python-poetry.org/), or any python package manager.

```bash
$ pipx install semgrep-mcp
$ semgrep-mcp --help

Usage: semgrep-mcp [OPTIONS]

  Entry point for the MCP server

  Supports both stdio and sse transports. For stdio, it will read from stdin
  and write to stdout. For sse, it will start an HTTP server on port 8000.

Options:
  --version                    Show the version and exit.
  -t, --transport [stdio|sse]  Transport protocol to use (stdio or sse)
  --help                       Show this message and exit.
```

## Run From Source

### Setup

#### CLI Environment

1. Install `uv` using their [installation instructions](https://docs.astral.sh/uv/getting-started/installation/)

1. Ensure you have Python 3.13+ installed

1. Clone this repository

1. Install Semgrep ([additional methods](https://semgrep.dev/docs/getting-started/quickstart)):

   ```bash
   pip install semgrep
   ```

#### Docker

1. Install `docker` using their [installation instructions](https://docs.docker.com/get-started/get-docker/)
1. Clone this repository
1. Build the server

```bash
docker build -t semgrep-mcp .
```

### Running

#### CLI Environment

##### SSE Mode<a name="sse-mode"></a>

```bash
uv run mcp run ./src/semgrep_mcp/server.py -t sse
```

Or as a script

```bash
chmod +x ./src/semgrep_mcp/server.py
./src/semgrep_mcp/server.py -t sse
```

##### STDIO Mode<a name="stdio-mode"></a>

```bash
uv run mcp run ./src/semgrep_mcp/server.py -t stdio
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
        "args": ["run", "mcp", "run", "src", "semgrep_mcp", "server.py"]
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
        "args": ["run", "mcp", "run", "src", "semgrep_mcp", "server.py"]
    }
  }
}
```

## Cursor in SSE Mode

1. Ensure your Semgrep MCP is [running in SSE mode](#sse-mode) in the terminal
1. Go to Cursor > Settings > Cursor Settings
1. Choose the `MCP` tab
1. Click "Add new MCP server"
1. Name: `Semgrep`, Type: `sse`, Server URL: `http://127.0.0.1:8000/sse`
1. Ensure the MCP server is enabled

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
