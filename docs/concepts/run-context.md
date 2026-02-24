# Run Context

The Run Context is the core concept in Botanu SDK. It represents a single execution attempt of a business event that you want to track for cost attribution.

## Events and Runs

An **event** is one business transaction -- a logical unit of work that produces a business outcome. Examples:

- Processing an incoming request
- Handling a scheduled job
- Executing a pipeline step
- Responding to a webhook

A **run** is one execution attempt within an event. Each retry of the same event gets a new `run_id` but shares the same `event_id`. A single run may involve:

- Multiple LLM calls (possibly to different providers)
- Database queries
- Storage operations
- External API calls
- Message queue operations

An event will have an **outcome** -- the business result of the work (success, failure, partial, etc.).

## The run_id

Every run is identified by a unique `run_id` -- a UUIDv7 that is:

- **Time-sortable**: IDs generated later sort after earlier ones
- **Globally unique**: No collisions across services
- **Propagated automatically**: Flows through your entire application via W3C Baggage

```python
from botanu.models.run_context import generate_run_id

run_id = generate_run_id()
# "019abc12-def3-7890-abcd-1234567890ab"
```

## RunContext Model

The `RunContext` dataclass holds all metadata for a run:

```python
from botanu.models.run_context import RunContext

ctx = RunContext.create(
    workflow="process",
    event_id="evt-001",
    customer_id="cust-456",
    environment="production",
    tenant_id="tenant-123",
)

print(ctx.run_id)       # "019abc12-def3-7890-..."
print(ctx.root_run_id)  # Same as run_id for top-level runs
print(ctx.attempt)      # 1 (first attempt)
```

### Key Fields

| Field | Description |
|-------|-------------|
| `run_id` | Unique identifier for this run (UUIDv7) |
| `root_run_id` | ID of the original run (for retries, same as `run_id` for first attempt) |
| `event_id` | Identifier for the business event (same across retries) |
| `customer_id` | Identifier for the customer this event belongs to |
| `workflow` | Workflow/function name |
| `environment` | Deployment environment (production, staging, etc.) |
| `attempt` | Attempt number (1 for first, 2+ for retries) |
| `tenant_id` | Optional tenant identifier for multi-tenant systems |

## Creating Runs

### Using the Decorator (Recommended)

```python
from botanu import botanu_workflow

@botanu_workflow("process", event_id="evt-001", customer_id="cust-456")
def do_work():
    # RunContext is automatically created and propagated
    # All operations inside inherit the same run_id
    pass
```

The `workflow` alias also works:

```python
from botanu import workflow

@workflow("process", event_id="evt-001", customer_id="cust-456")
def do_work():
    pass
```

### Using the Context Manager

```python
from botanu import run_botanu

def do_work():
    with run_botanu("process", event_id="evt-001", customer_id="cust-456"):
        # RunContext is active within this block
        pass
```

### Manual Creation

```python
from botanu.models.run_context import RunContext

ctx = RunContext.create(
    workflow="process",
    event_id="evt-001",
    customer_id="cust-456",
    tenant_id="acme-corp",
)

# Use ctx.to_baggage_dict() to propagate via HTTP headers
# Use ctx.to_span_attributes() to add to spans
```

## Retry Handling

When a run fails and is retried, use `create_retry()` to maintain lineage:

```python
previous = RunContext.create(
    workflow="process",
    event_id="evt-001",
    customer_id="cust-456",
)

# First attempt fails...

retry = RunContext.create_retry(previous)
print(retry.attempt)          # 2
print(retry.retry_of_run_id)  # Previous run_id
print(retry.root_run_id)      # Same as previous.run_id
print(retry.run_id)           # New unique ID
```

This enables:
- Tracking total attempts for a business event
- Correlating retries back to the previous request
- Calculating aggregate cost across all attempts

## Deadlines and Cancellation

RunContext supports deadline and cancellation tracking:

```python
ctx = RunContext.create(
    workflow="process",
    event_id="evt-001",
    customer_id="cust-456",
    deadline_seconds=30.0,  # 30 second deadline
)

# Check deadline
if ctx.is_past_deadline():
    raise TimeoutError("Deadline exceeded")

# Check remaining time
remaining = ctx.remaining_time_seconds()

# Request cancellation
ctx.request_cancellation(reason="user")
if ctx.is_cancelled():
    # Clean up and exit
    pass
```

## Outcomes

Record the business outcome of a run using `emit_outcome`:

```python
from botanu import emit_outcome
from botanu.models.run_context import RunStatus

emit_outcome(
    RunStatus.SUCCESS,
    value_type="task_completed",
    value_amount=1.0,
    confidence=0.95,
    reason="Completed successfully",
)
```

`RunStatus` values: `SUCCESS`, `FAILURE`, `PARTIAL`, `TIMEOUT`, `CANCELED`.

`emit_outcome` accepts these keyword arguments: `value_type`, `value_amount`, `confidence`, `reason`, `error_type`, `metadata`.

## Serialization

### To Baggage (for HTTP propagation)

```python
# Lean mode (default): essential fields
baggage = ctx.to_baggage_dict()
# {"botanu.run_id": "...", "botanu.workflow": "...", "botanu.event_id": "...", "botanu.customer_id": "..."}

# Full mode: all fields
baggage = ctx.to_baggage_dict(lean_mode=False)
# Adds: botanu.environment, botanu.tenant_id, botanu.parent_run_id, botanu.root_run_id,
#        botanu.attempt, botanu.retry_of_run_id, botanu.deadline, botanu.cancelled
```

### To Span Attributes

```python
attrs = ctx.to_span_attributes()
# {"botanu.run_id": "...", "botanu.workflow": "...", ...}
```

### From Baggage (receiving side)

```python
ctx = RunContext.from_baggage(baggage_dict)
if ctx is None:
    # Required fields missing, create new context
    ctx = RunContext.create(workflow="unknown", event_id="evt-fallback", customer_id="unknown")
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BOTANU_ENVIRONMENT` | Default environment | `"production"` |
| `BOTANU_PROPAGATION_MODE` | `"lean"` or `"full"` | `"lean"` |

## Best Practices

1. **One event per business outcome**: Don't create events for internal operations
2. **Use descriptive workflow names**: They appear in dashboards and queries
3. **Leverage tenant_id**: Essential for multi-tenant cost attribution
4. **Handle retries properly**: Always use `create_retry()` for retry attempts
5. **Always provide event_id and customer_id**: They are required for proper cost attribution

## See Also

- [Context Propagation](context-propagation.md) - How context flows through your application
- [Outcomes](../tracking/outcomes.md) - Recording business outcomes
