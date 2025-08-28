"""Global test configuration for semgrep-mcp tests."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_default_environment():
    """Set up default environment variables for all tests.

    This fixture automatically runs before any test session and ensures
    that USE_SEMGREP_RPC is set to 'false' by default unless overridden
    by individual tests using decorators.
    """
    # Set USE_SEMGREP_RPC to false by default if not already set
    if "USE_SEMGREP_RPC" not in os.environ:
        os.environ["USE_SEMGREP_RPC"] = "false"

    yield

    # Cleanup is handled automatically by pytest and individual test decorators
