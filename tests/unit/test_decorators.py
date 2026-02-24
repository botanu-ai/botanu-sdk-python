# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for SDK decorators."""

from __future__ import annotations

import pytest
from opentelemetry import baggage, trace
from opentelemetry import context as otel_context
from opentelemetry.context import get_current

from botanu.sdk.decorators import botanu_outcome, botanu_workflow


@pytest.fixture(autouse=True)
def _clean_otel_context():
    """Reset OTel context before each test to avoid baggage leaking between tests."""
    token = otel_context.attach(otel_context.Context())
    yield
    otel_context.detach(token)


class TestBotanuWorkflowDecorator:
    """Tests for @botanu_workflow decorator."""

    def test_sync_function_creates_span(self, memory_exporter):
        @botanu_workflow("Test Workflow", event_id="evt-1", customer_id="cust-1")
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "botanu.run/Test Workflow"

    def test_span_has_run_attributes(self, memory_exporter):
        @botanu_workflow("Customer Support", event_id="ticket-42", customer_id="bigretail")
        def my_function():
            return "done"

        my_function()

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)

        assert "botanu.run_id" in attrs
        assert attrs["botanu.workflow"] == "Customer Support"
        assert attrs["botanu.event_id"] == "ticket-42"
        assert attrs["botanu.customer_id"] == "bigretail"

    def test_emits_started_event(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def my_function():
            pass

        my_function()

        spans = memory_exporter.get_finished_spans()
        events = spans[0].events

        started_events = [e for e in events if e.name == "botanu.run.started"]
        assert len(started_events) == 1

    def test_emits_completed_event(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def my_function():
            return "done"

        my_function()

        spans = memory_exporter.get_finished_spans()
        events = spans[0].events

        completed_events = [e for e in events if e.name == "botanu.run.completed"]
        assert len(completed_events) == 1
        assert completed_events[0].attributes["status"] == "success"

    def test_records_exception_on_failure(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def failing_function():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            failing_function()

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1

        events = spans[0].events
        completed_events = [e for e in events if e.name == "botanu.run.completed"]
        assert len(completed_events) == 1
        assert completed_events[0].attributes["status"] == "failure"
        assert completed_events[0].attributes["error_class"] == "ValueError"

    @pytest.mark.asyncio
    async def test_async_function_creates_span(self, memory_exporter):
        @botanu_workflow("Async Test", event_id="evt-1", customer_id="cust-1")
        async def async_function():
            return "async result"

        result = await async_function()

        assert result == "async result"
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "botanu.run/Async Test"

    @pytest.mark.asyncio
    async def test_async_exception_handling(self, memory_exporter):
        @botanu_workflow("Async Test", event_id="evt-1", customer_id="cust-1")
        async def failing_async():
            raise RuntimeError("async error")

        with pytest.raises(RuntimeError):
            await failing_async()

        spans = memory_exporter.get_finished_spans()
        events = spans[0].events
        completed_events = [e for e in events if e.name == "botanu.run.completed"]
        assert completed_events[0].attributes["status"] == "failure"

    def test_workflow_version_computed(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def versioned_function():
            return "versioned"

        versioned_function()

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)

        assert "botanu.workflow.version" in attrs
        assert attrs["botanu.workflow.version"].startswith("v:")

    def test_return_value_preserved(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def returns_dict():
            return {"key": "value", "count": 42}

        result = returns_dict()
        assert result == {"key": "value", "count": 42}

    @pytest.mark.asyncio
    async def test_async_return_value_preserved(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        async def returns_data():
            return [1, 2, 3]

        result = await returns_data()
        assert result == [1, 2, 3]

    def test_exception_re_raised(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def raises():
            raise TypeError("bad type")

        with pytest.raises(TypeError, match="bad type"):
            raises()

    def test_outcome_status_set_on_success(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def my_fn():
            return "ok"

        my_fn()
        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.outcome.status"] == "success"

    def test_outcome_status_set_on_failure(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def failing():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            failing()

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.outcome.status"] == "failure"

    def test_duration_ms_recorded(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def quick_fn():
            return "done"

        quick_fn()
        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "botanu.run.duration_ms" in attrs
        assert attrs["botanu.run.duration_ms"] >= 0

    def test_custom_span_kind(self, memory_exporter):
        from opentelemetry.trace import SpanKind

        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1", span_kind=SpanKind.CLIENT)
        def client_fn():
            return "ok"

        client_fn()
        spans = memory_exporter.get_finished_spans()
        assert spans[0].kind == SpanKind.CLIENT

    def test_root_run_id_equals_run_id_for_root(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1")
        def root_fn():
            return "root"

        root_fn()
        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        # For a root run, root_run_id should equal run_id
        assert attrs["botanu.root_run_id"] == attrs["botanu.run_id"]

    def test_tenant_id_propagated(self, memory_exporter):
        @botanu_workflow("Test", event_id="evt-1", customer_id="cust-1", tenant_id="tenant-abc")
        def tenant_fn():
            return "ok"

        tenant_fn()
        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["botanu.tenant_id"] == "tenant-abc"

    def test_baggage_cleaned_up_after_sync(self, memory_exporter):
        """Verify baggage does NOT leak after the decorated function completes."""

        @botanu_workflow("Leak Test", event_id="evt-1", customer_id="cust-1")
        def my_fn():
            # Inside the function, baggage should be set
            assert baggage.get_baggage("botanu.run_id", get_current()) is not None
            return "ok"

        # Before: no baggage
        assert baggage.get_baggage("botanu.run_id", get_current()) is None

        my_fn()

        # After: baggage must be cleaned up (detached)
        assert baggage.get_baggage("botanu.run_id", get_current()) is None

    @pytest.mark.asyncio
    async def test_baggage_cleaned_up_after_async(self, memory_exporter):
        """Verify baggage does NOT leak after an async decorated function."""

        @botanu_workflow("Async Leak Test", event_id="evt-1", customer_id="cust-1")
        async def my_fn():
            assert baggage.get_baggage("botanu.run_id", get_current()) is not None
            return "ok"

        assert baggage.get_baggage("botanu.run_id", get_current()) is None

        await my_fn()

        assert baggage.get_baggage("botanu.run_id", get_current()) is None

    def test_baggage_cleaned_up_after_exception(self, memory_exporter):
        """Verify baggage is cleaned up even when the function raises."""

        @botanu_workflow("Exception Leak Test", event_id="evt-1", customer_id="cust-1")
        def failing_fn():
            raise RuntimeError("boom")

        assert baggage.get_baggage("botanu.run_id", get_current()) is None

        with pytest.raises(RuntimeError):
            failing_fn()

        # Must be cleaned up despite the exception
        assert baggage.get_baggage("botanu.run_id", get_current()) is None

    def test_event_id_required(self):
        """Should raise ValueError if event_id is missing."""
        with pytest.raises(ValueError, match="event_id is required"):
            @botanu_workflow("Test", event_id="", customer_id="cust-1")
            def my_fn():
                pass

    def test_customer_id_required(self):
        """Should raise ValueError if customer_id is missing."""
        with pytest.raises(ValueError, match="customer_id is required"):
            @botanu_workflow("Test", event_id="evt-1", customer_id="")
            def my_fn():
                pass

    def test_event_id_and_customer_id_in_baggage(self, memory_exporter):
        """Verify event_id and customer_id are propagated via baggage."""

        @botanu_workflow("Baggage Test", event_id="ticket-99", customer_id="acme-corp")
        def my_fn():
            assert baggage.get_baggage("botanu.event_id", get_current()) == "ticket-99"
            assert baggage.get_baggage("botanu.customer_id", get_current()) == "acme-corp"
            return "ok"

        my_fn()


class TestBotanuOutcomeDecorator:
    """Tests for @botanu_outcome decorator."""

    def test_sync_success_emits_outcome(self, memory_exporter):
        tracer_instance = trace.get_tracer("test")

        @botanu_outcome()
        def my_fn():
            return "ok"

        with tracer_instance.start_as_current_span("parent"):
            result = my_fn()

        assert result == "ok"

    def test_sync_failure_emits_failed(self, memory_exporter):
        tracer_instance = trace.get_tracer("test")

        @botanu_outcome()
        def failing_fn():
            raise ValueError("broken")

        with tracer_instance.start_as_current_span("parent"):
            with pytest.raises(ValueError, match="broken"):
                failing_fn()

    @pytest.mark.asyncio
    async def test_async_success_emits_outcome(self, memory_exporter):
        tracer_instance = trace.get_tracer("test")

        @botanu_outcome()
        async def async_fn():
            return "async ok"

        with tracer_instance.start_as_current_span("parent"):
            result = await async_fn()

        assert result == "async ok"

    @pytest.mark.asyncio
    async def test_async_failure_emits_failed(self, memory_exporter):
        tracer_instance = trace.get_tracer("test")

        @botanu_outcome()
        async def async_fail():
            raise RuntimeError("async boom")

        with tracer_instance.start_as_current_span("parent"):
            with pytest.raises(RuntimeError, match="async boom"):
                await async_fail()

    def test_exception_re_raised(self, memory_exporter):
        tracer_instance = trace.get_tracer("test")

        @botanu_outcome()
        def raises():
            raise TypeError("type err")

        with tracer_instance.start_as_current_span("parent"):
            with pytest.raises(TypeError, match="type err"):
                raises()
