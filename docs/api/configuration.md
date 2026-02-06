# Configuration API Reference

## BotanuConfig

Dataclass for SDK configuration.

```python
from botanu.sdk.config import BotanuConfig
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `service_name` | `str` | `"unknown_service"` | Service name (from `OTEL_SERVICE_NAME`) |
| `service_version` | `str` | `None` | Service version (from `OTEL_SERVICE_VERSION`) |
| `service_namespace` | `str` | `None` | Service namespace (from `OTEL_SERVICE_NAMESPACE`) |
| `deployment_environment` | `str` | `"production"` | Environment (from `OTEL_DEPLOYMENT_ENVIRONMENT` or `BOTANU_ENVIRONMENT`) |
| `auto_detect_resources` | `bool` | `True` | Auto-detect cloud resources |
| `otlp_endpoint` | `str` | `"http://localhost:4318/v1/traces"` | OTLP endpoint |
| `otlp_headers` | `dict` | `None` | Custom headers for OTLP exporter |
| `max_export_batch_size` | `int` | `512` | Max spans per batch |
| `max_queue_size` | `int` | `2048` | Max spans in queue |
| `schedule_delay_millis` | `int` | `5000` | Delay between batch exports |
| `trace_sample_rate` | `float` | `1.0` | Sampling rate (1.0 = 100%) |
| `propagation_mode` | `str` | `"lean"` | `"lean"` or `"full"` |
| `auto_instrument_packages` | `list` | `[...]` | Packages to auto-instrument |

### Constructor

```python
config = BotanuConfig(
    service_name="my-service",
    deployment_environment="production",
    otlp_endpoint="http://collector:4318/v1/traces",
)
```

### Class Methods

#### from_yaml()

Load configuration from a YAML file.

```python
@classmethod
def from_yaml(cls, path: Optional[str] = None) -> BotanuConfig
```

**Parameters:**
- `path`: Path to YAML config file

**Raises:**
- `FileNotFoundError`: If config file doesn't exist
- `ValueError`: If YAML is malformed
- `ImportError`: If PyYAML is not installed

**Example:**

```python
config = BotanuConfig.from_yaml("config/botanu.yaml")
```

#### from_file_or_env()

Load config from file if exists, otherwise use environment variables.

```python
@classmethod
def from_file_or_env(cls, path: Optional[str] = None) -> BotanuConfig
```

**Search order:**
1. Explicit `path` argument
2. `BOTANU_CONFIG_FILE` environment variable
3. `./botanu.yaml`
4. `./botanu.yml`
5. `./config/botanu.yaml`
6. `./config/botanu.yml`
7. Falls back to environment-only config

**Example:**

```python
# Auto-discovers config file
config = BotanuConfig.from_file_or_env()

# Explicit path
config = BotanuConfig.from_file_or_env("my-config.yaml")
```

### Instance Methods

#### to_dict()

Export configuration as dictionary.

```python
def to_dict(self) -> Dict[str, Any]
```

**Example:**

```python
config = BotanuConfig(service_name="my-service")
print(config.to_dict())
# {
#     "service": {"name": "my-service", ...},
#     "otlp": {"endpoint": "...", ...},
#     ...
# }
```

---

## YAML Configuration Format

### Full Schema

```yaml
service:
  name: string              # Service name
  version: string           # Service version
  namespace: string         # Service namespace
  environment: string       # Deployment environment

resource:
  auto_detect: boolean      # Auto-detect cloud resources

otlp:
  endpoint: string          # OTLP endpoint URL
  headers:                  # Custom headers
    header-name: value

export:
  batch_size: integer       # Max spans per batch
  queue_size: integer       # Max spans in queue
  delay_ms: integer         # Delay between exports

sampling:
  rate: float               # Sampling rate (0.0-1.0)

propagation:
  mode: string              # "lean" or "full"

auto_instrument_packages:   # List of packages to instrument
  - package_name
```

### Environment Variable Interpolation

```yaml
service:
  name: ${OTEL_SERVICE_NAME:-default-service}
  environment: ${ENVIRONMENT}

