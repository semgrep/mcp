#!/usr/bin/env python3

import argparse
import re
from datetime import datetime
from pathlib import Path

import tomli
import tomli_w


def read_toml(file_path: Path) -> dict:
    """Read and parse a TOML file."""
    with open(file_path, "rb") as f:
        return tomli.load(f)


def write_toml(file_path: Path, data: dict) -> None:
    """Write data to a TOML file."""
    with open(file_path, "wb") as f:
        tomli_w.dump(data, f)


def bump_version(current_version: str, bump_type: str) -> str:
    """Bump the version number based on semver rules."""
    major, minor, patch = map(int, current_version.split("."))

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def update_pyproject_toml(file_path: Path, new_version: str) -> None:
    """Update version in pyproject.toml."""
    data = read_toml(file_path)
    data["project"]["version"] = new_version
    write_toml(file_path, data)


def update_server_py(file_path: Path, new_version: str) -> None:
    """Update version in server.py."""
    content = file_path.read_text()
    # Update version pattern in server.py
    new_content = re.sub(
        r'__version__\s*=\s*["\'][\d.]+["\']', f'__version__ = "{new_version}"', content
    )
    file_path.write_text(new_content)


def update_changelog(file_path: Path, new_version: str) -> None:
    """Update CHANGELOG.md with new version."""
    content = file_path.read_text()
    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"\n## [{new_version}] - {today}\n\n"

    if "# Changelog" in content:
        # Insert after the first line containing "# Changelog"
        parts = content.split("# Changelog", 1)
        content = parts[0] + "# Changelog" + new_entry + parts[1]
    else:
        # If no Changelog header exists, add it
        content = f"# Changelog\n{new_entry}\n{content}"

    file_path.write_text(content)


def update_chart_yaml(file_path: Path, new_version: str) -> None:
    """Update version in Chart.yaml."""
    content = file_path.read_text()
    # Update version: ...
    new_content = re.sub(r"version:\s*[\d.]+", f"version: {new_version}", content)
    # Update appVersion: ...
    new_content = re.sub(r'appVersion:\s*"[^"]*"', f'appVersion: "{new_version}"', new_content)
    file_path.write_text(new_content)


def main():
    parser = argparse.ArgumentParser(description="Bump version numbers in the project")
    parser.add_argument(
        "bump_type",
        nargs="?",
        choices=["major", "minor", "patch"],
        default="minor",
        help="Type of version bump (default: minor)",
    )
    args = parser.parse_args()

    # Get root directory
    root_dir = Path(__file__).parent.parent

    # Read current version from pyproject.toml
    pyproject_path = root_dir / "pyproject.toml"
    current_version = read_toml(pyproject_path)["project"]["version"]

    # Calculate new version
    new_version = bump_version(current_version, args.bump_type)

    # Update files
    update_pyproject_toml(pyproject_path, new_version)
    update_server_py(root_dir / "src" / "semgrep_mcp" / "server.py", new_version)
    update_changelog(root_dir / "CHANGELOG.md", new_version)
    update_chart_yaml(root_dir / "chart" / "semgrep-mcp" / "Chart.yaml", new_version)

    print(f"Successfully bumped version from {current_version} to {new_version}")
    print("Files updated:")
    print("- pyproject.toml")
    print("- src/semgrep_mcp/server.py")
    print("- CHANGELOG.md")
    print("- chart/semgrep-mcp/Chart.yaml")


if __name__ == "__main__":
    main()
