# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Helper functions for working with OpenTelemetry spans.

These functions add Botanu-specific attributes to the current span.
"""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import trace

from botanu.sdk.context import get_baggage

logger = logging.getLogger(__name__)

VALID_OUTCOME_STATUSES = {
    "success", "partial", "failed", "timeout", "canceled", "abandoned",
}


def emit_outcome(
    status: str,
    *,
    value_type: Optional[str] = None,
    value_amount: Optional[float] = None,
    confidence: Optional[float] = None,
    reason: Optional[str] = None,
    error_type: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
) -> None:
    """Emit an outcome for the current span.

    Sets span attributes for outcome tracking and ROI calculation.
    Also emits an OTel log record to trigger collector flush.

    Args:
        status: Outcome status. Must be one of ``"success"``, ``"partial"``,
            ``"failed"``, ``"timeout"``, ``"canceled"``, ``"abandoned"``.
        value_type: Type of business value (e.g., ``"tickets_resolved"``).
        value_amount: Quantified value amount.
        confidence: Confidence score (0.0–1.0).
        reason: Optional reason for the outcome.
        error_type: Error classification (e.g., ``"ValidationError"``).
        metadata: Additional key-value metadata to attach to the outcome.

    Raises:
        ValueError: If *status* is not a recognised outcome status.

    Example::

        >>> emit_outcome("success", value_type="tickets_resolved", value_amount=1)
        >>> emit_outcome("failed", error_type="TimeoutError", reason="LLM took >30s")
    """
    if status not in VALID_OUTCOME_STATUSES:
        raise ValueError(
            f"Invalid outcome status '{status}'. "
            f"Must be one of: {', '.join(sorted(VALID_OUTCOME_STATUSES))}"
        )

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

    if error_type:
        span.set_attribute("botanu.outcome.error_type", error_type)

    if metadata:
        for key, value in metadata.items():
            span.set_attribute(f"botanu.outcome.metadata.{key}", value)

    event_attrs: dict[str, object] = {"status": status}
    if value_type:
        event_attrs["value_type"] = value_type
    if value_amount is not None:
        event_attrs["value_amount"] = value_amount
    if error_type:
        event_attrs["error_type"] = error_type

    span.add_event("botanu.outcome_emitted", event_attrs)

    # Emit OTel log record for collector flush trigger
    event_id = get_baggage("botanu.event_id")
    if event_id:
        try:
            from opentelemetry._logs import get_logger_provider

            logger_provider = get_logger_provider()
            otel_logger = logger_provider.get_logger("botanu.outcome")
            otel_logger.emit(
                body=f"outcome:{status}",
                attributes={
                    "botanu.event_id": event_id,
                    "botanu.outcome.status": status,
                },
            )
        except Exception:
            pass  # Don't break user's code if logs not configured


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
