#!/usr/bin/env python3
"""Configuration script for Claude Code integration with Semgrep MCP using proper CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def check_claude_cli_available() -> bool:
    """Check if Claude CLI is available."""
    try:
        result = subprocess.run(["claude", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def configure_with_claude_cli() -> bool:
    """Configure Semgrep MCP using Claude CLI commands."""
    print("🔧 Configuring Semgrep MCP using Claude CLI...")

    # Get the current directory (should be the semgrep-mcp project root)
    current_dir = Path(__file__).parent.parent
    
    # Build command for semgrep-mcp from current directory
    command = [
        "uv",
        "run",
        "--directory",
        str(current_dir),
        "semgrep-mcp"
    ]

    # Prepare environment variables
    env_vars = {}
    
    # Add SEMGREP_APP_TOKEN if it exists
    if semgrep_token := os.getenv("SEMGREP_APP_TOKEN"):
        env_vars["SEMGREP_APP_TOKEN"] = semgrep_token

    # Prepare environment arguments for Claude CLI
    env_args = []
    for key, value in env_vars.items():
        env_args.extend(["-e", f"{key}={value}"])

    # Build the full Claude CLI command for user scope (global)
    claude_cmd = [
        "claude",
        "mcp",
        "add",
        "--scope",
        "user",
        "semgrep-mcp",
        *env_args,
        "--",
        *command,
    ]

    print(f"🚀 Running: {' '.join(claude_cmd)}")

    try:
        result = subprocess.run(claude_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Semgrep MCP configured successfully using Claude CLI")
            return True
        else:
            print(f"❌ Claude CLI configuration failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Failed to run Claude CLI: {e}")
        return False


def configure_with_json_file() -> bool:
    """Fallback: Configure using JSON file method."""
    print("🔧 Configuring Semgrep MCP using JSON file fallback...")

    home = Path.home()
    claude_config = home / ".claude.json"
    current_dir = Path(__file__).parent.parent

    # Prepare configuration
    config = {
        "mcpServers": {
            "semgrep-mcp": {
                "command": "uv",
                "args": [
                    "run",
                    "--directory", 
                    str(current_dir),
                    "semgrep-mcp"
                ],
                "env": {},
            }
        }
    }

    # Add environment variables
    if semgrep_token := os.getenv("SEMGREP_APP_TOKEN"):
        config["mcpServers"]["semgrep-mcp"]["env"]["SEMGREP_APP_TOKEN"] = semgrep_token

    # Load existing config if it exists
    existing_config = {}
    if claude_config.exists():
        try:
            with claude_config.open() as f:
                existing_config = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load existing config: {e}")

    # Merge configurations
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}

    existing_config["mcpServers"]["semgrep-mcp"] = config["mcpServers"]["semgrep-mcp"]

    # Write configuration
    try:
        with claude_config.open("w") as f:
            json.dump(existing_config, f, indent=2)
        print(f"✅ Configuration written to: {claude_config}")
        return True
    except OSError as e:
        print(f"❌ Failed to write configuration: {e}")
        return False


def verify_configuration() -> bool:
    """Verify the configuration was successful."""
    print("🔍 Verifying configuration...")

    # Check if Claude CLI can list the server
    if check_claude_cli_available():
        try:
            result = subprocess.run(
                ["claude", "mcp", "list"], capture_output=True, text=True
            )
            if result.returncode == 0 and "semgrep-mcp" in result.stdout:
                print("✅ Semgrep MCP found in Claude MCP server list")
                return True
            else:
                print("⚠️  Semgrep MCP not found in Claude MCP server list")
                return False
        except Exception as e:
            print(f"⚠️  Could not verify via Claude CLI: {e}")

    # Fallback: check if config file exists
    claude_config = Path.home() / ".claude.json"
    if claude_config.exists():
        try:
            with claude_config.open() as f:
                config = json.load(f)

            if "mcpServers" in config and "semgrep-mcp" in config["mcpServers"]:
                print("✅ Semgrep MCP found in configuration file")
                return True
            else:
                print("⚠️  Semgrep MCP not found in configuration file")
                return False
        except Exception as e:
            print(f"⚠️  Could not verify configuration file: {e}")
            return False

    print("⚠️  No configuration found")
    return False


def main():
    """Main configuration function."""
    print("🔧 Configuring Claude Code integration for Semgrep MCP...")
    print("🌐 Setting up global configuration for all Claude Code sessions...")

    # Check prerequisites
    if not check_claude_cli_available():
        print("⚠️  Claude CLI not found. Falling back to JSON file configuration.")
        print(
            "   For full functionality, install Claude CLI from: https://claude.ai/code"
        )
        success = configure_with_json_file()
    else:
        print("✅ Claude CLI found. Using recommended CLI configuration method.")
        success = configure_with_claude_cli()

        # If CLI method fails, try JSON fallback
        if not success:
            print("⚠️  CLI method failed. Trying JSON file fallback...")
            success = configure_with_json_file()

    if not success:
        print("❌ Configuration failed")
        sys.exit(1)

    # Verify configuration
    verification_success = verify_configuration()

    # Print summary
    current_dir = Path(__file__).parent.parent
    print("\n📋 Global Configuration Summary:")
    print("   🌐 Configuration Type: Global (available to all Claude Code sessions)")
    print("   📝 Server Name: semgrep-mcp")
    print(f"   🚀 Command: uv run --directory {current_dir} semgrep-mcp")

    print("   🌍 Environment Variables:")
    if os.getenv("SEMGREP_APP_TOKEN"):
        print(f"     SEMGREP_APP_TOKEN: {'*' * min(8, len(os.getenv('SEMGREP_APP_TOKEN')))}")
    else:
        print("     SEMGREP_APP_TOKEN: (not set)")

    # Check for environment variables
    print("\n🔍 Environment Check:")

    if not os.getenv("SEMGREP_APP_TOKEN"):
        print("⚠️  SEMGREP_APP_TOKEN not found in environment")
        print("   This is optional but recommended for accessing Semgrep findings")
        print("   Set it with: export SEMGREP_APP_TOKEN=your_token_here")
    else:
        print("✅ SEMGREP_APP_TOKEN is set")

    # Check if semgrep is available
    try:
        result = subprocess.run(
            ["semgrep", "--version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Semgrep is installed and available")
        else:
            print("⚠️  Semgrep is not working properly")
    except FileNotFoundError:
        print("❌ Semgrep is not installed")
        print("   Install it with: pip install semgrep")

    print("\n🚀 Next Steps:")
    if verification_success:
        print("1. 🎉 Configuration successful! Semgrep MCP is ready to use.")
        print("2. 🔄 Restart Claude Code to load the new configuration")
        print("3. 🌐 The Semgrep MCP tools will be available in ALL Claude Code sessions")
        print("4. 🔧 Try using the tools in any conversation:")
        print("   • semgrep_scan")
        print("   • semgrep_findings")
        print("   • security_check")
        print("5. 📊 Check MCP status in Claude Code with: /mcp")
    else:
        print("1. ⚠️  Configuration may not be fully working")
        print("2. 🔄 Try restarting Claude Code")
        print("3. 📋 If issues persist, run: claude mcp list")
        print("4. 🔧 Or check the configuration file manually")

    print("\n✨ Semgrep MCP global configuration complete!")
    if verification_success:
        print("🌟 The MCP server is configured and ready for all Claude Code sessions!")
    else:
        print("🔧 Please verify the configuration before using.")


if __name__ == "__main__":
    main()