# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Primary integration API: :func:`event` and :func:`step`.

``botanu.event(...)`` is the single integration point — works as a context
manager, an async context manager, or a decorator. It creates a run span
that:

- Generates a UUIDv7 run_id
- Emits ``run.started`` and ``run.completed`` events
- Propagates run context via W3C Baggage
- Stamps business attributes on every downstream span via the enricher
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generator, Optional, TypeVar, Union

from opentelemetry import baggage as otel_baggage
from opentelemetry import trace
from opentelemetry.context import attach, detach, get_current
from opentelemetry.trace import SpanKind, Status, StatusCode

from botanu.models.run_context import RunContext, RunStatus
from botanu.sdk.context import get_baggage

T = TypeVar("T")

tracer = trace.get_tracer("botanu_sdk")


def _compute_workflow_version(func: Callable[..., Any]) -> str:
    try:
        source = inspect.getsource(func)
        code_hash = hashlib.sha256(source.encode()).hexdigest()
        return f"v:{code_hash[:12]}"
    except (OSError, TypeError):
        return "v:unknown"


def _get_parent_run_id() -> Optional[str]:
    return get_baggage("botanu.run_id")


# ── Content capture ───────────────────────────────────────────────────────
#
# Gated by the same `content_capture_rate` config as LLMTracker so a single
# toggle controls both workflow-level and span-level capture. In-process PII
# scrubbing runs on the serialized payload before the attribute is written —
# see botanu/sdk/pii.py.

_CAPTURE_MAX_CHARS = 4096


def _should_capture_content() -> bool:
    """Single decision per event invocation — applied to both input + output
    so we never land a half-captured pair."""
    try:
        from botanu.sampling.content_sampler import should_capture_content
        from botanu.sdk.bootstrap import get_config

        cfg = get_config()
        rate = cfg.content_capture_rate if cfg else 0.0
        return should_capture_content(rate)
    except Exception:
        return False


def _serialize_for_capture(obj: Any) -> str:
    """Best-effort stringification. JSON first, repr fallback, truncated.

    PII scrub runs after serialization and before truncation so the regex
    sees the joined string (catches e.g. an email spanning dict values).
    """
    try:
        text = json.dumps(obj, default=repr, ensure_ascii=False)
    except Exception:
        try:
            text = repr(obj)
        except Exception:
            text = "<unserializable>"
    try:
        from botanu.sdk.bootstrap import get_config
        from botanu.sdk.pii import apply_scrub

        cfg = get_config()
        if cfg is not None:
            text = apply_scrub(text, cfg)
    except Exception:
        pass
    return text[:_CAPTURE_MAX_CHARS]


def _build_input_payload(
    func: Callable[..., Any], args: tuple, kwargs: dict
) -> dict[str, Any]:
    """Bind call args to parameter names. Falls back to positional if signature
    binding fails (unusual — reflective calls, C-extension wrappers)."""
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        return dict(bound.arguments)
    except Exception:
        return {"args": list(args), "kwargs": dict(kwargs)}


def _capture_input(span: trace.Span, func: Callable[..., Any], args: tuple, kwargs: dict) -> None:
    payload = _build_input_payload(func, args, kwargs)
    span.set_attribute("botanu.eval.input_content", _serialize_for_capture(payload))


def _capture_output(span: trace.Span, result: Any) -> None:
    span.set_attribute("botanu.eval.output_content", _serialize_for_capture(result))


def _emit_run_completed(
    span: trace.Span,
    run_ctx: RunContext,
    status: RunStatus,
    error_class: Optional[str] = None,
) -> None:
    duration_ms = (datetime.now(timezone.utc) - run_ctx.start_time).total_seconds() * 1000

    event_attrs: Dict[str, Union[str, float]] = {
        "run_id": run_ctx.run_id,
        "workflow": run_ctx.workflow,
        "status": status.value,
        "duration_ms": duration_ms,
    }
    if error_class:
        event_attrs["error_class"] = error_class
    if run_ctx.outcome and run_ctx.outcome.value_type:
        event_attrs["value_type"] = run_ctx.outcome.value_type
    if run_ctx.outcome and run_ctx.outcome.value_amount is not None:
        event_attrs["value_amount"] = run_ctx.outcome.value_amount

    span.add_event("botanu.run.completed", attributes=event_attrs)
    span.set_attribute("botanu.run.duration_ms", duration_ms)


# ── Unified primary API: botanu.event + botanu.step ──────────────────────
#
# One concept, three shapes (all equivalent):
#
#   with botanu.event(event_id=..., customer_id=..., workflow="..."):        ...
#   async with botanu.event(event_id=..., customer_id=..., workflow="..."):  ...
#   @botanu.event(event_id=lambda t: t.id, customer_id=..., workflow="...")  ...
#
# Capture of downstream LLM/HTTP/DB spans is done by enable()'s global OTel
# auto-instrumentation + the RunContextEnricher reading baggage — not by
# this class.


