"""OpenTelemetry integration for LLM observability.

Instruments the Anthropic and OpenAI SDKs to automatically
capture token usage, model info, and timing as OTLP spans.
A custom span processor bridges span data into the EventBus
for per-ticket accumulation.

Usage:
    from providers.telemetry import setup_telemetry

    event_bus = EventBus()
    setup_telemetry(event_bus=event_bus)

Configuration via ~/.agentic-perf/config.json:
    {
        "telemetry": {
            "enabled": true,
            "otlp_endpoint": "http://localhost:4317"
        }
    }

When otlp_endpoint is set, spans are also exported to an
external OTLP collector (Jaeger, Grafana Tempo, etc.).
When omitted, spans are only processed internally for
EventBus accumulation.
"""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import context, trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace import (
    ReadableSpan,
    SpanProcessor,
    TracerProvider,
)

logger = logging.getLogger(__name__)

# Context keys for correlation. Set by the agent loop
# before each LLM call so span processors can attribute
# usage to the right ticket and agent.
_TICKET_ID_KEY = context.create_key("agentic_perf.ticket_id")
_AGENT_NAME_KEY = context.create_key("agentic_perf.agent_name")


def set_ticket_context(
    ticket_id: str,
    agent_name: str = "",
) -> Context:
    """Set ticket and agent in the OpenTelemetry context.

    Call this in the agent loop before making LLM calls so
    that span processors can correlate token usage to the
    ticket and agent.
    """
    ctx = context.get_current()
    ctx = context.set_value(_TICKET_ID_KEY, ticket_id, ctx)
    if agent_name:
        ctx = context.set_value(_AGENT_NAME_KEY, agent_name, ctx)
    return ctx


def get_ticket_from_context(
    ctx: Context | None = None,
) -> str | None:
    """Get the ticket ID from the OpenTelemetry context."""
    ctx = ctx or context.get_current()
    return context.get_value(_TICKET_ID_KEY, ctx)


def get_agent_from_context(
    ctx: Context | None = None,
) -> str | None:
    """Get the agent name from the OpenTelemetry context."""
    ctx = ctx or context.get_current()
    return context.get_value(_AGENT_NAME_KEY, ctx)


class EventBusSpanProcessor(SpanProcessor):
    """Captures completed LLM spans and feeds data to EventBus.

    Extracts token usage, model info, and duration from spans
    produced by the Anthropic/OpenAI instrumentation packages
    and records them as cumulative usage per ticket.
    """

    def __init__(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    def on_start(
        self,
        span: ReadableSpan,
        parent_context: Context | None = None,
    ) -> None:
        """Store ticket and agent on the span."""
        ticket_id = get_ticket_from_context(parent_context)
        agent_name = get_agent_from_context(parent_context)
        if hasattr(span, "set_attribute"):
            if ticket_id:
                span.set_attribute("agentic_perf.ticket_id", ticket_id)
            if agent_name:
                span.set_attribute("agentic_perf.agent_name", agent_name)

    def on_end(self, span: ReadableSpan) -> None:
        """No-op — token accounting moved to AgentBase via LLMResponse.usage.

        This processor is retained for external OTLP export
        (Jaeger, Grafana Tempo) and span correlation, but no
        longer emits to the EventBus.
        """

    def shutdown(self) -> None:
        """No-op — EventBus manages its own lifecycle."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """No-op — writes are synchronous."""
        return True


def setup_telemetry(
    event_bus: Any | None = None,
    otlp_endpoint: str | None = None,
    enabled: bool = True,
) -> None:
    """Initialize OpenTelemetry with LLM instrumentation.

    Args:
        event_bus: EventBus instance for per-ticket usage
            accumulation. If None, spans are only exported
            to the OTLP endpoint (if configured).
        otlp_endpoint: OTLP collector endpoint (e.g.,
            http://localhost:4317). If None, no external
            export — spans are only processed internally.
        enabled: Set to False to skip all instrumentation.
    """
    if not enabled:
        logger.info("[telemetry] Disabled by configuration")
        return

    provider = TracerProvider()

    # Internal processor: bridge spans to EventBus
    if event_bus is not None:
        provider.add_span_processor(EventBusSpanProcessor(event_bus))
        logger.info("[telemetry] EventBus span processor enabled")

    # External export: send spans to an OTLP collector
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(f"[telemetry] OTLP export enabled: {otlp_endpoint}")
        except ImportError:
            logger.warning(
                "[telemetry] OTLP exporter not installed. "
                "Install opentelemetry-exporter-otlp-proto-"
                "grpc for external export."
            )

    trace.set_tracer_provider(provider)

    # Instrument the LLM SDKs
    try:
        from opentelemetry.instrumentation.anthropic import (
            AnthropicInstrumentor,
        )

        AnthropicInstrumentor().instrument()
        logger.info("[telemetry] Anthropic SDK instrumented")
    except ImportError:
        logger.debug("[telemetry] Anthropic instrumentation not available")

    try:
        from opentelemetry.instrumentation.openai import (
            OpenAIInstrumentor,
        )

        OpenAIInstrumentor().instrument()
        logger.info("[telemetry] OpenAI SDK instrumented")
    except ImportError:
        logger.debug("[telemetry] OpenAI instrumentation not available")
