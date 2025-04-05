#!/usr/bin/env python3
import asyncio
import click
import subprocess
import json
import os
import tempfile
import shutil
from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import (
    ErrorData,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------------

VERSION = "0.1.5"
DEFAULT_TIMEOUT = 300 # 5 mins in seconds

# ---------------------------------------------------------------------------------
# Global Variables
# ---------------------------------------------------------------------------------

# Global variable to store the semgrep executable path
semgrep_executable: Optional[str] = None
_semgrep_lock = asyncio.Lock()


# ---------------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------------

# Path validation
def validate_absolute_path(path_to_validate: str, param_name: str) -> str:
    """Validates an absolute path to ensure it's safe to use"""
    if not os.path.isabs(path_to_validate):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"{param_name} must be an absolute path. Received: {path_to_validate}"
            )
        )
    
    # Normalize path and ensure no path traversal is possible
    normalized_path = os.path.normpath(path_to_validate)
    
    # Check if normalized path is still absolute
    if not os.path.isabs(normalized_path):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=f"{param_name} contains invalid path traversal sequences"
            )
        )
    
    return normalized_path


def validate_config(config: Optional[str] = None) -> Optional[str]:
    """Validates semgrep configuration parameter"""
    # Allow registry references (p/ci, p/security, etc.)
    if config is None or config.startswith("p/") or config == "auto":
        return config
    
    # Otherwise, treat as path and validate
    return validate_absolute_path(config, "config")


# Semgrep utilities
def find_semgrep_path() -> Optional[str]:
    """
    Dynamically find semgrep in PATH or common installation directories
    Returns: Path to semgrep executable or None if not found
    """
    # Common paths where semgrep might be installed
    common_paths = [
        "semgrep",  # Default PATH
        "/usr/local/bin/semgrep",
        "/usr/bin/semgrep",
        "/opt/homebrew/bin/semgrep",  # Homebrew on macOS
        "/opt/semgrep/bin/semgrep",
        "/home/linuxbrew/.linuxbrew/bin/semgrep",  # Homebrew on Linux
        "/snap/bin/semgrep",  # Snap on Linux
    ]
    
    # Add Windows paths if on Windows
    if os.name == "nt":
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            common_paths.extend([
                os.path.join(app_data, "Python", "Scripts", "semgrep.exe"),
                os.path.join(app_data, "npm", "semgrep.cmd"),
            ])
    
    # Try each path
    for semgrep_path in common_paths:
        try:
            # For 'semgrep' (without path), check if it's in PATH
            if semgrep_path == "semgrep":
                try:
                    subprocess.run([semgrep_path, "--version"], 
                                  check=True, capture_output=True, text=True)
                    return semgrep_path
                except (subprocess.SubprocessError, FileNotFoundError):
                    continue
            
            # For absolute paths, check if the file exists before testing
            if os.path.isabs(semgrep_path):
                if not os.path.exists(semgrep_path):
                    continue
            
            # Try executing semgrep at this path
            try:
                subprocess.run([semgrep_path, "--version"], 
                              check=True, capture_output=True, text=True)
                return semgrep_path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        except Exception:
            # Continue to next path
            continue
    
    return None


async def ensure_semgrep_available() -> str:
    """
    Ensures semgrep is available and sets the global path in a thread-safe manner
    
    Returns:
        Path to semgrep executable
        
    Raises:
        McpError: If semgrep is not installed or not found
    """
    global semgrep_executable
    
    # Fast path - check if we already have the path
    if semgrep_executable:
        return semgrep_executable
    
    # Slow path - acquire lock and check again
    async with _semgrep_lock:
        # Double-check pattern
        if semgrep_executable:
            return semgrep_executable
            
        # Try to find semgrep
        semgrep_path = find_semgrep_path()
        
        if not semgrep_path:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message="Semgrep is not installed or not in your PATH. "
                    "Please install Semgrep manually before using this tool. "
                    "Installation options: "
                    "pip install semgrep, "
                    "macOS: brew install semgrep, "
                    "Or refer to https://semgrep.dev/docs/getting-started/"
                )
            )
        
        # Store the path for future use
        semgrep_executable = semgrep_path
        return semgrep_path

# Utility functions for handling code content
async def create_temp_files_from_code_content(code_files: List[Dict[str, str]]) -> str:
    """
    Creates temporary files from code content
    
    Args:
        code_files: List of dictionaries with 'filename' and 'content' keys
        
    Returns:
        Path to temporary directory containing the files
        
    Raises:
        McpError: If there are issues creating or writing to files
    """
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")
        
        # Create files in the temporary directory
        for file_info in code_files:
            filename = file_info.get("filename")
            content = file_info.get("content", "")
            
            if not filename:
                continue
            
            try:
                # Create subdirectories if needed
                file_path = os.path.join(temp_dir, filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Write content to file
                with open(file_path, "w") as f:
                    f.write(content)
            except (OSError, IOError) as e:
                raise McpError(
                    ErrorData(
                        code=INTERNAL_ERROR,
                        message=f"Failed to create or write to file {filename}: {str(e)}"
                    )
                )
        
        return temp_dir
    except Exception as e:
        if 'temp_dir' in locals():
            # Clean up temp directory if creation failed
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Failed to create temporary files: {str(e)}"
            )
        )


