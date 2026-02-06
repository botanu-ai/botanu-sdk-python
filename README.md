# Botanu SDK for Python

[![CI](https://github.com/botanu-ai/botanu-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/botanu-ai/botanu-sdk-python/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/botanu)](https://pypi.org/project/botanu/)
[![Python](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

OpenTelemetry-native run-level cost attribution for AI workflows.

## Overview

Botanu adds **runs** on top of distributed tracing. A run represents a single business transaction that may span multiple LLM calls, database queries, and services. By correlating all operations to a stable `run_id`, you get accurate cost attribution without sampling artifacts.

**Key features:**
- **Run-level attribution** — Link all costs to business outcomes
- **Cross-service correlation** — W3C Baggage propagation
- **OTel-native** — Works with any OpenTelemetry-compatible backend
- **GenAI support** — OpenAI, Anthropic, Vertex AI, and more

## Quick Start

```python
from botanu import enable, botanu_use_case, emit_outcome

enable(service_name="my-app")

@botanu_use_case(name="Customer Support")
async def handle_ticket(ticket_id: str):
    context = await fetch_context(ticket_id)
    response = await generate_response(context)
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
    return response
```

## Installation

```bash
pip install botanu            # Core SDK
pip install "botanu[sdk]"     # With OTel SDK + OTLP exporter
pip install "botanu[genai]"   # With GenAI instrumentation
pip install "botanu[all]"     # Everything included
```

| Extra | Description |
|-------|-------------|
| `sdk` | OpenTelemetry SDK + OTLP HTTP exporter |
| `instruments` | Auto-instrumentation for HTTP, databases |
| `genai` | GenAI provider instrumentation |
| `carriers` | Cross-service propagation (Celery, Kafka) |
| `all` | All extras |

## LLM Tracking

```python
from botanu.tracking.llm import track_llm_call

with track_llm_call(provider="openai", model="gpt-4") as tracker:
    response = await openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )
    tracker.set_tokens(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
```

## Data Tracking

```python
from botanu.tracking.data import track_db_operation, track_storage_operation

with track_db_operation(system="postgresql", operation="SELECT") as db:
    result = await cursor.execute(query)
    db.set_result(rows_returned=len(result))

with track_storage_operation(system="s3", operation="PUT") as storage:
    await s3.put_object(Bucket="bucket", Key="key", Body=data)
    storage.set_result(bytes_written=len(data))
```

## Documentation

- [Getting Started](./docs/getting-started/)
- [Concepts](./docs/concepts/)
- [Tracking Guides](./docs/tracking/)
- [Integration](./docs/integration/)
- [API Reference](./docs/api/)

## Requirements

- Python 3.9+
- OpenTelemetry Collector (recommended for production)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). This project uses DCO sign-off.

```bash
git commit -s -m "Your commit message"
```

## License

[Apache-2.0](./LICENSE)

This project is an [LF AI & Data Foundation](https://lfaidata.foundation/) project.
