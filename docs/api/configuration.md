# Configuration API Reference

## BotanuConfig

Dataclass for SDK configuration.

```python
from botanu.sdk.config import BotanuConfig
```

### Fields

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `service_name` | `str` | From env / `"unknown_service"` | Service name |
| `service_version` | `str` | From env | Service version |
| `service_namespace` | `str` | From env | Service namespace |
| `deployment_environment` | `str` | From env / `"production"` | Deployment environment |
| `auto_detect_resources` | `bool` | `True` | Auto-detect cloud resources |
| `otlp_endpoint` | `str` | From env / auto-configured when `BOTANU_API_KEY` is set / `"http://localhost:4318"` | OTLP endpoint |
| `otlp_headers` | `dict` | `None` | Custom headers for OTLP exporter — always honored |
| `content_capture_rate` | `float` | `0.10` | Prompt/response capture rate (0.0–1.0). Default 10% sample. See [Content Capture](../tracking/content-capture.md). |
| `pii_scrub_enabled` | `bool` | `True` | In-process PII scrub of captured content |
| `pii_scrub_use_presidio` | `bool` | `False` | Add Microsoft Presidio NER to the scrub pipeline |
| `max_export_batch_size` | `int` | `512` | Max spans per batch |
| `max_queue_size` | `int` | `65536` | Max spans in queue (~64 MB at ~1 KB/span) |
| `schedule_delay_millis` | `int` | `5000` | Delay between batch exports |
| `export_timeout_millis` | `int` | `30000` | Timeout for export operations |
| `auto_instrument_packages` | `list` | See below | Packages to auto-instrument |

`BOTANU_API_KEY` is not a field on the dataclass. When the env var is set, `BotanuConfig` auto-configures `otlp_endpoint` to `https://ingest.botanu.ai` and injects the bearer token into `otlp_headers` — but only for botanu-trusted hosts (any `*.botanu.ai` plus `localhost`).

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
  name: string
  version: string
  namespace: string
  environment: string

resource:
  auto_detect: boolean

otlp:
  endpoint: string
  headers:
    header-name: value

export:
  batch_size: integer
  queue_size: integer
  delay_ms: integer
  export_timeout_ms: integer

eval:
  content_capture_rate: float
  pii:
    enabled: boolean
    use_presidio: boolean
    replacement: string
    disable_patterns: [string]

auto_instrument_packages:
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

## `disable()`

Flush pending spans and shut down the SDK cleanly. Typically called at application shutdown.

```python
import botanu

botanu.disable()
```

---

## `is_enabled()`

Check if the SDK has been initialised.

```python
import botanu

if botanu.is_enabled():
    ...
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
| `BOTANU_AUTO_DETECT_RESOURCES` | Auto-detect cloud resources | `"true"` |
| `BOTANU_CONFIG_FILE` | Path to YAML config file | None |
| `BOTANU_COLLECTOR_ENDPOINT` | Override for OTLP endpoint | None |
| `BOTANU_MAX_QUEUE_SIZE` | Override max queue size | `65536` |
| `BOTANU_MAX_EXPORT_BATCH_SIZE` | Override max batch size | `512` |
| `BOTANU_EXPORT_TIMEOUT_MILLIS` | Override export timeout | `30000` |

---

## RunContext

Model for run metadata. Created automatically by `botanu.event(...)`.

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
def to_baggage_dict(self) -> Dict[str, str]
```

Always included: `botanu.run_id`, `botanu.workflow`, `botanu.event_id`, `botanu.customer_id`, `botanu.environment`.

Included when set: `botanu.tenant_id`, `botanu.parent_run_id`, `botanu.root_run_id`, `botanu.attempt`, `botanu.retry_of_run_id`, `botanu.deadline`, `botanu.cancelled`.

The `RunContextEnricher` stamps the first seven on downstream spans; the remaining five are for `from_baggage` to reconstruct retry and deadline state across process boundaries.

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
