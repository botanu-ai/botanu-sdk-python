# Quickstart

Get run-level cost attribution working in minutes.

## Prerequisites

- Python 3.9+
- OpenTelemetry Collector (see [Collector Configuration](../integration/collector.md))

## Step 1: Install

```bash
pip install "botanu[all]"
```

## Step 2: Enable

```python
from botanu import enable

enable(service_name="my-service")
```

## Step 3: Define Entry Point

```python
from botanu import botanu_use_case

@botanu_use_case(name="process_order")
def process_order(order_id: str):
    order = db.get_order(order_id)
    result = llm.analyze(order)
    return result
```

All LLM calls, database queries, and HTTP requests inside the function are automatically tracked with the same `run_id`.

## Complete Example

```python
from botanu import enable, botanu_use_case

enable(service_name="order-service")

@botanu_use_case(name="process_order")
def process_order(order_id: str):
    order = db.get_order(order_id)
    result = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": order.description}]
    )
    db.save_result(order_id, result)
    return result
```

## What Gets Tracked

| Attribute | Example | Description |
|-----------|---------|-------------|
| `botanu.run_id` | `019abc12-...` | Unique run identifier |
| `botanu.use_case` | `process_order` | Business use case |
| `gen_ai.usage.input_tokens` | `150` | LLM input tokens |
| `gen_ai.usage.output_tokens` | `200` | LLM output tokens |
| `db.system` | `postgresql` | Database system |

All spans share the same `run_id`, enabling cost-per-transaction analytics.

## Next Steps

- [Configuration](configuration.md) - Environment variables and YAML config
- [Kubernetes Deployment](../integration/kubernetes.md) - Zero-code instrumentation at scale
- [Context Propagation](../concepts/context-propagation.md) - Cross-service tracing
