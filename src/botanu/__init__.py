# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Botanu SDK - OpenTelemetry-native cost attribution for AI workflows.

Quick Start::

    import botanu

    botanu.enable()  # reads OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT env vars

    # One wrap around the agent entrypoint captures every LLM/HTTP/DB call.
    with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
        agent.run(ticket)

    # Or as a decorator, with lambda extractors from the function args:
    @botanu.event(
        workflow="Support",
        event_id=lambda t: t.id,
        customer_id=lambda t: t.user_id,
    )
    def handle_ticket(ticket):
        ...
"""

from __future__ import annotations

from botanu._version import __version__

# Run context model
from botanu.models.run_context import RunContext, RunOutcome, RunStatus

# Processors
from botanu.processors import RunContextEnricher, SampledSpanProcessor

# Bootstrap
from botanu.sdk.bootstrap import (
    disable,
    enable,
    is_enabled,
)

# Configuration
from botanu.sdk.config import BotanuConfig

# Context helpers  (core — no SDK dependency)
from botanu.sdk.context import (
    get_baggage,
    get_current_span,
    get_run_id,
    get_workflow,
    set_baggage,
)

# Primary integration API
from botanu.sdk.decorators import event, step

# Span helpers
from botanu.sdk.span_helpers import emit_outcome, set_business_context, set_correlation

__all__ = [
    "__version__",
    # Bootstrap
    "enable",
    "disable",
    "is_enabled",
    # Configuration
    "BotanuConfig",
    # Primary API
    "event",
    "step",
    # Span helpers
    "emit_outcome",
    "set_business_context",
    "set_correlation",
    "get_current_span",
    # Context
    "get_run_id",
    "get_workflow",
    "set_baggage",
    "get_baggage",
    # Run context
    "RunContext",
    "RunStatus",
    "RunOutcome",
    # Processors
    "RunContextEnricher",
    "SampledSpanProcessor",
]
