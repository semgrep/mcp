#!/usr/bin/env -S uv run --with mcp mcp run -t sse
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "mcp-server",
#     "semgrep",
#     "fastmcp"
# ]
# ///
from enum import Enum, auto
from mcp.server.fastmcp import FastMCP, Context
import subprocess
import json
import os
import time
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from time import sleep
import asyncio
import click

# ---------------------------------------------------------------------------------
# Constants
DEFAULT_SEMGREP_CONFIG = "auto"
DEFAULT_TIMEOUT = 300000  # 5 minutes in milliseconds


class ResultFormat:
    JSON = "json"
    SARIF = "sarif"
    TEXT = "text"


DEFAULT_RESULT_FORMAT = ResultFormat.TEXT

# Create an MCP server with SSE support enabled
# Note: We're not specifying http_routes to let FastMCP use its defaults
mcp = FastMCP(
    "Semgrep", 
    version="1.0.0", 
    request_timeout=300, 
)

# Error codes
class ErrorCode(Enum):
    """Error codes for MCP protocol
    https://modelcontextprotocol.io/docs/concepts/architecture#error-handling
    """
    ParseError = -32700
    InvalidRequest = -32600
    MethodNotFound = -32601
    InvalidParams = -32602
    InternalError = -32603


class McpError(Exception):
    """Custom error class for MCP protocol errors"""
    
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(self.message)


# Path validation
def validate_absolute_path(path_to_validate: str, param_name: str) -> str:
    """Validates an absolute path to ensure it's safe to use"""
    if not os.path.isabs(path_to_validate):
        raise McpError(
            ErrorCode.InvalidParams,
            f"{param_name} must be an absolute path. Received: {path_to_validate}"
        )
    
    # Normalize path and ensure no path traversal is possible
    normalized_path = os.path.normpath(path_to_validate)
    
    # Check if normalized path is still absolute
    if not os.path.isabs(normalized_path):
        raise McpError(
            ErrorCode.InvalidParams,
            f"{param_name} contains invalid path traversal sequences"
        )
    
    return normalized_path


def validate_config(config: str) -> str:
    """Validates semgrep configuration parameter"""
    # Allow registry references (p/ci, p/security, etc.)
    if config.startswith("p/") or config == "auto":
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


# Global variable to store the semgrep executable path
semgrep_executable = None


def ensure_semgrep_available() -> str:
    """
    Ensures semgrep is available and sets the global path
    Returns: Path to semgrep executable
    """
    global semgrep_executable
    
    # If we've already found semgrep, return its path
    if semgrep_executable:
        return semgrep_executable
    
    # Try to find semgrep
    semgrep_path = find_semgrep_path()
    
    if not semgrep_path:
        raise McpError(
            ErrorCode.InternalError,
            "Semgrep is not installed or not in your PATH. "
            "Please install Semgrep manually before using this tool. "
            "Installation options: "
            "pip install semgrep, "
            "macOS: brew install semgrep, "
            "Or refer to https://semgrep.dev/docs/getting-started/"
        )
    
    # Store the path for future use
    semgrep_executable = semgrep_path
    return semgrep_path


# New progress notification function
async def report_progress(ctx: Context, task_id: str):
    """Reports ongoing progress for a running task"""
    counter = 0
    while True:
        await asyncio.sleep(2)  # Wait 2 seconds between notifications
        counter += 2
        ctx.set_notification(f"Task {task_id} still running... ({counter}s elapsed)")


# Store scan results and status in memory
scan_results = {}
scan_status = {}
temp_dirs = {}  # Store temporary directories for each scan

