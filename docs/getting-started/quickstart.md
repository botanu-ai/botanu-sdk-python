# Quickstart

Get event-level cost attribution working in five minutes.

## Prerequisites

- Python 3.9 or newer
- A botanu API key from [app.botanu.ai](https://app.botanu.ai)

## 1. Install

```bash
pip install botanu
```

## 2. Set the API key

```bash
export BOTANU_API_KEY=<your-api-key>
```

The SDK auto-configures the OTLP endpoint to `https://ingest.botanu.ai` and sends the key as a bearer token.

Running your own collector instead? Point at it directly and skip the bearer header:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=my-service
```

## 3. Wrap your agent

```python
import botanu

with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    agent.run(ticket)
```

Every LLM call, HTTP call, and database query inside the block is captured and stamped with `event_id`, `customer_id`, and `workflow`.

## Decorator form

For long-lived handlers, a decorator reads cleaner:

```python
import botanu

@botanu.event(
    workflow="Support",
    event_id=lambda ticket: ticket.id,
    customer_id=lambda ticket: ticket.user_id,
)
def handle_ticket(ticket):
    return agent.run(ticket)
```

Works for both sync and `async def` functions.

## Multi-phase workflows

Break a multi-step event into phases with `step`:

```python
with botanu.event(event_id=ticket.id, customer_id=user.id, workflow="Support"):
    with botanu.step("retrieval"):
        docs = vector_db.query(ticket.query)
    with botanu.step("generation"):
        response = llm.complete(docs)
```

Each phase produces its own span and inherits the event's business context.

## What gets stamped on every span

| Attribute | Example |
| --- | --- |
| `botanu.run_id` | `019abc12-3f4d-7...` |
| `botanu.event_id` | `ticket-42` |
| `botanu.customer_id` | `acme-corp` |
| `botanu.workflow` | `Support` |
| `botanu.environment` | `production` |
| `gen_ai.usage.input_tokens` | `150` |
| `gen_ai.usage.output_tokens` | `200` |

All spans produced by auto-instrumentation (OpenAI, Anthropic, LangChain, httpx, SQLAlchemy, Redis, ~25 others) inherit these attributes automatically.

## Already using Datadog or another OTel APM?

The SDK detects existing `TracerProvider` setups and adds itself alongside without disturbing your sampling ratio. See [Coexisting with existing OTel / Datadog](../integration/existing-otel.md).

## Next

- [Configuration](configuration.md) — env vars, YAML, and advanced options
- [Concepts: Run Context](../concepts/run-context.md) — what `event_id` buys you
- [Outcomes](../tracking/outcomes.md) — how success/failure is resolved
- [Kubernetes Deployment](../integration/kubernetes.md)
