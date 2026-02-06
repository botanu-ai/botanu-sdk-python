# Installation

This guide covers installing Botanu SDK and its optional dependencies.

## Requirements

- Python 3.9 or later
- OpenTelemetry Collector (for span processing)

## Basic Installation

Install the core SDK with pip:

```bash
pip install botanu
```

The core package has minimal dependencies:
- `opentelemetry-api >= 1.20.0`

This is all you need if you already have OpenTelemetry configured in your application.

## Installation with Extras

### Full SDK (Recommended for Standalone)

If you don't have an existing OpenTelemetry setup:

```bash
pip install "botanu[sdk]"
```

This adds:
- `opentelemetry-sdk` - The OTel SDK implementation
- `opentelemetry-exporter-otlp-proto-http` - OTLP HTTP exporter

### Auto-Instrumentation

For automatic instrumentation of common libraries:

```bash
pip install "botanu[instruments]"
```

Includes instrumentation for:
- **HTTP clients**: requests, httpx, urllib3, aiohttp
- **Web frameworks**: FastAPI, Flask, Django, Starlette
- **Databases**: SQLAlchemy, psycopg2, asyncpg, pymongo, redis
- **Messaging**: Celery, Kafka
- **Other**: gRPC, logging

### GenAI Instrumentation

For automatic LLM provider instrumentation:

```bash
pip install "botanu[genai]"
```

Includes instrumentation for:
- OpenAI
- Anthropic
- Google Vertex AI
- Google GenAI
- LangChain

### Everything

To install all optional dependencies:

```bash
pip install "botanu[all]"
```

### Development

For development and testing:

```bash
pip install "botanu[dev]"
```

## Verify Installation

```python
import botanu
print(botanu.__version__)
```

## Docker

In a Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Botanu with SDK extras
RUN pip install "botanu[sdk]"

COPY . .

CMD ["python", "app.py"]
```

## Poetry

```toml
[tool.poetry.dependencies]
botanu = { version = "^0.1.0", extras = ["sdk"] }
```

## pip-tools / requirements.txt

```text
# requirements.in
botanu[sdk]>=0.1.0
```

Generate with:
```bash
pip-compile requirements.in
```

## Collector Setup

Botanu SDK sends traces to an OpenTelemetry Collector. You'll need one running to receive spans.

Quick start with Docker:

```bash
docker run -p 4318:4318 otel/opentelemetry-collector:latest
```

See [Collector Configuration](../integration/collector.md) for detailed setup.

## Next Steps

- [Quickstart](quickstart.md) - Your first instrumented application
- [Configuration](configuration.md) - Customize SDK behavior
