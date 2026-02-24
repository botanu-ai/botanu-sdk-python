# Configuration

Botanu SDK can be configured through code, environment variables, or YAML files.

## Configuration Precedence

1. **Code arguments** (explicit values passed to `BotanuConfig`)
2. **Environment variables** (`BOTANU_*`, `OTEL_*`)
3. **YAML config file** (`botanu.yaml` or specified path)
4. **Built-in defaults**

## Quick Configuration

### Code-Based

```python
from botanu import enable

enable(
    service_name="my-service",
    otlp_endpoint="http://collector:4318/v1/traces",
)
```

### Environment Variables

```bash
export OTEL_SERVICE_NAME=my-service
export OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318
export BOTANU_ENVIRONMENT=production
```

### YAML File

```yaml
# botanu.yaml
service:
  name: my-service
  version: 1.0.0
  environment: production

otlp:
  endpoint: http://collector:4318/v1/traces

propagation:
  mode: lean
```

Load with:

```python
from botanu.sdk.config import BotanuConfig

config = BotanuConfig.from_yaml("botanu.yaml")
```

## Full Configuration Reference

### BotanuConfig Fields

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
    otlp_headers: dict = None         # Custom headers for auth

    # Span export
    max_export_batch_size: int = 512
    max_queue_size: int = 65536
    schedule_delay_millis: int = 5000
    export_timeout_millis: int = 30000

    # Propagation mode
    propagation_mode: str = "lean"    # BOTANU_PROPAGATION_MODE

    # Auto-instrumentation
    auto_instrument_packages: list = [...]
```

## Environment Variables

### OpenTelemetry Standard Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OTEL_SERVICE_NAME` | Service name | `unknown_service` |
| `OTEL_SERVICE_VERSION` | Service version | None |
| `OTEL_SERVICE_NAMESPACE` | Service namespace | None |
| `OTEL_DEPLOYMENT_ENVIRONMENT` | Environment name | `production` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector base URL | `http://localhost:4318` |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | OTLP traces endpoint (full URL) | None |

### Botanu-Specific Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BOTANU_ENVIRONMENT` | Fallback for environment | `production` |
| `BOTANU_PROPAGATION_MODE` | `lean` or `full` | `lean` |
| `BOTANU_AUTO_DETECT_RESOURCES` | Auto-detect cloud resources | `true` |
| `BOTANU_CONFIG_FILE` | Path to YAML config | None |

## YAML Configuration

### Full Example

```yaml
# botanu.yaml - Full configuration example
service:
  name: ${OTEL_SERVICE_NAME:-my-service}
  version: ${APP_VERSION:-1.0.0}
  namespace: production
  environment: ${ENVIRONMENT:-production}

resource:
  auto_detect: true

otlp:
  endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:-http://localhost:4318}/v1/traces
  headers:
    Authorization: Bearer ${OTLP_AUTH_TOKEN}

export:
  batch_size: 512
  queue_size: 2048
  delay_ms: 5000

propagation:
  mode: lean

auto_instrument_packages:
  - requests
  - httpx
  - fastapi
  - sqlalchemy
  - openai_v2
```

### Environment Variable Interpolation

The YAML loader supports two interpolation patterns:

```yaml
# Simple interpolation
endpoint: ${COLLECTOR_URL}

# With default value
endpoint: ${COLLECTOR_URL:-http://localhost:4318}
```

### Loading Configuration

```python
from botanu.sdk.config import BotanuConfig

# Explicit path
config = BotanuConfig.from_yaml("config/botanu.yaml")

# Auto-discover (searches botanu.yaml, config/botanu.yaml)
config = BotanuConfig.from_file_or_env()

# Environment only
config = BotanuConfig()
```

## Propagation Modes

### Lean Mode (Default)

Propagates only essential fields to minimize header size:

- `botanu.run_id`
- `botanu.workflow`
- `botanu.event_id`
- `botanu.customer_id`

Best for high-traffic systems where header size matters.

### Full Mode

Propagates all context fields:

- `botanu.run_id`
- `botanu.workflow`
- `botanu.event_id`
- `botanu.customer_id`
- `botanu.environment`
- `botanu.tenant_id`
- `botanu.parent_run_id`

Enable with:

```bash
export BOTANU_PROPAGATION_MODE=full
```

## Auto-Instrumentation

### Default Packages

By default, Botanu enables instrumentation for:

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

### Customizing Packages

Override the default list via `BotanuConfig`:

```python
from botanu import enable
from botanu.sdk.config import BotanuConfig

config = BotanuConfig(auto_instrument_packages=["requests", "fastapi", "openai_v2"])
enable(config=config)
```

### Disabling Auto-Instrumentation

```python
enable(auto_instrumentation=False)
```

## Exporting Configuration

```python
config = BotanuConfig(
    service_name="my-service",
    deployment_environment="production",
)

# Export as dictionary
print(config.to_dict())
```

## See Also

- [Architecture](../concepts/architecture.md) - SDK design principles
- [Collector Configuration](../integration/collector.md) - Collector setup
- [Existing OTel Setup](../integration/existing-otel.md) - Integration with existing OTel
