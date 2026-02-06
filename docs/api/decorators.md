# Decorators API Reference

## @botanu_use_case

The primary decorator for creating runs with automatic context propagation.

```python
from botanu import botanu_use_case

@botanu_use_case(
    name: str,
    workflow: Optional[str] = None,
    *,
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
    auto_outcome_on_success: bool = True,
    span_kind: SpanKind = SpanKind.SERVER,
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | Required | Use case name (e.g., "Customer Support"). Low cardinality for grouping. |
| `workflow` | `str` | Function name | Workflow identifier. Defaults to the decorated function's qualified name. |
| `environment` | `str` | From env | Deployment environment (production, staging, etc.). |
| `tenant_id` | `str` | `None` | Tenant identifier for multi-tenant systems. |
| `auto_outcome_on_success` | `bool` | `True` | Automatically emit "success" outcome if function completes without exception. |
| `span_kind` | `SpanKind` | `SERVER` | OpenTelemetry span kind. |

### Behavior

1. **Generates UUIDv7 `run_id`** - Sortable, globally unique identifier
2. **Creates root span** - Named `botanu.run/{name}`
3. **Emits events** - `botanu.run.started` and `botanu.run.completed`
4. **Sets baggage** - Propagates context via W3C Baggage
5. **Records outcome** - On completion or exception

### Examples

#### Basic Usage

```python
@botanu_use_case("Customer Support")
async def handle_ticket(ticket_id: str):
    result = await process_ticket(ticket_id)
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
    return result
```

#### With All Parameters

```python
@botanu_use_case(
    name="Document Processing",
    workflow="pdf_extraction",
    environment="production",
    tenant_id="acme-corp",
    auto_outcome_on_success=False,
    span_kind=SpanKind.CONSUMER,
)
async def process_document(doc_id: str):
    ...
```

#### Sync Functions

```python
@botanu_use_case("Batch Processing")
def process_batch(batch_id: str):
    # Works with sync functions too
    return process_items(batch_id)
```

### Span Attributes

The decorator sets these span attributes:

| Attribute | Source |
|-----------|--------|
| `botanu.run_id` | Generated UUIDv7 |
| `botanu.use_case` | `name` parameter |
| `botanu.workflow` | `workflow` parameter or function name |
| `botanu.workflow_version` | SHA256 hash of function source |
| `botanu.environment` | `environment` parameter or env var |
| `botanu.tenant_id` | `tenant_id` parameter (if provided) |
| `botanu.parent_run_id` | Parent run ID (if nested) |

### Alias

`use_case` is an alias for `botanu_use_case`:

```python
from botanu import use_case

@use_case("My Use Case")
async def my_function():
    ...
```

---

## @botanu_outcome

Convenience decorator for sub-functions to emit outcomes based on success/failure.

```python
from botanu import botanu_outcome

@botanu_outcome(
    success: Optional[str] = None,
    partial: Optional[str] = None,
    failed: Optional[str] = None,
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `success` | `str` | `None` | Custom label for success outcome (reserved for future use). |
| `partial` | `str` | `None` | Custom label for partial outcome (reserved for future use). |
| `failed` | `str` | `None` | Custom label for failed outcome (reserved for future use). |

### Behavior

- **Does NOT create a new run** - Works within an existing run
- **Emits "success"** if function completes without exception
- **Emits "failed"** with exception class name if exception raised
- **Skips emission** if outcome already set on current span

### Example

```python
from botanu import botanu_use_case, botanu_outcome

@botanu_use_case("Data Pipeline")
async def run_pipeline():
    await extract_data()
    await transform_data()
    await load_data()

@botanu_outcome()
async def extract_data():
    # Emits "success" on completion
    return await fetch_from_source()

@botanu_outcome()
async def transform_data():
    # Emits "failed" with reason if exception
    return await apply_transformations()
```

---

## Function Signatures

### Async Support

Both decorators support async and sync functions:

```python
# Async
@botanu_use_case("Async Use Case")
async def async_handler():
    await do_work()

# Sync
@botanu_use_case("Sync Use Case")
def sync_handler():
    do_work()
```

### Return Values

Decorated functions preserve their return values:

```python
@botanu_use_case("Processing")
async def process(data) -> ProcessResult:
    return ProcessResult(status="complete", items=100)

result = await process(data)
assert isinstance(result, ProcessResult)
```

### Exception Handling

Exceptions are recorded and re-raised:

```python
@botanu_use_case("Risky Operation")
async def risky():
    raise ValueError("Something went wrong")

try:
    await risky()
except ValueError:
    # Exception is re-raised after recording
    pass
```

## See Also

- [Quickstart](../getting-started/quickstart.md) - Getting started
- [Run Context](../concepts/run-context.md) - Understanding runs
- [Outcomes](../tracking/outcomes.md) - Recording outcomes
