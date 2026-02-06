# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for context and baggage helpers."""

from __future__ import annotations

from opentelemetry import trace

from botanu.sdk.context import (
    get_baggage,
    get_current_span,
    get_run_id,
    get_use_case,
    set_baggage,
)


class TestBaggageHelpers:
    """Tests for baggage helper functions."""

    def test_set_and_get_baggage(self):
        token = set_baggage("test.key", "test-value")
        assert token is not None

        value = get_baggage("test.key")
        assert value == "test-value"

    def test_get_baggage_missing_key(self):
        value = get_baggage("nonexistent.key")
        assert value is None

    def test_get_run_id(self):
        set_baggage("botanu.run_id", "run-12345")
        assert get_run_id() == "run-12345"

    def test_get_run_id_not_set(self):
        # In a fresh context, run_id might not be set
        # This tests the function doesn't crash
        result = get_run_id()
        # Result could be None or a previously set value
        assert result is None or isinstance(result, str)

    def test_get_use_case(self):
        set_baggage("botanu.use_case", "Customer Support")
        assert get_use_case() == "Customer Support"


class TestSpanHelpers:
    """Tests for span helper functions."""

    def test_get_current_span_with_active_span(self, memory_exporter):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as expected_span:
            current = get_current_span()
            assert current == expected_span

    def test_get_current_span_no_active_span(self):
        # When no span is active, should return a non-recording span
        span = get_current_span()
        assert span is not None
        # Non-recording spans have is_recording() == False
        assert not span.is_recording()
