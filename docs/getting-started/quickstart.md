# Quickstart

Get event-level cost attribution working in 5 minutes.

## Prerequisites

- Python 3.9+
- OpenTelemetry Collector running (see [Collector Configuration](../integration/collector.md))

## Step 1: Install

```bash
pip install botanu
```

## Step 2: Set Environment Variables

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=my-service
```

Or in Docker / Kubernetes:

```yaml
environment:
  - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
  - OTEL_SERVICE_NAME=my-service
```

## Step 3: Enable SDK

```python
from botanu import enable

enable()
```

Call `enable()` once at application startup. It reads configuration from environment variables — no hardcoded values needed.

## Step 4: Define Entry Point

```python
from botanu import botanu_workflow

@botanu_workflow("my-workflow", event_id="evt-001", customer_id="cust-42")
async def do_work():
    data = await db.query(...)
    result = await llm.complete(data)
    return result
```

All LLM calls, database queries, and HTTP requests inside the function are automatically tracked with the same `run_id` tied to the `event_id`.

## Complete Example

**Entry service** (`entry/app.py`):

```python
from botanu import enable, botanu_workflow, emit_outcome

enable()

@botanu_workflow(
    "my-workflow",
    event_id=lambda req: req.event_id,
    customer_id=lambda req: req.customer_id,
)
async def handle_request(req):
    data = await fetch_data(req)
    result = await process(data)
    emit_outcome("success")
    return result
```

**Downstream service** (`intermediate/app.py`):

```python
from botanu import enable

enable()  # propagates run_id from incoming request — no decorator needed
```

## What Gets Tracked

| Attribute | Example | Description |
|-----------|---------|-------------|
| `botanu.run_id` | `019abc12-...` | Unique run identifier (UUIDv7) |
| `botanu.workflow` | `my-workflow` | Workflow name |
| `botanu.event_id` | `evt-001` | Business event identifier |
| `botanu.customer_id` | `cust-42` | Customer identifier |
| `gen_ai.usage.input_tokens` | `150` | LLM input tokens |
| `gen_ai.usage.output_tokens` | `200` | LLM output tokens |
| `db.system` | `postgresql` | Database system |

All spans across all services share the same `run_id`, enabling cost-per-event analytics.

## Next Steps

- [Configuration](configuration.md) - Environment variables and YAML config
- [Kubernetes Deployment](../integration/kubernetes.md) - Zero-code instrumentation at scale
- [Context Propagation](../concepts/context-propagation.md) - How run_id flows across services
