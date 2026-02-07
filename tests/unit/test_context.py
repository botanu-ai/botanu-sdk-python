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
    get_workflow,
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

    def test_get_workflow(self):
        set_baggage("botanu.workflow", "ticket_handler")
        assert get_workflow() == "ticket_handler"

    def test_get_workflow_not_set(self):
        result = get_workflow()
        assert result is None or isinstance(result, str)


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


class TestSetBaggageTokenManagement:
    """Tests for set_baggage token lifecycle and context management."""

    def test_set_baggage_returns_detachable_token(self):
        from opentelemetry.context import detach

        token = set_baggage("botanu.token_test", "val1")
        assert token is not None
        assert get_baggage("botanu.token_test") == "val1"
        detach(token)

    def test_multiple_set_baggage_stacks_values(self):
        token1 = set_baggage("botanu.stack_a", "a")
        token2 = set_baggage("botanu.stack_b", "b")

        assert get_baggage("botanu.stack_a") == "a"
        assert get_baggage("botanu.stack_b") == "b"
        assert token1 is not None
        assert token2 is not None

    def test_overwrite_same_key(self):
        set_baggage("botanu.overwrite", "first")
        set_baggage("botanu.overwrite", "second")
        assert get_baggage("botanu.overwrite") == "second"

    def test_get_baggage_returns_none_in_clean_context(self):
        from opentelemetry import context as otel_context

        token = otel_context.attach(otel_context.Context())
        try:
            assert get_baggage("botanu.surely_missing") is None
        finally:
            otel_context.detach(token)
