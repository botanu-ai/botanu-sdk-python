# Decorators API Reference

## @botanu_use_case

The primary decorator for creating runs with automatic context propagation.

```python
from botanu import botanu_use_case

@botanu_use_case(
    name: str,
    workflow: Optional[str] = None,
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | Required | Use case name for grouping |
| `workflow` | `str` | Function name | Workflow identifier |
| `environment` | `str` | From env | Deployment environment |
| `tenant_id` | `str` | `None` | Tenant identifier for multi-tenant systems |

### Example

```python
from botanu import botanu_use_case

@botanu_use_case(name="process_order")
def process_order(order_id: str):
    order = db.get_order(order_id)
    result = llm.analyze(order)
    return result
```

### Span Attributes

| Attribute | Description |
|-----------|-------------|
| `botanu.run_id` | Generated UUIDv7 |
| `botanu.use_case` | `name` parameter |
| `botanu.workflow` | `workflow` parameter or function name |
| `botanu.environment` | Deployment environment |
| `botanu.tenant_id` | Tenant identifier (if provided) |

### Alias

`use_case` is an alias for `botanu_use_case`:

```python
from botanu import use_case

@use_case(name="process_order")
def process_order(order_id: str):
    return db.get_order(order_id)
```

## @botanu_outcome

Decorator for sub-functions to emit outcomes based on success/failure.

```python
from botanu import botanu_outcome

@botanu_outcome()
def extract_data():
    return fetch_from_source()
```

- Emits "success" on completion
- Emits "failed" with exception class name if exception raised
- Does NOT create a new run

### Example

```python
from botanu import botanu_use_case, botanu_outcome

@botanu_use_case(name="data_pipeline")
def run_pipeline():
    extract_data()
    transform_data()
    load_data()

@botanu_outcome()
def extract_data():
    return fetch_from_source()

@botanu_outcome()
def transform_data():
    return apply_transformations()
```

## See Also

- [Quickstart](../getting-started/quickstart.md)
- [Run Context](../concepts/run-context.md)
