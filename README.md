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

A MCP server for using [Semgrep](https://semgrep.dev) to scan code for security vulnerabilies. Secure your [vibe coding](https://semgrep.dev/blog/2025/giving-appsec-a-seat-at-the-vibe-coding-table/)! 😅

> This beta project is under active development, we would love your feedback, bug reports, and feature requests. Join the `#mcp` [community slack](https://go.semgrep.dev/slack) channel!

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) is a standardized API for LLMs, Agents, and IDEs like Cursor, VS Code, Windsurf, or anything that supports MCP, to get specialized help, context, and harness the power of tools. Semgrep is a fast, deterministic static analysis semantically understands many [languages](https://semgrep.dev/docs/supported-languages) and comes with with over [5,000 rules](https://semgrep.dev/registry). 🛠️

## Contents

- [Getting Started](#getting-started)
  - [Cursor](#cursor)
  - [Hosted Server](#hosted-server)
- [Demo](#demo)
- [API](#api)
  - [Tools](#tools)
- [Usage](#usage)
  - [Standard Input/Output (stdio)](#standard-inputoutput-stdio)
  - [Server-Sent Events (SSE)](#server-sent-events-sse)
- [Semgrep AppSec Platform](#semgrep-appsec-platform)
- [Integrations](#integrations)
  - [Cursor IDE](#cursor-ide)
  - [VS Code / Copilot](#vs-code--copilot)
  - [Windsurf](#windsurf)
  - [Claude Desktop](#claude-desktop)
  - [OpenAI](#openai)
- [Contributing, Community, and Running From Source](#contributing-community-and-running-from-source)

## Getting started

Run the [python package](https://pypi.org/p/semgrep-mcp) as a CLI command

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

> An experimental server that may break. Once the MCP spec gains support for HTTP Streaming and OAuth in the near future, it will gain new functionality. 🚀

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

## API

### Tools

**Scanning Code**

- `security_check`: Scan code for security vulnerabilities
- `semgrep_scan`: Scan code files for security vulnerabilities with a given config string
- `semgrep_scan_with_custom_rule`: Scan code files using a custom Semgrep rule

**Understanding Code**

- `get_abstract_syntax_tree`: Output the Abstract Syntax Tree (AST) of code

**Meta**

- `supported_languages`: Return the list of langauges Semgrep supports
- `semgrep_rule_schema`: Fetches the latest semgrep rule JSON Schema

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

### Standard Input/Output (stdio)

The stdio transport enables communication through standard input and output streams. This is particularly useful for local integrations and command-line tools. See the [spec](https://modelcontextprotocol.io/docs/concepts/transports#built-in-transport-types) for more details.

#### Python

```bash
semgrep-mcp
```

By default, the python package will run in `stdio` mode. Because it's using the standard input and output streams, it will look like the tool is hanging without any print outs but this is normal.

#### Docker

This server is published to Github's Container Registry ([ghcr.io/semgrep/mcp](http://ghcr.io/semgrep/mcp))

```
docker run -i --rm ghcr.io/semgrep/mcp -t stdio
```

By default, the docker container is in `SSE` mode, so you will have to include `-t stdio` after the image name and run with `-i` to run in [interactive](https://docs.docker.com/reference/cli/docker/container/run/#interactive) mode.

### Server-Sent Events (SSE)

SSE transport enables server-to-client streaming with HTTP POST requests for client-to-server communication. See the [spec](https://modelcontextprotocol.io/docs/concepts/transports#server-sent-events-sse) for more details.

By default, the server wil listen on [0.0.0.0:8000/sse](https://127.0.0.1/sse) for client connections. To change any of this, set [FASTMCP\_\*](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/fastmcp/server.py#L63) environment variables. _The server must be running for clients to connect to it._

#### Python

```bash
semgrep-mcp -t sse
```

By default, the python package will run in `stdio` mode, so you will have to include `-t sse`.

#### Docker

```
docker run -p 8000:0000 ghcr.io/semgrep/mcp
```

## Semgrep AppSec Platform

> Please reach out to [support@semgrep.com](mailto:support@semgrep.com) if needed. ☎️

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

## Integrations

### Cursor IDE

Add the following JSON block to your `~/.cursor/mcp.json` global or `.cursor/mcp.json` project-specific configuration file.

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

![cursor MCP settings](/images/cursor.png)

See [cursor docs](https://docs.cursor.com/context/model-context-protocol) for more info.

### VS Code / Copilot

Click the install buttons at the top of this README for the quickest installation.

#### Manaul Configuration

Add the following JSON block to your User Settings (JSON) file in VS Code. You can do this by pressing `Ctrl + Shift + P` and typing `Preferences: Open User Settings (JSON)`.

```json
{
  "mcp": {
    "servers": {
      "semgrep": {
        "command": "uvx",
        "args": ["semgrep-mcp"]
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
      "command": "uvx",
        "args": ["semgrep-mcp"]
    }
  }
}
```

#### Using Docker

```json
{
  "mcp": {
    "servers": {
      "semgrep": {
        "command": "docker",
        "args": [
          "run",
          "-i",
          "--rm",
          "ghcr.io/semgrep/mcp",
          "-t",
          "stdio"
        ]
      }
    }
  }
}
```

See [VS Code docs](https://code.visualstudio.com/docs/copilot/chat/mcp-servers) for more info.

### Windsurf

See [Windsurf docs](https://docs.windsurf.com/windsurf/mcp) for more info.

### Claude Desktop

See [Anthropci docs](https://docs.anthropic.com/en/docs/agents-and-tools/mcp) for more info.

### OpenAI

See [OpenAI Agents SDK docs](https://openai.github.io/openai-agents-python/mcp/) for more info.

### Custom Clients

See [offical SDK docs](https://modelcontextprotocol.io/clients#adding-mcp-support-to-your-application) for more info.

#### Example Python SSE Client

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

## Contributing, Community, and Running From Source

> We love your feedback, bug reports, feature requests, and code. Join the `#mcp` [community slack](https://go.semgrep.dev/slack) channel! 🙏

See [CONTRIBUTING.md](CONTRIBUTING.md) for more info and details how to run from the MCP server from source code.

### Similar Tools 🔍

- [semgrep-vscode](https://github.com/semgrep/semgrep-vscode) - Official VS Code extension
- [semgrep-intellij](https://github.com/semgrep/semgrep-intellij) - IntelliJ plugin

### Community Projects 🌟

- [semgrep-rules](https://github.com/semgrep/semgrep-rules) - The official collection of Semgrep rules
- [mcp-server-semgrep](https://github.com/Szowesgad/mcp-server-semgrep) - Original inspiration written by [Szowesgad](https://github.com/Szowesgad) and [stefanskiasan](https://github.com/stefanskiasan)

### MCP Server Registries

- [Glama](https://glama.ai/mcp/servers/@semgrep/mcp)

  <a href="https://glama.ai/mcp/servers/4iqti5mgde">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/4iqti5mgde/badge" alt="Semgrep Server MCP server" />
  </a>

- [MCP.so](https://mcp.so/server/mcp/semgrep)

Made with ❤️ by the [Semgrep Team](https://semgrep.dev/about/)
