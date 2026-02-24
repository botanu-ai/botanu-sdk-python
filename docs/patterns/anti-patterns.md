# Anti-Patterns

Common mistakes to avoid when using Botanu SDK.

## Run Design Anti-Patterns

### Creating Runs for Internal Operations

**Don't** create runs for internal functions:

```python
# BAD - Too many runs
@botanu_workflow("fetch_data", event_id=event_id, customer_id=customer_id)  # Don't do this
async def fetch_data(event_id, customer_id):
    return await db.query(...)

@botanu_workflow("do_work", event_id=event_id, customer_id=customer_id)  # Or this
async def do_work(event_id, customer_id):
    return await llm.complete(...)

@botanu_workflow("handle_request", event_id=event_id, customer_id=customer_id)
async def handle_request(event_id, customer_id):
    data = await fetch_data(event_id, customer_id)
    result = await do_work(event_id, customer_id)
    return result
```

**Do** use a single run at the entry point:

```python
# GOOD - One run for the business outcome
@botanu_workflow("handle_request", event_id=event_id, customer_id=customer_id)
async def handle_request(event_id: str, customer_id: str):
    data = await fetch_data(event_id)  # Not decorated
    result = await do_work(data)  # Not decorated
    emit_outcome("success", value_type="requests_processed", value_amount=1)
    return result
```

### Nesting @botanu_workflow Decorators

**Don't** nest workflow decorators:

```python
# BAD - Nested runs create confusion
@botanu_workflow("outer", event_id=event_id, customer_id=customer_id)
async def outer():
    await inner()  # Creates a second run

@botanu_workflow("inner", event_id=event_id, customer_id=customer_id)  # Don't do this
async def inner():
    ...
```

**Do** use @botanu_workflow only at entry points:

```python
# GOOD - Only entry point is decorated
@botanu_workflow("main_flow", event_id=event_id, customer_id=customer_id)
async def main_flow():
    await step_one()  # No decorator
    await step_two()  # No decorator
```

### Generic Workflow Names

**Don't** use vague names:

```python
# BAD - Meaningless in dashboards
@botanu_workflow("process", event_id=event_id, customer_id=customer_id)
@botanu_workflow("handle", event_id=event_id, customer_id=customer_id)
@botanu_workflow("main", event_id=event_id, customer_id=customer_id)
@botanu_workflow("do_work", event_id=event_id, customer_id=customer_id)
```

**Do** use descriptive business names:

```python
# GOOD - Clear in reports
@botanu_workflow("support_resolution", event_id=event_id, customer_id=customer_id)
@botanu_workflow("invoice_processing", event_id=event_id, customer_id=customer_id)
@botanu_workflow("lead_scoring", event_id=event_id, customer_id=customer_id)
@botanu_workflow("document_analysis", event_id=event_id, customer_id=customer_id)
```

## Outcome Anti-Patterns

### Forgetting to Emit Outcomes

**Don't** leave runs without outcomes:

```python
# BAD - No outcome recorded
@botanu_workflow("process_order", event_id=order_id, customer_id=customer_id)
async def process_order(order_id, customer_id):
    result = await process(order_id)
    return result  # Where's the outcome?
```

**Do** always emit an outcome:

```python
# GOOD - Explicit outcome
@botanu_workflow("process_order", event_id=order_id, customer_id=customer_id)
async def process_order(order_id, customer_id):
    try:
        result = await process(order_id)
        emit_outcome("success", value_type="orders_processed", value_amount=1)
        return result
    except Exception as e:
        emit_outcome("failed", reason=type(e).__name__)
        raise
```

### Multiple Outcomes Per Run

**Don't** emit multiple outcomes:

```python
# BAD - Multiple outcomes are confusing
@botanu_workflow("batch_processing", event_id=batch_id, customer_id=customer_id)
async def process_batch(items):
    for item in items:
        await process(item)
        emit_outcome("success", value_type="item_processed")  # Don't do this
```

**Do** emit one summary outcome:

```python
# GOOD - One outcome at the end
@botanu_workflow("batch_processing", event_id=batch_id, customer_id=customer_id)
async def process_batch(items):
    processed = 0
    for item in items:
        await process(item)
        processed += 1
    emit_outcome("success", value_type="items_processed", value_amount=processed)
```

