#!/usr/bin/env python3
"""Configuration script for Claude Code integration with Semgrep MCP using proper CLI commands."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _validate_env_var_name(name: str) -> bool:
    """Validate environment variable name to prevent injection."""
    return re.match(r'^[A-Z_][A-Z0-9_]*$', name) is not None


def _validate_path(path: Path) -> bool:
    """Validate path to prevent directory traversal."""
    try:
        # Resolve and check if path is within reasonable bounds
        resolved = path.resolve()
        # Must be absolute and not contain suspicious patterns
        path_str = str(resolved)
        return (
            resolved.is_absolute() and
            '..' not in path.parts and
            not any(part.startswith('.') and len(part) > 1 for part in path.parts[1:])
        )
    except (OSError, ValueError):
        return False


def check_claude_cli_available() -> bool:
    """Check if Claude CLI is available."""
    try:
        result = subprocess.run(
            ["claude", "--version"], 
            capture_output=True, 
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def configure_with_claude_cli() -> bool:
    """Configure Semgrep MCP using Claude CLI commands."""
    print("🔧 Configuring Semgrep MCP using Claude CLI...")

    # Get the current directory (should be the semgrep-mcp project root)
    current_dir = Path(__file__).parent.parent
    
    # Validate path for security
    if not _validate_path(current_dir):
        print("❌ Invalid project directory path")
        return False
    
    # Build command for semgrep-mcp from current directory
    command = [
        "uv",
        "run",
        "--directory",
        str(current_dir),
        "semgrep-mcp"
    ]

    # Prepare environment variables with validation
    env_vars = {}
    
    # Add SEMGREP_APP_TOKEN if it exists and is valid
    if semgrep_token := os.getenv("SEMGREP_APP_TOKEN"):
        if _validate_env_var_name("SEMGREP_APP_TOKEN"):
            # Validate token format (basic check)
            if re.match(r'^[a-zA-Z0-9_-]+$', semgrep_token):
                env_vars["SEMGREP_APP_TOKEN"] = semgrep_token
            else:
                print("⚠️  Invalid SEMGREP_APP_TOKEN format, skipping")

    # Prepare environment arguments for Claude CLI
    env_args = []
    for key, value in env_vars.items():
        # Double-check key is safe
        if _validate_env_var_name(key):
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

    # Safe command display (don't show sensitive values)
    safe_cmd = []
    skip_next = False
    for i, arg in enumerate(claude_cmd):
        if skip_next:
            safe_cmd.append("***")
            skip_next = False
        elif arg == "-e":
            safe_cmd.append(arg)
            skip_next = True
        else:
            safe_cmd.append(arg)
    
    print(f"🚀 Running: {' '.join(safe_cmd)}")

    try:
        result = subprocess.run(
            claude_cmd, 
            capture_output=True, 
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("✅ Semgrep MCP configured successfully using Claude CLI")
            return True
        else:
            # Don't expose potentially sensitive stderr content
            print("❌ Claude CLI configuration failed")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Claude CLI command timed out")
        return False
    except Exception as e:
        print(f"❌ Failed to run Claude CLI: {type(e).__name__}")
        return False


def configure_with_json_file() -> bool:
    """Fallback: Configure using JSON file method."""
    print("🔧 Configuring Semgrep MCP using JSON file fallback...")

    home = Path.home()
    claude_config = home / ".claude.json"
    current_dir = Path(__file__).parent.parent

    # Validate paths
    if not _validate_path(current_dir):
        print("❌ Invalid project directory path")
        return False
    
    if not _validate_path(claude_config.parent):
        print("❌ Invalid config directory path")
        return False

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

    # Add environment variables with validation
    if semgrep_token := os.getenv("SEMGREP_APP_TOKEN"):
        if _validate_env_var_name("SEMGREP_APP_TOKEN"):
            if re.match(r'^[a-zA-Z0-9_-]+$', semgrep_token):
                config["mcpServers"]["semgrep-mcp"]["env"]["SEMGREP_APP_TOKEN"] = semgrep_token
            else:
                print("⚠️  Invalid SEMGREP_APP_TOKEN format, skipping")

    # Load existing config if it exists
    existing_config = {}
    if claude_config.exists():
        try:
            # Check file size to prevent loading huge files
            if claude_config.stat().st_size > 1024 * 1024:  # 1MB limit
                print("❌ Config file too large")
                return False
            
            with claude_config.open() as f:
                existing_config = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print("⚠️  Could not load existing config, creating new one")

    # Merge configurations safely
    if not isinstance(existing_config, dict):
        existing_config = {}
    
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}
    
    if not isinstance(existing_config["mcpServers"], dict):
        existing_config["mcpServers"] = {}

    existing_config["mcpServers"]["semgrep-mcp"] = config["mcpServers"]["semgrep-mcp"]

    # Write configuration with safety checks
    try:
        # Create backup if file exists
        if claude_config.exists():
            backup_path = claude_config.with_suffix('.json.backup')
            claude_config.rename(backup_path)
        
        with claude_config.open("w") as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=True)
        
        # Remove backup on success
        backup_path = claude_config.with_suffix('.json.backup')
        if backup_path.exists():
            backup_path.unlink()
        
        print(f"✅ Configuration written to: {claude_config}")
        return True
    except OSError:
        print("❌ Failed to write configuration")
        # Restore backup if it exists
        backup_path = claude_config.with_suffix('.json.backup')
        if backup_path.exists():
            backup_path.rename(claude_config)
        return False


def verify_configuration() -> bool:
    """Verify the configuration was successful."""
    print("🔍 Verifying configuration...")

    # Check if Claude CLI can list the server
    if check_claude_cli_available():
        try:
            result = subprocess.run(
                ["claude", "mcp", "list"], 
                capture_output=True, 
                text=True,
                timeout=15
            )
            if result.returncode == 0 and "semgrep-mcp" in result.stdout:
                print("✅ Semgrep MCP found in Claude MCP server list")
                return True
            else:
                print("⚠️  Semgrep MCP not found in Claude MCP server list")
                return False
        except subprocess.TimeoutExpired:
            print("⚠️  Claude CLI verification timed out")
            return False
        except Exception:
            print("⚠️  Could not verify via Claude CLI")

    # Fallback: check if config file exists
    claude_config = Path.home() / ".claude.json"
    if claude_config.exists() and _validate_path(claude_config):
        try:
            # Check file size before loading
            if claude_config.stat().st_size > 1024 * 1024:
                print("❌ Config file too large to verify")
                return False
                
            with claude_config.open() as f:
                config = json.load(f)

            if (isinstance(config, dict) and 
                "mcpServers" in config and 
                isinstance(config["mcpServers"], dict) and
                "semgrep-mcp" in config["mcpServers"]):
                print("✅ Semgrep MCP found in configuration file")
                return True
            else:
                print("⚠️  Semgrep MCP not found in configuration file")
                return False
        except (OSError, json.JSONDecodeError):
            print("⚠️  Could not verify configuration file")
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
    # Safe path display
    if _validate_path(current_dir):
        print(f"   🚀 Command: uv run --directory {current_dir} semgrep-mcp")
    else:
        print("   🚀 Command: [path validation failed]")

    print("   🌍 Environment Variables:")
    # Safe token display
    token = os.getenv("SEMGREP_APP_TOKEN")
    if token and re.match(r'^[a-zA-Z0-9_-]+$', token):
        print(f"     SEMGREP_APP_TOKEN: {'*' * min(8, len(token))}")
    else:
        print("     SEMGREP_APP_TOKEN: (not set)")

    # Check for environment variables
    print("\n🔍 Environment Check:")

    if not token:
        print("⚠️  SEMGREP_APP_TOKEN not found in environment")
        print("   This is optional but recommended for accessing Semgrep findings")
        print("   Set it with: export SEMGREP_APP_TOKEN=your_token_here")
    elif not re.match(r'^[a-zA-Z0-9_-]+$', token):
        print("⚠️  SEMGREP_APP_TOKEN has invalid format")
    else:
        print("✅ SEMGREP_APP_TOKEN is set")

    # Check if semgrep is available
    try:
        result = subprocess.run(
            ["semgrep", "--version"], 
            capture_output=True, 
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ Semgrep is installed and available")
        else:
            print("⚠️  Semgrep is not working properly")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("❌ Semgrep is not installed or not responding")
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