otlp:
  endpoint: ${COLLECTOR_URL:-http://localhost:4318}/v1/traces
  headers:
    Authorization: Bearer ${API_TOKEN}
```

Syntax:
- `${VAR_NAME}` - Required variable
- `${VAR_NAME:-default}` - Variable with default value

---

## enable()

Bootstrap function to initialize the SDK.

```python
from botanu import enable

enable(
    service_name: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    config: Optional[BotanuConfig] = None,
    auto_instrument: bool = True,
    auto_instrument_packages: Optional[List[str]] = None,
    propagation_mode: Optional[str] = None,
    **kwargs: Any,
) -> None
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `service_name` | `str` | From env | Service name |
| `otlp_endpoint` | `str` | From env | OTLP endpoint URL |
| `config` | `BotanuConfig` | `None` | Pre-built configuration |
| `auto_instrument` | `bool` | `True` | Enable auto-instrumentation |
| `auto_instrument_packages` | `list` | `None` | Override default packages |
| `propagation_mode` | `str` | `None` | `"lean"` or `"full"` |
| `**kwargs` | `Any` | `{}` | Additional config fields |

### Behavior

1. Creates/merges `BotanuConfig`
2. Configures `TracerProvider` with `RunContextEnricher`
3. Sets up OTLP exporter (if SDK extras installed)
4. Enables auto-instrumentation (if requested)
5. Configures W3C Baggage propagation

### Examples

#### Minimal

```python
from botanu import enable

enable(service_name="my-service")
```

#### With Config Object

```python
from botanu import enable
from botanu.sdk.config import BotanuConfig

config = BotanuConfig.from_yaml("config/botanu.yaml")
enable(config=config)
```

#### Custom Options

```python
enable(
    service_name="my-service",
    otlp_endpoint="http://collector:4318/v1/traces",
    auto_instrument_packages=["fastapi", "openai_v2"],
    propagation_mode="full",
)
```

---

## disable()

Disable the SDK and clean up resources.

```python
from botanu import disable

disable() -> None
```

### Behavior

1. Flushes pending spans
2. Shuts down span processors
3. Disables instrumentation

---

## is_enabled()

Check if the SDK is currently enabled.

```python
from botanu import is_enabled

is_enabled() -> bool
```

### Example

```python
if not is_enabled():
    enable(service_name="my-service")
```

---

## Environment Variables

### OpenTelemetry Standard

| Variable | Description | Default |
|----------|-------------|---------|
| `OTEL_SERVICE_NAME` | Service name | `"unknown_service"` |
| `OTEL_SERVICE_VERSION` | Service version | None |
| `OTEL_SERVICE_NAMESPACE` | Service namespace | None |
| `OTEL_DEPLOYMENT_ENVIRONMENT` | Deployment environment | `"production"` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP base endpoint | `"http://localhost:4318"` |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | OTLP traces endpoint (full URL) | None |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP headers (key=value pairs) | None |

### Botanu-Specific

| Variable | Description | Default |
|----------|-------------|---------|
| `BOTANU_ENVIRONMENT` | Fallback for environment | `"production"` |
| `BOTANU_PROPAGATION_MODE` | `"lean"` or `"full"` | `"lean"` |
| `BOTANU_TRACE_SAMPLE_RATE` | Sampling rate (0.0-1.0) | `"1.0"` |
| `BOTANU_AUTO_DETECT_RESOURCES` | Auto-detect cloud resources | `"true"` |
| `BOTANU_CONFIG_FILE` | Path to YAML config file | None |

---

## RunContext

Model for run metadata.

```python
from botanu.models.run_context import RunContext
```

### Class Methods

#### create()

Create a new run context.

```python
@classmethod
def create(
    cls,
    use_case: str,
    workflow: Optional[str] = None,
    workflow_version: Optional[str] = None,
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    deadline_seconds: Optional[float] = None,
) -> RunContext
```

#### create_retry()

Create a retry context from an original run.

```python
@classmethod
def create_retry(cls, original: RunContext) -> RunContext
```

#### from_baggage()

Reconstruct context from baggage dictionary.

```python
@classmethod
def from_baggage(cls, baggage: Dict[str, str]) -> Optional[RunContext]
```

### Instance Methods

#### to_baggage_dict()

Serialize to baggage format.

```python
def to_baggage_dict(self, lean_mode: bool = True) -> Dict[str, str]
```

#### to_span_attributes()

Serialize to span attributes.

```python
def to_span_attributes(self) -> Dict[str, Any]
```

#### as_current()

Context manager to set this as the current run.

```python
def as_current(self) -> ContextManager
```

#### complete()

Mark the run as complete.

```python
def complete(
    self,
    status: RunStatus,
    error_class: Optional[str] = None,
) -> None
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | Unique UUIDv7 identifier |
| `root_run_id` | `str` | Root run ID (same as run_id for first attempt) |
| `use_case` | `str` | Business use case name |
| `workflow` | `str` | Workflow/function name |
| `workflow_version` | `str` | Version hash |
| `environment` | `str` | Deployment environment |
| `tenant_id` | `str` | Tenant identifier |
| `parent_run_id` | `str` | Parent run ID |
| `attempt` | `int` | Attempt number |
| `start_time` | `datetime` | Run start time |
| `outcome` | `RunOutcome` | Recorded outcome |

---

## RunStatus

Enum for run status.

```python
from botanu.models.run_context import RunStatus

class RunStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
```

## See Also

- [Configuration Guide](../getting-started/configuration.md) - Configuration how-to
- [Architecture](../concepts/architecture.md) - SDK design
- [Existing OTel Setup](../integration/existing-otel.md) - Integration patterns
