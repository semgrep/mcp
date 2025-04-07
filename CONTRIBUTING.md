# Contributing

Your contributions to this project are most welcome! Please see the ["good first issue"](https://github.com/semgrep/mcp/labels/good%20first%20issue) label for easy tasks and join the `#mcp` [community slack](https://go.semgrep.dev/slack) channel for help.

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

##### STDIO Mode

```bash
uv run mcp run ./src/semgrep_mcp/server.py -t stdio
```

##### SSE Mode

```bash
uv run mcp run ./src/semgrep_mcp/server.py -t sse
```

See the official [python mcp sdk](https://github.com/modelcontextprotocol/python-sdk) for more details and configuration options.

Run as a script

```bash
chmod +x ./src/semgrep_mcp/server.py
./src/semgrep_mcp/server.py --help
```

#### Docker

##### STDIO Mode

```bash
docker run -i --rm semgrep-mcp -t stdio
```

##### SSE Mode

```bash
docker run -p 8000:8000 semgrep-mcp
```

### Running the Development Server

Start the MCP server in development mode:

```bash
uv run mcp dev ./src/semgrep_mcp/server.py
```

By default, the MCP server runs on `http://localhost:8000` with the inspector server on `http://localhost:6274`.

**Note:** When opening the inspector sever, add query parameters to the url to increase the default timeout of the server from 10s

[http://localhost:6274/?timeout=300000](http://localhost:6274/?timeout=300000)

# Releasing

1. First we need to bump the version

   ```bash
   # takes one argument {patch, minor, major} with 'minor' as the default argument
   uv run python ./scripts/bump_version.py 
   ```

1. Verify the release diff looks right, add any [changelog](CHANGELOG.md) notes.
1. Merge the release in to `main`
1. Tag with `git tag -a vX.Y.Z -m "vX.Y.Z"`
1. Verify builds are green
1. Manually approve the [`publish.yaml`](https://github.com/semgrep/mcp/actions/workflows/publish.yml) workflow.
1. Verify the release looks good on [PyPI](https://pypi.org/p/semgrep-mcp)
