"""Test utilities and decorators for the semgrep-mcp test suite."""

import functools
import os
from collections.abc import Callable
from typing import Any
from unittest.mock import patch


def with_env_var(var_name: str, value: str) -> Callable:
    """Generic decorator to temporarily set an environment variable for a test.

    Args:
        var_name: The name of the environment variable to set
        value: The value to set it to

    Example:
        @with_env_var("DEBUG", "true")
        def test_with_debug():
            assert os.getenv("DEBUG") == "true"
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with patch.dict(os.environ, {var_name: value}):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Convenience decorators for common environment variable patterns
enable_semgrep_rpc = with_env_var("USE_SEMGREP_RPC", "true")