class _Event:
    """Dual-use: context manager (sync + async) and decorator.

    Customers construct via :func:`event`; they don't instantiate this
    directly. Re-entrancy is not supported on a single instance — each
    ``with`` / ``async with`` / ``@`` usage should get its own ``event(...)``
    call (which is the natural pattern).
    """

    def __init__(
        self,
        *,
        event_id: Union[str, Callable[..., str]],
        customer_id: Union[str, Callable[..., str]],
        workflow: str,
        environment: Optional[str] = None,
        tenant_id: Optional[str] = None,
        auto_outcome_on_success: bool = True,
        capture_input: Optional[bool] = None,
        span_kind: SpanKind = SpanKind.SERVER,
    ) -> None:
        if not workflow or not isinstance(workflow, str):
            raise ValueError("workflow is required and must be a non-empty string")
        if not callable(event_id):
            if not isinstance(event_id, str) or not event_id:
                raise ValueError("event_id must be a non-empty string or a callable")
        if not callable(customer_id):
            if not isinstance(customer_id, str) or not customer_id:
                raise ValueError("customer_id must be a non-empty string or a callable")

        self.event_id = event_id
        self.customer_id = customer_id
        self.workflow = workflow
        self.environment = environment
        self.tenant_id = tenant_id
        self.auto_outcome_on_success = auto_outcome_on_success
        self.capture_input = capture_input
        self.span_kind = span_kind

        self._span_cm: Any = None
        self._span: Optional[trace.Span] = None
        self._baggage_token: Any = None
        self._run_ctx: Optional[RunContext] = None

    def _begin(
        self,
        resolved_event_id: str,
        resolved_customer_id: str,
        workflow_version: Optional[str] = None,
    ):
        parent_run_id = _get_parent_run_id()
        run_ctx = RunContext.create(
            workflow=self.workflow,
            event_id=resolved_event_id,
            customer_id=resolved_customer_id,
            workflow_version=workflow_version,
            environment=self.environment,
            tenant_id=self.tenant_id,
            parent_run_id=parent_run_id,
        )
        span_cm = tracer.start_as_current_span(
            name=f"botanu.run/{self.workflow}",
            kind=self.span_kind,
        )
        span = span_cm.__enter__()
        for key, value in run_ctx.to_span_attributes().items():
            span.set_attribute(key, value)
        span.add_event(
            "botanu.run.started",
            attributes={"run_id": run_ctx.run_id, "workflow": run_ctx.workflow},
        )
        ctx = get_current()
        for key, value in run_ctx.to_baggage_dict().items():
            ctx = otel_baggage.set_baggage(key, value, context=ctx)
        baggage_token = attach(ctx)
        return span_cm, span, baggage_token, run_ctx

    def _end_success(self, span_cm, span, baggage_token, run_ctx) -> None:
        if self.auto_outcome_on_success:
            run_ctx.complete(RunStatus.SUCCESS)
        span.set_status(Status(StatusCode.OK))
        _emit_run_completed(span, run_ctx, RunStatus.SUCCESS)
        detach(baggage_token)
        span_cm.__exit__(None, None, None)

    def _end_failure(self, span_cm, span, baggage_token, run_ctx, exc) -> None:
        span.set_status(Status(StatusCode.ERROR, str(exc)))
        span.record_exception(exc)
        run_ctx.complete(RunStatus.FAILURE, error_class=exc.__class__.__name__)
        _emit_run_completed(
            span, run_ctx, RunStatus.FAILURE, error_class=exc.__class__.__name__,
        )
        detach(baggage_token)
        span_cm.__exit__(type(exc), exc, exc.__traceback__)

    def _resolve_capture(self) -> bool:
        if self.capture_input is True:
            return True
        if self.capture_input is False:
            return False
        return _should_capture_content()

    # ── Sync context manager ──
    def __enter__(self) -> RunContext:
        if callable(self.event_id) or callable(self.customer_id):
            raise TypeError(
                "botanu.event(...) with a callable event_id/customer_id must be "
                "used as a decorator, not as a context manager. "
                "Either pass resolved string values, or use @botanu.event(...)."
            )
        span_cm, span, token, run_ctx = self._begin(self.event_id, self.customer_id)
        self._span_cm = span_cm
        self._span = span
        self._baggage_token = token
        self._run_ctx = run_ctx
        return run_ctx

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        span_cm = self._span_cm
        span = self._span
        token = self._baggage_token
        run_ctx = self._run_ctx
        self._span_cm = self._span = self._baggage_token = self._run_ctx = None
        if exc_type is None:
            self._end_success(span_cm, span, token, run_ctx)
        else:
            self._end_failure(span_cm, span, token, run_ctx, exc_val)
        return False  # propagate exceptions

    # ── Async context manager ──
    async def __aenter__(self) -> RunContext:
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return self.__exit__(exc_type, exc_val, exc_tb)

    # ── Decorator ──
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        workflow_version = _compute_workflow_version(func)
        is_async = inspect.iscoroutinefunction(func)
        parent = self

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            eid = parent.event_id(*args, **kwargs) if callable(parent.event_id) else parent.event_id
            cid = parent.customer_id(*args, **kwargs) if callable(parent.customer_id) else parent.customer_id
            span_cm, span, token, run_ctx = parent._begin(eid, cid, workflow_version)
            capture = parent._resolve_capture()
            if capture:
                _capture_input(span, func, args, kwargs)
            try:
                result = await func(*args, **kwargs)
                if capture:
                    _capture_output(span, result)
                parent._end_success(span_cm, span, token, run_ctx)
                return result
            except Exception as exc:
                parent._end_failure(span_cm, span, token, run_ctx, exc)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            eid = parent.event_id(*args, **kwargs) if callable(parent.event_id) else parent.event_id
            cid = parent.customer_id(*args, **kwargs) if callable(parent.customer_id) else parent.customer_id
            span_cm, span, token, run_ctx = parent._begin(eid, cid, workflow_version)
            capture = parent._resolve_capture()
            if capture:
                _capture_input(span, func, args, kwargs)
            try:
                result = func(*args, **kwargs)
                if capture:
                    _capture_output(span, result)
                parent._end_success(span_cm, span, token, run_ctx)
                return result
            except Exception as exc:
                parent._end_failure(span_cm, span, token, run_ctx, exc)
                raise

        return async_wrapper if is_async else sync_wrapper  # type: ignore[return-value]


