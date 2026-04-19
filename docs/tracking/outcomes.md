# Outcomes

> **⚠️ DEPRECATED (2026-04-16):** The `status` argument on `emit_outcome()` no
> longer stamps `botanu.outcome.status` on the span. Customer-reported outcome
> was removed because it was trivially fakeable — a misconfigured or
> adversarial SDK could claim every event succeeded and skew cost-per-outcome.
>
> **What determines event outcome now:** botanu derives the outcome server-side
> from, in priority order:
>
> 1. A System-of-Record (SoR) connector (Zendesk, Stripe, your own webhook).
> 2. A human reviewer verdict from the HITL queue.
> 3. The evaluator's LLM-as-judge verdict rollup for the event's runs.
> 4. `pending` if nothing above fires yet.
>
> **What still works:** the other `emit_outcome(...)` fields (`reason`,
> `error_type`, `value_type`, `value_amount`, `confidence`, `metadata`) still
> stamp as *diagnostic* span attributes. They are useful for debugging and
> drill-down in the dashboard; they are not the authoritative outcome.
>
> Every call to `emit_outcome(status=...)` emits a `DeprecationWarning`.

## Overview

An **event** is one business transaction (a support ticket, an order, a report
generation). An event has one outcome that botanu determines from the signals
above. What you can do from the SDK is enrich the event with diagnostic
context — a reason string, an error classification, a value figure for
cost-per-value math, or arbitrary metadata.

**Hierarchy refresher:**

- **Event** — one business unit of work (has an `event_id`). Outcome lives here.
- **Run** — one execution attempt for an event. Retries replace the previous
  attempt; see [Run Context](../concepts/run-context.md).
- **Span** — one LLM/DB/tool call within a run.

## The diagnostic helpers

`emit_outcome` is now a thin helper that writes a fixed set of diagnostic
attributes onto the current span. Everything except `status` still stamps.

```python
from botanu import botanu_workflow, emit_outcome

@botanu_workflow("fulfill-order", event_id=order.id, customer_id=customer.id)
async def process_order(order):
    result = await do_work(order)

    # Diagnostic fields — useful for dashboard drill-down and cost-per-value
    # math, but not the authoritative outcome.
    emit_outcome(
        "success",                      # accepted for back-compat, DeprecationWarning
        value_type="orders_fulfilled",
        value_amount=1,
        metadata={"sku_count": len(order.items)},
    )
    return result
```

If you do not need any of the diagnostic fields, you can drop `emit_outcome`
entirely. `@botanu_workflow` already creates the run and span — outcome will
be filled in server-side from the signals above.

## emit_outcome() reference

```python
emit_outcome(
    status: str,                    # Required for validation; does NOT stamp the outcome.
    *,
    value_type: str | None = None,  # Free-form business-value label.
    value_amount: float | None = None,
    confidence: float | None = None, # 0.0–1.0
    reason: str | None = None,       # Free-form; especially for failures.
    error_type: str | None = None,   # Exception/classification name.
    metadata: dict | None = None,    # Arbitrary diagnostic kv.
)
```

### status (required but diagnostic-only)

`status` is still validated against the set below. It is accepted for
backward compatibility and its value is not written to the span.

| Value | Intended meaning |
| --- | --- |
| `success` | Event produced the intended result |
| `partial` | Event produced some of the intended result |
| `failed` | Event did not produce a result |
| `timeout` | Event did not finish in its deadline |
| `canceled` | Event was canceled by user or system |
| `abandoned` | Event was abandoned without completion |

A value outside this set raises `ValueError`. `"failure"` is not valid — use
`"failed"`.

### Other fields

Everything below stamps as a `botanu.outcome.*` diagnostic attribute:

```python
emit_outcome("success", value_type="tickets_resolved", value_amount=1)
emit_outcome("success", value_type="revenue_generated", value_amount=1299.99)
emit_outcome("success", value_type="classifications_completed",
             value_amount=1, confidence=0.92)
emit_outcome("failed", reason="upstream_unavailable", error_type="ServiceUnavailable")
emit_outcome("timeout", reason="model_took_too_long", error_type="DeadlineExceeded")
emit_outcome("partial", reason="processed_3_of_5", value_amount=3)
emit_outcome("success", value_type="items_processed", value_amount=10,
             metadata={"batch_id": "abc-123", "retry_count": 2})
```

## Span attributes that are still emitted

| Attribute | Description |
| --- | --- |
| `botanu.outcome.value_type` | What was achieved (free-form label) |
| `botanu.outcome.value_amount` | Quantified value |
| `botanu.outcome.confidence` | Confidence score (0.0–1.0) |
| `botanu.outcome.reason` | Reason string (especially for failures) |
| `botanu.outcome.error_type` | Error classification |
| `botanu.outcome.metadata.*` | Flattened metadata dict |

> `botanu.outcome.status` is **not** emitted. Dashboards that read from
> `runs.outcome_status` are reading a legacy physical column kept only for
> backward compatibility; the authoritative field is `events.final_outcome`,
> which is written by the platform, not the SDK.

## Automatic outcome (convenience)

`@botanu_workflow(..., auto_outcome_on_success=True)` (default) automatically
calls `emit_outcome("success")` at the end of a successful call, and
`emit_outcome("failed", reason=type(exc).__name__)` on exception. Since
`status` no longer stamps the outcome, this is pure convenience — it still
writes `reason` and `error_type` for failures, which is useful diagnostic
context.

Disable if you prefer explicit calls:

```python
@botanu_workflow("my-workflow", event_id=event_id, customer_id=customer_id,
                 auto_outcome_on_success=False)
async def my_function():
    result = await do_work()
    emit_outcome("success", value_type="items", value_amount=1)
    return result
```

## Context manager form

When you can't use the decorator:

```python
from botanu import run_botanu, emit_outcome

async def my_function(event_id: str, customer_id: str):
    async with run_botanu("my-workflow", event_id=event_id, customer_id=customer_id):
        result = await do_work()
        emit_outcome("success", value_type="items_processed",
                     value_amount=result.count)
        return result
```

## Cost-per-outcome math

Cost-per-outcome is computed by the platform from:

- the `runs.cost_total_usd` column populated by the cost engine, and
- the `events.final_outcome` column populated by the outcome resolver.

You don't query these yourself — open the dashboard. What you *can* do from
the SDK is annotate with `value_type` / `value_amount` so a business-value
column appears alongside cost-per-outcome in the dashboard.

## See also

- [Run Context](../concepts/run-context.md) — the event/run/span hierarchy
- [LLM Tracking](llm-tracking.md) — per-call attribution
- [Content Capture](content-capture.md) — capturing prompts/responses for eval
- [Best Practices](../patterns/best-practices.md)
