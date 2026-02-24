# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Botanu SDK - OpenTelemetry-native cost attribution for AI workflows.

Quick Start::

    from botanu import enable, botanu_workflow, emit_outcome

    enable()  # reads config from OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT env vars

    @botanu_workflow(name="Customer Support")
    async def handle_request(data):
        result = await process(data)
        emit_outcome("success", value_type="tickets_resolved", value_amount=1)
        return result
"""

from __future__ import annotations

from botanu._version import __version__

# Run context model
from botanu.models.run_context import RunContext, RunOutcome, RunStatus

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

# Decorators  (primary integration point)
from botanu.sdk.decorators import botanu_workflow, run_botanu, workflow

# Span helpers
from botanu.sdk.span_helpers import emit_outcome, set_business_context

__all__ = [
    "__version__",
    # Bootstrap
    "enable",
    "disable",
    "is_enabled",
    # Configuration
    "BotanuConfig",
    # Decorators / context managers
    "botanu_workflow",
    "run_botanu",
    "workflow",
    # Span helpers
    "emit_outcome",
    "set_business_context",
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
]
