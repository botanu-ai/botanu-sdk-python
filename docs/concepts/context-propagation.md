# Context Propagation

Context propagation ensures that the `run_id` and other metadata flow through your entire application -- across function calls, HTTP requests, message queues, and async workers.

## How It Works

Botanu uses **W3C Baggage** for context propagation, the same standard used by OpenTelemetry for distributed tracing.

```
+-----------------------------------------------------------------+
|  HTTP Request Headers                                           |
+-----------------------------------------------------------------+
|  traceparent: 00-{trace_id}-{span_id}-01                       |
|  baggage: botanu.run_id=019abc12...,botanu.workflow=process     |
+-----------------------------------------------------------------+
```

When you make an outbound HTTP request, the `botanu.run_id` travels in the `baggage` header alongside the trace context.

## Propagation Modes

### Full Mode (recommended)

Full mode is the durable direction — every cross-service call carries the
complete baggage needed to reconstruct run context downstream. The SDK
propagates exactly these seven keys (defined as `BAGGAGE_KEYS_FULL` in
[`src/botanu/processors/enricher.py`](../../src/botanu/processors/enricher.py)):

- `botanu.run_id`
- `botanu.workflow`
- `botanu.event_id`
- `botanu.customer_id`
- `botanu.environment`
- `botanu.tenant_id`
- `botanu.parent_run_id`

Enable it explicitly:

```bash
export BOTANU_PROPAGATION_MODE=full
```

```python
# Full mode baggage (~250 bytes, values-dependent)
baggage: botanu.run_id=019abc12-...,botanu.workflow=process,botanu.event_id=evt-001,botanu.customer_id=cust-456,botanu.environment=production,botanu.tenant_id=tnt-abc,botanu.parent_run_id=019abc11-...
```

Fields that live on `RunContext` but **not** in baggage — `root_run_id`,
`attempt`, `retry_of_run_id`, `deadline`, `cancelled` — are reconstructed
from local state, not carried on the wire. If you need them downstream,
propagate them yourself via your message envelope (see "Message Queue
Propagation" below).

### Lean Mode (deprecated — will be removed)

Lean mode propagates only the first four keys from the full list. It was
the default in early 0.x releases and is still accepted for backward
compatibility, but it is **deprecated** — full mode will become the only
mode in a future release. Do not build new services assuming lean mode.

## In-Process Propagation

Within a single process, context is propagated via Python's `contextvars`:

```python
from botanu import botanu_workflow

@botanu_workflow("process", event_id="evt-001", customer_id="cust-456")
def do_work():
    # Context is set here

    do_something()    # Inherits context
    do_more_work()    # Inherits context
    save_result()     # Inherits context
```

The `RunContextEnricher` span processor automatically reads baggage and writes to span attributes:

```python
class RunContextEnricher(SpanProcessor):
    def on_start(self, span, parent_context):
        for key in ["botanu.run_id", "botanu.workflow"]:
            value = baggage.get_baggage(key, parent_context)
            if value:
                span.set_attribute(key, value)
```

This ensures **every span** -- including auto-instrumented ones -- gets the `run_id`.

## HTTP Propagation

### Outbound Requests

When using instrumented HTTP clients (`requests`, `httpx`, `urllib3`), baggage is automatically propagated:

```python
import requests

@botanu_workflow("process", event_id="evt-001", customer_id="cust-456")
def do_work():
    # Baggage is automatically added to headers
    response = requests.get("https://api.example.com/data")
```

### Inbound Requests (Frameworks)

For web frameworks (`FastAPI`, `Flask`, `Django`), use the middleware to extract context:

```python
# FastAPI
from botanu.sdk.middleware import BotanuMiddleware

app = FastAPI()
app.add_middleware(BotanuMiddleware)

@app.post("/tasks")
def process(request: Request):
    # RunContext is extracted from incoming baggage
    # or created if not present
    pass
```

## Message Queue Propagation

For async messaging systems, you need to manually inject and extract context.

### Injecting Context (Producer)

```python
from botanu.sdk.context import get_run_id, get_baggage

def publish_message(queue, payload):
    run_id = get_run_id()

    message = {
        "payload": payload,
        "metadata": {
            "run_id": run_id,
            "workflow": get_baggage("botanu.workflow"),
            "event_id": get_baggage("botanu.event_id"),
            "customer_id": get_baggage("botanu.customer_id"),
        }
    }
    queue.publish(message)
```

### Extracting Context (Consumer)

```python
from botanu.models.run_context import RunContext
from botanu import run_botanu

def process_message(message):
    baggage = message.get("metadata", {})
    ctx = RunContext.from_baggage(baggage)

    if ctx:
        # Continue with existing context using context manager
        with run_botanu(
            ctx.workflow,
            event_id=ctx.event_id,
            customer_id=ctx.customer_id,
        ):
            do_work(message["payload"])
    else:
        # Create new context
        with run_botanu(
            "process_message",
            event_id="evt-fallback",
            customer_id="unknown",
        ):
            do_work(message["payload"])
```

## Cross-Service Propagation

```
+--------------+     HTTP      +--------------+     Kafka     +--------------+
|   Service A  | ------------> |   Service B  | ------------> |   Service C  |
|              |   baggage:    |              |   message     |              |
|  run_id=X    |   run_id=X    |  run_id=X    |   run_id=X    |  run_id=X    |
+--------------+               +--------------+               +--------------+
```

The same `run_id` flows through all services, enabling:
- End-to-end cost attribution
- Cross-service trace correlation
- Distributed debugging

## Baggage Size Limits

W3C Baggage has practical size limits (most intermediaries allow 8 KB, but
individual hops may clip earlier). Typical sizes for botanu baggage:

| Mode | Typical size | Notes |
| --- | --- | --- |
| Full (recommended) | ~250 bytes | 7 keys, well under any limit |
| Lean (deprecated) | ~120 bytes | 4 keys, historical only |

## Propagation and Auto-Instrumentation

The SDK works seamlessly with OTel auto-instrumentation:

```python
from botanu import enable

enable(
    service_name="my-service",
    auto_instrumentation=True,  # Enable auto-instrumentation
)
```

Auto-instrumented libraries will automatically propagate baggage:
- `requests`, `httpx`, `urllib3` (HTTP clients)
- `fastapi`, `flask`, `django` (Web frameworks)
- `celery` (Task queues)
- `grpc` (gRPC)

## Debugging Propagation

### Check Current Context

```python
from botanu.sdk.context import get_baggage, get_run_id

run_id = get_run_id()
print(f"Current run_id: {run_id}")

workflow = get_baggage("botanu.workflow")
print(f"Current workflow: {workflow}")
```

### Verify Header Propagation

```python
# In your HTTP client
import httpx

def debug_request():
    with httpx.Client() as client:
        response = client.get(
            "https://httpbin.org/headers",
        )
        print(response.json())
        # Check for 'baggage' header in response
```

## Common Issues

### Context Not Propagating

1. **Missing initialization**: Ensure `enable()` is called at startup
2. **Missing middleware**: Add `BotanuMiddleware` to your web framework
3. **Async context loss**: Use `contextvars`-aware async patterns

### Duplicate run_ids

1. **Multiple decorators**: Only use `@botanu_workflow` at the entry point
2. **Middleware + decorator**: Choose one, not both

## See Also

- [Run Context](run-context.md) - Understanding the RunContext model
- [Architecture](architecture.md) - Overall SDK architecture
