# Botanu SDK for Python

[![CI](https://github.com/botanu-ai/botanu-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/botanu-ai/botanu-sdk-python/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/botanu.svg)](https://pypi.org/project/botanu/)
[![Python versions](https://img.shields.io/pypi/pyversions/botanu.svg)](https://pypi.org/project/botanu/)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/botanu-ai/botanu-sdk-python/badge)](https://scorecard.dev/viewer/?uri=github.com/botanu-ai/botanu-sdk-python)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

OpenTelemetry-native **run-level cost attribution** for AI workflows.

## Overview

Botanu adds **runs** on top of distributed tracing. A run represents a single business transaction that may span multiple LLM calls, database queries, and services. By correlating all operations to a stable `run_id`, you get accurate cost attribution without sampling artifacts.

**Key features:**
- 🎯 **Run-level attribution** — Link all costs to business outcomes
- 🔗 **Cross-service correlation** — W3C Baggage propagation
- 📊 **OTel-native** — Works with any OpenTelemetry-compatible backend
- ⚡ **Minimal overhead** — < 0.5ms per request
- 🤖 **GenAI support** — OpenAI, Anthropic, Vertex AI, and more

## Quick Start

```python
from botanu import enable, botanu_use_case, emit_outcome

# Initialize at startup
enable(service_name="my-app")

@botanu_use_case(name="Customer Support")
async def handle_ticket(ticket_id: str):
    # All operations inside get the same run_id
    context = await fetch_context(ticket_id)
    response = await generate_response(context)

    # Record the business outcome
    emit_outcome("success", value_type="tickets_resolved", value_amount=1)
    return response
```

## Installation

```bash
# Core SDK (opentelemetry-api only, ~50KB)
pip install botanu

# With OTel SDK + OTLP exporter (for standalone use)
pip install "botanu[sdk]"

# With GenAI provider instrumentation
pip install "botanu[genai]"

# Everything included
pip install "botanu[all]"
```

### Extras

| Extra | Description |
|-------|-------------|
| `sdk` | OpenTelemetry SDK + OTLP HTTP exporter |
| `instruments` | Auto-instrumentation for HTTP, databases, etc. |
| `genai` | GenAI provider instrumentation (OpenAI, Anthropic, etc.) |
| `carriers` | Cross-service propagation helpers (Celery, Kafka) |
| `all` | All of the above |
| `dev` | Development and testing tools |

## LLM Tracking

Track LLM calls with full cost attribution:

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

Track database and storage operations:

```python
from botanu.tracking.data import track_db_operation, track_storage_operation

# Database
with track_db_operation(system="postgresql", operation="SELECT") as db:
    result = await cursor.execute(query)
    db.set_result(rows_returned=len(result))

# Storage
with track_storage_operation(system="s3", operation="PUT") as storage:
    await s3.put_object(Bucket="bucket", Key="key", Body=data)
    storage.set_result(bytes_written=len(data))
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Your Application                         │
│                                                               │
│  @botanu_use_case    track_llm_call()    track_db_operation()│
│         │                   │                    │            │
│         └───────────────────┴────────────────────┘            │
│                             │                                 │
│                    Botanu SDK (thin)                          │
│            - Generate run_id (UUIDv7)                         │
│            - Set W3C Baggage                                  │
│            - Record spans                                     │
└─────────────────────────────┬─────────────────────────────────┘
                              │ OTLP
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                   OpenTelemetry Collector                     │
│                                                               │
│  - PII redaction           - Cost calculation                 │
│  - Vendor normalization    - Cardinality management           │
└──────────────────────────────────────────────────────────────┘
```

## Documentation

Full documentation is available at [docs.botanu.ai](https://docs.botanu.ai) and in the [`docs/`](./docs/) folder:

- [Getting Started](./docs/getting-started/)
- [Concepts](./docs/concepts/)
- [Tracking Guides](./docs/tracking/)
- [Integration](./docs/integration/)
- [API Reference](./docs/api/)

## Requirements

- Python 3.9+
- OpenTelemetry Collector (for production use)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). This project uses [DCO](./DCO) sign-off.

```bash
git commit -s -m "Your commit message"
```

## License

[Apache-2.0](./LICENSE) — see [NOTICE](./NOTICE) for attribution.

This project is an [LF AI & Data Foundation](https://lfaidata.foundation/) project.
