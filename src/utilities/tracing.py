#!/usr/bin/env python3

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# coupling: these need to be kept in sync with semgrep-proprietary/tracing.py
DEFAULT_TRACE_ENDPOINT = "https://telemetry.semgrep.dev/v1/traces"
DEFAULT_DEV_ENDPOINT = "https://telemetry.dev2.semgrep.dev/v1/traces"
DEFAULT_LOCAL_ENDPOINT = "http://localhost:4318/v1/traces"

MCP_SERVICE_NAME = "mcp"


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

    # Create resource with basic attributes
    resource = Resource.create(
        {
            SERVICE_NAME: MCP_SERVICE_NAME,
            DEPLOYMENT_ENVIRONMENT: env,
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
