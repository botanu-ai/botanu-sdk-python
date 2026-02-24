# Configuration API Reference

## BotanuConfig

Dataclass for SDK configuration.

```python
from botanu.sdk.config import BotanuConfig
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `service_name` | `str` | From env / `"unknown_service"` | Service name |
| `service_version` | `str` | From env | Service version |
| `service_namespace` | `str` | From env | Service namespace |
| `deployment_environment` | `str` | From env / `"production"` | Deployment environment |
| `auto_detect_resources` | `bool` | `True` | Auto-detect cloud resources |
| `otlp_endpoint` | `str` | From env / `"http://localhost:4318"` | OTLP endpoint |
| `otlp_headers` | `dict` | `None` | Custom headers for OTLP exporter |
| `max_export_batch_size` | `int` | `512` | Max spans per batch |
| `max_queue_size` | `int` | `65536` | Max spans in queue (~64 MB at ~1 KB/span) |
| `schedule_delay_millis` | `int` | `5000` | Delay between batch exports |
| `export_timeout_millis` | `int` | `30000` | Timeout for export operations |
| `propagation_mode` | `str` | `"lean"` | `"lean"` or `"full"` |
| `auto_instrument_packages` | `list` | See below | Packages to auto-instrument |

### Constructor

```python
config = BotanuConfig(
    service_name="my-service",
    deployment_environment="production",
    otlp_endpoint="http://collector:4318",
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
- `FileNotFoundError`: If config file does not exist
- `ValueError`: If YAML is malformed
- `ImportError`: If PyYAML is not installed

**Example:**

```python
config = BotanuConfig.from_yaml("config/botanu.yaml")
```

#### from_file_or_env()

Load config from file if it exists, otherwise use environment variables.

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
  export_timeout_ms: integer # Export timeout

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
  endpoint: ${COLLECTOR_URL:-http://localhost:4318}
  headers:
    Authorization: Bearer ${API_TOKEN}
```

Syntax:
- `${VAR_NAME}` - Required variable
- `${VAR_NAME:-default}` - Variable with default value

---

## enable()

Bootstrap function to initialise the SDK.

```python
from botanu import enable

enable(
    service_name: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    environment: Optional[str] = None,
    auto_instrumentation: bool = True,
    propagators: Optional[List[str]] = None,
    log_level: str = "INFO",
    config: Optional[BotanuConfig] = None,
    config_file: Optional[str] = None,
) -> bool
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `service_name` | `str` | From env | Service name |
| `otlp_endpoint` | `str` | From env | OTLP endpoint URL |
| `environment` | `str` | From env | Deployment environment |
| `auto_instrumentation` | `bool` | `True` | Enable auto-instrumentation |
| `propagators` | `list[str]` | `["tracecontext", "baggage"]` | Propagator list |
| `log_level` | `str` | `"INFO"` | Logging level |
| `config` | `BotanuConfig` | `None` | Pre-built configuration (overrides individual params) |
| `config_file` | `str` | `None` | Path to YAML config file |

### Returns

`True` if successfully initialised, `False` if already initialised.

### Behaviour

1. Creates/merges `BotanuConfig`
2. Configures `TracerProvider` with `RunContextEnricher`
3. Sets up OTLP exporter
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

#### From environment only

```python
from botanu import enable

# Reads OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT, etc.
enable()
```

---

## disable()

Disable the SDK and clean up resources.

```python
from botanu import disable

disable() -> None
```

### Behaviour

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
| `BOTANU_AUTO_DETECT_RESOURCES` | Auto-detect cloud resources | `"true"` |
| `BOTANU_CONFIG_FILE` | Path to YAML config file | None |
| `BOTANU_COLLECTOR_ENDPOINT` | Override for OTLP endpoint | None |
| `BOTANU_MAX_QUEUE_SIZE` | Override max queue size | `65536` |
| `BOTANU_MAX_EXPORT_BATCH_SIZE` | Override max batch size | `512` |
| `BOTANU_EXPORT_TIMEOUT_MILLIS` | Override export timeout | `30000` |

---

## RunContext

Model for run metadata. Created automatically by `@botanu_workflow` and
`run_botanu`.

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
    workflow: str,
    event_id: str,
    customer_id: str,
    workflow_version: Optional[str] = None,
    environment: Optional[str] = None,
    tenant_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    root_run_id: Optional[str] = None,
    attempt: int = 1,
    retry_of_run_id: Optional[str] = None,
    deadline_seconds: Optional[float] = None,
) -> RunContext
```

#### create_retry()

Create a retry context from a previous run.

```python
@classmethod
def create_retry(cls, previous: RunContext) -> RunContext
```

#### from_baggage()

Reconstruct context from baggage dictionary.

```python
@classmethod
def from_baggage(cls, baggage: Dict[str, str]) -> Optional[RunContext]
```

### Instance Methods

#### to_baggage_dict()

Serialise to baggage format.

```python
def to_baggage_dict(self, lean_mode: Optional[bool] = None) -> Dict[str, str]
```

#### to_span_attributes()

Serialise to span attributes.

```python
def to_span_attributes(self) -> Dict[str, Union[str, float, int, bool]]
```

#### complete()

Mark the run as complete.

```python
def complete(
    self,
    status: RunStatus,
    reason_code: Optional[str] = None,
    error_class: Optional[str] = None,
    value_type: Optional[str] = None,
    value_amount: Optional[float] = None,
    confidence: Optional[float] = None,
) -> None
```

#### is_past_deadline()

```python
def is_past_deadline(self) -> bool
```

#### is_cancelled()

```python
def is_cancelled(self) -> bool
```

#### request_cancellation()

```python
def request_cancellation(self, reason: str = "user") -> None
```

#### remaining_time_seconds()

```python
def remaining_time_seconds(self) -> Optional[float]
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | Unique UUIDv7 identifier |
| `workflow` | `str` | Workflow name |
| `event_id` | `str` | Business event identifier |
| `customer_id` | `str` | Customer identifier |
| `environment` | `str` | Deployment environment |
| `workflow_version` | `str` | Version hash |
| `tenant_id` | `str` | Tenant identifier |
| `parent_run_id` | `str` | Parent run ID |
| `root_run_id` | `str` | Root run ID (same as `run_id` for first attempt) |
| `attempt` | `int` | Attempt number |
| `retry_of_run_id` | `str` | Run ID of the previous attempt |
| `start_time` | `datetime` | Run start time |
| `deadline` | `float` | Absolute deadline (epoch seconds) |
| `cancelled` | `bool` | Whether the run is cancelled |
| `outcome` | `RunOutcome` | Recorded outcome |

---

## RunStatus

Enum for run outcome status.

```python
from botanu.models.run_context import RunStatus

class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELED = "canceled"
```

## See Also

- [Configuration Guide](../getting-started/configuration.md) - Configuration how-to
- [Architecture](../concepts/architecture.md) - SDK design
- [Existing OTel Setup](../integration/existing-otel.md) - Integration patterns
