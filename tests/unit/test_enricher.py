# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for RunContextEnricher processor."""

from __future__ import annotations

from unittest import mock

from opentelemetry import baggage, context, trace
from opentelemetry.sdk.trace import ReadableSpan

from botanu.processors.enricher import RunContextEnricher


class TestRunContextEnricher:
    """Tests for RunContextEnricher processor."""

    def test_init_lean_mode_default(self):
        """Default should be lean mode."""
        enricher = RunContextEnricher()
        assert enricher._lean_mode is True
        assert enricher._baggage_keys == RunContextEnricher.BAGGAGE_KEYS_LEAN

    def test_init_lean_mode_false(self):
        """Can enable full mode."""
        enricher = RunContextEnricher(lean_mode=False)
        assert enricher._lean_mode is False
        assert enricher._baggage_keys == RunContextEnricher.BAGGAGE_KEYS_FULL

    def test_on_start_reads_baggage(self, memory_exporter):
        """on_start should read baggage and set span attributes."""
        enricher = RunContextEnricher(lean_mode=True)

        # Set up baggage context - start from a clean context
        ctx = context.Context()
        ctx = baggage.set_baggage("botanu.run_id", "test-run-123", context=ctx)
        ctx = baggage.set_baggage("botanu.use_case", "Test Case", context=ctx)

        # Create a span with the baggage context
        tracer = trace.get_tracer("test")
        token = context.attach(ctx)
        try:
            with tracer.start_as_current_span("test-span") as span:
                # Manually call on_start to simulate processor behavior
                enricher.on_start(span, ctx)
        finally:
            context.detach(token)

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.run_id") == "test-run-123"
        assert attrs.get("botanu.use_case") == "Test Case"

    def test_on_start_full_mode(self, memory_exporter):
        """Full mode should read all baggage keys."""
        enricher = RunContextEnricher(lean_mode=False)

        # Set up baggage context with all keys - start from a clean context
        ctx = context.Context()
        ctx = baggage.set_baggage("botanu.run_id", "run-456", context=ctx)
        ctx = baggage.set_baggage("botanu.use_case", "Full Test", context=ctx)
        ctx = baggage.set_baggage("botanu.workflow", "my_workflow", context=ctx)
        ctx = baggage.set_baggage("botanu.environment", "staging", context=ctx)
        ctx = baggage.set_baggage("botanu.tenant_id", "tenant-789", context=ctx)

        tracer = trace.get_tracer("test")
        token = context.attach(ctx)
        try:
            with tracer.start_as_current_span("test-span") as span:
                enricher.on_start(span, ctx)
        finally:
            context.detach(token)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs.get("botanu.run_id") == "run-456"
        assert attrs.get("botanu.use_case") == "Full Test"
        assert attrs.get("botanu.workflow") == "my_workflow"
        assert attrs.get("botanu.environment") == "staging"
        assert attrs.get("botanu.tenant_id") == "tenant-789"

    def test_on_start_missing_baggage(self, memory_exporter):
        """Should handle missing baggage gracefully."""
        enricher = RunContextEnricher()

        # Create a clean context with no baggage
        clean_ctx = context.Context()

        tracer = trace.get_tracer("test")
        token = context.attach(clean_ctx)
        try:
            with tracer.start_as_current_span("test-span") as span:
                # Pass the clean context with no baggage
                enricher.on_start(span, clean_ctx)
        finally:
            context.detach(token)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        # No botanu attributes should be set
        assert "botanu.run_id" not in attrs

    def test_on_start_does_not_override_existing(self, memory_exporter):
        """Should not override existing span attributes."""
        enricher = RunContextEnricher()

        # Set up baggage context
        ctx = context.Context()
        ctx = baggage.set_baggage("botanu.run_id", "baggage-id", context=ctx)
        ctx = baggage.set_baggage("botanu.use_case", "Baggage Case", context=ctx)

        tracer = trace.get_tracer("test")
        token = context.attach(ctx)
        try:
            with tracer.start_as_current_span("test-span") as span:
                # Set attribute before enricher runs
                span.set_attribute("botanu.run_id", "existing-id")
                # Now run enricher - should not override
                enricher.on_start(span, ctx)
        finally:
            context.detach(token)

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        # Should keep existing value
        assert attrs.get("botanu.run_id") == "existing-id"
        # But should set use_case since it wasn't set before
        assert attrs.get("botanu.use_case") == "Baggage Case"

    def test_on_end_noop(self):
        """on_end should be a no-op."""
        enricher = RunContextEnricher()
        mock_span = mock.MagicMock(spec=ReadableSpan)
        # Should not raise
        enricher.on_end(mock_span)

    def test_shutdown_noop(self):
        """shutdown should be a no-op."""
        enricher = RunContextEnricher()
        # Should not raise
        enricher.shutdown()

    def test_force_flush_returns_true(self):
        """force_flush should return True."""
        enricher = RunContextEnricher()
        assert enricher.force_flush() is True
        assert enricher.force_flush(timeout_millis=1000) is True

    def test_baggage_keys_constants(self):
        """Verify baggage key constants."""
        assert "botanu.run_id" in RunContextEnricher.BAGGAGE_KEYS_LEAN
        assert "botanu.use_case" in RunContextEnricher.BAGGAGE_KEYS_LEAN
        assert len(RunContextEnricher.BAGGAGE_KEYS_LEAN) == 2

        assert "botanu.run_id" in RunContextEnricher.BAGGAGE_KEYS_FULL
        assert "botanu.workflow" in RunContextEnricher.BAGGAGE_KEYS_FULL
        assert "botanu.environment" in RunContextEnricher.BAGGAGE_KEYS_FULL
        assert len(RunContextEnricher.BAGGAGE_KEYS_FULL) == 6
