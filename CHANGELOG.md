# Changelog

## [0.8.0] - 2025-09-08
- Bumped Semgrep version to 1.135.0 for better tracing


## [0.7.2] - 2025-09-05
- Fixed a bug when loading local ~/.semgrep/settings.yml file using deprecated
  yaml.safe_load (PR#168)

## [0.7.1] - 2025-09-03
- Fixed a bug where tool deregistration would accidentally
  attempt to deregister a prompt

## [0.7.0] - 2025-09-02
- Added the ability to remove certain tools by specifying environment variables
  when hosting the server, e.g. `SEMGREP_SCAN_DISABLED=true` or `SEMGREP_FINDINGS_DISABLED=true`.
- Consolidated the `semgrep_scan` and `semgrep_scan_rpc` tools into one tool. You
  can specify to fall back to the `semgrep_scan` CLI-based tool by specifying `USE_SEMGREP_RPC=false`
  when hosting the server.
- Fixed a bug where Semgrep app tokens from being logged in via `semgrep login` on the local filesystem
  would not be properly sourced
- Fixed a bug where `.decode()` would be called on a `None` object when invoking Semgrep, sometimes
- Fixed a bug where in `gemini-cli`, Semgrep MCP tools would be skipped due to its types not
  being renderable into the parameter schema

## [0.6.0] - 2025-08-22

- Fixed a bug breaking authentication when running the Semgrep daemon

## [0.5.1] - 2025-08-18

- Fixed a bug where the `semgrep-interfaces` submodule could not be located properly

## [0.5.0] - 2025-08-18

- Add `semgrep_scan_rpc` tool
- Add `semgrep rpc` daemon functionality, which allows spawning
  a parallel `semgrep` process for logged-in users which can
  scan faster
- Fix: Bump `mcp` version so `FastMCP` constructor does not err


## [0.4.1] - 2025-06-30

- Make MCP transport stateless and use JSON
- Add Helm chart

## [0.4.0] - 2025-06-24

- Add `semgrep_findings` tool

## [0.3.0] - 2025-06-01

- Add support for `streamable-http` mode

## [0.2.1] - 2025-05-29

- Updated `mcp` dependancy to `1.9.2` which changes the default host in SSE mode from `0.0.0.0` to `127.0.0.1`

## [0.2.0] - 2025-04-28

- fix potential path traversal `safe_join`

## [0.1.13] - 2025-04-07

- add `write_custom_semgrep_rule` prompt to MCP server

## [0.1.12] - 2025-04-06

- `-h` and `-v` now work for `--help` and `--version` respectively

## [0.1.11] - 2025-04-06

- This CHANGELOG file
