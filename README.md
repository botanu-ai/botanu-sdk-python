# Botanu SDK for Python

[![PyPI version](https://img.shields.io/pypi/v/botanu)](https://pypi.org/project/botanu/)
[![Python](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue)](https://www.python.org/)

**Run-level cost attribution for AI workflows, built on OpenTelemetry.**

Botanu adds **runs** on top of distributed tracing. A run represents one business transaction that may span multiple LLM calls, database queries, and microservices. By correlating every operation to a stable `run_id`, you get per-transaction cost attribution without sampling artifacts.

## How It Works

```
User Request
    |
    v
  Entry Service          Intermediate Service         LLM / DB
  @botanu_use_case  -->  enable() propagates   -->  auto-instrumented
  creates run_id         run_id via W3C Baggage      spans tagged with run_id
```

1. **Entry point** creates a `run_id` with `@botanu_use_case`
2. **Every service** calls `enable()` to propagate the `run_id` via W3C Baggage
3. **All spans** across all services share the same `run_id`
4. **Traces export** to your OTel Collector via OTLP (configured by environment variable)

## Quick Start

### Install

```bash
pip install botanu
```

One install. Includes OTel SDK, OTLP exporter, and auto-instrumentation for 50+ libraries.

### Instrument Your Code

**Entry service** (where the workflow begins):

```python
from botanu import enable, botanu_use_case

enable()  # reads config from env vars

@botanu_use_case(name="Customer Support")
async def handle_ticket(ticket_id: str):
    data = await db.query(ticket_id)
    result = await llm.complete(data)
    return result
```

**Every other service** (intermediate, downstream):

```python
from botanu import enable

enable()  # propagates run_id from incoming request
```

That's it. No collector endpoint in code. No manual span creation.

### Configure via Environment Variables

All configuration is via environment variables. **Zero hardcoded values in code.**

| Variable | Description | Default |
|----------|-------------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Collector endpoint | `http://localhost:4318` |
| `OTEL_SERVICE_NAME` | Service name | `unknown_service` |
| `BOTANU_ENVIRONMENT` | Deployment environment | `production` |

```yaml
# docker-compose.yml / Kubernetes deployment
environment:
  - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
  - OTEL_SERVICE_NAME=my-service
```

See [Configuration Reference](./docs/getting-started/configuration.md) for all options.

## Auto-Instrumentation

Everything is included and auto-detected. If the library is in your dependencies, it gets instrumented:

| Category | Libraries |
|----------|-----------|
| **LLM Providers** | OpenAI, Anthropic, Vertex AI, Google GenAI, LangChain, Ollama, CrewAI |
| **Web Frameworks** | FastAPI, Flask, Django, Starlette, Falcon, Pyramid, Tornado |
| **HTTP Clients** | requests, httpx, urllib3, aiohttp |
| **Databases** | PostgreSQL (psycopg2/3, asyncpg), MySQL, SQLite, MongoDB, Redis, SQLAlchemy, Elasticsearch, Cassandra |
| **Messaging** | Celery, Kafka, RabbitMQ (pika) |
| **AWS** | botocore, boto3 (SQS) |
| **gRPC** | Client + Server |
| **Runtime** | logging, threading, asyncio |

No manual instrumentation required. Libraries not installed are silently skipped.

## Kubernetes at Scale

For large deployments (2000+ services), only entry points need code changes:

| Service Type | Code Change | Configuration |
|--------------|-------------|---------------|
| Entry point | `@botanu_use_case` decorator | `OTEL_EXPORTER_OTLP_ENDPOINT` env var |
| Intermediate | `enable()` call only | `OTEL_EXPORTER_OTLP_ENDPOINT` env var |

See [Kubernetes Deployment Guide](./docs/integration/kubernetes.md) for details.

## Architecture

```
                    +---------+     +---------+     +---------+
                    | Service | --> | Service | --> | Service |
                    | enable()| --> | enable()| --> | enable()|
                    +---------+     +---------+     +---------+
                         |               |               |
                         v               v               v
                    +-------------------------------------+
                    |       OTel Collector (OTLP)         |
                    +-------------------------------------+
                         |               |               |
                         v               v               v
                    Jaeger/Tempo   Prometheus   Your Backend
```

The SDK is a thin layer on OpenTelemetry:
- **SDK**: Generates `run_id`, propagates context, auto-instruments
- **Collector**: PII redaction, cardinality limits, routing, vendor enrichment

## Documentation

- [Getting Started](./docs/getting-started/) - Installation, quickstart, configuration
- [Concepts](./docs/concepts/) - Runs, context propagation, cost attribution
- [Integration](./docs/integration/) - Auto-instrumentation, Kubernetes, collector setup
- [API Reference](./docs/api/) - `enable()`, `@botanu_use_case`, `emit_outcome()`

## Requirements

- Python 3.9+
- OpenTelemetry Collector (recommended for production)

## Contributing

We welcome contributions. See [CONTRIBUTING.md](./CONTRIBUTING.md).

This project follows the [Developer Certificate of Origin (DCO)](https://developercertificate.org/). Sign off your commits:

```bash
git commit -s -m "Your commit message"
```

## License

[Apache-2.0](./LICENSE)

This project is an [LF AI & Data Foundation](https://lfaidata.foundation/) project.
