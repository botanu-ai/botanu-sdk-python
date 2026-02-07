# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Helper functions for working with OpenTelemetry spans.

These functions add Botanu-specific attributes to the current span.
"""

from __future__ import annotations

from typing import Optional

from opentelemetry import trace


def emit_outcome(
    status: str,
    *,
    value_type: Optional[str] = None,
    value_amount: Optional[float] = None,
    confidence: Optional[float] = None,
    reason: Optional[str] = None,
) -> None:
    """Emit an outcome for the current span.

    Sets span attributes for outcome tracking and ROI calculation.

    Args:
        status: Outcome status (``"success"``, ``"partial"``, ``"failed"``).
        value_type: Type of business value (e.g., ``"tickets_resolved"``).
        value_amount: Quantified value amount.
        confidence: Confidence score (0.0–1.0).
        reason: Optional reason for the outcome.

    Example::

        >>> emit_outcome("success", value_type="tickets_resolved", value_amount=1)
        >>> emit_outcome("failed", reason="missing_context")
    """
    span = trace.get_current_span()

    span.set_attribute("botanu.outcome", status)

    if value_type:
        span.set_attribute("botanu.outcome.value_type", value_type)

    if value_amount is not None:
        span.set_attribute("botanu.outcome.value_amount", value_amount)

    if confidence is not None:
        span.set_attribute("botanu.outcome.confidence", confidence)

    if reason:
        span.set_attribute("botanu.outcome.reason", reason)

    event_attrs: dict[str, object] = {"status": status}
    if value_type:
        event_attrs["value_type"] = value_type
    if value_amount is not None:
        event_attrs["value_amount"] = value_amount

    span.add_event("botanu.outcome_emitted", event_attrs)


def set_business_context(
    *,
    customer_id: Optional[str] = None,
    team: Optional[str] = None,
    cost_center: Optional[str] = None,
    region: Optional[str] = None,
) -> None:
    """Set business context attributes on the current span.

    Args:
        customer_id: Customer identifier for multi-tenant attribution.
        team: Team or department.
        cost_center: Cost centre for financial tracking.
        region: Geographic region.
    """
    span = trace.get_current_span()

    if customer_id:
        span.set_attribute("botanu.customer_id", customer_id)

    if team:
        span.set_attribute("botanu.team", team)

    if cost_center:
        span.set_attribute("botanu.cost_center", cost_center)

    if region:
        span.set_attribute("botanu.region", region)
