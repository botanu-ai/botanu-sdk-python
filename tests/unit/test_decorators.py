# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for SDK decorators."""

from __future__ import annotations

import pytest

from botanu.sdk.decorators import botanu_use_case


class TestBotanuUseCaseDecorator:
    """Tests for @botanu_use_case decorator."""

    def test_sync_function_creates_span(self, memory_exporter):
        @botanu_use_case("Test Use Case")
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "botanu.run/Test Use Case"

    def test_span_has_run_attributes(self, memory_exporter):
        @botanu_use_case("Customer Support", workflow="handle_ticket")
        def my_function():
            return "done"

        my_function()

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)

        assert "botanu.run_id" in attrs
        assert attrs["botanu.use_case"] == "Customer Support"
        assert attrs["botanu.workflow"] == "handle_ticket"

    def test_emits_started_event(self, memory_exporter):
        @botanu_use_case("Test")
        def my_function():
            pass

        my_function()

        spans = memory_exporter.get_finished_spans()
        events = spans[0].events

        started_events = [e for e in events if e.name == "botanu.run.started"]
        assert len(started_events) == 1

    def test_emits_completed_event(self, memory_exporter):
        @botanu_use_case("Test")
        def my_function():
            return "done"

        my_function()

        spans = memory_exporter.get_finished_spans()
        events = spans[0].events

        completed_events = [e for e in events if e.name == "botanu.run.completed"]
        assert len(completed_events) == 1
        assert completed_events[0].attributes["status"] == "success"

    def test_records_exception_on_failure(self, memory_exporter):
        @botanu_use_case("Test")
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
        @botanu_use_case("Async Test")
        async def async_function():
            return "async result"

        result = await async_function()

        assert result == "async result"
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "botanu.run/Async Test"

    @pytest.mark.asyncio
    async def test_async_exception_handling(self, memory_exporter):
        @botanu_use_case("Async Test")
        async def failing_async():
            raise RuntimeError("async error")

        with pytest.raises(RuntimeError):
            await failing_async()

        spans = memory_exporter.get_finished_spans()
        events = spans[0].events
        completed_events = [e for e in events if e.name == "botanu.run.completed"]
        assert completed_events[0].attributes["status"] == "failure"

    def test_workflow_version_computed(self, memory_exporter):
        @botanu_use_case("Test")
        def versioned_function():
            return "versioned"

        versioned_function()

        spans = memory_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)

        assert "botanu.workflow.version" in attrs
        assert attrs["botanu.workflow.version"].startswith("v:")
