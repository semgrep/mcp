# semgrep-mcp Helm Chart

This Helm chart deploys the `semgrep-mcp` server using the `semgrep/mcp:main` Docker image.

## Usage

```sh
helm install my-semgrep-mcp ./chart/semgrep-mcp
```

## Configuration

- `image.repository` (default: `semgrep/mcp`)
- `image.tag` (default: `main`)
- `service.port` (default: `8000`)
- `ingress.enabled` (default: `true`)
- `ingress.hosts[0].host` (default: `semgrep-mcp.local`)
- `env`: List of extra environment variables (e.g., `SEMGREP_API_TOKEN`)

## Example: Setting SEMGREP_API_TOKEN

In your `values.yaml` or with `--set`:

```yaml
env:
  - name: SEMGREP_API_TOKEN
    value: "your-token-here"
``` 