### Missing Failure Reasons

**Don't** emit failures without reasons:

```python
# BAD - No context for debugging
except Exception:
    emit_outcome("failed")  # Why did it fail?
    raise
```

**Do** include the failure reason:

```python
# GOOD - Reason helps debugging
except ValidationError:
    emit_outcome("failed", reason="validation_error")
    raise
except RateLimitError:
    emit_outcome("failed", reason="rate_limit_exceeded")
    raise
except Exception as e:
    emit_outcome("failed", reason=type(e).__name__)
    raise
```

## LLM Tracking Anti-Patterns

### Not Recording Tokens

**Don't** skip token recording:

```python
# BAD - No cost data
with track_llm_call(provider="openai", model="gpt-4"):
    response = await client.chat.completions.create(...)
    # Token usage not recorded
```

**Do** always record tokens:

```python
# GOOD - Tokens enable cost calculation
with track_llm_call(provider="openai", model="gpt-4") as tracker:
    response = await client.chat.completions.create(...)
    tracker.set_tokens(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
```

### Ignoring Cached Tokens

**Don't** forget cache tokens (they have different pricing):

```python
# BAD - Missing cache data
tracker.set_tokens(
    input_tokens=response.usage.prompt_tokens,
    output_tokens=response.usage.completion_tokens,
)
```

**Do** include cache breakdown:

```python
# GOOD - Full token breakdown
tracker.set_tokens(
    input_tokens=response.usage.prompt_tokens,
    output_tokens=response.usage.completion_tokens,
    cache_read_tokens=response.usage.cache_read_tokens,
    cache_write_tokens=response.usage.cache_write_tokens,
)
```

### Wrong Provider Names

**Don't** use inconsistent provider names:

```python
# BAD - Inconsistent naming
track_llm_call(provider="OpenAI", ...)     # Mixed case
track_llm_call(provider="open-ai", ...)    # Wrong format
track_llm_call(provider="gpt", ...)        # Model as provider
```

**Do** use standard provider names (auto-normalized):

```python
# GOOD - Standard names (or let SDK normalize)
track_llm_call(provider="openai", ...)
track_llm_call(provider="anthropic", ...)
track_llm_call(provider="azure_openai", ...)
```

## Configuration Anti-Patterns

### Sampling for Cost Attribution

### Hardcoding Configuration

**Don't** hardcode production values:

```python
# BAD - Hardcoded
enable(
    service_name="my-service",
    otlp_endpoint="http://prod-collector.internal:4318",
)
```

**Do** use environment variables:

```python
# GOOD - Environment-based
enable(service_name=os.environ["OTEL_SERVICE_NAME"])

# Or use YAML with interpolation
# botanu.yaml
# otlp:
#   endpoint: ${COLLECTOR_ENDPOINT}
```

### Disabling Auto-Instrumentation Unnecessarily

**Don't** disable auto-instrumentation without reason:

```python
# BAD - Missing automatic tracing
enable(
    service_name="my-service",
    auto_instrumentation=False,  # Why?
)
```

**Do** keep defaults or be selective:

```python
# GOOD - Default instrumentation (auto_instrumentation=True by default)
enable(service_name="my-service")
```

## Context Propagation Anti-Patterns

### Losing Context in Async Code

**Don't** spawn tasks without context:

```python
# BAD - Context lost
@botanu_workflow("parallel_work", event_id=event_id, customer_id=customer_id)
async def do_parallel_work():
    # These tasks don't inherit context
    await asyncio.gather(
        do_something(),
        do_something_else(),
    )
```

**Do** ensure context propagates:

```python
# GOOD - Context flows through asyncio
@botanu_workflow("parallel_work", event_id=event_id, customer_id=customer_id)
async def do_parallel_work():
    # asyncio with contextvars works correctly
    await asyncio.gather(
        do_something(),  # Inherits context
        do_something_else(),  # Inherits context
    )
```

### Not Extracting Context in Consumers

**Don't** ignore incoming context:

```python
# BAD - Context not extracted
def process_message(message):
    # run_id from producer is lost
    do_work(message["payload"])
```

**Do** extract and use context:

```python
# GOOD - Context continues
from botanu.sdk import set_baggage

def process_message(message):
    baggage = message.get("baggage", {})
    for key, value in baggage.items():
        set_baggage(key, value)
    do_work(message["payload"])
```

## Data Tracking Anti-Patterns

### Not Tracking Data Operations

**Don't** ignore database/storage costs:

```python
# BAD - Only LLM tracked
@botanu_workflow("analyze_data", event_id=event_id, customer_id=customer_id)
async def analyze_data():
    data = await snowflake.query(expensive_query)  # Not tracked!
    with track_llm_call(...) as tracker:
        result = await llm.complete(data)
        tracker.set_tokens(...)
```

**Do** track all cost-generating operations:

```python
# GOOD - Complete cost picture
@botanu_workflow("analyze_data", event_id=event_id, customer_id=customer_id)
async def analyze_data():
    with track_db_operation(system="snowflake", operation="SELECT") as db:
        data = await snowflake.query(expensive_query)
        db.set_bytes_scanned(data.bytes_scanned)

    with track_llm_call(...) as tracker:
        result = await llm.complete(data)
        tracker.set_tokens(...)
```

### Missing Bytes for Pay-Per-Scan

**Don't** forget bytes for warehouses:

```python
# BAD - Missing cost driver
with track_db_operation(system="bigquery", operation="SELECT") as db:
    result = await bq.query(sql)
    db.set_result(rows_returned=len(result))  # Rows don't determine cost!
```

**Do** include bytes scanned:

```python
# GOOD - Bytes scanned is the cost driver
with track_db_operation(system="bigquery", operation="SELECT") as db:
    result = await bq.query(sql)
    db.set_bytes_scanned(result.bytes_processed)
    db.set_result(rows_returned=len(result))
```

## Error Handling Anti-Patterns

### Swallowing Errors

**Don't** hide errors:

```python
# BAD - Error hidden
with track_llm_call(...) as tracker:
    try:
        response = await llm.complete(...)
    except Exception:
        pass  # Silently fails - no error recorded
```

**Do** record and propagate errors:

```python
# GOOD - Error tracked and raised
with track_llm_call(...) as tracker:
    try:
        response = await llm.complete(...)
    except Exception as e:
        tracker.set_error(e)
        emit_outcome("failed", reason=type(e).__name__)
        raise
```

### Ignoring Partial Successes

**Don't** mark all-or-nothing:

```python
# BAD - All items fail if one fails
@botanu_workflow("batch_work", event_id=batch_id, customer_id=customer_id)
async def process_batch(items):
    for item in items:
        await process(item)  # If one fails, no outcome
    emit_outcome("success", value_amount=len(items))
```

**Do** track partial success:

```python
# GOOD - Partial success recorded
@botanu_workflow("batch_work", event_id=batch_id, customer_id=customer_id)
async def process_batch(items):
    processed = 0
    failed = 0
    for item in items:
        try:
            await process(item)
            processed += 1
        except Exception:
            failed += 1

    if failed == 0:
        emit_outcome("success", value_type="items_processed", value_amount=processed)
    elif processed > 0:
        emit_outcome("partial", value_type="items_processed", value_amount=processed,
                     reason=f"failed_{failed}_of_{len(items)}")
    else:
        emit_outcome("failed", reason="all_items_failed")
```

## Testing Anti-Patterns

### Testing with Real Exporters

**Don't** send telemetry during tests:

```python
# BAD - Tests hit real collector
def test_workflow():
    enable(service_name="test")  # Sends to real endpoint!
    await do_work()
```

**Do** use NoOp or in-memory exporters:

```python
# GOOD - Tests are isolated
from opentelemetry.trace import NoOpTracerProvider

def setup_test():
    trace.set_tracer_provider(NoOpTracerProvider())

def test_workflow():
    await do_work()  # No external calls
```

## See Also

- [Best Practices](best-practices.md) - What to do
- [Quickstart](../getting-started/quickstart.md) - Getting started guide
- [Outcomes](../tracking/outcomes.md) - Outcome recording details
