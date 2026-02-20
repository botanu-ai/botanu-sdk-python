# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Decorators for automatic run span creation and context propagation.

The ``@botanu_workflow`` decorator is the primary integration point.
It creates a "run span" that:
- Generates a UUIDv7 run_id
- Emits ``run.started`` and ``run.completed`` events
- Propagates run context via W3C Baggage
- Records outcome at completion
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import inspect
from collections.abc import Mapping
from contextlib import asynccontextmanager, contextmanager
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


def botanu_workflow(
    name: str,
    *,
    event_id: Union[str, Callable[..., str]],
    customer_id: Union[str, Callable[..., str]],
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
        name: Workflow name (low cardinality, e.g. ``"Customer Support"``).
        event_id: Business unit of work (e.g. ticket ID). Required.
            Can be a static string or a callable that receives the same
            ``(*args, **kwargs)`` as the decorated function and returns a string.
        customer_id: End-customer being served (e.g. org ID). Required.
            Can be a static string or a callable (same signature as *event_id*).
        environment: Deployment environment.
        tenant_id: Tenant identifier for multi-tenant apps.
        auto_outcome_on_success: Emit ``"success"`` if no exception.
        span_kind: OpenTelemetry span kind (default: ``SERVER``).

    Examples::

        # Static values (known at decoration time):
        @botanu_workflow("Support", event_id="ticket-123", customer_id="acme-corp")
        async def handle_ticket(): ...

        # Dynamic values (extracted from function arguments at call time):
        @botanu_workflow(
            "Support",
            event_id=lambda request: request.workflow_id,
            customer_id=lambda request: request.customer_id,
        )
        async def handle_ticket(request: TicketRequest): ...
    """
    if isinstance(event_id, str) and not event_id:
        raise ValueError("event_id is required and must be a non-empty string")
    if isinstance(customer_id, str) and not customer_id:
        raise ValueError("customer_id is required and must be a non-empty string")
    if not callable(event_id) and not isinstance(event_id, str):
        raise ValueError("event_id must be a non-empty string or a callable")
    if not callable(customer_id) and not isinstance(customer_id, str):
        raise ValueError("customer_id must be a non-empty string or a callable")

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        workflow_version = _compute_workflow_version(func)
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            resolved_event_id = event_id(*args, **kwargs) if callable(event_id) else event_id
            resolved_customer_id = customer_id(*args, **kwargs) if callable(customer_id) else customer_id
            parent_run_id = _get_parent_run_id()
            run_ctx = RunContext.create(
                workflow=name,
                event_id=resolved_event_id,
                customer_id=resolved_customer_id,
                workflow_version=workflow_version,
                environment=environment,
                tenant_id=tenant_id,
                parent_run_id=parent_run_id,
            )

            with tracer.start_as_current_span(
                name=f"botanu.run/{name}",
                kind=span_kind,
            ) as span:
                for key, value in run_ctx.to_span_attributes().items():
                    span.set_attribute(key, value)

                span.add_event(
                    "botanu.run.started",
                    attributes={
                        "run_id": run_ctx.run_id,
                        "workflow": run_ctx.workflow,
                    },
                )

                ctx = get_current()
                for key, value in run_ctx.to_baggage_dict().items():
                    ctx = otel_baggage.set_baggage(key, value, context=ctx)
                baggage_token = attach(ctx)

                try:
                    result = await func(*args, **kwargs)

                    span_attrs = getattr(span, "attributes", None)
                    existing_outcome = (
                        span_attrs.get("botanu.outcome.status") if isinstance(span_attrs, Mapping) else None
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
                        span,
                        run_ctx,
                        RunStatus.FAILURE,
                        error_class=exc.__class__.__name__,
                    )
                    raise
                finally:
                    detach(baggage_token)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            resolved_event_id = event_id(*args, **kwargs) if callable(event_id) else event_id
            resolved_customer_id = customer_id(*args, **kwargs) if callable(customer_id) else customer_id
            parent_run_id = _get_parent_run_id()
            run_ctx = RunContext.create(
                workflow=name,
                event_id=resolved_event_id,
                customer_id=resolved_customer_id,
                workflow_version=workflow_version,
                environment=environment,
                tenant_id=tenant_id,
                parent_run_id=parent_run_id,
            )

            with tracer.start_as_current_span(
                name=f"botanu.run/{name}",
                kind=span_kind,
            ) as span:
                for key, value in run_ctx.to_span_attributes().items():
                    span.set_attribute(key, value)

                span.add_event(
                    "botanu.run.started",
                    attributes={
                        "run_id": run_ctx.run_id,
                        "workflow": run_ctx.workflow,
                    },
                )

                ctx = get_current()
                for key, value in run_ctx.to_baggage_dict().items():
                    ctx = otel_baggage.set_baggage(key, value, context=ctx)
                baggage_token = attach(ctx)

                try:
                    result = func(*args, **kwargs)

                    span_attrs = getattr(span, "attributes", None)
                    existing_outcome = (
                        span_attrs.get("botanu.outcome.status") if isinstance(span_attrs, Mapping) else None
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
                        span,
                        run_ctx,
                        RunStatus.FAILURE,
                        error_class=exc.__class__.__name__,
                    )
                    raise
                finally:
                    detach(baggage_token)

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

    span.set_attribute("botanu.outcome.status", status.value)
    span.set_attribute("botanu.run.duration_ms", duration_ms)


workflow = botanu_workflow


def botanu_outcome(
    success: Optional[str] = None,
    partial: Optional[str] = None,
    failed: Optional[str] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to automatically emit outcomes based on function result.

    This is a convenience decorator for sub-functions within a workflow.
    It does NOT create a new run — use ``@botanu_workflow`` for that.
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


@contextmanager
def run_botanu(
    name: str,
    *,
    event_id: str,
    customer_id: str,
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
    auto_outcome_on_success: bool = True,
    span_kind: SpanKind = SpanKind.SERVER,
) -> Generator[RunContext, None, None]:
    """Context manager to create a run span — non-decorator alternative to ``@botanu_workflow``.

    Use this when you can't decorate a function (dynamic workflows, simple scripts,
    or when the workflow name is determined at runtime).

    Args:
        name: Workflow name (low cardinality, e.g. ``"Customer Support"``).
        event_id: Business unit of work (e.g. ticket ID).
        customer_id: End-customer being served (e.g. org ID).
        environment: Deployment environment.
        tenant_id: Tenant identifier for multi-tenant apps.
        auto_outcome_on_success: Emit ``"success"`` if no exception.
        span_kind: OpenTelemetry span kind (default: ``SERVER``).

    Yields:
        RunContext with the generated run_id and metadata.

    Example::

        with run_botanu("Support", event_id="ticket-42", customer_id="acme") as run:
            result = call_llm(...)
            emit_outcome("success", value_type="tickets_resolved", value_amount=1)
    """
    parent_run_id = _get_parent_run_id()
    run_ctx = RunContext.create(
        workflow=name,
        event_id=event_id,
        customer_id=customer_id,
        environment=environment,
        tenant_id=tenant_id,
        parent_run_id=parent_run_id,
    )

    with tracer.start_as_current_span(
        name=f"botanu.run/{name}",
        kind=span_kind,
    ) as span:
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

        try:
            yield run_ctx

            span_attrs = getattr(span, "attributes", None)
            existing_outcome = (
                span_attrs.get("botanu.outcome.status")
                if isinstance(span_attrs, Mapping)
                else None
            )

            if existing_outcome is None and auto_outcome_on_success:
                run_ctx.complete(RunStatus.SUCCESS)

            span.set_status(Status(StatusCode.OK))
            _emit_run_completed(span, run_ctx, RunStatus.SUCCESS)

        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            run_ctx.complete(RunStatus.FAILURE, error_class=exc.__class__.__name__)
            _emit_run_completed(
                span, run_ctx, RunStatus.FAILURE, error_class=exc.__class__.__name__,
            )
            raise
        finally:
            detach(baggage_token)
