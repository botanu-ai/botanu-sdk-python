# Run Context

The Run Context is the core concept in Botanu SDK. It represents a single business transaction or workflow execution that you want to track for cost attribution.

## What is a Run?

A **run** is a logical unit of work that produces a business outcome. Examples:

- Resolving a customer support ticket
- Processing a document
- Generating a report
- Handling a chatbot conversation

A single run may involve:
- Multiple LLM calls (possibly to different providers)
- Database queries
- Storage operations
- External API calls
- Message queue operations

## The run_id

Every run is identified by a unique `run_id` — a UUIDv7 that is:

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
    use_case="Customer Support",
    workflow="handle_ticket",
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
| `use_case` | Business use case name (e.g., "Customer Support") |
| `workflow` | Optional workflow/function name |
| `environment` | Deployment environment (production, staging, etc.) |
| `attempt` | Attempt number (1 for first, 2+ for retries) |
| `tenant_id` | Optional tenant identifier for multi-tenant systems |

## Creating Runs

### Using the Decorator (Recommended)

```python
from botanu import botanu_use_case

@botanu_use_case("Customer Support")
def handle_ticket(ticket_id: str):
    # RunContext is automatically created and propagated
    # All operations inside inherit the same run_id
    pass
```

### Manual Creation

```python
from botanu.models.run_context import RunContext

ctx = RunContext.create(
    use_case="Document Processing",
    workflow="extract_entities",
    tenant_id="acme-corp",
)

# Use ctx.to_baggage_dict() to propagate via HTTP headers
# Use ctx.to_span_attributes() to add to spans
```

## Retry Handling

When a run fails and is retried, use `create_retry()` to maintain lineage:

```python
original = RunContext.create(use_case="Process Order")

# First attempt fails...

retry = RunContext.create_retry(original)
print(retry.attempt)          # 2
print(retry.retry_of_run_id)  # Original run_id
print(retry.root_run_id)      # Same as original.run_id
print(retry.run_id)           # New unique ID
```

This enables:
- Tracking total attempts for a business operation
- Correlating retries back to the original request
- Calculating aggregate cost across all attempts

## Deadlines and Cancellation

RunContext supports deadline and cancellation tracking:

```python
ctx = RunContext.create(
    use_case="Long Running Task",
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

## Serialization

### To Baggage (for HTTP propagation)

```python
# Lean mode (default): only run_id and use_case
baggage = ctx.to_baggage_dict()
# {"botanu.run_id": "...", "botanu.use_case": "..."}

# Full mode: all fields
baggage = ctx.to_baggage_dict(lean_mode=False)
# Includes workflow, environment, tenant_id, etc.
```

### To Span Attributes

```python
attrs = ctx.to_span_attributes()
# {"botanu.run_id": "...", "botanu.use_case": "...", ...}
```

### From Baggage (receiving side)

```python
ctx = RunContext.from_baggage(baggage_dict)
if ctx is None:
    # Required fields missing, create new context
    ctx = RunContext.create(use_case="Unknown")
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BOTANU_ENVIRONMENT` | Default environment | `"production"` |
| `BOTANU_PROPAGATION_MODE` | `"lean"` or `"full"` | `"lean"` |

## Best Practices

1. **One run per business outcome**: Don't create runs for internal operations
2. **Use descriptive use_case names**: They appear in dashboards and queries
3. **Leverage tenant_id**: Essential for multi-tenant cost attribution
4. **Handle retries properly**: Always use `create_retry()` for retry attempts

## See Also

- [Context Propagation](context-propagation.md) - How context flows through your application
- [Outcomes](../tracking/outcomes.md) - Recording business outcomes
