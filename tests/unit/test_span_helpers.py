# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for span helper functions."""

from __future__ import annotations

from opentelemetry import trace

from botanu.sdk.span_helpers import emit_outcome, set_business_context, set_correlation


class TestEmitOutcome:
    """emit_outcome stamps diagnostic fields only. Authoritative event outcome
    is resolved server-side from SoR connectors / HITL / eval verdict rollup.
    """

    def test_emit_outcome_does_not_stamp_status(self, memory_exporter):
        """There is no `botanu.outcome.status` attribute at all."""
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            emit_outcome(value_type="tickets_resolved", value_amount=1)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "botanu.outcome.status" not in attrs

    def test_emit_outcome_emits_diagnostic_fields(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            emit_outcome(
                reason="timeout",
                error_type="TimeoutError",
                value_type="tickets_resolved",
                value_amount=5.0,
                confidence=0.95,
            )

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.outcome.reason") == "timeout"
        assert attrs.get("botanu.outcome.error_type") == "TimeoutError"
        assert attrs.get("botanu.outcome.value_type") == "tickets_resolved"
        assert attrs.get("botanu.outcome.value_amount") == 5.0
        assert attrs.get("botanu.outcome.confidence") == 0.95

    def test_emit_outcome_event_no_status_attr(self, memory_exporter):
        """The `botanu.outcome_emitted` span event fires for diagnostics and
        does NOT carry `status` in its attributes."""
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            emit_outcome(value_type="orders", value_amount=1)

        spans = memory_exporter.get_finished_spans()
        events = [e for e in spans[0].events if e.name == "botanu.outcome_emitted"]
        assert len(events) == 1
        assert "status" not in dict(events[0].attributes)


class TestSetBusinessContext:
    """Tests for set_business_context function."""

    def test_set_customer_id(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_business_context(customer_id="cust-123")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.customer_id") == "cust-123"

    def test_set_team(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_business_context(team="platform-team")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.team") == "platform-team"

    def test_set_cost_center(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_business_context(cost_center="CC-456")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.cost_center") == "CC-456"

    def test_set_region(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_business_context(region="us-west-2")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.region") == "us-west-2"

    def test_set_multiple_contexts(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_business_context(
                customer_id="cust-123",
                team="support",
                cost_center="CC-456",
                region="eu-central-1",
            )

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.customer_id") == "cust-123"
        assert attrs.get("botanu.team") == "support"
        assert attrs.get("botanu.cost_center") == "CC-456"
        assert attrs.get("botanu.region") == "eu-central-1"


class TestSetCorrelation:
    """set_correlation stamps botanu.correlation.* for SoR Tier-1 matching."""

    def test_stamps_zendesk_ticket_id(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_correlation(zendesk_ticket_id="T-123")

        attrs = dict(memory_exporter.get_finished_spans()[0].attributes)
        assert attrs["botanu.correlation.zendesk_ticket_id"] == "T-123"

    def test_stamps_multiple_sor_ids(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_correlation(
                zendesk_ticket_id="T-1",
                stripe_charge_id="ch_abc",
                sfdc_opportunity_id="006000",
            )

        attrs = dict(memory_exporter.get_finished_spans()[0].attributes)
        assert attrs["botanu.correlation.zendesk_ticket_id"] == "T-1"
        assert attrs["botanu.correlation.stripe_charge_id"] == "ch_abc"
        assert attrs["botanu.correlation.sfdc_opportunity_id"] == "006000"

    def test_drops_none_and_empty(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_correlation(
                zendesk_ticket_id="T-1",
                stripe_charge_id=None,
                hubspot_deal_id="",
            )

        attrs = dict(memory_exporter.get_finished_spans()[0].attributes)
        assert "botanu.correlation.zendesk_ticket_id" in attrs
        assert "botanu.correlation.stripe_charge_id" not in attrs
        assert "botanu.correlation.hubspot_deal_id" not in attrs

    def test_coerces_non_string_to_string(self, memory_exporter):
        """A numeric SoR ID (e.g., integer ticket number) should stamp as string."""
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_correlation(zendesk_ticket_id=42)

        attrs = dict(memory_exporter.get_finished_spans()[0].attributes)
        assert attrs["botanu.correlation.zendesk_ticket_id"] == "42"

    def test_unfamiliar_prefix_still_stamps(self, memory_exporter, caplog):
        """Unknown SoR prefix logs info but still writes the attribute —
        customers may integrate with SoRs we haven't explicitly named."""
        import logging

        tracer = trace.get_tracer("test")
        with caplog.at_level(logging.INFO, logger="botanu.sdk.span_helpers"):
            with tracer.start_as_current_span("test-span"):
                set_correlation(acme_ticket_id="A-999")

        attrs = dict(memory_exporter.get_finished_spans()[0].attributes)
        assert attrs["botanu.correlation.acme_ticket_id"] == "A-999"
        assert any("unfamiliar SoR prefix" in r.message for r in caplog.records)

    def test_no_args_is_noop(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            set_correlation()

        attrs = dict(memory_exporter.get_finished_spans()[0].attributes)
        correlation_attrs = [k for k in attrs if k.startswith("botanu.correlation.")]
        assert correlation_attrs == []
