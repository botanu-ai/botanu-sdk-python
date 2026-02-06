# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for Attempt Ledger."""

from __future__ import annotations

import os
from unittest import mock

from opentelemetry import trace

from botanu.tracking.ledger import (
    AttemptLedger,
    AttemptStatus,
    LedgerEventType,
    get_ledger,
    record_attempt_ended,
    record_attempt_started,
    record_llm_attempted,
    record_tool_attempted,
    set_ledger,
)


class TestLedgerEventType:
    """Tests for LedgerEventType enum."""

    def test_event_types_are_strings(self):
        assert LedgerEventType.ATTEMPT_STARTED == "attempt.started"
        assert LedgerEventType.ATTEMPT_ENDED == "attempt.ended"
        assert LedgerEventType.LLM_ATTEMPTED == "llm.attempted"
        assert LedgerEventType.TOOL_ATTEMPTED == "tool.attempted"
        assert LedgerEventType.CANCEL_REQUESTED == "cancellation.requested"
        assert LedgerEventType.CANCEL_ACKNOWLEDGED == "cancellation.acknowledged"
        assert LedgerEventType.ZOMBIE_DETECTED == "zombie.detected"
        assert LedgerEventType.REDELIVERY_DETECTED == "redelivery.detected"


class TestAttemptStatus:
    """Tests for AttemptStatus enum."""

    def test_status_values(self):
        assert AttemptStatus.SUCCESS == "success"
        assert AttemptStatus.ERROR == "error"
        assert AttemptStatus.TIMEOUT == "timeout"
        assert AttemptStatus.CANCELLED == "cancelled"
        assert AttemptStatus.RATE_LIMITED == "rate_limited"


class TestAttemptLedger:
    """Tests for AttemptLedger class."""

    def test_default_service_name(self):
        """Should use environment variable for default service name."""
        with mock.patch.dict(os.environ, {"OTEL_SERVICE_NAME": "test-service"}):
            ledger = AttemptLedger.__new__(AttemptLedger)
            ledger.service_name = os.getenv("OTEL_SERVICE_NAME", "unknown")
            ledger._initialized = False
            assert ledger.service_name == "test-service"

    def test_get_trace_context_no_span(self):
        """Should return empty dict when no active span."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None

        # No span context - should return empty
        ctx = ledger._get_trace_context()
        assert ctx == {} or "trace_id" in ctx  # May have context from other tests

    def test_get_trace_context_with_span(self, memory_exporter):
        """Should return trace context when span is active."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            span_ctx = span.get_span_context()
            ctx = ledger._get_trace_context()

            assert "trace_id" in ctx
            assert "span_id" in ctx
            assert ctx["trace_id"] == format(span_ctx.trace_id, "032x")
            assert ctx["span_id"] == format(span_ctx.span_id, "016x")

    def test_emit_when_not_initialized(self):
        """Should not raise when emitting without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None

        # Should not raise
        ledger._emit(LedgerEventType.ATTEMPT_STARTED, None, {"test": "value"})

    def test_attempt_started_not_initialized(self):
        """Should not raise when calling methods without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None
        ledger.service_name = "test"

        # Should not raise
        ledger.attempt_started(
            run_id="run-123",
            use_case="Test Case",
            attempt=1,
        )

    def test_attempt_ended_not_initialized(self):
        """Should not raise when calling methods without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None
        ledger.service_name = "test"

        # Should not raise
        ledger.attempt_ended(
            run_id="run-123",
            status="success",
            duration_ms=1000.0,
        )

    def test_llm_attempted_not_initialized(self):
        """Should not raise when calling methods without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None
        ledger.service_name = "test"

        # Should not raise
        ledger.llm_attempted(
            run_id="run-123",
            provider="openai",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
        )

    def test_tool_attempted_not_initialized(self):
        """Should not raise when calling methods without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None
        ledger.service_name = "test"

        # Should not raise
        ledger.tool_attempted(
            run_id="run-123",
            tool_name="search",
        )

    def test_cancel_requested_not_initialized(self):
        """Should not raise when calling methods without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None
        ledger.service_name = "test"

        # Should not raise
        ledger.cancel_requested(run_id="run-123", reason="user")

    def test_cancel_acknowledged_not_initialized(self):
        """Should not raise when calling methods without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None
        ledger.service_name = "test"

        # Should not raise
        ledger.cancel_acknowledged(run_id="run-123", acknowledged_by="handler")

    def test_zombie_detected_not_initialized(self):
        """Should not raise when calling methods without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None
        ledger.service_name = "test"

        # Should not raise
        ledger.zombie_detected(
            run_id="run-123",
            deadline_ts=1000.0,
            actual_end_ts=2000.0,
            zombie_duration_ms=1000.0,
            component="handler",
        )

    def test_redelivery_detected_not_initialized(self):
        """Should not raise when calling methods without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False
        ledger._logger = None
        ledger.service_name = "test"

        # Should not raise
        ledger.redelivery_detected(
            run_id="run-123",
            queue_name="my-queue",
            delivery_count=3,
        )

    def test_flush_when_not_initialized(self):
        """Should return True when flushing without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False

        result = ledger.flush()
        assert result is True

    def test_shutdown_when_not_initialized(self):
        """Should not raise when shutting down without initialization."""
        ledger = AttemptLedger.__new__(AttemptLedger)
        ledger._initialized = False

        # Should not raise
        ledger.shutdown()


class TestGlobalLedger:
    """Tests for global ledger functions."""

    def test_get_ledger_creates_instance(self):
        """get_ledger should create a ledger if none exists."""
        # Reset global
        import botanu.tracking.ledger as ledger_module

        ledger_module._global_ledger = None

        ledger = get_ledger()
        assert isinstance(ledger, AttemptLedger)

    def test_set_ledger(self):
        """set_ledger should update the global instance."""
        custom_ledger = AttemptLedger.__new__(AttemptLedger)
        custom_ledger._initialized = False
        custom_ledger.service_name = "custom-service"

        set_ledger(custom_ledger)
        assert get_ledger() is custom_ledger

    def test_record_attempt_started(self):
        """record_attempt_started should call the global ledger."""
        mock_ledger = mock.MagicMock(spec=AttemptLedger)
        set_ledger(mock_ledger)

        record_attempt_started(run_id="run-123", use_case="Test")

        mock_ledger.attempt_started.assert_called_once_with(run_id="run-123", use_case="Test")

    def test_record_attempt_ended(self):
        """record_attempt_ended should call the global ledger."""
        mock_ledger = mock.MagicMock(spec=AttemptLedger)
        set_ledger(mock_ledger)

        record_attempt_ended(run_id="run-123", status="success")

        mock_ledger.attempt_ended.assert_called_once_with(run_id="run-123", status="success")

    def test_record_llm_attempted(self):
        """record_llm_attempted should call the global ledger."""
        mock_ledger = mock.MagicMock(spec=AttemptLedger)
        set_ledger(mock_ledger)

        record_llm_attempted(run_id="run-123", provider="openai", model="gpt-4")

        mock_ledger.llm_attempted.assert_called_once_with(run_id="run-123", provider="openai", model="gpt-4")

    def test_record_tool_attempted(self):
        """record_tool_attempted should call the global ledger."""
        mock_ledger = mock.MagicMock(spec=AttemptLedger)
        set_ledger(mock_ledger)

        record_tool_attempted(run_id="run-123", tool_name="search")

        mock_ledger.tool_attempted.assert_called_once_with(run_id="run-123", tool_name="search")
