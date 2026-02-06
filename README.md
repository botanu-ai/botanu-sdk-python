# Botanu SDK for Python

[![CI](https://github.com/botanu-ai/botanu-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/botanu-ai/botanu-sdk-python/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/botanu)](https://pypi.org/project/botanu/)
[![Python](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

OpenTelemetry-native run-level cost attribution for AI workflows.

## Overview

Botanu adds **runs** on top of distributed tracing. A run represents a single business transaction that may span multiple LLM calls, database queries, and services. By correlating all operations to a stable `run_id`, you get accurate cost attribution without sampling artifacts.

## Quick Start

```python
from botanu import enable, botanu_use_case

enable(service_name="my-service")

@botanu_use_case(name="my_workflow")
def my_function():
    data = db.query(...)
    result = llm.complete(...)
    return result
```

## Installation

```bash
pip install "botanu[all]"
```

| Extra | Description |
|-------|-------------|
| `sdk` | OpenTelemetry SDK + OTLP exporter |
| `instruments` | Auto-instrumentation for HTTP, databases |
| `genai` | Auto-instrumentation for LLM providers |
| `all` | All of the above (recommended) |

## What Gets Auto-Instrumented

When you install `botanu[all]`, the following are automatically tracked:

- **LLM Providers** — OpenAI, Anthropic, Vertex AI, Bedrock, Azure OpenAI
- **Databases** — PostgreSQL, MySQL, SQLite, MongoDB, Redis
- **HTTP** — requests, httpx, urllib3, aiohttp
- **Frameworks** — FastAPI, Flask, Django, Starlette
- **Messaging** — Celery, Kafka

No manual instrumentation required.

## Kubernetes Deployment

For large-scale deployments (2000+ services):

| Service Type | Code Change | Kubernetes Config |
|--------------|-------------|-------------------|
| Entry point | `@botanu_use_case` decorator | Annotation |
| Intermediate | None | Annotation only |

```yaml
# Intermediate services - annotation only, no code changes
metadata:
  annotations:
    instrumentation.opentelemetry.io/inject-python: "true"
```

Auto-instrumentation captures all HTTP calls including retries (requests, httpx, aiohttp, urllib3).

See [Kubernetes Deployment Guide](./docs/integration/kubernetes.md) for details.

## Documentation

- [Getting Started](./docs/getting-started/)
- [Concepts](./docs/concepts/)
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
