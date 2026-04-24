# `event` and `step`

## `botanu.event(...)`

Primary integration point. Works as a [context manager](https://docs.python.org/3/library/contextlib.html), an [async context manager](https://docs.python.org/3/reference/datamodel.html#async-context-managers), or a decorator.

```python
def event(
    *,
    event_id: str | Callable,
    customer_id: str | Callable,
    workflow: str,
    environment: str | None = None,
    tenant_id: str | None = None,
    auto_outcome_on_success: bool = True,
    capture_input: bool | None = None,
    span_kind: SpanKind = SpanKind.SERVER,
) -> _Event
```

### Parameters

| Parameter | Description |
| --- | --- |
| `event_id` | Business event identifier — the join key for outcome correlation. String, or a callable taking the decorated function's args. In context-manager form must be a resolved string. |
| `customer_id` | Customer being served. String or callable with the same rules as `event_id`. |
| `workflow` | Workflow name (low cardinality). Required. |
| `environment` | Deployment environment override. Falls back to `BOTANU_ENVIRONMENT` or `OTEL_DEPLOYMENT_ENVIRONMENT`. |
| `tenant_id` | Tenant identifier for multi-tenant apps. |
| `auto_outcome_on_success` | Mark the run `SUCCESS` on clean exit. Default `True`. |
| `capture_input` | Force content capture on/off. `None` (default) uses the sampled `content_capture_rate`. |
| `span_kind` | [OTel span kind](https://opentelemetry.io/docs/specs/otel/trace/api/#spankind). Default `SERVER`. |

### Context manager

```python
import botanu

with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    agent.run(ticket)
```

### Async context manager

```python
async with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    await agent.arun(ticket)
```

### Decorator

Supports callables for `event_id` and `customer_id`:

```python
@botanu.event(
    workflow="Support",
    event_id=lambda ticket: ticket.id,
    customer_id=lambda ticket: ticket.user_id,
)
def handle_ticket(ticket):
    ...
```

Works for both sync and `async def` functions.

## `botanu.step(name)`

Context manager for multi-phase workflows. Nests inside an `event` scope and emits a span with `kind=INTERNAL`.

```python
with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    with botanu.step("retrieval"):
        docs = vector_db.query(ticket.query)
    with botanu.step("generation"):
        response = llm.complete(docs)
```

Each step stamps `botanu.step=<name>` on its span and propagates it via baggage.

## See also

- [Run Context](../concepts/run-context.md)
- [Context Propagation](../concepts/context-propagation.md)
- [Outcomes](../tracking/outcomes.md)
