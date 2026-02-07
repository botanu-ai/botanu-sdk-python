# Installation

## Requirements

- Python 3.9 or later
- OpenTelemetry Collector (recommended for production)

## Install

```bash
pip install botanu
```

One install gives you everything:

- **OTel SDK** + OTLP HTTP exporter
- **Auto-instrumentation** for 50+ libraries (HTTP, databases, messaging, GenAI, AWS, gRPC)

Instrumentation packages are lightweight shims that silently no-op when the target library is not installed. Zero bloat.

## Verify

```python
import botanu
print(botanu.__version__)
```

## Package Managers

### pip / requirements.txt

```text
botanu>=0.1.0
```

### Poetry

```toml
[tool.poetry.dependencies]
botanu = "^0.1.0"
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install botanu
COPY . .
CMD ["python", "app.py"]
```

## Development

For running tests and linting:

```bash
pip install "botanu[dev]"
```

## Collector Setup

The SDK sends traces to an OpenTelemetry Collector via OTLP HTTP (port 4318). Configure the endpoint via environment variable:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

Quick start with Docker:

```bash
docker run -p 4318:4318 otel/opentelemetry-collector:latest
```

See [Collector Configuration](../integration/collector.md) for production setup.

## Next Steps

- [Quickstart](quickstart.md) - Your first instrumented application
- [Configuration](configuration.md) - Environment variables and YAML config
