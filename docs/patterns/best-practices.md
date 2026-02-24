# Best Practices

Patterns for effective cost attribution with Botanu SDK.

## Run Design

### One Run Per Business Outcome

A run should represent a complete business transaction:

```python
# GOOD - One run for one business outcome
@botanu_workflow("process_order", event_id=order_id, customer_id=customer_id)
async def process_order(order_id: str, customer_id: str):
    data = await fetch_data(order_id)
    result = await do_work(data)
    emit_outcome("success", value_type="orders_processed", value_amount=1)
```

```python
# BAD - Multiple runs for one outcome
@botanu_workflow("fetch_data", event_id=event_id, customer_id=customer_id)
async def fetch_data(event_id: str, customer_id: str):
    ...

@botanu_workflow("do_work", event_id=event_id, customer_id=customer_id)  # Don't do this
async def do_work(event_id: str, customer_id: str):
    ...
```

### Use Descriptive Workflow Names

Workflow names appear in dashboards and queries. Choose names carefully:

```python
# GOOD - Clear, descriptive names
@botanu_workflow("support_resolution", event_id=event_id, customer_id=customer_id)
@botanu_workflow("document_analysis", event_id=event_id, customer_id=customer_id)
@botanu_workflow("lead_scoring", event_id=event_id, customer_id=customer_id)

# BAD - Generic or technical names
@botanu_workflow("handle", event_id=event_id, customer_id=customer_id)
@botanu_workflow("process", event_id=event_id, customer_id=customer_id)
@botanu_workflow("main", event_id=event_id, customer_id=customer_id)
```

## Outcome Recording

### Always Record Outcomes

Every run should have an explicit outcome:

```python
@botanu_workflow("process_data", event_id=data_id, customer_id=customer_id)
async def process_data(data_id: str, customer_id: str):
    try:
        result = await process(data_id)
        emit_outcome("success", value_type="records_processed", value_amount=result.count)
        return result
    except ValidationError:
        emit_outcome("failed", reason="validation_error")
        raise
    except TimeoutError:
        emit_outcome("failed", reason="timeout")
        raise
```

### Quantify Value When Possible

Include value amounts for better ROI analysis:

```python
# GOOD - Quantified outcomes
emit_outcome("success", value_type="items_sent", value_amount=50)
emit_outcome("success", value_type="revenue_generated", value_amount=1299.99)
emit_outcome("success", value_type="documents_processed", value_amount=10)

# LESS USEFUL - No quantity
emit_outcome("success")
```

### Use Consistent Value Types

Standardize your value types across the organization:

```python
# Define standard value types
class ValueTypes:
    ITEMS_PROCESSED = "items_processed"
    DOCUMENTS_ANALYZED = "documents_analyzed"
    LEADS_SCORED = "leads_scored"
    MESSAGES_SENT = "messages_sent"
    REVENUE_GENERATED = "revenue_generated"

# Use consistently
emit_outcome("success", value_type=ValueTypes.ITEMS_PROCESSED, value_amount=1)
```

### Include Reasons for Failures

Always explain why something failed:

```python
emit_outcome("failed", reason="rate_limit_exceeded")
emit_outcome("failed", reason="invalid_input")
emit_outcome("failed", reason="model_unavailable")
emit_outcome("failed", reason="context_too_long")
```

## LLM Tracking

### Always Record Token Usage

Tokens are the primary cost driver for LLMs:

```python
with track_llm_call(provider="openai", model="gpt-4") as tracker:
    response = await client.chat.completions.create(...)
    # Always set tokens
    tracker.set_tokens(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
```

### Record Provider Request IDs

Request IDs enable reconciliation with provider invoices:

```python
tracker.set_request_id(
    provider_request_id=response.id,  # From provider
    client_request_id=uuid.uuid4().hex,  # Your internal ID
)
```

### Track Retries

Record attempt numbers for accurate cost per success:

```python
for attempt in range(max_retries):
    with track_llm_call(provider="openai", model="gpt-4") as tracker:
        tracker.set_attempt(attempt + 1)
        try:
            response = await client.chat.completions.create(...)
            break
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff)
```

### Use Correct Operation Types

Specify the operation type for accurate categorization:

```python
from botanu.tracking.llm import track_llm_call, ModelOperation

# Chat completion
with track_llm_call(provider="openai", model="gpt-4", operation=ModelOperation.CHAT):
    ...

# Embeddings
with track_llm_call(provider="openai", model="text-embedding-3-small", operation=ModelOperation.EMBEDDINGS):
    ...
```

## Data Tracking

### Track All Cost-Generating Operations

Include databases, storage, and messaging:

```python
@botanu_workflow("run_pipeline", event_id=pipeline_id, customer_id=customer_id)
async def run_pipeline(pipeline_id: str, customer_id: str):
    # Track warehouse query (billed by bytes scanned)
    with track_db_operation(system="snowflake", operation="SELECT") as db:
        db.set_bytes_scanned(result.bytes_scanned)
        db.set_query_id(result.query_id)

    # Track storage operations (billed by requests + data)
    with track_storage_operation(system="s3", operation="PUT") as storage:
        storage.set_result(bytes_written=len(data))

    # Track messaging (billed by message count)
    with track_messaging_operation(system="sqs", operation="publish", destination="queue") as msg:
        msg.set_result(message_count=batch_size)
```

