# Configuration

One environment variable is enough for most installations. Code and YAML are available for anything more complex.

## Minimal

```bash
export BOTANU_API_KEY=<your-api-key>
python your_app.py
```

When `BOTANU_API_KEY` is set, the SDK auto-configures the OTLP endpoint to `https://ingest.botanu.ai` and sends the key as a bearer token on every export. No other variables are required.

## The API key is only sent to botanu-trusted endpoints

If you override the OTLP endpoint to anything outside the botanu-trusted list, the SDK will not attach your API key. This prevents a misconfigured `OTEL_EXPORTER_OTLP_ENDPOINT` from leaking tenant credentials to a third-party backend.

Trusted hosts:

- Any host ending in `.botanu.ai`
- `localhost`, `127.0.0.1`, `::1`, `0.0.0.0`

For any other endpoint, the exporter ships without a bearer header. If your self-hosted collector needs auth, set `OTEL_EXPORTER_OTLP_HEADERS` or pass `otlp_headers=` to `BotanuConfig` explicitly — those headers are always honored.

## Configuration precedence

1. Environment variables (`BOTANU_*`, `OTEL_*`)
2. YAML config file (`botanu.yaml` or a path you pass)
3. Built-in defaults

## Environment variables

```bash
export BOTANU_API_KEY=<your-api-key>
export OTEL_SERVICE_NAME=my-service
export BOTANU_ENVIRONMENT=production
export BOTANU_CONTENT_CAPTURE_RATE=0.10
```

## YAML

```yaml
service:
  name: my-service
  version: 1.0.0
  environment: production

otlp:
  endpoint: https://ingest.botanu.ai

eval:
  content_capture_rate: 0.10
```

```python
from botanu.sdk.config import BotanuConfig

config = BotanuConfig.from_yaml("botanu.yaml")
```

## `BotanuConfig` fields

```python
from dataclasses import dataclass

@dataclass
class BotanuConfig:
    service_name: str = None
    service_version: str = None
    service_namespace: str = None
    deployment_environment: str = None

    auto_detect_resources: bool = True

    otlp_endpoint: str = None
    otlp_headers: dict = None

    max_export_batch_size: int = 512
    max_queue_size: int = 65536
    schedule_delay_millis: int = 5000
    export_timeout_millis: int = 30000

    content_capture_rate: float = 0.10
```

`BOTANU_API_KEY` is not a field on the dataclass — when the env var is set, `BotanuConfig` auto-configures `otlp_endpoint` + `otlp_headers` for the botanu-trusted endpoint.

## Environment variable reference

### OpenTelemetry standard

| Variable | Description | Default |
| --- | --- | --- |
| `OTEL_SERVICE_NAME` | Service name | `unknown_service` |
| `OTEL_SERVICE_VERSION` | Service version | None |
| `OTEL_SERVICE_NAMESPACE` | Service namespace | None |
| `OTEL_DEPLOYMENT_ENVIRONMENT` | Environment name | `production` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector base URL | Auto-set to `https://ingest.botanu.ai` when `BOTANU_API_KEY` is set |
| `OTEL_EXPORTER_OTLP_HEADERS` | Extra OTLP headers | None |

### botanu-specific

| Variable | Description | Default |
| --- | --- | --- |
| `BOTANU_API_KEY` | API key for Botanu Cloud. Auto-configures endpoint and bearer token on trusted hosts. | None |
| `BOTANU_ENVIRONMENT` | Fallback for environment | `production` |
| `BOTANU_CONTENT_CAPTURE_RATE` | Content-capture sampling rate, `0.0`–`1.0`. See [Content Capture](../tracking/content-capture.md). | `0.0` |
| `BOTANU_AUTO_DETECT_RESOURCES` | Auto-detect cloud resources | `true` |
| `BOTANU_CONFIG_FILE` | Path to YAML config | None |
| `BOTANU_COLLECTOR_ENDPOINT` | OTLP endpoint override (same behavior as `OTEL_EXPORTER_OTLP_ENDPOINT`) | None |

## Content capture

Prompt and response capture for the evaluator is disabled by default. Turn it on with:

```bash
export BOTANU_CONTENT_CAPTURE_RATE=0.10
```

The SDK scrubs PII in-process before writing the captured content. See [Content Capture](../tracking/content-capture.md) for the scrub pipeline, custom patterns, and opt-out flags.

## Zero-code initialization

If you can't edit the entry point (third-party process runner, gunicorn preload), import `botanu.register` at process start:

```bash
python -c "import botanu.register" -m your_app
```

## Auto-instrumentation

### Default packages

```python
[
    "requests", "httpx", "urllib3", "aiohttp_client",
    "fastapi", "flask", "django", "starlette",
    "sqlalchemy", "psycopg2", "asyncpg", "pymongo", "redis",
    "celery", "kafka_python",
    "grpc",
    "openai_v2", "anthropic", "vertexai", "google_genai", "langchain",
    "logging",
]
```

### Customizing

Set `BOTANU_AUTO_INSTRUMENT_PACKAGES` (comma-separated) or put the list in `botanu.yaml`:

```yaml
auto_instrument_packages:
  - requests
  - fastapi
  - openai_v2
```

### Disabling

Set `BOTANU_AUTO_INSTRUMENTATION=false` to skip auto-instrumentation entirely. Only do this if you've manually instrumented every library you care about.

## See also

- [Quickstart](quickstart.md)
- [Architecture](../concepts/architecture.md)
- [Collector](../integration/collector.md)
- [Coexisting with existing OTel / Datadog](../integration/existing-otel.md)
- [Content Capture](../tracking/content-capture.md)
