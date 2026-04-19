# Quickstart

Get event-level cost attribution working in 5 minutes.

## Prerequisites

- Python 3.9+
- A botanu API key (sign up at [botanu.ai](https://botanu.ai))

## Step 1: Install

```bash
pip install botanu
```

## Step 2: Set one environment variable

```bash
export BOTANU_API_KEY=<your-api-key>
```

That's it for the Botanu Cloud SaaS. The SDK auto-configures the OTLP
endpoint to `https://ingest.botanu.ai` and attaches your API key as a
bearer token.

### Alternative — self-hosted or local collector

If you run your own OTel collector, point at it explicitly:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=my-service
```

See [Collector](../integration/collector.md). Note: the SDK does not
attach your `BOTANU_API_KEY` to non-botanu endpoints — set
`OTEL_EXPORTER_OTLP_HEADERS` if your self-hosted collector needs auth.

## Step 3: Enable SDK

```python
from botanu import enable

enable()
```

Call `enable()` once at application startup. It reads configuration from environment variables — no hardcoded values needed.

> **Already using Datadog or another OTel APM?** `enable()` auto-detects
> your existing TracerProvider and adds botanu alongside without
> disturbing your sampling ratio or APM bill. See [Using botanu with an
> existing OTel / APM setup](../integration/existing-otel.md).

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
from botanu import enable, botanu_workflow

enable()

@botanu_workflow(
    "my-workflow",
    event_id=lambda req: req.event_id,
    customer_id=lambda req: req.customer_id,
)
async def handle_request(req):
    data = await fetch_data(req)
    return await process(data)
```

No `emit_outcome("success")` call is needed — event outcome is resolved
server-side from eval verdict / HITL / SoR. See [Outcomes](../tracking/outcomes.md).

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

- [Configuration](configuration.md) — environment variables and YAML config
- [Using botanu with existing OTel / Datadog](../integration/existing-otel.md) — brownfield detection + sampling preservation
- [Content Capture](../tracking/content-capture.md) — enabling prompt/response capture for eval
- [Outcomes](../tracking/outcomes.md) — how event outcome is resolved
- [Kubernetes Deployment](../integration/kubernetes.md) — zero-code instrumentation at scale
- [Context Propagation](../concepts/context-propagation.md) — how run_id flows across services