### Include Bytes for Pay-Per-Scan Services

For data warehouses billed by data scanned:

```python
with track_db_operation(system="bigquery", operation="SELECT") as db:
    result = await bq_client.query(sql)
    db.set_bytes_scanned(result.total_bytes_processed)
    db.set_result(rows_returned=result.num_rows)
```

## Context Propagation

### Use Middleware for Web Services

Extract context from incoming requests:

```python
from fastapi import FastAPI
from botanu.sdk.middleware import BotanuMiddleware

app = FastAPI()
app.add_middleware(BotanuMiddleware)
```

### Propagate Context in Message Queues

Inject and extract context manually for async messaging:

```python
from botanu.sdk import set_baggage, get_baggage

# Producer
def publish_message(payload):
    message = {
        "payload": payload,
        "baggage": {
            "botanu.workflow": get_baggage("botanu.workflow"),
            "botanu.event_id": get_baggage("botanu.event_id"),
            "botanu.customer_id": get_baggage("botanu.customer_id"),
        }
    }
    queue.publish(message)

# Consumer
def process_message(message):
    baggage = message.get("baggage", {})
    for key, value in baggage.items():
        set_baggage(key, value)
    do_work(message["payload"])
```

### Use Lean Mode for High-Traffic Systems

Default lean mode minimizes header overhead:

```python
# Lean mode: ~100 bytes of baggage
# Propagates: run_id, botanu.workflow

# Full mode: ~300 bytes of baggage
# Propagates: run_id, botanu.workflow, botanu.event_id, botanu.customer_id,
#             environment, tenant_id, parent_run_id
```

## Configuration

### Use Environment Variables in Production

Keep configuration out of code:

```bash
export OTEL_SERVICE_NAME=my-service
export OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318
export BOTANU_ENVIRONMENT=production
```

### Use YAML for Complex Configuration

For multi-environment setups:

```yaml
# config/production.yaml
service:
  name: ${OTEL_SERVICE_NAME}
  environment: production

otlp:
  endpoint: ${COLLECTOR_ENDPOINT}

propagation:
  mode: lean
```

## Multi-Tenant Systems

### Always Include Tenant ID

For accurate per-tenant cost attribution:

```python
@botanu_workflow("handle_request", event_id=request_id, customer_id=cust_id, tenant_id=request.tenant_id)
async def handle_request(request):
    ...
```

### Use Business Context

Add additional attribution dimensions via baggage:

```python
set_baggage("team", "engineering")
set_baggage("cost_center", "R&D")
set_baggage("region", "us-west-2")
```

## Error Handling

### Record Errors Explicitly

Don't lose error context:

```python
with track_llm_call(provider="openai", model="gpt-4") as tracker:
    try:
        response = await client.chat.completions.create(...)
    except openai.APIError as e:
        tracker.set_error(e)  # Records error type and message
        raise
```

### Emit Outcomes for Errors

Even failed runs should have outcomes:

```python
@botanu_workflow("process_data", event_id=data_id, customer_id=customer_id)
async def process_data(data_id: str, customer_id: str):
    try:
        await do_work(data_id)
        emit_outcome("success", value_type="items_processed", value_amount=1)
    except ValidationError:
        emit_outcome("failed", reason="validation_error")
        raise
    except Exception as e:
        emit_outcome("failed", reason=type(e).__name__)
        raise
```

## Performance

### Use Async Tracking

For async applications, ensure tracking is non-blocking:

```python
# The SDK uses span events, not separate API calls
# This is already non-blocking
with track_llm_call(provider="openai", model="gpt-4") as tracker:
    response = await do_something()
    tracker.set_tokens(...)  # Immediate, non-blocking
```

### Batch Database Tracking

For batch operations, track at batch level:

```python
# GOOD - Batch tracking
with track_db_operation(system="postgresql", operation="INSERT") as db:
    await cursor.executemany(insert_sql, batch_of_1000_rows)
    db.set_result(rows_affected=1000)

# LESS EFFICIENT - Per-row tracking
for row in batch_of_1000_rows:
    with track_db_operation(system="postgresql", operation="INSERT") as db:
        await cursor.execute(insert_sql, row)
        db.set_result(rows_affected=1)
```

## Testing

### Mock Tracing in Tests

Use the NoOp tracer for unit tests:

```python
from opentelemetry import trace
from opentelemetry.trace import NoOpTracerProvider

def setup_test_tracing():
    trace.set_tracer_provider(NoOpTracerProvider())
```

### Test Outcome Recording

Verify outcomes are emitted correctly:

```python
from unittest.mock import patch

def test_successful_outcome():
    with patch("botanu.sdk.span_helpers.emit_outcome") as mock_emit:
        result = await do_work("123")
        mock_emit.assert_called_with("success", value_type="items_processed", value_amount=1)
```

## See Also

- [Anti-Patterns](anti-patterns.md) - What to avoid
- [Architecture](../concepts/architecture.md) - SDK design principles
- [Configuration](../getting-started/configuration.md) - Configuration options
