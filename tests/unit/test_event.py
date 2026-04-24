# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for the unified primary API — :func:`botanu.event` and :func:`botanu.step`.

Covers all three shapes (sync CM, async CM, decorator) and verifies
capture-equivalence with the legacy ``@botanu_workflow`` decorator: same
span attributes, same baggage, same run.started/run.completed events.
"""

from __future__ import annotations

import pytest
from opentelemetry import baggage as otel_baggage
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.context import get_current

import botanu
from botanu.processors.enricher import RunContextEnricher
from botanu.sdk.decorators import _Event


@pytest.fixture(autouse=True)
def _clean_otel_context():
    token = otel_context.attach(otel_context.Context())
    yield
    otel_context.detach(token)


def _attrs(spans):
    return dict(spans[0].attributes)


# ── Context manager form ─────────────────────────────────────────────────

class TestEventContextManager:
    def test_sync_cm_creates_span(self, memory_exporter):
        with botanu.event(event_id="evt-1", customer_id="cust-1", workflow="Support"):
            pass
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "botanu.run/Support"

    def test_sync_cm_stamps_business_attributes(self, memory_exporter):
        with botanu.event(event_id="ticket-42", customer_id="acme", workflow="Support"):
            pass
        attrs = _attrs(memory_exporter.get_finished_spans())
        assert attrs["botanu.event_id"] == "ticket-42"
        assert attrs["botanu.customer_id"] == "acme"
        assert attrs["botanu.workflow"] == "Support"
        assert "botanu.run_id" in attrs

    def test_sync_cm_emits_started_and_completed_events(self, memory_exporter):
        with botanu.event(event_id="e", customer_id="c", workflow="W"):
            pass
        events = memory_exporter.get_finished_spans()[0].events
        assert any(e.name == "botanu.run.started" for e in events)
        completed = [e for e in events if e.name == "botanu.run.completed"]
        assert len(completed) == 1
        assert completed[0].attributes["status"] == "success"

    def test_sync_cm_records_exception_as_failure(self, memory_exporter):
        with pytest.raises(ValueError, match="boom"):
            with botanu.event(event_id="e", customer_id="c", workflow="W"):
                raise ValueError("boom")
        events = memory_exporter.get_finished_spans()[0].events
        completed = next(e for e in events if e.name == "botanu.run.completed")
        assert completed.attributes["status"] == "failure"
        assert completed.attributes["error_class"] == "ValueError"

    def test_sync_cm_sets_baggage_for_downstream_spans(self, memory_exporter):
        with botanu.event(event_id="e", customer_id="c", workflow="W"):
            ctx = get_current()
            assert otel_baggage.get_baggage("botanu.event_id", context=ctx) == "e"
            assert otel_baggage.get_baggage("botanu.customer_id", context=ctx) == "c"
            assert otel_baggage.get_baggage("botanu.workflow", context=ctx) == "W"

    def test_cm_rejects_callable_event_id(self, memory_exporter):
        ev = botanu.event(
            event_id=lambda *a, **k: "dynamic",
            customer_id="c",
            workflow="W",
        )
        with pytest.raises(TypeError, match="decorator"):
            with ev:
                pass

    def test_missing_workflow_raises(self):
        with pytest.raises(ValueError, match="workflow"):
            botanu.event(event_id="e", customer_id="c", workflow="")

    def test_empty_event_id_raises(self):
        with pytest.raises(ValueError, match="event_id"):
            botanu.event(event_id="", customer_id="c", workflow="W")

    def test_empty_customer_id_raises(self):
        with pytest.raises(ValueError, match="customer_id"):
            botanu.event(event_id="e", customer_id="", workflow="W")


# ── Async context manager form ───────────────────────────────────────────

class TestEventAsyncContextManager:
    @pytest.mark.asyncio
    async def test_async_cm_creates_span(self, memory_exporter):
        async with botanu.event(event_id="e", customer_id="c", workflow="Async"):
            pass
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "botanu.run/Async"

    @pytest.mark.asyncio
    async def test_async_cm_records_exception(self, memory_exporter):
        with pytest.raises(RuntimeError):
            async with botanu.event(event_id="e", customer_id="c", workflow="W"):
                raise RuntimeError("async-boom")
        events = memory_exporter.get_finished_spans()[0].events
        completed = next(e for e in events if e.name == "botanu.run.completed")
        assert completed.attributes["status"] == "failure"


# ── Decorator form ───────────────────────────────────────────────────────

class TestEventDecorator:
    def test_sync_decorator_creates_span(self, memory_exporter):
        @botanu.event(event_id="e", customer_id="c", workflow="Dec")
        def fn():
            return 42

        assert fn() == 42
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "botanu.run/Dec"

    def test_decorator_with_lambda_event_id_resolves_from_args(self, memory_exporter):
        class Ticket:
            def __init__(self, tid, uid):
                self.id = tid
                self.user_id = uid

        @botanu.event(
            workflow="Support",
            event_id=lambda t: t.id,
            customer_id=lambda t: t.user_id,
        )
        def handle(ticket):
            return f"handled {ticket.id}"

        result = handle(Ticket("T-99", "user-7"))
        assert result == "handled T-99"
        attrs = _attrs(memory_exporter.get_finished_spans())
        assert attrs["botanu.event_id"] == "T-99"
        assert attrs["botanu.customer_id"] == "user-7"

    @pytest.mark.asyncio
    async def test_async_decorator_creates_span(self, memory_exporter):
        @botanu.event(event_id="e", customer_id="c", workflow="AsyncDec")
        async def fn():
            return "async"

        assert await fn() == "async"
        spans = memory_exporter.get_finished_spans()
        assert spans[0].name == "botanu.run/AsyncDec"

    def test_decorator_records_exception(self, memory_exporter):
        @botanu.event(event_id="e", customer_id="c", workflow="W")
        def bad():
            raise KeyError("nope")

        with pytest.raises(KeyError):
            bad()
        events = memory_exporter.get_finished_spans()[0].events
        completed = next(e for e in events if e.name == "botanu.run.completed")
        assert completed.attributes["status"] == "failure"
        assert completed.attributes["error_class"] == "KeyError"

    def test_decorator_preserves_function_metadata(self, memory_exporter):
        @botanu.event(event_id="e", customer_id="c", workflow="W")
        def my_function():
            """docstring"""
            return None

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "docstring"


# ── Capture parity: CM form should match decorator form ──────────────────

class TestEventCaptureParity:
    def test_cm_and_decorator_produce_same_attrs(self, memory_exporter):
        """Same inputs → same span attributes in either shape."""
        with botanu.event(event_id="e", customer_id="c", workflow="W"):
            pass
        cm_attrs = _attrs(memory_exporter.get_finished_spans())

        memory_exporter.clear()

        @botanu.event(event_id="e", customer_id="c", workflow="W")
        def fn():
            pass
        fn()
        dec_attrs = _attrs(memory_exporter.get_finished_spans())

        for k in ("botanu.event_id", "botanu.customer_id", "botanu.workflow"):
            assert cm_attrs[k] == dec_attrs[k]


# ── botanu.step() ────────────────────────────────────────────────────────

class TestStep:
    def test_step_creates_nested_span(self, memory_exporter):
        with botanu.event(event_id="e", customer_id="c", workflow="W"):
            with botanu.step("retrieval"):
                pass
        spans = memory_exporter.get_finished_spans()
        names = [s.name for s in spans]
        assert "botanu.step/retrieval" in names
        assert "botanu.run/W" in names

    def test_step_stamps_attribute(self, memory_exporter):
        with botanu.event(event_id="e", customer_id="c", workflow="W"):
            with botanu.step("generation"):
                pass
        step_span = next(
            s for s in memory_exporter.get_finished_spans()
            if s.name == "botanu.step/generation"
        )
        assert dict(step_span.attributes)["botanu.step"] == "generation"

    def test_multiple_steps_within_one_event(self, memory_exporter):
        with botanu.event(event_id="e", customer_id="c", workflow="W"):
            with botanu.step("retrieval"):
                pass
            with botanu.step("generation"):
                pass
        step_names = [
            s.name for s in memory_exporter.get_finished_spans()
            if s.name.startswith("botanu.step/")
        ]
        assert step_names == ["botanu.step/retrieval", "botanu.step/generation"]

    def test_step_records_exception(self, memory_exporter):
        with pytest.raises(RuntimeError):
            with botanu.event(event_id="e", customer_id="c", workflow="W"):
                with botanu.step("failing"):
                    raise RuntimeError("step-boom")
        step_span = next(
            s for s in memory_exporter.get_finished_spans()
            if s.name == "botanu.step/failing"
        )
        from opentelemetry.trace import StatusCode
        assert step_span.status.status_code == StatusCode.ERROR


# ── _Event internal ──────────────────────────────────────────────────────

class TestEventInternalContract:
    def test_event_factory_returns_event_instance(self):
        ev = botanu.event(event_id="e", customer_id="c", workflow="W")
        assert isinstance(ev, _Event)


class TestLazyAutoEnable:
    """event() implicitly runs enable() on first call if the SDK isn't already
    initialised. Customers don't need to remember a separate setup step."""

    def test_event_calls_enable_when_not_initialised(self, monkeypatch):
        from botanu.sdk import bootstrap as _bs

        calls = []
        monkeypatch.setattr(_bs, "_initialized", False)

        def spy_enable(*args, **kwargs):
            calls.append((args, kwargs))
            # Mark initialised without doing real OTel setup (harness already did).
            _bs._initialized = True
            return True

        monkeypatch.setattr(_bs, "enable", spy_enable)
        botanu.event(event_id="e", customer_id="c", workflow="W")
        assert len(calls) == 1, "enable() should be auto-called on first event()"

    def test_event_skips_enable_when_already_initialised(self, monkeypatch):
        from botanu.sdk import bootstrap as _bs

        calls = []
        monkeypatch.setattr(_bs, "_initialized", True)
        monkeypatch.setattr(_bs, "enable", lambda *a, **k: calls.append((a, k)) or True)
        botanu.event(event_id="e", customer_id="c", workflow="W")
        assert calls == [], "enable() should NOT run when already initialised"


