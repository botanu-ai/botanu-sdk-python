# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Helper functions for working with OpenTelemetry spans.

These functions add Botanu-specific attributes to the current span.
"""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import trace

logger = logging.getLogger(__name__)


def emit_outcome(
    *,
    value_type: Optional[str] = None,
    value_amount: Optional[float] = None,
    confidence: Optional[float] = None,
    reason: Optional[str] = None,
    error_type: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
) -> None:
    """Emit diagnostic outcome fields on the current span.

    These are **diagnostic only** — the authoritative event outcome is
    resolved server-side from SoR connectors / HITL reviews / eval verdict
    rollup. Use these fields to enrich dashboards with business value
    signals (tickets resolved, dollars saved, etc.) and error diagnostics.

    Args:
        value_type: Type of business value (e.g., ``"tickets_resolved"``).
        value_amount: Quantified value amount.
        confidence: Confidence score (0.0–1.0).
        reason: Optional diagnostic reason.
        error_type: Error classification (e.g., ``"ValidationError"``).
        metadata: Additional diagnostic key-value metadata.
    """
    span = trace.get_current_span()

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

    event_attrs: dict[str, object] = {}
    if value_type:
        event_attrs["value_type"] = value_type
    if value_amount is not None:
        event_attrs["value_amount"] = value_amount
    if error_type:
        event_attrs["error_type"] = error_type
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


# ── SoR correlation (Tier 1) ──────────────────────────────────────────────
#
# Links a Botanu event to a record in the customer's system of record so the
# sor-connector's OutcomeSignal (e.g. Zendesk ticket reopen, Stripe refund)
# can find the matching event. Tier-1 correlation writes a span attribute of
# the form `botanu.correlation.<key>_id` that the sor-connector reads in its
# normalizer. Confidence of Tier 1 matches is 1.0.
#
# Convention: pass keyword args named `<sor>_id` — the suffix is stripped so
# the stamped attribute is `botanu.correlation.<sor>_id`. If the caller
# passes a key that doesn't end in `_id`, we stamp it verbatim and warn.
#
# Examples::
#
#     set_correlation(zendesk_ticket_id="T-123")
#     set_correlation(stripe_charge_id="ch_1NAbcd", zendesk_ticket_id="T-123")
#     set_correlation(sfdc_opportunity_id="0065g00000abcdef")

_SUPPORTED_SOR_PREFIXES = frozenset({
    "zendesk",
    "stripe",
    "salesforce",
    "sfdc",
    "jira",
    "servicenow",
    "hubspot",
    "intercom",
    "freshdesk",
    "zoho",
    "front",
})


def set_correlation(**correlations: Optional[str]) -> None:
    """Stamp one or more `botanu.correlation.*` span attributes.

    Called inside a :func:`botanu.event` scope to link the current event to
    one or more external SoR records. The sor-connector uses these attributes
    to correlate inbound webhooks (ticket reopen, refund, etc.) back to this
    event via Tier-1 correlation.

    Each keyword becomes a span attribute. A ``None`` or empty-string value
    is dropped silently so it's safe to pass conditionally-set IDs.

    Args:
        **correlations: keyword args like ``zendesk_ticket_id="T-123"``.
            The key is stamped verbatim as ``botanu.correlation.<key>``.

    Example::

        with botanu.event(event_id="evt-42", customer_id="acme", workflow="Support"):
            set_correlation(zendesk_ticket_id=ticket.id)
            ...
    """
    if not correlations:
        return

    span = trace.get_current_span()
    for key, value in correlations.items():
        if value is None or value == "":
            continue
        # Soft validation: warn on unfamiliar prefixes, still stamp. Customers
        # may integrate with SoRs we don't yet have named support for.
        prefix = key.split("_", 1)[0]
        if prefix not in _SUPPORTED_SOR_PREFIXES:
            logger.info(
                "set_correlation: unfamiliar SoR prefix %r; stamping "
                "botanu.correlation.%s anyway",
                prefix,
                key,
            )
        span.set_attribute(f"botanu.correlation.{key}", str(value))
