# Decorators API Reference

## @botanu_workflow

The primary decorator for creating workflow runs with automatic context propagation.

```python
from botanu import botanu_workflow

@botanu_workflow(
    name: str,
    *,
    event_id: Union[str, Callable[..., str]],
    customer_id: Union[str, Callable[..., str]],
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
    auto_outcome_on_success: bool = True,
    span_kind: SpanKind = SpanKind.SERVER,
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | Required | Workflow name (low cardinality, e.g. `"Customer Support"`) |
| `event_id` | `str \| Callable` | Required | Business transaction identifier (e.g. ticket ID). Can be a static string or a callable that receives the same `(*args, **kwargs)` as the decorated function. |
| `customer_id` | `str \| Callable` | Required | End-customer being served (e.g. org ID). Same static/callable rules as `event_id`. |
| `environment` | `str` | From env | Deployment environment |
| `tenant_id` | `str` | `None` | Tenant identifier for multi-tenant systems |
| `auto_outcome_on_success` | `bool` | `True` | Emit `"success"` outcome if no exception |
| `span_kind` | `SpanKind` | `SERVER` | OpenTelemetry span kind |

### Example

```python
from botanu import botanu_workflow

# Static values:
@botanu_workflow("my-workflow", event_id="evt-001", customer_id="cust-42")
def do_work():
    result = do_something()
    return result

# Dynamic values extracted from function arguments:
@botanu_workflow(
    "my-workflow",
    event_id=lambda request: request.event_id,
    customer_id=lambda request: request.customer_id,
)
async def handle_request(request):
    ...
```

### Span Attributes

| Attribute | Description |
|-----------|-------------|
| `botanu.run_id` | Generated UUIDv7 |
| `botanu.workflow` | `name` parameter |
| `botanu.event_id` | Resolved `event_id` |
| `botanu.customer_id` | Resolved `customer_id` |
| `botanu.environment` | Deployment environment |
| `botanu.tenant_id` | Tenant identifier (if provided) |

### Alias

`workflow` is an alias for `botanu_workflow`:

```python
from botanu import workflow

@workflow("my-workflow", event_id="evt-001", customer_id="cust-42")
def do_work():
    ...
```

---

## run_botanu

Context manager alternative to `@botanu_workflow` for cases where you cannot
use a decorator (dynamic workflows, scripts, runtime-determined names).

```python
from botanu import run_botanu

with run_botanu(
    name: str,
    *,
    event_id: str,
    customer_id: str,
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
    auto_outcome_on_success: bool = True,
    span_kind: SpanKind = SpanKind.SERVER,
) as run_ctx: RunContext
```

### Example

```python
from botanu import run_botanu, emit_outcome

with run_botanu("my-workflow", event_id="evt-001", customer_id="cust-42") as run:
    result = do_something()
    emit_outcome("success")
```

The yielded `RunContext` contains `run_id`, `workflow`, `event_id`, and other
metadata. Parameters are identical to `@botanu_workflow`.

## See Also

- [Quick Start](../getting-started/quickstart.md)
- [Run Context](../concepts/run-context.md)
