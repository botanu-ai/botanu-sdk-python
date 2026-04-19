# Configuration

botanu SDK can be configured with a single environment variable (the common
case) or through code / YAML for everything else.

## Simplest config — just the API key

For the Botanu Cloud SaaS, a single env var is enough:

```bash
export BOTANU_API_KEY=<your-api-key>
python your_app.py
```

When `BOTANU_API_KEY` is set, `enable()` auto-configures the OTLP endpoint
to `https://ingest.botanu.ai` and attaches the key as a bearer token on the
exporter. You do not need to set `OTEL_EXPORTER_OTLP_ENDPOINT` too.

## ⚠ The API key is only sent to botanu-trusted endpoints

If you override the OTLP endpoint to something that isn't owned by
botanu — e.g., you point OTLP at Datadog, Honeycomb, or a self-hosted
collector — **the SDK will not attach your botanu API key to the
exporter's Authorization header**. It is silently dropped. This is to
prevent a misconfigured `OTEL_EXPORTER_OTLP_ENDPOINT` from leaking your
tenant credentials to a third-party backend.

The trusted endpoint list is hard-coded in
[`src/botanu/sdk/config.py`](../../src/botanu/sdk/config.py):

- any host ending in `.botanu.ai` (e.g., `ingest.botanu.ai`)
- `localhost`, `127.0.0.1`, `::1`, `0.0.0.0` (local development)

For any other endpoint the exporter runs without a bearer header. If you
are shipping OTLP to a non-botanu backend and want auth on that exporter,
set `OTEL_EXPORTER_OTLP_HEADERS` or pass `otlp_headers=` to `BotanuConfig`
explicitly — those headers are always honored.

## Configuration precedence

1. **Code arguments** passed to `enable()` or `BotanuConfig(...)`.
2. **Environment variables** (`BOTANU_*`, `OTEL_*`).
3. **YAML config file** (`botanu.yaml` or a path you pass).
4. **Built-in defaults.**

## Code-based

```python
from botanu import enable

enable(
    service_name="my-service",
    otlp_endpoint="https://ingest.botanu.ai",
)
```

## Environment variables

```bash
export BOTANU_API_KEY=<your-api-key>           # enough on its own for Botanu Cloud
export OTEL_SERVICE_NAME=my-service
export BOTANU_ENVIRONMENT=production
export BOTANU_CONTENT_CAPTURE_RATE=0.10        # see Content Capture docs
```

## YAML file

```yaml
# botanu.yaml
service:
  name: my-service
  version: 1.0.0
  environment: production

otlp:
  endpoint: https://ingest.botanu.ai

content:
  capture_rate: 0.10

propagation:
  mode: full
```

Load with:

```python
from botanu.sdk.config import BotanuConfig

config = BotanuConfig.from_yaml("botanu.yaml")
```

## Full `BotanuConfig` fields

```python
from dataclasses import dataclass

@dataclass
class BotanuConfig:
    # Service identification
    service_name: str = None          # OTEL_SERVICE_NAME
    service_version: str = None       # OTEL_SERVICE_VERSION
    service_namespace: str = None     # OTEL_SERVICE_NAMESPACE
    deployment_environment: str = None # OTEL_DEPLOYMENT_ENVIRONMENT

    # Resource detection
    auto_detect_resources: bool = True # BOTANU_AUTO_DETECT_RESOURCES

    # OTLP exporter
    otlp_endpoint: str = None         # OTEL_EXPORTER_OTLP_ENDPOINT
    otlp_headers: dict = None         # Custom headers (always honored)

    # API key (auto-configures endpoint + Authorization header on trusted hosts)
    api_key: str = None               # BOTANU_API_KEY

    # Span export
    max_export_batch_size: int = 512
    max_queue_size: int = 65536
    schedule_delay_millis: int = 5000
    export_timeout_millis: int = 30000

    # Content capture for eval (0.0 disables; see Content Capture doc)
    content_capture_rate: float = 0.0  # BOTANU_CONTENT_CAPTURE_RATE

    # Propagation mode — "full" is the target. "lean" is deprecated.
    propagation_mode: str = "lean"    # BOTANU_PROPAGATION_MODE
```

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
| `BOTANU_API_KEY` | API key for Botanu Cloud. Auto-configures the endpoint and bearer token on trusted hosts. | None |
| `BOTANU_ENVIRONMENT` | Fallback for environment | `production` |
| `BOTANU_CONTENT_CAPTURE_RATE` | Content-capture sampling rate (0.0–1.0). See [Content Capture](../tracking/content-capture.md). | `0.0` |
| `BOTANU_PROPAGATION_MODE` | `full` (recommended) or `lean` (deprecated) | `lean` |
| `BOTANU_AUTO_DETECT_RESOURCES` | Auto-detect cloud resources | `true` |
| `BOTANU_CONFIG_FILE` | Path to YAML config | None |
| `BOTANU_COLLECTOR_ENDPOINT` | Override for OTLP endpoint (same behavior as `OTEL_EXPORTER_OTLP_ENDPOINT`) | None |

## Content capture

Prompt / response capture for the evaluator is disabled by default.
Turn it on with `BOTANU_CONTENT_CAPTURE_RATE`:

```bash
export BOTANU_CONTENT_CAPTURE_RATE=0.10   # 10% of calls captured
```

See [Content Capture](../tracking/content-capture.md) for the full
pipeline, the three capture points, and the PII-scrubbing chain.

## Propagation modes

botanu's durable direction is **full-mode only** — every cross-service
call carries the complete run context in W3C Baggage. `lean` mode is still
present in the SDK for backward compatibility but will be removed; do not
depend on it.

Set explicitly:

```bash
export BOTANU_PROPAGATION_MODE=full
```

See [Context Propagation](../concepts/context-propagation.md) for the
exact field list.

## Zero-code initialization

If you want `enable()` to run without a line of code, import the
`botanu.register` module at process start. It calls `enable()` under the
hood:

```bash
python -c "import botanu.register" -m your_app
```

Or, for containers, add `botanu.register` to your `PYTHONSTARTUP`:

```bash
PYTHONSTARTUP=$(python -c "import botanu, os; print(os.path.dirname(botanu.__file__) + '/register.py')")
```

This is useful when you cannot edit the entry point (e.g., a third-party
process runner).

## Auto-instrumentation

### Default packages

```python
[
    # HTTP clients
    "requests", "httpx", "urllib3", "aiohttp_client",
    # Web frameworks
    "fastapi", "flask", "django", "starlette",
    # Databases
    "sqlalchemy", "psycopg2", "asyncpg", "pymongo", "redis",
    # Messaging
    "celery", "kafka_python",
    # gRPC
    "grpc",
    # GenAI
    "openai_v2", "anthropic", "vertexai", "google_genai", "langchain",
    # Runtime
    "logging",
]
```

### Customizing packages

```python
from botanu import enable
from botanu.sdk.config import BotanuConfig

config = BotanuConfig(auto_instrument_packages=["requests", "fastapi", "openai_v2"])
enable(config=config)
```

### Disabling

```python
enable(auto_instrumentation=False)
```

## See also

- [Quickstart](quickstart.md)
- [Architecture](../concepts/architecture.md)
- [Collector](../integration/collector.md)
- [Existing OTel / Datadog setup](../integration/existing-otel.md)
- [Content Capture](../tracking/content-capture.md)