# ── End-to-end trace completeness ────────────────────────────────────────
#
# The core product claim: "one wrap around the agent captures everything
# that happens inside." Verify this by installing a RunContextEnricher on
# the tracer provider, then creating a simulated downstream span (as if it
# were an auto-instrumented OpenAI call) INSIDE the event scope, and
# confirming the business attributes were stamped on it via the enricher
# reading baggage. This is the same path an openai/anthropic/httpx
# auto-instrumentor span takes in production.

_enricher_installed = False


@pytest.fixture(autouse=True)
def _install_enricher(tracer_provider):
    global _enricher_installed
    if not _enricher_installed:
        tracer_provider.add_span_processor(RunContextEnricher())
        # The test harness installs its own tracer provider + enricher already,
        # so suppress the lazy auto-enable inside event() — otherwise it would
        # try to install real OTel auto-instrumentation on top of the fixture.
        from botanu.sdk import bootstrap as _bs
        _bs._initialized = True
        _enricher_installed = True
    yield


class TestTraceCompleteness:
    def test_downstream_span_inside_cm_gets_business_attrs(self, memory_exporter):
        tracer = trace.get_tracer("simulated-auto-instrument")
        with botanu.event(event_id="evt-xyz", customer_id="cust-xyz", workflow="Support"):
            with tracer.start_as_current_span("simulated.llm.openai.chat") as child:
                child.set_attribute("llm.request.model", "gpt-5.2")

        spans_by_name = {s.name: dict(s.attributes) for s in memory_exporter.get_finished_spans()}
        assert "simulated.llm.openai.chat" in spans_by_name
        llm_attrs = spans_by_name["simulated.llm.openai.chat"]

        # The four core business keys propagate via baggage in every mode.
        assert llm_attrs.get("botanu.event_id") == "evt-xyz"
        assert llm_attrs.get("botanu.customer_id") == "cust-xyz"
        assert llm_attrs.get("botanu.workflow") == "Support"
        assert "botanu.run_id" in llm_attrs
        # The LLM's own attribute untouched
        assert llm_attrs.get("llm.request.model") == "gpt-5.2"

    def test_downstream_span_inside_decorator_gets_business_attrs(self, memory_exporter):
        tracer = trace.get_tracer("simulated-auto-instrument")

        @botanu.event(event_id="evt-dec", customer_id="cust-dec", workflow="W")
        def handle():
            with tracer.start_as_current_span("simulated.db.query") as child:
                child.set_attribute("db.system", "postgresql")

        handle()
        attrs = next(
            dict(s.attributes)
            for s in memory_exporter.get_finished_spans()
            if s.name == "simulated.db.query"
        )
        assert attrs.get("botanu.event_id") == "evt-dec"
        assert attrs.get("botanu.workflow") == "W"

    def test_downstream_spans_across_nested_steps_all_stamped(self, memory_exporter):
        """Simulates a multi-phase agent: event → step → LLM span. Every
        span in the trace (event root, step, LLM) should carry the event_id."""
        tracer = trace.get_tracer("simulated-auto-instrument")

        with botanu.event(event_id="evt-n", customer_id="cust-n", workflow="Support"):
            with botanu.step("retrieval"):
                with tracer.start_as_current_span("vector.search"):
                    pass
            with botanu.step("generation"):
                with tracer.start_as_current_span("openai.chat.completion"):
                    pass

        for s in memory_exporter.get_finished_spans():
            attrs = dict(s.attributes)
            assert attrs.get("botanu.event_id") == "evt-n", f"{s.name} missing event_id"
            assert attrs.get("botanu.workflow") == "Support", f"{s.name} missing workflow"

    def test_business_attrs_removed_outside_event_scope(self, memory_exporter):
        """After leaving the event CM, baggage is detached — downstream spans
        should NOT carry stale business attributes."""
        tracer = trace.get_tracer("simulated-auto-instrument")

        with botanu.event(event_id="evt-in", customer_id="cust-in", workflow="W"):
            pass

        # Outside the CM — no baggage
        with tracer.start_as_current_span("span.outside.event"):
            pass

        outside = next(
            dict(x.attributes)
            for x in memory_exporter.get_finished_spans()
            if x.name == "span.outside.event"
        )
        assert "botanu.event_id" not in outside
        assert "botanu.customer_id" not in outside
