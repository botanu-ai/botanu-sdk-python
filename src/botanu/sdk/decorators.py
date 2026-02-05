# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Decorators for automatic run span creation and context propagation.

The ``@botanu_use_case`` decorator is the primary integration point.
It creates a "run span" that:
- Generates a UUIDv7 run_id
- Emits ``run.started`` and ``run.completed`` events
- Propagates run context via W3C Baggage
- Records outcome at completion
"""

from __future__ import annotations

import functools
import hashlib
import inspect
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from botanu.models.run_context import RunContext, RunStatus
from botanu.sdk.context import get_baggage, set_baggage
from botanu.tracking.metrics import record_run_completed

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


def botanu_use_case(
    name: str,
    workflow: Optional[str] = None,
    *,
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
    auto_outcome_on_success: bool = True,
    span_kind: SpanKind = SpanKind.SERVER,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to create a run span with automatic context propagation.

    This is the primary integration point. It:

    1. Creates a UUIDv7 ``run_id`` (sortable, globally unique)
    2. Creates a ``botanu.run`` span as the root of the run
    3. Emits ``run.started`` event
    4. Propagates run context via W3C Baggage
    5. On completion: emits ``run.completed`` event with outcome

    Args:
        name: Use case name (low cardinality, e.g. ``"Customer Support"``).
        workflow: Workflow name (defaults to function qualified name).
        environment: Deployment environment.
        tenant_id: Tenant identifier for multi-tenant apps.
        auto_outcome_on_success: Emit ``"success"`` if no exception.
        span_kind: OpenTelemetry span kind (default: ``SERVER``).

    Example::

        @botanu_use_case("Customer Support")
        async def handle_ticket(ticket_id: str):
            result = await process_ticket(ticket_id)
            emit_outcome("success", value_type="tickets_resolved", value_amount=1)
            return result
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        workflow_name = workflow or func.__qualname__
        workflow_version = _compute_workflow_version(func)
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            parent_run_id = _get_parent_run_id()
            run_ctx = RunContext.create(
                use_case=name,
                workflow=workflow_name,
                workflow_version=workflow_version,
                environment=environment,
                tenant_id=tenant_id,
                parent_run_id=parent_run_id,
            )

            with tracer.start_as_current_span(
                name=f"botanu.run/{name}", kind=span_kind,
            ) as span:
                for key, value in run_ctx.to_span_attributes().items():
                    span.set_attribute(key, value)

                span.add_event(
                    "botanu.run.started",
                    attributes={
                        "run_id": run_ctx.run_id,
                        "use_case": run_ctx.use_case,
                        "workflow": workflow_name,
                    },
                )

                for key, value in run_ctx.to_baggage_dict().items():
                    set_baggage(key, value)

                try:
                    result = await func(*args, **kwargs)

                    span_attrs = getattr(span, "attributes", None)
                    existing_outcome = (
                        span_attrs.get("botanu.outcome.status") if span_attrs else None
                    )

                    if existing_outcome is None and auto_outcome_on_success:
                        run_ctx.complete(RunStatus.SUCCESS)

                    span.set_status(Status(StatusCode.OK))
                    _emit_run_completed(span, run_ctx, RunStatus.SUCCESS)
                    return result

                except Exception as exc:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.record_exception(exc)
                    run_ctx.complete(RunStatus.FAILURE, error_class=exc.__class__.__name__)
                    _emit_run_completed(
                        span, run_ctx, RunStatus.FAILURE, error_class=exc.__class__.__name__,
                    )
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            parent_run_id = _get_parent_run_id()
            run_ctx = RunContext.create(
                use_case=name,
                workflow=workflow_name,
                workflow_version=workflow_version,
                environment=environment,
                tenant_id=tenant_id,
                parent_run_id=parent_run_id,
            )

            with tracer.start_as_current_span(
                name=f"botanu.run/{name}", kind=span_kind,
            ) as span:
                for key, value in run_ctx.to_span_attributes().items():
                    span.set_attribute(key, value)

                span.add_event(
                    "botanu.run.started",
                    attributes={
                        "run_id": run_ctx.run_id,
                        "use_case": run_ctx.use_case,
                        "workflow": workflow_name,
                    },
                )

                for key, value in run_ctx.to_baggage_dict().items():
                    set_baggage(key, value)

                try:
                    result = func(*args, **kwargs)

                    span_attrs = getattr(span, "attributes", None)
                    existing_outcome = (
                        span_attrs.get("botanu.outcome.status") if span_attrs else None
                    )

                    if existing_outcome is None and auto_outcome_on_success:
                        run_ctx.complete(RunStatus.SUCCESS)

                    span.set_status(Status(StatusCode.OK))
                    _emit_run_completed(span, run_ctx, RunStatus.SUCCESS)
                    return result

                except Exception as exc:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.record_exception(exc)
                    run_ctx.complete(RunStatus.FAILURE, error_class=exc.__class__.__name__)
                    _emit_run_completed(
                        span, run_ctx, RunStatus.FAILURE, error_class=exc.__class__.__name__,
                    )
                    raise

        if is_async:
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _emit_run_completed(
    span: trace.Span,
    run_ctx: RunContext,
    status: RunStatus,
    error_class: Optional[str] = None,
) -> None:
    duration_ms = (datetime.now(timezone.utc) - run_ctx.start_time).total_seconds() * 1000

    event_attrs: Dict[str, Union[str, float]] = {
        "run_id": run_ctx.run_id,
        "use_case": run_ctx.use_case,
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

    span.set_attribute("botanu.outcome.status", status.value)
    span.set_attribute("botanu.run.duration_ms", duration_ms)

    record_run_completed(
        use_case=run_ctx.use_case,
        status=status.value,
        environment=run_ctx.environment,
        duration_ms=duration_ms,
        workflow=run_ctx.workflow,
    )


# Alias
use_case = botanu_use_case


def botanu_outcome(
    success: Optional[str] = None,
    partial: Optional[str] = None,
    failed: Optional[str] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to automatically emit outcomes based on function result.

    This is a convenience decorator for sub-functions within a use case.
    It does NOT create a new run — use ``@botanu_use_case`` for that.
    """
    from botanu.sdk.span_helpers import emit_outcome

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                result = await func(*args, **kwargs)
                span = trace.get_current_span()
                if not span.attributes or "botanu.outcome.status" not in span.attributes:
                    emit_outcome("success")
                return result
            except Exception as exc:
                emit_outcome("failed", reason=exc.__class__.__name__)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                result = func(*args, **kwargs)
                span = trace.get_current_span()
                if not span.attributes or "botanu.outcome.status" not in span.attributes:
                    emit_outcome("success")
                return result
            except Exception as exc:
                emit_outcome("failed", reason=exc.__class__.__name__)
                raise

        if is_async:
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator
