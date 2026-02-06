# Anti-Patterns

Common mistakes to avoid when using Botanu SDK.

## Run Design Anti-Patterns

### Creating Runs for Internal Operations

**Don't** create runs for internal functions:

```python
# BAD - Too many runs
@botanu_use_case("Fetch Context")  # Don't do this
async def fetch_context(ticket_id):
    return await db.query(...)

@botanu_use_case("Generate Response")  # Or this
async def generate_response(context):
    return await llm.complete(...)

@botanu_use_case("Customer Support")
async def handle_ticket(ticket_id):
    context = await fetch_context(ticket_id)
    response = await generate_response(context)
    return response
```

**Do** use a single run at the entry point:

```python
# GOOD - One run for the business outcome
@botanu_use_case("Customer Support")
async def handle_ticket(ticket_id):
    context = await fetch_context(ticket_id)  # Not decorated
    response = await generate_response(context)  # Not decorated
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
    return response
```

### Nesting @botanu_use_case Decorators

**Don't** nest use case decorators:

```python
# BAD - Nested runs create confusion
@botanu_use_case("Outer")
async def outer():
    await inner()  # Creates a second run

@botanu_use_case("Inner")  # Don't do this
async def inner():
    ...
```

**Do** use @botanu_use_case only at entry points:

```python
# GOOD - Only entry point is decorated
@botanu_use_case("Main Workflow")
async def main():
    await step_one()  # No decorator
    await step_two()  # No decorator
```

### Generic Use Case Names

**Don't** use vague names:

```python
# BAD - Meaningless in dashboards
@botanu_use_case("Process")
@botanu_use_case("Handle")
@botanu_use_case("Main")
@botanu_use_case("DoWork")
```

**Do** use descriptive business names:

```python
# GOOD - Clear in reports
@botanu_use_case("Customer Support")
@botanu_use_case("Invoice Processing")
@botanu_use_case("Lead Qualification")
@botanu_use_case("Document Analysis")
```

## Outcome Anti-Patterns

### Forgetting to Emit Outcomes

**Don't** leave runs without outcomes:

```python
# BAD - No outcome recorded
@botanu_use_case("Process Order")
async def process_order(order_id):
    result = await process(order_id)
    return result  # Where's the outcome?
```

**Do** always emit an outcome:

```python
# GOOD - Explicit outcome
@botanu_use_case("Process Order")
async def process_order(order_id):
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
@botanu_use_case("Batch Processing")
async def process_batch(items):
    for item in items:
        await process(item)
        emit_outcome("success", value_type="item_processed")  # Don't do this
```

**Do** emit one summary outcome:

```python
# GOOD - One outcome at the end
@botanu_use_case("Batch Processing")
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
    auto_instrument_packages=[],  # Why?
)
```

**Do** keep defaults or be selective:

```python
# GOOD - Default instrumentation
enable(service_name="my-service")

# Or selective
enable(
    service_name="my-service",
    auto_instrument_packages=["fastapi", "openai_v2", "sqlalchemy"],
)
```

## Context Propagation Anti-Patterns

### Losing Context in Async Code

**Don't** spawn tasks without context:

```python
# BAD - Context lost
@botanu_use_case("Parallel Processing")
async def process():
    # These tasks don't inherit context
    await asyncio.gather(
        task_one(),
        task_two(),
    )
```

**Do** ensure context propagates:

```python
# GOOD - Context flows through asyncio
@botanu_use_case("Parallel Processing")
async def process():
    # asyncio with contextvars works correctly
    await asyncio.gather(
        task_one(),  # Inherits context
        task_two(),  # Inherits context
    )
```

### Not Extracting Context in Consumers

**Don't** ignore incoming context:

```python
# BAD - Context not extracted
def process_message(message):
    # run_id from producer is lost
    handle_payload(message["payload"])
```

**Do** extract and use context:

```python
# GOOD - Context continues
def process_message(message):
    baggage = message.get("baggage", {})
    ctx = RunContext.from_baggage(baggage)
    if ctx:
        with ctx.as_current():
            handle_payload(message["payload"])
```

## Data Tracking Anti-Patterns

### Not Tracking Data Operations

**Don't** ignore database/storage costs:

```python
# BAD - Only LLM tracked
@botanu_use_case("Analysis")
async def analyze():
    data = await snowflake.query(expensive_query)  # Not tracked!
    with track_llm_call(...) as tracker:
        result = await llm.complete(data)
        tracker.set_tokens(...)
```

**Do** track all cost-generating operations:

```python
# GOOD - Complete cost picture
@botanu_use_case("Analysis")
async def analyze():
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
@botanu_use_case("Batch")
async def process_batch(items):
    for item in items:
        await process(item)  # If one fails, no outcome
    emit_outcome("success", value_amount=len(items))
```

**Do** track partial success:

```python
# GOOD - Partial success recorded
@botanu_use_case("Batch")
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
    await my_workflow()
```

**Do** use NoOp or in-memory exporters:

```python
# GOOD - Tests are isolated
from opentelemetry.trace import NoOpTracerProvider

def setup_test():
    trace.set_tracer_provider(NoOpTracerProvider())

def test_workflow():
    await my_workflow()  # No external calls
```

## See Also

- [Best Practices](best-practices.md) - What to do
- [Quickstart](../getting-started/quickstart.md) - Getting started guide
- [Outcomes](../tracking/outcomes.md) - Outcome recording details