def get_semgrep_scan_args(temp_dir: str, config: Optional[str] = None) -> List[str]:
    """
    Builds command arguments for semgrep scan
    
    Args:
        temp_dir: Path to temporary directory containing the files
        config: Optional Semgrep configuration (e.g. "auto" or absolute path to rule file)
    
    Returns:
        List of command arguments
    """

    # Build command arguments and just run semgrep scan 
    # if no config is provided to allow for either the default "auto" 
    # or whatever the logged in config is
    args = ["scan", "--json", "--experimental"] # avoid the extra exec
    if config:
        args.extend(["--config", config])
    args.append(temp_dir)
    return args

def validate_code_files(code_files: List[Dict[str, str]]) -> None:
    """
    Validates the code_files parameter for semgrep scan
    
    Args:
        code_files: List of dictionaries with 'filename' and 'content' keys
        
    Raises:
        McpError: If validation fails
    """
    if not code_files or not isinstance(code_files, list):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message="code_files must be a non-empty list of file objects"
            )
        )
    
    for file_info in code_files:
        if not isinstance(file_info, dict) or "filename" not in file_info or "content" not in file_info:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message="Each file object must have 'filename' and 'content' keys"
                )
            )
        

async def run_semgrep(args: List[str]) -> str:
    """
    Runs semgrep with the given arguments
    
    Args:
        args: List of command arguments
        
    Returns:
        Output of semgrep command
    """

    # Ensure semgrep is available
    semgrep_path = await ensure_semgrep_available()

    # Execute semgrep command
    process = await asyncio.create_subprocess_exec(
        semgrep_path,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )   
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=f"Error running semgrep: ({process.returncode}) {stderr.decode()}"
            )   
        )
    
    return stdout.decode()

def remove_temp_dir_from_results(results: Dict[str, Any], temp_dir: str) -> None:
    """
    Clean the results from semgrep by converting temporary file paths back to original relative paths
    
    Args:
        results: Dictionary containing semgrep results
        temp_dir: Path to temporary directory used for scanning
    """
    if "results" in results:
        for finding in results["results"]:
            if "path" in finding:
                rel_path = os.path.relpath(finding["path"], temp_dir)
                finding["path"] = rel_path
    if "paths" in results:
        if "scanned" in results["paths"]:
            scanned_paths = [os.path.relpath(path, temp_dir) for path in results["paths"]["scanned"]]
            results["paths"]["scanned"] = scanned_paths
        if "skipped" in results["paths"]:
            skipped_paths = [os.path.relpath(path, temp_dir) for path in results["paths"]["skipped"]]
            results["paths"]["skipped"] = skipped_paths

# ---------------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------------

# Create a fast MCP server
mcp = FastMCP(
    "Semgrep", 
    version=VERSION, 
    request_timeout=DEFAULT_TIMEOUT, 
)


@mcp.tool()
async def get_supported_languages() -> List[str]:
    """
    Returns a list of supported languages by Semgrep
    
    Returns:
        List of supported languages
    """
    
    args = ["show", "supported-languages", "--experimental"]

    # Parse output and return list of languages
    languages = await run_semgrep(args)
    return [lang.strip() for lang in languages.strip().split('\n') if lang.strip()]

@mcp.tool()
async def semgrep_scan(code_files: List[Dict[str, str]], config: Optional[str] = None) -> Dict[str, Any]:
    """
    Runs a Semgrep scan on provided code content and returns the findings in JSON format
    
    Args:
        code_files: List of dictionaries with 'filename' and 'content' keys
        config: Optional Semgrep configuration (e.g. "auto")
        
    Returns:
        Dictionary with scan results in Semgrep JSON format
    """
    # Validate config
    config = validate_config(config)
    
    # Validate code_files
    validate_code_files(code_files)

    try:
        # Create temporary files from code content
        temp_dir = await create_temp_files_from_code_content(code_files)
        args = get_semgrep_scan_args(temp_dir, config)
        output = await run_semgrep(args)
        results = json.loads(output)
        remove_temp_dir_from_results(results, temp_dir)
        return results
    
    except McpError as e:
        raise e
    except json.JSONDecodeError as e:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=f"Error parsing semgrep output: {str(e)}"
            )
        )
    except Exception as e:
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR, 
                message=f"Error running semgrep scan: {str(e)}"
            )
        )

    finally:
        if 'temp_dir' in locals():
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)


@click.command()
@click.version_option(version=VERSION, prog_name="Semgrep MCP Server")
@click.option(
    "-t", "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    envvar="MCP_TRANSPORT",
    help="Transport protocol to use (stdio or sse)"
)
def main(transport: str):
    """Entry point for the MCP server
    
    Supports both stdio and sse transports. For stdio, it will read from stdin and write to stdout.
    For sse, it will start an HTTP server on the specified host and port.
    """
    if transport == "stdio":
        asyncio.run(mcp.run(transport="stdio"))
    else:  # sse
        asyncio.run(mcp.run(transport="sse"))

if __name__ == "__main__":
    main()