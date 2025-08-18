# Changelog
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
