# Installation

## Requirements

- Python 3.9 or later

## Install

```bash
pip install botanu
```

One install gives you everything:

- **OTel SDK** + OTLP HTTP exporter
- **Auto-instrumentation** for 50+ libraries (HTTP, databases, messaging, GenAI, AWS, gRPC)

Instrumentation packages are lightweight shims that silently no-op when the target library is not installed. Zero bloat.

## Configure

Set your API key as an environment variable. The SDK auto-configures the OTLP endpoint to `ingest.botanu.ai` — no other configuration needed.

```bash
export BOTANU_API_KEY="btnu_live_..."
```

That's it. No collector to run, no infrastructure to deploy. Botanu hosts everything.

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
ENV BOTANU_API_KEY="btnu_live_..."
CMD ["python", "app.py"]
```

## Development

For running tests and linting:

```bash
pip install "botanu[dev]"
```

## Next Steps

- [Quickstart](quickstart.md) - Your first instrumented application
- [Configuration](configuration.md) - Environment variables and YAML config
