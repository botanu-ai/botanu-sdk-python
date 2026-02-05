# Quickstart

Get run-level cost attribution working in 5 minutes.

## Prerequisites

- Python 3.9+
- Botanu SDK installed (`pip install "botanu[sdk]"`)
- OpenTelemetry Collector running (see [Collector Configuration](../integration/collector.md))

## Step 1: Enable the SDK

At application startup, enable Botanu:

```python
from botanu import enable

enable(service_name="my-ai-service")
```

This:
- Configures OpenTelemetry with OTLP export
- Adds the `RunContextEnricher` span processor
- Enables W3C Baggage propagation

## Step 2: Define a Use Case

Wrap your entry point with `@botanu_use_case`:

```python
from botanu import botanu_use_case, emit_outcome

@botanu_use_case("Customer Support")
async def handle_support_ticket(ticket_id: str):
    # Your business logic here
    context = await fetch_ticket_context(ticket_id)
    response = await generate_response(context)
    await send_response(ticket_id, response)

    # Record the business outcome
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
    return response
```

Every operation inside this function (LLM calls, database queries, HTTP requests) will be automatically linked to the same `run_id`.

## Step 3: Track LLM Calls

For manual LLM tracking (when auto-instrumentation isn't available):

```python
from botanu.tracking.llm import track_llm_call

@botanu_use_case("Document Analysis")
async def analyze_document(doc_id: str):
    document = await fetch_document(doc_id)

    with track_llm_call(provider="openai", model="gpt-4") as tracker:
        response = await openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": document}]
        )
        tracker.set_tokens(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
        tracker.set_request_id(response.id)

    emit_outcome("success", value_type="documents_analyzed", value_amount=1)
    return response.choices[0].message.content
```

## Step 4: Track Data Operations

Track database and storage operations for complete cost visibility:

```python
from botanu.tracking.data import track_db_operation, track_storage_operation

@botanu_use_case("Data Pipeline")
async def process_data(job_id: str):
    # Track database reads
    with track_db_operation(system="postgresql", operation="SELECT") as db:
        rows = await fetch_records(job_id)
        db.set_result(rows_returned=len(rows))

    # Track storage writes
    with track_storage_operation(system="s3", operation="PUT") as storage:
        await upload_results(job_id, rows)
        storage.set_result(bytes_written=len(rows) * 1024)

    emit_outcome("success", value_type="jobs_processed", value_amount=1)
```

## Complete Example

```python
import asyncio
from botanu import enable, botanu_use_case, emit_outcome
from botanu.tracking.llm import track_llm_call
from botanu.tracking.data import track_db_operation

# Initialize at startup
enable(service_name="support-bot")

@botanu_use_case("Customer Support")
async def handle_ticket(ticket_id: str):
    """Process a customer support ticket."""

    # Fetch ticket from database (auto-tracked if using instrumented client)
    with track_db_operation(system="postgresql", operation="SELECT") as db:
        ticket = await db_client.fetch_ticket(ticket_id)
        db.set_result(rows_returned=1)

    # Generate response with LLM
    with track_llm_call(provider="openai", model="gpt-4") as llm:
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful support agent."},
                {"role": "user", "content": ticket.description}
            ]
        )
        llm.set_tokens(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    # Save response (auto-tracked)
    with track_db_operation(system="postgresql", operation="INSERT") as db:
        await db_client.save_response(ticket_id, response.choices[0].message.content)
        db.set_result(rows_affected=1)

    # Record business outcome
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)

    return response.choices[0].message.content

# Run
asyncio.run(handle_ticket("TICKET-123"))
```

## What Gets Tracked

After running, you'll have spans with:

| Attribute | Value | Description |
|-----------|-------|-------------|
| `botanu.run_id` | `019abc12-...` | Unique run identifier (UUIDv7) |
| `botanu.use_case` | `Customer Support` | Business use case |
| `botanu.outcome` | `success` | Outcome status |
| `gen_ai.usage.input_tokens` | `150` | LLM input tokens |
| `gen_ai.usage.output_tokens` | `200` | LLM output tokens |
| `gen_ai.provider.name` | `openai` | LLM provider |
| `db.system` | `postgresql` | Database system |

All spans share the same `run_id`, enabling:
- Total cost per business transaction
- Cost breakdown by component
- Cost-per-outcome analytics

## Next Steps

- [Configuration](configuration.md) - Environment variables and YAML config
- [LLM Tracking](../tracking/llm-tracking.md) - Detailed LLM instrumentation
- [Context Propagation](../concepts/context-propagation.md) - Cross-service tracing
