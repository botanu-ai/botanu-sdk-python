# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for span helper functions."""

from __future__ import annotations

from opentelemetry import trace

from botanu.sdk.span_helpers import emit_outcome, set_business_context


class TestEmitOutcome:
    """Tests for emit_outcome function."""

    def test_emit_success_outcome(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            emit_outcome("success")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.outcome") == "success"

    def test_emit_failure_outcome(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            emit_outcome("failed", reason="timeout")

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.outcome") == "failed"
        assert attrs.get("botanu.outcome.reason") == "timeout"

    def test_emit_outcome_with_value(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            emit_outcome(
                "success",
                value_type="tickets_resolved",
                value_amount=5.0,
            )

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.outcome") == "success"
        assert attrs.get("botanu.outcome.value_type") == "tickets_resolved"
        assert attrs.get("botanu.outcome.value_amount") == 5.0

    def test_emit_outcome_with_confidence(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            emit_outcome("success", confidence=0.95)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.outcome.confidence") == 0.95

    def test_emit_outcome_adds_event(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            emit_outcome("success", value_type="orders", value_amount=1)

        spans = memory_exporter.get_finished_spans()
        events = [e for e in spans[0].events if e.name == "botanu.outcome_emitted"]
        assert len(events) == 1
        assert events[0].attributes["status"] == "success"


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
