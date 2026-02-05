# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Context and baggage helpers for Botanu SDK.

Uses OpenTelemetry Context and Baggage for propagation.
"""

from __future__ import annotations

from typing import Optional

from opentelemetry import baggage, trace
from opentelemetry.context import attach, detach, get_current


def set_baggage(key: str, value: str) -> object:
    """Set a baggage value and attach the new context.

    Baggage is automatically propagated across service boundaries via
    W3C Baggage header.

    Args:
        key: Baggage key (e.g., ``"botanu.run_id"``).
        value: Baggage value.

    Returns:
        Token for detaching the context later.
    """
    ctx = baggage.set_baggage(key, value, context=get_current())
    return attach(ctx)


def get_baggage(key: str) -> Optional[str]:
    """Get a baggage value from the current context.

    Args:
        key: Baggage key (e.g., ``"botanu.run_id"``).

    Returns:
        Baggage value or ``None`` if not set.
    """
    return baggage.get_baggage(key, context=get_current())


def get_current_span() -> trace.Span:
    """Get the current active span.

    Returns:
        Current span (may be non-recording if no span is active).
    """
    return trace.get_current_span()


def get_run_id() -> Optional[str]:
    """Get the current ``run_id`` from baggage."""
    return get_baggage("botanu.run_id")


def get_use_case() -> Optional[str]:
    """Get the current ``use_case`` from baggage."""
    return get_baggage("botanu.use_case")


def get_workflow() -> Optional[str]:
    """Get the current ``workflow`` from baggage."""
    return get_baggage("botanu.workflow")
