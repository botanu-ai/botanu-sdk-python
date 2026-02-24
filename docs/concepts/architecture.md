# Architecture

Botanu SDK follows a "thin SDK, smart collector" architecture. The SDK does minimal work in your application's hot path, delegating heavy processing to the OpenTelemetry Collector.

## Design Principles

### 1. Minimal Hot-Path Overhead

The SDK only performs lightweight operations during request processing:
- Generate UUIDv7 `run_id`
- Read/write W3C Baggage
- Record token counts as span attributes

**Target overhead**: < 0.5ms per request

### 2. OTel-Native

Built on OpenTelemetry primitives, not alongside them:
- Uses standard `TracerProvider`
- Standard `SpanProcessor` for enrichment
- Standard OTLP export
- W3C Baggage for propagation

### 3. Collector-Side Processing

Heavy operations happen in the OTel Collector:
- PII redaction
- Cost calculation from token counts
- Vendor normalization
- Cardinality management
- Aggregation and sampling


## SDK Components

### BotanuConfig

Central configuration for the SDK:

```python
@dataclass
class BotanuConfig:
    service_name: str
    deployment_environment: str
    otlp_endpoint: str
    propagation_mode: str  # "lean" or "full"
    auto_instrument_packages: List[str]
```

### RunContext

Holds run metadata and provides serialization:

```python
@dataclass
class RunContext:
    run_id: str
    root_run_id: str
    workflow: str
    event_id: str
    customer_id: str
    attempt: int
    # ...
```

### RunContextEnricher

The only span processor in the SDK. Reads baggage, writes to spans:

```python
class RunContextEnricher(SpanProcessor):
    def on_start(self, span, parent_context):
        for key in self._baggage_keys:
            value = baggage.get_baggage(key, parent_context)
            if value:
                span.set_attribute(key, value)
```

### Tracking Helpers

Context managers for manual instrumentation:

- `track_llm_call()` - LLM/model operations
- `track_db_operation()` - Database operations
- `track_storage_operation()` - Object storage operations
- `track_messaging_operation()` - Message queue operations

## Data Flow

### 1. Run Initiation

```python
@botanu_workflow("process", event_id="evt-001", customer_id="cust-42")
def do_work():
    pass
```

1. Generate UUIDv7 `run_id`
2. Create `RunContext`
3. Set baggage in current context
4. Start root span with run attributes

### 2. Context Propagation

```python
# Within the run
response = requests.get("https://api.example.com")
```

1. HTTP instrumentation reads current context
2. Baggage is injected into request headers
3. Downstream service extracts baggage
4. Context continues propagating

### 3. Span Enrichment

Every span (including auto-instrumented):

1. `RunContextEnricher.on_start()` is called
2. Reads `botanu.run_id` from baggage
3. Writes to span attributes
4. Span is exported with run context

### 4. Export and Processing

1. `BatchSpanProcessor` batches spans
2. `OTLPSpanExporter` sends to collector
3. Collector processes (cost calc, PII redaction)
4. Spans written to backend

## Why This Architecture?

### SDK Stays Thin

| Operation | Location | Reason |
|-----------|----------|--------|
| run_id generation | SDK | Must be synchronous |
| Baggage propagation | SDK | Process-local |
| Token counting | SDK | Available at call site |
| Cost calculation | Collector | Pricing tables change |
| PII redaction | Collector | Consistent policy |
| Aggregation | Collector | Reduces data volume |

### No Vendor Lock-in

- Standard OTel export format
- Any OTel-compatible backend works
- Collector processors are configurable

### Minimal Dependencies

Core SDK only requires `opentelemetry-api`:

```toml
dependencies = [
    "opentelemetry-api >= 1.20.0",
]
```

Full SDK adds export capabilities:

```toml
[project.optional-dependencies]
sdk = [
    "opentelemetry-sdk >= 1.20.0",
    "opentelemetry-exporter-otlp-proto-http >= 1.20.0",
]
```

## Integration Points

### Existing TracerProvider

If you already have OTel configured:

```python
from opentelemetry import trace
from botanu.processors.enricher import RunContextEnricher

# Add our processor to your existing provider
provider = trace.get_tracer_provider()
provider.add_span_processor(RunContextEnricher())
```

### Existing Instrumentation

Botanu works alongside existing instrumentation:

```python
# Your existing setup
from opentelemetry.instrumentation.requests import RequestsInstrumentor
RequestsInstrumentor().instrument()

# Add Botanu
from botanu import enable
enable(service_name="my-service")

# Both work together - requests are instrumented AND get run_id
```

## Performance Characteristics

| Operation | Typical Latency |
|-----------|-----------------|
| `generate_run_id()` | < 0.01ms |
| `RunContextEnricher.on_start()` | < 0.05ms |
| `track_llm_call()` overhead | < 0.1ms |
| Baggage injection | < 0.01ms |

Total SDK overhead per request: **< 0.5ms**

## See Also

- [Run Context](run-context.md) - RunContext model details
- [Context Propagation](context-propagation.md) - How context flows
- [Collector Configuration](../integration/collector.md) - Collector setup