# Utility functions for handling code content
async def create_temp_files_from_code_content(code_files: List[Dict[str, str]]) -> str:
    """
    Creates temporary files from code content
    
    Args:
        code_files: List of dictionaries with 'filename' and 'content' keys
        
    Returns:
        Path to temporary directory containing the files
    """
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix="semgrep_scan_")
    
    # Create files in the temporary directory
    for file_info in code_files:
        filename = file_info.get("filename")
        content = file_info.get("content", "")
        
        if not filename:
            continue
        
        # Create subdirectories if needed
        file_path = os.path.join(temp_dir, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write content to file
        with open(file_path, "w") as f:
            f.write(content)
    
    return temp_dir

async def cleanup_temp_dir(scan_id: str):
    """
    Cleans up temporary directory for a scan
    
    Args:
        scan_id: Identifier for the scan
    """
    if scan_id in temp_dirs:
        temp_dir = temp_dirs[scan_id]
        try:
            # Remove temporary directory and all its contents
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            del temp_dirs[scan_id]
        except Exception as e:
            print(f"Error cleaning up temporary directory: {str(e)}")

@mcp.tool()
async def start_scan_from_content(ctx: Context, code_files: List[Dict[str, str]], config: str = DEFAULT_SEMGREP_CONFIG) -> Dict[str, Any]:
    """
    Starts a Semgrep scan with code content provided directly
    
    Args:
        ctx: MCP context for sending notifications
        code_files: List of dictionaries with 'filename' and 'content' keys
        config: Semgrep configuration (e.g. "auto" or absolute path to rule file)
        
    Returns:
        Dictionary with scan information
    """
    # Validate config
    config = validate_config(config) if not config.startswith("p/") and config != "auto" else config
    
    # Validate code_files
    if not code_files or not isinstance(code_files, list):
        raise McpError(
            ErrorCode.InvalidParams,
            "code_files must be a non-empty list of file objects"
        )
    
    for file_info in code_files:
        if not isinstance(file_info, dict) or "filename" not in file_info or "content" not in file_info:
            raise McpError(
                ErrorCode.InvalidParams,
                "Each file object must have 'filename' and 'content' keys"
            )
    
    # Generate a unique scan ID
    scan_id = f"scan-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    
    # Initialize scan status
    scan_status[scan_id] = {
        "status": "started",
        "progress": 0,
        "start_time": time.time()
    }
    
    # Start scan in background with progress reporting
    asyncio.create_task(run_background_scan_with_content(ctx, scan_id, code_files, config))
    
    # Return scan information
    return {
        "status": "started",
        "scan_id": scan_id,
        "message": f"Scan started with ID: {scan_id}. Progress will be reported via notifications."
    }

async def run_background_scan_with_content(ctx: Context, scan_id: str, code_files: List[Dict[str, str]], config: str) -> None:
    """
    Runs a scan in the background with code content and updates scan status with progress notifications
    
    Args:
        ctx: MCP context for sending notifications
        scan_id: Unique identifier for the scan
        code_files: List of dictionaries with 'filename' and 'content' keys
        config: Semgrep configuration
    """
    try:
        # Initial notification
        ctx.set_notification(f"Starting scan {scan_id}...")
        
        # Update status
        scan_status[scan_id]["status"] = "in_progress"
        
        # Create temporary files from code content
        temp_dir = await create_temp_files_from_code_content(code_files)
        temp_dirs[scan_id] = temp_dir
        
        # Ensure semgrep is available
        semgrep_path = ensure_semgrep_available()
        
        # Build command arguments
        args = [semgrep_path, "scan", "--json", "--config", config, temp_dir]
        
        # Execute semgrep command
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Start progress reporting
        progress_task = asyncio.create_task(report_scan_progress(ctx, scan_id))
        
        # Wait for process to complete
        stdout, stderr = await process.communicate()
        
        # Cancel progress reporting
        progress_task.cancel()
        
        # Parse results
        if process.returncode == 0 or stdout:
            try:
                results = json.loads(stdout.decode())
                
                # Update file paths in results to use original filenames instead of temp paths
                if "results" in results:
                    for finding in results["results"]:
                        if "path" in finding:
                            # Extract the relative path from the temp directory
                            rel_path = os.path.relpath(finding["path"], temp_dir)
                            finding["path"] = rel_path
                
                scan_results[scan_id] = results
                
                # Count findings by severity
                findings = results.get("results", [])
                severity_counts = {}
                for finding in findings:
                    severity = finding.get("extra", {}).get("severity", "unknown")
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                # Update status
                scan_status[scan_id] = {
                    "status": "completed",
                    "progress": 100,
                    "end_time": time.time(),
                    "total_findings": len(findings),
                    "by_severity": severity_counts
                }
                
                # Final notification
                ctx.set_notification(
                    f"Scan {scan_id} completed with {len(findings)} findings: " +
                    ", ".join([f"{count} {sev}" for sev, count in severity_counts.items()])
                )
            except json.JSONDecodeError as e:
                scan_status[scan_id] = {
                    "status": "error",
                    "error": f"Error parsing semgrep output: {str(e)}"
                }
                ctx.set_notification(f"Scan {scan_id} failed: Error parsing semgrep output")
        else:
            scan_status[scan_id] = {
                "status": "error",
                "error": stderr.decode()
            }
            ctx.set_notification(f"Scan {scan_id} failed: {stderr.decode()[:100]}...")
        
        # Clean up temporary files
        await cleanup_temp_dir(scan_id)
        
    except Exception as e:
        scan_status[scan_id] = {
            "status": "error",
            "error": str(e)
        }
        ctx.set_notification(f"Scan {scan_id} failed: {str(e)}")
        
        # Clean up temporary files
        await cleanup_temp_dir(scan_id)

async def report_scan_progress(ctx: Context, scan_id: str):
    """Reports progress for a running scan"""
    progress = 0
    try:
        while progress < 100:
            await asyncio.sleep(2)  # Wait between progress updates
            
            # Simulate progress
            progress += 5
            if progress > 95:
                progress = 95  # Cap at 95% until complete
                
            # Update status
            scan_status[scan_id]["progress"] = progress
            
            # Send notification
            ctx.set_notification(f"Scan {scan_id} in progress: {progress}% complete")
    except asyncio.CancelledError:
        # Task was cancelled, which is expected when scan completes
        pass

@mcp.tool()
async def get_scan_status(scan_id: str) -> Dict[str, Any]:
    """
    Gets the current status of a scan
    
    Args:
        scan_id: Identifier for the scan
        
    Returns:
        Dictionary with scan status information
    """
    if scan_id not in scan_status:
        raise McpError(
            ErrorCode.InvalidParams,
            f"No scan found with ID: {scan_id}"
        )
    
    return {
        "scan_id": scan_id,
        **scan_status[scan_id]
    }

@mcp.tool()
async def get_scan_results(scan_id: str) -> Dict[str, Any]:
    """
    Gets the results of a completed scan
    
    Args:
        scan_id: Identifier for the scan
        
    Returns:
        Dictionary with scan results
    """
    if scan_id not in scan_status:
        raise McpError(
            ErrorCode.InvalidParams,
            f"No scan found with ID: {scan_id}"
        )
    
    if scan_status[scan_id]["status"] != "completed":
        raise McpError(
            ErrorCode.InvalidParams,
            f"Scan {scan_id} is not completed. Current status: {scan_status[scan_id]['status']}"
        )
    
    if scan_id not in scan_results:
        raise McpError(
            ErrorCode.InternalError,
            f"Results not found for scan {scan_id}"
        )
    
    return scan_results[scan_id]

@mcp.tool()
async def get_supported_languages() -> List[str]:
    """
    Returns a list of supported languages by Semgrep
    
    Returns:
        List of supported languages
    """
    try:
        # Ensure semgrep is available
        semgrep_path = ensure_semgrep_available()
        
        # Execute semgrep command to get supported languages
        process = await asyncio.create_subprocess_exec(
            semgrep_path, 'show', 'supported-languages',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise McpError(
                ErrorCode.InternalError,
                f"Error getting supported languages: {stderr.decode()}"
            )
            
        # Parse output and return list of languages
        languages = stdout.decode().strip().split('\n')
        return [lang.strip() for lang in languages if lang.strip()]
        
    except Exception as e:
        if isinstance(e, McpError):
            raise e
        raise McpError(
            ErrorCode.InternalError, 
            f"Error getting supported languages: {str(e)}"
        )

@mcp.tool()
async def semgrep_scan(code_files: List[Dict[str, str]], config: str = DEFAULT_SEMGREP_CONFIG) -> Dict[str, Any]:
    """
    Runs a Semgrep scan on provided code content and returns the findings in JSON format
    
    Args:
        code_files: List of dictionaries with 'filename' and 'content' keys
        config: Semgrep configuration (e.g. "auto" or absolute path to rule file)
        
    Returns:
        Dictionary with scan results in Semgrep JSON format
    """
    # Validate config
    config = validate_config(config) if not config.startswith("p/") and config != "auto" else config
    
    # Validate code_files
    if not code_files or not isinstance(code_files, list):
        raise McpError(
            ErrorCode.InvalidParams,
            "code_files must be a non-empty list of file objects"
        )
    
    for file_info in code_files:
        if not isinstance(file_info, dict) or "filename" not in file_info or "content" not in file_info:
            raise McpError(
                ErrorCode.InvalidParams,
                "Each file object must have 'filename' and 'content' keys"
            )
    
    try:
        # Create temporary files from code content
        temp_dir = await create_temp_files_from_code_content(code_files)
        
        # Ensure semgrep is available
        semgrep_path = ensure_semgrep_available()
        
        # Build command arguments
        args = [semgrep_path, "scan", "--json", "--config", config, temp_dir]
        
        # Execute semgrep command
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Clean up temporary files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        if process.returncode != 0 and not stdout:
            raise McpError(
                ErrorCode.InternalError,
                f"Error running semgrep scan: {stderr.decode()}"
            )
            
        # Parse JSON output and update file paths
        try:
            results = json.loads(stdout.decode())
            
            # Update file paths in results to use original filenames instead of temp paths
            if "results" in results:
                for finding in results["results"]:
                    if "path" in finding:
                        # Extract the relative path from the temp directory
                        rel_path = os.path.relpath(finding["path"], temp_dir)
                        finding["path"] = rel_path
            
            return results
        except json.JSONDecodeError as e:
            raise McpError(
                ErrorCode.InternalError,
                f"Error parsing semgrep output: {str(e)}"
            )
        
    except Exception as e:
        if isinstance(e, McpError):
            raise e
        raise McpError(
            ErrorCode.InternalError, 
            f"Error running semgrep scan: {str(e)}"
        )

# Keep the original functions for backward compatibility
@mcp.tool()
async def start_scan(ctx: Context, target_path: str, config: str = DEFAULT_SEMGREP_CONFIG) -> Dict[str, Any]:
    """
    Starts a Semgrep scan with progress updates via notifications
    
    Args:
        ctx: MCP context for sending notifications
        target_path: Absolute path to the file or directory to scan
        config: Semgrep configuration (e.g. "auto" or absolute path to rule file)
        
    Returns:
        Dictionary with scan information
    """
    # Validate parameters
    target_path = validate_absolute_path(target_path, "target_path")
    config = validate_config(config)
    
    # Check if path exists
    if not os.path.exists(target_path):
        raise McpError(
            ErrorCode.InvalidParams,
            f"The specified path does not exist: {target_path}"
        )
    
    # Generate a unique scan ID
    scan_id = f"scan-{int(time.time())}"
    
    # Initialize scan status
    scan_status[scan_id] = {
        "status": "started",
        "progress": 0,
        "start_time": time.time()
    }
    
    # Start scan in background with progress reporting
    asyncio.create_task(run_background_scan_with_progress(ctx, scan_id, target_path, config))
    
    # Return scan information
    return {
        "status": "started",
        "scan_id": scan_id,
        "message": f"Scan started with ID: {scan_id}. Progress will be reported via notifications."
    }

async def run_background_scan_with_progress(ctx: Context, scan_id: str, target_path: str, config: str) -> None:
    """
    Runs a scan in the background and updates scan status with progress notifications
    
    Args:
        ctx: MCP context for sending notifications
        scan_id: Unique identifier for the scan
        target_path: Path to scan
        config: Semgrep configuration
    """
    try:
        # Initial notification
        ctx.set_notification(f"Starting scan {scan_id}...")
        
        # Update status
        scan_status[scan_id]["status"] = "in_progress"
        
        # Ensure semgrep is available
        semgrep_path = ensure_semgrep_available()
        
        # Build command arguments
        args = [semgrep_path, "scan", "--json", "--config", config, target_path]
        
        # Execute semgrep command
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Start progress reporting
        progress_task = asyncio.create_task(report_scan_progress(ctx, scan_id))
        
        # Wait for process to complete
        stdout, stderr = await process.communicate()
        
        # Cancel progress reporting
        progress_task.cancel()
        
        # Parse results
        if process.returncode == 0 or stdout:
            try:
                results = json.loads(stdout.decode())
                scan_results[scan_id] = results
                
                # Count findings by severity
                findings = results.get("results", [])
                severity_counts = {}
                for finding in findings:
                    severity = finding.get("extra", {}).get("severity", "unknown")
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                # Update status
                scan_status[scan_id] = {
                    "status": "completed",
                    "progress": 100,
                    "end_time": time.time(),
                    "total_findings": len(findings),
                    "by_severity": severity_counts
                }
                
                # Final notification
                ctx.set_notification(
                    f"Scan {scan_id} completed with {len(findings)} findings: " +
                    ", ".join([f"{count} {sev}" for sev, count in severity_counts.items()])
                )
            except json.JSONDecodeError as e:
                scan_status[scan_id] = {
                    "status": "error",
                    "error": f"Error parsing semgrep output: {str(e)}"
                }
                ctx.set_notification(f"Scan {scan_id} failed: Error parsing semgrep output")
        else:
            scan_status[scan_id] = {
                "status": "error",
                "error": stderr.decode()
            }
            ctx.set_notification(f"Scan {scan_id} failed: {stderr.decode()[:100]}...")
        
    except Exception as e:
        scan_status[scan_id] = {
            "status": "error",
            "error": str(e)
        }
        ctx.set_notification(f"Scan {scan_id} failed: {str(e)}")

def validate_sse_params(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    """Validates that host and port are only set when using SSE transport"""
    if ctx.params.get('transport') != 'sse' and value != param.default:
        raise click.BadParameter(f"{param.name} can only be set when transport is 'sse'")
    return value

@click.command()
@click.option(
    "-t", "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport protocol to use (stdio or sse)"
)
@click.option(
    "--host",
    default="127.0.0.1",
    callback=validate_sse_params,
    help="Host to bind to when using SSE transport"
)
@click.option(
    "--port",
    default=8000,
    type=int,
    callback=validate_sse_params,
    help="Port to bind to when using SSE transport"
)
def cli(transport: str, host: str, port: int):
    """Entry point for the CLI.
    
    Supports both stdio and sse transports. For stdio, it will read from stdin and write to stdout.
    For sse, it will start an HTTP server on the specified host and port.
    """
    if transport == "stdio":
        asyncio.run(mcp.run(transport="stdio"))
    else:  # sse
        asyncio.run(mcp.run(transport="sse", host=host, port=port))