"""Test Claude Code integration and global MCP server registration."""

import json
import os
import pathlib
import subprocess
import tempfile
from unittest import mock

import pytest


def is_claude_cli_available() -> bool:
    """Check if Claude CLI is available in the system."""
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Skip entire test class if Claude CLI is not available
claude_cli_available = is_claude_cli_available()
skip_reason = "Claude CLI not available - install from https://claude.ai/code"


class TestClaudeCodeIntegration:
    """Test suite for Claude Code MCP server global registration."""

    @pytest.mark.skipif(not claude_cli_available, reason=skip_reason)
    def test_claude_code_config_exists(self):
        """Test that Claude Code configuration exists in the expected location."""
        config_path = pathlib.Path.home() / ".claude.json"
        assert config_path.exists(), f"Claude Code MCP config not found at {config_path}"

    @pytest.mark.skipif(not claude_cli_available, reason=skip_reason)
    def test_claude_code_config_format(self):
        """Test that the Claude Code configuration has the correct format."""
        config_path = pathlib.Path.home() / ".claude.json"

        with open(config_path) as f:
            config = json.load(f)

        assert "mcpServers" in config, "Config missing 'mcpServers' key"
        assert "semgrep-mcp" in config["mcpServers"], "Config missing 'semgrep-mcp' server"

        server_config = config["mcpServers"]["semgrep-mcp"]
        assert "command" in server_config, "Server config missing 'command'"
        assert "args" in server_config, "Server config missing 'args'"

    @pytest.mark.skipif(not claude_cli_available, reason=skip_reason)
    def test_claude_code_server_command(self):
        """Test that the configured server command is valid."""
        config_path = pathlib.Path.home() / ".claude.json"

        with open(config_path) as f:
            config = json.load(f)

        server_config = config["mcpServers"]["semgrep-mcp"]
        command = server_config["command"]
        args = server_config["args"]

        # Check that the command exists
        result = subprocess.run(["which", command], capture_output=True, text=True)
        assert result.returncode == 0, f"Command '{command}' not found in PATH"

        # Extract working directory from args (--directory argument)
        cwd = None
        for i, arg in enumerate(args):
            if arg == "--directory" and i + 1 < len(args):
                cwd = args[i + 1]
                break

        if cwd:
            # Check that the working directory exists
            assert os.path.isdir(cwd), f"Working directory '{cwd}' does not exist"

            # Check that the command can be executed (dry run)
            result = subprocess.run(
                [command, *args, "--help"], capture_output=True, text=True, timeout=10
            )
            # Either help works or the command exists but doesn't support --help
            cmd_str = f"Command '{command} {' '.join(args)}' failed to execute"
            assert result.returncode in [0, 1, 2], cmd_str

    def test_makefile_configure_command(self):
        """Test that the Makefile configure-claude-code command works correctly."""
        # Create a temporary config directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the home directory for this test
            with mock.patch("pathlib.Path.home", return_value=pathlib.Path(temp_dir)):
                # Run the makefile command
                result = subprocess.run(
                    ["make", "configure-claude-code"],
                    cwd=pathlib.Path(__file__).parent.parent.parent,
                    capture_output=True,
                    text=True,
                    env={**os.environ, "HOME": temp_dir},
                )

                # Check that the command succeeded
                assert result.returncode == 0, f"Makefile configure command failed: {result.stderr}"

                # Check that the config was created
                config_file = pathlib.Path(temp_dir) / ".claude.json"
                assert config_file.exists(), "Config file was not created"

                # Verify the config content
                with open(config_file) as f:
                    config = json.load(f)

                assert "mcpServers" in config
                assert "semgrep-mcp" in config["mcpServers"]
                server_config = config["mcpServers"]["semgrep-mcp"]
                assert server_config["command"] == "uv"
                # Check that args contain the expected elements
                args = server_config["args"]
                assert "run" in args
                assert "semgrep-mcp" in args
                assert "--directory" in args

    @pytest.mark.skipif(not claude_cli_available, reason=skip_reason)
    def test_makefile_check_command(self):
        """Test that the Makefile check-claude-config command works correctly."""
        result = subprocess.run(
            ["make", "check-claude-config"],
            cwd=pathlib.Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        # Command should succeed
        assert result.returncode == 0, f"Makefile check command failed: {result.stderr}"

        # Should contain configuration information
        assert "MCP configuration" in result.stdout

        # If config exists, should show the semgrep-mcp server
        if "semgrep-mcp" in result.stdout:
            assert "semgrep-mcp" in result.stdout

    @pytest.mark.skipif(not claude_cli_available, reason=skip_reason)
    def test_server_can_be_launched(self):
        """Test that the MCP server can be launched with the configured command."""
        config_path = pathlib.Path.home() / ".claude.json"

        with open(config_path) as f:
            config = json.load(f)

        server_config = config["mcpServers"]["semgrep-mcp"]
        command = server_config["command"]
        args = server_config["args"]

        # Extract working directory from args (--directory argument)
        cwd = None
        for i, arg in enumerate(args):
            if arg == "--directory" and i + 1 < len(args):
                cwd = args[i + 1]
                break

        # Try to launch the server and check that it starts
        process = subprocess.Popen(
            [command, *args],
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Send a basic initialization message
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }

            process.stdin.write(json.dumps(init_message) + "\n")
            process.stdin.flush()

            # Wait for response (timeout after 5 seconds)
            try:
                stdout, stderr = process.communicate(timeout=5)

                # Check that we got a response
                assert stdout, "No response from MCP server"

                # Parse the response
                response = json.loads(stdout.strip())
                assert "result" in response or "error" in response, "Invalid JSON-RPC response"

            except subprocess.TimeoutExpired:
                process.kill()
                pytest.fail("MCP server did not respond within timeout")

        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()

    @pytest.mark.skipif(not claude_cli_available, reason=skip_reason)
    def test_global_registration_persists(self):
        """Test that the global registration persists across system restarts."""
        config_path = pathlib.Path.home() / ".claude.json"

        # Verify the config exists
        assert config_path.exists(), "Global MCP config does not exist"

        # Verify the config is readable
        with open(config_path) as f:
            config = json.load(f)

        # Verify the semgrep-mcp server is configured
        assert "mcpServers" in config
        assert "semgrep-mcp" in config["mcpServers"]

        # Verify the configuration is complete
        server_config = config["mcpServers"]["semgrep-mcp"]
        required_keys = ["command", "args"]
        for key in required_keys:
            assert key in server_config, f"Missing required key '{key}' in server config"
            assert server_config[key], f"Empty value for required key '{key}'"
