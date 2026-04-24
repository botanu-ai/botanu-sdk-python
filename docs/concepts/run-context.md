# Run Context

The run context is the data the SDK carries through one business event, connecting the root span, every auto-instrumented child span, and downstream services via [W3C Baggage](https://www.w3.org/TR/baggage/).

## Events and runs

- **Event**: one business transaction (resolving a ticket, processing an order). Identified by `event_id`.
- **Run**: one execution attempt within an event. Retries share `event_id`, get new `run_id`.
- **Outcome**: resolved server-side from SoR connectors, HITL reviews, or eval verdicts. The SDK does not set it.

## `run_id`

[UUIDv7](https://datatracker.ietf.org/doc/html/draft-ietf-uuidrev-rfc4122bis), generated per run. Time-sortable, globally unique.

## `RunContext`

Most code doesn't touch this directly. `botanu.event(...)` creates it:

```python
import botanu

with botanu.event(event_id="ticket-42", customer_id="acme", workflow="Support"):
    agent.run(ticket)
```

Decorator form:

```python
@botanu.event(workflow="Support", event_id=lambda t: t.id, customer_id=lambda t: t.user_id)
def handle_ticket(ticket):
    ...
```

### Fields

| Field | Description |
| --- | --- |
| `run_id` | This run (UUIDv7) |
| `root_run_id` | First attempt's `run_id` |
| `event_id` | Business event identifier |
| `customer_id` | Customer this event belongs to |
| `workflow` | Workflow name |
| `environment` | Deployment environment |
| `attempt` | 1 for first, 2+ for retries |
| `tenant_id` | Optional, for multi-tenant apps |
| `parent_run_id` | If nested inside a parent event |

### Manual creation

For custom propagation paths (message queues, cross-process handoffs):

```python
from botanu.models.run_context import RunContext

ctx = RunContext.create(workflow="Support", event_id="ticket-42", customer_id="acme")
baggage = ctx.to_baggage_dict()
```

## Retries

```python
retry = RunContext.create_retry(previous_ctx)

retry.attempt          # 2
retry.retry_of_run_id  # previous_ctx.run_id
retry.root_run_id      # previous_ctx.run_id
retry.run_id           # fresh UUIDv7
```

## Deadlines and cancellation

```python
ctx = RunContext.create(
    workflow="Support",
    event_id="ticket-42",
    customer_id="acme",
    deadline_seconds=30.0,
)

if ctx.is_past_deadline():
    raise TimeoutError

ctx.request_cancellation(reason="user")
if ctx.is_cancelled():
    ...
```

## Serialization

```python
ctx.to_baggage_dict()
ctx.to_span_attributes()
RunContext.from_baggage(baggage_dict)
```

`to_baggage_dict()` always includes `botanu.run_id`, `botanu.workflow`, `botanu.event_id`, `botanu.customer_id`, `botanu.environment`. It adds `tenant_id`, `parent_run_id`, `root_run_id`, `attempt`, `retry_of_run_id`, `deadline`, `cancelled` when those are set on the context.

The `RunContextEnricher` stamps the first seven of those on every downstream span. The remaining five (`root_run_id`, `attempt`, `retry_of_run_id`, `deadline`, `cancelled`) are included for `from_baggage()` to reconstruct retry and deadline state when context crosses a process boundary (e.g. a queue worker).

## See also

- [Context Propagation](context-propagation.md)
- [Outcomes](../tracking/outcomes.md)
- [event API reference](../api/event.md)
