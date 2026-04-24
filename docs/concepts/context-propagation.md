# Context Propagation

The SDK uses [W3C Baggage](https://www.w3.org/TR/baggage/) to carry business context across function calls, HTTP requests, message queues, and async workers.

## Keys

The `RunContextEnricher` stamps these seven keys on every span that starts inside an event scope, by reading them from [W3C Baggage](https://www.w3.org/TR/baggage/) on the active [OTel context](https://opentelemetry.io/docs/specs/otel/context/):

- `botanu.run_id`
- `botanu.workflow`
- `botanu.event_id`
- `botanu.customer_id`
- `botanu.environment`
- `botanu.tenant_id` (when set)
- `botanu.parent_run_id` (when nested inside a parent event)

Additional keys (`botanu.root_run_id`, `botanu.attempt`, `botanu.retry_of_run_id`, `botanu.deadline`, `botanu.cancelled`) ride in the baggage dict too when they have non-default values, so that `RunContext.from_baggage(...)` on the receiving side of cross-process propagation can reconstruct retry and deadline state.

## In-process

Context flows via Python [`contextvars`](https://docs.python.org/3/library/contextvars.html):

```python
import botanu

with botanu.event(event_id="ticket-42", customer_id="acme", workflow="Support"):
    fetch_from_db()
    call_llm()
    publish_result()
```

The `RunContextEnricher` span processor stamps the seven keys on every span that starts inside the scope, including auto-instrumented ones.

## HTTP

[OTel HTTP instrumentors](https://opentelemetry.io/docs/languages/python/instrumentation/) (requests, httpx, urllib3, aiohttp) propagate baggage automatically on outbound calls.

For inbound, add the middleware to your web framework:

```python
from fastapi import FastAPI
from botanu.sdk.middleware import BotanuMiddleware

app = FastAPI()
app.add_middleware(BotanuMiddleware)
```

## Message queues

Inject on the producer side:

```python
from botanu.sdk.context import get_baggage, get_run_id

message = {
    "payload": payload,
    "metadata": {
        "botanu.run_id": get_run_id(),
        "botanu.workflow": get_baggage("botanu.workflow"),
        "botanu.event_id": get_baggage("botanu.event_id"),
        "botanu.customer_id": get_baggage("botanu.customer_id"),
    },
}
```

Extract on the consumer side:

```python
import botanu
from botanu.models.run_context import RunContext

ctx = RunContext.from_baggage(message["metadata"])

with botanu.event(event_id=ctx.event_id, customer_id=ctx.customer_id, workflow=ctx.workflow):
    do_work(message["payload"])
```

## Debugging

```python
from botanu.sdk.context import get_baggage, get_run_id

print(get_run_id())
print(get_baggage("botanu.event_id"))
```

## See also

- [Run Context](run-context.md)
- [Architecture](architecture.md)
