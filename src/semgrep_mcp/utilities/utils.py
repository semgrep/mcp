import asyncio
import os
import subprocess
from pathlib import Path

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData
from ruamel.yaml import YAML

SETTINGS_FILENAME = "settings.yml"
_SEMGREP_LOCK = asyncio.Lock()
# Global variable to store the semgrep executable path
SEMGREP_EXECUTABLE: str | None = None
SEMGREP_PATH = os.getenv("SEMGREP_PATH", None)


def is_hosted() -> bool:
    """
    Check if the user is using the hosted version of the MCP server.
    """
    return os.environ.get("SEMGREP_IS_HOSTED", "false").lower() == "true"


def get_user_settings_file() -> Path:
    def get_user_data_folder() -> Path:
        config_home = os.getenv("XDG_CONFIG_HOME")
        if config_home is None or not Path(config_home).is_dir():
            parent_dir = Path.home()
        else:
            parent_dir = Path(config_home)
        return parent_dir / ".semgrep"

    path = os.getenv("SEMGREP_SETTINGS_FILE", str(get_user_data_folder() / SETTINGS_FILENAME))
    return Path(path)


def get_semgrep_app_token() -> str | None:
    """
    Returns the deployment ID the token is for, if token is valid
    """

    # Prioritize environment variable first
    env_token = os.environ.get("SEMGREP_APP_TOKEN")
    if env_token is not None:
        return env_token

    # Fall back to settings file if environment variable is not set
    user_settings_file = get_user_settings_file()
    if user_settings_file.exists():
        with open(user_settings_file) as f:
            yaml = YAML(typ="safe", pure=True)
            settings = yaml.load(f)
            return settings.get("api_token")

    return None


################################################################################
# Finding Semgrep #
################################################################################


# Semgrep utilities
def find_semgrep_info() -> tuple[str | None, str]:
    """
    Dynamically find semgrep in PATH or common installation directories
    Returns: Path to semgrep executable and version or (None, "unknown") if not found
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

    if SEMGREP_PATH:
        common_paths.append(SEMGREP_PATH)

    # Add Windows paths if on Windows
    if os.name == "nt":
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            common_paths.extend(
                [
                    os.path.join(app_data, "Python", "Scripts", "semgrep.exe"),
                    os.path.join(app_data, "npm", "semgrep.cmd"),
                ]
            )

    # Try each path
    for semgrep_path in common_paths:
        # For 'semgrep' (without path), check if it's in PATH
        if semgrep_path == "semgrep":
            try:
                process = subprocess.run(
                    [semgrep_path, "--version"], check=True, capture_output=True, text=True
                )
                return semgrep_path, process.stdout.strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        # For absolute paths, check if the file exists before testing
        if os.path.isabs(semgrep_path):
            if not os.path.exists(semgrep_path):
                continue

            # Try executing semgrep at this path
            try:
                process = subprocess.run(
                    [semgrep_path, "--version"], check=True, capture_output=True, text=True
                )
                return semgrep_path, process.stdout.strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

    return None, "unknown"


def find_semgrep_path() -> str | None:
    """
    Find the path to the semgrep executable

    Returns:
        Path to semgrep executable or None if not found
    """
    semgrep_path, _ = find_semgrep_info()
    return semgrep_path


def get_semgrep_version() -> str:
    """
    Get the version of the semgrep binary.
    """
    _, semgrep_version = find_semgrep_info()
    return semgrep_version


async def ensure_semgrep_available() -> str:
    """
    Ensures semgrep is available and sets the global path in a thread-safe manner

    Returns:
        Path to semgrep executable

    Raises:
        McpError: If semgrep is not installed or not found
    """
    global SEMGREP_EXECUTABLE

    # Fast path - check if we already have the path
    if SEMGREP_EXECUTABLE:
        return SEMGREP_EXECUTABLE

    # Slow path - acquire lock and find semgrep
    async with _SEMGREP_LOCK:
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
                    "Or refer to https://semgrep.dev/docs/getting-started/",
                )
            )

        # Store the path for future use
        SEMGREP_EXECUTABLE = semgrep_path
        return semgrep_path


def set_semgrep_executable(semgrep_path: str) -> None:
    global SEMGREP_EXECUTABLE
    SEMGREP_EXECUTABLE = semgrep_path