def _ensure_enabled() -> None:
    """Lazy-init the SDK on first ``event()`` call so customers don't have to
    remember a separate ``botanu.enable()``. Explicit ``enable(...)`` is still
    honoured — this is a no-op if already initialised."""
    from botanu.sdk.bootstrap import enable, is_enabled
    if not is_enabled():
        enable()


def event(
    *,
    event_id: Union[str, Callable[..., str]],
    customer_id: Union[str, Callable[..., str]],
    workflow: str,
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
    auto_outcome_on_success: bool = True,
    capture_input: Optional[bool] = None,
    span_kind: SpanKind = SpanKind.SERVER,
) -> _Event:
    """Mark a scope as a botanu business event — the primary integration point.

    Works as a context manager, an async context manager, or a decorator. All
    three forms capture the same LLM/HTTP/DB calls inside the scope and stamp
    ``event_id``, ``customer_id``, and ``workflow`` onto every captured span
    via W3C baggage.

    Args:
        event_id: Business event identifier — the primary join key for outcome
            correlation (SoR webhooks, HITL reviews, etc.). In decorator form
            can be a callable that receives the decorated function's args.
            In context manager form must be a resolved string.
        customer_id: End-customer being served. Same callable/string rules as
            *event_id*.
        workflow: Workflow name (low cardinality, e.g. ``"Customer Support"``).
        environment: Deployment environment.
        tenant_id: Tenant identifier.
        auto_outcome_on_success: Mark run complete with SUCCESS on clean exit.
        capture_input: Force content capture on/off. ``None`` (default) uses
            the sampled ``content_capture_rate`` from bootstrap config.
        span_kind: OpenTelemetry span kind (default: ``SERVER``).

    Examples::

        # Context manager — works anywhere (scripts, notebooks, wrapping agents)
        with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
            agent.run(ticket)

        # Async context manager
        async with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
            await agent.arun(ticket)

        # Decorator — sugar for production handlers (supports lambda extractors)
        @botanu.event(
            workflow="Support",
            event_id=lambda t: t.id,
            customer_id=lambda t: t.user_id,
        )
        def handle_ticket(ticket):
            ...

    .. note::
        ``enable()`` runs implicitly on the first ``event()`` call if the SDK
        hasn't been initialised yet. Call ``botanu.enable(...)`` explicitly
        only if you need to override config (custom endpoint, API key, etc.).
    """
    _ensure_enabled()
    return _Event(
        event_id=event_id,
        customer_id=customer_id,
        workflow=workflow,
        environment=environment,
        tenant_id=tenant_id,
        auto_outcome_on_success=auto_outcome_on_success,
        capture_input=capture_input,
        span_kind=span_kind,
    )


@contextmanager
def step(name: str) -> Generator[trace.Span, None, None]:
    """Mark a phase within a :func:`event` scope.

    Use nested inside ``with botanu.event(...)`` to break a multi-step workflow
    into phases (e.g., ``"retrieval"``, ``"generation"``, ``"validation"``).
    Each step emits its own span and propagates ``botanu.step=<name>`` via
    baggage so downstream spans inherit the step label.

    Args:
        name: Step name (low cardinality, stable across invocations).

    Yields:
        The step span.

    Example::

        with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
            with botanu.step("retrieval"):
                docs = vector_db.query(...)
            with botanu.step("generation"):
                response = llm.complete(docs)
    """
    with tracer.start_as_current_span(
        name=f"botanu.step/{name}",
        kind=SpanKind.INTERNAL,
    ) as span:
        span.set_attribute("botanu.step", name)
        ctx = get_current()
        ctx = otel_baggage.set_baggage("botanu.step", name, context=ctx)
        token = attach(ctx)
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
        finally:
            detach(token)
