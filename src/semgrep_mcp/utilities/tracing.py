#!/usr/bin/env python3

import functools
import logging
import os
from collections.abc import Awaitable, Callable, Generator, Mapping
from contextlib import contextmanager
from typing import Concatenate, ParamSpec, TypeVar

import httpx
from mcp.server.fastmcp import Context
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from ruamel.yaml import YAML

from semgrep_mcp.semgrep import SemgrepContext, is_hosted
from semgrep_mcp.utilities.utils import get_user_settings_file

# coupling: these need to be kept in sync with semgrep-proprietary/tracing.py
DEFAULT_TRACE_ENDPOINT = "https://telemetry.semgrep.dev/v1/traces"
DEFAULT_DEV_ENDPOINT = "https://telemetry.dev2.semgrep.dev/v1/traces"
DEFAULT_LOCAL_ENDPOINT = "http://localhost:4318/v1/traces"

DEPLOYMENT_ROUTE = "/api/agent/deployments/current"
SEMGREP_URL = os.environ.get("SEMGREP_URL", "https://semgrep.dev")

MCP_SERVICE_NAME = "mcp"

yaml = YAML()

################################################################################
# Metrics Helpers #
################################################################################


def get_deployment_id_from_token(token: str) -> str:
    """
    Returns the deployment ID the token is for, if token is valid
    """
    if not token:
        return ""

    resp = httpx.get(
        f"{SEMGREP_URL}{DEPLOYMENT_ROUTE}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200:
        deployment = resp.json().get("deployment")
        return deployment.get("id") if deployment else ""
    else:
        return ""


def get_token_from_user_settings() -> str:
    settings_file = get_user_settings_file()
    if not os.access(settings_file, os.R_OK) or not settings_file.is_file():
        return ""
    with settings_file.open() as fd:
        yaml_contents = yaml.load(fd)

    if not isinstance(yaml_contents, Mapping):
        return ""

    return yaml_contents.get("api_token", "")


################################################################################
# Tracing #
################################################################################


def get_trace_endpoint() -> tuple[str, str]:
    """Get the appropriate trace endpoint based on environment."""
    env = os.environ.get("ENVIRONMENT", "dev").lower()

    if env == "prod":
        return (DEFAULT_TRACE_ENDPOINT, "prod")
    elif env == "local":
        return (DEFAULT_LOCAL_ENDPOINT, "local")
    else:
        return (DEFAULT_DEV_ENDPOINT, "dev")


@contextmanager
def start_tracing(name: str) -> Generator[trace.Span, None, None]:
    """Initialize OpenTelemetry tracing."""
    (endpoint, env) = get_trace_endpoint()

    token = os.environ.get("SEMGREP_APP_TOKEN", get_token_from_user_settings())

    # Create resource with basic attributes
    resource = Resource.create(
        {
            SERVICE_NAME: MCP_SERVICE_NAME,
            DEPLOYMENT_ENVIRONMENT: env,
            "metrics.is_hosted": is_hosted(),
            "metrics.deployment_id": get_deployment_id_from_token(token),
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Create OTLP exporter
    exporter = OTLPSpanExporter(endpoint=endpoint)

    # Create span processor
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set the global tracer provider
    trace.set_tracer_provider(provider)

    # Get tracer instance
    tracer = trace.get_tracer(MCP_SERVICE_NAME)

    with tracer.start_as_current_span(name) as span:
        trace_id = trace.format_trace_id(span.get_span_context().trace_id)

        logging.info("Tracing initialized")
        logging.info(f"Tracing initialized with trace ID: {trace_id}")

        yield span


@contextmanager
def with_span(
    parent_span: trace.Span,
    name: str,
) -> Generator[trace.Span, None, None]:
    tracer = trace.get_tracer(MCP_SERVICE_NAME)

    context = trace.set_span_in_context(parent_span)
    with tracer.start_span(name, context=context) as span:
        yield span


R = TypeVar("R")
P = ParamSpec("P")


def with_tool_span(
    span_name: str | None = None,
) -> Callable[
    [Callable[Concatenate[Context, P], Awaitable[R]]],
    Callable[Concatenate[Context, P], Awaitable[R]],
]:
    """
    Decorator to wrap MCP tools with a tracing span.

    All tools decorated by @with_tool_span must have a Context parameter.

    Args:
        span_name: Optional name for the span. If not provided, uses the function name.
    """

    def decorator(
        func: Callable[Concatenate[Context, P], Awaitable[R]],
    ) -> Callable[Concatenate[Context, P], Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(ctx: Context, *args: P.args, **kwargs: P.kwargs) -> R:
            context: SemgrepContext = ctx.request_context.lifespan_context
            name = span_name or func.__name__

            with with_span(context.top_level_span, name):
                return await func(ctx, *args, **kwargs)

        return wrapper

    return decorator
